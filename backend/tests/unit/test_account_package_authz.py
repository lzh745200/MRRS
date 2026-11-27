"""账号包授权目录与矩阵推导回归（P-AP）。"""

from __future__ import annotations

import pytest

from app.core.account_package_authz import (
    AccountPackageAuthorizationError,
    _allowed_menu_keys_for_grants,
    authorization_summary,
    clear_authorization_catalog_cache,
    derive_grants,
    get_authorization_catalog,
    menu_keys_for_pages,
    validate_manifest_grants,
    validate_menu_selection,
)


@pytest.fixture(autouse=True)
def _fresh_catalog():
    clear_authorization_catalog_cache()
    yield
    clear_authorization_catalog_cache()


def _codes(err: pytest.ExceptionInfo[AccountPackageAuthorizationError]) -> str:
    return err.value.code


def test_catalog_shape_and_modules_are_known() -> None:
    catalog = get_authorization_catalog()
    assert len(catalog["sections"]) == 7
    assert len(catalog["pages"]) == 54
    assert len(catalog["modules"]) == 32
    assert len(catalog["catalog_version"]) == 64

    pages = {page["key"]: page for page in catalog["pages"]}
    assert "dashboard" in pages
    assert pages["dashboard"]["modules"] == []
    assert pages["dashboard"]["can_edit"] is False
    assert "system-console-org" in pages
    assert "users-orgs" in pages["system-console-org"]["modules"]
    assert any(tab["key"] == "users-orgs" for tab in pages["system-console-org"]["tabs"])

    # 授权目录中的页面必须都有真实路由；历史 key 不进入勾选树。
    assert all(page["key"] for page in catalog["pages"])
    assert "households" not in pages


def test_catalog_is_cached_and_can_be_cleared() -> None:
    first = get_authorization_catalog()
    second = get_authorization_catalog()
    assert first["catalog_version"] == second["catalog_version"]
    assert first["sections"] is second["sections"]
    clear_authorization_catalog_cache()
    third = get_authorization_catalog()
    assert third["catalog_version"] == first["catalog_version"]


def test_derive_page_view_and_edit_expands_modules() -> None:
    assert derive_grants({"villages": "view"}) == {"villages": "view"}
    assert derive_grants({"projects": "edit"}) == {"projects": "edit"}
    console = derive_grants({"system-console-org": "edit"})
    assert console["system-console-org"] == "edit"
    assert console["users-orgs"] == "edit"
    assert console["organizations"] == "edit"


def test_derive_mixed_module_cannot_downgrade_page_edit() -> None:
    # 顺序无关：页面 edit 推导出的模块 edit 必须胜出。
    result = derive_grants({"system-console-org": "edit", "users-orgs": "view"})
    assert result["users-orgs"] == "edit"


def test_derive_rejects_invalid_shapes_levels_and_keys() -> None:
    with pytest.raises(AccountPackageAuthorizationError) as exc:
        derive_grants({"unknown-page": "view"})
    assert _codes(exc) == "AP_GRANT_INVALID"

    with pytest.raises(AccountPackageAuthorizationError) as exc:
        derive_grants({"villages": "write"})
    assert _codes(exc) == "AP_GRANT_INVALID"

    with pytest.raises(AccountPackageAuthorizationError) as exc:
        derive_grants(["villages"])  # type: ignore[arg-type]
    assert _codes(exc) == "AP_GRANT_SHAPE"

    with pytest.raises(AccountPackageAuthorizationError) as exc:
        derive_grants({"dashboard": "edit"})
    assert _codes(exc) == "AP_GRANT_INVALID"


def test_derive_accepts_module_keys_and_empty_selection() -> None:
    assert derive_grants({"users-orgs": "view"}) == {"users-orgs": "view"}
    assert derive_grants({}) == {}
    assert derive_grants(None) == {}  # type: ignore[arg-type]
    assert validate_manifest_grants(None) == {}


def test_authorization_summary_counts_pages_and_modules() -> None:
    summary = authorization_summary({"projects": "edit", "villages": "view"})
    assert summary["page_count"] == 2
    assert summary["edit_page_count"] == 1
    assert summary["view_page_count"] == 1
    assert summary["module_count"] == 2
    assert len(summary["digest"]) == 64


