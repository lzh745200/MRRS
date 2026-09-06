"""订阅分发服务测试：next_run_at 纯函数确定性 + dispatch 到期扫描。

墙钟纪律（CI#84 教训）：next_run_at 是纯函数，全部用固定 datetime 断言，
任何用例不得依赖 datetime.now()。
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.subscription_dispatch_service import (
    SubscriptionDispatchService,
    next_run_at,
)


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


class TestNextRunAtDaily:
    def test_same_day_later_time(self):
        base = _dt("2026-09-06 07:00")
        assert next_run_at("daily", None, "08:00", base) == _dt("2026-09-06 08:00")

    def test_time_already_passed_goes_next_day(self):
        base = _dt("2026-09-06 10:00")
        assert next_run_at("daily", None, "08:00", base) == _dt("2026-09-07 08:00")

    def test_send_time_invalid_falls_back_0800(self):
        base = _dt("2026-09-06 09:00")
        assert next_run_at("daily", None, "25:99", base) == _dt("2026-09-07 08:00")

    def test_send_time_none_defaults_0800(self):
        base = _dt("2026-09-06 09:00")
        assert next_run_at("daily", None, None, base) == _dt("2026-09-07 08:00")

    def test_send_time_with_seconds(self):
        base = _dt("2026-09-06 06:30")
        assert next_run_at("daily", None, "07:15:30", base) == datetime(2026, 9, 6, 7, 15)


class TestNextRunAtWeekly:
    def test_same_weekday_later_time(self):
        # 2026-09-07 是周一；base 周一 05:00，send_day=1（周一）06:30 → 当天
        base = _dt("2026-09-07 05:00")
        assert next_run_at("weekly", 1, "06:30", base) == _dt("2026-09-07 06:30")

    def test_same_weekday_time_passed_next_week(self):
        base = _dt("2026-09-07 10:00")
        assert next_run_at("weekly", 1, "06:30", base) == _dt("2026-09-14 06:30")

    def test_later_in_week(self):
        # 周五 09-11 → send_day=7（周日）09-13
        base = _dt("2026-09-11 10:00")
        assert next_run_at("weekly", 7, "06:30", base) == _dt("2026-09-13 06:30")

    def test_earlier_in_week_wraps_to_next_week(self):
        # 周日 09-13 10:00 → send_day=1（周一）→ 下周一 09-14
        base = _dt("2026-09-13 10:00")
        assert next_run_at("weekly", 1, "06:30", base) == _dt("2026-09-14 06:30")

    def test_send_day_none_defaults_monday(self):
        base = _dt("2026-09-11 10:00")  # 周五
        assert next_run_at("weekly", None, "06:30", base) == _dt("2026-09-14 06:30")

    def test_send_day_out_of_range_falls_back_monday(self):
        base = _dt("2026-09-11 10:00")  # 周五
        assert next_run_at("weekly", 9, "06:30", base) == _dt("2026-09-14 06:30")


class TestNextRunAtMonthly:
    def test_same_month_future_day(self):
        base = _dt("2026-03-15 10:00")
        assert next_run_at("monthly", 20, "08:00", base) == _dt("2026-03-20 08:00")

    def test_day_passed_next_month(self):
        base = _dt("2026-03-21 10:00")
        assert next_run_at("monthly", 20, "08:00", base) == _dt("2026-04-20 08:00")

    def test_day_31_clamped_in_february(self):
        # base=1 月 31 日之后 → 2 月无 31 号钳制为 28
        base = _dt("2026-01-31 10:00")
        assert next_run_at("monthly", 31, "08:00", base) == _dt("2026-02-28 08:00")

    def test_day_31_in_leap_february(self):
        base = _dt("2028-01-31 10:00")  # 2028 闰年
        assert next_run_at("monthly", 31, "08:00", base) == _dt("2028-02-29 08:00")

    def test_clamped_day_in_clamped_month_counts_as_due_next_month(self):
        # base=02-28 08:00（恰为 2 月钳制日已发）→ 下一次 3-31
        base = _dt("2026-02-28 08:00")
        assert next_run_at("monthly", 31, "08:00", base) == _dt("2026-03-31 08:00")

    def test_year_rollover(self):
        base = _dt("2026-12-20 10:00")
        assert next_run_at("monthly", 20, "08:00", base) == _dt("2027-01-20 08:00")

    def test_send_day_none_defaults_1st(self):
        base = _dt("2026-03-05 10:00")
        assert next_run_at("monthly", None, "08:00", base) == _dt("2026-04-01 08:00")


class TestNextRunAtQuarterly:
    def test_same_quarter_future(self):
        base = _dt("2026-01-05 10:00")
        assert next_run_at("quarterly", 15, "08:00", base) == _dt("2026-01-15 08:00")

    def test_same_quarter_passed_next_quarter(self):
        base = _dt("2026-01-20 10:00")
        assert next_run_at("quarterly", 15, "08:00", base) == _dt("2026-04-15 08:00")

    def test_between_quarters_skips_to_next(self):
        # 2 月不在季度首月集合 → 本季 1-15 已过 → 下一季 4-15
        base = _dt("2026-02-10 10:00")
        assert next_run_at("quarterly", 15, "08:00", base) == _dt("2026-04-15 08:00")

    def test_year_rollover(self):
        base = _dt("2026-11-20 10:00")
        assert next_run_at("quarterly", 15, "08:00", base) == _dt("2027-01-15 08:00")


class TestNextRunAtInvalid:
    @pytest.mark.parametrize("bad", ["", "yearly", None])
    def test_unknown_frequency_raises(self, bad):
        with pytest.raises(ValueError):
            next_run_at(bad, 1, "08:00", _dt("2026-09-06 10:00"))


# ════════════════ dispatch_due_subscriptions ════════════════


def _make_sub(
    sub_id=1,
    user_id=7,
    frequency="daily",
    send_day=None,
    send_time="08:00",
    last_sent_at=None,
    created_at=datetime(2026, 9, 1, 8, 0),
    is_active=True,
    format="xlsx",
    output_dir=None,
):
    sub = MagicMock()
    sub.id = sub_id
    sub.user_id = user_id
    sub.name = f"订阅{sub_id}"
    sub.report_type = "comprehensive"
    sub.format = format
    sub.frequency = frequency
    sub.send_day = send_day
    sub.send_time = send_time
    sub.last_sent_at = last_sent_at
    sub.created_at = created_at
    sub.is_active = is_active
    sub.output_dir = output_dir
    return sub


@pytest.fixture
def dispatch_env(tmp_path):
    """构造 dispatch 依赖环境：假 db + mock 生成 IO + 固定 uploads 路径。"""
    from app.models.user import User

    owner = MagicMock(spec=User)
    owner.id = 7

    service = SubscriptionDispatchService()
    written = {}

    async def fake_generate(db, sub, user, now):
        from pathlib import Path

        out_dir = Path(tmp_path) / "subscription_reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"subscription-{sub.id}.xlsx"
        file_path.write_bytes(b"xlsx-bytes")
        sub.last_sent_at = now
        written[sub.id] = str(file_path)
        return {"file_name": file_path.name, "file_path": str(file_path), "size": 10}

    service.generate_for_subscription = AsyncMock(side_effect=fake_generate)
    return service, owner, written


class TestDispatchDueSubscriptions:
    @pytest.mark.asyncio
    async def test_due_subscription_dispatched(self, dispatch_env):
        service, owner, written = dispatch_env
        db = MagicMock()
        sub = _make_sub(created_at=datetime(2026, 9, 1, 8, 0))
        db.query.return_value.filter.return_value.all.return_value = [sub]
        db.query.return_value.filter.return_value.first.return_value = owner

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 10, 8, 0))

        assert stats == {"dispatched": 1, "skipped": 0, "failed": 0}
        assert 1 in written
        assert sub.last_sent_at == datetime(2026, 9, 10, 8, 0)

    @pytest.mark.asyncio
    async def test_not_due_skipped(self, dispatch_env):
        service, owner, written = dispatch_env
        db = MagicMock()
        # created_at=09-01 daily → 到期应为 09-02；now=09-01 09:00 未到期
        sub = _make_sub(created_at=datetime(2026, 9, 1, 8, 0))
        db.query.return_value.filter.return_value.all.return_value = [sub]

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 1, 9, 0))

        assert stats == {"dispatched": 0, "skipped": 1, "failed": 0}
        assert written == {}

    @pytest.mark.asyncio
    async def test_recently_sent_not_redispatched_same_cycle(self, dispatch_env):
        """last_sent_at=今天 08:00（daily 08:00 已发）→ 下一基准明天 08:00 → now=当天 20:00 不重发。"""
        service, owner, written = dispatch_env
        db = MagicMock()
        sub = _make_sub(
            frequency="daily", send_time="08:00",
            last_sent_at=datetime(2026, 9, 10, 8, 0),
        )
        db.query.return_value.filter.return_value.all.return_value = [sub]

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 10, 20, 0))

        assert stats == {"dispatched": 0, "skipped": 1, "failed": 0}

    @pytest.mark.asyncio
    async def test_inactive_filtered_at_query_level(self, dispatch_env):
        """禁用订阅在查询层过滤——断言过滤条件真实包含 is_active 约束。"""
        service, owner, written = dispatch_env
        db = MagicMock()
        # 模拟真实 DB：is_active=True 过滤后禁用订阅不出现在结果里
        db.query.return_value.filter.return_value.all.return_value = []

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 10, 8, 0))

        filter_arg = db.query.return_value.filter.call_args[0][0]
        assert "is_active" in str(filter_arg)
        assert stats == {"dispatched": 0, "skipped": 0, "failed": 0}
        assert written == {}

    @pytest.mark.asyncio
    async def test_one_failure_does_not_block_others(self, dispatch_env):
        service, owner, written = dispatch_env
        db = MagicMock()
        bad = _make_sub(sub_id=1, created_at=datetime(2026, 9, 1, 8, 0))
        good = _make_sub(sub_id=2, created_at=datetime(2026, 9, 1, 8, 0))
        db.query.return_value.filter.return_value.all.return_value = [bad, good]

        async def flaky_generate(db, sub, user, now):
            if sub.id == 1:
                raise RuntimeError("磁盘不可写")
            return await service.generate_for_subscription.side_effect_actual(db, sub, user, now)

        # 用 side_effect 包装：id=1 抛错
        orig = service.generate_for_subscription.side_effect

        async def wrapper(db, sub, user, now):
            if sub.id == 1:
                raise RuntimeError("磁盘不可写")
            return await orig(db, sub, user, now)

        service.generate_for_subscription = AsyncMock(side_effect=wrapper)

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 10, 8, 0))

        assert stats == {"dispatched": 1, "skipped": 0, "failed": 1}
        assert 2 in written and 1 not in written
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_frequency_counted_failed(self, dispatch_env):
        service, owner, written = dispatch_env
        db = MagicMock()
        sub = _make_sub(frequency="yearly", created_at=datetime(2026, 9, 1, 8, 0))
        db.query.return_value.filter.return_value.all.return_value = [sub]

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 10, 8, 0))

        assert stats["failed"] == 1
        db.rollback.assert_called_once()


class TestParseSendTimeErrors:
    def test_non_numeric_time_falls_back(self):
        # _parse_send_time 的 except 分支：非数字小时/分钟回落 08:00
        base = _dt("2026-09-06 09:00")
        assert next_run_at("daily", None, "abc:xy", base) == _dt("2026-09-07 08:00")


class TestQuarterlyCatchupYearRollover:
    def test_q4_missed_rolls_to_next_year_january(self):
        # base=10 月（季度月）已过 send_day → 追到下一季 1 月且跨年（135-136 行）
        base = _dt("2026-10-20 10:00")
        assert next_run_at("quarterly", 15, "08:00", base) == _dt("2027-01-15 08:00")


class TestDispatchNoBase:
    @pytest.mark.asyncio
    async def test_both_timestamps_none_skipped(self, dispatch_env):
        service, owner, written = dispatch_env
        db = MagicMock()
        sub = _make_sub(last_sent_at=None, created_at=None)
        db.query.return_value.filter.return_value.all.return_value = [sub]

        stats = await service.dispatch_due_subscriptions(db, datetime(2026, 9, 10, 8, 0))

        assert stats["skipped"] == 1
        assert written == {}


class TestGenerateForSubscriptionReal:
    """generate_for_subscription 真实执行（不 mock 自身）：导出/落盘/消息/last_sent_at。"""

    def _make_db_and_sub(self, tmp_path, fmt="xlsx", output_dir=None, report_type="comprehensive"):
        sub = _make_sub(format=fmt, output_dir=output_dir)
        sub.report_type = report_type
        sub.year = 2026
        db = MagicMock()
        return db, sub

    @pytest.mark.asyncio
    @pytest.mark.parametrize("fmt,method,ext", [("xlsx", "export_to_excel", "xlsx"), ("pdf", "export_to_pdf", "pdf")])
    async def test_generates_and_delivers(self, monkeypatch, tmp_path, fmt, method, ext):
        from app.services.subscription_dispatch_service import SubscriptionDispatchService
        from app.models.user import User

        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        owner = MagicMock(spec=User)
        owner.id = 7
        db = MagicMock()
        sub = self._make_db_and_sub(tmp_path, fmt=fmt)[1]

        payload = b"report-bytes"
        with patch(
            "app.services.report_service.ReportService",
        ) as MockReportSvc:
            instance = MockReportSvc.return_value
            setattr(instance, method, AsyncMock(return_value=payload))
            with patch("app.services.message_service.MessageService") as MockMsg:
                result = await SubscriptionDispatchService().generate_for_subscription(
                    db, sub, owner, datetime(2026, 9, 10, 8, 0)
                )

        assert result["size"] == len(payload)
        assert result["file_name"].endswith(ext)
        from pathlib import Path

        assert Path(result["file_path"]).read_bytes() == payload
        # 送达语义：last_sent_at 更新 + 站内消息
        assert sub.last_sent_at == datetime(2026, 9, 10, 8, 0)
        MockMsg.return_value.send_system_message.assert_called_once()
        kwargs = MockMsg.return_value.send_system_message.call_args.kwargs
        assert kwargs["user_id"] == 7
        assert "订阅1" in kwargs["title"]

    @pytest.mark.asyncio
    async def test_custom_output_dir_wins_over_uploads(self, monkeypatch, tmp_path):
        from app.services.subscription_dispatch_service import SubscriptionDispatchService
        from app.models.user import User

        custom = tmp_path / "custom_out"
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        owner = MagicMock(spec=User)
        db = MagicMock()
        sub = self._make_db_and_sub(tmp_path, output_dir=str(custom))

        with patch("app.services.report_service.ReportService") as MockReportSvc:
            MockReportSvc.return_value.export_to_excel = AsyncMock(return_value=b"data")
            with patch("app.services.message_service.MessageService"):
                result = await SubscriptionDispatchService().generate_for_subscription(
                    db, sub, owner, datetime(2026, 9, 10, 8, 0)
                )

        assert result["file_path"].startswith(str(custom))
        assert (custom / result["file_name"]).exists()
