"""拨款指令模型

实现指标文数字化解析与拨款文件拆分，
支持拨款金额分配至下级单位虚拟账户，提供拨款状态跟踪。
"""

from sqlalchemy import (
    Column,
    Date,
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


class FundAllocationOrder(Base):
    """拨款指令"""

    __tablename__ = "fund_allocation_orders"

    __table_args__ = (
        Index("ix_fao_fund_id", "fund_id"),
        Index("ix_fao_project_id", "project_id"),
        Index("ix_fao_status", "status"),
        Index("ix_fao_order_no", "order_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联项目ID",
    )
    order_no = Column(String(100), unique=True, nullable=False, comment="拨款指令编号")
    source_document = Column(String(200), nullable=True, comment="指标文编号")
    total_amount = Column(Numeric(15, 4), nullable=False, comment="拨款总金额(万元)")
    allocated_amount = Column(Numeric(15, 4), default=0, comment="已分配金额(万元)")
    target_organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="目标单位ID",
    )
    target_organization_name = Column(String(200), nullable=True, comment="目标单位名称")
    target_account = Column(String(200), nullable=True, comment="目标账户(虚拟或实有)")
    issue_date = Column(Date, nullable=True, comment="下达日期")
    effective_date = Column(Date, nullable=True, comment="生效日期")
    expiry_date = Column(Date, nullable=True, comment="失效日期")
    status = Column(
        String(20),
        default="draft",
        comment="状态: draft/issued/received/completed/cancelled",
    )
    received_at = Column(DateTime(timezone=True), nullable=True, comment="接收时间")
    received_by = Column(String(50), nullable=True, comment="接收人")
    remarks = Column(Text, nullable=True, comment="备注")
    created_by = Column(String(50), nullable=True, comment="创建人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FundAllocationOrder(id={self.id}, order_no={self.order_no}, amount={self.total_amount})>"


class AllocationOrderItem(Base):
    """拨款指令明细（拆分到下级单位）"""

    __tablename__ = "allocation_order_items"

    __table_args__ = (
        Index("ix_aoi_order_id", "order_id"),
        Index("ix_aoi_organization_id", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer,
        ForeignKey("fund_allocation_orders.id", ondelete="SET NULL"),
        nullable=False,
        comment="拨款指令ID",
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="接收单位ID",
    )
    organization_name = Column(String(200), nullable=True, comment="接收单位名称")
    amount = Column(Numeric(15, 4), nullable=False, comment="分配金额(万元)")
    account = Column(String(200), nullable=True, comment="接收账户")
    status = Column(String(20), default="pending", comment="状态: pending/transferred/confirmed")
    transferred_at = Column(DateTime(timezone=True), nullable=True, comment="划转时间")
    confirmed_at = Column(DateTime(timezone=True), nullable=True, comment="确认时间")
    remarks = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<AllocationOrderItem(id={self.id}, amount={self.amount})>"
