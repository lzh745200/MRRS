"""
成效评估模型
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)

from app.models.base import Base


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
