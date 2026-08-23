"""统计口径排除软删数据回归测试 (T05)

需求：软删除（is_active=False）的帮扶村/项目/经费不纳入任何统计模块。
覆盖：系统概览、项目统计、成效评估、KPI 汇总。
"""
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user


@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch(
        "app.middleware.camel_to_snake._convert_keys",
        side_effect=lambda obj, converter: (obj, False),
    ):
        yield


@pytest.fixture
def client_and_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    admin = Mock(
        id=1, username="admin", role="admin", is_superuser=True,
        is_active=True, permissions_list=["*"], organization_id=1,
    )

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: admin

    from app.core.cache import default_cache

    default_cache.clear()

    client = TestClient(app, raise_server_exceptions=False)
    yield client, db
    db.close()
    engine.dispose()
    app.dependency_overrides = original


def _mk_village(db, name, is_active=True):
    from app.models.supported_village import SupportedVillage

    v = SupportedVillage(
        village_name=name, province="贵州省", county="测试县",
        organization_id=1, created_by=1,
    )
    v.is_active = is_active
    db.add(v)
    db.flush()
    return v


def _mk_project(db, name, village_id, budget=10, is_active=True):
    from app.models.project import Project

    p = Project(name=name, village_id=village_id, code=f"T05-{name}", budget=budget)
    p.is_active = is_active
    db.add(p)
    db.flush()
    return p


class TestSummaryExcludesSoftDeleted:
    def test_counts_exclude_deleted(self, client_and_db):
        client, db = client_and_db
        v = _mk_village(db, "口径村A")
        _mk_project(db, "活跃项目", v.id)
        _mk_project(db, "软删项目", v.id, is_active=False)
        from app.models.fund import Fund

        f_active = Fund(amount=100, status="approved", village_id=v.id)
        f_deleted = Fund(amount=999, status="approved", village_id=v.id)
        f_deleted.is_active = False
        db.add_all([f_active, f_deleted])
        db.commit()

        resp = client.get("/api/v1/statistics/summary")
        assert resp.status_code == 200, resp.text[:200]
        data = resp.json().get("data") or resp.json()
        assert data["total_projects"] == 1
        assert data["total_funds"] == 1
        assert data["approved_funds_amount"] == 100

    def test_projects_statistics_exclude_deleted(self, client_and_db):
        client, db = client_and_db
        v = _mk_village(db, "项目统计村")
        _mk_project(db, "活1", v.id, budget=100)
        _mk_project(db, "删2", v.id, budget=5000, is_active=False)
        db.commit()

        resp = client.get("/api/v1/statistics/projects/statistics")
        assert resp.status_code == 200, resp.text[:200]
        data = resp.json().get("data") or {}
        # 预算合计只含活跃项目
        assert float(data["total_budget"]) == 100
        names = [p["name"] for p in data["recent_projects"]]
        assert "删2" not in names


class TestAssessmentExcludesSoftDeleted:
    def test_village_scores_skip_deleted(self, client_and_db):
        client, db = client_and_db
        _mk_village(db, "评估村-在册")
        _mk_village(db, "评估村-已删", is_active=False)
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200, resp.text[:300]
        payload = resp.json().get("data") or {}
        items = payload.get("items") if isinstance(payload, dict) else payload
        names = {it.get("village_name") for it in (items or [])}
        assert "评估村-在册" in names
        assert "评估村-已删" not in names


class TestKpiSummaryExcludesSoftDeleted:
    def test_kpi_counts_exclude_deleted(self, client_and_db):
        client, db = client_and_db
        v = _mk_village(db, "KPI村")
        _mk_project(db, "KPI活跃", v.id)
        _mk_project(db, "KPI软删", v.id, is_active=False)
        _mk_village(db, "KPI软删村", is_active=False)
        db.commit()

        resp = client.get("/api/v1/analytics/kpi-summary")
        assert resp.status_code == 200, resp.text[:300]
        body = resp.json()
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        assert data["total_projects"] == 1
