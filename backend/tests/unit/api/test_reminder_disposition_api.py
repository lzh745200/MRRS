"""提醒处置 API（w17-001）：端点契约 / 越权 / 参数校验 / 错误兜底 / user 维度修复。

关键回归：`GET /reminders` 必须把 current_user.id 传给编排器
（历史缺陷：未传 user_id → fail-closed 恒返回空，提醒中心永远看不到提醒）。
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _mk_message(db, user_id=7, message_type="approval_overtime", title="审批超时"):
    from app.models.message import Message

    msg = Message(user_id=user_id, message_type=message_type, title=title, content="内容")
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@pytest.fixture
def api_client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base
    from app.models.user import User  # noqa: F401  FK 目标表注册
    from app.models.reminder_disposition import ReminderDisposition  # noqa: F401
    from app.models.work_log import WorkLog  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    user = SimpleNamespace(id=7, username="u7", role="admin")

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, session, user, app
    finally:
        app.dependency_overrides = original_overrides
        session.close()
        engine.dispose()


class TestListEndpoint:
    def test_list_passes_user_id_and_stats(self, api_client):
        client, _db, _user, _app = api_client
        items = [
            {"id": 1, "state": "open", "is_read": False, "title": "a"},
            {"id": 2, "state": "handled", "is_read": True, "title": "b"},
        ]
        with patch("app.services.reminder_orchestrator.list_reminders", return_value=items) as mocked:
            resp = client.get("/api/v1/reminders")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert data["unread"] == 1
        assert data["stats"]["pending"] == 1
        assert data["stats"]["handled"] == 1
        # 关键回归：user 维度必须真实传入（修复恒空缺陷）
        assert mocked.call_args.kwargs["user_id"] == 7
        assert mocked.call_args.kwargs["include_ignored"] is False

    def test_list_include_ignored_passthrough(self, api_client):
        client, _db, _user, _app = api_client
        with patch("app.services.reminder_orchestrator.list_reminders", return_value=[]) as mocked:
            resp = client.get("/api/v1/reminders", params={"include_ignored": "true"})
        assert resp.status_code == 200
        assert mocked.call_args.kwargs["include_ignored"] is True

    def test_list_exception_returns_500_not_fake_empty_stats(self, api_client):
        """故障必须外显为 500。

        旧实现 catch 住异常后返回 `200 + items=[] + 全 0 统计`，前端会把
        「提醒服务不可用」显示成「今天没有待办提醒」——故障伪装成真实业务数据，
        用户与审计都无法察觉。本用例原先钉的正是这个旧行为，已随修复一并纠正。
        """
        client, _db, _user, _app = api_client
        with patch(
            "app.services.reminder_orchestrator.list_reminders",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/v1/reminders")
        assert resp.status_code == 500


class TestDispositionEndpoints:
    def test_handle_with_note(self, api_client):
        client, db, _user, _app = api_client
        msg = _mk_message(db)
        resp = client.post(f"/api/v1/reminders/{msg.id}/handle", json={"note": "已核实"})
        assert resp.status_code == 200
        assert resp.json()["data"]["state"] == "handled"
        db.refresh(msg)
        assert msg.is_read is True

    def test_handle_without_body(self, api_client):
        client, db, _user, _app = api_client
        msg = _mk_message(db)
        resp = client.post(f"/api/v1/reminders/{msg.id}/handle")
        assert resp.status_code == 200
        assert resp.json()["data"]["state"] == "handled"

    def test_handle_not_owned_404(self, api_client):
        client, db, _user, _app = api_client
        msg = _mk_message(db, user_id=8)
        resp = client.post(f"/api/v1/reminders/{msg.id}/handle")
        assert resp.status_code == 404

    def test_handle_missing_404(self, api_client):
        client, _db, _user, _app = api_client
        resp = client.post("/api/v1/reminders/99999/handle")
        assert resp.status_code == 404

    def test_ignore_with_and_without_reason(self, api_client):
        client, db, _user, _app = api_client
        msg1 = _mk_message(db, title="忽略1")
        msg2 = _mk_message(db, title="忽略2")
        resp1 = client.post(f"/api/v1/reminders/{msg1.id}/ignore", json={"note": "重复"})
        resp2 = client.post(f"/api/v1/reminders/{msg2.id}/ignore")
        assert resp1.status_code == 200 and resp1.json()["data"]["state"] == "ignored"
        assert resp1.json()["data"]["note"] == "重复"
        assert resp2.status_code == 200 and resp2.json()["data"]["note"] is None

    def test_snooze_with_days_and_default(self, api_client):
        client, db, _user, _app = api_client
        msg1 = _mk_message(db, title="延期1")
        msg2 = _mk_message(db, title="延期2")
        resp1 = client.post(f"/api/v1/reminders/{msg1.id}/snooze", json={"days": 3})
        resp2 = client.post(f"/api/v1/reminders/{msg2.id}/snooze")
        assert resp1.status_code == 200
        assert resp1.json()["data"]["snooze_until"] is not None
        assert "延期 3 天" in resp1.json()["message"]
        assert resp2.status_code == 200
        assert "延期 7 天" in resp2.json()["message"]

    @pytest.mark.parametrize("days", [0, 91])
    def test_snooze_out_of_range_422(self, api_client, days):
        client, db, _user, _app = api_client
        msg = _mk_message(db)
        resp = client.post(f"/api/v1/reminders/{msg.id}/snooze", json={"days": days})
        assert resp.status_code == 422

    def test_snooze_service_level_invalid_is_400(self, api_client):
        client, db, _user, _app = api_client
        from app.services.reminder_disposition_service import InvalidSnoozeDaysError

        msg = _mk_message(db)
        with patch(
            "app.api.v1.reminders._snooze",
            side_effect=InvalidSnoozeDaysError("延期天数须在 1-90 之间"),
        ):
            resp = client.post(f"/api/v1/reminders/{msg.id}/snooze", json={"days": 3})
        assert resp.status_code == 400

    def test_reopen_with_and_without_note(self, api_client):
        client, db, _user, _app = api_client
        msg1 = _mk_message(db, title="重开1")
        msg2 = _mk_message(db, title="重开2")
        assert client.post(f"/api/v1/reminders/{msg1.id}/handle", json={}).status_code == 200
        assert client.post(f"/api/v1/reminders/{msg2.id}/handle", json={}).status_code == 200
        resp1 = client.post(f"/api/v1/reminders/{msg1.id}/reopen", json={"note": "仍需跟进"})
        resp2 = client.post(f"/api/v1/reminders/{msg2.id}/reopen")
        assert resp1.status_code == 200 and resp1.json()["data"]["state"] == "open"
        assert resp1.json()["data"]["note"] == "仍需跟进"
        assert resp2.status_code == 200 and resp2.json()["data"]["note"] is None

    def test_unexpected_error_is_generic_500(self, api_client):
        client, db, _user, _app = api_client
        msg = _mk_message(db)
        with patch("app.api.v1.reminders._handle", side_effect=RuntimeError("secret-internal")):
            resp = client.post(f"/api/v1/reminders/{msg.id}/handle")
        assert resp.status_code == 500
        assert "secret-internal" not in resp.text

    def test_missing_username_branch(self, api_client):
        client, db, user, _app = api_client
        msg = _mk_message(db)
        user.username = None  # getattr(...) or "" 兜底分支
        resp = client.post(f"/api/v1/reminders/{msg.id}/handle")
        assert resp.status_code == 200
