"""Tests for data/data_packages.py -- data package management API."""
import contextlib
import io
import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import pytest

from app.api.v1.data.data.data_packages import (
    get_package_service,
    get_history_service,
    get_permission_service,
    get_db,
)
from app.schemas.data_package import (
    DataPackageExportResult,
    DataPackageImportResult,
    DataPackageManifest,
    DataPackageValidationResult,
    DataPackageConfirmResult,
)

BASE = "/api/v1/data-packages"


@contextlib.contextmanager
def _override_deps(client, svc=None, hist=None, perm=None, db=None):
    """Set up dependency overrides for service functions used via Depends()."""
    orig = client.app.dependency_overrides.copy()
    if svc is not None:
        client.app.dependency_overrides[get_package_service] = lambda: svc
    if hist is not None:
        client.app.dependency_overrides[get_history_service] = lambda: hist
    if perm is not None:
        client.app.dependency_overrides[get_permission_service] = lambda: perm
    if db is not None:
        client.app.dependency_overrides[get_db] = lambda: db
    try:
        yield
    finally:
        client.app.dependency_overrides = orig


class TestOneClickReport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/one-click-report")
        assert resp.status_code == 401

    def test_no_org_id_returns_400(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=None):
            resp = client_with_mocked_auth.post(f"{BASE}/one-click-report")
            assert resp.status_code == 400
            assert "未绑定组织" in resp.json()["detail"]

    def test_success_file_response(self, client_with_mocked_auth):
        import tempfile as _tf
        _tf_obj = _tf.NamedTemporaryFile(delete=False, suffix=".zip")
        _tf_obj.write(b"fake zip content")
        _tf_obj.close()

        mock_result = MagicMock()
        mock_result.package_id = 1
        mock_result.file_path = _tf_obj.name
        mock_result.file_name = "report_package.zip"
        mock_result.file_size = 1024
        mock_result.manifest = MagicMock()
        mock_result.manifest.record_counts = {"villages": 10, "projects": 5}
        mock_result.manifest.model_dump.return_value = {"record_counts": {"villages": 10, "projects": 5}}

        try:
            with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
                mock_svc = MagicMock()
                mock_svc.export_package = AsyncMock(return_value=mock_result)
                with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
                    resp = client_with_mocked_auth.post(f"{BASE}/one-click-report")
                    assert resp.status_code == 200
        finally:
            import os as _os
            if _os.path.exists(_tf_obj.name):
                _os.unlink(_tf_obj.name)

    def test_success_file_not_exists(self, client_with_mocked_auth):
        mock_result = MagicMock()
        mock_result.package_id = 1
        mock_result.file_path = None
        mock_result.file_name = "report_package.zip"
        mock_result.file_size = 1024
        mock_result.manifest = MagicMock()
        mock_result.manifest.record_counts = {"villages": 10}
        mock_result.manifest.model_dump.return_value = {"record_counts": {"villages": 10}}

        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_package = AsyncMock(return_value=mock_result)
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
                resp = client_with_mocked_auth.post(f"{BASE}/one-click-report")
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["package_id"] == 1

    def test_with_body_params(self, client_with_mocked_auth):
        mock_result = MagicMock()
        mock_result.package_id = 2
        mock_result.file_path = None
        mock_result.file_name = "custom.zip"
        mock_result.file_size = 2048
        mock_result.manifest = MagicMock()
        mock_result.manifest.record_counts = {"schools": 20}
        mock_result.manifest.model_dump.return_value = {"record_counts": {"schools": 20}}

        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_package = AsyncMock(return_value=mock_result)
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
                resp = client_with_mocked_auth.post(
                    f"{BASE}/one-click-report",
                    json={"year": 2024, "data_types": ["schools"], "remarks": "annual report"},
                )
                assert resp.status_code == 200
                _, kwargs = mock_svc.export_package.call_args
                assert kwargs["data_types"] == ["schools"]

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_package = AsyncMock(side_effect=RuntimeError("export failed"))
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
                resp = client_with_mocked_auth.post(f"{BASE}/one-click-report")
                assert resp.status_code == 500