def test_menu_selection_must_be_subset_of_granted_pages() -> None:
    grants = derive_grants({"projects": "view"})
    assert validate_menu_selection(["projects"], grants) == ["projects"]
    assert validate_menu_selection([], grants) is None
    assert validate_menu_selection(None, grants) is None

    with pytest.raises(AccountPackageAuthorizationError) as exc:
        validate_menu_selection(["villages"], grants)
    assert _codes(exc) == "AP_MENU_NOT_ALLOWED"

    with pytest.raises(AccountPackageAuthorizationError) as exc:
        validate_menu_selection(["not-a-menu"], grants)
    assert _codes(exc) == "AP_MENU_NOT_ALLOWED"


def test_menu_keys_for_console_pages_include_tabs() -> None:
    keys = menu_keys_for_pages(["system-console-org"])
    assert "system-console-org" in keys
    assert "users-orgs" in keys
    assert menu_keys_for_pages(["unknown"]) == frozenset()


def test_catalog_skips_invalid_sections_entries_and_empty_sections(monkeypatch) -> None:
    from app.api.v1 import menus as menus_module

    monkeypatch.setattr(
        menus_module,
        "MENU_SECTIONS",
        [
            {"key": "", "label": "空 key", "order": 0},
            {"key": "dashboard", "label": "工作台", "order": 1},
            {"key": "empty-section", "label": "空分组", "order": 2},
        ],
    )
    monkeypatch.setattr(
        menus_module,
        "MENU_DEFINITIONS",
        [
            {"key": "bad-kind", "path": "/bad", "kind": "weird", "section": "dashboard"},
            {"key": "unknown-section", "path": "/x", "section": "no-such-section"},
            {
                "key": "group-without-valid-child",
                "label": "空组",
                "kind": "group",
                "section": "dashboard",
                "children": [{"key": "", "path": ""}],
            },
        ],
    )
    clear_authorization_catalog_cache()
    catalog = get_authorization_catalog()
    # 空 section key 被跳过；dashboard 已在 MENU_SECTIONS 中时不重复插入；
    # 空分组没有有效子项时整段不出现。
    assert catalog["sections"] == []
    assert catalog["pages"] == []


def test_catalog_tolerates_permission_catalog_failure(monkeypatch) -> None:
    from app.core import permission_catalog as permission_catalog_module

    def _boom():
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(permission_catalog_module, "get_catalog", _boom)
    clear_authorization_catalog_cache()
    catalog = get_authorization_catalog()
    assert catalog["modules"] == []
    assert all(page["modules"] == [] for page in catalog["pages"])


def test_derive_rejects_non_string_level_and_key(monkeypatch) -> None:
    with pytest.raises(AccountPackageAuthorizationError) as exc:
        derive_grants({"villages": 1})  # type: ignore[dict-item]
    assert _codes(exc) == "AP_GRANT_INVALID"

    with pytest.raises(AccountPackageAuthorizationError) as exc:
        derive_grants({1: "view"})  # type: ignore[dict-item]
    assert _codes(exc) == "AP_GRANT_INVALID"

    assert derive_grants({"   ": "view"}) == {}


def test_manifest_grants_must_be_mapping() -> None:
    with pytest.raises(AccountPackageAuthorizationError) as exc:
        validate_manifest_grants(["villages"])  # type: ignore[arg-type]
    assert _codes(exc) == "AP_GRANT_SHAPE"

    assert validate_manifest_grants({"villages": "view"}) == {"villages": "view"}


def test_known_menu_walk_skips_empty_keys(monkeypatch) -> None:
    from app.api.v1 import menus as menus_module

    monkeypatch.setattr(
        menus_module,
        "MENU_DEFINITIONS",
        [{"key": "", "children": [{"key": "child-page"}]}],
    )
    assert validate_menu_selection(["child-page"], {}) == ["child-page"]


def test_allowed_menu_keys_handles_module_only_grants() -> None:
    allowed = _allowed_menu_keys_for_grants({"funds": "view"})
    assert "funds" in allowed


def test_menu_selection_rejects_non_list_and_allows_empty_grants() -> None:
    with pytest.raises(AccountPackageAuthorizationError) as exc:
        validate_menu_selection("dashboard", {})  # type: ignore[arg-type]
    assert _codes(exc) == "AP_GRANT_SHAPE"

    assert validate_menu_selection(["dashboard"], {}) == ["dashboard"]

