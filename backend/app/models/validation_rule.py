"""
ValidationRule Model - 数据校验规则
管理员可配置字段级校验规则（必填、正数、日期格式、文件类型、跨字段逻辑等）
"""

from enum import Enum

from sqlalchemy import Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Integer, String, Text, func

from app.models.base import Base, UtcDateTime


class RuleType(str, Enum):
    """规则类型"""

    required = "required"  # 必填
    positive = "positive"  # 正数
    non_negative = "non_negative"  # 非负数
    date_format = "date_format"  # 日期格式
    file_type = "file_type"  # 文件类型限制
    max_length = "max_length"  # 最大长度
    min_length = "min_length"  # 最小长度
    range = "range"  # 数值范围
    regex = "regex"  # 正则表达式
    cross_field = "cross_field"  # 跨字段逻辑 (如 帮扶经费≤项目总预算)
    enum_values = "enum_values"  # 枚举值限制


class ValidationRule(Base):
    __tablename__ = "validation_rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # 所属模块
    module = Column(String(50), nullable=False, index=True)  # village/school/fund/project/rural_task
    # 字段名
    field = Column(String(100), nullable=False)
    # 规则类型
    rule_type = Column(SQLEnum(RuleType, native_enum=False), nullable=False)
    # 规则参数（JSON）- 如 {"min": 0, "max": 100} 或 {"pattern": "^\\d{4}-\\d{2}-\\d{2}$"}
    params = Column(Text, nullable=True)  # JSON string
    # 错误提示信息
    error_message = Column(String(500), nullable=False, default="数据校验失败")
    # 规则描述
    description = Column(String(500), nullable=True)
    # 是否启用
    is_active = Column(Boolean, default=True, nullable=False)
    # 优先级（数字越小优先级越高）
    priority = Column(Integer, default=100, nullable=False)
    # 审计
    created_at = Column(UtcDateTime(), server_default=func.now())
    updated_at = Column(UtcDateTime(), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, nullable=True)
