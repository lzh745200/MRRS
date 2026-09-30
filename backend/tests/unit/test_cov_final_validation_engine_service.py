"""
补覆盖测试 - app.services.validation_engine_service

针对既有测试未覆盖的缺口行：
- validate() 的 range/pattern/enum/length 规则分支（65-72, 76-77, 81, 86, 88）
- validate_with_db_rules() 的 DB 规则加载与执行（95-120）
- _check_typed_rule() 的全部规则类型分支（127-157）
"""
from unittest.mock import MagicMock

from app.services.validation_engine_service import ValidationEngineService


def _make_rule(field, rule_type, params=None, message=None):
    """构造模拟的 ValidationRule 记录。

    必须对齐真实模型列名：错误文案列是 error_message（不是 message），
    params 是 JSON 字符串列——历史上测试用 message 属性掩盖了
    AttributeError → 校验规则静默失效的缺陷。
    """
    rule = MagicMock(name=f"rule_{field}_{rule_type}")
    rule.field = field
    rule.rule_type = rule_type
    rule.params = params
    rule.error_message = message
    return rule


def _make_db(rules):
    """构造返回指定规则列表的链式 MagicMock db。"""
    db = MagicMock(name="db")
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rules
    return db


class TestValidateRangeRule:
    """validate() 的 range 检查分支（行 64-72）"""

    def test_range_min_violation(self):
        service = ValidationEngineService()
        errors = service.validate({"age": 5}, {"age": {"min": 10}})
        assert errors == ["age 不能小于 10"]

    def test_range_max_violation(self):
        service = ValidationEngineService()
        errors = service.validate({"age": 150}, {"age": {"max": 100}})
        assert errors == ["age 不能大于 100"]

    def test_range_non_numeric_value(self):
        service = ValidationEngineService()
        errors = service.validate({"age": "abc"}, {"age": {"min": 1, "max": 100}})
        assert errors == ["age 必须为数字"]

    def test_range_value_within_bounds(self):
        service = ValidationEngineService()
        errors = service.validate({"age": 50}, {"age": {"min": 0, "max": 100}})
        assert errors == []


class TestValidatePatternEnumLength:
    """validate() 的 regex/enum/length 检查分支（行 75-88）"""

    def test_pattern_mismatch(self):
        service = ValidationEngineService()
        errors = service.validate({"code": "abc"}, {"code": {"pattern": r"^\d+$"}})
        assert errors == ["code 格式不正确"]

    def test_pattern_match_passes(self):
        service = ValidationEngineService()
        errors = service.validate({"code": "12345"}, {"code": {"pattern": r"^\d+$"}})
        assert errors == []

    def test_enum_violation(self):
        service = ValidationEngineService()
        errors = service.validate({"color": "red"}, {"color": {"enum": ["green", "blue"]}})
        assert len(errors) == 1
        assert "color 必须为以下值之一" in errors[0]

    def test_min_length_violation(self):
        service = ValidationEngineService()
        errors = service.validate({"name": "ab"}, {"name": {"min_length": 5}})
        assert errors == ["name 长度不能少于 5"]

    def test_max_length_violation(self):
        service = ValidationEngineService()
        errors = service.validate({"name": "abcdef"}, {"name": {"max_length": 3}})
        assert errors == ["name 长度不能超过 3"]


class TestValidateWithDbRules:
    """validate_with_db_rules() 的 DB 规则加载与执行（行 95-120）"""

    def test_no_db_falls_back_to_empty_rules(self):
        """无 db 时退化为空规则验证，恒通过（行 95-96）"""
        service = ValidationEngineService(db=None)
        errors = service.validate_with_db_rules({"anything": "x"}, module="village")
        assert errors == []

    def test_db_rules_empty_result(self):
        """DB 无匹配规则时返回空错误并写入 _errors（行 105-106, 119-120）"""
        service = ValidationEngineService(db=_make_db([]))
        errors = service.validate_with_db_rules({"name": "x"}, module="village")
        assert errors == []
        assert service.get_errors() == []

    def test_db_rules_required_and_typed(self):
        """覆盖 required 命中/通过、类型化规则失败/通过、value 为 None 跳过、
        params 为 None 的 or 兜底、error_message 为 None 的默认文案（行 106-117）"""
        rules = [
            # required 且字段缺失 → 报错（使用自定义 message）
            _make_rule("name", "required", params=None, message="必须填写名称"),
            # required 且字段存在 → 通过
            _make_rule("code", "required", params=None, message=None),
            # range 失败 → 报错（message 为 None 走默认文案）
            _make_rule("amount", "range", params={"min": 10}, message=None),
            # range 通过 → 不报错
            _make_rule("score", "range", params={"min": 0, "max": 100}, message="分数异常"),
            # value 为 None → elif 分支不进入，跳过
            _make_rule("remark", "regex", params={"pattern": r"^\d+$"}, message=None),
        ]
        service = ValidationEngineService(db=_make_db(rules))
        data = {"code": "C001", "amount": 5, "score": 80, "remark": None}

        errors = service.validate_with_db_rules(data, module="fund")

        assert errors == ["name: 必须填写名称", "amount: 校验失败"]
        assert service.get_errors() == errors


class TestCheckTypedRule:
    """_check_typed_rule() 全部规则类型分支（行 127-157），True 表示校验失败"""

    def setup_method(self):
        self.service = ValidationEngineService()

    def test_range_min_failure(self):
        assert self.service._check_typed_rule("range", 5, {"min": 10}) is True

    def test_range_max_failure(self):
        assert self.service._check_typed_rule("range", 150, {"max": 100}) is True

    def test_range_invalid_value(self):
        assert self.service._check_typed_rule("range", "abc", {"min": 1}) is True

    def test_range_pass_falls_through_to_false(self):
        assert self.service._check_typed_rule("range", 50, {"min": 0, "max": 100}) is False

    def test_regex_mismatch_and_match(self):
        assert self.service._check_typed_rule("regex", "abc", {"pattern": r"^\d+$"}) is True
        assert self.service._check_typed_rule("regex", "123", {"pattern": r"^\d+$"}) is False

    def test_enum_not_allowed_and_allowed(self):
        assert self.service._check_typed_rule("enum", "x", {"values": ["a", "b"]}) is True
        assert self.service._check_typed_rule("enum", "a", {"values": ["a", "b"]}) is False

    def test_length_min_failure(self):
        assert self.service._check_typed_rule("length", "ab", {"min": 5}) is True

    def test_length_max_failure_and_pass(self):
        assert self.service._check_typed_rule("length", "abcdef", {"max": 3}) is True
        assert self.service._check_typed_rule("length", "abc", {"min": 1, "max": 5}) is False

    def test_positive_branches(self):
        assert self.service._check_typed_rule("positive", -5, {}) is True
        assert self.service._check_typed_rule("positive", 0, {}) is True
        assert self.service._check_typed_rule("positive", 5, {}) is False
        assert self.service._check_typed_rule("positive", "abc", {}) is True

    def test_non_negative_branches(self):
        assert self.service._check_typed_rule("non_negative", -1, {}) is True
        assert self.service._check_typed_rule("non_negative", 0, {}) is False
        assert self.service._check_typed_rule("non_negative", "xyz", {}) is True

    def test_unknown_rule_type_returns_false(self):
        assert self.service._check_typed_rule("cross_field", "v", {}) is False
