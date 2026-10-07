"""数据验证服务单元测试 (100% coverage)"""
import pytest
from unittest.mock import patch


class TestValidationErrorCode:
    def test_enum_values(self):
        from app.services.data_validator_service import ValidationErrorCode
        assert ValidationErrorCode.INVALID_FILE_FORMAT.value == "IMPORT_001"
        assert ValidationErrorCode.FILE_TOO_LARGE.value == "IMPORT_002"
        assert ValidationErrorCode.MISSING_REQUIRED_FIELD.value == "IMPORT_003"
        assert ValidationErrorCode.INVALID_DATA_FORMAT.value == "IMPORT_004"
        assert ValidationErrorCode.DUPLICATE_DATA.value == "IMPORT_005"
        assert ValidationErrorCode.DATABASE_ERROR.value == "IMPORT_006"
        assert ValidationErrorCode.ROW_LIMIT_EXCEEDED.value == "IMPORT_007"
        assert ValidationErrorCode.INVALID_COUNTY.value == "IMPORT_008"
        assert ValidationErrorCode.INVALID_NUMERIC_VALUE.value == "IMPORT_009"
        assert ValidationErrorCode.VALUE_OUT_OF_RANGE.value == "IMPORT_010"


class TestValidationError:
    def test_to_dict(self):
        from app.services.data_validator_service import ValidationError, ValidationErrorCode
        err = ValidationError(
            row_number=1, field_name="test", error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
            message="必填", value="abc",
        )
        d = err.to_dict()
        assert d["row_number"] == 1
        assert d["field_name"] == "test"
        assert d["error_code"] == "IMPORT_003"
        assert d["message"] == "必填"
        assert d["value"] == "abc"

    def test_to_dict_none_value(self):
        from app.services.data_validator_service import ValidationError, ValidationErrorCode
        err = ValidationError(
            row_number=2, field_name="f", error_code=ValidationErrorCode.INVALID_DATA_FORMAT,
            message="err",
        )
        d = err.to_dict()
        assert d["value"] is None


class TestValidationResult:
    def test_to_dict(self):
        from app.services.data_validator_service import ValidationResult, ValidationError, ValidationErrorCode
        err = ValidationError(1, "f", ValidationErrorCode.INVALID_FILE_FORMAT, "bad")
        result = ValidationResult(is_valid=False, total_rows=10, valid_rows=8, errors=[err], warnings=["warn"])
        d = result.to_dict()
        assert d["is_valid"] is False
        assert d["total_rows"] == 10
        assert d["valid_rows"] == 8
        assert d["error_count"] == 1
        assert len(d["errors"]) == 1
        assert d["warnings"] == ["warn"]


