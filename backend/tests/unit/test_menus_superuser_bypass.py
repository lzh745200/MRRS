"""超级管理员菜单豁免（RBAC BugFix）回归测试 —— v2 单一菜单源

背景（2026-09-12）：app/api/v1/menus.py 的 _get_user_accessible_menu_keys
过滤链为「用户级 allowed_menus > 绑定权限包 > 角色默认」，对超级管理员无豁免——
admin 被历史遗留的 allowed_menus 旧配置或权限包裁剪，导致 /menus/accessible
只下发少量菜单；而权限配置弹窗读取的 /menus/all 是全量，形成
"弹窗全勾选、菜单看不到"。

W21（单一菜单源 v2）后响应结构改为
`{version: 2, sections: [...], flat_keys: [...]}`，本文件锁定：
  A. is_superuser=True 且 allowed_menus 是很小的旧集合 → 全量 menus
  B. 普通用户 allowed_menus 小集合 → 仍被裁剪（回归保护，行为不变）
  C. 仅 role='super_admin'（is_superuser 标志为 False）同样豁免
  D. 直接调用 _get_user_accessible_menu_keys 的函数级断言
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# 历史遗留的"很小"用户级菜单配置（修复前会把系统设置等模块全部裁掉）
SMALL_LEGACY_MENUS = json.dumps(["dashboard", "villages"])

# 系统设置下的深层菜单 key（v2 中作为 console tabs 下发）——修复前不在旧 allowed_menus 里
DEEP_MENU_KEYS = ("machine-code", "cache", "admin-dashboard")


# ── helpers ──────────────────────────────────────────────────────────
def _make_user(
    user_id: int = 2,
    username: str = "testuser",
    role: str = "user",
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
    user.allowed_menus = allowed_menus
    user.permission_pack_id = None
    if not allowed_menus:
        user.allowed_menus_list = None
    else:
        try:
            user.allowed_menus_list = json.loads(allowed_menus)
        except (json.JSONDecodeError, TypeError):
            user.allowed_menus_list = None
    return user


def _flatten_sections(sections: list[dict]) -> set[str]:
    """展开 v2 sections 的可见 key（含 group/console 本身 + children + tabs）"""
    keys: set[str] = set()
    for section in sections:
        for item in section["items"]:
            keys.add(item["key"])
            for child in item.get("children") or []:
                keys.add(child["key"])
            for tab in item.get("tabs") or []:
                keys.add(tab["key"])
    return keys


def _section_keys(body: dict) -> set[str]:
    return _flatten_sections(body["data"]["sections"])


# ── fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def mock_db():
    """Fake SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def menus_app(mock_db):
    """Create a clean FastAPI app with the menus router and dependency overrides."""
    from app.api.v1 import deps as api_deps  # re-exports get_db / get_current_user

    app = FastAPI()
    app.dependency_overrides[api_deps.get_db] = lambda: mock_db

    from app.api.v1.menus import router
    app.include_router(router)
    return app


@pytest.fixture
def client(menus_app):
    return TestClient(menus_app)


def _login_as(menus_app, user: MagicMock) -> None:
    from app.api.v1 import deps as api_deps
    menus_app.dependency_overrides[api_deps.get_current_user] = lambda: user


# =====================================================================
#  用例 A：超管豁免
# =====================================================================
class TestSuperuserBypass:
    def test_superuser_with_legacy_allowed_menus_gets_full_tree(self, menus_app, client):
        """用例 A：is_superuser=True 且 allowed_menus 是很小的旧集合 → 全量菜单"""
        from app.api.v1.menus import _iter_definition_keys

        user = _make_user(
            user_id=9,
            username="admin",
            role="admin",
            is_superuser=True,
            allowed_menus=SMALL_LEGACY_MENUS,
        )
        _login_as(menus_app, user)

        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["version"] == 2

        # 全量 = MENU_DEFINITIONS 的全部 key（父级 + children + tabs）；dashboard/历史兼容 key 不入 sections
        all_keys = set(_iter_definition_keys())
        from app.api.v1.menus import MENU_DEFINITIONS
        legacy_keys = {entry["key"] for entry in MENU_DEFINITIONS if entry.get("legacy")}
        assert _section_keys(body) == all_keys - {"dashboard"} - legacy_keys
        # flat_keys 含 dashboard + 历史兼容 key，且为定义顺序全量
        assert body["data"]["flat_keys"] == _iter_definition_keys()
        # 修复前被裁掉的深层系统菜单必须可见（v2 中为 console tabs）
        for key in DEEP_MENU_KEYS:
            assert key in _section_keys(body)

    def test_superuser_source_reporting_unchanged(self, menus_app, client):
        """超管豁免只改 key 集合，不影响 source 判定逻辑（allowed_menus 存在 → 'user'）"""
        user = _make_user(
            user_id=9,
            username="admin",
            role="admin",
            is_superuser=True,
            allowed_menus=SMALL_LEGACY_MENUS,
        )
        _login_as(menus_app, user)

        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        assert resp.json()["source"] == "user"


