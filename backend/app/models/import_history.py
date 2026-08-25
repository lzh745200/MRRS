"""
ImportHistory model for tracking Excel import operations.
Records import history including success / failure counts and error details.
"""

import enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .user import User  # noqa: F401 - relationship 字符串引用注册


class ImportMode(str, enum.Enum):
    """导入模式枚举"""

    INCREMENTAL = "incremental"  # 增量导入
    FULL = "full"  # 全量覆盖


class ImportStatus(str, enum.Enum):
    """导入状态枚举"""

    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class ImportHistory(Base):
    """
    导入历史记录模型
    用于记录Excel批量导入操作的历史和结果

    Requirements: 1.8 - 导入完成后生成导入结果报告
    """

    __tablename__ = "import_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作用户ID(用户删除后置空，导入历史作为合规留痕保留)",
    )
    file_name = Column(String(255), nullable=False, comment="上传文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    import_mode = Column(
        String(20),
        nullable=False,
        default=ImportMode.INCREMENTAL.value,
        comment="导入模式: incremental / full",
    )
    entity_type = Column(String(50), nullable=False, comment="导入实体类型(如: supported_village)")
    total_rows = Column(Integer, default=0, comment="总行数")
    success_rows = Column(Integer, default=0, comment="成功行数")
    failed_rows = Column(Integer, default=0, comment="失败行数")
    error_details = Column(JSON, nullable=True, comment="错误详情列表")
    status = Column(
        String(20),
        default=ImportStatus.PENDING.value,
        nullable=False,
        comment="导入状态",
    )
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    # Relationships
    user = relationship("User", backref="import_histories")

    __table_args__ = (
        Index("ix_import_histories_user_id", "user_id"),
        Index("ix_import_histories_status", "status"),
        Index("ix_import_histories_entity_type", "entity_type"),
        Index("ix_import_histories_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<ImportHistory(id={self.id}, file='{self.file_name}', status='{self.status}')>"

    @property
    def is_completed(self) -> bool:
        """Check if import is completed"""
        return self.status == ImportStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if import failed"""
        return self.status == ImportStatus.FAILED.value

    @property
    def is_processing(self) -> bool:
        """Check if import is in progress"""
        return self.status == ImportStatus.PROCESSING.value

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if not self.total_rows or not self.success_rows:
            return 0.0
        return (self.success_rows / self.total_rows) * 100
