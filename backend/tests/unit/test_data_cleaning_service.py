"""数据清洗服务单元测试"""
from unittest.mock import patch
from app.services.data_cleaning_service import DataCleaningService


class TestDeduplicate:
    def test_empty_records_returns_empty_list(self):
        assert DataCleaningService.deduplicate([], ["name"]) == []

    def test_no_duplicates_returns_all(self):
        records = [
            {"name": "张三", "phone": "13800138001"},
            {"name": "李四", "phone": "13800138002"},
        ]
        result = DataCleaningService.deduplicate(records, ["name", "phone"])
        assert len(result) == 2

    def test_exact_duplicate_removed(self):
        records = [
            {"name": "张三", "phone": "13800138001"},
            {"name": "张三", "phone": "13800138001"},
        ]
        result = DataCleaningService.deduplicate(records, ["name", "phone"])
        assert len(result) == 1

    def test_high_similarity_is_duplicate(self):
        records = [
            {"name": "张三丰", "phone": "13800138001"},
            {"name": "张三峰", "phone": "13800138001"},
        ]
        result = DataCleaningService.deduplicate(records, ["name", "phone"], similarity_threshold=0.8)
        assert len(result) == 1

    def test_low_similarity_not_duplicate(self):
        records = [
            {"name": "张三", "phone": "13800138001"},
            {"name": "李四", "phone": "13900139002"},
        ]
        result = DataCleaningService.deduplicate(records, ["name", "phone"], similarity_threshold=0.95)
        assert len(result) == 2

    def test_missing_key_field_uses_empty_string(self):
        records = [
            {"name": "张三"},
            {"name": "张三"},
        ]
        result = DataCleaningService.deduplicate(records, ["name", "phone"])
        assert len(result) == 1


class TestCalculateSimilarity:
    def test_different_length_returns_zero(self):
        assert DataCleaningService._calculate_similarity(("a",), ("a", "b")) == 0.0

    def test_identical_tuples_returns_one(self):
        assert DataCleaningService._calculate_similarity(("a", "b"), ("a", "b")) == 1.0

    def test_partial_similarity(self):
        sim = DataCleaningService._calculate_similarity(("abc",), ("abd",))
        assert 0.0 < sim < 1.0

    def test_empty_tuple_returns_zero(self):
        assert DataCleaningService._calculate_similarity((), ()) == 0.0


class TestStandardizePhone:
    def test_none_returns_none(self):
        assert DataCleaningService.standardize_phone(None) is None

    def test_empty_string_returns_none(self):
        assert DataCleaningService.standardize_phone("") is None

    def test_valid_mobile_11_digits(self):
        assert DataCleaningService.standardize_phone("13800138001") == "13800138001"

    def test_mobile_with_formatting(self):
        assert DataCleaningService.standardize_phone("138-0013-8001") == "13800138001"

    def test_landline_10_digits(self):
        assert DataCleaningService.standardize_phone("01012345678") == "01012345678"

    def test_landline_12_digits(self):
        assert DataCleaningService.standardize_phone("021123456789") == "021123456789"

    def test_short_number_returns_none(self):
        assert DataCleaningService.standardize_phone("12345") is None

    def test_11_digits_not_starting_with_one_returned_as_landline(self):
        assert DataCleaningService.standardize_phone("23800138001") == "23800138001"


class TestStandardizeEmail:
    def test_none_returns_none(self):
        assert DataCleaningService.standardize_email(None) is None

    def test_empty_string_returns_none(self):
        assert DataCleaningService.standardize_email("") is None

    def test_valid_email_lowered_and_stripped(self):
        assert DataCleaningService.standardize_email("  Test@Example.COM  ") == "test@example.com"

    def test_invalid_email_no_at_sign_returns_none(self):
        assert DataCleaningService.standardize_email("notanemail") is None

    def test_invalid_email_no_domain_returns_none(self):
        assert DataCleaningService.standardize_email("user@") is None


class TestStandardizeAddress:
    def test_none_returns_none(self):
        assert DataCleaningService.standardize_address(None) is None

    def test_empty_string_returns_none(self):
        assert DataCleaningService.standardize_address("") is None

    def test_multiple_spaces_collapsed(self):
        result = DataCleaningService.standardize_address("  广东省  广州市  ")
        assert result == "广东省 广州市"

    def test_leading_trailing_spaces_removed(self):
        result = DataCleaningService.standardize_address("  广东省广州市  ")
        assert result == "广东省广州市"

    def test_standard_replacements_applied(self):
        result = DataCleaningService.standardize_address("XX省XX市XX县")
        assert "省" in result and "市" in result and "县" in result


