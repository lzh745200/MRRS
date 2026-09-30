"""
ImportExportHistory model for audit trail of data package operations.
Tracks all import and export operations for compliance and debugging.
"""

import enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base

from .data_package import DataPackage  # noqa: F401 - relationship 字符串引用注册
from .organization import Organization  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册


class OperationType(str, enum.Enum):
    """操作类型枚举"""

    EXPORT = "export"  # 导出
    IMPORT = "import"  # 导入
    PREVIEW = "preview"  # 预览
    VALIDATE = "validate"  # 验证
    CONFIRM = "confirm"  # 确认导入
    CANCEL = "cancel"  # 取消
    DELETE = "delete"  # 删除


class OperationResult(str, enum.Enum):
    """操作结果枚举"""

    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    PARTIAL = "partial"  # 部分成功


class ImportExportHistory(Base):
    """
    导入导出历史记录模型
    用于审计追踪所有数据包的导入导出操作
    """

    __tablename__ = "import_export_history"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(
        Integer,
        ForeignKey("data_packages.id", ondelete="SET NULL"),
        nullable=True,
        comment="数据包ID",
    )
    operation_type = Column(String(20), nullable=False, comment="操作类型")
    # 审计追踪表：组织删除绝不能连带清空导入导出历史（原 CASCADE），
    # 否则"谁在什么时候导出了什么"的留痕随组织一起消失。改为 SET NULL + 可空，
    # 历史行保留，仅失去组织归类（深审 LIVE）。
    org_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作组织ID(组织删除后置空，审计留痕保留)",
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作用户ID(用户删除后置空，导入导出留痕保留)",
    )
    operation_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="操作时间",
    )
    result = Column(
        String(20),
        default=OperationResult.SUCCESS.value,
        nullable=False,
        comment="操作结果",
    )
    details_json = Column(Text, nullable=True, comment="操作详情JSON")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # Additional metadata
    file_name = Column(String(200), nullable=True, comment="文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    record_count = Column(Integer, nullable=True, comment="记录数")
    data_types = Column(Text, nullable=True, comment="数据类型(JSON数组)")
    duration_ms = Column(Integer, nullable=True, comment="操作耗时(毫秒)")
    ip_address = Column(String(50), nullable=True, comment="操作IP地址")
    user_agent = Column(String(500), nullable=True, comment="用户代理")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    # Relationships
    package = relationship("DataPackage", backref="history")
    organization = relationship("Organization", backref="import_export_history")
    user = relationship("User", backref="import_export_operations")

    __table_args__ = (
        Index("ix_import_export_history_package_id", "package_id"),
        Index("ix_import_export_history_org_id", "org_id"),
        Index("ix_import_export_history_user_id", "user_id"),
        Index("ix_import_export_history_operation_type", "operation_type"),
        Index("ix_import_export_history_operation_time", "operation_time"),
        Index("ix_import_export_history_result", "result"),
    )

    def __repr__(self):
        return f"<ImportExportHistory(id={self.id}, type='{self.operation_type}', result='{self.result}')>"

    @property
    def is_success(self) -> bool:
        """Check if operation was successful"""
        return self.result == OperationResult.SUCCESS.value

    @property
    def is_failed(self) -> bool:
        """Check if operation failed"""
        return self.result == OperationResult.FAILED.value
