"""提醒处置台账（提醒中心处置闭环）。

每条提醒（``messages`` 行）至多一行处置状态：

- ``state``: ``open`` / ``handled`` / ``ignored``
- ``snooze_until``: 延期至（UTC，空=未延期）
- ``note``: 处置说明或忽略原因

设计取舍：
- **独立表而不是 messages 加列** —— 消息中心（站内消息）与提醒中心共用
  ``messages`` 表，处置状态只对提醒类消息有意义；独立表避免改动消息中心的
  读写路径与既有响应形状。
- **不参与跨机数据包**（``DATA_TYPE_MODELS`` 未登记）：处置是"本机某人"的
  操作状态，跨机无意义（message id 跨机不对应）。
- 行按 ``message_id`` 唯一；消息删除后成为孤儿行，读取侧按 join 自然忽略。
"""
from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlalchemy.sql import func

from .base import Base, UtcDateTime


class ReminderDisposition(Base):
    """一条提醒的处置状态（每人每条提醒至多一行）。"""

    __tablename__ = "reminder_dispositions"
    __table_args__ = (
        Index("ix_reminder_dispositions_user_state", "user_id", "state"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    message_id = Column(
        Integer,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="提醒消息ID（唯一）",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="处置人（提醒接收人）",
    )
    state = Column(
        String(16),
        nullable=False,
        default="open",
        comment="处置状态: open / handled / ignored",
    )
    note = Column(String(500), nullable=True, comment="处置说明或忽略原因")
    snooze_until = Column(UtcDateTime(), nullable=True, comment="延期至（UTC，空=未延期）")
    acted_at = Column(UtcDateTime(), nullable=True, comment="最近一次处置动作时间（UTC）")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<ReminderDisposition(message_id={self.message_id}, state='{self.state}')>"
