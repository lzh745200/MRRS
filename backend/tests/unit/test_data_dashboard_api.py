"""Dashboard API unit tests — 100% coverage for app.api.v1.data.data.dashboard"""
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.data.data.dashboard import _get_cached, _set_cached, invalidate_dashboard_cache
from app.core.database import get_db
from app.core.security import get_current_user


@pytest.fixture
def admin_user():
    u = Mock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.name = "管理员"
    u.organization_id = 1
    return u


@pytest.fixture
def client(admin_user):
    from app.main import app
    app.dependency_overrides = {}

    async def mu():
        return admin_user

    def mock_get_db():
        return MagicMock()

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = mu
    app.dependency_overrides[get_db] = mock_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original_overrides


# ==================== Cache helper tests ====================

class TestCacheHelpers:
    @patch("app.api.v1.data.data.dashboard._cache", None)
    def test_get_cached_none(self):
        assert _get_cached("x") is None

    @patch("app.api.v1.data.data.dashboard._cache")
    def test_get_cached_ok(self, m):
        m.get.return_value = "v"; assert _get_cached("x") == "v"

    @patch("app.api.v1.data.data.dashboard._cache")
    def test_get_cached_exc(self, m):
        m.get.side_effect = Exception("x"); assert _get_cached("x") is None

    @patch("app.api.v1.data.data.dashboard._cache", None)
    def test_set_cached_none(self):
        _set_cached("x", "v")

    @patch("app.api.v1.data.data.dashboard._cache")
    def test_set_cached_ok(self, m):
        _set_cached("x", "v", 60); m.set.assert_called_once_with("x", "v", expire=60)

    @patch("app.api.v1.data.data.dashboard._cache")
    def test_set_cached_exc(self, m):
        m.set.side_effect = Exception("x"); _set_cached("x", "v")

    @patch("app.api.v1.data.data.dashboard._cache", None)
    def test_invalidate_none(self):
        invalidate_dashboard_cache()

    @patch("app.api.v1.data.data.dashboard._cache")
    def test_invalidate_ok(self, m):
        invalidate_dashboard_cache(); m.clear.assert_called_once()

    @patch("app.api.v1.data.data.dashboard._cache")
    def test_invalidate_exc(self, m):
        m.clear.side_effect = Exception("x"); invalidate_dashboard_cache()


# ==================== GET /dashboard/stats ====================

