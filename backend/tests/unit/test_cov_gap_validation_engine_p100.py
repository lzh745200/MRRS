"""app.services.validation_engine_service 缺口补口（.coveragerc fail_under=100）。

缺失行：30-35 —— _load_rule_params 的"truthy 非 dict"输入路径（ValidationRule.params
是 Text 列，存 JSON 字符串）：
  · 合法 JSON 对象字符串 → 解析为 dict；
  · 非法 JSON（ValueError）/ 不可序列化类型（TypeError）→ warning + 降级 {}，
    不得让 params.get(...) 抛 AttributeError 被宽 except 吞掉（历史缺陷：range/
    regex/enum/length **所有**规则静默失效，深审 critical）；
  · 合法 JSON 但非对象（数组/标量）→ 同样降级 {}。
"""

from unittest.mock import MagicMock, patch

import app.services.validation_engine_service as ves
from app.services.validation_engine_service import (
    ValidationEngineService,
    _load_rule_params,
)


class TestLoadRuleParams:
    def test_json_object_string_is_parsed(self):
        assert _load_rule_params('{"min": 10, "max": 20}') == {"min": 10, "max": 20}

    def test_invalid_json_degrades_to_empty_with_warning(self):
        with patch.object(ves, "logger") as mock_logger:
            assert _load_rule_params("{not-json") == {}
        mock_logger.warning.assert_called_once()

    def test_non_object_json_degrades_to_empty(self):
        assert _load_rule_params("[1, 2, 3]") == {}
        assert _load_rule_params("5") == {}
        assert _load_rule_params('"just text"') == {}

    def test_unserializable_type_degrades_to_empty(self):
        # json.loads(5) 抛 TypeError（而非 ValueError）→ 同样降级为空规则
        with patch.object(ves, "logger") as mock_logger:
            assert _load_rule_params(5) == {}
        mock_logger.warning.assert_called_once()

    def test_dict_and_empty_inputs_shortcut(self):
        rule = {"min": 1}
        assert _load_rule_params(rule) is rule      # dict 原样返回（不复制）
        assert _load_rule_params(None) == {}
        assert _load_rule_params("") == {}


class TestJsonStringParamsEnforced:
    """端到端：rule.params 为 JSON 字符串时规则仍然生效（不再静默失效）。"""

    def _db_with(self, rule):
        db = MagicMock(name="db")
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rule]
        return db

    def _rule(self, params):
        rule = MagicMock(name="rule")
        rule.field = "amount"
        rule.rule_type = "range"
        rule.params = params
        rule.error_message = None
        return rule

    def test_range_rule_with_json_string_params_is_enforced(self):
        service = ValidationEngineService(db=self._db_with(self._rule('{"min": 10}')))
        assert service.validate_with_db_rules({"amount": 5}, module="fund") == ["amount: 校验失败"]

    def test_rule_with_broken_json_params_is_skipped_not_crashed(self):
        """非法 JSON → 空规则 → range 无 min/max 约束 → 不报错也不抛异常。"""
        service = ValidationEngineService(db=self._db_with(self._rule("{broken")))
        with patch.object(ves, "logger") as mock_logger:
            assert service.validate_with_db_rules({"amount": 5}, module="fund") == []
        mock_logger.warning.assert_called_once()
