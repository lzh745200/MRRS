"""Tests for import_export/import_data.py — data import API."""
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.core.database import get_db

BASE = "/api/v1/import"


class TestDownloadImportTemplate:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/template")
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelTemplateService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.generate_village_template.return_value = b"xlsx_content"
            mock_svc_cls.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/template", params={"entity_type": "supported_village"})
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            assert resp.content == b"xlsx_content"

    def test_invalid_entity_type(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/template", params={"entity_type": "invalid"})
        assert resp.status_code == 400

    def test_project_template(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelTemplateService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.generate_project_template.return_value = b"project_xlsx"
            mock_svc_cls.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/template", params={"entity_type": "project"})
            assert resp.status_code == 200
            mock_svc.generate_project_template.assert_called_once()

    def test_fund_template(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelTemplateService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.generate_fund_template.return_value = b"fund_xlsx"
            mock_svc_cls.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/template", params={"entity_type": "fund"})
            assert resp.status_code == 200

    def test_school_template(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelTemplateService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.generate_school_template.return_value = b"school_xlsx"
            mock_svc_cls.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/template", params={"entity_type": "school"})
            assert resp.status_code == 200

    def test_policy_template(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelTemplateService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.generate_policy_template.return_value = b"policy_xlsx"
            mock_svc_cls.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/template", params={"entity_type": "policy"})
            assert resp.status_code == 200


class TestImportVillages:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/villages")
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "success": True, "total_rows": 10, "success_rows": 10,
            "failed_rows": 0, "skipped_rows": 0, "error_count": 0,
            "errors": [], "created_ids": [1, 2, 3],
        }

        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.import_data_async = AsyncMock(return_value=mock_result)
            mock_svc_cls.return_value = mock_svc

            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.post(
                    f"{BASE}/villages",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"mode": "incremental"},
                )
                assert resp.status_code == 200
                assert resp.json()["success_rows"] == 10

    def test_invalid_mode(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/villages",
            files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            params={"mode": "invalid"},
        )
        assert resp.status_code == 400


class TestImportEntities:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/entities")
        assert resp.status_code == 401

    def test_success_incremental(self, client_with_mocked_auth):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "success": True, "total_rows": 5, "success_rows": 5,
            "failed_rows": 0, "skipped_rows": 0, "error_count": 0,
            "errors": [], "created_ids": [1, 2],
        }

        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.import_data_async = AsyncMock(return_value=mock_result)
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.post(
                    f"{BASE}/entities",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"mode": "incremental", "entity_type": "project"},
                )
                assert resp.status_code == 200
                assert resp.json()["success"] is True

    def test_dry_run_mode(self, client_with_mocked_auth):
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "success": True, "total_rows": 5, "success_rows": 5,
            "failed_rows": 0, "skipped_rows": 0, "error_count": 0,
            "errors": [], "created_ids": [],
        }

        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            with patch("app.core.database.SessionLocal") as mock_session_cls:
                mock_dry_db = MagicMock()
                mock_session_cls.return_value = mock_dry_db
                mock_svc = MagicMock()
                mock_svc.import_data_async = AsyncMock(return_value=mock_result)
                mock_svc_cls.return_value = mock_svc
                resp = client_with_mocked_auth.post(
                    f"{BASE}/entities",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"mode": "incremental", "entity_type": "fund", "dry_run": "true"},
                )
                assert resp.status_code == 200
                mock_svc.import_data_async.assert_called_once()
                assert mock_dry_db.close.called

    def test_empty_filename(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/entities",
            files={"file": b"data"},
            params={"mode": "incremental"},
        )
        assert resp.status_code == 400

    def test_invalid_file_format(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/entities",
            files={"file": ("data.txt", b"data", "text/plain")},
            params={"mode": "incremental"},
        )
        assert resp.status_code == 400

    def test_invalid_entity_type(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/entities",
            files={"file": ("data.xlsx", b"data", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            params={"mode": "incremental", "entity_type": "invalid"},
        )
        assert resp.status_code == 400


class TestValidateImportData:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/validate")
        assert resp.status_code == 401

    def test_empty_filename(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate",
            files={"file": b""},
        )
        assert resp.status_code == 400

    def test_invalid_entity_type(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate",
            files={"file": ("data.xlsx", b"data", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            params={"entity_type": "invalid"},
        )
        assert resp.status_code == 400

    def test_village_validation_success(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.parse_excel_headers.return_value = {0: "village_name", 1: "county"}
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")
        mock_validator.validate_import_data.return_value = {"is_valid": True}
        mock_validator.get_validation_summary.return_value = {
            "is_valid": True, "total_rows": 0, "valid_rows": 0,
            "invalid_rows": 0, "error_count": 0, "warning_count": 0,
            "errors_by_type": {}, "errors_by_field": {},
            "warnings": [], "first_errors": [],
        }

        with patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            with patch("openpyxl.load_workbook") as mock_load:
                mock_wb = MagicMock()
                mock_ws = MagicMock()
                mock_ws.iter_rows.return_value = [["name", "county"], ["test", "都匀市"]]
                mock_load.return_value = mock_wb
                mock_wb.active = mock_ws
                resp = client_with_mocked_auth.post(
                    f"{BASE}/validate",
                    files={"file": ("data.xlsx", b"binary", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "supported_village", "validate_county": "true", "validate_tiered_level": "true"},
                )
                assert resp.status_code == 200
                assert resp.json()["is_valid"] is True

    def test_invalid_file_format(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (False, "不支持的文件格式")

        with patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            resp = client_with_mocked_auth.post(
                f"{BASE}/validate",
                files={"file": ("bad.xlsx", b"bad", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                params={"entity_type": "supported_village"},
            )
            assert resp.status_code == 400

    def test_file_too_large(self, client_with_mocked_auth):
        """R2：体积闸门前移到分块读取（原 validator.validate_file_size 事后校验
        已被 read_upload_with_limit 取代，避免先整包入内存再拒绝）。"""
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (True, "")

        import app.api.v1.import_export.import_data as id_module

        with patch.object(id_module, "_IMPORT_MAX_FILE_SIZE", 16), \
                patch.object(id_module, "_IMPORT_MAX_FILE_SIZE_MSG", "文件大小超过限制"), \
                patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            resp = client_with_mocked_auth.post(
                f"{BASE}/validate",
                files={"file": ("large.xlsx", b"x" * 100, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                params={"entity_type": "supported_village"},
            )
            assert resp.status_code == 400
            assert "文件大小超过限制" in resp.json()["detail"]

    def test_entity_type_project_validation(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.parse_excel_headers.return_value = {0: "name"}
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")
        mock_validator.validate_batch.return_value = MagicMock(
            is_valid=True, total_rows=5, valid_rows=5,
            errors=[], warnings=[]
        )

        with patch("app.api.v1.import_export.import_data.EntityImportValidator", return_value=mock_validator):
            with patch("openpyxl.load_workbook") as mock_load:
                mock_wb = MagicMock()
                mock_ws = MagicMock()
                mock_ws.iter_rows.return_value = [["name"], ["test"]]
                mock_load.return_value = mock_wb
                mock_wb.active = mock_ws
                resp = client_with_mocked_auth.post(
                    f"{BASE}/validate",
                    files={"file": ("data.xlsx", b"binary", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "project"},
                )
                assert resp.status_code == 200

    def test_parse_error(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")

        with patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            with patch("openpyxl.load_workbook", side_effect=Exception("corrupt file")):
                resp = client_with_mocked_auth.post(
                    f"{BASE}/validate",
                    files={"file": ("bad.xlsx", b"bad", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "supported_village"},
                )
                assert resp.status_code == 400


class TestPreviewImportData:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/preview")
        assert resp.status_code == 401

    def test_empty_filename(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/preview",
            files={"file": b""},
        )
        assert resp.status_code == 400

    def test_invalid_entity_type(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/preview",
            files={"file": ("data.xlsx", b"data", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            params={"entity_type": "invalid"},
        )
        assert resp.status_code == 400

    def test_success_village(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")
        mock_validator.validate_row.return_value = []
        mock_validator._generate_warnings.return_value = []

        mock_importer = MagicMock()
        mock_importer.parse_excel.return_value = ([{"village_name": "示范村", "county": "都匀市"}], ["village_name"])

        with patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            with patch("app.api.v1.import_export.import_data.ExcelImporterService", return_value=mock_importer):
                mock_db = MagicMock()
                mock_db.query.return_value.all.return_value = []
                client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
                resp = client_with_mocked_auth.post(
                    f"{BASE}/preview",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "supported_village"},
                )
                assert resp.status_code == 200
                assert resp.json()["total_rows"] == 1
                assert resp.json()["valid_rows"] == 1

    def test_success_with_duplicates(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")
        mock_validator.validate_row.return_value = []
        mock_validator._generate_warnings.return_value = ["some warning"]

        mock_importer = MagicMock()
        mock_importer.parse_excel.return_value = (
            [{"village_name": "existing村", "county": "都匀市"}],
            ["village_name"],
        )

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = [("existing村",)]

        with patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            with patch("app.api.v1.import_export.import_data.ExcelImporterService", return_value=mock_importer):
                client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
                resp = client_with_mocked_auth.post(
                    f"{BASE}/preview",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "supported_village"},
                )
                assert resp.status_code == 200
                assert resp.json()["duplicate_in_db_rows"] == 1
                assert len(resp.json()["warnings"]) > 0

    def test_project_preview(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")
        mock_validator.validate_row.return_value = []
        mock_validator._generate_warnings.return_value = []
        mock_validator.config = {"duplicate_key": "name"}

        mock_importer = MagicMock()
        mock_importer.parse_excel.return_value = ([{"name": "项目1"}], ["name"])

        with patch("app.api.v1.import_export.import_data.EntityImportValidator", return_value=mock_validator):
            with patch("app.api.v1.import_export.import_data.ExcelImporterService", return_value=mock_importer):
                mock_db = MagicMock()
                mock_db.query.return_value.all.return_value = []
                client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
                resp = client_with_mocked_auth.post(
                    f"{BASE}/preview",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "project"},
                )
                assert resp.status_code == 200

    def test_parse_error(self, client_with_mocked_auth):
        mock_validator = MagicMock()
        mock_validator.validate_file_format.return_value = (True, "")
        mock_validator.validate_file_size.return_value = (True, "")

        with patch("app.api.v1.import_export.import_data.DataValidatorService", return_value=mock_validator):
            with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc.parse_excel.side_effect = Exception("parse failed")
                mock_svc_cls.return_value = mock_svc
                client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: MagicMock()
                resp = client_with_mocked_auth.post(
                    f"{BASE}/preview",
                    files={"file": ("data.xlsx", b"xlsxdata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    params={"entity_type": "supported_village"},
                )
                assert resp.status_code == 400


class TestGetImportHistory:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        mock_history = MagicMock()
        mock_history.id = 1
        mock_history.user_id = 1
        mock_history.file_name = "import.xlsx"
        mock_history.file_size = 1024
        mock_history.import_mode = "incremental"
        mock_history.entity_type = "supported_village"
        mock_history.status = "completed"
        mock_history.total_rows = 10
        mock_history.success_rows = 10
        mock_history.failed_rows = 0
        mock_history.started_at = None
        mock_history.completed_at = None
        mock_history.created_at = datetime(2024, 1, 1, 12, 0, 0)

        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_import_history.return_value = ([mock_history], 1)
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.get(f"{BASE}/history")
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["total"] == 1
                assert len(data["items"]) == 1
                assert data["items"][0]["id"] == 1

    def test_empty(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_import_history.return_value = ([], 0)
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.get(f"{BASE}/history")
                assert resp.status_code == 200
                assert resp.json()["data"]["total"] == 0

    def test_pagination_params(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_import_history.return_value = ([], 0)
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.get(f"{BASE}/history", params={"page": 2, "page_size": 10})
                assert resp.status_code == 200
                _, kwargs = mock_svc.get_import_history.call_args
                assert kwargs["page"] == 2
                assert kwargs["page_size"] == 10


class TestGetImportHistoryDetail:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/history/1")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_import_history_by_id.return_value = None
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.get(f"{BASE}/history/999")
                assert resp.status_code == 404

    def test_other_user_forbidden(self, client_with_regular_user_auth):
        mock_history = MagicMock()
        mock_history.id = 1
        mock_history.user_id = 999  # different from regular_user (id=2)
        mock_history.file_name = "import.xlsx"
        mock_history.file_size = 1024
        mock_history.import_mode = "incremental"
        mock_history.entity_type = "supported_village"
        mock_history.status = "completed"
        mock_history.total_rows = 10
        mock_history.success_rows = 10
        mock_history.failed_rows = 0
        mock_history.started_at = None
        mock_history.completed_at = None
        mock_history.created_at = datetime(2024, 1, 1, 12, 0, 0)

        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_import_history_by_id.return_value = mock_history
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_regular_user_auth.get(f"{BASE}/history/1")
                assert resp.status_code == 403

    def test_success_own_record(self, client_with_mocked_auth):
        mock_history = MagicMock()
        mock_history.id = 1
        mock_history.user_id = 1  # matches admin user id
        mock_history.file_name = "import.xlsx"
        mock_history.file_size = 1024
        mock_history.import_mode = "incremental"
        mock_history.entity_type = "supported_village"
        mock_history.status = "completed"
        mock_history.total_rows = 10
        mock_history.success_rows = 10
        mock_history.failed_rows = 0
        mock_history.started_at = None
        mock_history.completed_at = None
        mock_history.created_at = datetime(2024, 1, 1, 12, 0, 0)

        with patch("app.api.v1.import_export.import_data.ExcelImporterService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_import_history_by_id.return_value = mock_history
            mock_svc_cls.return_value = mock_svc
            with patch("app.api.v1.import_export.import_data.get_db") as mock_get_db:
                mock_get_db.return_value = MagicMock()
                resp = client_with_mocked_auth.get(f"{BASE}/history/1")
                assert resp.status_code == 200
                assert resp.json()["id"] == 1
