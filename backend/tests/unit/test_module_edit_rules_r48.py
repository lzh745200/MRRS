# -*- coding: utf-8 -*-
"""R48 阶段 4：写闸门收敛（module_edit_rules + grant_guard ↔ org_module_policies）。

覆盖：
- 共享规则 ``core/module_edit_rules.py`` 的模式归一化/禁用判定/标签；
- 中间件 ``evaluate_org_policy`` 的单一查询路径（含 fail-open 分支）；
- ``grant_guard`` 在矩阵 active 时尊重组织模块开关（更严者生效，enforce 403）。
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import grant_guard as gg
from app.core import module_edit_rules as rules
from app.middleware import org_module_policy_gate as gate
from app.services.effective_grant_service import GrantMatrix


class TestRules:
    @pytest.mark.parametrize("raw,expected", [
        ("off", "off"),
        ("SHADOW", "shadow"),
        (" enforce ", "enforce"),
    ])
    def test_normalize_valid(self, raw, expected):
        assert rules.normalize_mode(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "bogus", "enabled"])
    def test_normalize_invalid_defaults_to_shadow(self, raw):
        assert rules.normalize_mode(raw) == rules.MODE_SHADOW

    def test_normalize_custom_default(self):
        assert rules.normalize_mode(None, default=rules.MODE_OFF) == rules.MODE_OFF

    @pytest.mark.parametrize("edit_mode,blocked", [
        ("read_only", True), ("disabled", True),
        ("full_edit", False), (None, False), ("bogus", False),
    ])
    def test_is_blocked_edit_mode(self, edit_mode, blocked):
        assert rules.is_blocked_edit_mode(edit_mode) is blocked

    def test_edit_mode_label(self):
        assert rules.edit_mode_label("read_only") == "只读"
        assert rules.edit_mode_label("disabled") == "禁用"
        assert rules.edit_mode_label("custom") == "custom"
        assert rules.edit_mode_label(None) == ""


class TestGateEvaluateOrgPolicy:
    def test_no_user(self, monkeypatch):
        monkeypatch.setattr(gate, "load_policy_edit_mode_cached", lambda *a: "disabled")
        assert gate.evaluate_org_policy(object(), None, "projects") is None

    def test_no_org(self, monkeypatch):
        called = []
        monkeypatch.setattr(gate, "load_policy_edit_mode_cached", lambda *a: called.append(a))
        assert gate.evaluate_org_policy(object(), SimpleNamespace(organization_id=None), "projects") is None
        assert called == []

    def test_blocked(self, monkeypatch):
        monkeypatch.setattr(gate, "load_policy_edit_mode_cached", lambda *a: "read_only")
        user = SimpleNamespace(organization_id=7)
        assert gate.evaluate_org_policy(object(), user, "projects") == "read_only"

    @pytest.mark.parametrize("mode", ["full_edit", None, "bogus"])
    def test_allowed(self, monkeypatch, mode):
        monkeypatch.setattr(gate, "load_policy_edit_mode_cached", lambda *a: mode)
        user = SimpleNamespace(organization_id=7)
        assert gate.evaluate_org_policy(object(), user, "projects") is None


def _request(path="/api/v1/projects", method="POST"):
    return SimpleNamespace(method=method, url=SimpleNamespace(path=path))


def _db():
    return SimpleNamespace(close=lambda: None)


def _user(org_id=7):
    return SimpleNamespace(id=9, organization_id=org_id)


class TestGuardHonoursOrgPolicy:
    """矩阵 active 时，grant_guard 与 org_module_policies 更严者生效。"""

    @pytest.fixture(autouse=True)
    def _session(self, monkeypatch):
        monkeypatch.setattr("app.core.database.SessionLocal", lambda: _db())

    @pytest.mark.asyncio
    async def test_enforce_policy_blocks_edit(self, monkeypatch):
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: _user())
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "edit"}),
        )
        monkeypatch.setattr(
            "app.middleware.org_module_policy_gate.evaluate_org_policy",
            lambda _db, _u, _m: "disabled",
        )
        with pytest.raises(HTTPException) as exc:
            await gg.enforce_write_grant(_request())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_shadow_policy_does_not_raise(self, monkeypatch, caplog):
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_SHADOW)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: _user())
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "edit"}),
        )
        monkeypatch.setattr(
            "app.middleware.org_module_policy_gate.evaluate_org_policy",
            lambda _db, _u, _m: "read_only",
        )
        caplog.set_level("WARNING", logger="app.core.grant_guard")
        await gg.enforce_write_grant(_request())
        assert "org_policy:read_only" in caplog.text

    @pytest.mark.asyncio
    async def test_matrix_view_still_wins_before_policy(self, monkeypatch):
        calls = []
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: _user())
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "view"}),
        )
        monkeypatch.setattr(
            "app.middleware.org_module_policy_gate.evaluate_org_policy",
            lambda *a: calls.append(a) or "disabled",
        )
        with pytest.raises(HTTPException):
            await gg.enforce_write_grant(_request())
        assert calls == []

    @pytest.mark.asyncio
    async def test_policy_allowed_passes(self, monkeypatch):
        calls = []
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: _user())
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=True, levels={"projects": "edit"}),
        )
        monkeypatch.setattr(
            "app.middleware.org_module_policy_gate.evaluate_org_policy",
            lambda _db, _u, _m: calls.append(_m) or None,
        )
        await gg.enforce_write_grant(_request())
        assert calls == ["projects"]

    @pytest.mark.asyncio
    async def test_inactive_matrix_skips_policy(self, monkeypatch):
        calls = []
        monkeypatch.setattr(gg, "current_mode", lambda: gg.MODE_ENFORCE)
        monkeypatch.setattr(gg, "resolve_user", lambda _r, _d: _user())
        monkeypatch.setattr(
            "app.services.effective_grant_service.get_grant_matrix",
            lambda _db, _u: GrantMatrix(active=False),
        )
        monkeypatch.setattr(
            "app.middleware.org_module_policy_gate.evaluate_org_policy",
            lambda *a: calls.append(a) or "disabled",
        )
        await gg.enforce_write_grant(_request())
        assert calls == []
