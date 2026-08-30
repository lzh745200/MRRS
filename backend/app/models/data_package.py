"""
DataPackage Model
数据包模型 - 用于数据导入导出管理
"""

from enum import Enum

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base

from .organization import Organization  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册


class PackageType(str, Enum):
    """数据包类型枚举"""

    task = "task"  # 任务包（管理员分发）
    report = "report"  # 上报包（普通用户上报）
    update = "update"  # 增量更新包（基于基准包导出变更记录）


class PackageStatus(str, Enum):
    """数据包状态枚举"""

    draft = "draft"  # 草稿
    pending = "pending"  # 待处理
    validated = "validated"  # 已验证
    imported = "imported"  # 已导入
    failed = "failed"  # 失败
    cancelled = "cancelled"  # 已取消


class DataPackage(Base):
    """
    数据包模型

    用于管理数据导入导出的包信息，包括文件路径、状态、验证结果等。
    """

    __tablename__ = "data_packages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    package_code = Column(String(50), unique=True, nullable=False, comment="数据包编码")
    org_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        comment="组织ID",
    )
    file_path = Column(String(500), nullable=True, comment="文件路径")
    file_name = Column(String(255), nullable=True, comment="文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    status = Column(
        SQLEnum(PackageStatus, native_enum=False),
        default=PackageStatus.draft,
        nullable=False,
        comment="状态",
    )
    type = Column(String(20), default="report", nullable=False, comment="数据包类型: task/report")
    version = Column(String(20), default="1.0", nullable=False, comment="数据包版本")
    data_types = Column(JSON, nullable=True, comment="包含的数据类型")
    record_count = Column(Integer, default=0, comment="记录总数")
    manifest = Column(JSON, nullable=True, comment="清单信息")
    checksum = Column(String(64), nullable=True, comment="校验和(SHA256)")
    error_message = Column(Text, nullable=True, comment="错误信息")
    description = Column(Text, nullable=True, comment="描述")

    # 加密信息
    is_encrypted = Column(Boolean, default=False, nullable=True, comment="是否加密")
    encryption_algorithm = Column(String(50), nullable=True, comment="加密算法")
    encryption_salt = Column(String(128), nullable=True, comment="密钥派生盐值(hex)")
    encryption_iterations = Column(Integer, nullable=True, comment="PBKDF2迭代次数")

    # 创建信息
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )

    # 导入信息
    imported_at = Column(DateTime(timezone=True), nullable=True, comment="导入时间")
    imported_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="导入人ID",
    )

    # 更新信息
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    # Relationships
    organization = relationship("Organization", backref="data_packages")
    creator = relationship("User", foreign_keys=[created_by], backref="created_packages")
    importer = relationship("User", foreign_keys=[imported_by], backref="imported_packages")

    __table_args__ = (
        Index("ix_data_packages_org_id", "org_id"),
        Index("ix_data_packages_status", "status"),
        Index("ix_data_packages_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<DataPackage(id={self.id}, code='{self.package_code}', status='{self.status}')>"

    @property
    def is_importable(self) -> bool:
        """是否可以导入"""
        return self.status == PackageStatus.validated

    @property
    def is_editable(self) -> bool:
        """是否可以编辑"""
        return self.status in (PackageStatus.draft, PackageStatus.pending)
