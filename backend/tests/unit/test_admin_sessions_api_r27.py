"""管理端用户会话端点的按会话精确吊销分支（2026-10-14 R27）。

覆盖 `POST /system/admin/users/{id}/sessions/{sid}/revoke` 的两条路径：
- session_id 命中 user_sessions → 只吊销该会话（access/refresh jti 进黑名单），
  **不**递增 token_version（不影响该用户其它设备）；
- 未命中（历史登录）→ 退回既有 token_version 全量踢下线语义（向前兼容）。
"""
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.user_session import UserSession


@pytest.fixture
def client_admin(mock_db, admin_user):
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original_overrides


def _user(uid=2, username="op"):
    u = MagicMock()
    u.id = uid
    u.username = username
    u.role = "user"
    u.is_active = True
    return u


def test_revoke_by_session_id_revokes_only_that_session(client_admin, mock_db):
    """命中会话：吊销该会话（jti 进黑名单 + 标记 revoked_at），不动 token_version。"""
    from app.models.user import User

    user = User(username="op")
    user.id = 2
    user.is_active = True
    session = UserSession(user_id=2, token_jti="acc-xyz", login_at=datetime.now())
    mock_db.add(user)
    mock_db.add(session)

    with patch("app.core.token_blacklist.add") as bl_add, patch(
        "app.core.token_blacklist.add_to_db"
    ) as bl_persist, patch("app.services.session_service.safe_commit"):
        resp = client_admin.post(f"/api/v1/system/admin/users/2/sessions/{session.id}/revoke")

    assert resp.status_code == 200
    assert "该会话" in resp.json()["message"]
    # refresh_jti 为 None → 只有 access jti 进黑名单
    assert [c.args[0] for c in bl_add.call_args_list] == ["acc-xyz"]
    assert bl_persist.call_count == 1
    assert session.revoked_at is not None and session.revoked_by == 1
    assert user.token_version_safe == 0  # 精确吊销不得递增 token_version（否则踢掉其它设备）


def test_revoke_unknown_session_falls_back_to_token_version(client_admin, mock_db):
    """未命中会话（历史登录）：退回 token_version 全量踢下线（兼容旧语义）。"""
    from app.models.user import User

    user = User(username="op")
    user.id = 2
    user.is_active = True
    user.token_version = 3
    mock_db.add(user)

    with patch("app.services.session_service.safe_commit"):
        resp = client_admin.post("/api/v1/system/admin/users/2/sessions/999/revoke")

    assert resp.status_code == 200
    assert "已强制登出用户" in resp.json()["message"]
    assert user.token_version == 4  # 递增一位


def test_list_sessions_returns_real_rows(client_admin, mock_db):
    """列表端点返回真实活跃会话（此前恒为空数组）。"""
    from app.models.user import User

    user = User(username="op")
    user.id = 2
    user.is_active = True
    row = UserSession(user_id=2, token_jti="acc-live", login_at=datetime.now())
    mock_db.add(user)
    mock_db.add(row)

    with patch("app.services.session_service.safe_commit"):
        resp = client_admin.get("/api/v1/system/admin/users/2/sessions")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [s["session_id"] for s in data["sessions"]] == [row.id]  # 前端契约字段（别名）
    assert data["sessions"][0]["jti"] == "acc-live"
