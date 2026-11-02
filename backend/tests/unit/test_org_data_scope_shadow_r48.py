# -*- coding: utf-8 -*-
"""R48 组织级 data_scope 影子观测。

保证两件事：
1. 默认 off 时零行为变化（``get_data_scope`` 返回值与改造前一致）；
2. shadow 时只记录差异，绝不参与过滤。
"""

from types import SimpleNamespace

import pytest

from app.core import data_permission
from app.core import org_data_scope_shadow as shadow
from app.core.config import settings
from app.core.data_permission import DataScope, get_data_scope


def _user(level="3", data_scope=None, role="admin", org=True, org_id=7):
    org_obj = SimpleNamespace(id=7, level=level, data_scope=data_scope) if org else None
    return SimpleNamespace(
        id=9,
        role=role,
        is_superuser=False,
        organization_id=org_id,
        organization=org_obj,
    )


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    shadow._LOGGED.clear()
    monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "off")
    yield
    shadow._LOGGED.clear()


class TestMode:
    def test_default_off(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "")
        assert shadow.current_mode() == "off"

    def test_shadow(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "SHADOW")
        assert shadow.current_mode() == "shadow"

    def test_unknown_falls_back_off(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "enforce")
        assert shadow.current_mode() == "off"

    def test_none_falls_back_off(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", None)
        assert shadow.current_mode() == "off"


class TestDerivedScope:
    def test_none_org(self):
        assert shadow.derived_org_scope(None) is None

    @pytest.mark.parametrize("explicit", ["all", "subtree", "self"])
    def test_explicit_wins(self, explicit):
        org = SimpleNamespace(level="1", data_scope=explicit)
        assert shadow.derived_org_scope(org) == explicit

    @pytest.mark.parametrize("level,expected", [("1", "subtree"), ("2", "subtree"), ("3", "self")])
    def test_level_derivation(self, level, expected):
        assert shadow.derived_org_scope(SimpleNamespace(level=level)) == expected

    def test_invalid_explicit_falls_back_to_level(self):
        org = SimpleNamespace(level="3", data_scope="bogus")
        assert shadow.derived_org_scope(org) == "self"

    def test_unknown_level(self):
        assert shadow.derived_org_scope(SimpleNamespace(level="9", data_scope=None)) is None


class TestObserve:
    def test_off_returns_none(self):
        assert shadow.observe_org_data_scope(_user(), "own_dept") is None

    def test_shadow_without_org(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        assert shadow.observe_org_data_scope(_user(org=False), "own_dept") is None
        assert "影子观测失败" not in caplog.text

    def test_shadow_without_derivable_scope(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        assert shadow.observe_org_data_scope(_user(level="9"), "own_dept") is None

    def test_shadow_unknown_role_scope(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        assert shadow.observe_org_data_scope(_user(), "weird") is None

    def test_shadow_not_narrower(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        result = shadow.observe_org_data_scope(_user(level="2"), "own_dept")
        assert result == {
            "org_id": 7,
            "org_scope": "subtree",
            "role_scope": "own_dept",
            "would_narrow": False,
        }

    def test_shadow_narrower_warns_once(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        caplog.set_level("WARNING", logger="app.core.org_data_scope_shadow")
        user = _user(level="3")
        first = shadow.observe_org_data_scope(user, "own_dept")
        second = shadow.observe_org_data_scope(user, "own_dept")
        assert first["would_narrow"] is True
        assert second["would_narrow"] is True
        assert len(caplog.records) == 1
        assert "影子观测" in caplog.text

    def test_shadow_log_cache_overflow(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        caplog.set_level("WARNING", logger="app.core.org_data_scope_shadow")
        for i in range(shadow._MAX_LOGGED):
            shadow._LOGGED[(i, i, "own_dept", "self")] = True
        shadow.observe_org_data_scope(_user(level="3"), "own_dept")
        assert len(shadow._LOGGED) == 1
        assert len(caplog.records) == 1

    def test_exception_is_swallowed(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        caplog.set_level("DEBUG", logger="app.core.org_data_scope_shadow")

        class Boom:
            id = 9

            @property
            def organization(self):
                raise RuntimeError("detached instance")

        assert shadow.observe_org_data_scope(Boom(), "own_dept") is None
        assert "影子观测失败" in caplog.text


class TestGetDataScopeHook:
    def test_off_still_delegates(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            data_permission, "observe_org_data_scope", lambda user, scope: called.append(scope)
        )
        assert get_data_scope(_user()) == DataScope.OWN_DEPT
        assert called == ["own_dept"]

    def test_shadow_keeps_result(self, monkeypatch):
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        assert get_data_scope(_user(level="3")) == DataScope.OWN_DEPT

    def test_none_user_short_circuits(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            data_permission, "observe_org_data_scope", lambda user, scope: called.append(scope)
        )
        assert get_data_scope(None) == DataScope.OWN
        assert called == []

    def test_legacy_admin_without_org_still_own(self, monkeypatch):
        user = SimpleNamespace(id=1, role="admin", is_superuser=False, organization_id=None)
        monkeypatch.setattr(settings, "ORG_DATA_SCOPE_MODE", "shadow")
        assert get_data_scope(user) == DataScope.OWN
