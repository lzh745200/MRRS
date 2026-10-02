"""
成效评估模型
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.models.base import Base, UtcDateTime


class EffectivenessEvaluation(Base):
    """成效评估表"""

    __tablename__ = "effectiveness_evaluations"

    __table_args__ = (
        # 同村同年度只应有一份评估：EffectivenessService 按 (village_id, year)
        # 查一取最新后更新（_find_evaluation），缺数据库级唯一约束时并发评估
        # 会插入重复行，排名/取数结果随查询顺序漂移。
        UniqueConstraint("village_id", "year", name="uq_effectiveness_village_year"),
    )

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
        UtcDateTime(), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at = Column(
        UtcDateTime(), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        UtcDateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
