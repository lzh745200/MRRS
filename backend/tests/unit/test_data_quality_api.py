import pytest
from unittest.mock import Mock, patch
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


class TestGetDataQualityReport:
    def test_success(self, client):
        from app.models.supported_village import SupportedVillage, VillagePopulation, VillageIncome

        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        sv1 = SupportedVillage(village_name="村1", county="县A", province="省X")
        sv2 = SupportedVillage(village_name="村2", county="县A", province="省X")
        db.add_all([sv1, sv2])
        db.flush()

        db.add(VillagePopulation(supported_village_id=sv1.id, year=datetime.now().year, total_population=100))
        db.add(VillagePopulation(supported_village_id=sv2.id, year=datetime.now().year, total_population=200))
        db.add(VillageIncome(supported_village_id=sv1.id, year=datetime.now().year, per_capita_income=5000.0))
        db.add(VillageIncome(supported_village_id=sv2.id, year=datetime.now().year, per_capita_income=6000.0))
        db.add(VillageIncome(supported_village_id=sv1.id, year=datetime.now().year - 1, per_capita_income=3000.0))
        db.commit()

        resp = client.get("/api/v1/data-quality/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "null_rate_report" in data
        assert "income_anomalies" in data
        assert "filing_progress" in data
        assert data["null_rate_report"]["total_villages"] == 2

    def test_exception(self, client):
        from app.core.database import get_db

        mock_db = Mock()
        mock_db.query.side_effect = RuntimeError("db error")
        original_override = client.app.dependency_overrides.get(get_db)
        client.app.dependency_overrides[get_db] = lambda: mock_db
        try:
            resp = client.get("/api/v1/data-quality/report")
            assert resp.status_code == 200
            data = resp.json()
            assert "error" in data
            assert data["null_rate_report"] == {}
            assert data["income_anomalies"] == []
            assert data["filing_progress"] == {}
        finally:
            if original_override:
                client.app.dependency_overrides[get_db] = original_override
            else:
                del client.app.dependency_overrides[get_db]


class TestRunFullCheck:
    def test_no_issues(self, client):
        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 100
        assert data["total_issues"] == 0

    def test_with_all_issue_types(self, client):
        from app.models.supported_village import SupportedVillage
        from app.models.project import Project
        from app.models.fund import Fund
        from app.models.school import School

        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        db.add(SupportedVillage(village_name="", county="县A"))
        db.add(SupportedVillage(village_name="村1", county=None))
        db.add(Project(name="", status="active"))
        db.add(Fund(amount=-100))
        db.add(Fund(amount=-200))
        db.add(School(name="学校1"))
        db.add(School(name="学校1"))
        db.add(Project(name="重复项目", status="active"))
        db.add(Project(name="重复项目", status="active"))
        db.add(Project(name="重复项目", status="active"))
        db.flush()
        db.commit()

        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_issues"] >= 4
        assert data["score"] < 100

    def test_null_field_skipped_when_column_missing(self, client):
        """Cover `if col is None: continue` branch"""
        from app.models.supported_village import SupportedVillage

        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        db.add(SupportedVillage(village_name="test"))
        db.commit()

        with patch("app.api.v1.data.data.data_quality.getattr", side_effect=lambda obj, name, *a: None):
            resp = client.post("/api/v1/data-quality/full-check")
            assert resp.status_code == 200
            assert resp.json()["total_issues"] >= 0

    def test_dup_villages_none_names(self, client):
        """Cover `', '.join(d[0] or '' for d in dup_villages[:5])` when name is None"""
        from app.models.supported_village import SupportedVillage

        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        db.add(SupportedVillage(village_name="dup"))
        db.add(SupportedVillage(village_name="dup"))
        db.commit()

        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200
        data = resp.json()
        assert any(i["check"] == "duplicate" for i in data["issues"])

    def test_no_orphan_projects(self, client):
        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200

    def test_orphan_project_village(self, client):
        from app.models.project import Project
        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        db.add(Project(name="orphan", status="active", village_id=9999))
        db.commit()
        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200
        data = resp.json()
        assert any(i["check"] == "referential_integrity" and i["table"] == "projects" for i in data["issues"])

    def test_orphan_fund_project(self, client):
        from app.models.fund import Fund
        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        db.add(Fund(amount=100, project_id=9999))
        db.commit()
        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200
        data = resp.json()
        assert any(i["check"] == "referential_integrity" and i["table"] == "funds" for i in data["issues"])

    def test_negative_budget(self, client):
        from app.models.project import Project
        db = client.app.dependency_overrides[list(client.app.dependency_overrides.keys())[0]]()
        db.add(Project(name="neg_budget", status="active", budget=-1))
        db.commit()
        resp = client.post("/api/v1/data-quality/full-check")
        assert resp.status_code == 200
        data = resp.json()
        assert any(i["check"] == "value_range" and i["field"] == "budget" for i in data["issues"])


class TestCalcNullRates:
    def test_basic(self):
        from app.api.v1.data.data.data_quality import _calc_null_rates
        mock_db = Mock()

        mock_villages_q = Mock()
        mock_villages_q.all.return_value = [(1, "村1", "县A")]
        mock_villages_q2 = Mock()
        mock_villages_q2.all.return_value = [(1, 2023)]
        mock_villages_q3 = Mock()
        mock_villages_q3.all.return_value = [(1, 2023)]

        def query_side(*args):
            first = args[0]
            if 'SupportedVillage' in str(first):
                return mock_villages_q
            if 'VillagePopulation' in str(first):
                return mock_villages_q2
            if 'VillageIncome' in str(first):
                return mock_villages_q3
            return Mock()

        mock_db.query = query_side
        result = _calc_null_rates(mock_db)
        assert result["total_villages"] == 1
        assert len(result["expected_years"]) > 0

    def test_no_villages(self):
        from app.api.v1.data.data.data_quality import _calc_null_rates
        mock_db = Mock()
        mock_q = Mock()
        mock_q.all.return_value = []
        mock_db.query.return_value = mock_q
        result = _calc_null_rates(mock_db)
        assert result["total_villages"] == 0
        assert result["population_fill_rate"] == 0
        assert result["income_fill_rate"] == 0


class TestDetectIncomeAnomalies:
    def _setup_mock_db(self, income_rows, name_rows):
        mock_db = Mock()
        call_count = [0]

        def query_side(*args):
            call_count[0] += 1
            q = Mock()
            if call_count[0] == 1:
                q.order_by.return_value.all.return_value = income_rows
            else:
                q.all.return_value = name_rows
            return q

        mock_db.query = query_side
        return mock_db

    def test_no_anomalies(self):
        from app.api.v1.data.data.data_quality import _detect_income_anomalies
        mock_db = self._setup_mock_db(
            [(1, 2022, 5000.0), (1, 2023, 5200.0)],
            [(1, "村1")]
        )
        result = _detect_income_anomalies(mock_db)
        assert result == []

    def test_high_anomaly(self):
        from app.api.v1.data.data.data_quality import _detect_income_anomalies
        mock_db = self._setup_mock_db(
            [(1, 2022, 1000.0), (1, 2023, 3000.0)],
            [(1, "村1")]
        )
        result = _detect_income_anomalies(mock_db)
        assert len(result) == 1
        assert result[0]["severity"] == "high"

    def test_medium_anomaly(self):
        from app.api.v1.data.data.data_quality import _detect_income_anomalies
        mock_db = self._setup_mock_db(
            [(1, 2022, 1000.0), (1, 2023, 1600.0)],
            [(1, "村1")]
        )
        result = _detect_income_anomalies(mock_db)
        assert len(result) == 1
        assert result[0]["severity"] == "medium"

    def test_prev_val_zero(self):
        from app.api.v1.data.data.data_quality import _detect_income_anomalies
        mock_db = self._setup_mock_db(
            [(1, 2022, 0.0), (1, 2023, 5000.0)],
            [(1, "村1")]
        )
        result = _detect_income_anomalies(mock_db)
        assert result == []

    def test_empty_rows(self):
        from app.api.v1.data.data.data_quality import _detect_income_anomalies
        mock_db = self._setup_mock_db([], [])
        result = _detect_income_anomalies(mock_db)
        assert result == []


class TestCalcFilingProgress:
    def test_basic(self):
        from app.api.v1.data.data.data_quality import _calc_filing_progress
        mock_db = Mock()

        mock_counties = Mock()
        mock_counties.all.return_value = [("县A", 2)]
        mock_db.query.return_value.group_by.return_value.all.return_value = [("县A", 2)]

        mock_filled = Mock()
        mock_filled.all.return_value = [("县A", datetime.now().year, 1)]
        mock_db.query.return_value.join.return_value.group_by.return_value.all.return_value = [("县A", datetime.now().year, 1)]

        result = _calc_filing_progress(mock_db)
        assert "expected_years" in result
        assert "matrix" in result
        assert len(result["matrix"]) == 1
        assert result["matrix"][0]["county"] == "县A"

    def test_county_none(self):
        from app.api.v1.data.data.data_quality import _calc_filing_progress
        mock_db = Mock()
        mock_db.query.return_value.group_by.return_value.all.return_value = [(None, 1)]
        mock_db.query.return_value.join.return_value.group_by.return_value.all.return_value = []
        result = _calc_filing_progress(mock_db)
        assert result["matrix"][0]["county"] == "未知"


class TestNullRateEdgeCases:
    def test_population_filled_rate_zero_villages(self):
        from app.api.v1.data.data.data_quality import _calc_null_rates
        mock_db = Mock()
        mock_q = Mock()
        mock_q.all.return_value = []
        mock_db.query.return_value = mock_q
        result = _calc_null_rates(mock_db)
        assert result["population_fill_rate"] == 0
        assert result["income_fill_rate"] == 0

    def test_village_with_no_county(self):
        from app.api.v1.data.data.data_quality import _calc_null_rates
        mock_db = Mock()
        mock_q = Mock()
        mock_q.all.return_value = [(1, "test", None)]
        mock_q2 = Mock()
        mock_q2.all.return_value = []
        mock_q3 = Mock()
        mock_q3.all.return_value = []

        def query_side(*args):
            first = args[0]
            if 'SupportedVillage' in str(first):
                return mock_q
            if 'VillagePopulation' in str(first):
                return mock_q2
            if 'VillageIncome' in str(first):
                return mock_q3
            return Mock()
        mock_db.query = query_side
        result = _calc_null_rates(mock_db)
        assert result["villages"][0]["county"] == "未知"
