"""结对帮扶服务层单测（w17-002）：校验 / 归一化 / 名称富化 / 统计 / 对象可达性。"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.data_permission import OrgScopeFilter
from app.models import Base
from app.models.organization import Organization  # noqa: F401
from app.models.pairing import PairingRecord, VisitRecord
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.models.user import User  # noqa: F401
from app.services.pairing_service import (
    attach_partner_names,
    ensure_pairing_valid,
    normalize_partner_fields,
    pairing_stats,
    resolve_partner,
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


def _mk_pairing(db, **kw):
    base = dict(
        subject_type="unit",
        subject_name="某单位",
        partner_type="village",
        title="对口帮扶",
        status="active",
        organization_id=1,
        created_by=7,
    )
    base.update(kw)
    p = PairingRecord(**base)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


class TestEnsurePairingValid:
    def test_valid_village(self):
        ensure_pairing_valid(
            subject_type="unit",
            partner_type="village",
            village_id=1,
            status="active",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

    def test_valid_without_dates_and_status(self):
        ensure_pairing_valid(subject_type="person", partner_type="student", student_name="张三")

    def test_invalid_subject_type(self):
        with pytest.raises(HTTPException) as ei:
            ensure_pairing_valid(subject_type="army", partner_type="village", village_id=1)
        assert ei.value.status_code == 422

    def test_invalid_partner_type(self):
        with pytest.raises(HTTPException) as ei:
            ensure_pairing_valid(subject_type="unit", partner_type="city")
        assert ei.value.status_code == 422

    def test_invalid_status(self):
        with pytest.raises(HTTPException) as ei:
            ensure_pairing_valid(
                subject_type="unit", partner_type="village", village_id=1, status="frozen"
            )
        assert ei.value.status_code == 422

    def test_village_requires_id(self):
        with pytest.raises(HTTPException):
            ensure_pairing_valid(subject_type="unit", partner_type="village")

    def test_school_requires_id(self):
        with pytest.raises(HTTPException):
            ensure_pairing_valid(subject_type="unit", partner_type="school")

    def test_student_requires_name(self):
        with pytest.raises(HTTPException):
            ensure_pairing_valid(subject_type="unit", partner_type="student")

    def test_end_before_start(self):
        with pytest.raises(HTTPException) as ei:
            ensure_pairing_valid(
                subject_type="unit",
                partner_type="village",
                village_id=1,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 4, 30),
            )
        assert ei.value.status_code == 422


class TestNormalizePartnerFields:
    def test_without_partner_type_keeps_payload(self):
        payload = {"partner_type": None, "village_id": 5, "school_id": 6, "student_name": "李四"}
        assert normalize_partner_fields(payload) is payload
        assert payload["village_id"] == 5
        assert payload["student_name"] == "李四"

    def test_village_clears_others(self):
        out = normalize_partner_fields(
            {"partner_type": "village", "village_id": 1, "school_id": 2, "student_name": "王五"}
        )
        assert out == {"partner_type": "village", "village_id": 1, "school_id": None, "student_name": None}

    def test_school_clears_others(self):
        out = normalize_partner_fields(
            {"partner_type": "school", "village_id": 1, "school_id": 2, "student_name": "王五"}
        )
        assert out == {"partner_type": "school", "village_id": None, "school_id": 2, "student_name": None}

    def test_student_clears_others(self):
        out = normalize_partner_fields(
            {"partner_type": "student", "village_id": 1, "school_id": 2, "student_name": "王五"}
        )
        assert out == {"partner_type": "student", "village_id": None, "school_id": None, "student_name": "王五"}


class TestResolvePartner:
    def test_student_is_noop(self, db):
        resolve_partner(db, partner_type="student", current_user=_user())

    def test_village_without_id_is_noop(self, db):
        resolve_partner(db, partner_type="village", village_id=None, current_user=_user())

    def test_village_ok(self, db):
        v = _mk_village(db)
        resolve_partner(db, partner_type="village", village_id=v.id, current_user=_user())

    def test_village_missing(self, db):
        from app.core.errors import AppError

        with pytest.raises(AppError):
            resolve_partner(db, partner_type="village", village_id=999, current_user=_user())

    def test_village_soft_deleted(self, db):
        from app.core.errors import AppError

        v = _mk_village(db, active=False)
        with pytest.raises(AppError):
            resolve_partner(db, partner_type="village", village_id=v.id, current_user=_user())

    def test_village_cross_org_forbidden(self, db):
        v = _mk_village(db, org_id=1, created_by=7)
        outsider = _user(id=9, role="user", organization_id=2, data_scope="org")
        with pytest.raises(HTTPException) as ei:
            resolve_partner(db, partner_type="village", village_id=v.id, current_user=outsider)
        assert ei.value.status_code == 403

    def test_school_ok(self, db):
        s = _mk_school(db)
        resolve_partner(db, partner_type="school", school_id=s.id, current_user=_user())

    def test_school_missing(self, db):
        from app.core.errors import AppError

        with pytest.raises(AppError):
            resolve_partner(db, partner_type="school", school_id=999, current_user=_user())

    def test_school_soft_deleted(self, db):
        from app.core.errors import AppError

        s = _mk_school(db, active=False)
        with pytest.raises(AppError):
            resolve_partner(db, partner_type="school", school_id=s.id, current_user=_user())

    def test_school_cross_org_forbidden(self, db):
        s = _mk_school(db, org_id=1, created_by=7)
        outsider = _user(id=9, role="user", organization_id=2, data_scope="org")
        with pytest.raises(HTTPException) as ei:
            resolve_partner(db, partner_type="school", school_id=s.id, current_user=outsider)
        assert ei.value.status_code == 403


class TestAttachPartnerNames:
    def test_empty_list(self, db):
        assert attach_partner_names(db, []) == []

    def test_village_and_school_and_student(self, db):
        v = _mk_village(db, name="幸福村")
        s = _mk_school(db, name="希望小学")
        items = [
            {"partner_type": "village", "village_id": v.id},
            {"partner_type": "village", "village_id": 999},  # 村已不存在 → None
            {"partner_type": "school", "school_id": s.id},
            {"partner_type": "school", "school_id": 999},  # 校已不存在 → None
            {"partner_type": "student", "student_name": "张三"},
            {"partner_type": "other", "student_name": None},
        ]
        attach_partner_names(db, items)
        assert items[0]["partner_name"] == "幸福村"
        assert items[1]["partner_name"] is None
        assert items[2]["partner_name"] == "希望小学"
        assert items[3]["partner_name"] is None
        assert items[4]["partner_name"] == "张三"
        assert items[5]["partner_name"] is None

    def test_only_school_ids(self, db):
        s = _mk_school(db)
        items = [{"partner_type": "school", "school_id": s.id}]
        attach_partner_names(db, items)
        assert items[0]["partner_name"] == "希望小学"

    def test_only_village_ids(self, db):
        v = _mk_village(db)
        items = [{"partner_type": "village", "village_id": v.id}]
        attach_partner_names(db, items)
        assert items[0]["partner_name"] == "幸福村"

    def test_soft_deleted_partner_not_resolved(self, db):
        """软删的村/校不再解析显示名（与软删过滤门禁同口径）。"""
        v = _mk_village(db, name="已删村", active=False)
        s = _mk_school(db, name="已删校", active=False)
        items = [
            {"partner_type": "village", "village_id": v.id},
            {"partner_type": "school", "school_id": s.id},
        ]
        attach_partner_names(db, items)
        assert items[0]["partner_name"] is None
        assert items[1]["partner_name"] is None


class TestPairingStats:
    def test_stats_counts(self, db):
        _mk_pairing(db)  # 在帮 village
        _mk_pairing(
            db,
            subject_type="person",
            partner_type="school",
            school_id=1,
            title="助学",
            status="ended",
        )
        visit = VisitRecord(
            pairing_id=1, visit_date=date(2026, 3, 1), visitors="甲", organization_id=1, created_by=7
        )
        db.add(visit)
        db.commit()

        stats = pairing_stats(db, OrgScopeFilter(is_admin=True))
        assert stats == {
            "total": 2,
            "active": 1,
            "ended": 1,
            "villages": 1,
            "schools": 1,
            "students": 0,
            "visits": 1,
        }

    def test_stats_include_deleted(self, db):
        p = _mk_pairing(db)
        p.is_active = False
        db.commit()
        assert pairing_stats(db, OrgScopeFilter(is_admin=True))["total"] == 0
        assert pairing_stats(db, OrgScopeFilter(is_admin=True), include_deleted=True)["total"] == 1

    def test_stats_visits_of_deleted_pairing(self, db):
        p = _mk_pairing(db)
        db.add(
            VisitRecord(
                pairing_id=p.id,
                visit_date=date(2026, 3, 1),
                visitors="甲",
                organization_id=1,
                created_by=7,
            )
        )
        db.commit()
        p.is_active = False
        db.commit()
        assert pairing_stats(db, OrgScopeFilter(is_admin=True))["visits"] == 0
        assert (
            pairing_stats(db, OrgScopeFilter(is_admin=True), include_deleted=True)["visits"] == 1
        )


class TestModelRepr:
    def test_repr(self, db):
        p = _mk_pairing(db)
        assert "PairingRecord" in repr(p)
        v = VisitRecord(
            pairing_id=p.id, visit_date=date(2026, 3, 1), visitors="甲", organization_id=1, created_by=7
        )
        assert "VisitRecord" in repr(v)
