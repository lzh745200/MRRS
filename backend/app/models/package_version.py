"""
数据包版本管理模型
"""

from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from app.models.base import Base, UtcDateTime

from .data_package import DataPackage  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册


class PackageVersion(Base):
    """数据包版本管理"""

    __tablename__ = "package_versions"

    __table_args__ = (
        # 同一数据包内版本号必须唯一：API 虽按 (package_id, version) 查重后返回 400，
        # 但缺数据库级约束，并发写入/直写可绕过（compare 端点按该组合取单行）。
        UniqueConstraint("package_id", "version", name="uq_package_version_package_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(
        Integer,
        ForeignKey("data_packages.id", ondelete="CASCADE"),
        nullable=False,
        comment="数据包ID",
    )
    version = Column(String(20), nullable=False, comment="版本号")
    changes = Column(Text, comment="变更记录（JSON格式）")
    description = Column(Text, comment="版本说明")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="创建时间")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )

    # 关系
    # package_id 非空且 ondelete=CASCADE：删父行必须交给数据库级联清理。
    # 缺 passive_deletes 时 ORM 会先把 package_id 置空（非空列）→ IntegrityError。
    package = relationship(
        "DataPackage",
        backref=backref("versions", cascade="all, delete-orphan", passive_deletes=True),
    )
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<PackageVersion(id={self.id}, package_id={self.package_id}, version='{self.version}')>"
