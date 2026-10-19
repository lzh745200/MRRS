"""单一菜单源 v2 契约测试（W21）

契约：`.scratch/w21-nav-single-source/000-contract.md` §2/§3/§4/§8。

覆盖目标（`app/api/v1/menus.py` 语句 + 分支 100%）：
- sections 组装（/menus/accessible 与 /menus/all 的 v2 结构）；
- 三级过滤优先级：superuser 全量 > user.allowed_menus > 启用中权限包 > 角色默认；
- group 可见性 / children 裁剪；console 可见性 / tabs 裁剪（契约 §3）；
- `_PUBLIC_ACCESS_KEYS` 无条件并入；历史兼容 key 的 flat_keys 语义；
- 6 个系统管理 console + tabs 的契约结构（§4）；
- 角色默认 / 角色归一化；/menus/user-menus 读写；异常分支。
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import deps as api_deps  # 与 menus.py 共享同一个 get_db/get_current_user 对象


# 契约 §4：6 个板块（工作台 dashboard 固定渲染，不入 sections）
CONTRACT_SECTIONS = [
    ("business", "帮扶业务", 10),
    ("rural", "乡村振兴", 20),
    ("collab", "工作协同", 30),
    ("report", "分析汇报", 40),
    ("data", "数据管理", 50),
    ("system", "系统管理", 90),
]

# 契约 §4：系统管理 6 个聚合页 console -> tabs(key, path)
CONTRACT_CONSOLES = {
    "system-console-org": (
        "/system/console/org",
        [
            ("users-orgs", "/system/users"),
            ("roles", "/system/roles"),
            ("menus", "/system/menus"),
            ("system-permission-packs", "/system/permission-packs"),
            ("organizations", "/organization"),
            # R34：R33 单位授权的两个页面补齐导航出口
            ("system-org-grant", "/system/org-grant"),
            ("system-grant-import", "/system/grant-import"),
        ],
    ),
    "system-console-security": (
        "/system/console/security",
        [
            ("audit", "/system/audit"),
            ("zero-trust", "/system/zero-trust"),
            ("secrets", "/system/secrets"),
            ("data-tier", "/system/data-tier"),
            ("encryption", "/system/encryption"),
            ("machine-code", "/admin/machine-code/management"),
        ],
    ),
    "system-console-ops": (
        "/system/console/ops",
        [
            ("system-overview", "/system/overview"),
            ("health-check", "/system/health-check"),
            ("monitor", "/system/monitoring"),
            ("cache", "/system/cache"),
            ("tasks", "/system/tasks"),
            ("environment", "/system/environment"),
            ("error-reports", "/system/error-reports"),
        ],
    ),
    "system-console-storage": (
        "/system/console/storage",
        [
            ("backup", "/system/backup"),
            ("chunked-upload", "/system/chunked-upload"),
            ("map-tiles", "/system/map-tiles"),
            ("control-package", "/system/control-package"),
            ("config-package", "/system/config"),
        ],
    ),
    "system-console-settings": (
        "/system/console/settings",
        [
            # W22（v1.14.0）：i18n 多语言与 email 邮件设置随需求下线（key 保留为 legacy）
            ("update-logs", "/system/update-logs"),
        ],
    ),
    "system-console-about": (
        "/system/console/about",
        [
            ("about", "/system/about"),
            ("feedback", "/system/feedback"),
            ("help", "/help"),
            ("admin-dashboard", "/admin/dashboard"),
        ],
    ),
}

# 旧 key（W21 之前 MENU_DEFINITIONS 中的全部 key）——必须全部保留（可承载的进
# children/tabs，无导航出口的进历史兼容 key），仅 3 个死项/重复项显式删除。
OLD_MENU_KEYS = {
    "dashboard", "villages", "schools", "projects", "funds-admin", "funds-user",
    "funds-lifecycle", "funds-settlement", "policies", "rural-works", "approval",
    "helpData", "comprehensive-entry", "batch-import", "data-verify", "validation-rules",
    "data-analysis", "report-templates", "report-export", "analytics", "analytics-dashboard",
    "analytics-map", "work-analysis", "data-upload", "data-package-report",
    "data-package-receive", "data-package-list", "data-package-version", "data",
    "data-overview", "user-backup", "data-quality", "data-logs", "batch-operations",
    "system", "machine-code", "pass-code", "users-orgs", "system-config", "audit",
    "feedback", "backup", "cache", "monitor", "help", "health-check", "about",
    "update-logs", "system-permission-packs", "tasks", "secrets", "i18n", "data-tier",
    "map-tiles", "environment", "zero-trust", "error-reports", "system-overview",
    "admin-dashboard", "messages", "effectiveness", "effectiveness-rankings",
    "effectiveness-evaluate", "todos", "sentiment", "reminder", "checkin",
    "system-security", "pairing", "donation", "handover",
}

# 契约 §4 中新增的 tab key（旧前端 menu-config 已有、旧后端 MENU_DEFINITIONS 没有；
# 其余 tab key 必须沿用旧 key 以保持权限包兼容）
NEW_TAB_KEYS = {
    "roles", "menus", "organizations", "encryption",
    "chunked-upload", "control-package", "config-package", "email",
    # R34：R33 单位授权两个 tab（新增 key，无旧 key 可沿用）
    "system-org-grant", "system-grant-import",
}

# 契约明确删除的死项 / 重复路径项
DELETED_MENU_KEYS = {"user-backup", "data-quality", "system-security"}


# ── helpers ──────────────────────────────────────────────────────────
def _make_user(
    user_id: int = 2,
    username: str = "testuser",
    role: str = "user",
    is_superuser: bool = False,
    allowed_menus: str | None = None,
    full_name: str = "Test User",
):
    """构造仅具备 menus 路由所需表面的 MagicMock User"""
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


def _make_pack(menu_keys=("dashboard", "villages")):
    pack = MagicMock()
    pack.menu_keys_list = list(menu_keys)
    return pack


def _sections_keys(sections: list[dict]) -> set[str]:
    """展开 sections 的可见 key（含 group/console 本身 + children + tabs）"""
    keys: set[str] = set()
    for section in sections:
        for item in section["items"]:
            keys.add(item["key"])
            for child in item.get("children") or []:
                keys.add(child["key"])
            for tab in item.get("tabs") or []:
                keys.add(tab["key"])
    return keys


def _iter_entries(definitions: list[dict]) -> list[tuple[dict, str]]:
    """展开全部条目：[(entry, role)]，role ∈ top / child / tab（与门禁脚本口径一致）"""
    flattened: list[tuple[dict, str]] = []
    for entry in definitions:
        flattened.append((entry, "top"))
        for child in entry.get("children") or []:
            flattened.append((child, "child"))
        for tab in entry.get("tabs") or []:
            flattened.append((tab, "tab"))
    return flattened


def _legacy_keys() -> set[str]:
    from app.api.v1.menus import MENU_DEFINITIONS
    return {entry["key"] for entry in MENU_DEFINITIONS if entry.get("legacy")}


# ── fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def admin_user():
    return _make_user(user_id=1, username="admin", role="admin", is_superuser=False)


@pytest.fixture
def super_admin_user():
    return _make_user(user_id=1, username="root", role="super_admin", is_superuser=True)


@pytest.fixture
def menus_app(mock_db, admin_user):
    app = FastAPI()
    app.dependency_overrides[api_deps.get_db] = lambda: mock_db
    app.dependency_overrides[api_deps.get_current_user] = lambda: admin_user

    from app.api.v1.menus import router
    app.include_router(router)
    return app


@pytest.fixture
def client(menus_app):
    return TestClient(menus_app)


def _set_user(menus_app, user: MagicMock) -> None:
    menus_app.dependency_overrides[api_deps.get_current_user] = lambda: user


# =====================================================================
#  契约 §4：单一菜单源结构
# =====================================================================
class TestMenuSourceStructure:
    def test_sections_exact_contract(self):
        from app.api.v1.menus import MENU_SECTIONS

        actual = [(s["key"], s["label"], s["order"]) for s in MENU_SECTIONS]
        assert actual == CONTRACT_SECTIONS

    def test_six_consoles_exact_contract(self):
        from app.api.v1.menus import MENU_SECTIONS, _section_entries

        system_items = [
            entry for section in MENU_SECTIONS if section["key"] == "system"
            for entry in _section_entries(section["key"])
        ]
        console_keys = [item["key"] for item in system_items]
        assert console_keys == list(CONTRACT_CONSOLES)
        for item in system_items:
            expected_path, expected_tabs_keys = CONTRACT_CONSOLES[item["key"]]
            assert item["kind"] == "console"
            assert item["path"] == expected_path
            assert item["roles"] == ["admin", "super_admin"]
            assert [(tab["key"], tab["path"]) for tab in item["tabs"]] == expected_tabs_keys
            # tabs.key 必须是旧 key（权限包兼容），仅契约新增的 8 个 tab key 例外；
            # 且不得带 kind 字段（契约 §2）
            for tab in item["tabs"]:
                assert tab["key"] in OLD_MENU_KEYS | NEW_TAB_KEYS
                assert "kind" not in tab
                assert "roles" in tab

    def test_old_keys_all_retained_except_documented_deletions(self):
        from app.api.v1.menus import _iter_definition_keys

        current = set(_iter_definition_keys())
        missing = OLD_MENU_KEYS - current - DELETED_MENU_KEYS
        assert missing == set(), f"旧 key 丢失: {sorted(missing)}"
        assert current & DELETED_MENU_KEYS == set()
        # 3 个死项删除理由见 menus.py 注释（重复路径 / 占位分组）
        assert DELETED_MENU_KEYS == {"user-backup", "data-quality", "system-security"}

    def test_section_items_order_and_path_uniqueness(self):
        from app.api.v1.menus import MENU_DEFINITIONS, MENU_SECTIONS, _section_entries

        paths: list[str] = []
        for section in MENU_SECTIONS:
            entries = _section_entries(section["key"])
            orders = [entry["order"] for entry in entries]
            assert orders == sorted(orders)
            assert len(entries) > 0
        for entry, _role in _iter_entries(MENU_DEFINITIONS):
            if entry.get("path"):
                paths.append(entry["path"])
        assert len(paths) == len(set(paths)), "契约 §7 规则 D：菜单路径必须唯一"

    def test_definition_keys_unique(self):
        from app.api.v1.menus import _iter_definition_keys

        keys = _iter_definition_keys()
        assert len(keys) == len(set(keys))

    def test_legacy_keys_have_no_section_and_no_path(self):
        from app.api.v1.menus import MENU_DEFINITIONS

        legacy = [entry for entry in MENU_DEFINITIONS if entry.get("legacy")]
        assert len(legacy) > 0
        for entry in legacy:
            assert entry["section"] is None
            assert entry["path"] is None


def _load_definitions():
    from app.api.v1.menus import _iter_entries, MENU_DEFINITIONS
    return [entry for entry, _role in _iter_entries(MENU_DEFINITIONS)]


# =====================================================================
#  /menus/accessible
# =====================================================================
class TestAccessibleMenus:
    def test_v2_shape_and_version(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer"))
        body = client.get("/menus/accessible").json()
        assert body["success"] is True
        data = body["data"]
        assert data["version"] == 2
        assert set(data) == {"version", "sections", "flat_keys"}
        assert isinstance(data["sections"], list) and data["sections"]
        assert isinstance(data["flat_keys"], list) and data["flat_keys"]
        for section in data["sections"]:
            assert set(section) == {"key", "label", "order", "items"}
            assert section["items"]
            for item in section["items"]:
                assert item["kind"] in {"page", "group", "console"}
                assert "path" in item or item["kind"] == "group"
                if item["kind"] == "group":
                    assert "path" not in item and item["children"]
                if item["kind"] == "console":
                    assert item["path"] and item["tabs"]

    def test_superuser_gets_full_tree(self, menus_app, client, super_admin_user):
        from app.api.v1.menus import _iter_definition_keys

        _set_user(menus_app, super_admin_user)
        body = client.get("/menus/accessible").json()
        assert body["source"] == "role"
        # superuser 全量：sections 覆盖除 dashboard/历史兼容 key 外的全部 key
        non_section = {"dashboard"} | _legacy_keys()
        assert _sections_keys(body["data"]["sections"]) == set(_iter_definition_keys()) - non_section
        # flat_keys 含 dashboard + 历史兼容 key，且为定义顺序全量
        assert body["data"]["flat_keys"] == _iter_definition_keys()

    def test_role_default_viewer_has_no_admin_console(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer"))
        body = client.get("/menus/accessible").json()
        assert body["source"] == "role"
        keys = set(body["data"]["flat_keys"])
        assert "dashboard" in keys
        assert "funds-admin" in keys
        assert "system-console-org" not in keys
        assert "system-console-about" in keys  # about/help tabs roles=None → 全角色可见

    def test_user_level_allowed_menus_source_user(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer", allowed_menus='["dashboard", "villages"]'))
        body = client.get("/menus/accessible").json()
        assert body["source"] == "user"
        sections = body["data"]["sections"]
        keys = _sections_keys(sections)
        assert "villages" in keys
        assert "projects" not in keys
        # 公开模块强制并入
        assert {"policies", "analytics", "analytics-dashboard", "analytics-map", "work-analysis"} <= keys
        # dashboard 不在 sections，但在 flat_keys（前端固定渲染）
        assert "dashboard" not in keys
        assert body["data"]["flat_keys"][0] == "dashboard"

    def test_empty_allowed_menus_only_public_modules(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer", allowed_menus="[]"))
        body = client.get("/menus/accessible").json()
        assert body["source"] == "user"
        keys = set(body["data"]["flat_keys"])
        assert "dashboard" not in keys
        assert {"policies", "analytics", "analytics-dashboard", "analytics-map",
                "work-analysis", "helpData", "data-analysis"} == keys

    def test_pack_source(self, menus_app, client, mock_db):
        user = _make_user(role="user")
        user.permission_pack_id = 7
        mock_db.query.return_value.filter.return_value.first.return_value = _make_pack()
        _set_user(menus_app, user)
        body = client.get("/menus/accessible").json()
        assert body["source"] == "pack"
        keys = set(body["data"]["flat_keys"])
        assert "villages" in keys
        assert "projects" not in keys

    def test_pack_disabled_falls_back_to_role(self, menus_app, client, mock_db):
        user = _make_user(role="user")
        user.permission_pack_id = 7
        mock_db.query.return_value.filter.return_value.first.return_value = None
        _set_user(menus_app, user)
        body = client.get("/menus/accessible").json()
        assert body["source"] == "role"

    def test_group_children_trimmed_when_partially_allowed(self, menus_app, client):
        _set_user(menus_app, _make_user(
            role="viewer", allowed_menus='["funds-admin"]',
        ))
        body = client.get("/menus/accessible").json()
        funds = None
        for section in body["data"]["sections"]:
            for item in section["items"]:
                if item["key"] == "funds":
                    funds = item
        assert funds is not None
        assert funds["kind"] == "group"
        assert [child["key"] for child in funds["children"]] == ["funds-admin"]

    def test_group_hidden_when_no_child_allowed(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer", allowed_menus='["funds"]'))
        body = client.get("/menus/accessible").json()
        keys = _sections_keys(body["data"]["sections"])
        assert "funds" not in keys  # group 自身 key 在 allowed 中，但无 child 可见 → 不出现

    def test_console_visible_when_console_key_allowed_all_tabs(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer", allowed_menus='["system-console-ops"]'))
        body = client.get("/menus/accessible").json()
        console = _find_item(body["data"]["sections"], "system-console-ops")
        assert console is not None
        assert {tab["key"] for tab in console["tabs"]} == {
            "system-overview", "health-check", "monitor", "cache", "tasks",
            "environment", "error-reports",
        }

    def test_console_visible_when_only_tab_key_allowed(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer", allowed_menus='["cache"]'))
        body = client.get("/menus/accessible").json()
        console = _find_item(body["data"]["sections"], "system-console-ops")
        assert console is not None
        assert [tab["key"] for tab in console["tabs"]] == ["cache"]
        # console 可见 → 其 key 进入 flat_keys（契约 §2：含 group/console 本身）
        flat = set(body["data"]["flat_keys"])
        assert "cache" in flat
        assert "system-console-ops" in flat

    def test_console_hidden_when_no_tab_allowed(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer", allowed_menus='["dashboard"]'))
        body = client.get("/menus/accessible").json()
        assert _find_item(body["data"]["sections"], "system-console-ops") is None

    def test_legacy_allowed_key_enters_flat_keys_but_not_sections(self, menus_app, client):
        _set_user(menus_app, _make_user(
            role="viewer", allowed_menus='["dashboard", "system", "data-analysis"]',
        ))
        body = client.get("/menus/accessible").json()
        flat = body["data"]["flat_keys"]
        assert "system" in flat
        assert "data-analysis" in flat
        assert "system" not in _sections_keys(body["data"]["sections"])


def _find_item(sections: list[dict], key: str):
    for section in sections:
        for item in section["items"]:
            if item["key"] == key:
                return item
    return None


# =====================================================================
#  /menus/all
# =====================================================================
class TestAllMenus:
    def test_admin_gets_full_v2_structure(self, menus_app, client):
        from app.api.v1.menus import (
            MENU_SECTIONS,
            _iter_definition_keys,
            _section_entries,
        )

        resp = client.get("/menus/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["version"] == 2
        assert data["flat_keys"] == _iter_definition_keys()
        keys = _sections_keys(data["sections"])
        assert keys == set(_iter_definition_keys()) - {"dashboard"} - _legacy_keys()
        # 完整 roles：admin console 带 roles 下发，tabs 完整
        console = _find_item(data["sections"], "system-console-org")
        assert console["roles"] == ["admin", "super_admin"]
        assert len(console["tabs"]) == 7
        # 不做用户级过滤：非管理员专属条目也在
        assert "users-orgs" in keys
        # /all 的 sections 覆盖所有 section 归属的顶层条目（dashboard/legacy 不在 sections）
        expected_top = sum(len(_section_entries(section["key"])) for section in MENU_SECTIONS)
        assert sum(len(section["items"]) for section in data["sections"]) == expected_top

    def test_non_admin_forbidden(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer"))
        resp = client.get("/menus/all")
        assert resp.status_code == 403
        assert "管理员权限" in resp.json()["detail"]

    def test_manager_role_forbidden(self, menus_app, client):
        # 历史管理角色 manager 不归一化为系统管理员（core/permission_utils.is_admin 语义）
        _set_user(menus_app, _make_user(role="manager"))
        assert client.get("/menus/all").status_code == 403

    def test_super_admin_allowed(self, menus_app, client, super_admin_user):
        _set_user(menus_app, super_admin_user)
        assert client.get("/menus/all").status_code == 200


# =====================================================================
#  /menus/user-menus/{user_id}
# =====================================================================
class TestUserMenuConfig:
    def test_get_custom_config(self, menus_app, client, mock_db):
        target = _make_user(user_id=10, username="target", role="viewer",
                            allowed_menus='["dashboard", "villages"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.get("/menus/user-menus/10")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["mode"] == "custom"
        assert data["is_customized"] is True
        assert data["menu_keys"] == ["dashboard", "villages"]
        assert "system-console-org" in data["all_valid_keys"]

    def test_get_role_default_config(self, menus_app, client, mock_db):
        target = _make_user(user_id=11, username="target", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.get("/menus/user-menus/11")
        data = resp.json()["data"]
        assert data["mode"] == "role_default"
        assert data["is_customized"] is False
        assert set(data["menu_keys"]) == set(data["role_default_keys"])

    def test_get_forbidden_for_non_admin(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer"))
        assert client.get("/menus/user-menus/10").status_code == 403

    def test_get_not_found(self, menus_app, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/menus/user-menus/999")
        assert resp.status_code == 404
        assert "用户不存在" in resp.json()["detail"]


# =====================================================================
#  PUT /menus/user-menus/{user_id}
# =====================================================================
class TestSetUserMenuConfig:
    def test_restore_role_default(self, menus_app, client, mock_db):
        target = _make_user(user_id=20, username="tgt", role="viewer",
                            allowed_menus='["dashboard"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.put("/menus/user-menus/20", json={"menu_keys": None})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "role_default"
        assert target.allowed_menus is None
        mock_db.commit.assert_called()

    def test_clear_all_menus(self, menus_app, client, mock_db):
        target = _make_user(user_id=21, username="tgt", role="viewer",
                            allowed_menus='["dashboard"]')
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.put("/menus/user-menus/21", json={"menu_keys": []})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "custom"
        assert target.allowed_menus == "[]"

    def test_set_custom_menu_keys(self, menus_app, client, mock_db):
        target = _make_user(user_id=22, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.put(
            "/menus/user-menus/22",
            json={"menu_keys": ["dashboard", "villages", "system"]},  # system 为历史兼容 key
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "custom"
        assert json.loads(target.allowed_menus) == ["dashboard", "villages", "system"]

    def test_invalid_menu_key_rejected(self, menus_app, client, mock_db):
        target = _make_user(user_id=23, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.put(
            "/menus/user-menus/23",
            json={"menu_keys": ["dashboard", "nonexistent_key_xyz"]},
        )
        assert resp.status_code == 400
        assert "nonexistent_key_xyz" in resp.json()["detail"]
        mock_db.commit.assert_not_called()

    def test_cannot_modify_self(self, menus_app, client, mock_db):
        target = _make_user(user_id=1, username="admin", role="admin")
        mock_db.query.return_value.filter.return_value.first.return_value = target
        resp = client.put("/menus/user-menus/1", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 400
        assert "不能修改自己的菜单权限" in resp.json()["detail"]

    def test_not_found(self, menus_app, client, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert client.put("/menus/user-menus/999", json={"menu_keys": []}).status_code == 404

    def test_work_log_failure_does_not_block(self, menus_app, client, mock_db, monkeypatch):
        import app.api.v1.menus as menus_module

        target = _make_user(user_id=24, username="tgt", role="viewer")
        mock_db.query.return_value.filter.return_value.first.return_value = target

        def boom(*args, **kwargs):
            raise RuntimeError("log boom")

        monkeypatch.setattr(menus_module, "write_work_log", boom)
        resp = client.put("/menus/user-menus/24", json={"menu_keys": ["dashboard"]})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "custom"

    def test_forbidden_for_non_admin(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer"))
        assert client.put("/menus/user-menus/10", json={"menu_keys": []}).status_code == 403


# =====================================================================
#  /menus/role-defaults
# =====================================================================
class TestRoleDefaults:
    def test_admin_gets_role_defaults(self, menus_app, client):
        resp = client.get("/menus/role-defaults")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert set(data) == {"super_admin", "admin", "user", "viewer"}
        assert "dashboard" in data["viewer"]
        assert "system-console-org" in data["admin"]
        assert "system-console-org" not in data["viewer"]
        # admin 默认应覆盖全部 key（roles=None 或含 admin）
        from app.api.v1.menus import _iter_definition_keys
        assert set(data["admin"]) <= set(_iter_definition_keys())

    def test_forbidden_for_non_admin(self, menus_app, client):
        _set_user(menus_app, _make_user(role="viewer"))
        assert client.get("/menus/role-defaults").status_code == 403


# =====================================================================
#  纯函数 / 分支覆盖
# =====================================================================
class TestHelpers:
    def test_get_user_bound_pack_rejects_invalid_ids(self):
        from app.api.v1.menus import _get_user_bound_pack

        db = MagicMock()
        for invalid in (None, "7", True, 0, -1, MagicMock()):
            user = MagicMock()
            user.permission_pack_id = invalid
            assert _get_user_bound_pack(user, db) is None
        # 合法 int：db 无包 → None；有包 → 包对象
        user = MagicMock()
        user.permission_pack_id = 7
        db.query.return_value.filter.return_value.first.return_value = None
        assert _get_user_bound_pack(user, db) is None
        pack = _make_pack()
        db.query.return_value.filter.return_value.first.return_value = pack
        assert _get_user_bound_pack(user, db) is pack

    def test_flatten_menu_keys_with_children_and_tabs(self):
        from app.api.v1.menus import _flatten_menu_keys

        tree = [
            {"key": "a"},
            {"key": "b", "children": [{"key": "b1"}]},
            {"key": "c", "tabs": [{"key": "c1"}, {"key": "c2"}]},
        ]
        assert _flatten_menu_keys(tree) == {"a", "b", "b1", "c", "c1", "c2"}

    def test_filter_entry_branches(self):
        from app.api.v1.menus import _filter_entry

        page = {"key": "p", "label": "P", "path": "/p", "kind": "page", "roles": None, "order": 1}
        assert _filter_entry(page, {"p"})["path"] == "/p"
        assert _filter_entry(page, set()) is None

        group = {
            "key": "g", "label": "G", "kind": "group", "roles": None, "order": 1,
            "children": [{"key": "g1", "label": "G1", "path": "/g1", "kind": "page", "roles": None}],
        }
        assert _filter_entry(group, {"g1"})["children"][0]["key"] == "g1"
        assert _filter_entry(group, {"g"}) is None

        console = {
            "key": "x", "label": "X", "path": "/x", "kind": "console", "roles": None, "order": 1,
            "tabs": [{"key": "t1", "label": "T1", "path": "/t1", "roles": None}],
        }
        assert len(_filter_entry(console, {"x"})["tabs"]) == 1
        assert _filter_entry(console, {"t1"})["tabs"][0]["key"] == "t1"
        assert _filter_entry(console, set()) is None

    def test_build_sections_no_visible_items(self):
        from app.api.v1.menus import _build_sections

        assert _build_sections(set()) == []
        assert len(_build_sections()) == len(CONTRACT_SECTIONS)

    def test_build_flat_keys_branches(self):
        from app.api.v1.menus import _build_flat_keys, _build_sections, _iter_definition_keys

        # allowed None -> 全量定义顺序
        assert _build_flat_keys(_build_sections()) == _iter_definition_keys()
        # dashboard 不在 allowed -> 不出现；可见条目 key 在 allowed -> 进入 flat_keys
        flat = _build_flat_keys([], {"villages"})
        assert "dashboard" not in flat
        sections = [{"key": "business", "items": [{"key": "villages"}]}]
        assert _build_flat_keys(sections, {"villages"}) == ["villages"]
        # 历史兼容 key 且 allowed -> 进入 flat_keys（按定义顺序）
        flat = _build_flat_keys([], {"system", "data-analysis"})
        assert flat == ["data-analysis", "system"]

    def test_role_default_normalization(self):
        from app.api.v1.menus import _get_role_default_menu_keys

        assert _get_role_default_menu_keys("operator") == _get_role_default_menu_keys("user")
        assert _get_role_default_menu_keys("manager") == _get_role_default_menu_keys("admin")
        assert _get_role_default_menu_keys("approval_leader") == _get_role_default_menu_keys("admin")
        assert isinstance(_get_role_default_menu_keys("viewer"), frozenset)
        # lru_cache：同一 role 返回同一对象
        assert _get_role_default_menu_keys("operator") is _get_role_default_menu_keys("operator")

    def test_user_accessible_keys_priorities(self):
        from app.api.v1.menus import (
            _PUBLIC_ACCESS_KEYS,
            _get_user_accessible_menu_keys,
            _iter_definition_keys,
        )

        db = MagicMock()
        # superuser 全量
        superuser = _make_user(role="admin", is_superuser=True, allowed_menus='["dashboard"]')
        assert _get_user_accessible_menu_keys(superuser, db) == set(_iter_definition_keys())
        # allowed_menus 优先
        custom = _make_user(role="admin", allowed_menus='["dashboard"]')
        assert _get_user_accessible_menu_keys(custom, db) == {"dashboard"} | _PUBLIC_ACCESS_KEYS
        # 权限包
        pack_user = _make_user(role="user")
        pack_user.permission_pack_id = 3
        db.query.return_value.filter.return_value.first.return_value = _make_pack(
            ("dashboard", "schools")
        )
        assert _get_user_accessible_menu_keys(pack_user, db) == {
            "dashboard", "schools"
        } | _PUBLIC_ACCESS_KEYS
        # 角色默认
        role_user = _make_user(role="viewer")
        keys = _get_user_accessible_menu_keys(role_user, db)
        assert "dashboard" in keys
        assert "system-console-org" not in keys

    def test_serialize_entry_kinds(self):
        from app.api.v1.menus import MENU_DEFINITIONS, _serialize_entry

        by_kind = {}
        for entry in MENU_DEFINITIONS:
            by_kind.setdefault(entry.get("kind"), entry)
        page = _serialize_entry(by_kind["page"])
        assert "path" in page and "children" not in page and "tabs" not in page
        group = _serialize_entry(by_kind["group"])
        assert "path" not in group and group["children"]
        console = _serialize_entry(by_kind["console"])
        assert console["path"] and console["tabs"] and "children" not in console
