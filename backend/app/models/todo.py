"""待办事项模型"""

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.models.base import Base, UtcDateTime


class Todo(Base):
    """待办事项模型"""

    __tablename__ = "todos"

    __table_args__ = (
        Index("ix_todos_user_completed", "user_id", "completed"),
        Index("ix_todos_priority", "priority"),
        Index("ix_todos_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="待办标题")
    description = Column(Text, nullable=True, comment="待办描述")
    # 存 ISO 日期字符串（YYYY-MM-DD），保留 String(20) 不改列类型（需迁移）：
    # 读取方 backup_scheduler 用 `Todo.deadline >= today_str` 做字典序比较、
    # `strptime(..., "%Y-%m-%d")` 解析 —— 命中与解析都要求写入严格为 ISO 格式。
    deadline = Column(String(20), nullable=True, comment="截止日期（ISO 格式 YYYY-MM-DD）")
    completed = Column(Boolean, default=False, nullable=False, comment="是否完成")
    priority = Column(String(10), default="medium", nullable=False, comment="优先级: high/medium/low")
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属用户ID",
    )

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
        nullable=False,
        comment="更新时间",
    )

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "deadline": self.deadline,
            "completed": self.completed,
            "priority": self.priority,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Todo(id={self.id}, title={self.title}, completed={self.completed})>"
