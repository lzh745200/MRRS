# -*- coding: utf-8 -*-
"""有效权限裁决点测试（§2.5 / §4.1）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import effective_permission_service as svc


def _user(**kw):
    org = SimpleNamespace(grant_version=kw.pop("grant_version", 3))
    base = dict(
        id=7,
        permissions_version=2,
        organization_id=1,
        organization=org,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _matrix(active: bool, levels=None):
    return SimpleNamespace(active=active, levels=levels or {})


@pytest.fixture(autouse=True)
def _clear():
    svc.clear_cache()
    yield
    svc.clear_cache()


def _patch_sources(monkeypatch, *, permissions, pages, matrix, restricted=None):
    async def fake_permissions(self, user_id, db):
        return set(permissions), set(restricted or ())

    monkeypatch.setattr(
        "app.services.rbac_service.RBACService.get_user_permissions_with_restrictions",
        fake_permissions,
    )
    monkeypatch.setattr(
        "app.services.effective_grant_service.get_grant_matrix",
        lambda db, user: matrix,
    )
    monkeypatch.setattr(
        "app.api.v1.menus._get_user_accessible_menu_keys",
        lambda user, db, matrix=None: set(pages),
    )


@pytest.mark.asyncio
async def test_resolve_legacy_expands_aliases_and_keeps_pages(monkeypatch):
    _patch_sources(
        monkeypatch,
        permissions=["data:create"],
        pages=["villages", "dashboard"],
        matrix=_matrix(False),
        restricted=["x:read"],
    )
    result = await svc.resolve(None, _user())

    assert result.pages == frozenset({"villages", "dashboard"})
    assert result.modules == {}
    assert "villages:write" in result.actions
    assert "projects:write" in result.actions
    assert "roles:write" not in result.actions
    assert result.denied == frozenset({"x:read"})
    assert result.version == "2.3"
    assert result.has("data:create")
    assert result.has("villages:write")
    assert not result.has("roles:write")


@pytest.mark.asyncio
async def test_resolve_active_matrix_filters_write_and_keeps_readonly_pages(monkeypatch):
    _patch_sources(
        monkeypatch,
        permissions=[
            "villages:read", "villages:write", "projects:write",
            "dashboard:read", "users-orgs:manage_roles",
        ],
        pages=["villages", "projects", "dashboard"],
        matrix=_matrix(True, {"villages": "view", "projects": "edit", "users-orgs": "edit"}),
    )
    result = await svc.resolve(None, _user())

    assert "villages:read" in result.actions
    assert "villages:write" not in result.actions       # 模块只读 → 写被收窄
    assert "projects:write" in result.actions           # 模块 edit → 保留
    assert "dashboard:read" in result.actions           # 只读页无模块，不被误删
    assert "users-orgs:manage_roles" in result.actions
    assert result.can_view_page("dashboard")
    assert not result.can_edit_page("villages")
    assert result.can_edit_page("projects")


@pytest.mark.asyncio
async def test_resolve_active_matrix_can_edit_console_page(monkeypatch):
    _patch_sources(
        monkeypatch,
        permissions=["system-console-org:read", "system-console-org:write"],
        pages=["system-console-org"],
        matrix=_matrix(True, {"users-orgs": "edit"}),
    )
    result = await svc.resolve(None, _user())

    assert "system-console-org:write" in result.actions
    assert result.can_edit_page("system-console-org")


@pytest.mark.asyncio
async def test_resolve_cache_hits_until_version_changes(monkeypatch):
    calls = {"n": 0}

    async def fake_permissions(self, user_id, db):
        calls["n"] += 1
        return {"villages:read"}, set()

    monkeypatch.setattr(
        "app.services.rbac_service.RBACService.get_user_permissions_with_restrictions",
        fake_permissions,
    )
    monkeypatch.setattr(
        "app.services.effective_grant_service.get_grant_matrix",
        lambda db, user: _matrix(False),
    )
    monkeypatch.setattr(
        "app.api.v1.menus._get_user_accessible_menu_keys",
        lambda u, d, matrix=None: {"villages"},
    )

    user = _user()
    first = await svc.resolve(None, user)
    second = await svc.resolve(None, user)
    assert first is second
    assert calls["n"] == 1
    assert svc.get_cached(None, user) is first

    user.permissions_version = 3
    third = await svc.resolve(None, user)
    assert third is not first
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_filter_edge_branches_and_no_module_page(monkeypatch):
    _patch_sources(
        monkeypatch,
        permissions=["bigscreen:read", "bigscreen:write", "audit:read", "bad", ""],
        pages=["bigscreen"],
        matrix=_matrix(True, {"villages": "view"}),
    )
    result = await svc.resolve(None, _user())
    assert "bigscreen:read" in result.actions       # 无映射页保留 read
    assert "bigscreen:write" not in result.actions  # 无映射页不允许写
    assert "audit:read" not in result.actions       # 模块级 read 无 view → 收窄
    assert not result.can_edit_page("bigscreen")    # 无模块映射 → 不可写


@pytest.mark.asyncio
async def test_cache_limit_clears(monkeypatch):
    _patch_sources(
        monkeypatch,
        permissions=["villages:read"],
        pages=["villages"],
        matrix=_matrix(False),
    )
    monkeypatch.setattr(svc, "_CACHE_LIMIT", 1)
    await svc.resolve(None, _user(id=1))
    await svc.resolve(None, _user(id=2))
    assert len(svc._CACHE) == 1


@pytest.mark.asyncio
async def test_resolve_active_empty_matrix_fails_closed(monkeypatch):
    """active=True 但 levels 为空（授权被清空/账号包只激活版本）必须裁剪。

    历史缺陷：按 `if levels:` 判断是否裁剪，active-empty 会直接跳过过滤，
    把 RBAC 全量动作放行，而菜单侧此时几乎为空 —— 一旦接入路由即为越权。
    """
    _patch_sources(
        monkeypatch,
        permissions=[
            "villages:read", "villages:write", "dashboard:read",
            "users-orgs:manage_roles",
        ],
        pages=["dashboard"],
        matrix=_matrix(True, {}),
    )
    result = await svc.resolve(None, _user())

    assert result.actions == frozenset({"dashboard:read"})
    assert not result.has("villages:read")
    assert not result.has("villages:write")
    assert not result.has("users-orgs:manage_roles")


@pytest.mark.asyncio
async def test_resolve_does_not_cache_without_permissions_version(monkeypatch):
    """真实 User 还没有 permissions_version 列 → 不得缓存，避免权限变更后读旧快照。"""
    calls = {"n": 0}

    async def fake_permissions(self, user_id, db):
        calls["n"] += 1
        return {"villages:read"}, set()

    monkeypatch.setattr(
        "app.services.rbac_service.RBACService.get_user_permissions_with_restrictions",
        fake_permissions,
    )
    monkeypatch.setattr(
        "app.services.effective_grant_service.get_grant_matrix",
        lambda db, user: _matrix(False),
    )
    monkeypatch.setattr(
        "app.api.v1.menus._get_user_accessible_menu_keys",
        lambda u, d, matrix=None: {"villages"},
    )

    user = SimpleNamespace(
        id=9, organization_id=1, organization=SimpleNamespace(grant_version=0)
    )
    first = await svc.resolve(None, user)
    second = await svc.resolve(None, user)

    assert first is not second
    assert calls["n"] == 2
    assert svc._CACHE == {}
    assert svc.get_cached(None, user) is None


@pytest.mark.asyncio
async def test_cache_hit_skips_grant_matrix_query(monkeypatch):
    """缓存命中不应再查单位授权矩阵（原实现先查矩阵后查缓存）。"""
    matrix_calls = {"n": 0}

    async def fake_permissions(self, user_id, db):
        return {"villages:read"}, set()

    def fake_matrix(db, user):
        matrix_calls["n"] += 1
        return _matrix(False)

    monkeypatch.setattr(
        "app.services.rbac_service.RBACService.get_user_permissions_with_restrictions",
        fake_permissions,
    )
    monkeypatch.setattr(
        "app.services.effective_grant_service.get_grant_matrix", fake_matrix
    )
    monkeypatch.setattr(
        "app.api.v1.menus._get_user_accessible_menu_keys",
        lambda u, d, matrix=None: {"villages"},
    )

    user = _user()
    first = await svc.resolve(None, user)
    second = await svc.resolve(None, user)

    assert first is second
    assert matrix_calls["n"] == 1


@pytest.mark.asyncio
async def test_resolve_passes_resolved_matrix_to_menu_helper(monkeypatch):
    """菜单解析必须复用已解析的矩阵，避免一次请求查两次库。"""
    seen = {}
    sentinel = _matrix(False)

    async def fake_permissions(self, user_id, db):
        return {"villages:read"}, set()

    def fake_menu(user, db, matrix=None):
        seen["matrix"] = matrix
        return {"villages"}

    monkeypatch.setattr(
        "app.services.rbac_service.RBACService.get_user_permissions_with_restrictions",
        fake_permissions,
    )
    monkeypatch.setattr(
        "app.services.effective_grant_service.get_grant_matrix",
        lambda db, user: sentinel,
    )
    monkeypatch.setattr(
        "app.api.v1.menus._get_user_accessible_menu_keys", fake_menu
    )

    await svc.resolve(None, _user())
    assert seen["matrix"] is sentinel


@pytest.mark.asyncio
async def test_resolve_none_user_returns_empty(monkeypatch):
    result = await svc.resolve(None, None)
    assert not result.pages
    assert not result.actions
    assert result.version == "0.0"
    assert not result.has("villages:read")
