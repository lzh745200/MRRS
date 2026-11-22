# -*- coding: utf-8 -*-
"""动作权限目录单测（覆盖 app/core/permission_catalog.py 的全部分支）。

覆盖点：
- 菜单扁平化（children / tabs / 非 dict 脏数据）；
- 页面级与模块级动作构建（写模块命中与否、附加动作）；
- 单数前缀别名（已知单数、不规则复数、目标不存在时不建）；
- normalize / is_known / expand（含 legacy 粗粒度、`*` 通配、未识别码保留）；
- 单例缓存与重置。
"""

from __future__ import annotations

import dataclasses

import pytest

from app.core import permission_catalog as pc


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    """每个用例前后都清缓存，避免单例污染。"""
    pc.reset_catalog_cache()
    yield
    pc.reset_catalog_cache()


# ── 菜单扁平化 ──────────────────────────────────────────────


def test_iter_entries_flattens_children_and_tabs():
    defs = [
        {"key": "a", "kind": "page", "children": [{"key": "a1", "kind": "page"}]},
        {"key": "b", "kind": "group", "tabs": [{"key": "b-tab"}]},
    ]
    keys = [e.get("key") for e in pc._iter_entries(defs)]
    assert keys == ["a", "a1", "b", "b-tab"]


def test_iter_entries_ignores_non_dict_items():
    defs = [None, "x", {"key": "a", "kind": "page", "children": [None, 3]}]  # type: ignore[list-item]
    keys = [e.get("key") for e in pc._iter_entries(defs)]  # type: ignore[arg-type]
    assert keys == ["a"]


def test_iter_entries_skips_non_dict_tabs():
    defs = [{"key": "a", "kind": "page", "tabs": ["oops", {"key": "a-tab"}]}]
    keys = [e.get("key") for e in pc._iter_entries(defs)]
    assert keys == ["a", "a-tab"]


# ── 目录构建 ────────────────────────────────────────────────


def test_build_page_actions_adds_write_for_write_modules():
    out = pc._build_page_actions(["villages", "dashboard"], {"villages"})
    assert out["villages"] == ("read", "write", "delete")
    assert out["dashboard"] == ("read",)


def test_build_module_actions_excludes_pages_and_adds_extra():
    out = pc._build_module_actions({"villages", "users-orgs", "roles"}, {"villages"})
    assert "villages" not in out
    assert out["users-orgs"] == ("read", "write", "delete", "manage_roles")
    assert out["roles"] == ("read", "write", "delete", "manage_roles")


def test_build_module_actions_without_extra_actions():
    out = pc._build_module_actions({"audit"}, set())
    assert out["audit"] == ("read", "write", "delete")


def test_build_prefix_alias_handles_irregular_and_missing_targets():
    alias = pc._build_prefix_alias(["villages", "policies", "funds-admin", "system"])
    assert alias["village"] == "villages"
    assert alias["policy"] == "policies"
    # fund 的复数 funds 不是页面（资金页是 funds-admin）→ 不建别名
    assert "fund" not in alias
    # system 本身是页面，且 systems 不存在 → 不建
    assert "system" not in alias


def test_build_prefix_alias_skips_when_singular_is_also_a_page():
    alias = pc._build_prefix_alias(["policy", "policies"])
    assert alias == {}


# ── normalize / is_known ────────────────────────────────────


def test_normalize_maps_singular_prefix():
    catalog = pc.get_catalog()
    assert catalog.normalize("village:read") == "villages:read"


def test_normalize_keeps_unknown_or_prefixless_codes():
    catalog = pc.get_catalog()
    assert catalog.normalize("nonsense:read") == "nonsense:read"
    assert catalog.normalize("read") == "read"


def test_is_known_accepts_legacy_and_normalized_codes():
    catalog = pc.get_catalog()
    assert catalog.is_known("villages:read")
    assert catalog.is_known("village:read")  # 单数前缀
    assert catalog.is_known("data:create")  # legacy 粗粒度


def test_is_known_rejects_unknown_and_wildcard():
    catalog = pc.get_catalog()
    assert not catalog.is_known("nonsense:read")
    assert not catalog.is_known("*:read")


# ── expand ──────────────────────────────────────────────────


def test_expand_normalizes_plain_code():
    catalog = pc.get_catalog()
    assert catalog.expand(["village:read"]) == {"villages:read"}


def test_expand_legacy_alias_to_concrete_codes():
    catalog = pc.get_catalog()
    assert catalog.expand(["village:manage"]) == {
        "villages:read",
        "villages:write",
        "villages:delete",
    }


def test_expand_wildcard_covers_all_codes_with_action():
    catalog = pc.get_catalog()
    expanded = catalog.expand(["data:create"])
    assert expanded
    assert all(code.endswith(":write") for code in expanded)
    assert "villages:write" in expanded


def test_expand_keeps_unknown_codes_for_debuggability():
    catalog = pc.get_catalog()
    assert catalog.expand(["ghost:read"]) == {"ghost:read"}


def test_expand_skips_empty_and_non_string_items():
    catalog = pc.get_catalog()
    assert catalog.expand(["", None, 1]) == set()  # type: ignore[list-item]


def test_expand_target_wildcard_and_plain():
    catalog = pc.get_catalog()
    assert catalog._expand_target("*:read") == {
        code for code in catalog.all_codes if code.endswith(":read")
    }
    assert catalog._expand_target("villages:read") == {"villages:read"}


# ── 只读视图与缓存 ──────────────────────────────────────────


def test_page_keys_and_actions_of_page():
    catalog = pc.get_catalog()
    assert "villages" in catalog.page_keys()
    assert "read" in catalog.actions_of_page("villages")
    assert catalog.actions_of_page("not-a-page") == ()


def test_get_catalog_is_cached_until_reset():
    first = pc.get_catalog()
    assert pc.get_catalog() is first
    pc.reset_catalog_cache()
    assert pc.get_catalog() is not first


def test_catalog_is_immutable():
    catalog = pc.get_catalog()
    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog.all_codes = frozenset()  # type: ignore[misc]
