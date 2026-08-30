"""
RuralTask Model - 乡村振兴工作任务
RuralWork 的子任务，支持年度管理、审批状态追踪、上下级协作
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base, EncryptedText

from .rural_work import RuralWork  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册
from .village import Village  # noqa: F401 - relationship 字符串引用注册


class TaskCategory(str, Enum):
    """任务分类"""

    infrastructure = "infrastructure"  # 基础设施
    industry = "industry"  # 产业帮扶
    education = "education"  # 教育帮扶
    healthcare = "healthcare"  # 医疗帮扶
    environment = "environment"  # 环境改善
    party_building = "party_building"  # 党建帮扶
    consumption = "consumption"  # 消费帮扶
    employment = "employment"  # 就业帮扶
    other = "other"  # 其他


class TaskStatus(str, Enum):
    """任务状态"""

    draft = "draft"  # 草稿
    pending_approval = "pending_approval"  # 待审批
    approved = "approved"  # 已审批
    rejected = "rejected"  # 已驳回
    in_progress = "in_progress"  # 进行中
    completed = "completed"  # 已完成
    cancelled = "cancelled"  # 已取消


class TaskPriority(str, Enum):
    """优先级"""

    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class RuralTask(Base):
    __tablename__ = "rural_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # 关联乡村工作
    rural_work_id = Column(
        Integer,
        ForeignKey("rural_works.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    # 基本信息
    title = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=True)  # 任务编号 e.g. TASK-2025-001
    category = Column(
        SQLEnum(TaskCategory, native_enum=False),
        default=TaskCategory.other,
        nullable=False,
    )
    status = Column(SQLEnum(TaskStatus, native_enum=False), default=TaskStatus.draft, nullable=False)
    priority = Column(
        SQLEnum(TaskPriority, native_enum=False),
        default=TaskPriority.medium,
        nullable=False,
    )
    # 年度管理
    year = Column(Integer, nullable=False, default=lambda: datetime.now().year)
    quarter = Column(Integer, nullable=True)  # 1-4 季度，可选
    # 任务详情
    description = Column(Text, nullable=True)
    target = Column(Text, nullable=True)  # 预期目标
    result = Column(Text, nullable=True)  # 完成成果
    # 资金信息
    budget = Column(Float, default=0.0)  # 预算(万元)
    actual_cost = Column(Float, default=0.0)  # 实际花费(万元)
    # 进度
    progress = Column(Integer, default=0)  # 0-100
    # 责任人
    responsible_unit = Column(String(100), nullable=True)  # 责任单位
    responsible_person = Column(String(50), nullable=True)  # 负责人
    contact_phone = Column(EncryptedText(64), nullable=True, comment="联系电话(透明加密, ADR-0005)")
    # 时间
    planned_start = Column(DateTime(timezone=True), nullable=True)
    planned_end = Column(DateTime(timezone=True), nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    # 审批
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_comment = Column(Text, nullable=True)
    # 关联帮扶村
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="CASCADE"), nullable=True)
    # 附件（JSON存储文件列表）
    attachments = Column(Text, nullable=True)  # JSON: [{name, path, size}]
    # 审计
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # 关系
    rural_work = relationship("RuralWork", backref="tasks")
    village = relationship("Village", backref="rural_tasks")
    creator = relationship("User", foreign_keys=[created_by], backref="created_rural_tasks")
    updater = relationship("User", foreign_keys=[updated_by], backref="updated_rural_tasks")
    submitter = relationship("User", foreign_keys=[submitted_by])
    approver = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        Index("ix_rural_tasks_work_year", "rural_work_id", "year"),
        Index("ix_rural_tasks_status", "status"),
        Index("ix_rural_tasks_category", "category"),
        Index("ix_rural_tasks_village", "village_id"),
        Index("ix_rural_tasks_year", "year"),
    )
