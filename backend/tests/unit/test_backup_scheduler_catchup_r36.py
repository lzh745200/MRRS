# -*- coding: utf-8 -*-
"""R36 · 备份调度启动补跑（`app/services/backup_scheduler.py`）

背景：离线单机常见"机器每天只开机几小时 / 刚好错过 02:00"，纯每日定时会让
自动备份长期不执行（``last_backup_time`` 一直陈旧），磁盘无可用备份。启动时
补跑一次是这类场景的最小修复。

幂等要求（本文件的核心断言）：补跑判定必须与 ``auto_backup_job`` 内部的
间隔 early-return **完全一致**（同配置键 ``backup_interval_days``、同
``last_backup_time``、同 ``parse_local_wallclock`` 归一）——补跑写入新的
``last_backup_time`` 之后，当日 02:00 的 daily 任务会正常跳过，不会重复备份。
"""
from datetime import datetime

import pytest
from unittest.mock import MagicMock, patch

import app.services.backup_scheduler as bm

# autouse fixture 会把 _is_pytest_process 打成 False（模拟生产语义）；
# 这里留存真实实现，供「保护开关」用例断言。
_REAL_IS_PYTEST = bm._is_pytest_process


class FakeTimer:
    """替代 threading.Timer：记录回调而不真正起线程。"""

    instances = []

    def __init__(self, delay, callback, *args, **kwargs):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.name = ""
        self._alive = False
        FakeTimer.instances.append(self)

    def start(self):
        self._alive = True

    def cancel(self):
        self._alive = False

    def is_alive(self):
        return self._alive


class FakeDateTime:
    """固定"当前时间"，供补跑判定使用。"""

    fixed_now = datetime(2026, 10, 24, 9, 0, 0)

    @classmethod
    def now(cls):
        return cls.fixed_now


@pytest.fixture(autouse=True)
def _isolate_scheduler_state():
    bm.stop_backup_scheduler()
    bm._stopping.clear()  # stop() 会置位停止标志；本文件多数用例需要「运行中」语义
    FakeTimer.instances = []
    FakeDateTime.fixed_now = datetime(2026, 10, 24, 9, 0, 0)
    # 真实生产语义（非 pytest）下验证补跑链路；保护开关本身另有用例覆盖
    with patch.object(bm, "_is_pytest_process", return_value=False):
        yield
    bm.stop_backup_scheduler()
    FakeTimer.instances = []


def _db_row(value):
    row = MagicMock()
    row.value = value
    return row


def _db_with_last_backup(value):
    """构造只响应 last_backup_time 查询的 mock 会话。"""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        _db_row(value) if value is not None else None
    )
    return db


class TestLastBackupTimeRead:
    def test_reads_naive_local_wallclock_value(self):
        """写入端是 naive 本地墙钟（datetime.now().isoformat()），读取端必须还原。"""
        db = _db_with_last_backup("2026-10-20 02:00:00")
        assert bm._last_backup_time(db) == datetime(2026, 10, 20, 2, 0, 0)

    def test_offset_value_is_normalized_to_naive(self):
        """带时区偏移的脏值 → 归一成 naive（否则 naive-aware 相减抛 TypeError）。"""
        db = _db_with_last_backup("2026-10-20T02:00:00+08:00")
        parsed = bm._last_backup_time(db)
        assert parsed is not None
        assert parsed.tzinfo is None

    def test_missing_row_returns_none(self):
        assert bm._last_backup_time(_db_with_last_backup(None)) is None

    def test_empty_string_returns_none(self):
        assert bm._last_backup_time(_db_with_last_backup("")) is None

    def test_non_string_value_returns_none(self):
        db = MagicMock()
        row = MagicMock()
        row.value = 12345
        db.query.return_value.filter.return_value.first.return_value = row
        assert bm._last_backup_time(db) is None

    def test_dirty_value_returns_none_instead_of_raising(self):
        """脏值（无法解析）视为"从未备份"，不得抛异常炸掉调度。"""
        assert bm._last_backup_time(_db_with_last_backup("not-a-timestamp")) is None


class TestCatchupDue:
    def test_never_backed_up_is_due(self):
        db = _db_with_last_backup(None)
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_int_config", return_value=1):
            due, interval_days = bm._backup_catchup_due(db=db)
        assert due is True
        assert interval_days == 1

    def test_older_than_interval_is_due(self):
        db = _db_with_last_backup("2026-10-20 02:00:00")  # 4 天前
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_int_config", return_value=1):
            due, interval_days = bm._backup_catchup_due(db=db)
        assert due is True
        assert interval_days == 1

    def test_within_interval_is_not_due(self):
        db = _db_with_last_backup("2026-10-24 03:00:00")  # 6 小时前
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_int_config", return_value=1):
            due, interval_days = bm._backup_catchup_due(db=db)
        assert due is False
        assert interval_days == 1

    def test_respects_configured_interval_days(self):
        """间隔取自配置（与 auto_backup_job 同键），3 天间隔时 2 天前不够触发。"""
        db = _db_with_last_backup("2026-10-22 02:00:00")
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_int_config", return_value=3):
            due, interval_days = bm._backup_catchup_due(db=db)
        assert due is False
        assert interval_days == 3

    def test_opens_own_session_when_db_not_given(self):
        cm = MagicMock()
        cm.__enter__.return_value = _db_with_last_backup("2026-10-20 02:00:00")
        cm.__exit__.return_value = False
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_db_context", return_value=cm), \
             patch.object(bm, "get_int_config", return_value=1):
            due, _ = bm._backup_catchup_due()
        assert due is True
        cm.__exit__.assert_called_once()


