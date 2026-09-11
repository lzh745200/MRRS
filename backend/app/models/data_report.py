"""
DataReport model for managing data submission workflow between organizations.
Tracks the status of data reports from subordinate to superior units.
"""

import enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .data_package import DataPackage  # noqa: F401 - relationship 字符串引用注册
from .organization import Organization  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册


class ReportStatus(str, enum.Enum):
    """上报状态枚举"""

    DRAFT = "draft"  # 草稿
    SUBMITTED = "submitted"  # 已提交
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒绝
    CANCELLED = "cancelled"  # 已取消


class DataReport(Base):
    """
    数据上报模型
    用于跟踪下级单位向上级单位提交数据的状态
    """

    __tablename__ = "data_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_code = Column(String(100), unique=True, index=True, nullable=False, comment="上报编码")
    package_id = Column(
        Integer,
        ForeignKey("data_packages.id", ondelete="SET NULL"),
        nullable=False,
        comment="数据包ID",
    )
    source_org_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        comment="来源组织ID(下级)",
    )
    target_org_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标组织ID(上级)",
    )
    status = Column(String(20), default=ReportStatus.DRAFT.value, nullable=False, comment="状态")
    title = Column(String(200), nullable=True, comment="上报标题")
    # 上报类型（monthly/annual/...）。R29 修复：请求模型把它列为**必填**、响应模型也
    # 回显，但模型没有该列且 service 从未使用 → 调用方必须传一个"传了也没用"的值，
    # 响应里恒为空串（静默丢弃）。
    report_type = Column(String(50), nullable=True, comment="上报类型")
    description = Column(Text, nullable=True, comment="上报说明")
    comment = Column(Text, nullable=True, comment="审批意见")
    rejection_reason = Column(Text, nullable=True, comment="拒绝原因")

    # Submission info
    submitted_at = Column(DateTime(timezone=True), nullable=True, comment="提交时间")
    submitted_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="提交人ID",
    )

    # Review info
    reviewed_at = Column(DateTime(timezone=True), nullable=True, comment="审批时间")
    reviewed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审批人ID",
    )

    # Deadline
    deadline = Column(DateTime(timezone=True), nullable=True, comment="截止时间")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    # Relationships
    package = relationship("DataPackage", backref="reports")
    source_org = relationship("Organization", foreign_keys=[source_org_id], backref="submitted_data_reports")
    target_org = relationship("Organization", foreign_keys=[target_org_id], backref="received_data_reports")
    submitter = relationship("User", foreign_keys=[submitted_by], backref="submitted_reports")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_reports")
    creator = relationship("User", foreign_keys=[created_by], backref="created_reports")

    __table_args__ = (
        Index("ix_data_reports_source_org_id", "source_org_id"),
        Index("ix_data_reports_target_org_id", "target_org_id"),
        Index("ix_data_reports_status", "status"),
        Index("ix_data_reports_submitted_at", "submitted_at"),
        Index("ix_data_reports_deadline", "deadline"),
    )

    def __repr__(self):
        return f"<DataReport(id={self.id}, code='{self.report_code}', status='{self.status}')>"

    @property
    def is_pending(self) -> bool:
        """Check if report is pending review"""
        return self.status == ReportStatus.SUBMITTED.value

    @property
    def is_editable(self) -> bool:
        """Check if report can be edited"""
        return self.status == ReportStatus.DRAFT.value

    @property
    def is_reviewable(self) -> bool:
        """Check if report can be reviewed"""
        return self.status == ReportStatus.SUBMITTED.value

    @property
    def is_overdue(self) -> bool:
        """Check if report is past deadline"""
        if not self.deadline:
            return False
        from datetime import datetime, timezone

        return datetime.now(timezone.utc) > self.deadline and self.status == ReportStatus.DRAFT.value