class TestListDataPackages:
    def test_requires_auth(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 401

    def test_no_org_id_returns_empty(self, client_with_mocked_auth):
        from app.core.security import get_current_user
        user = MagicMock()
        user.organization_id = None
        user.org_id = None
        client_with_mocked_auth.app.dependency_overrides[get_current_user] = lambda: user
        resp = client_with_mocked_auth.get(BASE)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_no_permission_returns_empty(self, client_with_mocked_auth):
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 200
            assert resp.json()["total"] == 0

    def test_success(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.package_code = "PK-001"
        mock_pkg.type = "report"
        mock_pkg.status = "completed"
        mock_pkg.description = "Test package"
        mock_pkg.file_name = "pkg.zip"
        mock_pkg.file_size = 1024
        mock_pkg.record_count = 50
        mock_pkg.created_at = None
        mock_pkg.error_message = None

        mock_svc = MagicMock()
        mock_svc.get_packages_by_org.return_value = [mock_pkg]
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 200
            assert resp.json()["total"] == 1

    def test_filter_params(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_packages_by_org.return_value = []
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(BASE, params={"status": "completed", "type": "report"})
            assert resp.status_code == 200
            _, kwargs = mock_svc.get_packages_by_org.call_args
            assert kwargs.get("status") == "completed"
            assert kwargs.get("type_filter") == "report"


class TestGetDataPackage:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/999")
            assert resp.status_code == 404

    def test_no_permission_returns_404(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.org_id = 99

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1")
            assert resp.status_code == 404

    def test_success(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.package_code = "PK-001"
        mock_pkg.type = "report"
        mock_pkg.status = "completed"
        mock_pkg.description = "Test"
        mock_pkg.file_name = "pkg.zip"
        mock_pkg.file_size = 1024
        mock_pkg.record_count = 50
        mock_pkg.created_at = None
        mock_pkg.error_message = None

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1")
            assert resp.status_code == 200
            assert resp.json()["id"] == 1


class TestPreviewDataForExport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/preview", json={"data_types": ["villages"]})
        assert resp.status_code == 401

    def test_success_default_types(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.count.return_value = 5
            mock_db.query.return_value = mock_query
            mock_svc.db = mock_db
            with _override_deps(client_with_mocked_auth, svc=mock_svc):
                resp = client_with_mocked_auth.post(f"{BASE}/preview", json={"data_types": ["villages"]})
                assert resp.status_code == 200
                assert "counts" in resp.json()["data"]

    def test_unknown_data_type(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_db = MagicMock()
            mock_svc.db = mock_db
            with _override_deps(client_with_mocked_auth, svc=mock_svc):
                resp = client_with_mocked_auth.post(f"{BASE}/preview", json={"data_types": ["unknown_type"]})
                assert resp.status_code == 200
                assert resp.json()["data"]["counts"]["unknown_type"] == 0

    def test_no_org_id_uses_fallback(self, client_with_mocked_auth):
        from app.core.security import get_current_user
        user = MagicMock()
        user.organization_id = None
        user.org_id = None
        client_with_mocked_auth.app.dependency_overrides[get_current_user] = lambda: user

        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.count.return_value = 0
            mock_db.query.return_value = mock_query
            mock_svc.db = mock_db
            with _override_deps(client_with_mocked_auth, svc=mock_svc):
                resp = client_with_mocked_auth.post(f"{BASE}/preview", json={"data_types": ["villages"]})
                assert resp.status_code == 200


class TestExportDataPackage:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/export", json={"data_types": ["villages"]})
        assert resp.status_code == 401

    def test_no_org_id(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=None):
            resp = client_with_mocked_auth.post(f"{BASE}/export", json={"data_types": ["villages"]})
            assert resp.status_code == 400

    def test_no_permission(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_perm = MagicMock()
            mock_perm.can_access_organization.return_value = False
            with _override_deps(client_with_mocked_auth, perm=mock_perm):
                resp = client_with_mocked_auth.post(f"{BASE}/export", json={"data_types": ["villages"]})
                assert resp.status_code == 403

    def test_success(self, client_with_mocked_auth):
        mock_result = DataPackageExportResult(
            package_id=1,
            package_code="PK-001",
            file_name="export.zip",
            file_size=2048,
            manifest=DataPackageManifest(record_counts={"villages": 10}),
            download_url="/api/v1/data-packages/1/download",
        )

        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_package = AsyncMock(return_value=mock_result)
            mock_perm = MagicMock()
            mock_perm.can_access_organization.return_value = True
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
                resp = client_with_mocked_auth.post(f"{BASE}/export", json={"data_types": ["villages"]})
                assert resp.status_code == 200
                assert resp.json()["package_id"] == 1

    def test_business_error(self, client_with_mocked_auth):
        from app.core.exceptions import BusinessError
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_package = AsyncMock(side_effect=BusinessError("no data"))
            mock_perm = MagicMock()
            mock_perm.can_access_organization.return_value = True
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
                resp = client_with_mocked_auth.post(f"{BASE}/export", json={"data_types": ["villages"]})
                assert resp.status_code == 400

    def test_unexpected_error(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_package = AsyncMock(side_effect=RuntimeError("unexpected"))
            mock_perm = MagicMock()
            mock_perm.can_access_organization.return_value = True
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
                resp = client_with_mocked_auth.post(f"{BASE}/export", json={"data_types": ["villages"]})
                assert resp.status_code == 500


class TestImportDataPackage:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/import")
        assert resp.status_code == 401

    def test_no_filename(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(f"{BASE}/import", files={"file": ("", b"data", "application/zip")})
        assert resp.status_code == 422

    def test_not_zip(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(f"{BASE}/import", files={"file": ("data.txt", b"hello", "text/plain")})
        assert resp.status_code == 422

    @patch("tempfile.NamedTemporaryFile")
    def test_empty_file(self, mock_tempfile, client_with_mocked_auth):
        mock_tempfile.return_value.name = "C:\\temp\\empty.zip"
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, perm=mock_perm):
            resp = client_with_mocked_auth.post(
                f"{BASE}/import", files={"file": ("data.zip", b"", "application/zip")}
            )
            assert resp.status_code == 422

    def test_no_org_id(self, client_with_mocked_auth):
        from app.core.security import get_current_user
        user = MagicMock()
        user.org_id = None
        client_with_mocked_auth.app.dependency_overrides[get_current_user] = lambda: user
        resp = client_with_mocked_auth.post(
            f"{BASE}/import", files={"file": ("data.zip", b"zipdata", "application/zip")}
        )
        assert resp.status_code == 400

    @patch("tempfile.NamedTemporaryFile")
    def test_success(self, mock_tempfile, client_with_mocked_auth):
        mock_tempfile.return_value.name = "C:\\temp\\upload.zip"

        mock_result = DataPackageImportResult(
            package_id=1,
            package_code="PK-001",
            manifest=DataPackageManifest(record_counts={"villages": 10}, data_types=["villages"]),
            validation=DataPackageValidationResult(is_valid=True, errors=[]),
        )

        mock_svc = MagicMock()
        mock_svc.import_package = AsyncMock(return_value=mock_result)
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.post(
                f"{BASE}/import",
                files={"file": ("data.zip", b"zipdata", "application/zip")},
                data={"org_id": "1"},
            )
            assert resp.status_code == 200

    @patch("tempfile.NamedTemporaryFile")
    def test_validation_failure(self, mock_tempfile, client_with_mocked_auth):
        mock_tempfile.return_value.name = "C:\\temp\\bad.zip"

        mock_result = DataPackageImportResult(
            package_id=1,
            manifest=DataPackageManifest(record_counts={}, data_types=[]),
            validation=DataPackageValidationResult(is_valid=False, errors=[]),
        )

        mock_svc = MagicMock()
        mock_svc.import_package = AsyncMock(return_value=mock_result)
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.post(
                f"{BASE}/import",
                files={"file": ("bad.zip", b"zipdata", "application/zip")},
            )
            assert resp.status_code == 200

    @patch("tempfile.NamedTemporaryFile")
    def test_business_error_unzip(self, mock_tempfile, client_with_mocked_auth):
        mock_tempfile.return_value.name = "C:\\temp\\corrupt.zip"

        from app.core.exceptions import BusinessError
        mock_svc = MagicMock()
        mock_svc.import_package = AsyncMock(side_effect=BusinessError("无法解压"))
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.post(
                f"{BASE}/import",
                files={"file": ("bad.zip", b"zipdata", "application/zip")},
            )
            assert resp.status_code == 400

    @patch("tempfile.NamedTemporaryFile")
    def test_business_error_manifest(self, mock_tempfile, client_with_mocked_auth):
        mock_tempfile.return_value.name = "C:\\temp\\no_manifest.zip"

        from app.core.exceptions import BusinessError
        mock_svc = MagicMock()
        mock_svc.import_package = AsyncMock(side_effect=BusinessError("manifest missing"))
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.post(
                f"{BASE}/import",
                files={"file": ("bad.zip", b"zipdata", "application/zip")},
            )
            assert resp.status_code == 400


class TestValidateDataPackage:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/validate")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
            resp = client_with_mocked_auth.post(f"{BASE}/999/validate")
            assert resp.status_code == 404

    def test_success(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = "/path/to/pkg.zip"

        mock_result = DataPackageValidationResult(is_valid=True, errors=[])

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_svc.validate_package = AsyncMock(return_value=mock_result)
        mock_hist = MagicMock()
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=mock_hist):
            resp = client_with_mocked_auth.post(f"{BASE}/1/validate")
            assert resp.status_code == 200
            mock_hist.record_validate.assert_called_once()

    def test_invalid(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = "/path/to/pkg.zip"

        mock_result = DataPackageValidationResult(
            is_valid=False,
            errors=[],
        )

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_svc.validate_package = AsyncMock(return_value=mock_result)
        mock_hist = MagicMock()
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=mock_hist):
            resp = client_with_mocked_auth.post(f"{BASE}/1/validate")
            assert resp.status_code == 200
            assert resp.json()["is_valid"] is False


class TestPreviewDataPackage:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1/preview")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/999/preview")
            assert resp.status_code == 404

    def test_no_permission_returns_empty(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 99

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm, hist=MagicMock()):
            resp = client_with_mocked_auth.get(f"{BASE}/1/preview")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_success(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1

        mock_preview = [
            {"data_type": "villages", "total": 10, "sample": [], "columns": []}
        ]

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_svc.preview_package_data = AsyncMock(return_value=mock_preview)
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        mock_hist = MagicMock()
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm, hist=mock_hist):
            resp = client_with_mocked_auth.get(f"{BASE}/1/preview")
            assert resp.status_code == 200
            assert len(resp.json()) == 1


class TestConfirmImport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/confirm", json={})
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=MagicMock()):
            resp = client_with_mocked_auth.post(f"{BASE}/999/confirm", json={})
            assert resp.status_code == 404

    def test_no_permission(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 99

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.post(f"{BASE}/1/confirm", json={})
            assert resp.status_code == 403

    def test_success(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1

        mock_result = DataPackageConfirmResult(
            success=True,
            imported_counts={"villages": 10},
            skipped_counts={},
            error_counts={},
        )

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_svc.confirm_import = AsyncMock(return_value=mock_result)
        mock_hist = MagicMock()
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=mock_hist, perm=mock_perm):
            resp = client_with_mocked_auth.post(
                f"{BASE}/1/confirm",
                json={"overwrite_existing": True, "selected_types": ["villages"]},
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_business_error(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1

        from app.core.exceptions import BusinessError
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_svc.confirm_import = AsyncMock(side_effect=BusinessError("already imported"))
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.post(f"{BASE}/1/confirm", json={})
            assert resp.status_code == 400


class TestDownloadDataPackage:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1/download")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=MagicMock()):
            resp = client_with_mocked_auth.get(f"{BASE}/999/download")
            assert resp.status_code == 404

    def test_no_permission_returns_404(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 99

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1/download")
            assert resp.status_code == 404

    def test_no_file_path_returns_409(self, client_with_mocked_auth):
        """R9：校验失败被拒绝的包不落实体文件 → 409 明确语义（非模糊 404）。"""
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = None

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1/download")
            assert resp.status_code == 409
            assert "拒绝" in resp.json()["detail"]

    def test_file_missing_on_disk_returns_404(self, client_with_mocked_auth):
        """有路径但磁盘缺失 → 仍为 404（与 409 的『无实体文件』区分）。"""
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = "Z:/nonexistent/path/pkg.zip"

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1/download")
            assert resp.status_code == 404

    def test_success(self, client_with_mocked_auth):
        import tempfile as _tf
        _tf_obj = _tf.NamedTemporaryFile(delete=False, suffix=".zip")
        _tf_obj.write(b"fake zip content")
        _tf_obj.close()

        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = _tf_obj.name
        mock_pkg.file_name = "pkg.zip"
        mock_pkg.package_code = "PK-001"

        try:
            mock_svc = MagicMock()
            mock_svc.get_package.return_value = mock_pkg
            mock_perm = MagicMock()
            mock_perm.can_access_organization.return_value = True
            with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=mock_perm):
                resp = client_with_mocked_auth.get(f"{BASE}/1/download")
                assert resp.status_code == 200
        finally:
            import os as _os
            if _os.path.exists(_tf_obj.name):
                _os.unlink(_tf_obj.name)


class TestDeleteDataPackage:
    def test_requires_auth(self, client):
        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=MagicMock()):
            resp = client_with_mocked_auth.delete(f"{BASE}/999")
            assert resp.status_code == 404

    def test_no_permission(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 99

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.delete(f"{BASE}/1")
            assert resp.status_code == 403

    def test_success_with_file(self, client_with_mocked_auth):
        import tempfile as _tf
        _tf_obj = _tf.NamedTemporaryFile(delete=False, suffix=".zip")
        _tf_obj.write(b"content")
        _tf_obj.close()

        mock_db = MagicMock()
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = _tf_obj.name

        try:
            mock_svc = MagicMock()
            mock_svc.get_package.return_value = mock_pkg
            mock_perm = MagicMock()
            mock_perm.can_access_organization.return_value = True
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm, db=mock_db):
                resp = client_with_mocked_auth.delete(f"{BASE}/1")
                assert resp.status_code == 200
                assert resp.json()["message"] == "删除成功"
                mock_db.delete.assert_called_once()
        finally:
            import os as _os
            if _os.path.exists(_tf_obj.name):
                _os.unlink(_tf_obj.name)

    def test_success_no_file(self, client_with_mocked_auth):
        mock_db = MagicMock()
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1
        mock_pkg.file_path = None

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm, db=mock_db):
            resp = client_with_mocked_auth.delete(f"{BASE}/1")
            assert resp.status_code == 200


class TestGetPackageHistory:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1/history")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = None
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=MagicMock()):
            resp = client_with_mocked_auth.get(f"{BASE}/999/history")
            assert resp.status_code == 404

    def test_no_permission_returns_empty(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 99

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = False
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock(), perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1/history")
            assert resp.status_code == 200
            assert resp.json()["data"]["items"] == []

    def test_success(self, client_with_mocked_auth):
        mock_pkg = MagicMock()
        mock_pkg.id = 1
        mock_pkg.org_id = 1

        mock_hist_entry = MagicMock()
        mock_hist_entry.id = 1
        mock_hist_entry.operation_type = "export"
        mock_hist_entry.result = "success"
        mock_hist_entry.user_id = 1
        mock_hist_entry.operation_time = None
        mock_hist_entry.duration_ms = 100
        mock_hist_entry.error_message = None

        mock_svc = MagicMock()
        mock_svc.get_package.return_value = mock_pkg
        mock_hist = MagicMock()
        mock_hist.get_history_by_package.return_value = [mock_hist_entry]
        mock_perm = MagicMock()
        mock_perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=mock_hist, perm=mock_perm):
            resp = client_with_mocked_auth.get(f"{BASE}/1/history")
            assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 1
        assert resp.json()["data"]["items"][0]["operation_type"] == "export"


class TestExportEncryptedPackage:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/export-encrypted")
        assert resp.status_code == 401

    def test_no_org_id(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=None):
            resp = client_with_mocked_auth.post(f"{BASE}/export-encrypted", json={"data_types": ["villages"]})
            assert resp.status_code == 400

    def test_short_password(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            resp = client_with_mocked_auth.post(
                f"{BASE}/export-encrypted",
                json={"data_types": ["villages"], "password": "short"}
            )
            assert resp.status_code == 400

    def test_success(self, client_with_mocked_auth):
        mock_result = DataPackageExportResult(
            package_id=1,
            package_code="PK-ENC-001",
            file_name="encrypted.zip",
            file_size=2048,
            manifest=DataPackageManifest(record_counts={"villages": 10}),
        )

        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_encrypted_package = AsyncMock(return_value=mock_result)
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
                resp = client_with_mocked_auth.post(
                    f"{BASE}/export-encrypted",
                    json={"data_types": ["villages"], "password": "longenough"}
                )
                assert resp.status_code == 200
                assert resp.json()["package_id"] == 1

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_svc.export_encrypted_package = AsyncMock(side_effect=RuntimeError("encryption failed"))
            with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
                resp = client_with_mocked_auth.post(
                    f"{BASE}/export-encrypted",
                    json={"data_types": ["villages"], "password": "longenough"}
                )
                assert resp.status_code == 500


class TestUploadEncryptedPackage:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/upload-encrypted")
        assert resp.status_code == 401

    def test_no_org_id(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=None):
            resp = client_with_mocked_auth.post(
                f"{BASE}/upload-encrypted", files={"file": ("pkg.zip", b"data", "application/zip")}
            )
            assert resp.status_code == 400

    def test_success_not_encrypted(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_package_record = MagicMock()
            mock_package_record.id = 1
            mock_package_record.package_code = "PK-001"
            mock_package_record.org_id = 1
            mock_package_record.file_name = "pkg.zip"
            mock_package_record.file_size = 1024
            mock_package_record.status = "pending"
            mock_package_record.created_at = None
            mock_package_record.is_encrypted = False
            mock_svc._create_package_record.return_value = mock_package_record
            with _override_deps(client_with_mocked_auth, svc=mock_svc):
                resp = client_with_mocked_auth.post(
                    f"{BASE}/upload-encrypted",
                    files={"file": ("pkg.zip", b"zipdata", "application/zip")}
                )
                assert resp.status_code == 200
                assert resp.json()["id"] == 1

    def test_success_encrypted(self, client_with_mocked_auth):
        with patch("app.api.v1.data.data.data_packages.get_org_with_fallback", return_value=1):
            mock_svc = MagicMock()
            mock_db = MagicMock()
            mock_package_record = MagicMock()
            mock_package_record.id = 2
            mock_package_record.package_code = "PK-002"
            mock_package_record.org_id = 1
            mock_package_record.file_name = "encrypted.zip"
            mock_package_record.file_size = 2048
            mock_package_record.status = "pending"
            mock_package_record.created_at = None
            mock_package_record.is_encrypted = False
            mock_svc._create_package_record.return_value = mock_package_record
            mock_svc.db = mock_db
            with _override_deps(client_with_mocked_auth, svc=mock_svc):
                import zipfile
                with patch("zipfile.ZipFile", side_effect=zipfile.BadZipFile("not a zip")):
                    resp = client_with_mocked_auth.post(
                        f"{BASE}/upload-encrypted",
                        files={"file": ("enc.zip", b"encrypted_data", "application/zip")},
                    )
                    assert resp.status_code == 200
                    assert mock_package_record.is_encrypted is True
                    mock_db.commit.assert_called_once()


class TestDecryptAndPreviewPackage:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/decrypt-preview/1")
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        mock_result = {"decrypted": True, "data_types": ["villages"]}

        mock_svc = MagicMock()
        mock_svc.decrypt_and_preview_package = AsyncMock(return_value=mock_result)
        with _override_deps(client_with_mocked_auth, svc=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/decrypt-preview/1",
                json={"password": "decrypt123"}
            )
            assert resp.status_code == 200
            assert resp.json()["decrypted"] is True

    def test_business_error(self, client_with_mocked_auth):
        from app.core.exceptions import BusinessError
        mock_svc = MagicMock()
        mock_svc.decrypt_and_preview_package = AsyncMock(side_effect=BusinessError("wrong password"))
        with _override_deps(client_with_mocked_auth, svc=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/decrypt-preview/1",
                json={"password": "wrong"}
            )
            assert resp.status_code == 400

    def test_unexpected_error(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.decrypt_and_preview_package = AsyncMock(side_effect=RuntimeError("decrypt failed"))
        with _override_deps(client_with_mocked_auth, svc=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/decrypt-preview/1",
                json={"password": "test1234"}
            )
            assert resp.status_code == 500


class TestConfirmImportWithConflictResolution:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/confirm-import/1", json={"conflict_strategy": "KEEP_BOTH"})
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        mock_result = {"imported": True, "records_imported": 50}

        mock_svc = MagicMock()
        mock_svc.confirm_import_with_conflict_resolution = AsyncMock(return_value=mock_result)
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
            resp = client_with_mocked_auth.post(
                f"{BASE}/confirm-import/1",
                json={"conflict_strategy": "OVERWRITE"}
            )
            assert resp.status_code == 200

    def test_error(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.confirm_import_with_conflict_resolution = AsyncMock(side_effect=RuntimeError("import failed"))
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
            resp = client_with_mocked_auth.post(
                f"{BASE}/confirm-import/1",
                json={"conflict_strategy": "SKIP"}
            )
            assert resp.status_code == 500
