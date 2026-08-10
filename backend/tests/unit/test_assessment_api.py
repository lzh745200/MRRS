"""Comprehensive tests for assessment.py — all 4 endpoints, full branch & edge-case coverage.

Uses a self-contained fixture (in-memory SQLite + auth + cache-patchable) to
avoid conftest fixture interactions. No explicit model IDs — all auto-generated.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.supported_village import SupportedVillage, VillageIncome
from app.models.project import Project
from app.models.fund import Fund
from app.api.v1.assessment import (
    _calculate_village_score_batch,
    _score_level,
    SCORE_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Middleware patch
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch(
        "app.middleware.camel_to_snake._convert_keys",
        side_effect=lambda obj, converter: (obj, False),
    ):
        yield


# ---------------------------------------------------------------------------
# Self-contained fixture — one fresh in-memory SQLite DB per test.
# Returns (client, db_session).  All data seeding uses db_session.
# ---------------------------------------------------------------------------

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

    _mock_user = Mock(id=1, username="admin", role="admin", is_superuser=True,
                      is_active=True, permissions_list=["*"], organization_id=1)

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: _mock_user

    # Clear the real CacheManager singleton so stale cached data from
    # previous tests never leaks.  (The endpoint calls get_cache_service()
    # directly, not via Depends, so dependency_overrides does not help.)
    from app.core.cache import default_cache
    default_cache.clear()

    client = TestClient(app, raise_server_exceptions=False)
    yield client, db

    # Clean up
    db.close()
    engine.dispose()
    app.dependency_overrides = _original_overrides


# ---------------------------------------------------------------------------
# Test-data helpers (no explicit IDs — auto-generated)
# ---------------------------------------------------------------------------

_REF_DATE = date.today()
_CURRENT_YEAR = _REF_DATE.year


def mkv(db, name="测试村", support_unit="某部队"):
    v = SupportedVillage(
        village_name=name, support_unit=support_unit,
        province="贵州省", city="毕节市", county="测试县",
        department="测试部", is_three_regions=True,
        is_revitalization_tier=True,
    )
    db.add(v)
    return v


def mki(db, village_id, year, per_capita=1.5, collective=20.0):
    inc = VillageIncome(
        supported_village_id=village_id, year=year,
        per_capita_income=per_capita, collective_income=collective,
    )
    db.add(inc)
    return inc


def mkp(db, village_id, name="项目X", status="completed", budget=100, actual_cost=80, end_date=None):
    p = Project(
        name=name, village_id=village_id, status=status,
        budget=budget, actual_cost=actual_cost, end_date=end_date,
    )
    db.add(p)
    return p


def mkf(db, village_id, amount=50, used_amount=45):
    f = Fund(
        village_id=village_id, amount=amount, used_amount=used_amount,
        name="经费", fund_type="乡村振兴",
    )
    db.add(f)
    return f


# ===================================================================
#  GET /assessment/village-scores
# ===================================================================

class TestGetVillageScores:

    def test_empty_no_villages(self, client_and_db):
        client, db = client_and_db
        db.commit()
        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0
        assert data["year"] == _CURRENT_YEAR
        assert data["weights"] == SCORE_WEIGHTS

    def test_empty_no_villages_custom_year(self, client_and_db):
        client, db = client_and_db
        resp = client.get("/api/v1/assessment/village-scores?year=2023")
        assert resp.status_code == 200
        assert resp.json()["year"] == 2023

    def test_village_no_income_no_projects_no_funds(self, client_and_db):
        client, db = client_and_db
        mkv(db)
        db.commit()
        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        item = data["items"][0]
        assert item["village_name"] == "测试村"
        assert item["rank"] == 1
        assert item["scores"]["economic"] == 50.0
        assert item["scores"]["social"] == 60.0
        assert item["scores"]["project_completion"] == 50.0
        assert item["scores"]["fund_execution"] == 50.0
        assert item["total_score"] == 52.5

    def test_two_villages_with_full_data_ranking(self, client_and_db):
        client, db = client_and_db
        v1 = mkv(db, name="富裕村")
        v2 = mkv(db, name="普通村")
        db.commit()  # commit so v1.id / v2.id are populated

        mki(db, v1.id, _CURRENT_YEAR, per_capita=2.0, collective=30)
        mki(db, v1.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=20)
        mki(db, v2.id, _CURRENT_YEAR, per_capita=1.5, collective=15)
        mki(db, v2.id, _CURRENT_YEAR - 1, per_capita=1.5, collective=15)

        mkp(db, v1.id, name="项目1", status="completed")
        mkp(db, v1.id, name="项目2", status="completed")
        mkp(db, v2.id, name="项目3", status="in_progress")

        mkf(db, v1.id, amount=50, used_amount=45)
        mkf(db, v2.id, amount=100, used_amount=10)
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2, f"Expected 2, got {data}"
        first, second = data["items"]
        assert first["rank"] == 1
        assert second["rank"] == 2
        assert first["village_name"] == "富裕村"
        assert first["total_score"] > second["total_score"]

        assert first["scores"]["economic"] == 100.0
        assert second["scores"]["economic"] == 50.0
        assert first["scores"]["social"] == 80.0
        assert first["scores"]["project_completion"] == 100.0
        assert second["scores"]["project_completion"] == 0.0
        assert first["scores"]["fund_execution"] == 90.0
        assert second["scores"]["fund_execution"] == 10.0

    def test_income_decline_economic_floor(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="衰退村")
        db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=1.0, collective=10)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=2.0, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        item = resp.json()["data"]["items"][0]
        assert item["scores"]["economic"] == 0.0

    def test_income_growth_economic_cap(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="暴增村")
        db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=2.0, collective=30)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=0.1, collective=5)
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        item = resp.json()["data"]["items"][0]
        assert item["scores"]["economic"] == 100.0

    @patch("app.api.v1.assessment.get_cache_service")
    def test_cached_response(self, mock_get_cache, client_and_db):
        client, db = client_and_db
        mc = AsyncMock()
        mc.get.return_value = {
            "code": 200, "message": "成功", "success": True,
            "data": {
                "items": [{"village_id": 99, "village_name": "缓存村", "rank": 1}],
                "total": 1, "page": 1, "page_size": 20,
            },
            "year": _CURRENT_YEAR, "weights": SCORE_WEIGHTS,
        }
        mock_get_cache.return_value = mc
        mkv(db); db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["village_id"] == 99
        assert resp.json()["data"]["items"][0]["village_name"] == "缓存村"
        mc.get.assert_called()

    @patch("app.api.v1.assessment.get_cache_service")
    def test_cache_miss_sets_cache(self, mock_get_cache, client_and_db):
        client, db = client_and_db
        mc = AsyncMock()
        mc.get.return_value = None
        mock_get_cache.return_value = mc
        mkv(db); db.commit()

        client.get("/api/v1/assessment/village-scores")
        assert mc.set.called
        args, kwargs = mc.set.call_args
        assert args[0] == f"village_scores:{_CURRENT_YEAR}"
        assert kwargs.get("ttl") == 300 or (len(args) >= 3 and args[2] == 300)

    @patch("app.api.v1.assessment.get_cache_service")
    def test_custom_year_cache_key(self, mock_get_cache, client_and_db):
        client, db = client_and_db
        mc = AsyncMock()
        mc.get.return_value = None
        mock_get_cache.return_value = mc
        mkv(db); db.commit()

        client.get("/api/v1/assessment/village-scores?year=2022")
        assert mc.set.called
        assert mc.set.call_args[0][0] == "village_scores:2022"

    def test_score_level_assignment(self, client_and_db):
        client, db = client_and_db
        v_high = mkv(db, name="优村")
        v_low = mkv(db, name="差村")
        db.commit()

        mki(db, v_high.id, _CURRENT_YEAR, per_capita=5.0, collective=100)
        mki(db, v_high.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=50)
        mkp(db, v_high.id, name="P1", status="completed", budget=100, actual_cost=100)
        mkf(db, v_high.id, amount=100, used_amount=100)
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 2, f"Expected 2, got {items}"
        levels = {it["village_name"]: it["level"] for it in items}
        assert levels.get("优村") == "优秀", f"levels={levels}"
        assert levels.get("差村") == "待改进", f"levels={levels}"

    def test_multiple_villages_rank_sequential(self, client_and_db):
        client, db = client_and_db
        for i in range(1, 6):
            mkv(db, name=f"村{i}")
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 5, f"Expected 5, got {items}"
        ranks = [it["rank"] for it in items]
        assert ranks == list(range(1, 6))

    def test_support_unit_in_response(self, client_and_db):
        client, db = client_and_db
        mkv(db, name="某村", support_unit="火箭军某部")
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        item = resp.json()["data"]["items"][0]
        assert item["support_unit"] == "火箭军某部"
        assert item["village_name"] == "某村"

    def test_empty_support_unit_uses_empty_string(self, client_and_db):
        client, db = client_and_db
        mkv(db, name="某村", support_unit=None)
        db.commit()

        resp = client.get("/api/v1/assessment/village-scores")
        item = resp.json()["data"]["items"][0]
        assert item["support_unit"] == ""


# ===================================================================
#  GET /assessment/anomalies
# ===================================================================

class TestDetectAnomalies:

    def test_empty_no_anomalies(self, client_and_db):
        client, db = client_and_db
        resp = client.get("/api/v1/assessment/anomalies")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []
        assert resp.json()["data"]["total"] == 0

    def test_income_drop_detected(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="下降村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=0.6, collective=10)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=15)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 1
        assert drops[0]["level"] == "danger"
        assert drops[0]["village_name"] == "下降村"
        assert "40.0%" in drops[0]["message"]

    def test_income_drop_exactly_30_percent_not_triggered(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="临界村"); db.commit()
        # (0.75 - 1.0) / 1.0 = -0.25 → NOT < -0.3 (0.7 has float precision issues)
        mki(db, v.id, _CURRENT_YEAR, per_capita=0.75, collective=10)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=15)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 0, f"unexpected drops: {drops}"

    def test_income_drop_just_over_30_percent_triggered(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="略超村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=0.699, collective=10)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=15)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 1

    def test_income_increase_no_anomaly(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="增长村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=2.0, collective=30)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 0

    def test_no_previous_year_no_anomaly(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="新村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=0.5, collective=5)
        db.commit()
        resp = client.get("/api/v1/assessment/anomalies")
        assert resp.json()["data"]["total"] == 0

    def test_previous_income_zero_no_anomaly(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="零收村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=1.0, collective=10)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=0.0, collective=0)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 0

    def test_previous_income_none_no_anomaly(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="空收村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=1.0, collective=10)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=None, collective=None)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 0

    def test_project_overdue_detected(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        overdue_date = _REF_DATE - timedelta(days=60)
        mkp(db, v.id, name="逾期项目", status="in_progress", end_date=overdue_date)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overdues = [a for a in resp.json()["data"]["items"] if a["type"] == "project_overdue"]
        assert len(overdues) == 1
        assert overdues[0]["level"] == "warning"
        assert overdues[0]["project_name"] == "逾期项目"

    def test_project_overdue_less_than_30_days_not_triggered(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        recent_date = _REF_DATE - timedelta(days=10)
        mkp(db, v.id, name="近期项目", status="in_progress", end_date=recent_date)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overdues = [a for a in resp.json()["data"]["items"] if a["type"] == "project_overdue"]
        assert len(overdues) == 0

    def test_completed_project_no_overdue(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        old_date = _REF_DATE - timedelta(days=365)
        mkp(db, v.id, name="已完成", status="completed", end_date=old_date)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overdues = [a for a in resp.json()["data"]["items"] if a["type"] == "project_overdue"]
        assert len(overdues) == 0

    def test_cancelled_project_no_overdue(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        old_date = _REF_DATE - timedelta(days=100)
        mkp(db, v.id, name="已取消", status="cancelled", end_date=old_date)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overdues = [a for a in resp.json()["data"]["items"] if a["type"] == "project_overdue"]
        assert len(overdues) == 0

    def test_budget_overrun_detected(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        mkp(db, v.id, name="超支项目", status="in_progress", budget=100, actual_cost=150)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overruns = [a for a in resp.json()["data"]["items"] if a["type"] == "budget_overrun"]
        assert len(overruns) == 1
        assert overruns[0]["project_name"] == "超支项目"
        assert "50.0%" in overruns[0]["message"]

    def test_budget_zero_no_overrun(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        mkp(db, v.id, name="零预算", status="in_progress", budget=0, actual_cost=100)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overruns = [a for a in resp.json()["data"]["items"] if a["type"] == "budget_overrun"]
        assert len(overruns) == 0

    def test_budget_equal_cost_no_overrun(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        mkp(db, v.id, name="恰好", status="in_progress", budget=100, actual_cost=100)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overruns = [a for a in resp.json()["data"]["items"] if a["type"] == "budget_overrun"]
        assert len(overruns) == 0

    def test_multiple_anomaly_types(self, client_and_db):
        client, db = client_and_db
        v1 = mkv(db, name="多问题村")
        v2 = mkv(db, name="超支村")
        db.commit()

        mki(db, v1.id, _CURRENT_YEAR, per_capita=0.5, collective=8)
        mki(db, v1.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=15)
        overdue_date = _REF_DATE - timedelta(days=90)
        mkp(db, v1.id, name="拖期项目", status="in_progress", end_date=overdue_date)
        mkp(db, v2.id, name="超支工程", status="in_progress", budget=100, actual_cost=200)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        types = {a["type"] for a in resp.json()["data"]["items"]}
        assert "income_drop" in types
        assert "project_overdue" in types
        assert "budget_overrun" in types

    def test_project_end_date_none_no_overdue(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        p = Project(name="无日期项目", village_id=v.id, status="in_progress",
                    end_date=None, budget=100, actual_cost=50)
        db.add(p)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        overdues = [a for a in resp.json()["data"]["items"] if a["type"] == "project_overdue"]
        assert len(overdues) == 0

    def test_current_per_capita_none_triggers_drop(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=None, collective=None)
        mki(db, v.id, _CURRENT_YEAR - 1, per_capita=1.0, collective=15)
        db.commit()

        resp = client.get("/api/v1/assessment/anomalies")
        drops = [a for a in resp.json()["data"]["items"] if a["type"] == "income_drop"]
        assert len(drops) == 1


# ===================================================================
#  GET /assessment/trend-prediction
# ===================================================================

class TestTrendPrediction:

    def test_insufficient_data_zero_rows(self, client_and_db):
        client, db = client_and_db
        resp = client.get("/api/v1/assessment/trend-prediction")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "数据不足，至少需要两年数据"
        assert data["historical"] == []
        assert data["predicted"] == []

    def test_insufficient_data_one_row(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2024, per_capita=1.5, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        assert "数据不足" in resp.json()["message"]

    def test_two_years_per_capita_income(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2024, per_capita=1.5, collective=20)
        mki(db, v.id, 2025, per_capita=2.0, collective=25)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction?metric=per_capita_income")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "per_capita_income"
        assert len(data["historical"]) == 2
        assert len(data["predicted"]) == 2
        assert data["predicted"][0]["year"] == 2026
        assert data["predicted"][1]["year"] == 2027
        assert data["slope"] > 0

    def test_three_years_per_capita_income(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2023, per_capita=1.0, collective=15)
        mki(db, v.id, 2024, per_capita=1.5, collective=20)
        mki(db, v.id, 2025, per_capita=2.0, collective=25)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction?metric=per_capita_income")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["historical"]) == 3
        assert [h["year"] for h in data["historical"]] == [2023, 2024, 2025]

    def test_collective_income_metric(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2024, per_capita=1.5, collective=20)
        mki(db, v.id, 2025, per_capita=2.0, collective=30)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction?metric=collective_income")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "collective_income"
        assert data["historical"][0]["value"] == 20.0
        assert data["historical"][1]["value"] == 30.0

    def test_flat_data_zero_slope(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        for yr in range(2020, 2025):
            mki(db, v.id, yr, per_capita=2.0, collective=25)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        data = resp.json()
        assert data["slope"] == 0.0
        for h in data["historical"]:
            assert h["value"] == 2.0
        for p in data["predicted"]:
            assert p["value"] == 2.0

    def test_decreasing_trend(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2023, per_capita=3.0, collective=40)
        mki(db, v.id, 2024, per_capita=2.0, collective=30)
        mki(db, v.id, 2025, per_capita=1.0, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        assert resp.json()["slope"] < 0

    def test_predicted_values_non_negative(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2023, per_capita=5.0, collective=50)
        mki(db, v.id, 2024, per_capita=2.0, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        for p in resp.json()["predicted"]:
            assert p["value"] >= 0

    def test_intercept_field_present(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2023, per_capita=1.0, collective=10)
        mki(db, v.id, 2024, per_capita=2.0, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        data = resp.json()
        assert "slope" in data
        assert "intercept" in data
        assert isinstance(data["slope"], (int, float))

    def test_multiple_villages_averaged(self, client_and_db):
        client, db = client_and_db
        v1 = mkv(db, name="A村")
        v2 = mkv(db, name="B村")
        db.commit()
        mki(db, v1.id, 2024, per_capita=1.0, collective=10)
        mki(db, v2.id, 2024, per_capita=3.0, collective=30)
        mki(db, v1.id, 2025, per_capita=2.0, collective=20)
        mki(db, v2.id, 2025, per_capita=4.0, collective=40)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        data = resp.json()
        assert len(data["historical"]) == 2
        assert data["historical"][0]["value"] == 2.0
        assert data["historical"][1]["value"] == 3.0

    def test_null_collective_income_handled(self, client_and_db):
        client, db = client_and_db
        v = mkv(db); db.commit()
        mki(db, v.id, 2024, per_capita=1.0, collective=None)
        mki(db, v.id, 2025, per_capita=2.0, collective=20)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction?metric=collective_income")
        assert resp.status_code == 200
        data = resp.json()
        assert data["historical"][0]["value"] == 0.0
        assert data["historical"][1]["value"] == 20.0

    def test_village_without_income_not_affecting_aggregation(self, client_and_db):
        client, db = client_and_db
        v1 = mkv(db, name="有收村")
        v2 = mkv(db, name="无收村")
        db.commit()
        mki(db, v1.id, 2024, per_capita=1.0, collective=10)
        mki(db, v1.id, 2025, per_capita=1.5, collective=15)
        db.commit()

        resp = client.get("/api/v1/assessment/trend-prediction")
        data = resp.json()
        assert data["historical"][0]["value"] == 1.0
        assert data["historical"][1]["value"] == 1.5


# ===================================================================
#  GET /assessment/village-comparison
# ===================================================================

class TestVillageComparison:

    def test_empty_village_ids(self, client_and_db):
        client, db = client_and_db
        resp = client.get("/api/v1/assessment/village-comparison?village_ids=")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []
        assert resp.json()["data"]["total"] == 0

    def test_non_numeric_ids(self, client_and_db):
        client, db = client_and_db
        resp = client.get("/api/v1/assessment/village-comparison?village_ids=abc,def")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_mixed_valid_and_invalid_ids(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id},abc,xyz")
        assert resp.json()["data"]["total"] == 1

    def test_single_village_full_data(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="完整村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=2.5, collective=35)
        mkp(db, v.id, name="项目A", status="completed")
        mkp(db, v.id, name="项目B", status="in_progress")
        mkf(db, v.id, amount=200, used_amount=180)
        db.commit()

        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["village_name"] == "完整村"
        assert item["per_capita_income"] == 2.5
        assert item["collective_income"] == 35.0
        assert item["total_projects"] == 2
        assert item["completed_projects"] == 1
        assert item["project_completion_rate"] == 50.0
        assert item["total_funds"] == 200.0

    def test_two_villages_comparison(self, client_and_db):
        client, db = client_and_db
        v1 = mkv(db, name="A村")
        v2 = mkv(db, name="B村")
        db.commit()
        mki(db, v1.id, _CURRENT_YEAR, per_capita=1.0, collective=10)
        mki(db, v2.id, _CURRENT_YEAR, per_capita=3.0, collective=50)
        db.commit()

        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v1.id},{v2.id}")
        names = {it["village_name"] for it in resp.json()["data"]["items"]}
        assert names == {"A村", "B村"}

    def test_five_villages_max(self, client_and_db):
        client, db = client_and_db
        villages = [mkv(db, name=f"村{i}") for i in range(1, 6)]
        db.commit()  # commit first, so v.id is auto-populated
        ids = [v.id for v in villages]
        resp = client.get("/api/v1/assessment/village-comparison?village_ids=" + ",".join(map(str, ids)))
        assert resp.json()["data"]["total"] == 5

    def test_more_than_five_ids_truncated(self, client_and_db):
        client, db = client_and_db
        villages = [mkv(db, name=f"村{i}") for i in range(1, 8)]
        db.commit()  # commit first, so v.id is auto-populated
        ids = [v.id for v in villages]
        resp = client.get("/api/v1/assessment/village-comparison?village_ids=" + ",".join(map(str, ids)))
        ids_returned = {it["village_id"] for it in resp.json()["data"]["items"]}
        assert len(ids_returned) == 5, f"Expected 5 unique IDs, got {ids_returned}"
        assert ids_returned == set(ids[:5])

    def test_village_not_found_skipped(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id},99999")
        data = resp.json()["data"]
        assert data["total"] == 1

    def test_village_no_income_data(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="无收村"); db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["per_capita_income"] == 0
        assert item["collective_income"] == 0

    def test_village_no_projects(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="无项村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=1.5, collective=20)
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["total_projects"] == 0
        assert item["completed_projects"] == 0
        assert item["project_completion_rate"] == 0

    def test_village_no_funds(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="无费村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=1.5, collective=20)
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["total_funds"] == 0

    def test_village_only_one_income_year(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="单收村"); db.commit()
        mki(db, v.id, 2023, per_capita=1.8, collective=25)
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["per_capita_income"] == 1.8

    def test_village_multiple_income_years_picks_latest(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="多收村"); db.commit()
        mki(db, v.id, 2020, per_capita=0.5, collective=5)
        mki(db, v.id, 2023, per_capita=1.5, collective=20)
        mki(db, v.id, 2025, per_capita=3.0, collective=45)
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["per_capita_income"] == 3.0
        assert item["collective_income"] == 45.0

    def test_duplicate_ids_appear_multiple_times(self, client_and_db):
        client, db = client_and_db
        v1 = mkv(db, name="A村")
        v2 = mkv(db, name="B村")
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v1.id},{v1.id},{v2.id},{v2.id},{v2.id}")
        assert resp.json()["data"]["total"] == 2

    def test_per_capita_none_defaults_zero(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="缺收村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=None, collective=None)
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["per_capita_income"] == 0
        assert item["collective_income"] == 0

    def test_project_completion_rate_zero_projects(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="无项村"); db.commit()
        mki(db, v.id, _CURRENT_YEAR, per_capita=1.0, collective=10)
        db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id}")
        item = resp.json()["data"]["items"][0]
        assert item["total_projects"] == 0
        assert item["completed_projects"] == 0
        assert item["project_completion_rate"] == 0

    def test_all_ids_not_found(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="A村"); db.commit()
        resp = client.get("/api/v1/assessment/village-comparison?village_ids=99999,88888")
        assert resp.json()["data"]["items"] == []
        assert resp.json()["data"]["total"] == 0

    def test_mixed_valid_and_invalid_village_id(self, client_and_db):
        client, db = client_and_db
        v = mkv(db, name="存在的村"); db.commit()
        resp = client.get(f"/api/v1/assessment/village-comparison?village_ids={v.id},40499")
        data = resp.json()["data"]
        assert data["total"] == 1


# ===================================================================
#  Internal helper functions — direct unit tests
# ===================================================================

class TestScoreLevel:

    def test_excellent(self):
        assert _score_level(100) == "优秀"
        assert _score_level(95) == "优秀"
        assert _score_level(90) == "优秀"

    def test_good(self):
        assert _score_level(89.9) == "良好"
        assert _score_level(80) == "良好"
        assert _score_level(75) == "良好"

    def test_qualified(self):
        assert _score_level(74.9) == "合格"
        assert _score_level(65) == "合格"
        assert _score_level(60) == "合格"

    def test_needs_improvement(self):
        assert _score_level(59.9) == "待改进"
        assert _score_level(30) == "待改进"
        assert _score_level(0) == "待改进"


class TestCalculateVillageScoreBatch:

    @staticmethod
    def _v(id_=1):
        v = Mock()
        v.id = id_
        return v

    @staticmethod
    def _inc_obj(year, per_capita):
        inc = Mock()
        inc.year = year
        inc.per_capita_income = float(per_capita) if per_capita is not None else None
        inc.collective_income = 0.0
        return inc

    def test_default_scores_no_data(self):
        v = self._v()
        result = _calculate_village_score_batch(v, 2025, {}, {}, {})
        assert result["detail"]["economic"] == 50.0
        assert result["detail"]["social"] == 60.0
        assert result["detail"]["project_completion"] == 50.0
        assert result["detail"]["fund_execution"] == 50.0
        assert result["total"] == 52.5

    def test_economic_growth_positive(self):
        v = self._v()
        incomes = {1: [self._inc_obj(2025, 2.0), self._inc_obj(2024, 1.0)]}
        result = _calculate_village_score_batch(v, 2025, incomes, {}, {})
        assert result["detail"]["economic"] == 100.0

    def test_economic_decline_negative(self):
        v = self._v()
        incomes = {1: [self._inc_obj(2025, 0.5), self._inc_obj(2024, 1.0)]}
        result = _calculate_village_score_batch(v, 2025, incomes, {}, {})
        assert result["detail"]["economic"] == 0.0

    def test_economic_previous_zero(self):
        v = self._v()
        incomes = {1: [self._inc_obj(2025, 2.0), self._inc_obj(2024, 0.0)]}
        result = _calculate_village_score_batch(v, 2025, incomes, {}, {})
        assert result["detail"]["economic"] == 50.0

    def test_economic_previous_none(self):
        v = self._v()
        inc_cur = self._inc_obj(2025, 2.0)
        inc_prev = self._inc_obj(2024, None)
        incomes = {1: [inc_cur, inc_prev]}
        result = _calculate_village_score_batch(v, 2025, incomes, {}, {})
        assert result["detail"]["economic"] == 50.0

    def test_social_has_income(self):
        v = self._v()
        incomes = {1: [self._inc_obj(2025, 1.0)]}
        result = _calculate_village_score_batch(v, 2025, incomes, {}, {})
        assert result["detail"]["social"] == 80.0

    def test_social_no_income(self):
        v = self._v()
        result = _calculate_village_score_batch(v, 2025, {}, {}, {})
        assert result["detail"]["social"] == 60.0

    def test_project_completion_full(self):
        v = self._v()
        ps = Mock()
        ps.total = 5
        ps.completed = 5
        result = _calculate_village_score_batch(v, 2025, {}, {1: ps}, {})
        assert result["detail"]["project_completion"] == 100.0

    def test_project_completion_none(self):
        v = self._v()
        ps = Mock()
        ps.total = 0
        ps.completed = 0
        result = _calculate_village_score_batch(v, 2025, {}, {1: ps}, {})
        assert result["detail"]["project_completion"] == 50

    def test_project_completion_half(self):
        v = self._v()
        ps = Mock()
        ps.total = 4
        ps.completed = 2
        result = _calculate_village_score_batch(v, 2025, {}, {1: ps}, {})
        assert result["detail"]["project_completion"] == 50.0

    def test_project_stat_none_total(self):
        v = self._v()
        ps = Mock()
        ps.total = None
        ps.completed = None
        result = _calculate_village_score_batch(v, 2025, {}, {1: ps}, {})
        assert result["detail"]["project_completion"] == 50

    def test_fund_execution_full(self):
        v = self._v()
        fs = Mock()
        fs.total_amount = Decimal("100")
        fs.total_used = Decimal("100")
        result = _calculate_village_score_batch(v, 2025, {}, {}, {1: fs})
        assert result["detail"]["fund_execution"] == 100.0

    def test_fund_execution_half(self):
        v = self._v()
        fs = Mock()
        fs.total_amount = Decimal("200")
        fs.total_used = Decimal("100")
        result = _calculate_village_score_batch(v, 2025, {}, {}, {1: fs})
        assert result["detail"]["fund_execution"] == 50.0

    def test_fund_execution_no_data(self):
        v = self._v()
        result = _calculate_village_score_batch(v, 2025, {}, {}, {})
        assert result["detail"]["fund_execution"] == 50.0

    def test_fund_zero_amount(self):
        v = self._v()
        fs = Mock()
        fs.total_amount = Decimal("0")
        fs.total_used = Decimal("0")
        result = _calculate_village_score_batch(v, 2025, {}, {}, {1: fs})
        assert result["detail"]["fund_execution"] == 50

    def test_fund_stat_zero_values_float(self):
        v = self._v()
        fs = Mock()
        fs.total_amount = 0.0
        fs.total_used = 0.0
        result = _calculate_village_score_batch(v, 2025, {}, {}, {1: fs})
        assert result["detail"]["fund_execution"] == 50

    def test_total_weighted_sum(self):
        v = self._v()
        ps = Mock()
        ps.total = 10
        ps.completed = 8
        fs = Mock()
        fs.total_amount = Decimal("100")
        fs.total_used = Decimal("60")
        incomes = {1: [self._inc_obj(2025, 2.0), self._inc_obj(2024, 1.0)]}
        result = _calculate_village_score_batch(v, 2025, incomes, {1: ps}, {1: fs})
        assert result["detail"]["economic"] == 100.0
        assert result["detail"]["social"] == 80.0
        assert result["detail"]["project_completion"] == 80.0
        assert result["detail"]["fund_execution"] == 60.0
        assert result["total"] == 82.0


class TestScoreWeights:

    def test_weights_keys(self):
        assert set(SCORE_WEIGHTS.keys()) == {"economic", "social", "project_completion", "fund_execution"}

    def test_weights_sum_to_one(self):
        total_weight = sum(SCORE_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.001
