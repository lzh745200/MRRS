"""Project model."""

from enum import Enum

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .user import User  # noqa: F401 - relationship 字符串引用注册


class ProjectStatus(str, Enum):
    """Project status enum."""

    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectType(str, Enum):
    """Project type enum."""

    INFRASTRUCTURE = "infrastructure"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    AGRICULTURE = "agriculture"
    INDUSTRY = "industry"
    OTHER = "other"


class Project(Base):
    """Project model for rural revitalization projects."""

    __tablename__ = "projects"

    __table_args__ = (
        # 单列索引
        Index("ix_projects_status", "status"),
        Index("ix_projects_type", "type"),
        Index("ix_projects_village_id", "village_id"),
        Index("ix_projects_organization_id", "organization_id"),
        Index("ix_projects_created_by", "created_by"),
        # 复合索引 - 优化常见查询组合
        Index("ix_projects_status_type", "status", "type"),
        Index("ix_projects_status_created", "status", "created_at"),  # 按状态和时间排序
        Index("ix_projects_village_status", "village_id", "status"),  # 村庄级别的项目过滤
        Index("ix_projects_org_status", "organization_id", "status"),  # 组织级别的数据权限过滤
        Index("ix_projects_start_date", "start_date"),  # 按开始日期查询
        Index("ix_projects_end_date", "end_date"),  # 按结束日期查询
        Index("ix_projects_status_village", "status", "village_id"),  # 按状态+村过滤（与 ix_projects_village_status 列序互补）
        Index("ix_projects_is_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True, comment="项目名称")
    code = Column(String(50), unique=True, nullable=True, comment="项目编号")
    type = Column(String(50), default=ProjectType.OTHER.value, comment="项目类型")
    status = Column(String(20), default=ProjectStatus.DRAFT.value, comment="状态")

    description = Column(Text, nullable=True, comment="项目描述")
    objectives = Column(Text, nullable=True, comment="项目目标")

    # 注意：此列引用 supported_villages.id（帮扶村），而非 villages.id（普通村庄）
    # 保持列名 village_id 以兼容现有数据，仅添加说明注释
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=True,
        comment="帮扶村庄ID (references supported_villages.id, not villages.id)",
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="负责单位ID",
    )

    budget = Column(Numeric(15, 2), default=0, comment="预算金额")
    actual_cost = Column(Numeric(15, 2), default=0, comment="实际花费")
    invested_amount = Column(Numeric(15, 2), default=0, comment="已投资金额")

    start_date = Column(Date, nullable=True, comment="开始日期")
    end_date = Column(Date, nullable=True, comment="结束日期")
    actual_start_date = Column(Date, nullable=True, comment="实际开始日期")
    actual_end_date = Column(Date, nullable=True, comment="实际结束日期")

    progress = Column(Integer, default=0, comment="进度百分比")
    priority = Column(String(20), default="medium", comment="优先级: low/medium/high")

    leader = Column(String(50), nullable=True, comment="项目负责人")
    contact = Column(String(50), nullable=True, comment="联系方式")
    responsible_unit = Column(String(200), nullable=True, comment="负责单位")
    responsible_person = Column(String(50), nullable=True, comment="负责人")
    contact_phone = Column(String(20), nullable=True, comment="联系电话")

    # 资金来源与拨付信息
    fund_source = Column(String(50), nullable=True, comment="资金来源")
    payer_account_name = Column(String(200), nullable=True, comment="拨款账户名称")
    payer_account_number = Column(String(50), nullable=True, comment="拨款卡号")
    payer_bank = Column(String(200), nullable=True, comment="拨款开户行")
    payer_handler = Column(String(50), nullable=True, comment="拨款经办人")
    payer_contact = Column(String(50), nullable=True, comment="拨款方联系方式")
    payee_account_name = Column(String(200), nullable=True, comment="收款单位账户名称")
    payee_account_number = Column(String(50), nullable=True, comment="收款卡号")
    payee_bank = Column(String(200), nullable=True, comment="收款开户行")
    payee_handler = Column(String(50), nullable=True, comment="收款经办人")
    payee_contact = Column(String(50), nullable=True, comment="收款方联系方式")

    # 扩展字段
    urgency_level = Column(String(20), default="normal", comment="紧急程度")
    contract_number = Column(String(50), nullable=True, comment="合同编号")
    fund_manager = Column(String(50), nullable=True, comment="资金负责人")
    fund_usage_plan = Column(String(50), nullable=True, comment="资金使用计划")
    is_delayed = Column(Boolean, default=False, comment="是否延期")
    delay_reason = Column(Text, nullable=True, comment="延期原因")
    expected_benefits = Column(Text, nullable=True, comment="预期效益")
    achievements = Column(Text, nullable=True, comment="项目成果")
    tags = Column(String(500), nullable=True, comment="项目标签(逗号分隔)")
    remarks = Column(Text, nullable=True, comment="备注")

    # 经费管理扩展 —— 论证立项阶段经济指标
    total_budget_estimate = Column(Numeric(15, 2), nullable=True, comment="经费总预算估算(万元)")
    fund_source_category = Column(Text, nullable=True, comment="资金来源分类(JSON)")
    expected_economic_benefit = Column(Text, nullable=True, comment="预期经济效益量化指标")
    expected_military_benefit = Column(Text, nullable=True, comment="预期效益量化指标")

    # ================= 软删标记 =================
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用(软删标记)")

    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    # Relationships
    creator = relationship("User", back_populates="projects", foreign_keys=[created_by])
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")
    funds = relationship("Fund", back_populates="project")

    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "type": self.type,
            "status": self.status,
            "description": self.description,
            "objectives": self.objectives,
            "village_id": self.village_id,
            "organization_id": self.organization_id,
            "budget": float(self.budget) if self.budget else 0,
            "actual_cost": float(self.actual_cost) if self.actual_cost else 0,
            "invested_amount": (float(self.invested_amount) if self.invested_amount else 0),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "actual_start_date": (self.actual_start_date.isoformat() if self.actual_start_date else None),
            "actual_end_date": (self.actual_end_date.isoformat() if self.actual_end_date else None),
            "progress": self.progress,
            "leader": self.leader,
            "contact": self.contact,
            "responsible_unit": self.responsible_unit,
            "responsible_person": self.responsible_person,
            "contact_phone": self.contact_phone,
            "fund_source": self.fund_source,
            "fund_manager": self.fund_manager,
            "fund_usage_plan": self.fund_usage_plan,
            "urgency_level": self.urgency_level,
            "contract_number": self.contract_number,
            "payer_account_name": self.payer_account_name,
            "payer_account_number": self.payer_account_number,
            "payer_bank": self.payer_bank,
            "payer_handler": self.payer_handler,
            "payer_contact": self.payer_contact,
            "payee_account_name": self.payee_account_name,
            "payee_account_number": self.payee_account_number,
            "payee_bank": self.payee_bank,
            "payee_handler": self.payee_handler,
            "payee_contact": self.payee_contact,
            "is_delayed": (bool(self.is_delayed) if self.is_delayed is not None else False),
            "delay_reason": self.delay_reason,
            "expected_benefits": self.expected_benefits,
            "achievements": self.achievements,
            "tags": self.tags,
            "remarks": self.remarks,
            "is_active": self.is_active,
            "isActive": self.is_active,
            "isDeleted": self.is_active is False,
            "is_deleted": self.is_active is False,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# 重新导出 Fund 以兼容 from app.models.project import Fund 的写法
from app.models.fund import Fund  # noqa: E402, F401


class ProjectTask(Base):
    """项目任务模型"""

    __tablename__ = "project_tasks"

    __table_args__ = (
        Index("ix_project_tasks_project_id", "project_id"),
        Index("ix_project_tasks_status", "status"),
        Index("ix_project_tasks_priority", "priority"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    name = Column(String(200), nullable=False, comment="任务名称")
    description = Column(Text, nullable=True, comment="任务描述")
    status = Column(String(20), default="pending", comment="状态")
    priority = Column(Integer, default=0, comment="优先级")
    assignee = Column(String(50), nullable=True, comment="负责人")
    due_date = Column(Date, nullable=True, comment="截止日期")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    project = relationship("Project", back_populates="tasks")

    def __repr__(self):
        return f"<ProjectTask(id={self.id}, name={self.name})>"


class ProjectFile(Base):
    """项目附件模型 — 按阶段分类存储"""

    __tablename__ = "project_files"

    __table_args__ = (
        Index("ix_project_files_project_id", "project_id"),
        Index("ix_project_files_category", "category"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    category = Column(
        String(30),
        nullable=False,
        comment="分类: research/implementation/acceptance/photo",
    )
    filename = Column(String(300), nullable=False, comment="原始文件名")
    filepath = Column(String(500), nullable=False, comment="存储路径")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="上传人ID",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="上传时间",
    )

    project = relationship("Project", backref="files")

    def __repr__(self):
        return f"<ProjectFile(id={self.id}, filename={self.filename}, category={self.category})>"
