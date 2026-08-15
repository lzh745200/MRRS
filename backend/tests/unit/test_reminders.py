"""统一提醒(T3.2): reminder_orchestrator 扫描接线/幂等/API"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _msg(**kw):
    m = SimpleNamespace(
        id=1, message_type="approval_overtime", title="审批超时",
        content="内容", link="approval_overtime:5",
        is_read=False,
        created_at=None,
    )
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def test_run_reminder_scans_creates_messages():
    from app.services.reminder_orchestrator import run_reminder_scans

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_db

    scan_results = [
        [{"type": "approval_overtime", "entity_id": 5, "title": "审批A", "elapsed_hours": 50, "user_id": 1}],
        [{"type": "deadline_warning", "entity_id": 3, "title": "项目B", "end_date": "2026-09-01", "days_left": 2, "user_id": 2}],
        [{"type": "budget_warning", "entity_id": 9, "title": "经费C", "ratio": 90.5, "user_id": 1}],
    ]

    with patch("app.services.reminder_orchestrator.get_db_context", return_value=ctx):
        with patch("app.core.transaction.safe_commit"):
            with patch("app.services.reminder_engine.scan_overtime_approvals", return_value=scan_results[0]):
                with patch("app.services.reminder_engine.scan_deadline_warnings", return_value=scan_results[1]):
                    with patch("app.services.reminder_engine.scan_budget_warnings", return_value=scan_results[2]):
                        created = run_reminder_scans()
    assert len(created) == 3
    # Message 添加 3 次
    assert mock_db.add.call_count == 3


def test_run_reminder_scans_skips_recipient_unknown():
    """user_id 缺失的提醒跳过而不影响整批（messages.user_id NOT NULL 防护）"""
    from app.services.reminder_orchestrator import run_reminder_scans

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_db

    scan_results = [
        [{"type": "approval_overtime", "entity_id": 5, "title": "无接收人"}],  # user_id 缺失
        [{"type": "deadline_warning", "entity_id": 3, "title": "有接收人", "user_id": 2}],
    ]

    with patch("app.services.reminder_orchestrator.get_db_context", return_value=ctx):
        with patch("app.core.transaction.safe_commit"):
            with patch("app.services.reminder_engine.scan_overtime_approvals", return_value=scan_results[0]):
                with patch("app.services.reminder_engine.scan_deadline_warnings", return_value=scan_results[1]):
                    with patch("app.services.reminder_engine.scan_budget_warnings", return_value=[]):
                        created = run_reminder_scans()
    assert len(created) == 1
    assert mock_db.add.call_count == 1


def test_run_reminder_scans_dedupe():
    from app.services.reminder_orchestrator import run_reminder_scans

    mock_db = MagicMock()
    # 已存在同 link → 跳过
    mock_db.query.return_value.filter.return_value.first.return_value = _msg()
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_db

    with patch("app.services.reminder_orchestrator.get_db_context", return_value=ctx):
        with patch("app.services.reminder_engine.scan_overtime_approvals",
                   return_value=[{"type": "approval_overtime", "entity_id": 5, "title": "A"}]):
            with patch("app.services.reminder_engine.scan_deadline_warnings", return_value=[]):
                with patch("app.services.reminder_engine.scan_budget_warnings", return_value=[]):
                    created = run_reminder_scans()
    assert created == []
    assert mock_db.add.call_count == 0


def test_run_reminder_scans_exception_safe():
    from app.services.reminder_orchestrator import run_reminder_scans

    with patch("app.services.reminder_orchestrator.get_db_context", side_effect=RuntimeError("boom")):
        assert run_reminder_scans() == []


def test_format_reminder_variants():
    from app.services.reminder_orchestrator import _format_reminder

    assert "48" in _format_reminder({"type": "approval_overtime", "elapsed_hours": 48})
    assert "2026-09-01" in _format_reminder({"type": "deadline_warning", "end_date": "2026-09-01", "days_left": 2})
    assert "88" in _format_reminder({"type": "budget_warning", "ratio": 88})
    assert "fallback" in _format_reminder({"type": "unknown", "fallback": "fallback"})


def test_list_reminders():
    from app.services.reminder_orchestrator import list_reminders

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        _msg(id=2, message_type="deadline_warning", is_read=True),
    ]
    with patch("app.core.database.SessionLocal", return_value=mock_db):
        rows = list_reminders(10)
    assert len(rows) == 1
    assert rows[0]["type"] == "deadline_warning"
    assert rows[0]["is_read"] is True
    mock_db.close.assert_called_once()


def test_reminders_api_list():
    from app.main import app
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin")
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.reminder_orchestrator.list_reminders",
            return_value=[{"id": 1, "type": "budget_warning", "title": "x", "is_read": False}],
        ):
            resp = client.get("/api/v1/reminders")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["unread"] == 1
    finally:
        app.dependency_overrides.clear()


def test_reminders_api_scan():
    from app.main import app
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin")
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.reminder_orchestrator.run_reminder_scans",
            return_value=[{"type": "approval_overtime", "entity_id": 1}],
        ):
            resp = client.post("/api/v1/reminders/scan")
        assert resp.status_code == 200
        assert resp.json()["data"]["created"] == 1
    finally:
        app.dependency_overrides.clear()


def test_reminders_scan_requires_admin():
    from app.main import app
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role="user")
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.reminder_orchestrator.run_reminder_scans",
            return_value=[],
        ):
            resp = client.post("/api/v1/reminders/scan")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_reminder_scan_job_registered():
    import app.services.backup_scheduler as bm

    assert hasattr(bm, "reminder_scan_job")
    assert callable(bm.reminder_scan_job)
