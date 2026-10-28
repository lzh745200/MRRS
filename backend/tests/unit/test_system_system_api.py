"""
Tests for system.py — core system API.
"""

from unittest.mock import MagicMock

BASE = "/api/v1/system"


class TestGetSystemInfo:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/info")
        assert resp.status_code == 401

    def test_returns_info(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 5
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        resp = client_with_mocked_auth.get(f"{BASE}/info")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "帮扶管理信息系统"
        assert data["total_users"] == 5

    def test_db_error_defaults_to_zero(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB error")
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        resp = client_with_mocked_auth.get(f"{BASE}/info")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_users"] == 0


class TestGetSystemStatus:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/status")
        assert resp.status_code == 401

    def test_returns_status(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "running"
        assert "uptime_seconds" in data


class TestGetEnvironment:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/environment")
        assert resp.status_code == 401

    def test_returns_env(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/environment")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "python_version" in data
        assert "hostname" in data
        assert "packages" in data


class TestGetVersion:
    def test_returns_version_no_auth(self, client):
        resp = client.get(f"{BASE}/version")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["version"]
        assert data["name"] == "帮扶管理信息系统"
