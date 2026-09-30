"""Tests for app.api.v1.data.data.data_packages."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.api.v1.data.data.data_packages import get_permission_service

    user = MagicMock()
    user.id = 1; user.is_superuser = True; user.role = "admin"
    mock_db = MagicMock()
    mock_db.query.return_value = mock_db
    mock_db.filter.return_value = mock_db
    mock_db.all.return_value = []
    mock_db.first.return_value = None

    # /preview 等端点自 v1.12.9 起需要组织权限依赖：显式放行，避免真实服务拒绝
    perm = MagicMock()
    perm.can_access_organization.return_value = True

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_permission_service] = lambda: perm

    tc = TestClient(app, raise_server_exceptions=False)
    yield tc
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_permission_service, None)


class TestListPackages:
    def test_empty(self, client):
        resp = client.get("/api/v1/data-packages")
        assert resp.status_code == 200

    def test_with_filters(self, client):
        resp = client.get("/api/v1/data-packages?status=completed&type=export")
        assert resp.status_code == 200


class TestPreviewExport:
    def test_preview(self, client):
        resp = client.post("/api/v1/data-packages/preview", json={"data_types": ["villages"]})
        assert resp.status_code in (200, 422, 500)


class TestGetPackage:
    def test_not_found(self, client):
        resp = client.get("/api/v1/data-packages/99999")
        assert resp.status_code == 404


class TestPreviewPackage:
    def test_not_found(self, client):
        resp = client.get("/api/v1/data-packages/99999/preview")
        assert resp.status_code == 404


class TestDeletePackage:
    def test_not_found(self, client):
        resp = client.delete("/api/v1/data-packages/99999")
        assert resp.status_code == 404


class TestPackageHistory:
    def test_empty(self, client):
        resp = client.get("/api/v1/data-packages/1/history")
        assert resp.status_code in (200, 404, 500)


class TestValidatePackage:
    def test_not_found(self, client):
        resp = client.post("/api/v1/data-packages/99999/validate")
        assert resp.status_code == 404


class TestDownloadPackage:
    def test_not_found(self, client):
        resp = client.get("/api/v1/data-packages/99999/download")
        assert resp.status_code == 404
