# -*- coding: utf-8 -*-
"""R33：单位授权解析服务 + 菜单裁剪接入。

用真实 in-memory SQLite（只建 organizations / org_grants 两张表），覆盖：
- GrantMatrix 的四类判定（inactive 全拒、级别缺失即 none、可见/可写）；
- 组织树合并：子覆盖父、继承、子 deny 压父 grant、切断继承、脏数据成环、父级缺失；
- 缓存：命中不重查、grant_version 递增失效、clear_cache、超限清空；
- `menus._get_user_accessible_menu_keys` 的新旧两条路径（矩阵生效 vs legacy），
  以及"用户级 allowed_menus 只能收窄、不能扩大"这条防绕过规则。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import menus
from app.models.base import Base
from app.models.org_grant import OrgGrant
from app.models.organization import Organization
from app.services import effective_grant_service as egs
from app.services.effective_grant_service import (
    GrantMatrix,
    clear_cache,
    get_grant_matrix,
    module_keys_of,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Organization.__table__, OrgGrant.__table__])
    session = sessionmaker(bind=engine)()
    clear_cache()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        clear_cache()


def _user(org_id=None, superuser=False, role="user", allowed=None):
    return SimpleNamespace(
        organization_id=org_id,
        is_superuser=superuser,
        role=role,
        allowed_menus_list=allowed,
    )


def _org(db, name, parent=None, grant_version=0, inherit=True):
    org = Organization(
        name=name,
        parent_id=parent.id if parent is not None else None,
        grant_version=grant_version,
        inherit_from_parent=inherit,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _grant(db, org, module_key, level):
    db.add(OrgGrant(organization_id=org.id, module_key=module_key, level=level))
    db.commit()


class TestGrantMatrix:
    def test_inactive_denies_all(self):
        m = egs.INACTIVE
        assert m.active is False
        assert m.level("projects") == "none"
        assert m.can_view("projects") is False
        assert m.can_edit("projects") is False
        assert m.visible_keys() == set()

    def test_levels_and_predicates(self):
        m = GrantMatrix(active=True, levels={"a": "edit", "b": "view", "c": "none"})
        assert m.level("a") == "edit"
        assert m.level("missing") == "none"
        assert m.can_view("b") is True
        assert m.can_edit("b") is False
        assert m.can_edit("a") is True
        assert m.can_view("c") is False
        assert m.visible_keys() == {"a", "b"}

    def test_module_keys_of(self):
        assert module_keys_of({"a": "edit", "b": "none", "c": "view"}) == {"a", "c"}


class TestResolveBasics:
    def test_superuser_is_inactive(self, db):
        assert get_grant_matrix(db, _user(superuser=True)).active is False

    def test_no_organization(self, db):
        assert get_grant_matrix(db, _user()).active is False

    def test_organization_missing(self, db):
        assert get_grant_matrix(db, _user(org_id=99999)).active is False

    def test_org_without_grants_is_inactive(self, db):
        org = _org(db, "省厅")
        assert get_grant_matrix(db, _user(org.id)).active is False

    def test_org_with_grants_is_active(self, db):
        org = _org(db, "县局")
        _grant(db, org, "projects", "edit")
        m = get_grant_matrix(db, _user(org.id))
        assert m.active is True
        assert m.can_edit("projects") is True

    def test_version_only_counts_as_active(self, db):
        """已应用过授权包但矩阵为空（全部 none）也算激活，不能回落 legacy。"""
        org = _org(db, "县局", grant_version=3)
        m = get_grant_matrix(db, _user(org.id))
        assert m.active is True
        assert m.levels == {}
        assert m.can_view("projects") is False

    def test_invalid_level_row_is_ignored(self, db):
        org = _org(db, "县局")
        _grant(db, org, "projects", "own")  # 非法级别
        _grant(db, org, "funds", "view")
        m = get_grant_matrix(db, _user(org.id))
        assert m.level("projects") == "none"
        assert m.can_view("funds") is True


class TestInheritance:
    def test_child_inherits_parent(self, db):
        prov = _org(db, "省厅")
        city = _org(db, "市局", parent=prov)
        county = _org(db, "县局", parent=city)
        _grant(db, prov, "funds", "view")
        assert get_grant_matrix(db, _user(county.id)).can_view("funds") is True

    def test_deeper_level_wins(self, db):
        prov = _org(db, "省厅")
        city = _org(db, "市局", parent=prov)
        _grant(db, prov, "projects", "edit")
        _grant(db, city, "projects", "view")
        assert get_grant_matrix(db, _user(prov.id)).level("projects") == "edit"
        assert get_grant_matrix(db, _user(city.id)).level("projects") == "view"

    def test_child_deny_beats_parent_grant(self, db):
        prov = _org(db, "省厅")
        county = _org(db, "县局", parent=prov)
        _grant(db, prov, "funds", "edit")
        _grant(db, county, "funds", "none")
        assert get_grant_matrix(db, _user(county.id)).can_view("funds") is False

    def test_cut_inheritance_ignores_parent(self, db):
        prov = _org(db, "省厅")
        _grant(db, prov, "funds", "edit")
        county = _org(db, "县局", parent=prov, inherit=False)
        _grant(db, county, "projects", "view")
        m = get_grant_matrix(db, _user(county.id))
        assert m.level("funds") == "none"
        assert m.can_view("projects") is True

    def test_missing_parent_stops_chain(self, db):
        org = Organization(name="孤儿院", parent_id=123456)
        db.add(org)
        db.commit()
        db.refresh(org)
        _grant(db, org, "projects", "edit")
        assert get_grant_matrix(db, _user(org.id)).can_edit("projects") is True

    def test_parent_cycle_terminates(self, db):
        """脏数据成环不得死循环。"""
        a = _org(db, "A")
        b = _org(db, "B", parent=a)
        a.parent_id = b.id
        db.commit()
        _grant(db, a, "projects", "edit")
        m = get_grant_matrix(db, _user(b.id))
        assert m.can_edit("projects") is True


class TestCache:
    def test_second_read_hits_cache(self, db):
        org = _org(db, "县局")
        _grant(db, org, "projects", "edit")
        assert get_grant_matrix(db, _user(org.id)).level("projects") == "edit"
        # 改库但不递增 grant_version → 应命中缓存，读到的仍是旧值
        db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).update({"level": "none"})
        db.commit()
        assert get_grant_matrix(db, _user(org.id)).level("projects") == "edit"

    def test_version_bump_invalidates(self, db):
        org = _org(db, "县局")
        _grant(db, org, "projects", "edit")
        assert get_grant_matrix(db, _user(org.id)).level("projects") == "edit"
        db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).update({"level": "view"})
        org.grant_version = (org.grant_version or 0) + 1
        db.commit()
        assert get_grant_matrix(db, _user(org.id)).level("projects") == "view"

    def test_clear_cache_forces_reload(self, db):
        org = _org(db, "县局")
        _grant(db, org, "projects", "edit")
        get_grant_matrix(db, _user(org.id))
        db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).update({"level": "none"})
        db.commit()
        clear_cache()
        assert get_grant_matrix(db, _user(org.id)).level("projects") == "none"

    def test_cache_eviction_when_full(self, db, monkeypatch):
        monkeypatch.setattr(egs, "_CACHE_LIMIT", 1)
        first = _org(db, "县局一")
        second = _org(db, "县局二")
        _grant(db, first, "projects", "edit")
        _grant(db, second, "funds", "view")
        get_grant_matrix(db, _user(first.id))
        assert len(egs._CACHE) == 1
        get_grant_matrix(db, _user(second.id))
        assert len(egs._CACHE) == 1
        assert get_grant_matrix(db, _user(second.id)).can_view("funds") is True


class TestMenusIntegration:
    def test_matrix_active_uses_grants_only(self, db, monkeypatch):
        """矩阵生效时不再强制并入公开模块（上级"收掉"的意图必须生效）。"""
        matrix = GrantMatrix(active=True, levels={"projects": "edit", "funds": "view"})
        monkeypatch.setattr(egs, "get_grant_matrix", lambda _db, _u: matrix)
        keys = menus._get_user_accessible_menu_keys(_user(), MagicMock())
        assert keys == {"projects", "funds", "dashboard"}
        assert "policies" not in keys

    def test_matrix_active_user_allowed_can_only_narrow(self, db, monkeypatch):
        """用户级 allowed_menus 只能收窄 —— 防本地管理员绕过上级授权扩权。"""
        matrix = GrantMatrix(active=True, levels={"projects": "edit", "funds": "view"})
        monkeypatch.setattr(egs, "get_grant_matrix", lambda _db, _u: matrix)
        keys = menus._get_user_accessible_menu_keys(_user(allowed=["projects", "system"]), MagicMock())
        assert keys == {"projects", "dashboard"}

    def test_legacy_path_still_unions_public_keys(self, db, monkeypatch):
        monkeypatch.setattr(egs, "get_grant_matrix", lambda _db, _u: egs.INACTIVE)
        keys = menus._get_user_accessible_menu_keys(_user(), MagicMock())
        assert "policies" in keys
        assert len(keys) >= len(menus._PUBLIC_ACCESS_KEYS)
