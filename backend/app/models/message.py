"""
Message notification models for site messages and email notifications.
Supports system notifications, approval notifications, and task reminders.

Requirements: 5.1, 6.7, 7.1 - Message center and notification system
"""

import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.models.base import Base


class MessageType(str, enum.Enum):
    """消息类型枚举"""

    SYSTEM = "system"  # 系统通知
    APPROVAL = "approval"  # 审批通知
    TASK = "task"  # 任务提醒
    BACKUP = "backup"  # 备份提醒


class Message(Base):
    """
    站内消息模型
    用于存储用户的站内消息通知

    Requirements: 5.1 - 支持发送系统通知、审批通知、任务提醒三种消息类型
    Requirements: 5.2 - 显示未读消息数量
    Requirements: 5.4 - 标记消息为已读
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="接收用户ID",
    )
    message_type = Column(String(20), nullable=False, comment="消息类型: system / approval / task / backup")
    title = Column(String(200), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")
    link = Column(String(500), nullable=True, comment="关联链接")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    read_at = Column(DateTime(timezone=True), nullable=True, comment="阅读时间")

    __table_args__ = (
        Index("ix_messages_user_id", "user_id"),
        Index("ix_messages_message_type", "message_type"),
        Index("ix_messages_is_read", "is_read"),
        Index("ix_messages_created_at", "created_at"),
        Index("ix_messages_user_unread", "user_id", "is_read"),
        Index("idx_messages_user_read_created", "user_id", "is_read", "created_at"),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, type='{self.message_type}', title='{self.title[:20]}...')>"

    @property
    def is_system(self) -> bool:
        """是否为系统消息"""
        return self.message_type == MessageType.SYSTEM.value

    @property
    def is_approval(self) -> bool:
        """是否为审批消息"""
        return self.message_type == MessageType.APPROVAL.value

    @property
    def is_task(self) -> bool:
        """是否为任务消息"""
        return self.message_type == MessageType.TASK.value
