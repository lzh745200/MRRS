"""项目里程碑与变更记录模型"""

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base, UtcDateTime

from .project import Project  # noqa: F401 - relationship 字符串引用注册


class ProjectMilestone(Base):
    """项目里程碑"""

    __tablename__ = "project_milestones"

    __table_args__ = (
        Index("ix_pm_project_id", "project_id"),
        Index("ix_pm_status", "status"),
        Index("ix_pm_planned_date", "planned_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    name = Column(String(200), nullable=False, comment="里程碑名称")
    description = Column(Text, nullable=True, comment="里程碑描述")
    planned_date = Column(Date, nullable=False, comment="计划完成日期")
    actual_date = Column(Date, nullable=True, comment="实际完成日期")
    responsible_person = Column(String(50), nullable=True, comment="负责人")
    status = Column(
        String(20),
        default="pending",
        comment="状态: pending/in_progress/completed/overdue",
    )
    sort_order = Column(Integer, default=0, comment="排序序号")
    created_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    project = relationship("Project", backref="milestones")

    def __repr__(self):
        return f"<ProjectMilestone(id={self.id}, name={self.name}, status={self.status})>"


class ProjectChangeLog(Base):
    """项目变更记录"""

    __tablename__ = "project_change_logs"

    __table_args__ = (
        Index("ix_pcl_project_id", "project_id"),
        Index("ix_pcl_change_type", "change_type"),
        Index("ix_pcl_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    change_type = Column(
        String(50),
        nullable=False,
        comment="变更类型: status/budget/schedule/person/other",
    )
    field_name = Column(String(100), nullable=True, comment="变更字段名")
    old_value = Column(Text, nullable=True, comment="旧值")
    new_value = Column(Text, nullable=True, comment="新值")
    reason = Column(Text, nullable=True, comment="变更原因")
    operator = Column(String(50), nullable=True, comment="操作人")
    operator_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人ID",
    )
    created_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        nullable=False,
        comment="变更时间",
    )

    project = relationship("Project", backref="change_logs")

    def __repr__(self):
        return f"<ProjectChangeLog(id={self.id}, type={self.change_type})>"


# ==================== 项目状态流转引擎 ====================


# 合法的状态流转路径定义
VALID_TRANSITIONS = {
    "draft": ["pending", "cancelled"],
    "pending": ["approved", "draft", "cancelled"],
    "approved": ["in_progress", "cancelled"],
    "in_progress": ["completed", "cancelled"],
    "completed": [],  # 已完成不可变更
    "cancelled": ["draft"],  # 已取消可恢复为草稿
}

# 各阶段准入条件描述（前端也可用于校验提示）
TRANSITION_REQUIREMENTS = {
    ("draft", "pending"): {
        "required_fields": [
            "name",
            "type",
            "budget",
            "start_date",
            "end_date",
            "responsible_person",
        ],
        "description": "提交审批需填写：项目名称、类型、预算、开始日期、结束日期、负责人",
    },
    ("approved", "in_progress"): {
        "required_fields": ["actual_start_date"],
        "description": "启动项目需填写实际开始日期",
    },
    ("in_progress", "completed"): {
        "required_fields": ["actual_end_date", "achievements"],
        "description": "完成项目需填写实际结束日期和项目成果",
    },
}


def validate_status_transition(project, new_status: str) -> dict:
    """
    校验项目状态流转是否合法。

    Returns:
        {"valid": True} 或 {"valid": False, "error": "...", "missing_fields": [...]}
    """
    current = project.status or "draft"

    # 检查流转路径
    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        return {
            "valid": False,
            "error": f"不允许从「{current}」流转到「{new_status}」，可选目标状态: {', '.join(allowed) if allowed else '无'}",
            "missing_fields": [],
        }

    # 检查准入条件
    key = (current, new_status)
    req = TRANSITION_REQUIREMENTS.get(key)
    if req:
        missing = []
        for field in req["required_fields"]:
            val = getattr(project, field, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field)
        if missing:
            return {
                "valid": False,
                "error": req["description"],
                "missing_fields": missing,
            }

    return {"valid": True}


def calculate_milestone_progress(milestones: list) -> int:
    """根据里程碑完成比例计算项目进度百分比"""
    if not milestones:
        return 0
    completed = sum(1 for m in milestones if m.status == "completed")
    return round(completed / len(milestones) * 100)
