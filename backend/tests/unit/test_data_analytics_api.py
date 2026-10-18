import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

# W4-T6（2026-10-18）：删除本模块重复的 mock_settings fixture —— 与
# tests/conftest.py 的同名 autouse fixture 完全重复，且它会把 DATABASE_URL
# 强制回相对字面量（运行期现场解析会落到跨进程共享的 backend/test.db）。
# 统一走 conftest 的绝对路径版（TEST_DATABASE_URL）。


@pytest.fixture
def mock_current_user():
    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1
    return user


@pytest.fixture
def client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    original_db_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: db

    _mock_user = Mock(id=1, username="admin", role="admin", is_superuser=True, is_active=True,
                      permissions_list=["*"], organization_id=1)
    original_auth_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: _mock_user

    yield TestClient(app, raise_server_exceptions=False)

    if original_db_override:
        app.dependency_overrides[get_db] = original_db_override
    else:
        del app.dependency_overrides[get_db]
    if original_auth_override:
        app.dependency_overrides[get_current_user] = original_auth_override
    else:
        del app.dependency_overrides[get_current_user]
    db.close()
    engine.dispose()


class TestGetDashboard:
    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    def test_cached(self, mock_get_cached, client):
        mock_get_cached.return_value = {"cached": True}
        resp = client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["cached"] is True
        assert data["message"] == "仪表盘数据获取成功"

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.api.v1.data.data.analytics._set_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_dashboard_overview")
    def test_not_cached(self, mock_svc, mock_set, mock_get, client):
        mock_get.return_value = None
        mock_svc.return_value = {"total_villages": 10}
        resp = client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_villages"] == 10
        mock_set.assert_called_once()

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_dashboard_overview")
    def test_safe_api_exception(self, mock_svc, mock_get, client):
        mock_get.return_value = None
        mock_svc.side_effect = ValueError("DB error")
        resp = client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 500


class TestGetVillageAnalysis:
    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    def test_cached(self, mock_get, client):
        mock_get.return_value = {"village_data": True}
        resp = client.get("/api/v1/analytics/village-analysis")
        assert resp.status_code == 200
        assert resp.json()["data"]["village_data"] is True

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.api.v1.data.data.analytics._set_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_village_analysis")
    def test_not_cached(self, mock_svc, mock_set, mock_get, client):
        mock_get.return_value = None
        mock_svc.return_value = {"village_analysis": True}
        resp = client.get("/api/v1/analytics/village-analysis")
        assert resp.status_code == 200
        assert resp.json()["data"]["village_analysis"] is True
        mock_set.assert_called_once()

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_village_analysis")
    def test_safe_api_exception(self, mock_svc, mock_get, client):
        mock_get.return_value = None
        mock_svc.side_effect = RuntimeError("fail")
        resp = client.get("/api/v1/analytics/village-analysis")
        assert resp.status_code == 500


class TestGetFundingTrends:
    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    def test_cached(self, mock_get, client):
        mock_get.return_value = {"trends": []}
        resp = client.get("/api/v1/analytics/funding-trends?years=3")
        assert resp.status_code == 200
        assert resp.json()["data"]["trends"] == []

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.api.v1.data.data.analytics._set_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_funding_trends")
    def test_not_cached(self, mock_svc, mock_set, mock_get, client):
        mock_get.return_value = None
        mock_svc.return_value = {"trends": [{"year": 2024}]}
        resp = client.get("/api/v1/analytics/funding-trends")
        assert resp.status_code == 200
        assert resp.json()["data"]["trends"][0]["year"] == 2024

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_funding_trends")
    def test_safe_api_exception(self, mock_svc, mock_get, client):
        mock_get.return_value = None
        mock_svc.side_effect = RuntimeError("fail")
        resp = client.get("/api/v1/analytics/funding-trends")
        assert resp.status_code == 500