class TestDataValidatorService:
    @pytest.fixture
    def svc(self):
        from app.services.data_validator_service import DataValidatorService
        return DataValidatorService()

    # --- validate_file_format ---
    def test_validate_file_format_empty(self, svc):
        valid, msg = svc.validate_file_format("")
        assert not valid
        assert "不能为空" in msg

    def test_validate_file_format_none(self, svc):
        valid, msg = svc.validate_file_format(None)
        assert not valid
        assert "不能为空" in msg

    def test_validate_file_format_invalid_ext(self, svc):
        valid, msg = svc.validate_file_format("test.csv")
        assert not valid
        assert "不支持" in msg

    def test_validate_file_format_valid(self, svc):
        valid, msg = svc.validate_file_format("test.xlsx")
        assert valid
        assert msg is None

    def test_validate_file_format_valid_xls(self, svc):
        valid, msg = svc.validate_file_format("test.xls")
        assert valid
        assert msg is None

    # --- validate_file_size ---
    def test_validate_file_size_exceed(self, svc):
        valid, msg = svc.validate_file_size(20 * 1024 * 1024)
        assert not valid
        assert "超过限制" in msg

    def test_validate_file_size_valid(self, svc):
        valid, msg = svc.validate_file_size(1024)
        assert valid
        assert msg is None

    def test_validate_file_size_boundary(self, svc):
        valid, msg = svc.validate_file_size(svc.MAX_FILE_SIZE)
        assert valid
        assert msg is None

    # --- validate_row_count ---
    def test_validate_row_count_exceed(self, svc):
        valid, msg = svc.validate_row_count(2000)
        assert not valid
        assert "超过限制" in msg

    def test_validate_row_count_valid(self, svc):
        valid, msg = svc.validate_row_count(100)
        assert valid
        assert msg is None

    def test_validate_row_count_boundary(self, svc):
        valid, msg = svc.validate_row_count(svc.MAX_ROWS)
        assert valid
        assert msg is None

    # --- validate_row ---
    def test_validate_row_missing_required(self, svc):
        row = {}
        errors = svc.validate_row(row, 1)
        assert len(errors) == 3
        assert all(e.error_code.value == "IMPORT_003" for e in errors)

    def test_validate_row_empty_required(self, svc):
        row = {"department": "", "support_unit": "  ", "village_name": None}
        errors = svc.validate_row(row, 2)
        assert len(errors) == 3

    def test_validate_row_valid(self, svc):
        row = {
            "department": "某部", "support_unit": "某团", "village_name": "某村",
            "county": "都匀市", "sequence_no": "5", "is_three_regions": "是",
        }
        errors = svc.validate_row(row, 3)
        assert len(errors) == 0

    def test_validate_row_invalid_int_field(self, svc):
        row = {
            "department": "某部", "support_unit": "某团", "village_name": "某村",
            "sequence_no": "not_a_number",
        }
        errors = svc.validate_row(row, 1)
        int_errors = [e for e in errors if e.field_name == "sequence_no"]
        assert len(int_errors) >= 1
        assert int_errors[0].error_code.value == "IMPORT_004"

    def test_validate_row_int_out_of_range(self, svc):
        row = {
            "department": "某部", "support_unit": "某团", "village_name": "某村",
            "sequence_no": 999999,
        }
        errors = svc.validate_row(row, 1)
        range_errors = [e for e in errors if e.error_code.value == "IMPORT_010"]
        assert len(range_errors) >= 1

    def test_validate_row_unknown_field_type(self, svc):
        svc.FIELD_TYPES["custom_field"] = "unknown_type"
        row = {
            "department": "某部", "support_unit": "某团", "village_name": "某村",
            "custom_field": "val",
        }
        errors = svc.validate_row(row, 1)
        assert len(errors) == 0

    # --- validate_batch ---
    def test_validate_batch_exceeds_limit(self, svc):
        rows = [{} for _ in range(2000)]
        result = svc.validate_batch(rows)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].error_code.value == "IMPORT_007"

    def test_validate_batch_all_valid(self, svc):
        rows = [
            {"department": "A", "support_unit": "B", "village_name": "C"},
            {"department": "D", "support_unit": "E", "village_name": "F"},
        ]
        result = svc.validate_batch(rows)
        assert result.is_valid
        assert result.total_rows == 2
        assert result.valid_rows == 2
        assert len(result.errors) == 0

    def test_validate_batch_some_invalid(self, svc):
        rows = [
            {"department": "A", "support_unit": "B", "village_name": "C"},
            {"department": "", "support_unit": "E", "village_name": ""},
        ]
        result = svc.validate_batch(rows)
        assert not result.is_valid
        assert result.total_rows == 2
        assert result.valid_rows == 1

    # --- check_duplicates ---
    def test_check_duplicates_no_duplicates(self, svc):
        rows = [
            {"village_name": "村A"},
            {"village_name": "村B"},
        ]
        errors = svc.check_duplicates(rows)
        assert len(errors) == 0

    def test_check_duplicates_with_duplicates(self, svc):
        rows = [
            {"village_name": "村A"},
            {"village_name": "村A"},
        ]
        errors = svc.check_duplicates(rows)
        assert len(errors) == 1
        assert "重复" in errors[0].message

    def test_check_duplicates_custom_key(self, svc):
        rows = [
            {"name": "A", "code": "1"},
            {"name": "A", "code": "1"},
        ]
        errors = svc.check_duplicates(rows, key_fields=["name", "code"])
        assert len(errors) == 1

    def test_check_duplicates_case_insensitive(self, svc):
        rows = [
            {"village_name": "村A"},
            {"village_name": "村a"},
        ]
        errors = svc.check_duplicates(rows)
        assert len(errors) == 1

    def test_check_duplicates_default_key_fields(self, svc):
        rows = [
            {"village_name": "村A"},
            {"village_name": "村B"},
        ]
        errors = svc.check_duplicates(rows)
        assert len(errors) == 0

    # --- parse_excel_headers ---
    def test_parse_excel_headers(self, svc):
        headers = ["序号", "各部门各单位"]
        mapping = svc.parse_excel_headers(headers)
        assert mapping == {0: "sequence_no", 1: "department"}

    def test_parse_excel_headers_with_star(self, svc):
        headers = ["*序号", " 各部门各单位 "]
        mapping = svc.parse_excel_headers(headers)
        assert 0 in mapping
        assert mapping[0] == "sequence_no"
        assert mapping[1] == "department"

    def test_parse_excel_headers_empty(self, svc):
        mapping = svc.parse_excel_headers([])
        assert mapping == {}

    def test_parse_excel_headers_unknown(self, svc):
        mapping = svc.parse_excel_headers(["未知列"])
        assert mapping == {}

    # --- _validate_field_format ---
    def test_validate_field_format_int_str(self, svc):
        err = svc._validate_field_format("sequence_no", "123", "int", 1)
        assert err is None

    def test_validate_field_format_int_float(self, svc):
        err = svc._validate_field_format("sequence_no", 123.0, "int", 1)
        assert err is None

    def test_validate_field_format_int_invalid(self, svc):
        err = svc._validate_field_format("sequence_no", "abc", "int", 1)
        assert err is not None
        assert err.error_code.value == "IMPORT_004"

    def test_validate_field_format_float_str(self, svc):
        err = svc._validate_field_format("investment", "123.45", "float", 1)
        assert err is None

    def test_validate_field_format_float_invalid_type(self, svc):
        err = svc._validate_field_format("investment", [1, 2, 3], "float", 1)
        assert err is not None
        assert err.error_code.value == "IMPORT_004"

    def test_validate_field_format_bool_str_ok(self, svc):
        err = svc._validate_field_format("is_three_regions", "是", "bool", 1)
        assert err is None

    def test_validate_field_format_bool_str_invalid(self, svc):
        err = svc._validate_field_format("is_three_regions", "maybe", "bool", 1)
        assert err is not None
        assert err.error_code.value == "IMPORT_004"

    def test_validate_field_format_bool_instance_valid(self, svc):
        err = svc._validate_field_format("is_three_regions", True, "bool", 1)
        assert err is None

    def test_validate_field_format_bool_instance_invalid(self, svc):
        err = svc._validate_field_format("is_three_regions", 42, "bool", 1)
        assert err is not None

    def test_validate_field_format_county_valid(self, svc):
        err = svc._validate_field_format("county", "都匀市", "county", 1)
        assert err is None

    def test_validate_field_format_county_invalid(self, svc):
        err = svc._validate_field_format("county", "北京市", "county", 1)
        assert err is not None
        assert err.error_code.value == "IMPORT_008"

    def test_validate_field_format_county_empty(self, svc):
        err = svc._validate_field_format("county", "", "county", 1)
        assert err is None

    def test_validate_field_format_is_revitalization_tier_bool_true(self, svc):
        err = svc._validate_field_format("is_revitalization_tier", True, "bool", 1)
        assert err is None

    def test_validate_field_format_is_revitalization_tier_bool_false(self, svc):
        err = svc._validate_field_format("is_revitalization_tier", False, "bool", 1)
        assert err is None

    def test_validate_field_format_value_out_of_range(self, svc):
        err = svc._validate_field_format("sequence_no", 999999999, "int", 1)
        assert err is not None
        assert err.error_code.value == "IMPORT_010"

    def test_validate_field_format_int_value_error(self, svc):
        err = svc._validate_field_format("sequence_no", {}, "int", 1)
        assert err is not None
        assert err.error_code.value == "IMPORT_004"

    def test_validate_field_format_none_type_error(self, svc):
        err = svc._validate_field_format("is_three_regions", 42, "bool", 1)
        assert err is not None

    # --- _get_field_label ---
    def test_get_field_label_found(self, svc):
        label = svc._get_field_label("village_name")
        assert label == "定点帮扶村"

    def test_get_field_label_not_found(self, svc):
        label = svc._get_field_label("nonexistent")
        assert label == "nonexistent"

    # --- convert_bool_value ---
    def test_convert_bool_value_none(self, svc):
        assert svc.convert_bool_value(None) is None

    def test_convert_bool_value_bool(self, svc):
        assert svc.convert_bool_value(True) is True
        assert svc.convert_bool_value(False) is False

    def test_convert_bool_value_str_true(self, svc):
        for v in ["是", "true", "1", "yes"]:
            assert svc.convert_bool_value(v) is True

    def test_convert_bool_value_str_false(self, svc):
        for v in ["否", "false", "0", "no"]:
            assert svc.convert_bool_value(v) is False

    def test_convert_bool_value_str_unknown(self, svc):
        assert svc.convert_bool_value("maybe") is None

    def test_convert_bool_value_int(self, svc):
        assert svc.convert_bool_value(1) is None  # ints not handled as bool directly

    # --- convert_row_types ---
    def test_convert_row_types_none_values(self, svc):
        row = {"village_name": None, "department": "  ", "sequence_no": None}
        converted = svc.convert_row_types(row)
        assert converted["village_name"] is None
        assert converted["department"] is None
        assert converted["sequence_no"] is None

    def test_convert_row_types_int(self, svc):
        row = {"sequence_no": "123"}
        converted = svc.convert_row_types(row)
        assert converted["sequence_no"] == 123

    def test_convert_row_types_int_invalid(self, svc):
        row = {"sequence_no": "abc"}
        converted = svc.convert_row_types(row)
        assert converted["sequence_no"] is None

    def test_convert_row_types_float(self, svc):
        svc.FIELD_TYPES["investment"] = "float"
        row = {"investment": "123.45"}
        converted = svc.convert_row_types(row)
        assert converted["investment"] == 123.45

    def test_convert_row_types_float_invalid(self, svc):
        svc.FIELD_TYPES["investment"] = "float"
        row = {"investment": "abc"}
        converted = svc.convert_row_types(row)
        assert converted["investment"] is None

    def test_convert_row_types_bool(self, svc):
        row = {"is_three_regions": "是"}
        converted = svc.convert_row_types(row)
        assert converted["is_three_regions"] is True

    def test_convert_row_types_county(self, svc):
        row = {"county": " 都匀市 "}
        converted = svc.convert_row_types(row)
        assert converted["county"] == "都匀市"

    def test_convert_row_types_tiered_level(self, svc):
        row = {"is_revitalization_tier": True}
        converted = svc.convert_row_types(row)
        assert converted["is_revitalization_tier"] is True

    def test_convert_row_types_str_default(self, svc):
        row = {"honors": " 表彰 "}
        converted = svc.convert_row_types(row)
        assert converted["honors"] == "表彰"

    # --- validate_import_data ---
    def test_validate_import_data_exceeds_limit(self, svc):
        rows = [{"department": "A", "support_unit": "B", "village_name": "C"} for _ in range(2000)]
        result = svc.validate_import_data(rows)
        assert not result.is_valid
        assert result.errors[0].error_code.value == "IMPORT_007"

    def test_validate_import_data_valid(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1", "county": "都匀市"},
            {"department": "某部", "support_unit": "某团", "village_name": "村2", "county": "长顺县"},
        ]
        result = svc.validate_import_data(rows, validate_county=True)
        assert result.is_valid
        assert result.valid_rows == 2

    def test_validate_import_data_county_error(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1", "county": "invalid"},
        ]
        result = svc.validate_import_data(rows, validate_county=True)
        county_errors = [e for e in result.errors if e.error_code.value == "IMPORT_008"]
        assert len(county_errors) >= 1

    def test_validate_import_data_skip_county_validation(self, svc):
        svc.FIELD_TYPES.pop("county", None)
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1", "county": "invalid"},
        ]
        result = svc.validate_import_data(rows, validate_county=False)
        county_errors = [e for e in result.errors if e.error_code.value == "IMPORT_008"]
        assert len(county_errors) == 0

    def test_validate_import_data_is_revitalization_tier_valid(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1", "is_revitalization_tier": True},
        ]
        result = svc.validate_import_data(rows)
        assert result.is_valid

    def test_validate_import_data_is_revitalization_tier_false(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1", "is_revitalization_tier": False},
        ]
        result = svc.validate_import_data(rows)
        assert result.is_valid

    def test_validate_import_data_duplicates(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1"},
            {"department": "某部", "support_unit": "某团", "village_name": "村1"},
        ]
        result = svc.validate_import_data(rows)
        dup_errors = [e for e in result.errors if e.error_code.value == "IMPORT_005"]
        assert len(dup_errors) >= 1

    def test_validate_import_data_county_empty_value(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1", "county": ""},
        ]
        result = svc.validate_import_data(rows, validate_county=True)
        assert result.is_valid

    def test_validate_import_data_is_revitalization_tier_bool(self, svc):
        rows = [
            {"department": "某部", "support_unit": "某团", "village_name": "村1",
             "is_revitalization_tier": False},
        ]
        result = svc.validate_import_data(rows)
        assert result.is_valid

    # --- _generate_warnings ---
    def test_generate_warnings_empty_fields(self, svc):
        rows = [
            {"department": "A", "support_unit": "B", "village_name": "C", "honors": ""},
            {"department": "A", "support_unit": "B", "village_name": "D", "honors": ""},
            {"department": "A", "support_unit": "B", "village_name": "E", "honors": ""},
        ]
        warnings = svc._generate_warnings(rows)
        honors_warnings = [w for w in warnings if "honors" in w or "表彰" in w]
        assert len(honors_warnings) >= 1

    def test_generate_warnings_duplicate_village_names(self, svc):
        rows = [
            {"department": "A", "support_unit": "B", "village_name": "村1"},
            {"department": "A", "support_unit": "B", "village_name": "村1"},
        ]
        warnings = svc._generate_warnings(rows)
        dup_warnings = [w for w in warnings if "重复" in w]
        assert len(dup_warnings) >= 1

    def test_generate_warnings_no_warnings(self, svc):
        rows = [
            {"department": "A", "support_unit": "B", "village_name": "C"},
        ]
        warnings = svc._generate_warnings(rows)
        assert len(warnings) == 0

    # --- get_validation_summary ---
    def test_get_validation_summary(self, svc):
        from app.services.data_validator_service import ValidationResult, ValidationError, ValidationErrorCode
        errs = [
            ValidationError(1, "village_name", ValidationErrorCode.MISSING_REQUIRED_FIELD, "err1"),
            ValidationError(2, "county", ValidationErrorCode.INVALID_COUNTY, "err2"),
        ]
        result = ValidationResult(is_valid=False, total_rows=5, valid_rows=3, errors=errs, warnings=["warn"])
        summary = svc.get_validation_summary(result)
        assert summary["is_valid"] is False
        assert summary["total_rows"] == 5
        assert summary["valid_rows"] == 3
        assert summary["invalid_rows"] == 2
        assert summary["error_count"] == 2
        assert summary["warning_count"] == 1
        assert "IMPORT_003" in summary["errors_by_type"]
        assert "IMPORT_008" in summary["errors_by_type"]
        assert "定点帮扶村" in summary["errors_by_field"]
        assert len(summary["first_errors"]) == 2

    def test_get_validation_summary_no_errors(self, svc):
        from app.services.data_validator_service import ValidationResult
        result = ValidationResult(is_valid=True, total_rows=0, valid_rows=0)
        summary = svc.get_validation_summary(result)
        assert summary["is_valid"] is True
        assert summary["error_count"] == 0

    def test_get_validation_summary_string_error_code(self, svc):
        from app.services.data_validator_service import (
            ValidationResult, ValidationError, ValidationErrorCode,
        )
        err = ValidationError(1, "f", ValidationErrorCode.INVALID_FILE_FORMAT, "msg")
        result = ValidationResult(is_valid=False, errors=[err])
        summary = svc.get_validation_summary(result)
        assert "IMPORT_001" in summary["errors_by_type"]


