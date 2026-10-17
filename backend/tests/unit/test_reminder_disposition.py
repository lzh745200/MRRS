"""提醒处置闭环（w17-001）：服务层 + 编排富化 + 统计。

覆盖：
- 归属校验 fail-closed（无 user_id / 越权 / 不存在 / 非提醒类型）
- 处理 / 忽略 / 延期 / 重新打开（幂等、note 空值、非法天数）
- 审计留痕成功与失败（失败不阻断）
- 列表富化（state/note/snooze_until/entity_id/link、忽略过滤、未处理优先排序）
- summarize_reminders 各分支
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models.message import Message
from app.models.reminder_disposition import ReminderDisposition
from app.models.user import User  # noqa: F401  确保 users 表注册（messages FK）
from app.models.work_log import WorkLog  # noqa: F401  确保 work_logs 表注册
from app.services import reminder_disposition_service as svc
from app.services.reminder_orchestrator import (
    _parse_entity_id,
    list_reminders,
    summarize_reminders,
)
from app.utils.time_utils import utcnow


def _mk_message(db, user_id=7, message_type="approval_overtime", title="审批超时", link=None, **kw):
    msg = Message(
        user_id=user_id,
        message_type=message_type,
        title=title,
        content="提醒内容",
        link=link,
        **kw,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ─────────────────────────── 归属校验 ───────────────────────────


class TestOwnership:
    def test_missing_user_id_is_rejected(self, real_db_session):
        with pytest.raises(svc.ReminderNotFoundError):
            svc.load_owned_reminder(real_db_session, 1, None)

    def test_not_found_is_rejected(self, real_db_session):
        with pytest.raises(svc.ReminderNotFoundError):
            svc.load_owned_reminder(real_db_session, 999, 7)

    def test_other_users_message_is_rejected(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=8)
        with pytest.raises(svc.ReminderNotFoundError):
            svc.load_owned_reminder(real_db_session, msg.id, 7)

    def test_non_reminder_type_is_rejected(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7, message_type="system")
        with pytest.raises(svc.ReminderNotFoundError):
            svc.load_owned_reminder(real_db_session, msg.id, 7)

    def test_null_recipient_is_rejected(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=None)
        with pytest.raises(svc.ReminderNotFoundError):
            svc.load_owned_reminder(real_db_session, msg.id, 7)

    def test_owner_can_load(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        loaded = svc.load_owned_reminder(real_db_session, msg.id, 7)
        assert loaded.id == msg.id


# ─────────────────────────── 处置动作 ───────────────────────────


class TestDispositionActions:
    def test_handle_creates_row_marks_read_and_audits(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        result = svc.handle(real_db_session, msg.id, 7, note="已核实", username="u7")
        assert result["state"] == svc.STATE_HANDLED
        assert result["note"] == "已核实"
        row = real_db_session.query(ReminderDisposition).filter_by(message_id=msg.id).one()
        assert row.state == svc.STATE_HANDLED
        assert row.user_id == 7
        assert row.acted_at is not None
        refreshed = real_db_session.get(Message, msg.id)
        assert refreshed.is_read is True
        assert refreshed.read_at is not None
        log = real_db_session.query(WorkLog).filter(WorkLog.category == "reminder").one()
        assert "已核实" in log.content

    def test_handle_is_idempotent(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7, is_read=True)
        svc.handle(real_db_session, msg.id, 7)
        svc.handle(real_db_session, msg.id, 7, note="再次处理")
        rows = real_db_session.query(ReminderDisposition).filter_by(message_id=msg.id).all()
        assert len(rows) == 1
        assert rows[0].note == "再次处理"

    def test_handle_on_read_message_keeps_read_at(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7, is_read=True)
        assert msg.read_at is None
        svc.handle(real_db_session, msg.id, 7)
        refreshed = real_db_session.get(Message, msg.id)
        # 已读消息不重复写 read_at（_mark_read 的短路分支）
        assert refreshed.read_at is None

    def test_ignore_with_reason(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        result = svc.ignore(real_db_session, msg.id, 7, reason="重复提醒")
        assert result["state"] == svc.STATE_IGNORED
        assert result["note"] == "重复提醒"

    def test_ignore_without_reason_stores_none(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        result = svc.ignore(real_db_session, msg.id, 7)
        assert result["note"] is None

    def test_snooze_sets_future_deadline(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        expected = utcnow() + timedelta(days=7)
        result = svc.snooze(real_db_session, msg.id, 7, days=7)
        assert result["state"] == svc.STATE_OPEN
        assert result["snooze_until"] is not None
        until = datetime.fromisoformat(result["snooze_until"])
        assert abs((until - expected).total_seconds()) < 5

    @pytest.mark.parametrize("days", [0, 91, -1])
    def test_snooze_out_of_range(self, real_db_session, days):
        msg = _mk_message(real_db_session, user_id=7)
        with pytest.raises(svc.InvalidSnoozeDaysError):
            svc.snooze(real_db_session, msg.id, 7, days=days)

    def test_snooze_non_int(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        with pytest.raises(svc.InvalidSnoozeDaysError):
            svc.snooze(real_db_session, msg.id, 7, days="7")  # type: ignore[arg-type]

    def test_reopen_clears_state_and_snooze(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        svc.snooze(real_db_session, msg.id, 7, days=3)
        result = svc.reopen(real_db_session, msg.id, 7, note="仍需跟进")
        assert result["state"] == svc.STATE_OPEN
        assert result["snooze_until"] is None
        assert result["note"] == "仍需跟进"

    def test_reopen_without_note(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        svc.handle(real_db_session, msg.id, 7)
        result = svc.reopen(real_db_session, msg.id, 7)
        assert result["state"] == svc.STATE_OPEN
        assert result["note"] is None

    def test_audit_failure_does_not_block(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        with patch(
            "app.services.work_log_service.write_work_log",
            side_effect=RuntimeError("audit down"),
        ):
            result = svc.handle(real_db_session, msg.id, 7)
        assert result["state"] == svc.STATE_HANDLED
        assert real_db_session.query(ReminderDisposition).filter_by(message_id=msg.id).count() == 1


# ─────────────────────────── 序列化 / 批量加载 ───────────────────────────


class TestSerialization:
    def test_serialize_none_returns_open(self):
        assert svc.serialize_disposition(None) == {
            "state": "open",
            "note": None,
            "snooze_until": None,
            "acted_at": None,
        }

    def test_serialize_row_with_null_state_falls_back_to_open(self):
        row = SimpleNamespace(state=None, note="n", snooze_until=None, acted_at=None)
        out = svc.serialize_disposition(row)
        assert out["state"] == "open"
        assert out["note"] == "n"

    def test_serialize_row_with_values(self, real_db_session):
        msg = _mk_message(real_db_session, user_id=7)
        svc.snooze(real_db_session, msg.id, 7, days=2)
        row = real_db_session.query(ReminderDisposition).filter_by(message_id=msg.id).one()
        out = svc.serialize_disposition(row)
        assert out["snooze_until"] and out["acted_at"]

    def test_load_dispositions_empty_inputs(self, real_db_session):
        assert svc.load_dispositions(real_db_session, [None, None], 7) == {}
        assert svc.load_dispositions(real_db_session, [1], None) == {}
        assert svc.load_dispositions(real_db_session, [], 7) == {}

    def test_load_dispositions_filters_by_user(self, real_db_session):
        mine = _mk_message(real_db_session, user_id=7, title="我的")
        theirs = _mk_message(real_db_session, user_id=8, title="他的")
        svc.handle(real_db_session, mine.id, 7)
        svc.handle(real_db_session, theirs.id, 8)
        loaded = svc.load_dispositions(real_db_session, [mine.id, theirs.id], 7)
        assert set(loaded) == {mine.id}
        assert loaded[mine.id].user_id == 7


# ─────────────────────────── 列表富化 ───────────────────────────


def _q(all_value):
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.all.return_value = all_value
    return q


def _mock_session(messages, dispositions):
    db = MagicMock()
    msg_q = _q(messages)
    disp_q = _q(dispositions)
    db.query.side_effect = lambda model: msg_q if model is Message else disp_q
    return db


class TestListEnrichment:
    def test_entity_id_parsing(self):
        assert _parse_entity_id("approval_overtime:12") == 12
        assert _parse_entity_id(None) is None
        assert _parse_entity_id("no-colon") is None
        assert _parse_entity_id("type:not-a-number") is None

    def test_list_hides_ignored_by_default_and_sorts_pending_first(self):
        m1 = SimpleNamespace(
            id=1, message_type="deadline_warning", title="已处理", content="c",
            created_at=None, is_read=True, link=None,
        )
        m2 = SimpleNamespace(
            id=2, message_type="budget_warning", title="待处理", content="c",
            created_at=None, is_read=False, link="budget_warning:9",
        )
        m3 = SimpleNamespace(
            id=3, message_type="package_reminder", title="已忽略", content="c",
            created_at=None, is_read=False, link=None,
        )
        m4 = SimpleNamespace(id=4, message_type="backup_reminder", title="无 is_read", content="c", created_at=None)
        dispositions = [
            SimpleNamespace(message_id=1, state="handled", note=None, snooze_until=None, acted_at=None),
            SimpleNamespace(message_id=3, state="ignored", note="忽略", snooze_until=None, acted_at=None),
            SimpleNamespace(message_id=4, state="weird", note=None, snooze_until=None, acted_at=None),
        ]
        db = _mock_session([m1, m2, m3, m4], dispositions)
        with patch("app.core.database.SessionLocal", return_value=db):
            items = list_reminders(10, user_id=7)
        assert [i["id"] for i in items] == [2, 4, 1]  # pending(weird 视作 pending) 优先，已忽略被过滤
        assert items[0]["entity_id"] == 9
        assert items[1]["is_read"] is False  # 缺 is_read 属性分支
        assert items[2]["state"] == "handled"

    def test_list_include_ignored_keeps_and_ranks_last(self):
        m3 = SimpleNamespace(
            id=3, message_type="package_reminder", title="已忽略", content="c",
            created_at=None, is_read=False, link=None,
        )
        dispositions = [
            SimpleNamespace(message_id=3, state="ignored", note="忽略", snooze_until=None, acted_at=None),
        ]
        db = _mock_session([m3], dispositions)
        with patch("app.core.database.SessionLocal", return_value=db):
            items = list_reminders(10, user_id=7, include_ignored=True)
        assert len(items) == 1
        assert items[0]["state"] == "ignored"
        assert items[0]["note"] == "忽略"


# ─────────────────────────── 统计 ───────────────────────────


class TestSummarize:
    def test_counts_by_state_and_snooze_window(self):
        future = (utcnow() + timedelta(days=1)).isoformat()
        past = (utcnow() - timedelta(days=1)).isoformat()
        reminders = [
            {"state": "handled"},
            {"state": "ignored"},
            {"state": "open", "snooze_until": future},
            {"state": "open", "snooze_until": past},
            {"state": None, "snooze_until": "not-a-date"},
            {"snooze_until": future},
        ]
        stats = summarize_reminders(reminders)
        # 末项缺 state → 视作 open 且延期未到期，计入 pending/snoozed
        assert stats == {"pending": 4, "handled": 1, "ignored": 1, "snoozed": 2, "total": 6}

    def test_empty_list(self):
        assert summarize_reminders([]) == {
            "pending": 0, "handled": 0, "ignored": 0, "snoozed": 0, "total": 0,
        }
