"""app.api.v1.auth.rbac 覆盖率攻坚测试

模块现状：既有 test_rbac_* 针对 services.rbac_service / models.rbac，
本文件补齐 api 层 rbac.py 全部端点分支（92 缺口行）。

策略：
- require_admin() 返回的闭包依赖 get_current_active_user，
  覆盖后者即可让真实管理员校验逻辑执行（顺带覆盖 security.py 检查器）。
- TransactionManager.transaction 以 contextmanager 替换，yield 可控 mock 会话。
- rbac_service 以 MagicMock + AsyncMock 注入。
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.auth.rbac as rbac_mod
from app.core.database import get_db
from app.core.security import get_current_active_user, get_current_user
from app.services.rbac_service import Permission


# ==================== 公共设施 ====================


def _user(uid=1, role="admin"):
    return SimpleNamespace(id=uid, role=role, username="u", is_superuser=False)


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit", "join", "options", "group_by"):
        getattr(q, attr).return_value = q
    q.delete.return_value = 0
    q.scalar.return_value = kw.get("scalar")
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


def _db_with(queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


@pytest.fixture
def rbac_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _as_user(client, user):
    """注入登录用户；管理员检查器走真实 _admin_checker 逻辑"""
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[get_current_active_user] = lambda: user


def _use_db(client, db):
    client.app.dependency_overrides[get_db] = lambda: db


def _tx(sess):
    @contextmanager
    def _fake(db):
        yield sess

    return patch.object(rbac_mod.TransactionManager, "transaction", _fake)


def _svc_patch(**methods):
    svc = MagicMock()
    for name, ret in methods.items():
        setattr(svc, name, AsyncMock(return_value=ret))
    return patch.object(rbac_mod, "rbac_service", svc), svc


# ==================== POST /rbac/check ====================


class TestCheckPermission:
    def test_check(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, svc = _svc_patch(check_permission=True)
        with p:
            resp = rbac_client.post("/api/v1/rbac/check", json={"permission": "user:read"})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {
            "code": 200,
            "message": "success",
            "success": True,
            "has_permission": True,
            "permission": "user:read",
            "user_id": "1",
        }
        svc.check_permission.assert_awaited_once()


# ==================== GET /rbac/user/{uid}/permissions|roles ====================


class TestUserPermissionsAndRoles:
    def test_permissions_self(self, rbac_client):
        _as_user(rbac_client, _user(uid=1, role="viewer"))
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(get_user_permissions={"user:read"}, get_user_roles=[{"name": "普通"}])
        with p:
            resp = rbac_client.get("/api/v1/rbac/user/1/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "1"
        assert data["permissions"] == ["user:read"]
        assert data["roles"] == [{"name": "普通"}]

    def test_permissions_admin_views_other(self, rbac_client):
        _as_user(rbac_client, _user(uid=1, role="admin"))
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(get_user_permissions=set(), get_user_roles=[])
        with p:
            resp = rbac_client.get("/api/v1/rbac/user/2/permissions")
        assert resp.status_code == 200

    def test_permissions_forbidden_for_other(self, rbac_client):
        _as_user(rbac_client, _user(uid=1, role="viewer"))
        resp = rbac_client.get("/api/v1/rbac/user/2/permissions")
        assert resp.status_code == 403

    def test_roles_success(self, rbac_client):
        _as_user(rbac_client, _user(uid=1))
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(get_user_roles=[{"name": "管理员"}])
        with p:
            resp = rbac_client.get("/api/v1/rbac/user/1/roles")
        assert resp.status_code == 200
        assert resp.json() == {
            "code": 200,
            "message": "success",
            "success": True,
            "data": [{"name": "管理员"}],
            "count": 1,
        }

    def test_roles_forbidden_for_other(self, rbac_client):
        _as_user(rbac_client, _user(uid=1, role="viewer"))
        resp = rbac_client.get("/api/v1/rbac/user/2/roles")
        assert resp.status_code == 403


# ==================== 角色 CRUD ====================


class TestRoleCrud:
    def test_create_role(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        sess = MagicMock()
        p, svc = _svc_patch(create_role="role-1")
        with p, _tx(sess):
            resp = rbac_client.post(
                "/api/v1/rbac/roles",
                json={"name": "审计员", "description": "d", "permissions": ["user:read"], "is_system": False},
            )
        assert resp.status_code == 200
        assert resp.json()["role_id"] == "role-1"
        assert "审计员" in resp.json()["message"]
        svc.create_role.assert_awaited_once()

    def test_create_role_non_admin_403(self, rbac_client):
        _as_user(rbac_client, _user(role="viewer"))
        resp = rbac_client.post(
            "/api/v1/rbac/roles",
            json={"name": "x", "description": "d", "permissions": []},
        )
        assert resp.status_code == 403

    def test_list_roles(self, rbac_client):
        _as_user(rbac_client, _user())
        r1, r2 = MagicMock(), MagicMock()
        r1.to_dict.return_value = {"id": "r1"}
        r2.to_dict.return_value = {"id": "r2"}
        _use_db(rbac_client, _db_with([_q(scalar=2), _q(all=[r1, r2])]))
        resp = rbac_client.get("/api/v1/rbac/roles?skip=0&limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["data"] == [{"id": "r1"}, {"id": "r2"}]

    def test_get_role_found(self, rbac_client):
        _as_user(rbac_client, _user())
        role = MagicMock()
        role.to_dict.return_value = {"id": "r1", "name": "管理员"}
        _use_db(rbac_client, _db_with([_q(first=role), _q(all=[("user:read",), ("user:write",)])]))
        resp = rbac_client.get("/api/v1/rbac/roles/r1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["permissions"] == ["user:read", "user:write"]

    def test_get_role_not_found(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, _db_with([_q(first=None)]))
        resp = rbac_client.get("/api/v1/rbac/roles/ghost")
        assert resp.status_code == 404
        assert resp.json()["error"] == "角色不存在"

    def test_update_role_full(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        role = MagicMock()
        sess = _db_with([_q(first=role), _q()])  # 角色查询 + RolePermission 删除链
        with _tx(sess):
            resp = rbac_client.put(
                "/api/v1/rbac/roles/r1",
                json={"name": "新名", "description": "d2", "is_active": False, "permissions": ["a", "b"]},
            )
        assert resp.status_code == 200
        assert role.name == "新名"
        assert role.description == "d2"
        assert role.is_active is False
        assert sess.add.call_count == 2
        sess.flush.assert_called_once()
        sess.refresh.assert_called_once_with(role)
        assert "新名" in resp.json()["message"]

    def test_update_role_not_found(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        with _tx(_db_with([_q(first=None)])):
            resp = rbac_client.put("/api/v1/rbac/roles/ghost", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_role_success(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        role = MagicMock()
        role.is_system = False
        role.name = "临时"
        sess = _db_with([_q(first=role)])
        with _tx(sess):
            resp = rbac_client.delete("/api/v1/rbac/roles/r1")
        assert resp.status_code == 200
        sess.delete.assert_called_once_with(role)
        assert "临时" in resp.json()["message"]

    def test_delete_role_not_found(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        with _tx(_db_with([_q(first=None)])):
            resp = rbac_client.delete("/api/v1/rbac/roles/ghost")
        assert resp.status_code == 404

    def test_delete_system_role_rejected(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        role = MagicMock()
        role.is_system = True
        with _tx(_db_with([_q(first=role)])):
            resp = rbac_client.delete("/api/v1/rbac/roles/sys")
        assert resp.status_code == 400

    def test_get_role_users(self, rbac_client):
        _as_user(rbac_client, _user())
        row = SimpleNamespace(id=1, username="zhang", full_name="张三", role="admin", is_active=True)
        _use_db(rbac_client, _db_with([_q(all=[row])]))
        resp = rbac_client.get("/api/v1/rbac/roles/r1/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["username"] == "zhang"


# ==================== 权限分配 ====================


class TestAssignAndRevoke:
    def test_assign_newly_granted(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, svc = _svc_patch(assign_role={"success": True, "newly_granted": True})
        with p, _tx(MagicMock()):
            resp = rbac_client.post(
                "/api/v1/rbac/assign/role",
                json={"user_id": 2, "role_id": "r1", "expires_at": "2026-12-31T00:00:00"},
            )
        assert resp.status_code == 200
        assert resp.json()["newly_granted"] is True
        assert "已完成分配" in resp.json()["message"]
        # expires_at 被转为 isoformat 字符串
        assert svc.assign_role.await_args.kwargs["expires_at"] == "2026-12-31T00:00:00"

    def test_assign_already_exists(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(assign_role={"success": True, "newly_granted": False})
        with p, _tx(MagicMock()):
            resp = rbac_client.post("/api/v1/rbac/assign/role", json={"user_id": 2, "role_id": "r1"})
        assert resp.status_code == 200
        assert "无需操作" in resp.json()["message"]

    def test_assign_failure_400(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(assign_role={"success": False})
        with p, _tx(MagicMock()):
            resp = rbac_client.post("/api/v1/rbac/assign/role", json={"user_id": 2, "role_id": "r1"})
        assert resp.status_code == 400

    def test_revoke_role_success(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(revoke_role=True)
        with p, _tx(MagicMock()):
            resp = rbac_client.request("DELETE", "/api/v1/rbac/revoke/role", json={"user_id": 2, "role_id": "r1"})
        assert resp.status_code == 200
        assert "撤销成功" in resp.json()["message"]

    def test_revoke_role_failure_400(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(revoke_role=False)
        with p, _tx(MagicMock()):
            resp = rbac_client.request("DELETE", "/api/v1/rbac/revoke/role", json={"user_id": 2, "role_id": "r1"})
        assert resp.status_code == 400

    def test_grant_permission_with_skipped(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(grant_permissions_batch={"granted": ["a"], "skipped": ["b"], "failed": []})
        with p, _tx(MagicMock()):
            resp = rbac_client.post(
                "/api/v1/rbac/grant/permission",
                json={"user_id": 2, "permissions": ["a", "b"], "expires_at": "2026-12-31T00:00:00"},
            )
        assert resp.status_code == 200
        msg = resp.json()["message"]
        assert "新增 1" in msg and "跳过(已存在) 1" in msg

    def test_grant_permission_no_skipped(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(grant_permissions_batch={"granted": ["a"], "skipped": [], "failed": []})
        with p, _tx(MagicMock()):
            resp = rbac_client.post("/api/v1/rbac/grant/permission", json={"user_id": 2, "permissions": ["a"]})
        assert "跳过" not in resp.json()["message"]

    def test_revoke_permission_all_success(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(revoke_permissions_batch=(["a"], []))
        with p, _tx(MagicMock()):
            resp = rbac_client.post("/api/v1/rbac/revoke/permission", json={"user_id": 2, "permissions": ["a"]})
        data = resp.json()
        assert data["success"] is True
        assert data["revoked"] == ["a"]

    def test_revoke_permission_with_failed(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(revoke_permissions_batch=([], ["x"]))
        with p, _tx(MagicMock()):
            resp = rbac_client.post("/api/v1/rbac/revoke/permission", json={"user_id": 2, "permissions": ["x"]})
        assert resp.json()["success"] is False

    def test_save_permissions_full_message(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(save_permissions={"granted": ["a"], "revoked": ["b"], "skipped": ["c"]})
        with p, _tx(MagicMock()):
            resp = rbac_client.post(
                "/api/v1/rbac/save-permissions",
                json={"user_id": 2, "permissions": ["a"], "expires_at": "2026-12-31T00:00:00"},
            )
        msg = resp.json()["message"]
        assert "授予 1" in msg and "撤销 1" in msg and "跳过(已存在) 1" in msg

    def test_save_permissions_minimal_message(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(save_permissions={"granted": ["a"], "revoked": [], "skipped": []})
        with p, _tx(MagicMock()):
            resp = rbac_client.post("/api/v1/rbac/save-permissions", json={"user_id": 2, "permissions": ["a"]})
        msg = resp.json()["message"]
        assert "撤销" not in msg and "跳过" not in msg


# ==================== 权限列表 / 前端专用 ====================


class TestPermissionLists:
    def test_list_permissions(self, rbac_client):
        _as_user(rbac_client, _user())
        resp = rbac_client.get("/api/v1/rbac/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == len(Permission)
        assert data["success"] is True
        assert isinstance(data["categories"], dict) and data["categories"]

    def test_frontend_current_user_permissions(self, rbac_client):
        _as_user(rbac_client, _user())
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(
            get_user_permissions={Permission.USER_READ.value, Permission.ADMIN_ALL.value},
            get_user_roles=[{"name": "管理员"}],
        )
        with p:
            resp = rbac_client.get("/api/v1/rbac/frontend/current-user-permissions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["permissions"]["user"]["read"] is True
        assert data["permissions"]["village"]["read"] is False
        assert data["is_admin"] is True
        assert data["role_names"] == ["管理员"]

    def test_frontend_current_user_permissions_empty(self, rbac_client):
        _as_user(rbac_client, _user(role="viewer"))
        _use_db(rbac_client, MagicMock())
        p, _ = _svc_patch(get_user_permissions=set(), get_user_roles=[])
        with p:
            resp = rbac_client.get("/api/v1/rbac/frontend/current-user-permissions")
        data = resp.json()["data"]
        assert data["permissions"]["user"]["read"] is False
        assert data["is_admin"] is False
        assert data["role_names"] == []

    def test_route_permissions(self, rbac_client):
        _as_user(rbac_client, _user())
        resp = rbac_client.get("/api/v1/rbac/frontend/route-permissions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["/dashboard"] == ["user:read"]
        assert "/villages/delete/:id" in data
