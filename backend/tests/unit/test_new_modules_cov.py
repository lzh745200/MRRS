"""Coverage tests for 5 new modules.

Targets:
  - app/api/v1/control_package.py
  - app/api/v1/subordinate_reports.py
  - app/api/v1/subordinate_registry.py
  - app/api/v1/org_module_policy.py
"""

import io
import json
import zipfile
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import HTTPException, Request

from app.api.v1.control_package import (
    GenerateControlPackageRequest,
    generate_control_package,
    import_control_package,
    import_control_package_preview,
)
from app.api.v1.subordinate_reports import (
    _get_instance_code,
    _process_registration_report,
    _process_status_report,
    generate_registration_report,
    generate_status_report,
    import_subordinate_report,
)
from app.api.v1.subordinate_registry import (
    SubordinateCreateRequest,
    SubordinateUpdateRequest,
    delete_subordinate,
    get_subordinate,
    list_subordinates,
    register_subordinate,
    update_subordinate,
)
from app.api.v1.org_module_policy import (
    BatchPolicyRequest,
    ModulePolicyItem,
    export_org_policies,
    get_current_org_policies,
    get_org_policies,
    list_module_definitions,
    reset_org_policy,
    set_org_policies,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    return db


@pytest.fixture
def admin_user():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    return u


@pytest.fixture
def regular_user():
    u = MagicMock()
    u.id = 2
    u.username = "user1"
    u.role = "user"
    u.is_superuser = False
    u.organization_id = 2
    return u


def _make_zip(files: dict) -> bytes:
    """Build an in-memory ZIP from {name: content_str}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _mock_upload_file(content: bytes, filename: str = "test.zip"):
    """Create a mock UploadFile with async read()."""
    f = MagicMock()
    f.filename = filename
    f.read = AsyncMock(return_value=content)
    return f


# ── 1. control_package.py ────────────────────────────────────────────


class TestGenerateControlPackage:
    @patch("app.api.v1.control_package.write_work_log")
    def test_generate_full(self, mock_wl, mock_db, admin_user):
        """Lines 46-125: full generate with users + system_config."""
        pol = MagicMock()
        pol.module_key = "funds"
        pol.visibility = "visible"
        pol.edit_mode = "full_edit"

        usr = MagicMock()
        usr.username = "u1"
        usr.full_name = "User One"
        usr.role = "user"
        usr.data_scope = "own"
        usr.is_active = True
        usr.allowed_menus = None

        cfg = MagicMock()
        cfg.key = "site_name"
        cfg.value = "Test"

        call_idx = [0]

        def smart_query(model):
            call_idx[0] += 1
            q = MagicMock()
            if call_idx[0] == 1:
                q.filter.return_value.all.return_value = [pol]
            elif call_idx[0] == 2:
                q.filter.return_value.all.return_value = [usr]
            elif call_idx[0] == 3:
                q.all.return_value = [cfg]
            return q

        mock_db.query = MagicMock(side_effect=smart_query)

        body = GenerateControlPackageRequest(
            organization_id=1,
            include_users=True,
            include_rbac=True,
            include_system_config=True,
        )
        resp = generate_control_package(body, db=mock_db, current_user=admin_user)
        assert resp.media_type == "application/zip"
        assert "X-Package-Hash" in resp.headers
        mock_wl.assert_called_once()

    @patch("app.api.v1.control_package.write_work_log")
    def test_generate_no_users_no_config(self, mock_wl, mock_db, admin_user):
        """Generate with include_users=False, include_system_config=False."""
        pol = MagicMock()
        pol.module_key = "map"
        pol.visibility = "hidden"
        pol.edit_mode = "read_only"

        def smart_query(model):
            q = MagicMock()
            q.filter.return_value.all.return_value = [pol]
            return q

        mock_db.query = MagicMock(side_effect=smart_query)

        body = GenerateControlPackageRequest(
            organization_id=1,
            include_users=False,
            include_system_config=False,
        )
        resp = generate_control_package(body, db=mock_db, current_user=admin_user)
        assert resp.media_type == "application/zip"

    def test_generate_forbidden(self, mock_db, regular_user):
        """Non-admin gets 403."""
        body = GenerateControlPackageRequest(organization_id=1)
        with pytest.raises(HTTPException) as exc_info:
            generate_control_package(body, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.control_package.write_work_log", side_effect=Exception("log fail"))
    def test_generate_work_log_exception(self, mock_wl, mock_db, admin_user):
        """write_work_log failure is swallowed (lines ~120-122)."""
        def smart_query(model):
            q = MagicMock()
            q.filter.return_value.all.return_value = []
            q.all.return_value = []
            return q

        mock_db.query = MagicMock(side_effect=smart_query)
        body = GenerateControlPackageRequest(
            organization_id=1,
            include_users=False,
            include_system_config=False,
        )
        resp = generate_control_package(body, db=mock_db, current_user=admin_user)
        assert resp.media_type == "application/zip"


class TestImportControlPackagePreview:
    async def test_preview_valid(self, mock_db, admin_user):
        """Lines 150-183: valid ZIP preview."""
        manifest = {
            "package_version": "1.0",
            "package_type": "control",
            "target_organization_id": 1,
        }
        policies = [{"module_key": "funds", "visibility": "visible", "edit_mode": "full_edit"}]
        users = [{"username": "u1"}]
        content = _make_zip({
            "manifest.json": json.dumps(manifest),
            "module_policy.json": json.dumps(policies),
            "users.json": json.dumps(users),
        })
        f = _mock_upload_file(content, "pkg.zip")
        result = await import_control_package_preview(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result.valid is True
        assert result.module_policy_count == 1
        assert result.user_count == 1

    async def test_preview_not_zip_extension(self, mock_db, admin_user):
        """Non-.zip filename → 400."""
        f = _mock_upload_file(b"data", "pkg.txt")
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package_preview(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    async def test_preview_no_filename(self, mock_db, admin_user):
        """None filename → 400."""
        f = _mock_upload_file(b"data", None)
        f.filename = None
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package_preview(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    async def test_preview_missing_manifest(self, mock_db, admin_user):
        """ZIP without manifest.json → valid=False."""
        content = _make_zip({"other.json": "{}"})
        f = _mock_upload_file(content, "pkg.zip")
        result = await import_control_package_preview(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result.valid is False
        assert "manifest.json" in result.error

    async def test_preview_wrong_package_type(self, mock_db, admin_user):
        """manifest with wrong package_type → valid=False."""
        manifest = {"package_type": "data"}
        content = _make_zip({"manifest.json": json.dumps(manifest)})
        f = _mock_upload_file(content, "pkg.zip")
        result = await import_control_package_preview(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result.valid is False
        assert "非管控配置包类型" in result.error

    async def test_preview_bad_zip(self, mock_db, admin_user):
        """Corrupt data → valid=False with BadZipFile error."""
        f = _mock_upload_file(b"not-a-zip", "pkg.zip")
        result = await import_control_package_preview(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result.valid is False
        assert "ZIP" in result.error

    async def test_preview_bad_json(self, mock_db, admin_user):
        """Invalid JSON in manifest → valid=False."""
        content = _make_zip({"manifest.json": "not-json{"})
        f = _mock_upload_file(content, "pkg.zip")
        result = await import_control_package_preview(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result.valid is False
        assert "JSON" in result.error

    async def test_preview_no_optional_files(self, mock_db, admin_user):
        """Manifest only, no module_policy.json or users.json."""
        manifest = {"package_type": "control"}
        content = _make_zip({"manifest.json": json.dumps(manifest)})
        f = _mock_upload_file(content, "pkg.zip")
        result = await import_control_package_preview(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result.valid is True
        assert result.module_policy_count == 0
        assert result.user_count == 0


class TestImportControlPackage:
    @patch("app.api.v1.control_package.write_work_log")
    async def test_import_full(self, mock_wl, mock_db, admin_user):
        """Lines 193-267: full import with policies + system_config."""
        manifest = {
            "package_type": "control",
            "target_organization_id": 1,
        }
        policies = [
            {"module_key": "funds", "visibility": "hidden", "edit_mode": "read_only"},
            {"module_key": "map", "visibility": "visible", "edit_mode": "full_edit"},
        ]
        sys_cfg = {"site_name": "NewVal"}
        content = _make_zip({
            "manifest.json": json.dumps(manifest),
            "module_policy.json": json.dumps(policies),
            "system_config.json": json.dumps(sys_cfg),
        })
        f = _mock_upload_file(content, "pkg.zip")

        existing_pol = MagicMock()
        existing_cfg = MagicMock()
        call_idx = [0]

        def smart_query(model):
            call_idx[0] += 1
            q = MagicMock()
            if call_idx[0] == 1:
                q.filter.return_value.first.return_value = existing_pol
            elif call_idx[0] == 2:
                q.filter.return_value.first.return_value = None
            elif call_idx[0] == 3:
                q.filter.return_value.first.return_value = existing_cfg
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query = MagicMock(side_effect=smart_query)

        result = await import_control_package(
            file=f, db=mock_db, current_user=admin_user
        )
        body = result
        assert body["data"]["applied_policies"] == 2
        assert body["data"]["applied_configs"] == 1
        mock_db.commit.assert_called()
        mock_wl.assert_called_once()

    async def test_import_forbidden(self, mock_db, regular_user):
        """Non-admin import → 403."""
        f = _mock_upload_file(b"data", "pkg.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package(
                file=f, db=mock_db, current_user=regular_user
            )
        assert exc_info.value.status_code == 403

    async def test_import_missing_manifest(self, mock_db, admin_user):
        """ZIP without manifest → 400."""
        content = _make_zip({"other.json": "{}"})
        f = _mock_upload_file(content, "pkg.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    async def test_import_wrong_type(self, mock_db, admin_user):
        """Wrong package_type → 400."""
        manifest = {"package_type": "data"}
        content = _make_zip({"manifest.json": json.dumps(manifest)})
        f = _mock_upload_file(content, "pkg.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    async def test_import_bad_zip(self, mock_db, admin_user):
        """Corrupt ZIP → 400."""
        f = _mock_upload_file(b"corrupt", "pkg.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    @patch("app.api.v1.control_package.write_work_log")
    async def test_import_generic_exception(self, mock_wl, mock_db, admin_user):
        """Generic exception during import → 500 + rollback."""
        manifest = {"package_type": "control", "target_organization_id": 1}
        policies = [{"module_key": "funds", "visibility": "v", "edit_mode": "e"}]
        content = _make_zip({
            "manifest.json": json.dumps(manifest),
            "module_policy.json": json.dumps(policies),
        })
        f = _mock_upload_file(content, "pkg.zip")
        mock_db.query.side_effect = RuntimeError("db crash")
        with pytest.raises(HTTPException) as exc_info:
            await import_control_package(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called()

    @patch("app.api.v1.control_package.write_work_log", side_effect=Exception("log err"))
    async def test_import_work_log_exception(self, mock_wl, mock_db, admin_user):
        """write_work_log failure is swallowed on import."""
        manifest = {"package_type": "control", "target_organization_id": 1}
        content = _make_zip({"manifest.json": json.dumps(manifest)})
        f = _mock_upload_file(content, "pkg.zip")
        mock_db.query = MagicMock(return_value=MagicMock())
        result = await import_control_package(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result["data"]["applied_policies"] == 0


# ── 2. subordinate_reports.py ────────────────────────────────────────


class TestGenerateRegistrationReport:
    def test_generate_registration(self, mock_db, admin_user):
        """Lines 39-69: generate registration report."""
        u = MagicMock()
        u.username = "u1"
        u.full_name = "User"
        u.role = "user"
        u.is_active = True
        u.last_login = datetime(2026, 1, 1, tzinfo=timezone.utc)

        u2 = MagicMock()
        u2.username = "u2"
        u2.full_name = "User2"
        u2.role = "admin"
        u2.is_active = True
        u2.last_login = None

        mock_db.query.return_value.filter.return_value.all.return_value = [u, u2]

        resp = generate_registration_report(db=mock_db, current_user=admin_user)
        assert resp.media_type == "application/zip"
        assert "registration_report" in resp.headers["Content-Disposition"]


class TestGenerateStatusReport:
    @patch("app.api.v1.subordinate_reports._get_instance_code", return_value="INST001")
    def test_generate_status(self, mock_gic, mock_db, admin_user):
        """Lines 85-119: generate status report."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DATABASE_URL = "sqlite:///./nonexistent.db"
            mock_settings.PROJECT_VERSION = "1.4.3"
            resp = generate_status_report(db=mock_db, current_user=admin_user)

        assert resp.media_type == "application/zip"

    @patch("app.api.v1.subordinate_reports._get_instance_code", return_value=None)
    def test_generate_status_db_exists(self, mock_gic, mock_db, admin_user):
        """Status report when DB file exists (covers os.path.exists branch)."""
        import tempfile
        import os
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.write(b"x" * 2048)
        tmp.close()

        mock_db.query.return_value.filter.return_value.scalar.return_value = 3

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.DATABASE_URL = f"sqlite:///{tmp.name}"
            mock_settings.PROJECT_VERSION = "1.4.3"
            resp = generate_status_report(db=mock_db, current_user=admin_user)

        os.unlink(tmp.name)
        assert resp.media_type == "application/zip"


class TestImportSubordinateReport:
    async def test_import_status_report(self, mock_db, admin_user):
        """Lines 144-165: import with status_report.json.

        NOTE: argument-swap bug has been fixed, so dispatch works correctly.
        """
        report = {
            "report_type": "status",
            "organization_id": 1,
            "system_version": "1.4.3",
            "user_count": 10,
            "instance_code": "INST001",
        }
        content = _make_zip({"status_report.json": json.dumps(report)})
        f = _mock_upload_file(content, "report.zip")

        result = await import_subordinate_report(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result is not None

    async def test_import_registration_report(self, mock_db, admin_user):
        """Import with registration_report.json processes successfully."""
        report = {
            "report_type": "registration",
            "organization_id": 1,
            "users": [{"username": "u1"}, {"username": "u2"}],
        }
        content = _make_zip({"registration_report.json": json.dumps(report)})
        f = _mock_upload_file(content, "report.zip")

        result = await import_subordinate_report(
            file=f, db=mock_db, current_user=admin_user
        )
        assert result is not None

    async def test_import_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        f = _mock_upload_file(b"data", "report.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_subordinate_report(
                file=f, db=mock_db, current_user=regular_user
            )
        assert exc_info.value.status_code == 403

    async def test_import_unrecognized_format(self, mock_db, admin_user):
        """ZIP with unknown files → 400."""
        content = _make_zip({"unknown.json": "{}"})
        f = _mock_upload_file(content, "report.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_subordinate_report(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    async def test_import_bad_zip(self, mock_db, admin_user):
        """Corrupt ZIP → 400."""
        f = _mock_upload_file(b"corrupt", "report.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_subordinate_report(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 400

    async def test_import_generic_exception(self, mock_db, admin_user):
        """Generic exception → 500."""
        content = _make_zip({"status_report.json": "not-json{"})
        f = _mock_upload_file(content, "report.zip")
        with pytest.raises(HTTPException) as exc_info:
            await import_subordinate_report(
                file=f, db=mock_db, current_user=admin_user
            )
        assert exc_info.value.status_code == 500


class TestProcessStatusReport:
    def test_process_with_instance(self, mock_db, admin_user):
        """Lines 170-197: status report with matching instance."""
        report = {
            "organization_id": 1,
            "system_version": "1.4.3",
            "user_count": 5,
            "instance_code": "INST001",
        }
        zf_content = _make_zip({"status_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        instance = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = instance

        with patch("app.api.v1.subordinate_reports.write_work_log"):
            result = _process_status_report(zf, mock_db, admin_user)
        assert result["data"]["instance_updated"] is True
        assert instance.status == "online"
        mock_db.commit.assert_called()

    def test_process_no_instance_code(self, mock_db, admin_user):
        """Status report without instance_code."""
        report = {"organization_id": 1, "user_count": 3}
        zf_content = _make_zip({"status_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        with patch("app.api.v1.subordinate_reports.write_work_log"):
            result = _process_status_report(zf, mock_db, admin_user)
        assert result["data"]["instance_updated"] is False

    def test_process_instance_not_found(self, mock_db, admin_user):
        """Status report with instance_code but no matching DB record."""
        report = {"organization_id": 1, "instance_code": "MISSING", "user_count": 0}
        zf_content = _make_zip({"status_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.api.v1.subordinate_reports.write_work_log"):
            result = _process_status_report(zf, mock_db, admin_user)
        assert result["data"]["instance_updated"] is False

    def test_process_work_log_exception(self, mock_db, admin_user):
        """write_work_log failure is swallowed."""
        report = {"organization_id": 1, "user_count": 0}
        zf_content = _make_zip({"status_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        with patch(
            "app.api.v1.subordinate_reports.write_work_log",
            side_effect=Exception("fail"),
        ):
            result = _process_status_report(zf, mock_db, admin_user)
        assert result["data"]["report_type"] == "status"


class TestProcessRegistrationReport:
    def test_process_with_instance(self, mock_db, admin_user):
        """Lines 208-233: registration report with matching instance."""
        report = {
            "organization_id": 1,
            "users": [{"username": "u1"}],
        }
        zf_content = _make_zip({"registration_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        instance = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = instance

        with patch("app.api.v1.subordinate_reports.write_work_log"):
            result = _process_registration_report(zf, mock_db, admin_user)
        assert result["data"]["user_count"] == 1
        assert instance.status == "online"
        mock_db.commit.assert_called()

    def test_process_no_org_id(self, mock_db, admin_user):
        """Registration report without organization_id."""
        report = {"users": [{"username": "u1"}]}
        zf_content = _make_zip({"registration_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        with patch("app.api.v1.subordinate_reports.write_work_log"):
            result = _process_registration_report(zf, mock_db, admin_user)
        assert result["data"]["organization_id"] is None

    def test_process_instance_not_found(self, mock_db, admin_user):
        """Registration report with org_id but no matching instance."""
        report = {"organization_id": 99, "users": []}
        zf_content = _make_zip({"registration_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.api.v1.subordinate_reports.write_work_log"):
            result = _process_registration_report(zf, mock_db, admin_user)
        assert result["data"]["user_count"] == 0

    def test_process_work_log_exception(self, mock_db, admin_user):
        """write_work_log failure is swallowed."""
        report = {"organization_id": 1, "users": []}
        zf_content = _make_zip({"registration_report.json": json.dumps(report)})
        zf = zipfile.ZipFile(io.BytesIO(zf_content), "r")

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch(
            "app.api.v1.subordinate_reports.write_work_log",
            side_effect=Exception("fail"),
        ):
            result = _process_registration_report(zf, mock_db, admin_user)
        assert result["data"]["report_type"] == "registration"


class TestGetInstanceCode:
    def test_with_org_id_found(self, mock_db):
        """Lines 244-249: instance found."""
        instance = MagicMock()
        instance.instance_code = "CODE123"
        mock_db.query.return_value.filter.return_value.first.return_value = instance
        assert _get_instance_code(mock_db, 1) == "CODE123"

    def test_with_org_id_not_found(self, mock_db):
        """Instance not found → None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert _get_instance_code(mock_db, 1) is None

    def test_no_org_id(self, mock_db):
        """org_id is None → None."""
        assert _get_instance_code(mock_db, None) is None


# ── 3. subordinate_registry.py ───────────────────────────────────────


class TestListSubordinates:
    def test_list_all(self, mock_db, admin_user):
        """Lines 50-67: list without filters."""
        inst = MagicMock()
        inst.to_dict.return_value = {"id": 1, "instance_code": "A"}

        q = MagicMock()
        q.count.return_value = 1
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [inst]
        mock_db.query.return_value = q

        result = list_subordinates(
            page=1, page_size=20, keyword=None, license_status=None,
            db=mock_db, current_user=admin_user,
        )
        assert result["data"]["total"] == 1

    def test_list_with_keyword_and_status(self, mock_db, admin_user):
        """List with keyword + license_status filters."""
        q = MagicMock()
        q.filter.return_value = q
        q.count.return_value = 0
        q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = q

        result = list_subordinates(
            page=1, page_size=10, keyword="test", license_status="active",
            db=mock_db, current_user=admin_user,
        )
        assert result["data"]["total"] == 0

    def test_list_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        with pytest.raises(HTTPException) as exc_info:
            list_subordinates(
                page=1, page_size=20, keyword=None, license_status=None,
                db=mock_db, current_user=regular_user,
            )
        assert exc_info.value.status_code == 403


class TestRegisterSubordinate:
    @patch("app.api.v1.subordinate_registry.write_work_log")
    def test_register_success(self, mock_wl, mock_db, admin_user):
        """Lines 82-115: register new instance."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        body = SubordinateCreateRequest(
            organization_id=1,
            instance_code="INST0001",
            machine_code="MC001",
            system_version="1.4.3",
            license_expiry=date(2027, 1, 1),
            remark="test",
        )
        result = register_subordinate(body, db=mock_db, current_user=admin_user)
        assert result["message"] == "下级单位注册成功"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_wl.assert_called_once()

    def test_register_duplicate(self, mock_db, admin_user):
        """Duplicate instance_code → 400."""
        existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        body = SubordinateCreateRequest(
            organization_id=1, instance_code="DUP00001"
        )
        with pytest.raises(HTTPException) as exc_info:
            register_subordinate(body, db=mock_db, current_user=admin_user)
        assert exc_info.value.status_code == 400

    def test_register_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        body = SubordinateCreateRequest(
            organization_id=1, instance_code="INST0001"
        )
        with pytest.raises(HTTPException) as exc_info:
            register_subordinate(body, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403

    @patch(
        "app.api.v1.subordinate_registry.write_work_log",
        side_effect=Exception("fail"),
    )
    def test_register_work_log_exception(self, mock_wl, mock_db, admin_user):
        """write_work_log failure is swallowed."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        body = SubordinateCreateRequest(
            organization_id=1, instance_code="INST0002"
        )
        result = register_subordinate(body, db=mock_db, current_user=admin_user)
        assert result["message"] == "下级单位注册成功"


class TestUpdateSubordinate:
    @patch("app.api.v1.subordinate_registry.write_work_log")
    def test_update_success(self, mock_wl, mock_db, admin_user):
        """Lines 126-157: update all fields."""
        instance = MagicMock()
        instance.instance_code = "INST0001"
        mock_db.query.return_value.filter.return_value.first.return_value = instance

        body = SubordinateUpdateRequest(
            license_status="active",
            license_expiry=date(2027, 6, 1),
            system_version="1.5.0",
            remark="updated",
        )
        result = update_subordinate(1, body, db=mock_db, current_user=admin_user)
        assert result["message"] == "更新成功"
        assert instance.license_status == "active"
        assert instance.system_version == "1.5.0"
        mock_wl.assert_called_once()

    @patch("app.api.v1.subordinate_registry.write_work_log")
    def test_update_partial(self, mock_wl, mock_db, admin_user):
        """Update with only some fields set."""
        instance = MagicMock()
        instance.instance_code = "INST0001"
        mock_db.query.return_value.filter.return_value.first.return_value = instance

        body = SubordinateUpdateRequest(license_status="revoked")
        result = update_subordinate(1, body, db=mock_db, current_user=admin_user)
        assert result["message"] == "更新成功"

    def test_update_not_found(self, mock_db, admin_user):
        """Instance not found → 404."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        body = SubordinateUpdateRequest(license_status="active")
        with pytest.raises(HTTPException) as exc_info:
            update_subordinate(999, body, db=mock_db, current_user=admin_user)
        assert exc_info.value.status_code == 404

    def test_update_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        body = SubordinateUpdateRequest()
        with pytest.raises(HTTPException) as exc_info:
            update_subordinate(1, body, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403

    @patch(
        "app.api.v1.subordinate_registry.write_work_log",
        side_effect=Exception("fail"),
    )
    def test_update_work_log_exception(self, mock_wl, mock_db, admin_user):
        """write_work_log failure is swallowed."""
        instance = MagicMock()
        instance.instance_code = "INST0001"
        mock_db.query.return_value.filter.return_value.first.return_value = instance
        body = SubordinateUpdateRequest(remark="r")
        result = update_subordinate(1, body, db=mock_db, current_user=admin_user)
        assert result["message"] == "更新成功"


class TestGetSubordinate:
    def test_get_success(self, mock_db, admin_user):
        """Lines 167-176: get detail."""
        instance = MagicMock()
        instance.to_dict.return_value = {"id": 1}
        mock_db.query.return_value.filter.return_value.first.return_value = instance
        result = get_subordinate(1, db=mock_db, current_user=admin_user)
        assert result["data"]["id"] == 1

    def test_get_not_found(self, mock_db, admin_user):
        """Not found → 404."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            get_subordinate(999, db=mock_db, current_user=admin_user)
        assert exc_info.value.status_code == 404

    def test_get_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        with pytest.raises(HTTPException) as exc_info:
            get_subordinate(1, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403


class TestDeleteSubordinate:
    @patch("app.api.v1.subordinate_registry.write_work_log")
    def test_delete_success(self, mock_wl, mock_db, admin_user):
        """Lines 186-208: delete."""
        instance = MagicMock()
        instance.instance_code = "INST0001"
        mock_db.query.return_value.filter.return_value.first.return_value = instance
        result = delete_subordinate(1, db=mock_db, current_user=admin_user)
        assert result["message"] == "删除成功"
        mock_db.delete.assert_called_once_with(instance)
        mock_db.commit.assert_called()
        mock_wl.assert_called_once()

    def test_delete_not_found(self, mock_db, admin_user):
        """Not found → 404."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            delete_subordinate(999, db=mock_db, current_user=admin_user)
        assert exc_info.value.status_code == 404

    def test_delete_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        with pytest.raises(HTTPException) as exc_info:
            delete_subordinate(1, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403

    @patch(
        "app.api.v1.subordinate_registry.write_work_log",
        side_effect=Exception("fail"),
    )
    def test_delete_work_log_exception(self, mock_wl, mock_db, admin_user):
        """write_work_log failure is swallowed."""
        instance = MagicMock()
        instance.instance_code = "INST0001"
        mock_db.query.return_value.filter.return_value.first.return_value = instance
        result = delete_subordinate(1, db=mock_db, current_user=admin_user)
        assert result["message"] == "删除成功"


# ── 4. org_module_policy.py ──────────────────────────────────────────


class TestListModuleDefinitions:
    def test_list_modules(self, admin_user):
        """Line 39: return MODULE_DEFINITIONS."""
        result = list_module_definitions(current_user=admin_user)
        assert result["code"] == 200
        assert len(result["data"]) > 0
        keys = [m["key"] for m in result["data"]]
        assert "funds" in keys


class TestGetCurrentOrgPolicies:
    def test_with_org_id(self, mock_db, admin_user):
        """Lines 48-56: policies for current user's org."""
        p = MagicMock()
        p.module_key = "funds"
        p.visibility = "hidden"
        p.edit_mode = "read_only"
        mock_db.query.return_value.filter.return_value.all.return_value = [p]

        result = get_current_org_policies(db=mock_db, current_user=admin_user)
        assert len(result["data"]) == 1
        assert result["data"][0]["module_key"] == "funds"

    def test_no_org_id(self, mock_db):
        """User without organization_id → empty list."""
        user = MagicMock()
        user.organization_id = None
        result = get_current_org_policies(db=mock_db, current_user=user)
        assert result["data"] == []


class TestGetOrgPolicies:
    def test_get_with_custom_and_default(self, mock_db, admin_user):
        """Lines 73-90: merge DB policies with defaults."""
        p = MagicMock()
        p.module_key = "funds"
        p.visibility = "hidden"
        p.edit_mode = "disabled"
        mock_db.query.return_value.filter.return_value.all.return_value = [p]

        result = get_org_policies(1, db=mock_db, current_user=admin_user)
        data = result["data"]
        funds_entry = [d for d in data if d["key"] == "funds"][0]
        assert funds_entry["visibility"] == "hidden"
        assert funds_entry["is_custom"] is True

        dashboard_entry = [d for d in data if d["key"] == "dashboard"][0]
        assert dashboard_entry["visibility"] == "visible"
        assert dashboard_entry["is_custom"] is False

    def test_get_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        with pytest.raises(HTTPException) as exc_info:
            get_org_policies(1, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403


class TestSetOrgPolicies:
    @patch("app.api.v1.org_module_policy.write_work_log")
    def test_set_update_existing(self, mock_wl, mock_db, admin_user):
        """Lines 101-142: update existing policy."""
        existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        body = BatchPolicyRequest(policies=[
            ModulePolicyItem(
                module_key="funds", visibility="hidden", edit_mode="read_only"
            ),
        ])
        result = set_org_policies(1, body, db=mock_db, current_user=admin_user)
        assert result["data"]["updated"] == 1
        assert existing.visibility == "hidden"
        mock_db.commit.assert_called()
        mock_wl.assert_called_once()

    @patch("app.api.v1.org_module_policy.write_work_log")
    def test_set_create_new(self, mock_wl, mock_db, admin_user):
        """Create new policy (no existing record)."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        body = BatchPolicyRequest(policies=[
            ModulePolicyItem(module_key="map", visibility="visible"),
        ])
        result = set_org_policies(1, body, db=mock_db, current_user=admin_user)
        assert result["data"]["updated"] == 1
        mock_db.add.assert_called_once()

    def test_set_invalid_module_key(self, mock_db, admin_user):
        """Invalid module_key → 400."""
        body = BatchPolicyRequest(policies=[
            ModulePolicyItem(module_key="nonexistent"),
        ])
        with pytest.raises(HTTPException) as exc_info:
            set_org_policies(1, body, db=mock_db, current_user=admin_user)
        assert exc_info.value.status_code == 400

    def test_set_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        body = BatchPolicyRequest(policies=[])
        with pytest.raises(HTTPException) as exc_info:
            set_org_policies(1, body, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403

    @patch(
        "app.api.v1.org_module_policy.write_work_log",
        side_effect=Exception("fail"),
    )
    def test_set_work_log_exception(self, mock_wl, mock_db, admin_user):
        """write_work_log failure is swallowed."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        body = BatchPolicyRequest(policies=[
            ModulePolicyItem(module_key="funds"),
        ])
        result = set_org_policies(1, body, db=mock_db, current_user=admin_user)
        assert result["data"]["updated"] == 1


class TestResetOrgPolicy:
    def test_reset_existing(self, mock_db, admin_user):
        """Lines 153-164: reset existing policy."""
        policy = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = policy
        result = reset_org_policy(1, "funds", db=mock_db, current_user=admin_user)
        assert result["message"] == "已重置为默认策略"
        mock_db.delete.assert_called_once_with(policy)
        mock_db.commit.assert_called()

    def test_reset_nonexistent(self, mock_db, admin_user):
        """Reset when no policy exists → still success."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = reset_org_policy(1, "funds", db=mock_db, current_user=admin_user)
        assert result["message"] == "已重置为默认策略"
        mock_db.delete.assert_not_called()

    def test_reset_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        with pytest.raises(HTTPException) as exc_info:
            reset_org_policy(1, "funds", db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403


class TestExportOrgPolicies:
    def test_export_with_data(self, mock_db, admin_user):
        """Lines 174-181: export policies."""
        p = MagicMock()
        p.module_key = "funds"
        p.visibility = "visible"
        p.edit_mode = "full_edit"
        mock_db.query.return_value.filter.return_value.all.return_value = [p]

        result = export_org_policies(1, db=mock_db, current_user=admin_user)
        assert len(result["data"]) == 1
        assert result["data"][0]["module_key"] == "funds"

    def test_export_empty(self, mock_db, admin_user):
        """Export with no policies."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = export_org_policies(1, db=mock_db, current_user=admin_user)
        assert result["data"] == []

    def test_export_forbidden(self, mock_db, regular_user):
        """Non-admin → 403."""
        with pytest.raises(HTTPException) as exc_info:
            export_org_policies(1, db=mock_db, current_user=regular_user)
        assert exc_info.value.status_code == 403
