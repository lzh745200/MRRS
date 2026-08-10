import pytest
from unittest.mock import Mock, patch, AsyncMock, ANY
from datetime import datetime
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_settings():
    import os
    os.environ["SECRET_KEY"] = "test-secret-key-32-chars-long!!!!!"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    os.environ["CSRF_ENABLED"] = "false"
    from app.core.config import settings
    settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
    settings.ENVIRONMENT = "testing"
    settings.DEBUG = True
    settings.DATABASE_URL = "sqlite:///./test.db"
    settings.CSRF_ENABLED = False
    yield
    for k in ["SECRET_KEY", "ENVIRONMENT", "DEBUG", "DATABASE_URL", "CSRF_ENABLED"]:
        os.environ.pop(k, None)


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

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db

    _mock_user = Mock(id=1, username="admin", role="admin", is_superuser=True, is_active=True,
                      permissions_list=["*"], organization_id=1, email="admin@test.com")
    app.dependency_overrides[get_current_user] = lambda: _mock_user

    yield TestClient(app, raise_server_exceptions=False), db

    app.dependency_overrides = _original_overrides
    db.close()
    engine.dispose()


class TestExportExcel:
    def test_success(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_report_service
        # ReportService.export_to_excel / get_export_filename 均为 async def，
        # 测试需用 AsyncMock 反映真实异步契约（路由层 await 这些调用）。
        mock_svc = Mock()
        mock_svc.export_to_excel = AsyncMock(return_value=b"excel content")
        mock_svc.get_export_filename = AsyncMock(return_value="report_2024.xlsx")
        test_client.app.dependency_overrides[get_report_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/export/excel", json={"year": 2024})
        assert resp.status_code == 200
        assert resp.content == b"excel content"

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_report_service
        mock_svc = Mock()
        mock_svc.export_to_excel = AsyncMock(side_effect=RuntimeError("excel error"))
        mock_svc.get_export_filename = AsyncMock(return_value="report.xlsx")
        test_client.app.dependency_overrides[get_report_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/export/excel", json={"year": 2024})
        assert resp.status_code == 500


class TestExportPdf:
    def _setup(self, test_client):
        from app.api.v1.data.data.reports import get_report_service
        mock_svc = Mock()
        mock_svc.get_export_filename = AsyncMock(return_value="report_2024.pdf")
        test_client.app.dependency_overrides[get_report_service] = lambda: mock_svc
        return mock_svc

    def test_success(self, client):
        test_client, db = client
        mock_svc = self._setup(test_client)
        mock_svc.export_to_pdf = AsyncMock(return_value=b"pdf content")

        resp = test_client.post("/api/v1/reports/export/pdf", json={"year": 2024})
        assert resp.status_code == 200
        assert resp.content == b"pdf content"

    def test_import_error(self, client):
        test_client, db = client
        mock_svc = self._setup(test_client)
        mock_svc.export_to_pdf = AsyncMock(side_effect=ImportError("no reportlab"))

        resp = test_client.post("/api/v1/reports/export/pdf", json={"year": 2024})
        assert resp.status_code == 501

    def test_value_error(self, client):
        test_client, db = client
        mock_svc = self._setup(test_client)
        mock_svc.export_to_pdf = AsyncMock(side_effect=ValueError("invalid params"))

        resp = test_client.post("/api/v1/reports/export/pdf", json={"year": 2024})
        assert resp.status_code == 400

    def test_generic_exception(self, client):
        test_client, db = client
        mock_svc = self._setup(test_client)
        mock_svc.export_to_pdf = AsyncMock(side_effect=RuntimeError("generic fail"))

        resp = test_client.post("/api/v1/reports/export/pdf", json={"year": 2024})
        assert resp.status_code == 500


class TestExportComprehensiveReport:
    def test_without_village_ids(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_report_service
        # export_comprehensive_report 为 async def，需 AsyncMock。
        mock_svc = Mock()
        mock_svc.export_comprehensive_report = AsyncMock(return_value=b"comprehensive")
        test_client.app.dependency_overrides[get_report_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/export/comprehensive/2024")
        assert resp.status_code == 200
        assert resp.content == b"comprehensive"
        mock_svc.export_comprehensive_report.assert_called_once_with(2024, None, user=ANY)

    def test_with_village_ids(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_report_service
        mock_svc = Mock()
        mock_svc.export_comprehensive_report = AsyncMock(return_value=b"filtered")
        test_client.app.dependency_overrides[get_report_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/export/comprehensive/2024?village_ids=1,2,3")
        assert resp.status_code == 200
        mock_svc.export_comprehensive_report.assert_called_once_with(2024, [1, 2, 3], user=ANY)

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_report_service
        mock_svc = Mock()
        mock_svc.export_comprehensive_report = AsyncMock(side_effect=RuntimeError("fail"))
        test_client.app.dependency_overrides[get_report_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/export/comprehensive/2024")
        assert resp.status_code == 500


class TestGetFilterOptions:
    def test_success(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.get_filter_options.return_value = {"provinces": ["省X"], "tiers": ["1"], "departments": []}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/filter-options")
        assert resp.status_code == 200
        assert resp.json() == {"provinces": ["省X"], "tiers": ["1"], "departments": []}

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.get_filter_options.side_effect = RuntimeError("filter fail")
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/filter-options")
        assert resp.status_code == 500


class TestFilterVillages:
    def test_success(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_village = Mock(
            id=1, sequence_no=1, department="Dept", support_unit="Unit",
            village_name="村1", region_scope="scope",
            is_three_regions=False, is_key_county=False, is_provincial_demo=False
        )
        mock_svc.filter_villages.return_value = ([mock_village], 1)
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/analytics/filter", json={"province": "省X"})
        assert resp.status_code == 200
        payload = resp.json()
        data = payload["data"]
        assert data["total"] == 1
        assert data["page"] == 1
        # ok_list 的 pages 作为 extra kwarg 透传，位于信封顶层而非 data 内
        assert payload["pages"] == 1
        assert len(data["items"]) == 1

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.filter_villages.side_effect = RuntimeError("filter fail")
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/analytics/filter", json={"province": "省X"})
        assert resp.status_code == 500


class TestDrillDown:
    def test_success(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.drill_down.return_value = {"items": [], "total": 0}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/analytics/drill-down", json={"dimension": "province", "value": "省X"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.drill_down.side_effect = RuntimeError("drill fail")
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/analytics/drill-down", json={"dimension": "province", "value": "省X"})
        assert resp.status_code == 500


class TestCompareVillages:
    def test_success(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.compare_villages.return_value = {"villages": [], "year": 2024}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/analytics/compare-villages?year=2024", json={"village_ids": [1, 2, 3]})
        assert resp.status_code == 200
        assert resp.json()["year"] == 2024

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.compare_villages.side_effect = RuntimeError("compare fail")
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.post("/api/v1/reports/analytics/compare-villages?year=2024", json={"village_ids": [1, 2, 3]})
        assert resp.status_code == 500


class TestCompareYears:
    def test_success_with_metrics(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.compare_years.return_value = {"data": [1, 2]}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/compare-years/1?years=2022,2023&metrics=income,population")
        assert resp.status_code == 200

    def test_success_without_metrics(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.compare_years.return_value = {"data": []}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/compare-years/1?years=2022,2023")
        assert resp.status_code == 200

    def test_value_error_in_years(self, client):
        test_client, db = client
        resp = test_client.get("/api/v1/reports/analytics/compare-years/1?years=abc")
        assert resp.status_code == 400

    def test_generic_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.compare_years.side_effect = RuntimeError("years fail")
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/compare-years/1?years=2022,2023")
        assert resp.status_code == 500


class TestGetSummaryStatistics:
    def test_success_with_all_filters(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.get_summary_statistics.return_value = {"year": 2024}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/summary?year=2024&department=DeptA&is_three_regions=true&is_key_county=true")
        assert resp.status_code == 200

    def test_success_without_filters(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.get_summary_statistics.return_value = {"year": 2024}
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/summary")
        assert resp.status_code == 200

    def test_exception(self, client):
        test_client, db = client
        from app.api.v1.data.data.reports import get_analytics_service
        mock_svc = Mock()
        mock_svc.get_summary_statistics.side_effect = RuntimeError("summary fail")
        test_client.app.dependency_overrides[get_analytics_service] = lambda: mock_svc

        resp = test_client.get("/api/v1/reports/analytics/summary")
        assert resp.status_code == 500


class TestCreateSubscription:
    @patch("app.api.v1.data.data.reports._subscription_to_response")
    def test_success(self, mock_to_resp, client):
        test_client, db = client
        mock_to_resp.return_value = {
            "id": 1, "user_id": 1, "name": "月度报表", "report_type": "comprehensive",
            "format": "xlsx", "frequency": "monthly", "is_active": True, "created_at": None,
        }

        resp = test_client.post("/api/v1/reports/subscriptions", json={
            "name": "月度报表", "report_type": "comprehensive", "format": "xlsx",
            "frequency": "monthly", "village_ids": [1, 2], "include_sections": ["funding", "projects"]
        })
        assert resp.status_code == 200
        assert resp.json()["id"] > 0
        assert resp.json()["name"] == "月度报表"
        assert resp.json()["report_type"] == "comprehensive"

    @patch("app.api.v1.data.data.reports._subscription_to_response")
    def test_success_without_optional_fields(self, mock_to_resp, client):
        test_client, db = client
        mock_to_resp.return_value = {
            "id": 2, "user_id": 1, "name": "周报", "report_type": "comprehensive",
            "format": "xlsx", "frequency": "weekly", "is_active": True, "created_at": None,
        }

        resp = test_client.post("/api/v1/reports/subscriptions", json={
            "name": "周报", "report_type": "comprehensive", "format": "xlsx",
            "frequency": "weekly"
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "周报"
        assert resp.json()["frequency"] == "weekly"

    def test_exception(self, client):
        test_client, db = client
        from app.core.database import get_db
        mock_db = Mock()
        mock_db.add.side_effect = RuntimeError("db error")
        test_client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = test_client.post("/api/v1/reports/subscriptions", json={
                "name": "月度报表", "report_type": "comprehensive", "format": "xlsx",
                "frequency": "monthly"
            })
            assert resp.status_code == 500
        finally:
            test_client.app.dependency_overrides[get_db] = lambda: db


class TestListSubscriptions:
    def _make_sub(self, db, **kw):
        from app.models.supported_village import ReportSubscription
        sub = ReportSubscription(**kw)
        sub.last_sent_at = None
        sub.next_send_at = None
        return sub

    def test_success_without_filter(self, client):
        test_client, db = client
        s1 = self._make_sub(db, user_id=1, name="sub1", report_type="comprehensive", frequency="weekly")
        s2 = self._make_sub(db, user_id=1, name="sub2", report_type="fund_summary", frequency="monthly", is_active=False)
        db.add_all([s1, s2])
        db.commit()

        resp = test_client.get("/api/v1/reports/subscriptions")
        assert resp.status_code == 200
        # ok_list 信封格式：{code, data: {items, total, page, ...}, message}
        assert resp.json()["data"]["total"] == 2
        assert resp.json()["data"]["page"] == 1

    def test_success_with_active_filter(self, client):
        test_client, db = client
        s1 = self._make_sub(db, user_id=1, name="sub1", report_type="comprehensive", frequency="weekly")
        s2 = self._make_sub(db, user_id=1, name="sub2", report_type="fund_summary", frequency="monthly", is_active=False)
        db.add_all([s1, s2])
        db.commit()

        resp = test_client.get("/api/v1/reports/subscriptions?is_active=true")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_exception(self, client):
        test_client, db = client
        from app.core.database import get_db
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("db error")
        test_client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = test_client.get("/api/v1/reports/subscriptions")
            assert resp.status_code == 500
        finally:
            test_client.app.dependency_overrides[get_db] = lambda: db


class TestGetSubscription:
    def _make_sub(self, db, **kw):
        from app.models.supported_village import ReportSubscription
        sub = ReportSubscription(**kw)
        sub.last_sent_at = None
        sub.next_send_at = None
        return sub

    def test_found(self, client):
        test_client, db = client
        sub = self._make_sub(db, user_id=1, name="my sub", report_type="comprehensive", frequency="weekly")
        db.add(sub)
        db.commit()

        resp = test_client.get(f"/api/v1/reports/subscriptions/{sub.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "my sub"

    def test_not_found(self, client):
        test_client, db = client
        resp = test_client.get("/api/v1/reports/subscriptions/9999")
        assert resp.status_code == 404

    def test_exception(self, client):
        test_client, db = client
        from app.core.database import get_db
        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("db error")
        test_client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = test_client.get("/api/v1/reports/subscriptions/1")
            assert resp.status_code == 500
        finally:
            test_client.app.dependency_overrides[get_db] = lambda: db


class TestUpdateSubscription:
    def _make_sub(self, db, **kw):
        from app.models.supported_village import ReportSubscription
        sub = ReportSubscription(**kw)
        sub.last_sent_at = None
        sub.next_send_at = None
        return sub

    def test_update_all_fields(self, client):
        test_client, db = client
        sub = self._make_sub(db, user_id=1, name="old", report_type="comprehensive",
                             frequency="weekly", village_ids="[]", include_sections="[]")
        db.add(sub)
        db.commit()

        resp = test_client.put(f"/api/v1/reports/subscriptions/{sub.id}", json={
            "name": "new name", "frequency": "monthly",
            "village_ids": [1, 2], "include_sections": ["funding"]
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "new name"

    def test_update_village_ids_none(self, client):
        test_client, db = client
        sub = self._make_sub(db, user_id=1, name="old", report_type="comprehensive",
                             frequency="weekly", village_ids="[]")
        db.add(sub)
        db.commit()

        resp = test_client.put(f"/api/v1/reports/subscriptions/{sub.id}", json={
            "village_ids": None, "include_sections": None
        })
        assert resp.status_code == 200

    def test_not_found(self, client):
        test_client, db = client
        resp = test_client.put("/api/v1/reports/subscriptions/9999", json={"name": "new"})
        assert resp.status_code == 404

    def test_exception(self, client):
        test_client, db = client
        from app.core.database import get_db
        mock_db = Mock()
        mock_q = Mock()
        mock_q.filter.return_value.first.side_effect = RuntimeError("db error")
        mock_db.query.return_value = mock_q
        test_client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = test_client.put("/api/v1/reports/subscriptions/1", json={"name": "new"})
            assert resp.status_code == 500
        finally:
            test_client.app.dependency_overrides[get_db] = lambda: db


class TestDeleteSubscription:
    def test_success(self, client):
        test_client, db = client
        from app.models.supported_village import ReportSubscription
        sub = ReportSubscription(user_id=1, name="to delete", report_type="comprehensive", frequency="weekly")
        sub.last_sent_at = None
        sub.next_send_at = None
        db.add(sub)
        db.commit()
        sub_id = sub.id

        resp = test_client.delete(f"/api/v1/reports/subscriptions/{sub_id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "订阅已删除"

    def test_not_found(self, client):
        test_client, db = client
        resp = test_client.delete("/api/v1/reports/subscriptions/9999")
        assert resp.status_code == 404

    def test_exception(self, client):
        test_client, db = client
        from app.core.database import get_db
        mock_db = Mock()
        mock_q = Mock()
        mock_q.filter.return_value.first.side_effect = RuntimeError("db error")
        mock_db.query.return_value = mock_q
        test_client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = test_client.delete("/api/v1/reports/subscriptions/1")
            assert resp.status_code == 500
        finally:
            test_client.app.dependency_overrides[get_db] = lambda: db


class TestToggleSubscription:
    def _make_sub(self, db, **kw):
        from app.models.supported_village import ReportSubscription
        sub = ReportSubscription(**kw)
        sub.last_sent_at = None
        sub.next_send_at = None
        return sub

    def test_toggle_on_to_off(self, client):
        test_client, db = client
        sub = self._make_sub(db, user_id=1, name="toggle", report_type="comprehensive", frequency="weekly", is_active=True)
        db.add(sub)
        db.commit()
        sub_id = sub.id

        resp = test_client.post(f"/api/v1/reports/subscriptions/{sub_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False
        assert resp.json()["data"]["message"] == "订阅已禁用"

    def test_toggle_off_to_on(self, client):
        test_client, db = client
        sub = self._make_sub(db, user_id=1, name="toggle", report_type="comprehensive", frequency="weekly", is_active=False)
        db.add(sub)
        db.commit()
        sub_id = sub.id

        resp = test_client.post(f"/api/v1/reports/subscriptions/{sub_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is True
        assert resp.json()["data"]["message"] == "订阅已启用"

    def test_not_found(self, client):
        test_client, db = client
        resp = test_client.post("/api/v1/reports/subscriptions/9999/toggle")
        assert resp.status_code == 404

    def test_exception(self, client):
        test_client, db = client
        from app.core.database import get_db
        mock_db = Mock()
        mock_q = Mock()
        mock_q.filter.return_value.first.side_effect = RuntimeError("db error")
        mock_db.query.return_value = mock_q
        test_client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = test_client.post("/api/v1/reports/subscriptions/1/toggle")
            assert resp.status_code == 500
        finally:
            test_client.app.dependency_overrides[get_db] = lambda: db


class TestSubscriptionToResponse:
    def test_with_all_fields(self):
        from app.api.v1.data.data.reports import _subscription_to_response
        sub = Mock(spec=[
            "id", "user_id", "name", "report_type", "format", "year",
            "village_ids", "include_sections", "frequency", "send_day",
            "send_time", "email", "output_dir", "output_format", "is_active",
            "last_sent_at", "next_send_at", "created_at", "updated_at"
        ])
        sub.id = 1
        sub.user_id = 1
        sub.name = "test"
        sub.report_type = "comprehensive"
        sub.format = "xlsx"
        sub.year = 2024
        sub.village_ids = "[1, 2]"
        sub.include_sections = '["funding"]'
        sub.frequency = "weekly"
        sub.send_day = 1
        sub.send_time = "09:00"
        sub.email = "test@test.com"
        sub.output_dir = "/tmp/reports"
        sub.output_format = "xlsx"
        sub.is_active = True
        sub.last_sent_at = None
        sub.next_send_at = None
        sub.created_at = datetime(2024, 1, 1)
        sub.updated_at = datetime(2024, 1, 1)

        result = _subscription_to_response(sub)
        assert result["id"] == 1
        assert result["village_ids"] == [1, 2]
        assert result["include_sections"] == ["funding"]

    def test_with_none_fields(self):
        from app.api.v1.data.data.reports import _subscription_to_response
        sub = Mock(spec=[
            "id", "user_id", "name", "report_type", "format", "year",
            "village_ids", "include_sections", "frequency", "send_day",
            "send_time", "email", "output_dir", "output_format", "is_active",
            "last_sent_at", "next_send_at", "created_at", "updated_at"
        ])
        sub.id = 2
        sub.user_id = 1
        sub.name = "test2"
        sub.report_type = "fund_summary"
        sub.format = "xlsx"
        sub.year = None
        sub.village_ids = None
        sub.include_sections = None
        sub.frequency = "monthly"
        sub.send_day = None
        sub.send_time = None
        sub.email = None
        sub.output_dir = None
        sub.output_format = None
        sub.is_active = True
        sub.last_sent_at = None
        sub.next_sent_at = None
        sub.created_at = datetime(2024, 1, 1)
        sub.updated_at = datetime(2024, 1, 1)

        result = _subscription_to_response(sub)
        assert result["village_ids"] is None
        assert result["include_sections"] is None
