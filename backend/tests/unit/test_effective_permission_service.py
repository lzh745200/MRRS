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
        lambda user, db: set(pages),
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
    monkeypatch.setattr("app.api.v1.menus._get_user_accessible_menu_keys", lambda u, d: {"villages"})

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
async def test_resolve_none_user_returns_empty(monkeypatch):
    result = await svc.resolve(None, None)
    assert not result.pages
    assert not result.actions
    assert result.version == "0.0"
    assert not result.has("villages:read")
