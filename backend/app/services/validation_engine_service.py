"""
验证引擎服务

提供数据验证功能，支持从DB加载ValidationRule并执行完整规则检查。
"""

import json
import re
from dataclasses import dataclass
import logging
from typing import Optional, Any, Dict, List, Callable
from sqlalchemy.orm import Session

from app.utils.input_validator import InputValidator

logger = logging.getLogger(__name__)


def _load_rule_params(raw: Any) -> Dict[str, Any]:
    """把 ValidationRule.params 反序列化为字典。

    该列是 Text 且存 JSON 字符串；直接当字典用会让 _check_typed_rule 里的
    params.get(...) 抛 AttributeError，被宽 except 吞掉后**所有** range/regex/
    enum/length 规则静默失效（深审 critical）。非法 JSON 一律降级为空规则。
    """
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("校验规则 params 不是合法 JSON，已忽略: %r", raw)
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    errors: List[str]


class ValidationEngineService:
    """
    验证引擎服务

    提供统一的数据验证功能，支持 required/range/regex/enum/length 规则。
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._validators = {}
        self._errors = []

    def validate(self, data: Dict[str, Any], rules: Dict[str, Any]) -> List[str]:
        """
        验证数据

        Args:
            data: 待验证的数据
            rules: 验证规则字典，格式:
                {field: {"required": bool, "min": num, "max": num,
                         "pattern": str, "enum": list, "min_length": int, "max_length": int}}

        Returns:
            List[str]: 错误列表，空列表表示验证通过
        """
        errors = []
        for field, rule in rules.items():
            value = data.get(field)

            # required 检查
            if rule.get("required") and (value is None or (isinstance(value, str) and value.strip() == "")):
                errors.append(f"{field} 为必填项")
                continue

            if value is None:
                continue

            # range 检查
            if "min" in rule or "max" in rule:
                try:
                    v = float(value)
                    if rule.get("min") is not None and v < float(rule["min"]):
                        errors.append(f"{field} 不能小于 {rule['min']}")
                    if rule.get("max") is not None and v > float(rule["max"]):
                        errors.append(f"{field} 不能大于 {rule['max']}")
                except (ValueError, TypeError):
                    errors.append(f"{field} 必须为数字")

            # regex 检查
            if "pattern" in rule:
                if not re.match(rule["pattern"], str(value)):
                    errors.append(f"{field} 格式不正确")

            # enum 检查
            if "enum" in rule and value not in rule["enum"]:
                errors.append(f"{field} 必须为以下值之一: {rule['enum']}")

            # length 检查
            str_val = str(value)
            if "min_length" in rule and len(str_val) < rule["min_length"]:
                errors.append(f"{field} 长度不能少于 {rule['min_length']}")
            if "max_length" in rule and len(str_val) > rule["max_length"]:
                errors.append(f"{field} 长度不能超过 {rule['max_length']}")

        self._errors = errors
        return errors

    def validate_with_db_rules(self, data: Dict[str, Any], module: str) -> List[str]:
        """从DB加载ValidationRule并执行验证"""
        if not self.db:
            return self.validate(data, {})

        try:
            from app.models.validation_rule import ValidationRule
            db_rules = self.db.query(ValidationRule).filter(
                ValidationRule.module == module,
                ValidationRule.is_active == True,  # noqa: E712
            ).order_by(ValidationRule.priority.desc()).all()

            errors = []
            for rule in db_rules:
                field = rule.field
                value = data.get(field)
                params = _load_rule_params(rule.params)

                if rule.rule_type == "required":
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        errors.append(f"{field}: {rule.error_message or '为必填项'}")
                elif value is not None:
                    failed = self._check_typed_rule(rule.rule_type, value, params)
                    if failed:
                        errors.append(f"{field}: {rule.error_message or '校验失败'}")

            self._errors = errors
            return errors
        except Exception:  # pragma: no cover
            logger.debug("DB规则加载失败，跳过", exc_info=True)
            return []

    def _check_typed_rule(self, rule_type: str, value, params: dict) -> bool:  # noqa: C901 - 校验规则多类型分支,保持单函数便于审计
        """执行类型化规则检查，返回 True 表示校验失败"""
        if rule_type == "range":
            try:
                v = float(value)
                if params.get("min") is not None and v < float(params["min"]):
                    return True
                if params.get("max") is not None and v > float(params["max"]):
                    return True
            except (ValueError, TypeError):
                return True
        elif rule_type == "regex":
            return not re.match(params.get("pattern", ""), str(value))
        elif rule_type == "enum":
            allowed = params.get("values", [])
            return str(value) not in [str(a) for a in allowed]
        elif rule_type == "length":
            str_val = str(value)
            if params.get("min") is not None and len(str_val) < int(params["min"]):
                return True
            if params.get("max") is not None and len(str_val) > int(params["max"]):
                return True
        elif rule_type == "positive":
            try:
                return float(value) <= 0
            except (ValueError, TypeError):
                return True
        elif rule_type == "non_negative":
            try:
                return float(value) < 0
            except (ValueError, TypeError):
                return True
        return False

    def register_validator(self, name: str, validator: Any):
        """注册验证器"""
        self._validators[name] = validator

    def add_rule(self, name: str, validator: Callable):
        """添加验证规则"""
        self._validators[name] = validator

    def get_errors(self) -> List[str]:
        """获取错误列表"""
        return self._errors

    def clear_errors(self):
        """清除错误"""
        self._errors = []


# 别名导出
ValidationEngine = ValidationEngineService


def validate_entity(data: Dict[str, Any], rules: Dict[str, Any]) -> ValidationResult:
    """验证实体"""
    service = ValidationEngineService()
    errors = service.validate(data, rules)
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_string_length(value: str, min_len: int, max_len: int) -> bool:
    """验证字符串长度"""
    if not isinstance(value, str):
        return False
    return min_len <= len(value) <= max_len


def validate_email_format(email: str) -> bool:
    """验证邮箱格式（委托给 InputValidator）"""
    return InputValidator.validate_email(email)


def validate_phone_format(phone: str) -> bool:
    """验证手机号格式（委托给 InputValidator）"""
    return InputValidator.validate_phone(phone)


def validate_number_range(value: float, min_val: float, max_val: float) -> bool:
    """验证数字范围（委托给 InputValidator）"""
    return InputValidator.validate_number_range(value, min_val, max_val)


def validate_required_fields(data: Dict[str, Any], fields: List[str]) -> bool:
    """验证必填字段（委托给 InputValidator）"""
    try:
        InputValidator.validate_required_fields(data, fields)
        return True
    except Exception as e:
        logging.getLogger(__name__).debug("validate_required_fields failed: %s", e)
        return False
