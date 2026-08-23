"""督查规则模型

支持规则动态配置（启用/禁用/阈值调整），
用于经费异常检测引擎的规则化管理。
"""

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from .base import Base


class InspectionRule(Base):
    """督查规则"""

    __tablename__ = "inspection_rules"

    __table_args__ = (
        Index("ix_ir_rule_code", "rule_code"),
        Index("ix_ir_category", "category"),
        Index("ix_ir_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String(50), unique=True, nullable=False, comment="规则编码")
    name = Column(String(200), nullable=False, comment="规则名称")
    category = Column(
        String(50),
        nullable=False,
        comment="规则类别: overspend/deviation/idle/duplicate/large_cash/contract_split/single_source",
    )
    description = Column(Text, nullable=True, comment="规则描述")
    threshold_value = Column(Numeric(15, 4), nullable=True, comment="阈值")
    threshold_unit = Column(String(30), default="万元", comment="阈值单位")
    severity = Column(String(20), default="warning", comment="默认严重程度: info/warning/danger")
    is_active = Column(Boolean, default=True, comment="是否启用")
    check_expression = Column(Text, nullable=True, comment="检测表达式(供规则引擎解析)")
    suggestion_template = Column(Text, nullable=True, comment="处理建议模板")
    created_by = Column(String(50), nullable=True, comment="创建人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<InspectionRule(id={self.id}, code={self.rule_code}, active={self.is_active})>"