class TestFillMissingValues:
    def test_empty_records_returns_empty_list(self):
        assert DataCleaningService.fill_missing_values([], "name") == []

    def test_default_strategy_fills_none(self):
        records = [{"name": None}, {"name": "张三"}]
        result = DataCleaningService.fill_missing_values(records, "name", strategy="default", default_value="未知")
        assert result[0]["name"] == "未知"
        assert result[1]["name"] == "张三"

    def test_default_strategy_fills_empty_string(self):
        records = [{"name": ""}, {"name": "张三"}]
        result = DataCleaningService.fill_missing_values(records, "name", strategy="default", default_value="未知")
        assert result[0]["name"] == "未知"

    def test_default_strategy_skips_existing_value(self):
        records = [{"name": "张三"}]
        result = DataCleaningService.fill_missing_values(records, "name", strategy="default", default_value="未知")
        assert result[0]["name"] == "张三"

    def test_mean_strategy(self):
        records = [{"value": 10}, {"value": None}, {"value": 20}]
        result = DataCleaningService.fill_missing_values(records, "value", strategy="mean")
        assert result[1]["value"] == 15.0

    def test_mean_strategy_no_values_does_nothing(self):
        records = [{"value": None}]
        result = DataCleaningService.fill_missing_values(records, "value", strategy="mean")
        assert result[0]["value"] is None

    def test_mean_strategy_type_error_logs_warning(self):
        records = [{"value": "not_a_number"}, {"value": None}]
        with patch("app.services.data_cleaning_service.logger") as mock_logger:
            DataCleaningService.fill_missing_values(records, "value", strategy="mean")
            mock_logger.warning.assert_called_once()

    def test_median_strategy(self):
        records = [{"value": 10}, {"value": None}, {"value": 20}, {"value": 30}]
        result = DataCleaningService.fill_missing_values(records, "value", strategy="median")
        assert result[1]["value"] == 20

    def test_median_strategy_no_values_does_nothing(self):
        records = [{"value": None}]
        result = DataCleaningService.fill_missing_values(records, "value", strategy="median")
        assert result[0]["value"] is None

    def test_mode_strategy(self):
        records = [{"value": 10}, {"value": None}, {"value": 10}, {"value": 20}]
        result = DataCleaningService.fill_missing_values(records, "value", strategy="mode")
        assert result[1]["value"] == 10

    def test_mode_strategy_no_values_does_nothing(self):
        records = [{"value": None}]
        result = DataCleaningService.fill_missing_values(records, "value", strategy="mode")
        assert result[0]["value"] is None

    def test_unknown_strategy_returns_records_as_is(self):
        records = [{"name": None}]
        result = DataCleaningService.fill_missing_values(records, "name", strategy="unknown")
        assert result[0]["name"] is None


