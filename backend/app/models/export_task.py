"""
ExportTask model for managing data export operations.
Supports both synchronous and asynchronous export with status tracking.
"""

import enum
import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .user import User  # noqa: F401 - relationship 字符串引用注册


class ExportStatus(str, enum.Enum):
    """导出状态枚举"""

    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    EXPIRED = "expired"  # 已过期


class ExportTask(Base):
    """
    导出任务模型
    用于管理数据导出任务，支持同步和异步导出

    Requirements: 2.3 - 大数据量异步导出
    """

    __tablename__ = "export_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="操作用户ID",
    )
    task_id = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment="任务UUID",
    )
    export_type = Column(String(50), nullable=False, comment="导出类型(如: supported_village)")
    query_params = Column(JSON, nullable=True, comment="查询参数 / 筛选条件")
    file_path = Column(String(500), nullable=True, comment="导出文件路径")
    file_name = Column(String(255), nullable=True, comment="导出文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    record_count = Column(Integer, default=0, comment="导出记录数")
    status = Column(
        String(20),
        default=ExportStatus.PENDING.value,
        nullable=False,
        comment="导出状态",
    )
    error_message = Column(Text, nullable=True, comment="错误信息")
    expires_at = Column(DateTime(timezone=True), nullable=True, comment="文件过期时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")

    # Relationships
    user = relationship("User", backref="export_tasks")

    __table_args__ = (
        Index("ix_export_tasks_user_id", "user_id"),
        Index("ix_export_tasks_task_id", "task_id"),
        Index("ix_export_tasks_status", "status"),
        Index("ix_export_tasks_export_type", "export_type"),
        Index("ix_export_tasks_created_at", "created_at"),
        Index("ix_export_tasks_expires_at", "expires_at"),
    )

    def __repr__(self):
        return f"<ExportTask(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"

    @property
    def is_completed(self) -> bool:
        """Check if export is completed"""
        return self.status == ExportStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if export failed"""
        return self.status == ExportStatus.FAILED.value

    @property
    def is_processing(self) -> bool:
        """Check if export is in progress"""
        return self.status == ExportStatus.PROCESSING.value

    @property
    def is_expired(self) -> bool:
        """Check if export file is expired"""
        return self.status == ExportStatus.EXPIRED.value

    @property
    def is_downloadable(self) -> bool:
        """Check if file can be downloaded"""
        from datetime import datetime, timezone

        if self.status != ExportStatus.COMPLETED.value:
            return False
        if self.expires_at:
            expires = self.expires_at
            # SQLite DateTime 列不保留时区信息，读取值为 naive datetime；
            # 统一补上 UTC 时区后再与 aware now 比较，避免 TypeError
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                return False
        return True
