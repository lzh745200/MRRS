"""W1-T5 安全回归：认证收口——吊销体系闭环（ADR-0001）。

历史缺陷：get_current_user 主链路不查黑名单 → 登出/吊销形同虚设；
refresh 可当 access 用；管理员强制下线接口恒 400。

本文件通过**真实**认证依赖（不 mock get_current_user）做端到端闭环验证。
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.token_manager import create_token_pair
from app.main import app


def _hash(pwd: str) -> str:
    from app.core.security import get_password_hash

    return get_password_hash(pwd)


class _Env:
    def __init__(self, tc, db):
        self.tc = tc
        self.db = db


@pytest.fixture
def env(client):
    """内存库环境；提供种子用户工具。"""
    from app.core.database import get_db as _get_db

    db = next(client.app.dependency_overrides[_get_db]())

    def seed_user(username, role="user", is_superuser=False):
        from app.models.user import User

        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return existing
        u = User(
            username=username,
            hashed_password=_hash("OldPwd123!"),
            role=role,
            is_superuser=is_superuser,
            is_active=True,
            organization_id=1,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    yield _Env(tc=client, db=db), seed_user


class TestLogoutRevokesAccessToken:
    def test_access_token_dead_after_logout(self, env):
        """登出后原 access token 访问受保护端点必须 401（核心闭环）。"""
        e, seed_user = env
        seed_user("revokeme")
        pair = create_token_pair("revokeme")
        headers = {"Authorization": f"Bearer {pair['access_token']}"}

        r0 = e.tc.get("/api/v1/auth/me", headers=headers)
        assert r0.status_code == 200, f"前置失败：合法 token 应可用: {r0.text}"

        r1 = e.tc.post(
            "/api/v1/auth/logout",
            headers=headers,
            json={"refresh_token": pair["refresh_token"]},
        )
        assert r1.status_code == 200, r1.text

        r2 = e.tc.get("/api/v1/auth/me", headers=headers)
        assert r2.status_code == 401, f"登出后旧 access token 仍可用！{r2.text}"

    def test_refresh_token_in_body_dead_after_logout(self, env):
        e, seed_user = env
        seed_user("revokeme2")
        pair = create_token_pair("revokeme2")
        headers = {"Authorization": f"Bearer {pair['access_token']}"}
        e.tc.post("/api/v1/auth/logout", headers=headers,
                  json={"refresh_token": pair["refresh_token"]})
        # 刷新接口使用已吊销 refresh → 拒绝
        r = e.tc.post("/api/v1/auth/refresh",
                      json={"token": pair["refresh_token"]})
        assert r.status_code in (401, 400), f"已吊销 refresh 仍可刷新: {r.text}"


class TestRefreshCannotActAsAccess:
    def test_refresh_token_rejected_on_protected_route(self, env):
        """refresh token 不能当 access 用（类型校验）。"""
        e, seed_user = env
        seed_user("typetest")
        pair = create_token_pair("typetest")
        r = e.tc.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {pair['refresh_token']}"},
        )
        assert r.status_code == 401, "refresh token 竟可通过 access 校验"


class TestForceLogoutClosure:
    def test_admin_force_logout_kills_all_tokens(self, env):
        """管理员强制下线：token_version 递增后用户所有现存 token 立即失效。"""
        e, seed_user = env
        target = seed_user("victim")
        admin = seed_user("theadmin", role="admin", is_superuser=True)

        pair = create_token_pair("victim")
        headers = {"Authorization": f"Bearer {pair['access_token']}"}
        assert e.tc.get("/api/v1/auth/me", headers=headers).status_code == 200

        # 以 admin 身份调用强制下线（覆盖认证依赖，业务逻辑真实执行）
        original_overrides = e.tc.app.dependency_overrides.copy()
        e.tc.app.dependency_overrides[get_current_user] = lambda: admin
        try:
            r = e.tc.post(
                f"/api/v1/system/admin/users/{target.id}/sessions/whatever-session/revoke",
            )
        finally:
            e.tc.app.dependency_overrides = original_overrides
        assert r.status_code == 200, f"强制下线接口异常: {r.text}"

        r2 = e.tc.get("/api/v1/auth/me", headers=headers)
        assert r2.status_code == 401, f"强制下线后目标 token 仍可用！{r2.text}"
