"""
Notification preference model for user notification settings.
Allows users to configure which notifications they want to receive.

Requirements: 6.2 - Support user notification preference configuration
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .user import User  # noqa: F401 - relationship 字符串引用注册


class NotificationPreference(Base):
    """
    通知偏好设置模型
    用于存储用户的通知偏好配置

    Requirements: 6.2 - 支持用户配置邮件通知偏好（开启 / 关闭各类通知）
    """

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    # 通知偏好是纯粹的"每用户设置"，无审计价值：用户删除时随用户一并清除
    # （原 SET NULL 与 nullable=False 自相矛盾，删用户必然 IntegrityError）。
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="用户ID(用户删除时偏好一并清除)",
    )

    # 邮件通知偏好
    email_approval = Column(Boolean, default=True, comment="邮件 - 审批通知")
    email_task = Column(Boolean, default=True, comment="邮件 - 任务提醒")
    email_system = Column(Boolean, default=False, comment="邮件 - 系统通知")

    # 站内消息偏好
    site_approval = Column(Boolean, default=True, comment="站内 - 审批通知")
    site_task = Column(Boolean, default=True, comment="站内 - 任务提醒")
    site_system = Column(Boolean, default=True, comment="站内 - 系统通知")

    # WebSocket实时推送偏好
    push_approval = Column(Boolean, default=True, comment="推送 - 审批通知")
    push_task = Column(Boolean, default=True, comment="推送 - 任务提醒")
    push_system = Column(Boolean, default=True, comment="推送 - 系统通知")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    # Relationships
    # passive_deletes=True：由数据库 ON DELETE CASCADE 清理，ORM 不得先把
    # user_id 置空（非空列置空 → IntegrityError）。
    user = relationship(
        "User",
        backref=backref(
            "notification_preference",
            uselist=False,
            cascade="all, delete-orphan",
            passive_deletes=True,
        ),
    )

    __table_args__ = (Index("ix_notification_preferences_user_id", "user_id"),)

    def __repr__(self):
        return f"<NotificationPreference(id={self.id}, user_id={self.user_id})>"

    def should_send_email(self, message_type: str) -> bool:
        """
        检查是否应该发送邮件通知

        Args:
            message_type: 消息类型 (system / approval / task)

        Returns:
            是否应该发送邮件
        """
        type_map = {
            "system": self.email_system,
            "approval": self.email_approval,
            "task": self.email_task,
        }
        return type_map.get(message_type, False)

    def should_send_site_message(self, message_type: str) -> bool:
        """
        检查是否应该发送站内消息

        Args:
            message_type: 消息类型 (system / approval / task)

        Returns:
            是否应该发送站内消息
        """
        type_map = {
            "system": self.site_system,
            "approval": self.site_approval,
            "task": self.site_task,
        }
        return type_map.get(message_type, True)

    def should_push(self, message_type: str) -> bool:
        """
        检查是否应该推送实时通知

        Args:
            message_type: 消息类型 (system / approval / task)

        Returns:
            是否应该推送
        """
        type_map = {
            "system": self.push_system,
            "approval": self.push_approval,
            "task": self.push_task,
        }
        return type_map.get(message_type, True)

    @classmethod
    def get_default_preferences(cls) -> dict:
        """
        获取默认通知偏好配置

        Returns:
            默认配置字典
        """
        return {
            "email_approval": True,
            "email_task": True,
            "email_system": False,
            "site_approval": True,
            "site_task": True,
            "site_system": True,
            "push_approval": True,
            "push_task": True,
            "push_system": True,
        }
