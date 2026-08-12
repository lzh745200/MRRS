"""
Comprehensive pytest tests for app.api.v1.menus — all 5 endpoints.

Covers:
  - GET  /menus/accessible         (no authz required)
  - GET  /menus/all                (admin-only)
  - GET  /menus/user-menus/{uid}   (admin-only)
  - PUT  /menus/user-menus/{uid}   (admin-only)
  - GET  /menus/role-defaults      (admin-only)

Edge cases:
  - empty menu list
  - invalid / non-existent user id
  - duplicate menu keys in PUT body
  - superuser vs admin vs non-admin
  - custom vs role-default modes
  - self-modification guard
  - invalid menu keys in PUT body
  - user with allowed_menus = '' (falsy → treated as None)
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────
def _make_user(
    user_id: int = 2,
    username: str = "testuser",
    role: str = "admin",
    is_superuser: bool = False,
    allowed_menus: str | None = None,
    full_name: str = "Test User",
):
    """Build a MagicMock User with just enough surface for the router."""
    user = MagicMock()
    user.id = user_id
    user.username = username
    user.role = role
    user.is_superuser = is_superuser
    user.full_name = full_name

    # allowed_menus is the raw DB column (JSON string or None)
    user.allowed_menus = allowed_menus

    # allowed_menus_list mirrors the real property on models.user.User
    if not allowed_menus:
        user.allowed_menus_list = None
    else:
        try:
            user.allowed_menus_list = json.loads(allowed_menus)
        except (json.JSONDecodeError, TypeError):
            user.allowed_menus_list = None
    return user


# ── fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def mock_db():
    """Fake SQLAlchemy session."""
    session = MagicMock()
    return session


@pytest.fixture
def admin_user():
    """Default admin user used by most tests."""
    return _make_user(user_id=1, username="admin", role="admin", is_superuser=False)


@pytest.fixture
def super_admin_user():
    return _make_user(user_id=1, username="superadmin", role="super_admin", is_superuser=True)


@pytest.fixture
def non_admin_user():
    return _make_user(user_id=3, username="viewer", role="viewer", is_superuser=False)


@pytest.fixture
def manager_user():
    return _make_user(user_id=4, username="manager", role="manager", is_superuser=False)


# ── FastAPI app with the menus router wired up ───────────────────────
@pytest.fixture
def menus_app(mock_db, admin_user):
    """Create a clean FastAPI app with the menus router and dependency overrides."""
    from app.api.v1 import deps as api_deps  # re-exports get_db / get_current_user

    app = FastAPI()
    app.dependency_overrides[api_deps.get_db] = lambda: mock_db
    app.dependency_overrides[api_deps.get_current_user] = lambda: admin_user

    from app.api.v1.menus import router
    app.include_router(router)
    return app


@pytest.fixture
def client(menus_app):
    return TestClient(menus_app)


# ── convenience: override get_current_user per-test ───────────────────
def _set_user(menus_app, user: MagicMock):
    from app.api.v1 import deps as api_deps
    menus_app.dependency_overrides[api_deps.get_current_user] = lambda: user


# =====================================================================
#  GET /menus/accessible
# =====================================================================
class TestGetAccessibleMenus:
    """Tests for GET /menus/accessible — the current-user-visible menu tree."""

    def test_role_default_source_when_no_custom_menus(self, menus_app, client, non_admin_user):
        """When allowed_menus_list is None the source must be 'role'."""
        _set_user(menus_app, non_admin_user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["source"] == "role"
        assert isinstance(body["data"], list)

    def test_custom_source_when_allowed_menus_set(self, menus_app, client):
        """When the user has a custom allowed_menus list the source is 'user'."""
        user = _make_user(user_id=5, username="custom", role="viewer",
                          allowed_menus='["dashboard"]')
        _set_user(menus_app, user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["source"] == "user"
        assert len(body["data"]) == 1
        assert body["data"][0]["key"] == "dashboard"

    def test_empty_allowed_menus_list_returns_no_menus(self, menus_app, client):
        """allowed_menus = '[]' → user gets zero menus."""
        user = _make_user(user_id=6, username="empty", role="viewer",
                          allowed_menus="[]")
        _set_user(menus_app, user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["source"] == "user"
        assert body["data"] == []

    def test_role_default_for_admin_includes_many_keys(self, menus_app, client, admin_user):
        """An admin with no custom menus gets a large set from role defaults."""
        _set_user(menus_app, admin_user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "role"
        keys = [m["key"] for m in body["data"]]
        assert "dashboard" in keys
        assert "system" in keys

    def test_role_default_for_viewer_is_subset(self, menus_app, client, non_admin_user):
        """A viewer role sees fewer menus than an admin."""
        _set_user(menus_app, non_admin_user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        keys = [m["key"] for m in body["data"]]
        # viewer should NOT see system（系统管理仍仅管理员可见）
        assert "system" not in keys
        # 经费管理对普通用户开放菜单（操作权限由 require_funds_operator_role 限制）
        assert "funds-admin" in keys
        assert "funds-lifecycle" in keys
        assert "funds-settlement" in keys
        # viewer should see generic-access menus
        assert "dashboard" in keys

    def test_custom_menus_include_children(self, menus_app, client):
        """When parent AND child keys are allowed, children appear in the tree."""
        menukeys = [
            "analytics", "analytics-dashboard", "analytics-map",
            "work-analysis", "dashboard",
        ]
        user = _make_user(user_id=7, username="partial", role="viewer",
                          allowed_menus=json.dumps(menukeys))
        _set_user(menus_app, user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        keys = [m["key"] for m in body["data"]]
        assert "analytics" in keys
        assert "dashboard" in keys
        # analytics has children; they should be included because all child keys
        # are explicitly in the allowed_menus list
        analytics = next(m for m in body["data"] if m["key"] == "analytics")
        assert "children" in analytics
        assert len(analytics["children"]) > 0

    def test_super_admin_accessible(self, menus_app, client, super_admin_user):
        """Super admin with no custom menus gets all menus."""
        _set_user(menus_app, super_admin_user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "role"
        keys = [m["key"] for m in body["data"]]
        assert "system" in keys

    def test_allowed_menus_is_empty_string_treated_as_none(self, menus_app, client):
        """allowed_menus = '' → falsy → allowed_menus_list returns None → role default."""
        user = _make_user(user_id=8, username="emptystr", role="viewer",
                          allowed_menus="")
        _set_user(menus_app, user)
        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "role"


# =====================================================================
#  GET /menus/all
# =====================================================================
class TestGetAllMenus:
    """Tests for GET /menus/all — full definitions (admin only)."""

    def test_admin_gets_all_definitions(self, menus_app, client, admin_user):
        _set_user(menus_app, admin_user)
        resp = client.get("/menus/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        # at least the well-known top-level menus should be present
        keys = [m["key"] for m in body["data"]]
        for k in ("dashboard", "villages", "schools", "system"):
            assert k in keys

    def test_super_admin_gets_all_definitions(self, menus_app, client, super_admin_user):
        _set_user(menus_app, super_admin_user)
        resp = client.get("/menus/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_non_admin_forbidden(self, menus_app, client, non_admin_user):
        _set_user(menus_app, non_admin_user)
        resp = client.get("/menus/all")
        assert resp.status_code == 403
        assert "管理员权限" in resp.json()["detail"]

    def test_manager_not_admin(self, menus_app, client):
        """manager role is NOT in (ROLE_ADMIN, ROLE_SUPER_ADMIN) and not superuser."""
        user = _make_user(user_id=9, username="mgr", role="manager")
        _set_user(menus_app, user)
        resp = client.get("/menus/all")
        assert resp.status_code == 403


# =====================================================================
#  GET /menus/user-menus/{user_id}
# =====================================================================
class TestGetUserMenuConfig:
    """Tests for GET /menus/user-menus/{user_id} — admin-only lookup."""

    def test_admin_gets_custom_user_config(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=10, username="target", role="viewer",
                            allowed_menus='["dashboard","villages"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.get("/menus/user-menus/10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["mode"] == "custom"
        assert body["data"]["is_customized"] is True
        assert body["data"]["user_id"] == 10
        assert body["data"]["menu_keys"] == ["dashboard", "villages"]

    def test_admin_gets_role_default_user_config(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=11, username="roledef", role="viewer",
                            allowed_menus=None)
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.get("/menus/user-menus/11")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["mode"] == "role_default"
        assert body["data"]["is_customized"] is False
        assert "role_default_keys" in body["data"]
        assert "all_valid_keys" in body["data"]

    def test_non_admin_forbidden(self, menus_app, client, non_admin_user):
        _set_user(menus_app, non_admin_user)
        resp = client.get("/menus/user-menus/10")
        assert resp.status_code == 403

    def test_user_not_found(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        resp = client.get("/menus/user-menus/999")
        assert resp.status_code == 404
        assert "用户不存在" in resp.json()["detail"]

    def test_user_with_empty_allowed_menus_shows_custom_mode(self, menus_app, client, mock_db, admin_user):
        """allowed_menus='[]' is truthy → allowed_menus_list returns [] → custom mode."""
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=12, username="emptyarr", role="viewer",
                            allowed_menus="[]")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.get("/menus/user-menus/12")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["mode"] == "custom"
        assert body["data"]["menu_keys"] == []

    def test_super_admin_can_access(self, menus_app, client, mock_db, super_admin_user):
        _set_user(menus_app, super_admin_user)
        target = _make_user(user_id=13, username="tgt", role="viewer",
                            allowed_menus=None)
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.get("/menus/user-menus/13")
        assert resp.status_code == 200


# =====================================================================
#  PUT /menus/user-menus/{user_id}
# =====================================================================
class TestSetUserMenuConfig:
    """Tests for PUT /menus/user-menus/{user_id} — admin-only mutation."""

    # ── success cases ────────────────────────────────────────────────
    def test_set_custom_menu_keys(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=20, username="tgt", role="viewer",
                            allowed_menus=None)
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put(
            "/menus/user-menus/20",
            json={"menu_keys": ["dashboard", "villages", "schools"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["mode"] == "custom"
        assert "已设置" in body["message"]
        mock_db.commit.assert_called()

    def test_restore_role_defaults(self, menus_app, client, mock_db, admin_user):
        """menu_keys = None → restore role defaults (clear allowed_menus)."""
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=21, username="tgt", role="viewer",
                            allowed_menus='["dashboard"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put("/menus/user-menus/21", json={"menu_keys": None})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["mode"] == "role_default"
        assert "恢复角色默认" in body["message"]
        assert target.allowed_menus is None
        mock_db.commit.assert_called()

    def test_clear_all_menus(self, menus_app, client, mock_db, admin_user):
        """menu_keys = [] → user gets zero menus."""
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=22, username="tgt", role="viewer",
                            allowed_menus='["dashboard"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put("/menus/user-menus/22", json={"menu_keys": []})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["mode"] == "custom"
        assert "清空" in body["message"]
        mock_db.commit.assert_called()

    def test_duplicate_menu_keys_accepted(self, menus_app, client, mock_db, admin_user):
        """Duplicates are not rejected — they pass validation and are stored as-is."""
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=23, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put(
            "/menus/user-menus/23",
            json={"menu_keys": ["dashboard", "dashboard", "villages"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    # ── authz / not-found guards ─────────────────────────────────────
    def test_non_admin_forbidden(self, menus_app, client, non_admin_user):
        _set_user(menus_app, non_admin_user)
        resp = client.put("/menus/user-menus/20", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 403

    def test_user_not_found(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        resp = client.put("/menus/user-menus/999", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 404
        assert "用户不存在" in resp.json()["detail"]

    def test_cannot_modify_self(self, menus_app, client, mock_db, admin_user):
        """Admin cannot change their own menu permissions (prevents lock-out)."""
        _set_user(menus_app, admin_user)
        # admin_user.id == 1, so target user_id=1 is self
        target = _make_user(user_id=1, username="admin", role="admin")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put("/menus/user-menus/1", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 400
        assert "不能修改自己的菜单权限" in resp.json()["detail"]

    def test_cannot_modify_self_super_admin(self, menus_app, client, mock_db, super_admin_user):
        """Super admin also cannot change their own menu permissions."""
        _set_user(menus_app, super_admin_user)
        target = _make_user(user_id=1, username="superadmin", role="super_admin",
                            is_superuser=True)
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put("/menus/user-menus/1", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 400
        assert "不能修改自己的菜单权限" in resp.json()["detail"]

    # ── invalid keys ─────────────────────────────────────────────────
    def test_invalid_menu_key_rejected(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=24, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put(
            "/menus/user-menus/24",
            json={"menu_keys": ["dashboard", "nonexistent_key_xyz"]},
        )
        assert resp.status_code == 400
        assert "无效的菜单key" in resp.json()["detail"]
        assert "nonexistent_key_xyz" in resp.json()["detail"]

    def test_all_keys_invalid(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=25, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put(
            "/menus/user-menus/25",
            json={"menu_keys": ["bad1", "bad2"]},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "bad1" in detail
        assert "bad2" in detail

    def test_mixed_valid_and_invalid_keys(self, menus_app, client, mock_db, admin_user):
        """If at least one key is invalid, the entire request is rejected."""
        _set_user(menus_app, admin_user)
        target = _make_user(user_id=26, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.put(
            "/menus/user-menus/26",
            json={"menu_keys": ["dashboard", "invalid_one"]},
        )
        assert resp.status_code == 400
        assert "invalid_one" in resp.json()["detail"]
        # commit should NOT have been called
        mock_db.commit.assert_not_called()

    # ── edge: non-existent user id 0 ─────────────────────────────────
    def test_user_id_zero_not_found(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = client.put("/menus/user-menus/0", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 404

    # ── edge: manager user (is_admin False) tries to modify ──────────
    def test_manager_cannot_modify(self, menus_app, client, manager_user):
        _set_user(menus_app, manager_user)
        resp = client.put("/menus/user-menus/20", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 403


# =====================================================================
#  GET /menus/role-defaults
# =====================================================================
class TestGetRoleDefaultMenus:
    """Tests for GET /menus/role-defaults — admin only."""

    def test_admin_gets_all_role_defaults(self, menus_app, client, admin_user):
        _set_user(menus_app, admin_user)
        resp = client.get("/menus/role-defaults")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], dict)
        assert "super_admin" in body["data"]
        assert "admin" in body["data"]
        assert "viewer" in body["data"]
        # super_admin should have more keys than viewer
        assert len(body["data"]["super_admin"]) > len(body["data"]["viewer"])

    def test_non_admin_forbidden(self, menus_app, client, non_admin_user):
        _set_user(menus_app, non_admin_user)
        resp = client.get("/menus/role-defaults")
        assert resp.status_code == 403

    def test_manager_cannot_access(self, menus_app, client, manager_user):
        _set_user(menus_app, manager_user)
        resp = client.get("/menus/role-defaults")
        assert resp.status_code == 403

    def test_super_admin_can_access(self, menus_app, client, super_admin_user):
        _set_user(menus_app, super_admin_user)
        resp = client.get("/menus/role-defaults")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True


# =====================================================================
#  Integration-like: multiple calls with the same app
# =====================================================================
class TestEndToEndFlow:
    """Simulate a real admin workflow: look up a user, then update them."""

    def test_lookup_then_update(self, menus_app, client, mock_db, admin_user):
        _set_user(menus_app, admin_user)

        # Step 1 — look up a viewer user
        target = _make_user(user_id=30, username="flowuser", role="viewer",
                            allowed_menus=None)
        mock_db.query.return_value.filter.return_value.first.return_value = target

        resp = client.get("/menus/user-menus/30")
        assert resp.status_code == 200
        assert resp.json()["data"]["mode"] == "role_default"

        # Step 2 — set custom menus for that user
        resp = client.put(
            "/menus/user-menus/30",
            json={"menu_keys": ["dashboard", "schools", "policies"]},
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "custom"
        assert resp.json()["success"] is True

    def test_restore_after_custom(self, menus_app, client, mock_db, admin_user):
        """Set custom menus, then restore to role defaults."""
        _set_user(menus_app, admin_user)

        target = _make_user(user_id=31, username="rst", role="viewer",
                            allowed_menus='["dashboard"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target

        # First, confirm it is custom
        resp = client.get("/menus/user-menus/31")
        assert resp.json()["data"]["mode"] == "custom"

        # Then restore
        resp = client.put("/menus/user-menus/31", json={"menu_keys": None})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "role_default"
        assert target.allowed_menus is None


# =====================================================================
#  Unit-level: pure-function helpers
# =====================================================================
class TestHelperFunctions:
    """Direct unit tests of the helper functions inside menus.py."""

    def test_is_admin_true_for_admin_role(self):
        from app.api.v1.menus import _is_admin
        user = _make_user(role="admin")
        assert _is_admin(user) is True

    def test_is_admin_true_for_super_admin(self):
        from app.api.v1.menus import _is_admin
        user = _make_user(role="super_admin")
        assert _is_admin(user) is True

    def test_is_admin_true_for_superuser_flag(self):
        from app.api.v1.menus import _is_admin
        user = _make_user(role="viewer", is_superuser=True)
        assert _is_admin(user) is True

    def test_is_admin_false_for_viewer(self):
        from app.api.v1.menus import _is_admin
        user = _make_user(role="viewer")
        assert _is_admin(user) is False

    def test_is_admin_false_for_operator(self):
        from app.api.v1.menus import _is_admin
        user = _make_user(role="operator")
        assert _is_admin(user) is False

    def test_is_admin_false_for_approval_leader(self):
        from app.api.v1.menus import _is_admin
        user = _make_user(role="approval_leader")
        assert _is_admin(user) is False

    def test_flatten_menu_keys_includes_all(self):
        from app.api.v1.menus import _flatten_menu_keys, MENU_DEFINITIONS
        all_keys = _flatten_menu_keys(MENU_DEFINITIONS)
        assert "dashboard" in all_keys
        assert "system" in all_keys
        assert "backup" in all_keys  # child key
        assert "comprehensive-entry" in all_keys  # nested child
        # total should be reasonable (14 top-level + children)
        assert len(all_keys) > 20

    def test_filter_menu_tree_respects_allowed_keys(self):
        from app.api.v1.menus import _filter_menu_tree, MENU_DEFINITIONS
        filtered = _filter_menu_tree(MENU_DEFINITIONS, {"dashboard"})
        assert len(filtered) == 1
        assert filtered[0]["key"] == "dashboard"
        assert "children" not in filtered[0]

    def test_filter_menu_tree_includes_children_when_parent_allowed(self):
        from app.api.v1.menus import _filter_menu_tree, MENU_DEFINITIONS
        # analytics has children; all children keys must also be in allowed_keys
        filtered = _filter_menu_tree(
            MENU_DEFINITIONS,
            {"analytics", "analytics-dashboard", "analytics-map", "work-analysis"},
        )
        analytics = next(m for m in filtered if m["key"] == "analytics")
        assert "children" in analytics
        assert len(analytics["children"]) == 3

    def test_filter_menu_tree_empty_allowed_keys(self):
        from app.api.v1.menus import _filter_menu_tree, MENU_DEFINITIONS
        filtered = _filter_menu_tree(MENU_DEFINITIONS, set())
        assert filtered == []

    def test_role_default_menu_keys_are_frozenset(self):
        from app.api.v1.menus import _get_role_default_menu_keys
        keys = _get_role_default_menu_keys("admin")
        assert isinstance(keys, frozenset)
        assert len(keys) > 5

    def test_role_default_viewer_has_no_admin_keys(self):
        from app.api.v1.menus import _get_role_default_menu_keys
        viewer_keys = _get_role_default_menu_keys("viewer")
        assert "system" not in viewer_keys
        # 经费管理对普通用户（含 viewer）可见菜单，但操作权限由 require_funds_operator_role 限制
        assert "funds-admin" in viewer_keys
        assert "funds-lifecycle" in viewer_keys
        assert "funds-settlement" in viewer_keys

    def test_get_user_accessible_uses_custom_over_role(self):
        from app.api.v1.menus import _get_user_accessible_menu_keys
        user = _make_user(role="admin", allowed_menus='["dashboard"]')
        keys = _get_user_accessible_menu_keys(user)
        assert keys == {"dashboard"}

    def test_get_user_accessible_falls_back_to_role(self):
        from app.api.v1.menus import _get_user_accessible_menu_keys
        user = _make_user(role="viewer", allowed_menus=None)
        keys = _get_user_accessible_menu_keys(user)
        assert "dashboard" in keys
        assert "system" not in keys

    def test_get_user_accessible_empty_list_means_no_menus(self):
        from app.api.v1.menus import _get_user_accessible_menu_keys
        user = _make_user(role="admin", allowed_menus="[]")
        keys = _get_user_accessible_menu_keys(user)
        assert keys == set()

    def test_lru_cache_on_role_defaults(self):
        """_get_role_default_menu_keys is cached — same role returns same object."""
        from app.api.v1.menus import _get_role_default_menu_keys
        a = _get_role_default_menu_keys("operator")
        b = _get_role_default_menu_keys("operator")
        assert a is b  # same frozenset object via lru_cache

    def test_all_roles_have_at_least_dashboard(self):
        from app.api.v1.menus import _get_role_default_menu_keys
        for role in ("super_admin", "admin", "approval_leader", "manager", "operator", "viewer"):
            keys = _get_role_default_menu_keys(role)
            assert "dashboard" in keys, f"{role} should see dashboard"
