"""OCR 深审第二轮：提醒链路（UTC 口径 / 接收人解析 / 用户隔离）。

- reminder_engine: 用本机时区 datetime.now() 与库中 UTC 时间比较 → 非 UTC 主机
  （UTC+8）阈值与 elapsed_hours 整体偏移 8 小时；审批提醒未解析接收人 →
  orchestrator 因 messages.user_id NOT NULL 全部跳过。
- reminder_orchestrator.list_reminders: 无 user 维度 → 任意登录用户可见他人提醒。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.base import _utcnow
from app.services.reminder_engine import (
    _approval_recipient,
    _as_utc,
    _elapsed_hours,
    scan_approaching_approvals,
    scan_overtime_approvals,
)


def _task(task_id=1, created_at=None, approver=5, submitter=7, title=None):
    return SimpleNamespace(
        id=task_id,
        title=title,
        created_at=created_at,
        current_approver_id=approver,
        submitter_id=submitter,
        status="pending",
    )


def _db_with(tasks):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = tasks
    return db


class TestUtcHelpers:
    def test_elapsed_hours_treats_naive_db_value_as_utc(self):
        # SQLite 读回 created_at 是 naive，但语义是 UTC
        created = (_utcnow() - timedelta(hours=72)).replace(tzinfo=None)
        assert abs(_elapsed_hours(created) - 72.0) < 0.2

    def test_elapsed_hours_none_is_zero(self):
        assert _elapsed_hours(None) == 0.0

    def test_as_utc_converts_aware_timezone(self):
        local = datetime(2026, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=8)))
        assert _as_utc(local) == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


class TestApprovalRecipientResolution:
    def test_current_approver_wins(self):
        assert _approval_recipient(_task(approver=42, submitter=7)) == 42

    def test_falls_back_to_submitter(self):
        assert _approval_recipient(_task(approver=None, submitter=7)) == 7

    def test_returns_none_when_no_recipient(self):
        assert _approval_recipient(_task(approver=None, submitter=None)) is None


class TestApprovalScansCarryRecipient:
    def test_overtime_scan_sets_user_id_and_utc_elapsed(self):
        created = (_utcnow() - timedelta(hours=72)).replace(tzinfo=None)
        results = scan_overtime_approvals(_db_with([_task(created_at=created, approver=42)]), hours_threshold=48)
        assert len(results) == 1
        assert results[0]["user_id"] == 42
        assert abs(results[0]["elapsed_hours"] - 72.0) < 0.2

    def test_overtime_scan_recipient_none_when_unknown(self):
        created = (_utcnow() - timedelta(hours=72)).replace(tzinfo=None)
        results = scan_overtime_approvals(
            _db_with([_task(created_at=created, approver=None, submitter=None)])
        )
        assert results[0]["user_id"] is None

    def test_approaching_scan_sets_user_id(self):
        created = (_utcnow() - timedelta(hours=40)).replace(tzinfo=None)
        results = scan_approaching_approvals(
            _db_with([_task(created_at=created, approver=None, submitter=9)])
        )
        assert len(results) == 1
        assert results[0]["user_id"] == 9
        assert results[0]["type"] == "approval_approaching"