class TestCatchupJob:
    def test_runs_backup_once_when_due(self):
        with patch.object(bm, "_backup_catchup_due", return_value=(True, 1)), \
             patch.object(bm, "_run_scheduler_job") as run:
            bm._run_backup_catchup_job()

        run.assert_called_once_with(bm.auto_backup_job)

    def test_skips_when_within_interval(self):
        with patch.object(bm, "_backup_catchup_due", return_value=(False, 1)), \
             patch.object(bm, "_run_scheduler_job") as run:
            bm._run_backup_catchup_job()

        run.assert_not_called()

    def test_stopping_prevents_any_backup(self):
        """停止语义：_stopping 已置位时连判定都不做（不做幽灵 DB 写）。"""
        bm._stopping.set()
        with patch.object(bm, "_backup_catchup_due") as due, \
             patch.object(bm, "_run_scheduler_job") as run:
            bm._run_backup_catchup_job()

        due.assert_not_called()
        run.assert_not_called()

    def test_due_check_failure_is_swallowed(self):
        """判定阶段异常不得让调度线程崩溃（记 ERROR，下个周期/下次启动再试）。"""
        with patch.object(bm, "_backup_catchup_due", side_effect=RuntimeError("db locked")), \
             patch.object(bm, "_run_scheduler_job") as run:
            bm._run_backup_catchup_job()  # 不应抛出

        run.assert_not_called()

    def test_stop_between_decision_and_run_aborts_backup(self):
        """判定到期后、真正开跑前收到停止信号 → 不再写库（优雅关闭语义）。"""

        def _due_then_stop(*_args, **_kwargs):
            bm._stopping.set()
            return True, 1

        with patch.object(bm, "_backup_catchup_due", side_effect=_due_then_stop), \
             patch.object(bm, "_run_scheduler_job") as run:
            bm._run_backup_catchup_job()

        run.assert_not_called()

    def test_pytest_process_guard_prevents_real_backup(self):
        """保护开关：pytest 进程内绝不落真实备份（定时器会在用例间触发）。"""
        with patch.object(bm, "_is_pytest_process", return_value=True), \
             patch.object(bm, "_backup_catchup_due") as due, \
             patch.object(bm, "_run_scheduler_job") as run:
            bm._run_backup_catchup_job()

        due.assert_not_called()
        run.assert_not_called()

    def test_pytest_process_detected_via_sys_modules(self):
        """真实实现：本测试进程内 _is_pytest_process() 必须为 True。"""
        assert _REAL_IS_PYTEST() is True

    def test_idempotent_second_check_skips(self):
        """补跑成功后 last_backup_time 被刷新 → 再次判定不再补跑（不重复备份）。"""
        db = _db_with_last_backup("2026-10-20 02:00:00")
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_int_config", return_value=1):
            assert bm._backup_catchup_due(db=db)[0] is True

        # 补跑写入新时间后的同一判定
        db_after = _db_with_last_backup("2026-10-24 09:00:00")
        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm, "get_int_config", return_value=1):
            assert bm._backup_catchup_due(db=db_after)[0] is False


class TestCatchupRegistration:
    def test_start_registers_one_shot_catchup_timer(self):
        with patch.object(bm.threading, "Timer", FakeTimer):
            bm.start_backup_scheduler()

        names = [t.name for t in FakeTimer.instances]
        assert "scheduler-backup_catchup" in names

    def test_catchup_timer_is_one_shot_and_registered(self):
        """一次性：触发后不得自我重排；且必须登记在 _timers（stop 可 cancel）。"""
        with patch.object(bm.threading, "Timer", FakeTimer):
            bm.start_backup_scheduler()

        timer = next(t for t in FakeTimer.instances if t.name == "scheduler-backup_catchup")
        assert timer in bm._timers
        count_before = len(FakeTimer.instances)

        # 补跑真正执行时会被 _run_scheduler_job 转成独立事件循环跑 auto_backup_job；
        # 这里替换执行器即可验证"触发了一次"，不真的落备份（避免污染测试库/磁盘）。
        with patch.object(bm, "_run_scheduler_job") as run:
            timer.callback()

        run.assert_called_once_with(bm._run_backup_catchup_job)
        assert len(FakeTimer.instances) == count_before, "一次性补跑不得重排新 Timer"

    def test_catchup_skipped_after_stop(self):
        with patch.object(bm.threading, "Timer", FakeTimer):
            bm.start_backup_scheduler()
        timer = next(t for t in FakeTimer.instances if t.name == "scheduler-backup_catchup")

        bm._stopping.set()
        with patch.object(bm, "_run_scheduler_job") as run:
            timer.callback()

        run.assert_not_called()

    def test_start_source_wires_catchup(self):
        """接线断言：start_backup_scheduler 必须登记启动补跑。"""
        import inspect

        src = inspect.getsource(bm.start_backup_scheduler)
        assert "_schedule_backup_catchup(" in src
