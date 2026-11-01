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


class TestDryRunPackage:
    """长期项「两阶段导入」第一阶段端点（2026-11-01）。

    演练必须与 confirm 一样受组织权限约束，且错误必须可区分：
    包不存在 → 404；无权限 → 403；状态不允许 → 400；坏包 → 400「文件损坏」。
    """

    def _payload(self, resp):
        body = resp.json()
        return body.get("data", body)

    def test_not_found(self, client):
        resp = client.post("/api/v1/data-packages/99999/dry-run", json={})
        assert resp.status_code == 404

    def test_success(self, client):
        from app.api.v1.data.data.data_packages import get_package_service

        svc = MagicMock()
        svc.get_package.return_value = MagicMock(org_id=1)
        svc.dry_run_import.return_value = {
            "success": True,
            "package_id": 7,
            "package_code": "PKG-7",
            "status": "validated",
            "overwrite_existing": False,
            "types": [],
            "total_records": 3,
            "total_to_create": 2,
            "total_to_update": 0,
            "total_rejected": 1,
            "rejected": [],
            "message": "",
        }
        client.app.dependency_overrides[get_package_service] = lambda: svc
        try:
            resp = client.post("/api/v1/data-packages/7/dry-run", json={})
        finally:
            client.app.dependency_overrides.pop(get_package_service, None)

        assert resp.status_code == 200
        payload = self._payload(resp)
        assert payload.get("total_to_create", payload.get("totalToCreate")) == 2
        svc.dry_run_import.assert_called_once()

    def test_forbidden_foreign_org(self, client):
        from app.api.v1.data.data.data_packages import (
            get_package_service,
            get_permission_service,
        )

        svc = MagicMock()
        svc.get_package.return_value = MagicMock(org_id=99)
        perm = MagicMock()
        perm.can_access_organization.return_value = False
        client.app.dependency_overrides[get_package_service] = lambda: svc
        client.app.dependency_overrides[get_permission_service] = lambda: perm
        try:
            resp = client.post("/api/v1/data-packages/7/dry-run", json={})
        finally:
            client.app.dependency_overrides.pop(get_package_service, None)
            client.app.dependency_overrides.pop(get_permission_service, None)

        assert resp.status_code == 403
        svc.dry_run_import.assert_not_called()

    def test_business_error_maps_to_400(self, client):
        from app.api.v1.data.data.data_packages import get_package_service
        from app.core.exceptions import BusinessError

        svc = MagicMock()
        svc.get_package.return_value = MagicMock(org_id=1)
        svc.dry_run_import.side_effect = BusinessError("数据包状态不允许演练: pending")
        client.app.dependency_overrides[get_package_service] = lambda: svc
        try:
            resp = client.post("/api/v1/data-packages/7/dry-run", json={})
        finally:
            client.app.dependency_overrides.pop(get_package_service, None)

        assert resp.status_code == 400
        assert "状态不允许" in resp.text

    def test_bad_zip_maps_to_400(self, client):
        import zipfile as _zipfile

        from app.api.v1.data.data.data_packages import get_package_service

        svc = MagicMock()
        svc.get_package.return_value = MagicMock(org_id=1)
        svc.dry_run_import.side_effect = _zipfile.BadZipFile("bad")
        client.app.dependency_overrides[get_package_service] = lambda: svc
        try:
            resp = client.post("/api/v1/data-packages/7/dry-run", json={})
        finally:
            client.app.dependency_overrides.pop(get_package_service, None)

        assert resp.status_code == 400
        assert "损坏" in resp.text
