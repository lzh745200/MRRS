"""权限包（菜单套餐）API 测试

覆盖：
- CRUD 全流程；name 重复拒绝(400)；非法 menu_keys 拒绝(422)
- 绑定/解绑用户；绑定 admin/super_admin 角色被拒；绑定不存在用户被拒
- 绑定后 /menus/accessible 返回包内菜单（source == "pack"）
- 三级优先级：用户 allowed_menus 覆盖权限包；解绑后回落角色默认
- 包 menu_keys 修改后绑定用户菜单即时变化；停用包回落角色默认
- 有绑定用户时 DELETE 拒绝(400)；解绑后可删
- 非管理员访问全部端点 403
- 未绑包普通用户 /menus/accessible 与改动前行为一致（回归，source == "role"）
"""

import json
from unittest.mock import Mock

import pytest


# ── helpers ──────────────────────────────────────────────────────────
def _admin_mock():
    """管理员认证用户（仅做角色判断与日志记录，无需真实 DB 行）"""
    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1
    return user


def _set_auth(client, user):
    from app.core.security import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: user


def _create_user(db, username, role="user", allowed_menus=None, permission_pack_id=None):
    """在测试库中创建真实用户行"""
    from app.models.user import User

    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
        full_name=username,
        role=role,
        is_active=True,
        allowed_menus=allowed_menus,
        permission_pack_id=permission_pack_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_pack(client, name="pack-a", menu_keys=("dashboard", "villages"), **kw):
    """通过 API 创建权限包，返回响应 data"""
    resp = client.post(
        "/api/v1/permission-packs",
        json={"name": name, "menu_keys": list(menu_keys), **kw},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    return body["data"]


def _accessible_keys(client, user):
    """以指定用户身份请求 /menus/accessible，返回 (body, 顶层菜单key集合)"""
    _set_auth(client, user)
    resp = client.get("/api/v1/menus/accessible")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body, {m["key"] for m in body["data"]}


# 公开模块中的顶层菜单 key（子节点随父级出现在树内，不参与顶层集合比较）
_PUBLIC_TOP_KEYS = {"policies", "helpData", "analytics"}


# ── fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def ctx(client_with_db):
    """(client, db) + 管理员认证"""
    test_client, db = client_with_db
    _set_auth(test_client, _admin_mock())
    return test_client, db


# =====================================================================
#  CRUD
# =====================================================================
class TestPackCRUD:
    def test_create_and_list(self, ctx):
        client, db = ctx
        pack = _create_pack(client, description="基础套餐")
        assert pack["name"] == "pack-a"
        assert pack["menu_keys"] == ["dashboard", "villages"]
        assert pack["is_active"] is True
        assert pack["bound_user_count"] == 0

        resp = client.get("/api/v1/permission-packs")
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert len(items) == 1
        assert items[0]["id"] == pack["id"]

    def test_create_duplicate_name_rejected(self, ctx):
        client, _ = ctx
        _create_pack(client)
        resp = client.post(
            "/api/v1/permission-packs",
            json={"name": "pack-a", "menu_keys": ["dashboard"]},
        )
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]

    def test_create_invalid_menu_keys_422(self, ctx):
        client, _ = ctx
        resp = client.post(
            "/api/v1/permission-packs",
            json={"name": "bad-keys", "menu_keys": ["dashboard", "not-a-key", "ghost"]},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "not-a-key" in detail
        assert "ghost" in detail

    def test_update_pack(self, ctx):
        client, _ = ctx
        pack = _create_pack(client)
        resp = client.put(
            f"/api/v1/permission-packs/{pack['id']}",
            json={"name": "pack-b", "menu_keys": ["dashboard"], "is_active": False},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "pack-b"
        assert data["menu_keys"] == ["dashboard"]
        assert data["is_active"] is False

    def test_update_duplicate_name_rejected(self, ctx):
        client, _ = ctx
        _create_pack(client, name="pack-a")
        pack_b = _create_pack(client, name="pack-b")
        resp = client.put(
            f"/api/v1/permission-packs/{pack_b['id']}", json={"name": "pack-a"}
        )
        assert resp.status_code == 400

    def test_update_invalid_menu_keys_422(self, ctx):
        client, _ = ctx
        pack = _create_pack(client)
        resp = client.put(
            f"/api/v1/permission-packs/{pack['id']}",
            json={"menu_keys": ["not-a-key"]},
        )
        assert resp.status_code == 422
        assert "not-a-key" in resp.json()["detail"]

    def test_update_not_found_404(self, ctx):
        client, _ = ctx
        resp = client.put("/api/v1/permission-packs/999", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_pack(self, ctx):
        client, _ = ctx
        pack = _create_pack(client)
        resp = client.delete(f"/api/v1/permission-packs/{pack['id']}")
        assert resp.status_code == 200
        assert client.get("/api/v1/permission-packs").json()["data"] == []

    def test_delete_not_found_404(self, ctx):
        client, _ = ctx
        assert client.delete("/api/v1/permission-packs/999").status_code == 404


# =====================================================================
#  绑定 / 解绑
# =====================================================================
class TestBindUnbind:
    def test_bind_users_success(self, ctx):
        client, db = ctx
        pack = _create_pack(client)
        u1 = _create_user(db, "u1", role="user")
        u2 = _create_user(db, "u2", role="viewer")
        resp = client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id, u2.id]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["bound_user_ids"] == sorted([u1.id, u2.id])
        db.expire_all()
        assert db.get(type(u1), u1.id).permission_pack_id == pack["id"]
        assert db.get(type(u2), u2.id).permission_pack_id == pack["id"]

        # 列表中绑定用户数即时反映
        items = client.get("/api/v1/permission-packs").json()["data"]
        assert items[0]["bound_user_count"] == 2

    def test_bind_nonexistent_user_400(self, ctx):
        client, _ = ctx
        pack = _create_pack(client)
        resp = client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [999]},
        )
        assert resp.status_code == 400
        assert "999" in resp.json()["detail"]

    def test_bind_admin_role_rejected(self, ctx):
        client, db = ctx
        pack = _create_pack(client)
        admin_row = _create_user(db, "op-admin", role="admin")
        super_row = _create_user(db, "op-super", role="super_admin")
        resp = client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [admin_row.id, super_row.id]},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert str(admin_row.id) in detail
        assert str(super_row.id) in detail

    def test_bind_pack_not_found_404(self, ctx):
        client, db = ctx
        u1 = _create_user(db, "u1")
        resp = client.post(
            "/api/v1/permission-packs/999/bind-users", json={"user_ids": [u1.id]}
        )
        assert resp.status_code == 404

    def test_unbind_users(self, ctx):
        client, db = ctx
        pack = _create_pack(client)
        u1 = _create_user(db, "u1")
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        resp = client.post(
            f"/api/v1/permission-packs/{pack['id']}/unbind-users",
            json={"user_ids": [u1.id]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["unbound_user_ids"] == [u1.id]
        db.expire_all()
        assert db.get(type(u1), u1.id).permission_pack_id is None

    def test_delete_with_bound_users_rejected_then_ok(self, ctx):
        client, db = ctx
        pack = _create_pack(client)
        u1 = _create_user(db, "u1")
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        resp = client.delete(f"/api/v1/permission-packs/{pack['id']}")
        assert resp.status_code == 400
        assert "解绑" in resp.json()["detail"]

        client.post(
            f"/api/v1/permission-packs/{pack['id']}/unbind-users",
            json={"user_ids": [u1.id]},
        )
        assert client.delete(f"/api/v1/permission-packs/{pack['id']}").status_code == 200


# =====================================================================
#  菜单解析（三级优先级 + 即时生效 + 回归）
# =====================================================================
class TestMenuResolution:
    def test_bound_user_accessible_source_pack(self, ctx):
        client, db = ctx
        pack = _create_pack(client, menu_keys=("dashboard", "villages"))
        u1 = _create_user(db, "u1", role="user")
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        db.expire_all()
        u1 = db.get(type(u1), u1.id)
        body, keys = _accessible_keys(client, u1)
        assert body["source"] == "pack"
        # 政策法规/数据分析公开模块强制并入（2026-08-15）
        assert keys == {"dashboard", "villages"} | _PUBLIC_TOP_KEYS

    def test_allowed_menus_overrides_pack(self, ctx):
        """用户级 allowed_menus 优先级高于权限包"""
        client, db = ctx
        pack = _create_pack(client, menu_keys=("dashboard", "villages"))
        u1 = _create_user(db, "u1", role="user", allowed_menus=json.dumps(["dashboard"]))
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        db.expire_all()
        u1 = db.get(type(u1), u1.id)
        body, keys = _accessible_keys(client, u1)
        assert body["source"] == "user"
        assert keys == {"dashboard"} | _PUBLIC_TOP_KEYS

    def test_unbind_falls_back_to_role_default(self, ctx):
        client, db = ctx
        pack = _create_pack(client, menu_keys=("dashboard",))
        u1 = _create_user(db, "u1", role="user")
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/unbind-users",
            json={"user_ids": [u1.id]},
        )
        db.expire_all()
        u1 = db.get(type(u1), u1.id)
        body, keys = _accessible_keys(client, u1)
        assert body["source"] == "role"
        assert "dashboard" in keys
        assert len(keys) > 1  # 角色默认菜单不止 dashboard

    def test_pack_update_immediate_effect(self, ctx):
        """改包 menu_keys 后，绑定用户菜单即时变化"""
        client, db = ctx
        pack = _create_pack(client, menu_keys=("dashboard", "villages"))
        u1 = _create_user(db, "u1", role="user")
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        client.put(
            f"/api/v1/permission-packs/{pack['id']}",
            json={"menu_keys": ["dashboard", "schools"]},
        )
        db.expire_all()
        u1 = db.get(type(u1), u1.id)
        body, keys = _accessible_keys(client, u1)
        assert body["source"] == "pack"
        assert keys == {"dashboard", "schools"} | _PUBLIC_TOP_KEYS

    def test_inactive_pack_falls_back_to_role(self, ctx):
        """包被停用(is_active=False)后，绑定用户回落角色默认"""
        client, db = ctx
        pack = _create_pack(client, menu_keys=("dashboard",))
        u1 = _create_user(db, "u1", role="user")
        client.post(
            f"/api/v1/permission-packs/{pack['id']}/bind-users",
            json={"user_ids": [u1.id]},
        )
        client.put(
            f"/api/v1/permission-packs/{pack['id']}", json={"is_active": False}
        )
        db.expire_all()
        u1 = db.get(type(u1), u1.id)
        body, keys = _accessible_keys(client, u1)
        assert body["source"] == "role"
        assert len(keys) > 1

    def test_unbound_user_regression(self, ctx):
        """回归：未绑包普通用户 = 角色默认 + 公开模块（政策法规/数据分析）"""
        client, db = ctx
        u1 = _create_user(db, "u1", role="user")
        body, keys = _accessible_keys(client, u1)
        assert body["source"] == "role"
        assert "dashboard" in keys
        assert "system" not in keys  # 系统管理组仅管理员可见

        # 菜单树 = 角色默认过滤结果 + 公开模块强制并入（2026-08-15）
        from app.api.v1.menus import (
            MENU_DEFINITIONS,
            _PUBLIC_ACCESS_KEYS,
            _filter_menu_tree,
            _get_role_default_menu_keys,
        )

        expected = _filter_menu_tree(
            MENU_DEFINITIONS,
            set(_get_role_default_menu_keys("user")) | _PUBLIC_ACCESS_KEYS,
        )
        assert body["data"] == expected


# =====================================================================
#  管理员权限守卫
# =====================================================================
class TestAdminGuard:
    def test_non_admin_all_endpoints_403(self, client_with_db):
        client, db = client_with_db
        viewer = Mock()
        viewer.id = 9
        viewer.username = "viewer"
        viewer.role = "viewer"
        viewer.is_superuser = False
        viewer.is_active = True
        _set_auth(client, viewer)

        assert client.get("/api/v1/permission-packs").status_code == 403
        assert (
            client.post(
                "/api/v1/permission-packs",
                json={"name": "x", "menu_keys": []},
            ).status_code
            == 403
        )
        assert (
            client.put("/api/v1/permission-packs/1", json={"name": "x"}).status_code
            == 403
        )
        assert client.delete("/api/v1/permission-packs/1").status_code == 403
        assert (
            client.post(
                "/api/v1/permission-packs/1/bind-users", json={"user_ids": [1]}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/permission-packs/1/unbind-users", json={"user_ids": [1]}
            ).status_code
            == 403
        )