# =====================================================================
#  用例 B：普通用户回归保护
# =====================================================================
class TestNormalUserUnchanged:
    def test_normal_user_still_trimmed_by_allowed_menus(self, menus_app, client):
        """用例 B：普通用户 + 小 allowed_menus → 仍被裁剪（行为不变）"""
        user = _make_user(
            user_id=10,
            username="viewer",
            role="viewer",
            is_superuser=False,
            allowed_menus=SMALL_LEGACY_MENUS,
        )
        _login_as(menus_app, user)

        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()

        keys = _section_keys(body)
        flat = set(body["data"]["flat_keys"])
        # 用户配置内的菜单仍然可见
        assert "dashboard" in flat
        assert "villages" in keys
        # 修复前被裁掉的深层系统菜单，普通用户依旧不可见（未被豁免波及）
        for key in DEEP_MENU_KEYS:
            assert key not in keys
            assert key not in flat
        # 全角色公开模块仍无条件并入（原有行为不变）
        assert "policies" in keys
        assert "analytics" in keys

    def test_normal_user_allowed_menus_empty_stays_minimal(self, menus_app, client):
        """allowed_menus='[]' 的普通用户仅剩公开模块（回归保护）"""
        from app.api.v1.menus import _PUBLIC_ACCESS_KEYS

        user = _make_user(
            user_id=11,
            username="user",
            role="user",
            is_superuser=False,
            allowed_menus="[]",
        )
        _login_as(menus_app, user)

        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        body = resp.json()
        # 公开模块在 v2 sections 中的可见 key（helpData/data-analysis 为历史兼容 key，不入 sections）
        assert _section_keys(body) == {
            "policies", "analytics", "analytics-dashboard", "analytics-map", "work-analysis",
        }
        # flat_keys = 可见 key + 允许的历史兼容 key
        assert set(body["data"]["flat_keys"]) == set(_PUBLIC_ACCESS_KEYS)


# =====================================================================
#  用例 C/D：仅 role='super_admin' 与函数级断言
# =====================================================================
class TestSuperAdminRoleOnly:
    def test_role_only_super_admin_also_bypassed(self, menus_app, client):
        """用例 C：is_superuser=False 但 role='super_admin' → 同样豁免"""
        user = _make_user(
            user_id=12,
            username="root",
            role="super_admin",
            is_superuser=False,
            allowed_menus=SMALL_LEGACY_MENUS,
        )
        _login_as(menus_app, user)

        resp = client.get("/menus/accessible")
        assert resp.status_code == 200
        keys = _section_keys(resp.json())
        for key in DEEP_MENU_KEYS:
            assert key in keys


class TestBypassAtFunctionLevel:
    def test_superuser_returns_full_definition_keys(self, mock_db):
        """用例 D：直接调用 _get_user_accessible_menu_keys → 等于全量 key"""
        from app.api.v1.menus import (
            MENU_DEFINITIONS,
            _flatten_menu_keys,
            _get_user_accessible_menu_keys,
            _iter_definition_keys,
        )

        superuser = _make_user(
            user_id=13, username="admin", role="admin",
            is_superuser=True, allowed_menus=SMALL_LEGACY_MENUS,
        )
        keys = _get_user_accessible_menu_keys(superuser, mock_db)
        assert keys == _flatten_menu_keys(MENU_DEFINITIONS)
        assert keys == set(_iter_definition_keys())

    def test_normal_user_returns_trimmed_keys(self, mock_db):
        """普通用户同一函数仍走裁剪链（与用例 B 对应的函数级断言）"""
        from app.api.v1.menus import _PUBLIC_ACCESS_KEYS, _get_user_accessible_menu_keys

        normal = _make_user(
            user_id=14, username="viewer", role="viewer",
            is_superuser=False, allowed_menus=SMALL_LEGACY_MENUS,
        )
        keys = _get_user_accessible_menu_keys(normal, mock_db)
        assert keys == {"dashboard", "villages"} | _PUBLIC_ACCESS_KEYS