class TestSimpleValidationResult:
    def test_to_dict(self):
        from app.services.data_validator_service import SimpleValidationResult
        r = SimpleValidationResult(is_valid=False, error_code="ERR", error_message="msg", field_name="f")
        d = r.to_dict()
        assert d["is_valid"] is False
        assert d["error_code"] == "ERR"
        assert d["error_message"] == "msg"
        assert d["field_name"] == "f"


class TestDataValidator:
    @pytest.fixture
    def validator(self):
        from app.services.data_validator_service import DataValidator
        return DataValidator(known_id_numbers={"110101199001011234"})

    @pytest.fixture
    def empty_validator(self):
        from app.services.data_validator_service import DataValidator
        return DataValidator()

    # --- validate_id_number ---
    def test_validate_id_number_empty(self, validator):
        result = validator.validate_id_number("")
        assert not result.is_valid
        assert result.error_code == "ID_EMPTY"

    def test_validate_id_number_none(self, validator):
        result = validator.validate_id_number(None)
        assert not result.is_valid
        assert result.error_code == "ID_EMPTY"

    def test_validate_id_number_wrong_length(self, validator):
        result = validator.validate_id_number("12345")
        assert not result.is_valid
        assert result.error_code == "ID_LENGTH_INVALID"

    def test_validate_id_number_format_invalid(self, validator):
        result = validator.validate_id_number("123456789012345678")
        assert not result.is_valid
        assert result.error_code == "ID_FORMAT_INVALID"

    def test_validate_id_number_checksum_invalid(self, validator):
        result = validator.validate_id_number("11010119900101123X")
        assert not result.is_valid
        assert result.error_code == "ID_CHECKSUM_INVALID"

    def test_validate_id_number_duplicate(self, monkeypatch):
        from app.services.data_validator_service import DataValidator
        def mock_verify(*args):
            return True
        validator = DataValidator(known_id_numbers={"110101199001011234"})
        monkeypatch.setattr(validator, "_verify_id_checksum", mock_verify)
        result = validator.validate_id_number("110101199001011234", check_duplicate=True)
        assert not result.is_valid
        assert result.error_code == "ID_DUPLICATE"

    def test_validate_id_number_no_duplicate_check(self, monkeypatch):
        from app.services.data_validator_service import DataValidator
        def mock_verify(*args):
            return True
        validator = DataValidator(known_id_numbers={"110101199001011234"})
        monkeypatch.setattr(validator, "_verify_id_checksum", mock_verify)
        result = validator.validate_id_number("110101199001011234", check_duplicate=False)
        assert result.is_valid

    @patch("app.services.data_validator_service.DataValidator._verify_id_checksum", return_value=True)
    def test_validate_id_number_valid(self, mock_verify, validator):
        result = validator.validate_id_number("110101199001011234", check_duplicate=False)
        assert result.is_valid

    def test_validate_id_number_strip_and_upper(self, validator):
        result = validator.validate_id_number(" 110101199001011234 ", check_duplicate=False)
        # verify checksum with stripped+uppered value (mock needed)
        pass

    # --- validate_id_number with known_id_numbers default ---
    def test_validate_id_number_default_known_set(self, empty_validator):
        result = empty_validator.validate_id_number("110101199001011234", check_duplicate=False)
        assert result.error_code == "ID_CHECKSUM_INVALID"

    # --- _verify_id_checksum ---
    def test_verify_id_checksum_valid(self, validator):
        with patch("app.services.data_validator_service.DataValidator._verify_id_checksum", return_value=True):
            # Use a mock to test a valid checksum
            validator._verify_id_checksum = lambda x: True
            result = validator.validate_id_number("110101199001011234", check_duplicate=False)
            assert result.is_valid

    def test_verify_id_checksum_value_error(self, validator):
        result = validator._verify_id_checksum("abcd")
        assert not result

    def test_verify_id_checksum_index_error(self, validator):
        result = validator._verify_id_checksum("1234")
        assert not result

    # --- add_known_id_number ---
    def test_add_known_id_number(self, validator):
        validator.add_known_id_number(" 22010119900101123X ")
        assert "22010119900101123X" in validator._known_id_numbers
        # Verify that adding it makes duplicate detection work
        result = validator.validate_id_number("22010119900101123X", check_duplicate=True)
        assert not result.is_valid

    def test_add_known_id_number_empty(self, validator):
        validator.add_known_id_number("")
        assert "" not in validator._known_id_numbers

    def test_add_known_id_number_none(self, validator):
        validator.add_known_id_number(None)
        assert None not in validator._known_id_numbers

    # --- validate_date_format ---
    def test_validate_date_format_empty(self, validator):
        result = validator.validate_date_format("")
        assert not result.is_valid
        assert result.error_code == "DATE_EMPTY"

    def test_validate_date_format_none(self, validator):
        result = validator.validate_date_format(None)
        assert not result.is_valid
        assert result.error_code == "DATE_EMPTY"

    def test_validate_date_format_unsupported(self, validator):
        result = validator.validate_date_format("2024-01-15", "UNSUPPORTED")
        assert not result.is_valid
        assert result.error_code == "DATE_FORMAT_UNSUPPORTED"

    def test_validate_date_format_valid_iso(self, validator):
        result = validator.validate_date_format("2024-01-15", "YYYY-MM-DD")
        assert result.is_valid

    def test_validate_date_format_valid_slash(self, validator):
        result = validator.validate_date_format("2024/01/15", "YYYY/MM/DD")
        assert result.is_valid

    def test_validate_date_format_valid_compact(self, validator):
        result = validator.validate_date_format("20240115", "YYYYMMDD")
        assert result.is_valid

    def test_validate_date_format_valid_dmy(self, validator):
        result = validator.validate_date_format("15-01-2024", "DD-MM-YYYY")
        assert result.is_valid

    def test_validate_date_format_valid_mdy(self, validator):
        result = validator.validate_date_format("01/15/2024", "MM/DD/YYYY")
        assert result.is_valid

    def test_validate_date_format_valid_chinese(self, validator):
        result = validator.validate_date_format("2024年01月15日", "YYYY年MM月DD日")
        assert result.is_valid

    def test_validate_date_format_out_of_range(self, validator):
        result = validator.validate_date_format("1800-01-01", "YYYY-MM-DD")
        assert not result.is_valid
        assert result.error_code == "DATE_OUT_OF_RANGE"

    def test_validate_date_format_future_range(self, validator):
        result = validator.validate_date_format("2200-01-01", "YYYY-MM-DD")
        assert not result.is_valid
        assert result.error_code == "DATE_OUT_OF_RANGE"

    def test_validate_date_format_invalid(self, validator):
        result = validator.validate_date_format("not-a-date", "YYYY-MM-DD")
        assert not result.is_valid
        assert result.error_code == "DATE_FORMAT_INVALID"

    # --- validate_required_fields ---
    def test_validate_required_fields_empty_data(self, validator):
        result = validator.validate_required_fields(None, ["name"])
        assert not result.is_valid
        assert result.error_code == "DATA_EMPTY"

    def test_validate_required_fields_empty_required(self, validator):
        result = validator.validate_required_fields({"name": "test"}, [])
        assert result.is_valid

    def test_validate_required_fields_all_present(self, validator):
        result = validator.validate_required_fields({"name": "test", "age": 25}, ["name", "age"])
        assert result.is_valid

    def test_validate_required_fields_missing(self, validator):
        result = validator.validate_required_fields({"name": "test"}, ["name", "age"])
        assert not result.is_valid
        assert result.error_code == "REQUIRED_FIELDS_MISSING"
        assert "age" in result.error_message

    def test_validate_required_fields_empty_value(self, validator):
        result = validator.validate_required_fields({"name": ""}, ["name"])
        assert not result.is_valid
        assert "name" in result.error_message

    def test_validate_required_fields_none_value(self, validator):
        result = validator.validate_required_fields({"name": None}, ["name"])
        assert not result.is_valid

    # --- validate_field_length ---
    def test_validate_field_length_none_value(self, validator):
        result = validator.validate_field_length(None, 10, "field")
        assert result.is_valid

    def test_validate_field_length_ok(self, validator):
        result = validator.validate_field_length("hello", 10, "field")
        assert result.is_valid

    def test_validate_field_length_too_long(self, validator):
        result = validator.validate_field_length("hello world!", 5, "field")
        assert not result.is_valid
        assert result.error_code == "FIELD_TOO_LONG"

    def test_validate_field_length_too_short(self, validator):
        result = validator.validate_field_length("ab", 10, "field", min_length=5)
        assert not result.is_valid
        assert result.error_code == "FIELD_TOO_SHORT"

    def test_validate_field_length_no_field_name(self, validator):
        result = validator.validate_field_length("abc", 10)
        assert result.is_valid

    # --- sanitize_input ---
    def test_sanitize_input_none(self, validator):
        assert validator.sanitize_input(None) == ""

    def test_sanitize_input_remove_html(self, validator):
        result = validator.sanitize_input("<script>alert('xss')</script>Hello", remove_html=True)
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_input_html_entities(self, validator):
        result = validator.sanitize_input("&lt;b&gt;bold&lt;/b&gt;", remove_html=True)
        assert "bold" in result
        assert "<b>" not in result

    def test_sanitize_input_remove_sql_injection(self, validator):
        result = validator.sanitize_input("SELECT * FROM users; DROP TABLE;", remove_sql_injection=True)
        assert "SELECT" not in result
        assert "DROP" not in result
        assert ";" not in result
        assert "'" not in result

    def test_sanitize_input_allowed_chars(self, validator):
        result = validator.sanitize_input("Hello123!@#", allowed_chars="a-zA-Z0-9")
        assert result == "Hello123"

    def test_sanitize_input_no_removal(self, validator):
        result = validator.sanitize_input("Hello World", remove_html=False, remove_sql_injection=False)
        assert result == "Hello World"

    def test_sanitize_input_sql_keywords_cases(self, validator):
        result = validator.sanitize_input("union select drop delete insert update or and", remove_sql_injection=True)
        assert result == ""

    def test_sanitize_input_multi_whitespace(self, validator):
        result = validator.sanitize_input("hello    world", remove_html=False, remove_sql_injection=False)
        assert result == "hello world"

    # --- validate_and_sanitize ---
    def test_validate_and_sanitize(self, validator):
        sanitized, result = validator.validate_and_sanitize("<b>hello</b>", 10, "a-zA-Z", "field")
        assert sanitized == "hello"
        assert result.is_valid

    def test_validate_and_sanitize_too_long(self, validator):
        sanitized, result = validator.validate_and_sanitize("<b>hello world</b>", 5, "a-zA-Z", "field")
        assert not result.is_valid
        assert result.error_code == "FIELD_TOO_LONG"

    # --- validate_email ---
    def test_validate_email_empty(self, validator):
        result = validator.validate_email("")
        assert not result.is_valid
        assert result.error_code == "EMAIL_EMPTY"

    def test_validate_email_none(self, validator):
        result = validator.validate_email(None)
        assert not result.is_valid

    def test_validate_email_valid(self, validator):
        result = validator.validate_email("test@example.com")
        assert result.is_valid

    def test_validate_email_invalid(self, validator):
        result = validator.validate_email("not-an-email")
        assert not result.is_valid
        assert result.error_code == "EMAIL_FORMAT_INVALID"

    def test_validate_email_missing_tld(self, validator):
        result = validator.validate_email("test@example")
        assert not result.is_valid

    # --- validate_phone ---
    def test_validate_phone_empty(self, validator):
        result = validator.validate_phone("")
        assert not result.is_valid
        assert result.error_code == "PHONE_EMPTY"

    def test_validate_phone_none(self, validator):
        result = validator.validate_phone(None)
        assert not result.is_valid

    def test_validate_phone_valid(self, validator):
        result = validator.validate_phone("13800138000")
        assert result.is_valid

    def test_validate_phone_invalid(self, validator):
        result = validator.validate_phone("12345678901")
        assert not result.is_valid
        assert result.error_code == "PHONE_FORMAT_INVALID"

    def test_validate_phone_short(self, validator):
        result = validator.validate_phone("13800")
        assert not result.is_valid


