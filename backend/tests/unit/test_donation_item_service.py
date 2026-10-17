"""捐赠物资服务层单测（w17-003）：校验 / 去向可达性 / 数据域基座 / 统计 / 名称富化。"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.data_permission import OrgScopeFilter
from app.core.errors import AppError
from app.models import Base
from app.models.donation_item import DonationItem
from app.models.organization import Organization  # noqa: F401
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.models.user import User  # noqa: F401
from app.services.donation_item_service import (
    attach_destination_names,
    donation_base_query,
    donation_stats,
    ensure_donation_valid,
    normalize_destination_fields,
    resolve_destination,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(**kw):
    base = dict(id=7, username="admin7", role="admin", organization_id=1, data_scope="all")
    base.update(kw)
    return SimpleNamespace(**base)


def _mk_village(db, name="幸福村", org_id=1, created_by=7, active=True):
    v = SupportedVillage(
        village_name=name, organization_id=org_id, created_by=created_by, is_active=active
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _mk_school(db, name="希望小学", org_id=1, created_by=7, active=True):
    s = School(name=name, organization_id=org_id, created_by=created_by, is_active=active)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _mk_project(db, name="操场改造", org_id=1, created_by=7, active=True):
    p = Project(name=name, organization_id=org_id, created_by=created_by, is_active=active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _mk_item(db, **kw):
    base = dict(
        name="图书",
        category="book",
        quantity=100,
        unit="册",
        valuation=1.5,
        source_unit="某部队",
        destination_type="village",
        organization_id=1,
        created_by=7,
    )
    base.update(kw)
    item = DonationItem(**base)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class TestEnsureDonationValid:
    def test_valid_village(self):
        ensure_donation_valid(
            category="book",
            destination_type="village",
            village_id=1,
            quantity=10,
            valuation=1.2,
        )

    def test_valid_without_quantity_valuation(self):
        ensure_donation_valid(category="material", destination_type="school", school_id=2)

    @pytest.mark.parametrize("category", ["", "unknown", "BOOK"])
    def test_invalid_category(self, category):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(category=category, destination_type="village", village_id=1)
        assert ei.value.status_code == 422
        assert "物资类别" in ei.value.detail

    def test_invalid_destination_type(self):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(category="book", destination_type="alien", village_id=1)
        assert ei.value.status_code == 422
        assert "去向类型" in ei.value.detail

    def test_village_requires_id(self):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(category="book", destination_type="village")
        assert ei.value.status_code == 422
        assert "帮扶村" in ei.value.detail

    def test_school_requires_id(self):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(category="book", destination_type="school")
        assert ei.value.status_code == 422
        assert "帮扶学校" in ei.value.detail

    def test_project_requires_id(self):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(category="book", destination_type="project")
        assert ei.value.status_code == 422
        assert "帮扶项目" in ei.value.detail

    def test_negative_quantity(self):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(
                category="book", destination_type="village", village_id=1, quantity=-1
            )
        assert ei.value.status_code == 422
        assert "数量" in ei.value.detail

    def test_negative_valuation(self):
        with pytest.raises(HTTPException) as ei:
            ensure_donation_valid(
                category="book", destination_type="village", village_id=1, valuation=-0.01
            )
        assert ei.value.status_code == 422
        assert "折价" in ei.value.detail


class TestResolveDestination:
    def test_village_ok(self, db):
        v = _mk_village(db)
        resolve_destination(
            db, destination_type="village", village_id=v.id, current_user=_user()
        )

    def test_village_missing(self, db):
        with pytest.raises(AppError) as ei:
            resolve_destination(
                db, destination_type="village", village_id=999, current_user=_user()
            )
        assert ei.value.status_code == 404

    def test_village_soft_deleted(self, db):
        v = _mk_village(db, active=False)
        with pytest.raises(AppError) as ei:
            resolve_destination(
                db, destination_type="village", village_id=v.id, current_user=_user()
            )
        assert ei.value.status_code == 404

    def test_village_cross_org(self, db):
        v = _mk_village(db, org_id=2, created_by=7)
        outsider = _user(id=9, role="user", organization_id=1, data_scope="org")
        with pytest.raises(HTTPException) as ei:
            resolve_destination(
                db, destination_type="village", village_id=v.id, current_user=outsider
            )
        assert ei.value.status_code == 403
        assert "帮扶村" in ei.value.detail

    def test_school_ok_and_missing_and_cross_org(self, db):
        s = _mk_school(db)
        resolve_destination(db, destination_type="school", school_id=s.id, current_user=_user())

        with pytest.raises(AppError) as ei:
            resolve_destination(
                db, destination_type="school", school_id=999, current_user=_user()
            )
        assert ei.value.status_code == 404

        outsider = _user(id=9, role="user", organization_id=2, data_scope="org")
        with pytest.raises(HTTPException) as ei:
            resolve_destination(
                db, destination_type="school", school_id=s.id, current_user=outsider
            )
        assert ei.value.status_code == 403
        assert "帮扶学校" in ei.value.detail

    def test_school_soft_deleted(self, db):
        s = _mk_school(db, active=False)
        with pytest.raises(AppError) as ei:
            resolve_destination(db, destination_type="school", school_id=s.id, current_user=_user())
        assert ei.value.status_code == 404

    def test_project_ok_and_missing_and_cross_org(self, db):
        p = _mk_project(db)
        resolve_destination(db, destination_type="project", project_id=p.id, current_user=_user())

        with pytest.raises(AppError) as ei:
            resolve_destination(
                db, destination_type="project", project_id=999, current_user=_user()
            )
        assert ei.value.status_code == 404

        outsider = _user(id=9, role="user", organization_id=2, data_scope="org")
        with pytest.raises(HTTPException) as ei:
            resolve_destination(
                db, destination_type="project", project_id=p.id, current_user=outsider
            )
        assert ei.value.status_code == 403
        assert "帮扶项目" in ei.value.detail

    def test_project_soft_deleted(self, db):
        p = _mk_project(db, active=False)
        with pytest.raises(AppError) as ei:
            resolve_destination(
                db, destination_type="project", project_id=p.id, current_user=_user()
            )
        assert ei.value.status_code == 404

    def test_no_matching_branch_is_noop(self, db):
        # 未知类型 / 缺 ID：不抛错（组合校验由 ensure_donation_valid 负责）
        resolve_destination(db, destination_type="village", village_id=None, current_user=_user())
        resolve_destination(db, destination_type="alien", current_user=_user())


class TestBaseQueryAndScope:
    def test_soft_deleted_filtered_by_default(self, db):
        _mk_item(db, name="在用")
        _mk_item(db, name="已删", is_active=False)
        scope = OrgScopeFilter(is_admin=True)

        names = [i.name for i in donation_base_query(db, scope).all()]
        assert names == ["在用"]
        assert len(donation_base_query(db, scope, include_deleted=True).all()) == 2

    def test_org_scope_isolation(self, db):
        _mk_item(db, name="一团物资", organization_id=1)
        _mk_item(db, name="二团物资", organization_id=2)
        scope = OrgScopeFilter(is_admin=False, org_ids=[1])
        assert [i.name for i in donation_base_query(db, scope).all()] == ["一团物资"]

    def test_self_only_scope(self, db):
        _mk_item(db, name="我的", created_by=7)
        _mk_item(db, name="别人的", created_by=9)
        scope = OrgScopeFilter(is_admin=False, self_only=True, user_id=7)
        assert [i.name for i in donation_base_query(db, scope).all()] == ["我的"]

    def test_self_only_without_user_id_or_created_by_column(self, db):
        # self_only 且缺 user_id → filter(False)（fail-closed）
        _mk_item(db, created_by=7)
        scope = OrgScopeFilter(is_admin=False, self_only=True, user_id=None)
        assert donation_base_query(db, scope).all() == []

    def test_no_org_ids(self, db):
        _mk_item(db)
        scope = OrgScopeFilter(is_admin=False, org_ids=[])
        assert donation_base_query(db, scope).all() == []


class TestStats:
    def test_stats_empty(self, db):
        stats = donation_stats(db, OrgScopeFilter(is_admin=True))
        assert stats == {
            "total": 0,
            "villages": 0,
            "schools": 0,
            "projects": 0,
            "books": 0,
            "equipment": 0,
            "materials": 0,
            "quantity": 0.0,
            "valuation": 0.0,
        }

    def test_stats_by_destination_and_category(self, db):
        _mk_item(db, name="图书A", category="book", quantity=10, valuation=1, destination_type="village", village_id=1)
        _mk_item(db, name="图书B", category="book", quantity=5, valuation=0.5, destination_type="village", village_id=1)
        _mk_item(db, name="电脑", category="equipment", quantity=3, valuation=9, destination_type="school", school_id=1)
        _mk_item(db, name="米面", category="material", quantity=20, valuation=2, destination_type="project", project_id=1)
        stats = donation_stats(db, OrgScopeFilter(is_admin=True))
        assert stats["total"] == 4
        assert stats["villages"] == 2
        assert stats["schools"] == 1
        assert stats["projects"] == 1
        assert stats["books"] == 2
        assert stats["equipment"] == 1
        assert stats["materials"] == 1
        assert stats["quantity"] == 38.0
        assert stats["valuation"] == 12.5

    def test_stats_include_deleted_and_scope(self, db):
        _mk_item(db, name="在用", organization_id=1, quantity=1, valuation=1)
        _mk_item(db, name="已删", organization_id=1, quantity=1, valuation=1, is_active=False)
        _mk_item(db, name="别组织", organization_id=2, quantity=1, valuation=1)
        scope = OrgScopeFilter(is_admin=False, org_ids=[1])
        assert donation_stats(db, scope)["total"] == 1
        assert donation_stats(db, scope, include_deleted=True)["total"] == 2


class TestNormalizeDestinationFields:
    def test_clears_mismatched_ids(self):
        payload = {
            "destination_type": "school",
            "village_id": 1,
            "school_id": 2,
            "project_id": 3,
        }
        out = normalize_destination_fields(payload)
        assert out == {"destination_type": "school", "village_id": None, "school_id": 2, "project_id": None}

    def test_keeps_matching_id_for_each_type(self):
        for key, value in (("village_id", 1), ("school_id", 2), ("project_id", 3)):
            payload = {"destination_type": key.split("_")[0], key: value}
            assert normalize_destination_fields(payload)[key] == value

    def test_missing_destination_type_untouched(self):
        payload = {"village_id": 1}
        assert normalize_destination_fields(payload) == {"village_id": 1}


class TestAttachDestinationNames:
    def test_empty_list(self, db):
        assert attach_destination_names(db, []) == []

    def test_all_types_and_fallbacks(self, db):
        v = _mk_village(db, name="幸福村")
        s = _mk_school(db, name="希望小学")
        p = _mk_project(db, name="操场改造")
        deleted = _mk_village(db, name="已删村", active=False)
        items = [
            {"destination_type": "village", "village_id": v.id},
            {"destination_type": "village", "village_id": 999},  # 不存在 → None
            {"destination_type": "village", "village_id": deleted.id},  # 软删 → None
            {"destination_type": "school", "school_id": s.id},
            {"destination_type": "school", "school_id": 999},
            {"destination_type": "project", "project_id": p.id},
            {"destination_type": "project", "project_id": 999},
            {"destination_type": "alien", "village_id": v.id},
            {"destination_type": "village", "village_id": None},
        ]
        attach_destination_names(db, items)
        assert [i["destination_name"] for i in items] == [
            "幸福村",
            None,
            None,
            "希望小学",
            None,
            "操场改造",
            None,
            None,
            None,
        ]

    def test_only_school_ids_branch(self, db):
        s = _mk_school(db, name="希望小学")
        items = [{"destination_type": "school", "school_id": s.id}]
        attach_destination_names(db, items)
        assert items[0]["destination_name"] == "希望小学"


def test_donation_item_to_dict_and_repr(db):
    item = _mk_item(
        db,
        delivery_date=date(2026, 5, 1),
        receiver="张三",
        remark="备注",
        attachments=[{"url": "/uploads/a.pdf", "file_name": "a.pdf"}],
    )
    data = item.to_dict()
    assert data["quantity"] == 100.0
    assert data["valuation"] == 1.5
    assert data["delivery_date"] == "2026-05-01"
    assert data["attachments"] == [{"url": "/uploads/a.pdf", "file_name": "a.pdf"}]
    assert data["is_active"] is True
    assert data["is_deleted"] is False
    assert data["created_at"] is not None
    assert "DonationItem" in repr(item)


def test_donation_item_to_dict_defaults(db):
    item = _mk_item(db, quantity=None, valuation=None, attachments=None, delivery_date=None)
    data = item.to_dict()
    assert data["quantity"] == 0.0
    assert data["valuation"] == 0.0
    assert data["attachments"] == []
    assert data["delivery_date"] is None
