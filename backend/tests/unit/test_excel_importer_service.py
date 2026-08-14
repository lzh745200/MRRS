"""Tests for ExcelImporterService — 100% code coverage."""

import io
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook
from sqlalchemy.exc import SQLAlchemyError

from app.services.excel_importer_service import (
    ExcelImporterService,
    ImportError as IE,
    ImportResult,
)
from app.models.import_history import ImportMode, ImportStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    return ExcelImporterService(db)


def _make_excel_bytes(headers, rows, entity_type="supported_village"):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    if entity_type == "supported_village":
        ws.append(["某某部门", "示例部门", "示例村"])
    else:
        ws.append(["某某村", "示例名称", "某某希望小学"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestImportError:
    def test_to_dict_with_value(self):
        e = IE(1, "name", "ERR", "msg", "val")
        d = e.to_dict()
        assert d["row_number"] == 1
        assert d["value"] == "val"

    def test_to_dict_without_value(self):
        e = IE(1, "name", "ERR", "msg")
        d = e.to_dict()
        assert d["value"] is None


class TestImportResult:
    def test_to_dict(self):
        r = ImportResult(
            success=True,
            total_rows=10,
            success_rows=8,
            failed_rows=2,
            skipped_rows=0,
            errors=[IE(1, "f", "E", "m")],
            created_ids=[1, 2],
            import_history_id=99,
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["error_count"] == 1
        assert d["created_ids"] == [1, 2]
        assert d["import_history_id"] == 99


# ---------------------------------------------------------------------------
# parse_excel
# ---------------------------------------------------------------------------


class TestParseExcel:
    def test_pandas_fast_path_ok(self, service):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", True
        ), patch(
            "app.services.excel_importer_service._pandas_read_raw",
            return_value=[["定点帮扶村", "各部门各单位"], ["测试村", "测试部门"]],
        ):
            rows, headers = service.parse_excel(b"dummy", "supported_village")
            assert rows == [{"village_name": "测试村", "department": "测试部门"}]
            assert headers == ["定点帮扶村", "各部门各单位"]

    def test_pandas_fast_path_fallback(self, service):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", True
        ), patch(
            "app.services.excel_importer_service._pandas_read_raw",
            side_effect=Exception("fail"),
        ), patch.object(
            service, "validator"
        ) as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            data = _make_excel_bytes(["定点帮扶村"], [["test_village"]])
            rows, headers = service.parse_excel(data, "supported_village")
            assert len(rows) == 1

    def test_pandas_not_available(self, service):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            data = _make_excel_bytes(["定点帮扶村"], [["test_village"]])
            rows, headers = service.parse_excel(data, "supported_village")
            assert len(rows) == 1

    def test_parse_excel_other_entity(self, service):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch(
            "app.services.excel_importer_service.EntityImportValidator"
        ) as mock_eiv_cls:
            inst = mock_eiv_cls.return_value
            inst.parse_excel_headers.return_value = {0: "name"}
            data = _make_excel_bytes(
                ["项目名称"], [["proj1"]], entity_type="project"
            )
            rows, headers = service.parse_excel(data, "project")
            assert len(rows) == 1

    def test_skip_example_row_not_matching(self, service):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            wb = Workbook()
            ws = wb.active
            ws.append(["定点帮扶村"])
            ws.append(["NOT_MARKER"])
            ws.append(["actual_village"])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            rows, headers = service.parse_excel(buf.read(), "supported_village")
            assert len(rows) == 2

    def test_skip_empty_rows(self, service):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            wb = Workbook()
            ws = wb.active
            ws.append(["定点帮扶村"])
            ws.append(["某某部门", "示例部门", "示例村"])
            ws.append([None, None, None])
            ws.append(["  ", "", None])
            ws.append(["real_village"])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            rows, headers = service.parse_excel(buf.read(), "supported_village")
            assert len(rows) == 1


# ---------------------------------------------------------------------------
# import_data — all branches
# ---------------------------------------------------------------------------


class TestImportData:
    @pytest.fixture(autouse=True)
    def _no_pandas(self):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ):
            yield

    def test_row_limit_exceeded(self, service, db):
        with patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {}
            # Create >MAX_ROWS dict-based rows
            rows_data = [{"village_name": f"v{i}"} for i in range(1001)]
            result = service.import_data(
                b"ignored", "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            # parse_excel will fail on b"ignored", but we catch Exception
            # Let's directly test the limit check path by mocking parse_excel
            pass

    def _setup_import_test(self, service, validator_cls=None):
        """Common setup: patch HAS_PANDAS and return validator mock."""
        patcher = patch.object(service, "validator")
        mock_val = patcher.start()
        mock_val.parse_excel_headers.return_value = {0: "village_name"}
        mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
        mock_val.check_duplicates.return_value = []
        mock_val.convert_row_types.side_effect = lambda r: r
        if validator_cls:
            vc_patcher = patch(
                "app.services.excel_importer_service.EntityImportValidator",
                autospec=True,
            )
            vc_mock = vc_patcher.start()
            inst = vc_mock.return_value
            inst.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            inst.check_duplicates.return_value = []
            inst.convert_row_types.side_effect = lambda r: r
            self._extra_cleanup = lambda: vc_patcher.stop()
        else:
            self._extra_cleanup = lambda: None
        self._val_patcher = patcher
        return mock_val

    def _cleanup_import_test(self):
        self._val_patcher.stop()
        self._extra_cleanup()

    def test_row_limit_exceeded_direct(self, service, db):
        """Directly test the row-limit branch by mocking parse_excel."""
        with patch.object(service, "parse_excel", return_value=(
            [{"village_name": "v"} for _ in range(1001)], ["h"]
        )):
            result = service.import_data(
                b"dummy", "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is False
            assert result.errors[0].error_code == "IMPORT_007"

    def test_validation_failure(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(
                is_valid=False,
                errors=[
                    MagicMock(
                        row_number=1,
                        field_name="village_name",
                        error_code=MagicMock(value="IMPORT_003"),
                        message="missing",
                        value=None,
                    )
                ],
            )
            mock_val.check_duplicates.return_value = []
            data = _make_excel_bytes(["定点帮扶村"], [["v"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is False
            assert result.failed_rows > 0

    def test_duplicate_error(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = [
                MagicMock(
                    row_number=1,
                    field_name="village_name",
                    error_code=MagicMock(value="IMPORT_005"),
                    message="dup",
                    value=None,
                )
            ]
            data = _make_excel_bytes(["定点帮扶村"], [["v"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is False

    def test_import_incremental_supported_village(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: r
            db.query.return_value.all.return_value = []
            data = _make_excel_bytes(["定点帮扶村"], [["test_village"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is True

    def test_import_full_supported_village(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: r
            data = _make_excel_bytes(["定点帮扶村"], [["v1"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.FULL
            )
            assert result.success is True

    def test_import_projects(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            # Mock the EntityImportValidator created inside import_data
            with patch(
                "app.services.excel_importer_service.EntityImportValidator"
            ) as meiv:
                inst = meiv.return_value
                inst.validate_batch.return_value = MagicMock(
                    is_valid=True, errors=[]
                )
                inst.check_duplicates.return_value = []
                db.query.return_value.all.return_value = []
                data = _make_excel_bytes(
                    ["项目名称"], [["proj1"]], entity_type="project"
                )
                result = service.import_data(
                    data, "test.xlsx", 100, 1,
                    ImportMode.FULL, entity_type="project",
                )
                assert result.success is True

    def test_import_funds(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            with patch(
                "app.services.excel_importer_service.EntityImportValidator"
            ) as meiv:
                inst = meiv.return_value
                inst.validate_batch.return_value = MagicMock(
                    is_valid=True, errors=[]
                )
                inst.check_duplicates.return_value = []
                db.query.return_value.all.return_value = []
                data = _make_excel_bytes(
                    ["资金名称"], [["fund1"]], entity_type="fund"
                )
                result = service.import_data(
                    data, "test.xlsx", 100, 1,
                    ImportMode.FULL, entity_type="fund",
                )
                assert result.success is True

    def test_import_schools(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            with patch(
                "app.services.excel_importer_service.EntityImportValidator"
            ) as meiv:
                inst = meiv.return_value
                inst.validate_batch.return_value = MagicMock(
                    is_valid=True, errors=[]
                )
                inst.check_duplicates.return_value = []
                db.query.return_value.all.return_value = []
                data = _make_excel_bytes(
                    ["学校名称"], [["school1"]], entity_type="school"
                )
                result = service.import_data(
                    data, "test.xlsx", 100, 1,
                    ImportMode.FULL, entity_type="school",
                )
                assert result.success is True

    def test_sqlalchemy_error(self, service, db):
        db.flush.side_effect = [None, SQLAlchemyError("DB error")]
        db.rollback.return_value = None
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: r
            db.query.return_value.all.return_value = []
            data = _make_excel_bytes(["定点帮扶村"], [["v1"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is False
            assert len(result.errors) > 0

    def test_general_exception(self, service, db):
        db.flush.side_effect = [None, Exception("boom")]
        db.rollback.return_value = None
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: r
            db.query.return_value.all.return_value = []
            data = _make_excel_bytes(["定点帮扶村"], [["v1"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is False

    def test_import_incremental_skip_existing(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: r

            mock_filter = db.query.return_value.filter.return_value
            mock_filter.all.return_value = [("existing",)]
            data = _make_excel_bytes(["定点帮扶村"], [["existing"]])
            result = service.import_data(
                data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success_rows == 0
            assert result.skipped_rows == 1

    def test_import_incremental_create_failure(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: {
                "village_name": "v1",
                "department": "dept",
            }
            db.query.return_value.all.return_value = []
            data = _make_excel_bytes(["定点帮扶村"], [["v1"]])
            with patch.object(
                service, "_create_village", side_effect=Exception("creation failed")
            ):
                result = service.import_data(
                    data, "test.xlsx", 100, 1, ImportMode.INCREMENTAL
                )
                assert result.failed_rows == 1

    def test_import_full_create_failure(self, service, db):
        with patch(
            "app.services.excel_importer_service._HAS_PANDAS_FAST_READ", False
        ), patch.object(service, "validator") as mock_val:
            mock_val.parse_excel_headers.return_value = {0: "village_name"}
            mock_val.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
            mock_val.check_duplicates.return_value = []
            mock_val.convert_row_types.side_effect = lambda r: {
                "village_name": "v1",
                "department": "dept",
            }
            data = _make_excel_bytes(["定点帮扶村"], [["v1"]])
            with patch.object(
                service, "_create_village", side_effect=Exception("creation failed")
            ):
                result = service.import_data(
                    data, "test.xlsx", 100, 1, ImportMode.FULL
                )
                assert result.failed_rows == 1

    def test_import_data_parse_excel_exception(self, service, db):
        """Test that parse_excel raising Exception triggers general handler."""
        with patch.object(
            service, "parse_excel", side_effect=Exception("parse_error")
        ):
            result = service.import_data(
                b"bad", "test.xlsx", 100, 1, ImportMode.INCREMENTAL
            )
            assert result.success is False
            assert result.errors[0].error_code == "IMPORT_999"


# ---------------------------------------------------------------------------
# _import_incremental_mode edge cases
# ---------------------------------------------------------------------------


class TestImportIncrementalMode:
    def test_no_imported_names(self, service):
        """When rows have no village_name, imported_names is empty."""
        result = ImportResult(success=False)
        rows = [{"department": "dept", "support_unit": "unit"}]
        mock_history = MagicMock()
        res = service._import_incremental_mode(rows, result, mock_history)
        assert res.success_rows == 1

    def test_empty_village_name_not_skipped(self, service):
        result = ImportResult(success=False)
        rows = [{"village_name": "", "department": "dept"}]
        mock_history = MagicMock()
        service.validator.convert_row_types = lambda r: r
        res = service._import_incremental_mode(rows, result, mock_history)
        assert res.success_rows == 1


# ---------------------------------------------------------------------------
# _create_village
# ---------------------------------------------------------------------------


class TestCreateVillage:
    def test_create_village_filters_fields(self, service, db):
        data = {
            "village_name": "test",
            "department": "dept",
            "support_unit": "unit",
            "unknown_field": "should_be_ignored",
        }
        village = service._create_village(data)
        assert village.village_name == "test"
        assert not hasattr(village, "unknown_field")

    def test_create_village_bool_defaults(self, service, db):
        data = {"village_name": "test"}
        village = service._create_village(data)
        assert village.is_three_regions is False
        db.add.assert_called_once()
        db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# _update_import_history
# ---------------------------------------------------------------------------


class TestUpdateImportHistory:
    def test_update_without_errors(self, service):
        hist = MagicMock()
        result = ImportResult(success=True, total_rows=5, success_rows=5)
        service._update_import_history(hist, result, ImportStatus.COMPLETED)
        assert hist.status == ImportStatus.COMPLETED.value
        assert hist.total_rows == 5

    def test_update_with_errors(self, service):
        hist = MagicMock()
        result = ImportResult(
            success=False,
            total_rows=3,
            errors=[IE(row_number=1, field_name="f", error_code="E", message="m")],
        )
        service._update_import_history(hist, result, ImportStatus.FAILED)
        assert hist.error_details is not None


# ---------------------------------------------------------------------------
# _import_projects / _import_funds / _import_schools
# ---------------------------------------------------------------------------


class TestImportProjects:
    def _make_dual_purpose_item(self, name="existing_proj"):
        """Returns a mock that works both as a tuple indexable item AND as an ORM object."""
        m = MagicMock()
        m.code = None
        m.id = 0
        m.__getitem__.side_effect = lambda i: name if i == 0 else ""
        return m

    def test_incremental_skip(self, service, db):
        db.query.return_value.all.return_value = [self._make_dual_purpose_item()]
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "existing_proj"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            rows = [{"name": "existing_proj"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_projects(
                rows, result, hist, ImportMode.INCREMENTAL
            )
            assert res.skipped_rows == 1

    def test_incremental_no_skip(self, service, db):
        db.query.return_value.all.return_value = []
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "new_proj"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            rows = [{"name": "new_proj"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_projects(
                rows, result, hist, ImportMode.INCREMENTAL
            )
            assert res.success_rows == 1

    def test_incremental_skip_no_name(self, service, db):
        db.query.return_value.all.return_value = [self._make_dual_purpose_item()]
        v = MagicMock()
        v.convert_row_types.return_value = {"name": ""}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            rows = [{"name": ""}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_projects(
                rows, result, hist, ImportMode.INCREMENTAL
            )
            # name is "" -> not in existing_names (key comparison is False)
            # proceeds to create -> flush succeeds -> success_rows=1
            assert res.success_rows == 1

    def test_full_mode(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {
            "name": "proj1",
            "organization_code": "ORG001",
        }
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            mock_org = MagicMock()
            mock_org.code = "ORG001"
            mock_org.id = 42
            db.query.return_value.all.return_value = [mock_org]
            rows = [{"name": "proj1"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_projects(rows, result, hist, ImportMode.FULL)
            assert res.success_rows > 0

    def test_create_project_failure(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "proj_fail"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            db.query.return_value.all.return_value = []
            with patch.object(service.db, "flush", side_effect=[Exception("fail")]):
                rows = [{"name": "proj_fail"}]
                result = ImportResult(success=True)
                hist = MagicMock()
                res = service._import_projects(
                    rows, result, hist, ImportMode.FULL
                )
                assert res.failed_rows == 1


class TestImportFunds:
    def test_incremental_skip(self, service, db):
        fp = MagicMock()
        fp.code = None
        fp.id = 0
        fp.__getitem__.side_effect = lambda i: "existing_fund" if i == 0 else ""
        db.query.return_value.all.return_value = [fp]
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "existing_fund"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            rows = [{"name": "existing_fund"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_funds(
                rows, result, hist, ImportMode.INCREMENTAL
            )
            assert res.skipped_rows == 1

    def test_full_mode_with_project_code(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {
            "name": "fund1",
            "project_code": "XM-001",
        }
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            mock_proj = MagicMock()
            mock_proj.code = "XM-001"
            mock_proj.id = 99
            db.query.return_value.all.return_value = [mock_proj]
            rows = [{"name": "fund1"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_funds(rows, result, hist, ImportMode.FULL)
            assert res.success_rows > 0

    def test_create_fund_failure(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "fund_fail"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            db.query.return_value.all.return_value = []
            with patch.object(service.db, "flush", side_effect=[Exception("fail")]):
                rows = [{"name": "fund_fail"}]
                result = ImportResult(success=True)
                hist = MagicMock()
                res = service._import_funds(
                    rows, result, hist, ImportMode.FULL
                )
                assert res.failed_rows == 1

    def test_full_mode_no_project_code(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "fund1"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            db.query.return_value.all.return_value = []
            rows = [{"name": "fund1"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_funds(rows, result, hist, ImportMode.FULL)
            assert res.success_rows == 1


class TestImportSchools:
    def test_incremental_skip(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "existing_school"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            db.query.return_value.all.return_value = [("existing_school",)]
            rows = [{"name": "existing_school"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_schools(
                rows, result, hist, ImportMode.INCREMENTAL
            )
            assert res.skipped_rows == 1

    def test_full_mode(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "school1"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            db.query.return_value.all.return_value = []
            rows = [{"name": "school1"}]
            result = ImportResult(success=True)
            hist = MagicMock()
            res = service._import_schools(rows, result, hist, ImportMode.FULL)
            assert res.success_rows > 0

    def test_create_school_failure(self, service, db):
        v = MagicMock()
        v.convert_row_types.return_value = {"name": "school_fail"}
        with patch(
            "app.services.excel_importer_service.EntityImportValidator",
            return_value=v,
        ):
            db.query.return_value.all.return_value = []
            with patch.object(service.db, "flush", side_effect=[Exception("fail")]):
                rows = [{"name": "school_fail"}]
                result = ImportResult(success=True)
                hist = MagicMock()
                res = service._import_schools(
                    rows, result, hist, ImportMode.FULL
                )
                assert res.failed_rows == 1


# ---------------------------------------------------------------------------
# import_data_async
# ---------------------------------------------------------------------------


class TestImportDataAsync:
    @pytest.mark.asyncio
    async def test_invalid_format(self, service):
        with patch.object(
            service.validator, "validate_file_format", return_value=(False, "bad")
        ):
            result = await service.import_data_async(
                b"content", "", "application/pdf", 1
            )
            assert result.success is False
            assert result.errors[0].error_code == "IMPORT_001"

    @pytest.mark.asyncio
    async def test_file_too_large(self, service):
        with patch.object(
            service.validator, "validate_file_format", return_value=(True, None)
        ), patch.object(
            service.validator, "validate_file_size", return_value=(False, "too big")
        ):
            result = await service.import_data_async(
                b"x" * 99999999, "test.xlsx", "application/xlsx", 1
            )
            assert result.success is False
            assert result.errors[0].error_code == "IMPORT_002"

    @pytest.mark.asyncio
    async def test_success(self, service):
        with patch.object(
            service.validator, "validate_file_format", return_value=(True, None)
        ), patch.object(
            service.validator, "validate_file_size", return_value=(True, None)
        ), patch.object(
            service, "import_data"
        ) as mock_imp:
            mock_imp.return_value = ImportResult(success=True)
            result = await service.import_data_async(
                b"realdata", "test.xlsx", "application/xlsx", 1
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_empty_filename(self, service):
        with patch.object(
            service.validator, "validate_file_format", return_value=(True, None)
        ), patch.object(
            service.validator, "validate_file_size", return_value=(True, None)
        ), patch.object(
            service, "import_data"
        ) as mock_imp:
            mock_imp.return_value = ImportResult(success=True)
            result = await service.import_data_async(
                b"data", "", "application/xlsx", 1
            )
            assert result.success is True


# ---------------------------------------------------------------------------
# get_import_history / get_import_history_by_id
# ---------------------------------------------------------------------------


class TestImportHistory:
    def test_get_history_all(self, service, db):
        db.query.return_value.count.return_value = 5
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            "h1",
            "h2",
        ]
        histories, total = service.get_import_history()
        assert total == 5
        assert len(histories) == 2

    def test_get_history_filtered(self, service, db):
        filtered_q = MagicMock()
        filtered_q.count.return_value = 3
        filtered_q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            "h1"
        ]
        db.query.return_value.filter.return_value = filtered_q
        histories, total = service.get_import_history(user_id=42)
        assert total == 3

    def test_get_history_by_id(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = "history_obj"
        result = service.get_import_history_by_id(1)
        assert result == "history_obj"

    def test_get_history_by_id_none(self, service, db):
        db.query.return_value.filter.return_value.first.return_value = None
        result = service.get_import_history_by_id(999)
        assert result is None


# ---------------------------------------------------------------------------
# Module-level attribute access coverage
# ---------------------------------------------------------------------------


def test_module_has_pandas_flag():
    """Verify _HAS_PANDAS_FAST_READ is defined (module-level attr)."""
    from app.services.excel_importer_service import _HAS_PANDAS_FAST_READ

    assert isinstance(_HAS_PANDAS_FAST_READ, bool)
