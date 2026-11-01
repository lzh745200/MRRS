"""审计日志跨组织可读修复（短期改进第 4 项）回归测试。

锁定四个口径（2026-11-01）：
1. 部门级 admin 只看到本组织及子树的审计日志；
2. ``user_id`` 为 NULL 的系统日志对部门级 admin 不可见（fail-closed）；
3. 超级管理员看全部；
4. 无组织归属的管理员看到空集（绝不回落全量）。

使用真实 in-memory SQLite（fixture 写法参考 tests/unit/test_data_package_pk_collision_w18.py）。
"""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

BASE = "/api/v1/system/audit"


def _user(user_id, username, role="admin", is_superuser=False, organization_id=None):
    """轻量用户对象；organization_id / org_id 同时给出，兼容 _get_user_org_id 回退口径。"""
    return SimpleNamespace(
        id=user_id,
        username=username,
        role=role,
        is_superuser=is_superuser,
        organization_id=organization_id,
        org_id=organization_id,
    )


def _as_department_admin(state, org_id=1):
    state.set_user(_user(10, "dept-admin", organization_id=org_id))


def _as_superuser(state):
    state.set_user(_user(1, "root", role="super_admin", is_superuser=True))


def _as_orgless_admin(state):
    state.set_user(_user(11, "orgless-admin", organization_id=None))


