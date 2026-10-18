"""消费帮扶台账服务层（W22 v1.14.0）。

覆盖：查询基座（软删 + 数据域）、筛选四条件、村名富化（含软删村）、
统计（年度/品类/村分布/空数据）、记录权限（404/403）、帮扶村可达性校验、
导出行组装（枚举中文标签 / 公式注入防护）。
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.data_permission import OrgScopeFilter
from app.models.consumption import ConsumptionRecord
from app.models.organization import Organization
from app.models.supported_village import SupportedVillage
from app.services import consumption_service as svc_mod
from app.services.consumption_service import (
    apply_consumption_filters,
    attach_village_names,
    build_export_table,
    consumption_base_query,
    consumption_statistics,
    ensure_village_accessible,
    get_consumption_or_404,
)


@pytest.fixture
def db():
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _admin_scope() -> OrgScopeFilter:
    return OrgScopeFilter(is_admin=True)


def _org_scope(org_ids=(1,), user_id=7) -> OrgScopeFilter:
    return OrgScopeFilter(is_admin=False, org_ids=list(org_ids), user_id=user_id)


def _self_scope(user_id=7) -> OrgScopeFilter:
    return OrgScopeFilter(is_admin=False, self_only=True, user_id=user_id)


def _user(**kw):
    base = dict(id=7, username="u7", role="user", organization_id=1, data_scope="org")
    base.update(kw)
    return SimpleNamespace(**base)


def _mk_org(db, org_id=1, name="一团"):
    org = Organization(id=org_id, name=name)
    db.add(org)
    db.commit()
    return org


def _mk_village(db, name="幸福村", org_id=1, created_by=7, active=True):
    village = SupportedVillage(
        village_name=name, organization_id=org_id, created_by=created_by, is_active=active
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _mk_record(db, **kw):
    base = dict(
        category="agriculture",
        item_name="土鸡蛋",
        quantity=10,
        unit="斤",
        amount=100.0,
        buyer="某部队",
        seller="张三",
        seller_type="farmer",
        year=2026,
        organization_id=1,
        created_by=7,
        is_active=True,
    )
    base.update(kw)
    record = ConsumptionRecord(**base)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


class TestBaseQueryAndFilters:
    def test_base_query_soft_delete_and_scope(self, db):
        _mk_record(db, item_name="一团在用", organization_id=1)
        _mk_record(db, item_name="一团已删", organization_id=1, is_active=False)
        _mk_record(db, item_name="二团在用", organization_id=2)

        admin_rows = consumption_base_query(db, _admin_scope()).all()
        assert {r.item_name for r in admin_rows} == {"一团在用", "二团在用"}

        with_deleted = consumption_base_query(db, _admin_scope(), include_deleted=True).all()
        assert len(with_deleted) == 3

        org_rows = consumption_base_query(db, _org_scope([1])).all()
        assert [r.item_name for r in org_rows] == ["一团在用"]

        self_rows = consumption_base_query(db, _self_scope(user_id=7)).all()
        # 仅本人口径按 created_by 过滤（不看组织归属）：两条 created_by=7 的在用记录
        assert {r.item_name for r in self_rows} == {"一团在用", "二团在用"}

    def test_apply_filters_all_conditions(self, db):
        v1 = _mk_village(db, name="一村")
        v2 = _mk_village(db, name="二村")
        _mk_record(db, item_name="苹果", category="agriculture", year=2025, supported_village_id=v1.id, buyer="甲")
        _mk_record(db, item_name="土鸡", category="livestock", year=2026, supported_village_id=v2.id, seller="乙")

        query = consumption_base_query(db, _admin_scope())
        assert apply_consumption_filters(query, year=2026).count() == 1
        assert apply_consumption_filters(query, category="agriculture").count() == 1
        assert apply_consumption_filters(query, village_id=v2.id).count() == 1
        assert apply_consumption_filters(query, keyword="苹果").count() == 1
        assert apply_consumption_filters(query, keyword="乙").count() == 1
        assert apply_consumption_filters(query).count() == 2


class TestAttachVillageNames:
    def test_attach_names_with_soft_deleted_village(self, db):
        village = _mk_village(db, name="在用村")
        deleted_village = _mk_village(db, name="已删村", active=False)
        rows = [
            {"supported_village_id": village.id},
            {"supported_village_id": deleted_village.id},
            {"supported_village_id": None},
        ]
        result = attach_village_names(db, rows)
        assert result[0]["village_name"] == "在用村"
        assert result[1]["village_name"] is None  # 软删村不解析名称
        assert result[2]["village_name"] is None

    def test_attach_names_without_ids_skips_query(self, db):
        rows = [{"supported_village_id": None}]
        assert attach_village_names(db, rows) == [{"supported_village_id": None, "village_name": None}]


class TestStatistics:
    def test_statistics_groups_year_filter(self, db):
        v1 = _mk_village(db, name="一村")
        v2 = _mk_village(db, name="二村")
        _mk_record(db, category="agriculture", amount=100, year=2026, supported_village_id=v1.id)
        _mk_record(db, category="agriculture", amount=50, year=2026, supported_village_id=v1.id)
        _mk_record(db, category="livestock", amount=200, year=2025, supported_village_id=v2.id)
        _mk_record(db, category="handicraft", amount=30, year=2026, supported_village_id=None)

        stats = consumption_statistics(db, _admin_scope(), year=2026)
        assert stats["record_count"] == 3
        assert stats["total_amount"] == 180.0
        category_map = {row["category"]: row for row in stats["by_category"]}
        assert category_map["agriculture"]["record_count"] == 2
        assert category_map["agriculture"]["amount"] == 150.0
        assert category_map["handicraft"]["amount"] == 30.0
        assert "livestock" not in category_map
        village_map = {row["village_name"]: row for row in stats["by_village"]}
        assert village_map["一村"]["amount"] == 150.0
        assert None not in village_map

    def test_statistics_empty_and_include_deleted(self, db):
        empty = consumption_statistics(db, _admin_scope())
        assert empty == {
            "total_amount": 0.0,
            "record_count": 0,
            "by_category": [],
            "by_village": [],
        }

        _mk_record(db, amount=10, is_active=False)
        stats = consumption_statistics(db, _admin_scope(), include_deleted=True)
        assert stats["record_count"] == 1
        assert stats["total_amount"] == 10.0

    def test_statistics_scope_restricted(self, db):
        _mk_record(db, amount=100, organization_id=1, created_by=7)
        _mk_record(db, amount=200, organization_id=2, created_by=9)
        stats = consumption_statistics(db, _org_scope([1]))
        assert stats["record_count"] == 1
        assert stats["total_amount"] == 100.0

        self_stats = consumption_statistics(db, _self_scope(user_id=7))
        assert self_stats["record_count"] == 1
        assert self_stats["total_amount"] == 100.0


class TestRecordAndVillageGuards:
    def test_get_record_not_found(self, db):
        from app.core.errors import AppError

        with pytest.raises(AppError) as exc:
            get_consumption_or_404(db, 999, _user(), "无权访问")
        assert "不存在" in str(exc.value)

    def test_get_record_cross_org_forbidden(self, db):
        from fastapi import HTTPException

        record = _mk_record(db, organization_id=2, created_by=99)
        with pytest.raises(HTTPException) as exc:
            get_consumption_or_404(db, record.id, _user(id=7, organization_id=1), "无权编辑")
        assert exc.value.status_code == 403

    def test_get_record_owner_allowed(self, db):
        record = _mk_record(db, organization_id=2, created_by=7)
        assert get_consumption_or_404(db, record.id, _user(id=7, organization_id=1), "x").id == record.id

    def test_ensure_village_accessible_variants(self, db):
        from app.core.errors import AppError
        from fastapi import HTTPException

        ensure_village_accessible(db, None, _user())  # None 直接放行
        village = _mk_village(db)
        ensure_village_accessible(db, village.id, _user())  # 同组织放行

        with pytest.raises(AppError):
            ensure_village_accessible(db, 999, _user())
        soft_deleted = _mk_village(db, name="已删村", active=False)
        with pytest.raises(AppError):
            ensure_village_accessible(db, soft_deleted.id, _user())

        other = _mk_village(db, name="外人村", org_id=2)
        with pytest.raises(HTTPException) as exc:
            ensure_village_accessible(db, other.id, _user(id=9, organization_id=1))
        assert exc.value.status_code == 403


class TestBuildExportTable:
    def test_export_table_labels_and_formula_guard(self):
        rows = [
            {
                "id": 1,
                "year": 2026,
                "record_date": "2026-06-01",
                "category": "agriculture",
                "item_name": "=SUM(A1:A2)",   # 公式注入 → 前缀单引号
                "quantity": 10.0,
                "unit": "斤",
                "amount": 100.0,
                "buyer": "某部队",
                "seller": "张三",
                "seller_type": "farmer",
                "village_name": "幸福村",
                "remarks": None,
            },
            {
                "id": 2,
                "year": 2026,
                "record_date": None,
                "category": "unknown_category",   # 未登记枚举 → 原值输出
                "item_name": "竹编",
                "quantity": None,
                "unit": None,
                "amount": 30.0,
                "buyer": None,
                "seller": None,
                "seller_type": "unknown_seller",
                "village_name": None,
                "remarks": "备注",
            },
        ]
        headers, data_rows = build_export_table(rows)
        assert headers[0] == "ID"
        assert "产品名称" in headers
        assert data_rows[0][3] == "农产品"
        assert data_rows[0][4] == "'=SUM(A1:A2)"
        assert data_rows[0][10] == "农户"
        assert data_rows[1][3] == "unknown_category"
        assert data_rows[1][10] == "unknown_seller"
        assert data_rows[1][12] == "备注"


def test_module_constants_cover_contract_enums():
    """契约 §1.5 枚举必须与模型常量一致（防止后续迁移漏项）。"""
    assert svc_mod.CATEGORY_LABELS == {
        "agriculture": "农产品",
        "livestock": "畜禽",
        "handicraft": "手工制品",
        "other": "其他",
    }
    assert svc_mod.SELLER_TYPE_LABELS == {
        "farmer": "农户",
        "cooperative": "合作社",
        "enterprise": "企业",
    }
    assert [key for key, _label in svc_mod.EXPORT_COLUMNS][:3] == ["id", "year", "record_date"]