class TestGetDashboardStats:
    def test_all_zero(self, client):
        assert client.get("/api/v1/dashboard/stats").json() is None

    def test_cached(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache") as mc:
            mc.get.return_value = {"v": 1}
            assert client.get("/api/v1/dashboard/stats").json() == {"v": 1}

    def test_refresh(self, client):
        assert client.get("/api/v1/dashboard/stats?refresh=true").status_code == 200

    def test_exception(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_query_village_stats") as mv:
            mv.side_effect = Exception("x")
            assert client.get("/api/v1/dashboard/stats").json() is None


# ==================== GET /dashboard/summary ====================

class TestGetDashboardSummary:
    def test_ok(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None):
            r = client.get("/api/v1/dashboard/summary")
            assert "stats" in r.json() and "recent_activities" in r.json()

    def test_cached(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache") as mc:
            mc.get.return_value = {"stats": {}, "recent_activities": []}
            assert client.get("/api/v1/dashboard/summary").json() == {"stats": {}, "recent_activities": []}

    def test_stats_exception(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None), patch.object(d, "_query_village_stats") as mv:
            mv.side_effect = Exception("x")
            assert client.get("/api/v1/dashboard/summary").json()["stats"] == {}


# ==================== GET /dashboard/recent-activities ====================

class TestGetRecentActivities:
    def _call(self, client, **patches):
        ctx = patches[0] if len(patches) == 1 else patch.multiple(
            "app.api.v1.data.data.dashboard", **{k: v for k, v in patches})
        with ctx:
            return client.get("/api/v1/dashboard/recent-activities")

    def test_empty(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None), patch("app.core.database.SessionLocal") as msl:
            s = MagicMock()
            msl.return_value = s
            s.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            s.query.return_value.all.return_value = []
            assert client.get("/api/v1/dashboard/recent-activities").json()["items"] == []

    def test_cached(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache") as mc:
            mc.get.return_value = {"items": [{"id": "x"}]}
            assert client.get("/api/v1/dashboard/recent-activities").json()["items"][0]["id"] == "x"

    def test_hidden_filter(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None), patch("app.core.database.SessionLocal") as msl:
            s = MagicMock(); msl.return_value = s
            s.query.return_value.all.return_value = [("pid",)]
            s.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            assert client.get("/api/v1/dashboard/recent-activities").status_code == 200

    def test_fetch_hidden_exc(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None), patch("app.core.database.SessionLocal") as msl:
            s = MagicMock(); msl.return_value = s
            s.query.return_value.all.side_effect = Exception("x")
            s.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            assert client.get("/api/v1/dashboard/recent-activities").status_code == 200

    def test_custom_exc(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None), patch("app.core.database.SessionLocal") as msl:
            s = MagicMock(); msl.return_value = s
            s.query.return_value.all.return_value = []
            s.query.return_value.order_by.return_value.limit.return_value.all.side_effect = Exception("x")
            assert client.get("/api/v1/dashboard/recent-activities").status_code == 200




# ==================== POST /dashboard/recent-activities ====================

class TestCreateActivity:
    def test_ok(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache", None):
            r = client.post("/api/v1/dashboard/recent-activities", json={"action": "a", "target": "t"})
            assert r.status_code == 200 and "id" in r.json()

    def test_exception(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        db.add.side_effect = Exception("fail")
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.post("/api/v1/dashboard/recent-activities",
                               json={"action": "a", "target": "t"}).status_code == 500

    def test_cache_delete(self, client):
        import app.api.v1.data.data.dashboard as d
        with patch.object(d, "_cache") as mc:
            client.post("/api/v1/dashboard/recent-activities", json={"action": "a", "target": "t"})
            mc.delete.assert_called_once_with("dashboard_recent_activities")


# ==================== PUT /dashboard/recent-activities/{id} ====================

class TestUpdateActivity:
    def test_custom_ok(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        da = MagicMock(); da.id = 1
        db.query.return_value.filter.return_value.first.return_value = da
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            r = client.put("/api/v1/dashboard/recent-activities/custom_1", json={"type": "f"})
            assert r.status_code == 200 and r.json()["message"] == "更新成功"

    def test_custom_not_found(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.put("/api/v1/dashboard/recent-activities/custom_999",
                              json={"action": "x"}).status_code == 404

    def test_system_activity(self, client):
        r = client.put("/api/v1/dashboard/recent-activities/project_1", json={"type": "f"})
        assert r.status_code == 200 and r.json()["message"] == "无法更新系统自动生成的动态"

    def test_exception(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = Exception("fail")
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.put("/api/v1/dashboard/recent-activities/custom_1",
                              json={"action": "t"}).status_code == 500

    def test_cache_delete(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        da = MagicMock(); da.id = 1
        db.query.return_value.filter.return_value.first.return_value = da
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache") as mc:
            client.put("/api/v1/dashboard/recent-activities/custom_1", json={"target": "n"})
            mc.delete.assert_called_once_with("dashboard_recent_activities")


# ==================== DELETE /dashboard/recent-activities/{id} ====================

class TestDeleteActivity:
    def test_custom_exists(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        da = MagicMock(); da.id = 1
        db.query.return_value.filter.return_value.first.return_value = da
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.delete("/api/v1/dashboard/recent-activities/custom_1").status_code == 200

    def test_custom_not_found(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.delete("/api/v1/dashboard/recent-activities/custom_999").status_code == 200

    def test_system_first_time(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        # first query (custom check) returns None
        # second query (hidden check) returns None
        db.query.return_value.filter.return_value.first.side_effect = [None, None]
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.delete("/api/v1/dashboard/recent-activities/project_5").status_code == 200

    def test_system_already_hidden(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            None,  # custom check → None
            MagicMock(),  # hidden check → found
        ]
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.delete("/api/v1/dashboard/recent-activities/project_5").status_code == 200

    def test_exception(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = Exception("fail")
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache", None):
            assert client.delete("/api/v1/dashboard/recent-activities/custom_1").status_code == 500

    def test_cache_invalidation(self, client):
        import app.api.v1.data.data.dashboard as d
        db = MagicMock()
        da = MagicMock(); da.id = 1
        db.query.return_value.filter.return_value.first.return_value = da
        client.app.dependency_overrides[get_db] = lambda: db
        with patch.object(d, "_cache") as mc:
            client.delete("/api/v1/dashboard/recent-activities/custom_1")
            mc.delete.assert_called_once_with("dashboard_recent_activities")