class TestCleanDataset:
    def test_no_rules_returns_records(self):
        records = [{"name": "张三"}]
        result = DataCleaningService.clean_dataset(records, {})
        assert result == records

    def test_deduplicate_rule(self):
        records = [
            {"name": "张三", "phone": "13800138001"},
            {"name": "张三", "phone": "13800138001"},
        ]
        rules = {"deduplicate": {"key_fields": ["name", "phone"], "threshold": 0.9}}
        result = DataCleaningService.clean_dataset(records, rules)
        assert len(result) == 1

    def test_deduplicate_default_threshold(self):
        records = [{"name": "张三"}, {"name": "张三"}]
        rules = {"deduplicate": {"key_fields": ["name"]}}
        result = DataCleaningService.clean_dataset(records, rules)
        assert len(result) == 1

    def test_standardize_phone_rule(self):
        records = [{"phone": "138-0013-8001"}]
        rules = {"standardize": [{"field": "phone", "type": "phone"}]}
        result = DataCleaningService.clean_dataset(records, rules)
        assert result[0]["phone"] == "13800138001"

    def test_standardize_email_rule(self):
        records = [{"email": "  Test@Example.COM  "}]
        rules = {"standardize": [{"field": "email", "type": "email"}]}
        result = DataCleaningService.clean_dataset(records, rules)
        assert result[0]["email"] == "test@example.com"

    def test_standardize_address_rule(self):
        records = [{"address": "  广东省  广州市  "}]
        rules = {"standardize": [{"field": "address", "type": "address"}]}
        result = DataCleaningService.clean_dataset(records, rules)
        assert result[0]["address"] == "广东省 广州市"

    def test_standardize_empty_value_skipped(self):
        records = [{"phone": ""}]
        rules = {"standardize": [{"field": "phone", "type": "phone"}]}
        result = DataCleaningService.clean_dataset(records, rules)
        assert result[0]["phone"] == ""

    def test_standardize_none_value_skipped(self):
        records = [{"phone": None}]
        rules = {"standardize": [{"field": "phone", "type": "phone"}]}
        result = DataCleaningService.clean_dataset(records, rules)
        assert result[0]["phone"] is None

    def test_fill_missing_rule(self):
        records = [{"name": None}, {"name": "张三"}]
        rules = {"fill_missing": [{"field": "name", "strategy": "default", "default_value": "未知"}]}
        result = DataCleaningService.clean_dataset(records, rules)
        assert result[0]["name"] == "未知"
        assert result[1]["name"] == "张三"

    def test_all_rules_combined(self):
        records = [
            {"name": "张三", "phone": "138-0013-8001", "email": "  A@B.COM  "},
            {"name": "张三", "phone": "138-0013-8001", "email": "  A@B.COM  "},
            {"name": None, "phone": "139-0013-9002", "email": "  C@D.COM  "},
        ]
        rules = {
            "deduplicate": {"key_fields": ["name", "phone"], "threshold": 0.9},
            "standardize": [
                {"field": "phone", "type": "phone"},
                {"field": "email", "type": "email"},
            ],
            "fill_missing": [{"field": "name", "strategy": "default", "default_value": "未知"}],
        }
        result = DataCleaningService.clean_dataset(records, rules)
        assert len(result) == 2
        assert result[0]["phone"] == "13800138001"
        assert result[0]["email"] == "a@b.com"
        assert result[1]["name"] == "未知"
        assert result[1]["phone"] == "13900139002"


class TestTrimAndNormalizeRules:
    def test_trim_whitespace_strips_all_string_fields(self):
        records = [{"name": "  张三 ", "note": "x\n"}]
        result = DataCleaningService.clean_dataset(records, {"trim_whitespace": True})
        assert result[0]["name"] == "张三"
        assert result[0]["note"] == "x"

    def test_normalize_empty_placeholders_become_none(self):
        records = [
            {"phone": "-", "email": "N/A", "addr": "无", "name": "张三"},
            {"phone": "  ", "email": "null", "addr": "keep", "name": "李四"},
        ]
        result = DataCleaningService.clean_dataset(records, {"normalize_empty": True})
        assert result[0]["phone"] is None
        assert result[0]["email"] is None
        assert result[0]["addr"] is None
        assert result[1]["phone"] is None
        assert result[1]["email"] is None
        assert result[1]["addr"] == "keep"

    def test_unknown_rule_key_rejected_with_400(self):
        import asyncio

        import pytest
        from fastapi import HTTPException

        from app.api.v1.data_quality import CleanDataRequest, clean_data

        request = CleanDataRequest(
            records=[{"a": " b "}],
            cleaning_rules={"trim_whitespace": True, "no_such_rule": True},
        )
        admin = type("U", (), {"is_superuser": True})()
        with pytest.raises(HTTPException) as ei:
            asyncio.run(clean_data(request, current_user=admin))
        assert ei.value.status_code == 400
        assert "no_such_rule" in ei.value.detail

    def test_trim_and_normalize_via_endpoint(self):
        import asyncio

        from app.api.v1.data_quality import CleanDataRequest, clean_data

        request = CleanDataRequest(
            records=[{"a": " x ", "b": "-"}],
            cleaning_rules={"trim_whitespace": True, "normalize_empty": True},
        )
        admin = type("U", (), {"is_superuser": True})()
        resp = asyncio.run(clean_data(request, current_user=admin))
        assert resp["data"]["changed_count"] == 1
        assert resp["data"]["cleaned_records"][0]["a"] == "x"
        assert resp["data"]["cleaned_records"][0]["b"] is None
