"""app.services.data_validator_service 覆盖补全：is_revitalization_tier 取值校验。

line 581 —— 导入校验对"是否振兴梯队"列只接受真/假口径的取值（历史
tiered_development_level 字符串列已删除，模型列收窄为布尔
is_revitalization_tier）；非法取值必须落 ValidationError，否则脏值会静默写库。

说明：该分支原先引用的 ValidationErrorCode.INVALID_TIERED_LEVEL 在枚举中缺失
（命中即 AttributeError）；已由源码负责人补上该枚举成员（IMPORT_011），
故本文件直接使用真实枚举成员断言，不做任何注入/打桩。
"""

import pytest

from app.services.data_validator_service import (
    DataValidatorService,
    ValidationErrorCode,
)

_TIER_FIELD = "is_revitalization_tier"
_TIER_ILLEGAL_MARK = "取值非法"


def _row(tier="是", **over):
    """一行必填字段齐全的合法导入数据（便于用 valid_rows 观察行级结论）。

    注意：tier 必须走显式形参 —— 用 **_TIER_FIELD 传关键字会写成字面量键名。
    """
    base = {
        "department": "州帮扶办",
        "support_unit": "某某局",
        "village_name": "某某村",
        _TIER_FIELD: tier,
    }
    base.update(over)
    return base


def _tier_illegal_errors(result):
    return [
        e for e in result.errors
        if e.error_code == ValidationErrorCode.INVALID_TIERED_LEVEL
    ]


class TestImportDataTierValueValidation:
    def test_illegal_tier_value_is_reported(self):
        svc = DataValidatorService()

        result = svc.validate_import_data(
            [_row(tier="大概是吧")],
            validate_county=False, validate_tiered_level=True,
        )

        errors = _tier_illegal_errors(result)
        assert len(errors) == 1
        error = errors[0]
        assert error.row_number == 1
        assert error.field_name == _TIER_FIELD
        assert _TIER_ILLEGAL_MARK in error.message
        assert "大概是吧" in error.message
        assert "仅支持 是/否" in error.message
        # 该行被判为非法行：整份数据不通过，且该行不计入有效行
        assert result.is_valid is False
        assert result.valid_rows == 0

    def test_illegal_tier_value_reports_correct_row_number(self):
        svc = DataValidatorService()
        rows = [
            _row(village_name="一号村"),
            _row(village_name="二号村"),
            _row(village_name="三号村", tier="maybe"),
        ]

        result = svc.validate_import_data(
            rows, validate_county=False, validate_tiered_level=True,
        )

        errors = _tier_illegal_errors(result)
        assert len(errors) == 1
        assert errors[0].row_number == 3
        # 前两行仍然有效（只有第三行被这条额外校验判死）
        assert result.valid_rows == 2

    @pytest.mark.parametrize(
        "legal", ["是", "否", "true", "False", "1", "0", "yes", "N", "no", ""],
    )
    def test_legal_tier_values_pass(self, legal):
        svc = DataValidatorService()

        result = svc.validate_import_data(
            [_row(tier=legal)],
            validate_county=False, validate_tiered_level=True,
        )

        assert _tier_illegal_errors(result) == []

    def test_none_tier_is_skipped(self):
        """空值（未填）不参与该校验 —— 只有显式给了值才判合法性，且整行仍有效。"""
        svc = DataValidatorService()

        result = svc.validate_import_data(
            [_row(tier=None)],
            validate_county=False, validate_tiered_level=True,
        )

        assert _tier_illegal_errors(result) == []
        assert result.is_valid is True
        assert result.valid_rows == 1

    def test_validation_can_be_disabled(self):
        """validate_tiered_level=False 时即使取值非法也不出该条错误（导入模板可选列）。"""
        svc = DataValidatorService()

        result = svc.validate_import_data(
            [_row(tier="???")],
            validate_county=False, validate_tiered_level=False,
        )

        assert _tier_illegal_errors(result) == []

    def test_error_serialises_with_error_code_value(self):
        """错误对象可序列化（to_dict 取 .value），错误码即为 IMPORT_011。"""
        svc = DataValidatorService()

        result = svc.validate_import_data(
            [_row(tier="???")],
            validate_county=False, validate_tiered_level=True,
        )

        payload = _tier_illegal_errors(result)[0].to_dict()
        assert payload["error_code"] == ValidationErrorCode.INVALID_TIERED_LEVEL.value
        assert payload["field_name"] == _TIER_FIELD
