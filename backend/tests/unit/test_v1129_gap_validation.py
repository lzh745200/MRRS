"""v1.12.9 覆盖率补口：app/api/v1/validation.py 规则参数脏数据兜底（深审 LIVE）。

覆盖行（当前代码行号）：
- 224-227 `/validation/validate`：ValidationRule.params 是用户配置的 JSON 文本，
  非法 JSON（ValueError）或非字符串（TypeError）一律按"无参数"处理，
  绝不让脏规则把校验端点打成 500；
- 307-312 `_check_file_type`：非字符串值（如数字/None）不构成文件类型 → 不判失败。
"""

from unittest.mock import MagicMock

from app.api.v1.validation import _check_file_type, validate_data
from app.models.validation_rule import RuleType


def _db_with_rules(rules):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rules
    return db


def _rule(**kw):
    defaults = dict(
        id=1, module="village", field="name", rule_type=RuleType.required,
        params=None, error_message="数据校验失败", is_active=True, priority=1,
    )
    defaults.update(kw)
    return MagicMock(**defaults)


class TestValidateDataDirtyParams:
    async def test_invalid_json_params_treated_as_empty(self):
        """params 非法 JSON → 按无参数处理，规则照常执行（不 500）。"""
        rule = _rule(params="{not-json")
        result = await validate_data(
            module="village", data={}, current_user=MagicMock(), db=_db_with_rules([rule])
        )
        assert result["data"]["valid"] is False
        assert result["data"]["errors"][0]["field"] == "name"
        assert result["data"]["errors"][0]["rule_type"] == "required"

    async def test_non_string_params_type_error_treated_as_empty(self):
        rule = _rule(params=12345)
        result = await validate_data(
            module="village", data={"name": "有值"}, current_user=MagicMock(),
            db=_db_with_rules([rule]),
        )
        assert result["data"]["valid"] is True
        assert result["data"]["errors"] == []

    async def test_empty_params_string_uses_defaults(self):
        rule = _rule(params="")
        result = await validate_data(
            module="village", data={"name": "有值"}, current_user=MagicMock(),
            db=_db_with_rules([rule]),
        )
        assert result["data"]["valid"] is True


class TestCheckFileTypeNonString:
    def test_non_string_value_is_not_file_type_violation(self):
        assert _check_file_type(123, {"allowed": ["pdf"]}, {}) is False
        assert _check_file_type(None, {"allowed": ["pdf"]}, {}) is False

    def test_string_value_checked_against_allowlist(self):
        assert _check_file_type("a.pdf", {"allowed": ["pdf"]}, {}) is False
        assert _check_file_type("a.exe", {"allowed": ["pdf"]}, {}) is True