@pytest.fixture()
def scope_env():
    """TestClient + 真实内存库；通过 ``state.set_user`` 切换当前登录用户。"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    import app.core.database as _db_module
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # 审计中间件等绕过 get_db 的代码路径也走内存库
    _original_engine = _db_module.engine
    _original_session_local = _db_module.SessionLocal
    _db_module.engine = engine
    _db_module.SessionLocal = TestingSessionLocal

    state = SimpleNamespace(current_user=_user(1, "root", role="super_admin", is_superuser=True))
    state.set_user = lambda user: setattr(state, "current_user", user)

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: state.current_user

    try:
        state.client = TestClient(app, raise_server_exceptions=False)
        yield state, session
    finally:
        app.dependency_overrides = original_overrides
        _db_module.engine = _original_engine
        _db_module.SessionLocal = _original_session_local
        session.close()
        engine.dispose()


@pytest.fixture()
def seeded(scope_env):
    """组织树：1(根) ← 2(下级)；3 为其他组织。审计类数据按用户归属铺开。"""
    state, session = scope_env
    from app.models.audit import APIAccessLog, AuditLog, SecurityEvent
    from app.models.organization import Organization
    from app.models.user import User

    session.add_all(
        [
            Organization(id=1, name="本组织"),
            Organization(id=2, name="本组织下级", parent_id=1),
            Organization(id=3, name="其他组织"),
        ]
    )
    session.add_all(
        [
            User(id=101, username="u1", hashed_password="x", organization_id=1),
            User(id=102, username="u2", hashed_password="x", organization_id=2),
            User(id=103, username="u3", hashed_password="x", organization_id=3),
            User(id=104, username="u4", hashed_password="x", organization_id=None),
        ]
    )
    session.add_all(
        [
            AuditLog(id=1, user_id=101, username="u1", action="create", resource_type="user",
                     status="success", level="info"),
            AuditLog(id=2, user_id=102, username="u2", action="update", resource_type="fund",
                     status="failed", level="warning"),
            AuditLog(id=3, user_id=103, username="u3", action="delete", resource_type="user",
                     status="success", level="info"),
            AuditLog(id=4, user_id=None, username="system", action="config_change",
                     resource_type="config", status="success", level="info"),
            AuditLog(id=5, user_id=104, username="u4", action="export", resource_type="data",
                     status="success", level="info"),
        ]
    )
    session.add_all(
        [
            SecurityEvent(id=1, user_id=101, username="u1", severity="high",
                          event_type="brute_force_attempt", description="e1", resolved=False),
            SecurityEvent(id=2, user_id=102, username="u2", severity="high",
                          event_type="brute_force_attempt", description="e2", resolved=False),
            SecurityEvent(id=3, user_id=103, username="u3", severity="high",
                          event_type="brute_force_attempt", description="e3", resolved=False),
            SecurityEvent(id=4, user_id=None, username="system", severity="high",
                          event_type="brute_force_attempt", description="e4", resolved=False),
            SecurityEvent(id=5, user_id=104, username="u4", severity="high",
                          event_type="brute_force_attempt", description="e5", resolved=False),
        ]
    )
    session.add_all(
        [
            APIAccessLog(id=1, user_id=101, username="u1", endpoint="scope-check", method="GET"),
            APIAccessLog(id=2, user_id=102, username="u2", endpoint="scope-check", method="GET"),
            APIAccessLog(id=3, user_id=103, username="u3", endpoint="scope-check", method="GET"),
            APIAccessLog(id=4, user_id=None, username="system", endpoint="scope-check", method="GET"),
            APIAccessLog(id=5, user_id=104, username="u4", endpoint="scope-check", method="GET"),
        ]
    )
    session.commit()

    yield state, session


class TestAuditLogListScope:
    def test_department_admin_sees_only_own_org_and_subtree(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        resp = state.client.get(f"{BASE}/logs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert {item["username"] for item in body["items"]} == {"u1", "u2"}

    def test_department_admin_cannot_see_null_user_system_logs(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        body = state.client.get(f"{BASE}/logs").json()

        assert body["total"] == 2
        assert "system" not in {item["username"] for item in body["items"]}

    def test_list_filters_still_apply_on_scoped_query(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        resp = state.client.get(
            f"{BASE}/logs",
            params={
                "user_id": 101,
                "username": "u1",
                "action": "create",
                "resource_type": "user",
                "status": "success",
                "level": "info",
                "start_date": "2000-01-01T00:00:00",
                "end_date": "2100-01-01T00:00:00",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["username"] == "u1"

    def test_superuser_sees_all_organizations(self, seeded):
        state, _ = seeded
        _as_superuser(state)

        body = state.client.get(f"{BASE}/logs").json()

        assert body["total"] == 5
        assert {item["username"] for item in body["items"]} == {"u1", "u2", "u3", "system", "u4"}

    def test_admin_without_organization_sees_empty_set(self, seeded):
        state, _ = seeded
        _as_orgless_admin(state)

        body = state.client.get(f"{BASE}/logs").json()

        assert body["total"] == 0
        assert body["items"] == []


class TestAuditLogDetailScope:
    def test_detail_is_scoped_to_own_org(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        assert state.client.get(f"{BASE}/logs/1").status_code == 200
        assert state.client.get(f"{BASE}/logs/3").status_code == 404
        assert state.client.get(f"{BASE}/logs/4").status_code == 404

    def test_superuser_detail_sees_any_org(self, seeded):
        state, _ = seeded
        _as_superuser(state)

        assert state.client.get(f"{BASE}/logs/4").status_code == 200


class TestAuditLogExportScope:
    def test_export_is_scoped_to_own_org(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        body = state.client.get(f"{BASE}/logs/export", params={"format": "json"}).json()["data"]

        assert body["total"] == 2
        assert {item["user"] for item in body["items"]} == {"u1", "u2"}

    def test_export_superuser_gets_all(self, seeded):
        state, _ = seeded
        _as_superuser(state)

        body = state.client.get(f"{BASE}/logs/export", params={"format": "json"}).json()["data"]

        assert body["total"] == 5

    def test_export_orgless_admin_gets_empty(self, seeded):
        state, _ = seeded
        _as_orgless_admin(state)

        body = state.client.get(f"{BASE}/logs/export", params={"format": "json"}).json()["data"]

        assert body["total"] == 0


class TestAuditLogStatsScope:
    def test_stats_are_scoped_to_own_org(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        resp = state.client.get(
            f"{BASE}/stats",
            params={"start_date": "2000-01-01T00:00:00", "end_date": "2100-01-01T00:00:00"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert body["total_operations"] == 2
        assert set(body["by_action"]) == {"create", "update"}
        assert body["top_users"] == {"u1": 1, "u2": 1}
        assert body["failed_operations"] == 1
        assert body["warnings"] == 1
        assert body["today_operations"] == 2
        assert len(body["recent_activity"]) == 2

    def test_stats_superuser_gets_all(self, seeded):
        state, _ = seeded
        _as_superuser(state)

        body = state.client.get(f"{BASE}/stats").json()

        assert body["total_count"] == 5

    def test_stats_without_date_filters_still_scoped(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        body = state.client.get(f"{BASE}/stats").json()

        assert body["total_count"] == 2
        assert body["today_operations"] == 2


class TestSecurityEventScope:
    def test_department_admin_sees_only_own_org_events(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        resp = state.client.get(
            f"{BASE}/security/events",
            params={
                "severity": "high",
                "event_type": "brute_force_attempt",
                "resolved": "false",
                "start_date": "2000-01-01T00:00:00",
                "end_date": "2100-01-01T00:00:00",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert {item["username"] for item in body["items"]} == {"u1", "u2"}

    def test_superuser_sees_all_security_events(self, seeded):
        state, _ = seeded
        _as_superuser(state)

        body = state.client.get(f"{BASE}/security/events").json()

        assert body["total"] == 5

    def test_department_admin_without_filters_still_scoped(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        body = state.client.get(f"{BASE}/security/events").json()

        assert body["total"] == 2
        assert {item["username"] for item in body["items"]} == {"u1", "u2"}


class TestApiAccessScope:
    def test_department_admin_sees_only_own_org_api_logs(self, seeded):
        state, _ = seeded
        _as_department_admin(state, org_id=1)

        body = state.client.get(f"{BASE}/api-access", params={"endpoint": "scope-check"}).json()["data"]

        assert body["total"] == 2
        assert {item["username"] for item in body["items"]} == {"u1", "u2"}

    def test_superuser_sees_all_api_logs(self, seeded):
        state, _ = seeded
        _as_superuser(state)

        body = state.client.get(f"{BASE}/api-access", params={"endpoint": "scope-check"}).json()["data"]

        assert body["total"] == 5


def test_scope_helper_bypasses_superuser_query_untouched():
    """helper 单测：超级管理员必须拿到**同一个** query 对象（全量、零改造）。"""
    from app.api.v1.system.audit import _apply_audit_scope

    class _QueryStub:
        pass

    stub = _QueryStub()
    assert _apply_audit_scope(stub, None, _user(1, "root", role="super_admin", is_superuser=True)) is stub