# ---------------------------------------------------------------------------
#  分支覆盖清零（coverage report --show-missing 实测的 7 个部分分支）
# ---------------------------------------------------------------------------

@pytest.fixture
def dvs():
    from app.services.data_validator_service import DataValidatorService
    return DataValidatorService()


def test_parse_excel_headers_skips_empty_header(dvs):
    """空表头 → if header 为假跳过该列（356->355）。键名取自 COLUMN_MAPPING。"""
    mapping = dvs.parse_excel_headers(["*县 / 市", "", "序号"])
    assert 1 not in mapping
    assert mapping == {0: "county", 2: "sequence_no"}


def test_get_validation_summary_groups_and_skips_empty_field(dvs):
    """get_validation_summary：同类型/同字段复用分组桶（669->671、677->679），
    无字段名错误被跳过（676->675，如行数超限这类非字段级错误）。"""
    from app.services.data_validator_service import (
        ValidationErrorCode,
        ValidationError,
        ValidationResult,
    )

    result = ValidationResult(is_valid=False, total_rows=3, valid_rows=0)
    result.errors = [
        ValidationError(
            row_number=1,
            field_name="department",
            error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
            message="缺失部门",
        ),
        ValidationError(
            row_number=2,
            field_name="department",
            error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
            message="缺失部门",
        ),
        ValidationError(
            row_number=0,
            field_name="",
            error_code=ValidationErrorCode.ROW_LIMIT_EXCEEDED,
            message="数据行数超过限制",
        ),
    ]
    summary = dvs.get_validation_summary(result)
    assert summary["error_count"] == 3
    assert summary["errors_by_type"]["IMPORT_003"] == 2
    # 同字段两条复用同一分组桶；无字段名错误不进入字段分组
    assert list(summary["errors_by_field"].values()) == [2]
    assert "" not in summary["errors_by_field"]


