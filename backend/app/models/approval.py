"""
Approval workflow models for multi - level approval process.
Supports configurable approval workflows with up to 5 levels.

Requirements: 3.1, 3.2, 3.4 - Multi - level approval workflow
"""

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .user import User  # noqa: F401 - relationship 字符串引用注册


class ApproverType(str, enum.Enum):
    """审批人类型枚举"""

    USER = "user"  # 指定用户
    ROLE = "role"  # 指定角色


class ApprovalStatus(str, enum.Enum):
    """审批状态枚举"""

    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已通过
    REJECTED = "rejected"  # 已拒绝
    WITHDRAWN = "withdrawn"  # 已撤回


class ApprovalAction(str, enum.Enum):
    """审批操作枚举"""

    APPROVE = "approve"  # 通过
    REJECT = "reject"  # 拒绝
    TRANSFER = "transfer"  # 转交


class ApprovalWorkflow(Base):
    """
    审批流程配置模型
    用于定义不同实体类型的审批流程

    Requirements: 3.1 - 支持配置多级审批流程（最多支持5级）
    """

    __tablename__ = "approval_workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="流程名称")
    entity_type = Column(String(50), nullable=False, comment="实体类型(如: supported_village)")
    description = Column(Text, nullable=True, comment="流程描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    # Relationships
    nodes = relationship(
        "ApprovalNode",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="ApprovalNode.level",
    )
    tasks = relationship("ApprovalTask", back_populates="workflow")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_approval_workflows_entity_type", "entity_type"),
        Index("ix_approval_workflows_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<ApprovalWorkflow(id={self.id}, name='{self.name}', entity_type='{self.entity_type}')>"

    @property
    def level_count(self) -> int:
        """获取审批级别数量"""
        return len(self.nodes) if self.nodes else 0


class ApprovalNode(Base):
    """
    审批节点模型
    定义审批流程中的每个审批步骤

    Requirements: 3.3 - 支持配置审批人或审批角色
    """

    __tablename__ = "approval_nodes"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False, comment="审批级别 1 - 5")
    name = Column(String(100), nullable=False, comment="节点名称")
    approver_type = Column(
        String(20),
        nullable=False,
        default=ApproverType.USER.value,
        comment="审批人类型: user / role",
    )
    approver_id = Column(Integer, nullable=True, comment="审批人ID或角色ID")
    timeout_hours = Column(Integer, default=24, comment="超时时间(小时)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    # Relationships
    workflow = relationship("ApprovalWorkflow", back_populates="nodes")

    __table_args__ = (
        Index("ix_approval_nodes_workflow_id", "workflow_id"),
        Index("ix_approval_nodes_level", "level"),
        Index("ix_approval_nodes_approver", "approver_type", "approver_id"),
    )

    def __repr__(self):
        return f"<ApprovalNode(id={self.id}, level={self.level}, name='{self.name}')>"


class ApprovalTask(Base):
    """
    审批任务模型
    记录每个需要审批的数据变更请求

    Requirements: 3.2 - 自动创建审批任务
    Requirements: 3.4 - 记录审批意见和审批时间
    """

    __tablename__ = "approval_tasks"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(50), nullable=False, comment="实体类型")
    entity_id = Column(Integer, nullable=False, comment="实体ID")
    submitter_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="提交人ID",
    )
    current_level = Column(Integer, default=1, comment="当前审批级别")
    current_approver_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="当前审批人ID",
    )
    status = Column(
        String(20),
        default=ApprovalStatus.PENDING.value,
        nullable=False,
        comment="审批状态",
    )
    change_data = Column(JSON, nullable=True, comment="变更后的数据")
    original_data = Column(JSON, nullable=True, comment="变更前的数据")
    priority = Column(Integer, default=0, comment="优先级(数值越大越优先)")
    title = Column(String(200), nullable=True, comment="审批标题")
    description = Column(Text, nullable=True, comment="审批说明")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")

    # Relationships
    workflow = relationship("ApprovalWorkflow", back_populates="tasks")
    submitter = relationship("User", foreign_keys=[submitter_id], backref="submitted_approvals")
    current_approver = relationship("User", foreign_keys=[current_approver_id])
    records = relationship(
        "ApprovalRecord",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="ApprovalRecord.created_at",
    )

    __table_args__ = (
        Index("ix_approval_tasks_workflow_id", "workflow_id"),
        Index("ix_approval_tasks_entity", "entity_type", "entity_id"),
        Index("ix_approval_tasks_submitter_id", "submitter_id"),
        Index("ix_approval_tasks_current_approver_id", "current_approver_id"),
        Index("ix_approval_tasks_status", "status"),
        Index("ix_approval_tasks_priority_created", "priority", "created_at"),
    )

    def __repr__(self):
        return f"<ApprovalTask(id={self.id}, entity='{self.entity_type}:{self.entity_id}', status='{self.status}')>"

    @property
    def is_pending(self) -> bool:
        """是否待审批"""
        return self.status == ApprovalStatus.PENDING.value

    @property
    def is_approved(self) -> bool:
        """是否已通过"""
        return self.status == ApprovalStatus.APPROVED.value

    @property
    def is_rejected(self) -> bool:
        """是否已拒绝"""
        return self.status == ApprovalStatus.REJECTED.value

    @property
    def is_withdrawn(self) -> bool:
        """是否已撤回"""
        return self.status == ApprovalStatus.WITHDRAWN.value


class ApprovalRecord(Base):
    """
    审批记录模型
    记录每次审批操作的详细信息

    Requirements: 3.4 - 记录审批意见和审批时间
    Requirements: 3.7 - 支持审批转交
    """

    __tablename__ = "approval_records"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("approval_tasks.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False, comment="审批级别")
    approver_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审批人ID(用户删除后置空，审批留痕保留)",
    )
    action = Column(String(20), nullable=False, comment="审批操作: approve / reject / transfer")
    opinion = Column(Text, nullable=True, comment="审批意见")
    transfer_to_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="转交目标用户ID",
    )
    transfer_reason = Column(Text, nullable=True, comment="转交原因")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="审批时间")

    # Relationships
    task = relationship("ApprovalTask", back_populates="records")
    approver = relationship("User", foreign_keys=[approver_id], backref="approval_records")
    transfer_to = relationship("User", foreign_keys=[transfer_to_id])

    __table_args__ = (
        Index("ix_approval_records_task_id", "task_id"),
        Index("ix_approval_records_approver_id", "approver_id"),
        Index("ix_approval_records_level", "level"),
        Index("ix_approval_records_action", "action"),
        Index("ix_approval_records_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<ApprovalRecord(id={self.id}, task_id={self.task_id}, action='{self.action}')>"

    @property
    def is_approved(self) -> bool:
        """是否通过"""
        return self.action == ApprovalAction.APPROVE.value

    @property
    def is_rejected(self) -> bool:
        """是否拒绝"""
        return self.action == ApprovalAction.REJECT.value

    @property
    def is_transferred(self) -> bool:
        """是否转交"""
        return self.action == ApprovalAction.TRANSFER.value


# 向后兼容别名：ApprovalInstance = ApprovalRecord
# business_metrics_service.py 使用此别名
ApprovalInstance = ApprovalRecord
