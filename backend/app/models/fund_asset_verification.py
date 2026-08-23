"""资产联动校验模型

项目完工后自动校验已付款金额与转固资产价值，
作为项目销号的前置校验条件。
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.sql import func

from .base import Base


class FundAssetVerification(Base):
    """经费-资产联动校验记录"""

    __tablename__ = "fund_asset_verifications"

    __table_args__ = (
        Index("ix_fav_project_id", "project_id"),
        Index("ix_fav_settlement_id", "settlement_id"),
        Index("ix_fav_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    settlement_id = Column(
        Integer,
        ForeignKey("fund_settlements.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联决算ID",
    )
    total_paid = Column(Numeric(15, 4), default=0, comment="已付款总额(万元)")
    asset_value = Column(Numeric(15, 4), default=0, comment="转固资产价值(万元)")
    difference = Column(Numeric(15, 4), default=0, comment="差额(万元)")
    difference_rate = Column(Numeric(5, 2), default=0, comment="差异率(%)")
    status = Column(String(20), default="pending", comment="校验状态: pending/passed/failed/waived")
    verified_by = Column(String(50), nullable=True, comment="校验人")
    verified_at = Column(DateTime(timezone=True), nullable=True, comment="校验时间")
    opinion = Column(Text, nullable=True, comment="校验意见")
    remarks = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FundAssetVerification(id={self.id}, project={self.project_id}, status={self.status})>"
