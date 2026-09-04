"""app.api.v1.system.admin 覆盖补全 — 用户不存在时的 404 分支 (lines 437, 456)."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mocks():
    db = MagicMock(name="db")
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.first.return_value = None  # 用户不存在
    db.query.return_value = q

    user = MagicMock(name="user")
    user.id = 1
    user.role = "admin"
    user.is_superuser = True
    user.username = "admin"
    return db, q, user


@pytest.fixture
def client(mocks):
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    db, _, user = mocks
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    tc = TestClient(app, raise_server_exceptions=False)
    yield tc
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


class TestRevokeUserSession:
    def test_user_not_found(self, client):
        resp = client.post("/api/v1/system/admin/users/9/sessions/sess-abc/revoke")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "用户不存在"

    def _make_client(self, first, monkeypatch):
        """注入自定义 query 首结果的客户端（复用现有 fixture 模式）"""
        from app.main import app
        from app.core.database import get_db
        from app.core.security import get_current_user

        db, q, user = mocks_default()
        q.first.return_value = first
        db.query.return_value = q
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False), db

    def test_commit_failure_500(self, monkeypatch):
        """覆盖 admin.py:461-464 —— token_version 递增 commit 失败 → 500 + 回滚"""
        from types import SimpleNamespace

        target = SimpleNamespace(id=9, username="victim", token_version=3)
        tc, db = self._make_client(target, monkeypatch)
        db.commit.side_effect = Exception("db down")
        try:
            resp = tc.post("/api/v1/system/admin/users/9/sessions/s/revoke")
        finally:
            from app.main import app
            from app.core.database import get_db
            from app.core.security import get_current_user
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 500
        assert "强制登出失败" in resp.json()["detail"]
        db.rollback.assert_called_once()

    def test_real_jwt_session_revokes_token(self, monkeypatch):
        """覆盖 admin.py:466-469 —— session_id 为真实 JWT 格式(两个点)时额外按 jti 吊销"""
        from types import SimpleNamespace
        from unittest.mock import patch

        target = SimpleNamespace(id=9, username="victim", token_version=3)
        tc, db = self._make_client(target, monkeypatch)
        jwt_like = "header.payload.signature"  # 两个点 → 真实 JWT 分支
        try:
            with patch("app.core.token_manager.revoke_token") as m_revoke:
                resp = tc.post(
                    f"/api/v1/system/admin/users/9/sessions/{jwt_like}/revoke"
                )
        finally:
            from app.main import app
            from app.core.database import get_db
            from app.core.security import get_current_user
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
        assert resp.status_code == 200
        assert target.token_version == 4  # 递增成功
        m_revoke.assert_called_once_with(jwt_like, reason="admin_force_logout")


def mocks_default():
    """与 mocks fixture 同构的默认三元组（供非 fixture 注入场景复用）"""
    db = MagicMock(name="db")
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    user = MagicMock(name="user")
    user.id = 1
    user.role = "admin"
    user.is_superuser = True
    user.username = "admin"
    return db, q, user


class TestResetUserTwoFactor:
    def test_user_not_found(self, client):
        resp = client.post("/api/v1/system/admin/users/9/two-factor/reset")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "用户不存在"
