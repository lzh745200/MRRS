"""
成效评估模型
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.models.base import Base


class EffectivenessIndicator(Base):
    """评估指标表"""

    __tablename__ = "effectiveness_indicators"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    category = Column(String(50), nullable=False, index=True)  # economic/social/ecological
    description = Column(Text, nullable=True)
    calculation_formula = Column(Text, nullable=False)  # 计算公式
    weight = Column(Float, nullable=False, default=1.0)  # 权重
    unit = Column(String(20), nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class EffectivenessEvaluation(Base):
    """成效评估表"""

    __tablename__ = "effectiveness_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year = Column(Integer, nullable=False, index=True)
    indicators = Column(JSON, nullable=False)  # {indicator_id: value}
    economic_score = Column(Float, nullable=False)  # 经济指标得分
    social_score = Column(Float, nullable=False)  # 社会指标得分
    ecological_score = Column(Float, nullable=False)  # 生态指标得分
    total_score = Column(Float, nullable=False)  # 总分
    rank = Column(Integer, nullable=True)  # 排名
    grade = Column(String(10), nullable=True)  # 等级(A/B/C/D)
    report_path = Column(String(500), nullable=True)  # 报告文件路径
    evaluated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    evaluated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