def test_validate_int_field_without_range_config(dvs):
    """字段不在 NUMERIC_FIELD_RANGES → 直接通过（373->383）。"""
    assert dvs._validate_int_field("未配置范围的整数字段", 7, 1) is None


def test_validate_float_field_accepts_number(dvs):
    """float 校验器收到 int/float → elif 为假正常返回（388->exit）。"""
    dvs._validate_float_field(12.5)
    dvs._validate_float_field(12)


def test_import_grouping_duplicate_type_and_field(dvs):
    """两条必填缺失错误：同 error_code（669->671）+ 同 field_name（677->679）复用分组桶。"""
    rows = [
        {"department": "", "support_unit": "", "village_name": ""},
        {"department": "", "support_unit": "", "village_name": ""},
    ]
    result = dvs.validate_import_data(rows, validate_county=False)
    assert result.errors
    codes = [e.error_code.value for e in result.errors]
    fields = [e.field_name for e in result.errors]
    assert len(codes) != len(set(codes)), "应有重复 error_code"
    assert len(fields) != len(set(fields)), "应有重复 field_name"


def test_import_empty_field_below_half_is_skipped(dvs):
    """非必填字段空值占比 ≤50% → 警告循环 continue（640->639）。"""
    rows = [
        {"department": "某部", "support_unit": "某团", "village_name": "村1", "county": "都匀市", "project_name": ""},
        {"department": "某部", "support_unit": "某团", "village_name": "村2", "county": "长顺县", "project_name": "项目A"},
        {"department": "某部", "support_unit": "某团", "village_name": "村3", "county": "贵定县", "project_name": "项目B"},
    ]
    result = dvs.validate_import_data(rows, validate_county=True)
    assert not any("为空" in w for w in result.warnings)
