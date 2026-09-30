"""
Message template model for managing notification templates.
Supports variable placeholders for dynamic content generation.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5 - Message template management
"""

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base


class MessageTemplate(Base):
    """
    消息模板模型
    用于管理站内消息和邮件通知的模板

    Requirements: 7.1 - 提供消息模板管理界面
    Requirements: 7.2 - 支持变量占位符（如用户名、时间、链接等）
    Requirements: 7.3 - 预置常用消息模板
    Requirements: 7.4 - 记录修改历史
    Requirements: 7.5 - 支持模板的启用和禁用
    """

    __tablename__ = "message_templates"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, comment="模板编码")
    name = Column(String(100), nullable=False, comment="模板名称")
    message_type = Column(String(20), nullable=False, comment="消息类型: system / approval / task")
    title_template = Column(String(200), nullable=False, comment="标题模板")
    content_template = Column(Text, nullable=False, comment="内容模板")
    email_subject_template = Column(String(200), nullable=True, comment="邮件主题模板")
    email_body_template = Column(Text, nullable=True, comment="邮件正文模板")
    description = Column(Text, nullable=True, comment="模板描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_system = Column(Boolean, default=False, comment="是否为系统预置模板")
    created_by = Column(Integer, nullable=True, comment="创建人ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index("ix_message_templates_code", "code"),
        Index("ix_message_templates_message_type", "message_type"),
        Index("ix_message_templates_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<MessageTemplate(id={self.id}, code='{self.code}', name='{self.name}')>"

    def render_title(self, variables: dict) -> str:
        """
        渲染标题模板

        Args:
            variables: 变量字典，如 {"username": "张三", "time": "2024 - 01 - 01"}

        Returns:
            渲染后的标题
        """
        try:
            return self.title_template.format(**variables)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError):
            # 模板可能含位置占位符 {} / {0}（IndexError）、未转义花括号（ValueError），
            # 或 {user.name} 这类属性访问（AttributeError/TypeError）——模板由管理员
            # 在库存改，任何一类都不许穿透成 500（深审 LIVE）。
            return self.title_template

    def render_content(self, variables: dict) -> str:
        """
        渲染内容模板

        Args:
            variables: 变量字典

        Returns:
            渲染后的内容
        """
        try:
            return self.content_template.format(**variables)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError):
            return self.content_template

    def render_email_subject(self, variables: dict) -> str:
        """
        渲染邮件主题模板

        Args:
            variables: 变量字典

        Returns:
            渲染后的邮件主题
        """
        if not self.email_subject_template:
            return self.render_title(variables)
        try:
            return self.email_subject_template.format(**variables)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError):
            return self.email_subject_template

    def render_email_body(self, variables: dict) -> str:
        """
        渲染邮件正文模板

        Args:
            variables: 变量字典

        Returns:
            渲染后的邮件正文
        """
        if not self.email_body_template:
            return self.render_content(variables)
        try:
            return self.email_body_template.format(**variables)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError):
            return self.email_body_template


# 预置模板编码常量
class TemplateCode:
    """预置模板编码"""

    # 审批相关
    APPROVAL_SUBMITTED = "approval_submitted"  # 审批已提交
    APPROVAL_APPROVED = "approval_approved"  # 审批已通过
    APPROVAL_REJECTED = "approval_rejected"  # 审批已拒绝
    APPROVAL_TRANSFERRED = "approval_transferred"  # 审批已转交
    APPROVAL_WITHDRAWN = "approval_withdrawn"  # 审批已撤回
    APPROVAL_PENDING = "approval_pending"  # 待审批提醒
    APPROVAL_TIMEOUT = "approval_timeout"  # 审批超时提醒

    # 任务相关
    TASK_ASSIGNED = "task_assigned"  # 任务已分配
    TASK_COMPLETED = "task_completed"  # 任务已完成
    TASK_REMINDER = "task_reminder"  # 任务提醒

    # 系统相关
    SYSTEM_ANNOUNCEMENT = "system_announcement"  # 系统公告
    SYSTEM_MAINTENANCE = "system_maintenance"  # 系统维护通知
    IMPORT_COMPLETED = "import_completed"  # 导入完成通知
    EXPORT_COMPLETED = "export_completed"  # 导出完成通知