class TestGetPerformanceMetrics:
    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    def test_cached(self, mock_get, client):
        mock_get.return_value = {"metrics": True}
        resp = client.get("/api/v1/analytics/performance-metrics")
        assert resp.status_code == 200
        assert resp.json()["data"]["metrics"] is True

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.api.v1.data.data.analytics._set_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_performance_metrics")
    def test_not_cached(self, mock_svc, mock_set, mock_get, client):
        mock_get.return_value = None
        mock_svc.return_value = {"policies": {}}
        resp = client.get("/api/v1/analytics/performance-metrics")
        assert resp.status_code == 200

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.services.analytics_service.AnalyticsService.get_performance_metrics")
    def test_safe_api_exception(self, mock_svc, mock_get, client):
        mock_get.return_value = None
        mock_svc.side_effect = RuntimeError("fail")
        resp = client.get("/api/v1/analytics/performance-metrics")
        assert resp.status_code == 500


class TestGetComparisonAnalysis:
    @patch("app.services.analytics_service.AnalyticsService.get_comparison_analysis")
    def test_success(self, mock_svc, client):
        mock_svc.return_value = {"comparison": [], "compare_type": "province"}
        resp = client.post("/api/v1/analytics/comparison", json={"compare_type": "province"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.services.analytics_service.AnalyticsService.get_comparison_analysis")
    def test_safe_api_exception(self, mock_svc, client):
        mock_svc.side_effect = RuntimeError("fail")
        resp = client.post("/api/v1/analytics/comparison", json={"compare_type": "province"})
        assert resp.status_code == 500


class TestGenerateReport:
    @patch("app.services.analytics_service.AnalyticsService.generate_report_data")
    def test_success(self, mock_svc, client):
        mock_svc.return_value = {"report_type": "comprehensive"}
        resp = client.post("/api/v1/analytics/generate-report", json={"report_type": "comprehensive"})
        assert resp.status_code == 200

    @patch("app.services.analytics_service.AnalyticsService.generate_report_data")
    def test_safe_api_exception(self, mock_svc, client):
        mock_svc.side_effect = RuntimeError("fail")
        resp = client.post("/api/v1/analytics/generate-report", json={"report_type": "comprehensive"})
        assert resp.status_code == 500


class TestExportData:
    @patch("app.services.analytics_service.AnalyticsService.generate_report_data")
    def test_json_format(self, mock_gen, client):
        mock_gen.return_value = {"data": "test"}
        resp = client.post("/api/v1/analytics/export", json={"report_type": "json"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_gen.assert_called_once()

    @patch("app.services.analytics_service.AnalyticsService.generate_report_data")
    @patch("app.services.analytics_service.AnalyticsService.export_data")
    def test_excel_format(self, mock_export, mock_gen, client):
        mock_gen.return_value = {
            "dashboard": {"total_villages": 5},
            "performance": {"policies": {"total": 3}},
        }
        mock_export.return_value = b"fake excel bytes"
        resp = client.post("/api/v1/analytics/export", json={"report_type": "excel"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert resp.content == b"fake excel bytes"

    @patch("app.services.analytics_service.AnalyticsService.generate_report_data")
    def test_other_format(self, mock_gen, client):
        mock_gen.return_value = {"data": "custom"}
        resp = client.post("/api/v1/analytics/export", json={"report_type": "csv"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("app.services.analytics_service.AnalyticsService.generate_report_data")
    def test_safe_api_exception(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("fail")
        resp = client.post("/api/v1/analytics/export", json={"report_type": "json"})
        assert resp.status_code == 500


class TestGetRealtimeStats:
    @patch("app.services.analytics_service.AnalyticsService.get_dashboard_overview")
    def test_with_recent_updates(self, mock_svc, client):
        mock_svc.return_value = {"recent_updates": ["proj1", "proj2"]}
        resp = client.get("/api/v1/analytics/realtime-stats")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "overview" in data
        assert len(data["recent_activities"]) == 2
        assert "timestamp" in data

    @patch("app.services.analytics_service.AnalyticsService.get_dashboard_overview")
    def test_without_recent_updates(self, mock_svc, client):
        mock_svc.return_value = {"recent_updates": []}
        resp = client.get("/api/v1/analytics/realtime-stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["recent_activities"] == []

    @patch("app.services.analytics_service.AnalyticsService.get_dashboard_overview")
    def test_dashboard_none(self, mock_svc, client):
        mock_svc.return_value = None
        resp = client.get("/api/v1/analytics/realtime-stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["overview"] is None
        assert resp.json()["data"]["recent_activities"] == []

    @patch("app.services.analytics_service.AnalyticsService.get_dashboard_overview")
    def test_safe_api_exception(self, mock_svc, client):
        mock_svc.side_effect = RuntimeError("fail")
        resp = client.get("/api/v1/analytics/realtime-stats")
        assert resp.status_code == 500


class TestGetKpiSummary:
    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    def test_cached(self, mock_get, client):
        mock_get.return_value = {"total_villages": 10, "total_projects": 5}
        resp = client.get("/api/v1/analytics/kpi-summary?period=year")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_villages"] == 10

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.api.v1.data.data.analytics._set_cached", new_callable=AsyncMock)
    def test_not_cached_with_counts(self, mock_set, mock_get, client):
        mock_get.return_value = None
        from app.models.supported_village import SupportedVillage
        from app.models.project import Project

        sv = SupportedVillage(village_name="test", county="test_county")
        from app.core.database import get_db
        override_db = client.app.dependency_overrides[get_db]()
        override_db.add(sv)
        override_db.add(Project(name="p1", status="completed"))
        override_db.add(Project(name="p2", status="completed"))
        override_db.add(Project(name="p3", status="completed"))
        override_db.add(Project(name="p4", status="approved"))
        override_db.add(Project(name="p5", status="approved"))
        override_db.commit()

        resp = client.get("/api/v1/analytics/kpi-summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_villages"] == 1
        assert data["total_projects"] == 5
        assert data["completed_projects"] == 3
        assert data["approved_projects"] == 2

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    @patch("app.api.v1.data.data.analytics._set_cached", new_callable=AsyncMock)
    def test_nothing_found(self, mock_set, mock_get, client):
        mock_get.return_value = None
        resp = client.get("/api/v1/analytics/kpi-summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_projects"] == 0
        assert data["completion_rate"] == 0

    @patch("app.api.v1.data.data.analytics._get_cached", new_callable=AsyncMock)
    def test_safe_api_exception(self, mock_get, client):
        mock_get.return_value = None
        from app.core.database import get_db

        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("db fail")
        original_override = client.app.dependency_overrides.get(get_db)
        client.app.dependency_overrides[get_db] = lambda: mock_db

        try:
            resp = client.get("/api/v1/analytics/kpi-summary")
            assert resp.status_code == 500
        finally:
            if original_override:
                client.app.dependency_overrides[get_db] = original_override
            else:
                del client.app.dependency_overrides[get_db]


class TestGetAnalyticsHealth:
    def test_health(self, client):
        resp = client.get("/api/v1/analytics/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "healthy"


class TestCacheHelpers:
    @pytest.mark.asyncio
    async def test_get_cached_success(self):
        from app.api.v1.data.data.analytics import _get_cached
        from app.core.constants import ANALYTICS_CACHE_PREFIX
        mock_cache = AsyncMock()
        mock_cache.get.return_value = "value"
        with patch("app.api.v1.data.data.analytics.get_cache_service", new_callable=AsyncMock) as m:
            m.return_value = mock_cache
            result = await _get_cached("testkey")
            assert result == "value"
            mock_cache.get.assert_called_once_with(f"{ANALYTICS_CACHE_PREFIX}testkey")

    @pytest.mark.asyncio
    async def test_get_cached_exception(self):
        from app.api.v1.data.data.analytics import _get_cached
        with patch("app.api.v1.data.data.analytics.get_cache_service", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("cache down")
            result = await _get_cached("key")
            assert result is None

    @pytest.mark.asyncio
    async def test_set_cached_success(self):
        from app.api.v1.data.data.analytics import _set_cached
        from app.core.constants import ANALYTICS_CACHE_PREFIX
        mock_cache = AsyncMock()
        with patch("app.api.v1.data.data.analytics.get_cache_service", new_callable=AsyncMock) as m:
            m.return_value = mock_cache
            await _set_cached("testkey", {"data": 1})
            mock_cache.set.assert_called_once_with(f"{ANALYTICS_CACHE_PREFIX}testkey", {"data": 1}, 300)

    @pytest.mark.asyncio
    async def test_set_cached_exception(self):
        from app.api.v1.data.data.analytics import _set_cached
        with patch("app.api.v1.data.data.analytics.get_cache_service", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("cache down")
            await _set_cached("key", {"data": 1})
