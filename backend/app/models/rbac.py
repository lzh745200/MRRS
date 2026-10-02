"""
RBAC 权限模型

统一的角色-权限 ORM 模型，映射 rbac_* 系列表。
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, UtcDateTime

from .machine_code import MachineCode  # noqa: F401 - relationship 字符串引用注册


def _uuid() -> str:
    return str(uuid.uuid4())


class RbacRole(Base):
    """角色模型 — 映射 rbac_roles 表"""

    __tablename__ = "rbac_roles"
    __table_args__ = (
        Index("ix_rbac_roles_name", "name", unique=True),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(50), unique=True, nullable=False, comment="角色名称")
    description = Column(Text, comment="角色描述")
    is_system = Column(Boolean, default=False, comment="是否系统内置角色")
    is_active = Column(Boolean, default=True, comment="是否启用")
    priority = Column(Integer, default=100, comment="优先级，数字越小优先级越高")
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

    # 关系
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RbacRole(id='{self.id}', name='{self.name}')>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_system": self.is_system,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserRole(Base):
    """用户角色关联模型"""

    __tablename__ = "rbac_user_roles"
    __table_args__ = (
        Index("ix_rbac_user_roles_user_role", "user_id", "role_id"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(String(36), ForeignKey("rbac_roles.id", ondelete="CASCADE"), nullable=False)
    granted_by = Column(Integer, comment="授权人ID")
    expires_at = Column(UtcDateTime(), comment="过期时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关系
    role = relationship("RbacRole", back_populates="users")

    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id='{self.role_id}')>"


class RolePermission(Base):
    """角色权限关联模型"""

    __tablename__ = "rbac_role_permissions"
    __table_args__ = (
        Index("ix_rbac_rp_role_perm", "role_id", "permission"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    role_id = Column(String(36), ForeignKey("rbac_roles.id", ondelete="CASCADE"), nullable=False)
    permission = Column(String(50), nullable=False, comment="权限标识")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关系
    role = relationship("RbacRole", back_populates="role_permissions")

    def __repr__(self):
        return f"<RolePermission(role_id='{self.role_id}', permission='{self.permission}')>"


class UserPermission(Base):
    """用户直接权限模型"""

    __tablename__ = "rbac_user_permissions"
    __table_args__ = (
        Index("ix_rbac_up_user_perm", "user_id", "permission"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission = Column(String(50), nullable=False, comment="权限标识")
    granted_by = Column(Integer, comment="授权人ID")
    expires_at = Column(UtcDateTime(), comment="过期时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<UserPermission(user_id={self.user_id}, permission='{self.permission}')>"


class ResourceAccessControl(Base):
    """资源访问控制模型"""

    __tablename__ = "rbac_resource_access"
    __table_args__ = (
        Index("ix_rbac_ra_user_resource", "user_id", "resource_type", "resource_id"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resource_type = Column(String(50), nullable=False, comment="资源类型")
    resource_id = Column(String(36), nullable=False, comment="资源ID")
    access_level = Column(String(20), default="read", comment="访问级别: read, write, delete")
    granted_by = Column(Integer, comment="授权人ID")
    expires_at = Column(UtcDateTime(), comment="过期时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<ResourceAccessControl(user_id={self.user_id}, resource='{self.resource_type}:{self.resource_id}')>"


class AccessLog(Base):
    """RBAC 访问日志"""

    __tablename__ = "rbac_access_logs"
    __table_args__ = (
        Index("ix_rbac_al_user_action", "user_id", "action"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), nullable=False, comment="用户ID")
    action = Column(String(50), nullable=False, comment="操作动作")
    resource_type = Column(String(50), nullable=False, comment="资源类型")
    resource_id = Column(String(36), nullable=False, comment="资源ID")
    access_granted = Column(Boolean, nullable=False, comment="是否授权")
    reason = Column(String(200), comment="拒绝原因")
    ip_address = Column(String(50), comment="IP地址")
    user_agent = Column(Text, comment="用户代理")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<AccessLog(user_id='{self.user_id}', action='{self.action}', granted={self.access_granted})>"


class MachineCodePermission(Base):
    """机器码功能权限关联模型

    用于管理基于机器码的功能权限分配。
    管理员可以为每个机器码绑定特定的功能权限限制。
    """

    __tablename__ = "machine_code_permissions"
    __table_args__ = (
        Index("ix_mcp_machine_permission", "machine_code_id", "permission", unique=True),
        Index("ix_mcp_machine_code_id", "machine_code_id"),
        {"extend_existing": True},
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    machine_code_id = Column(
        Integer,
        ForeignKey("machine_codes.id", ondelete="CASCADE"),
        nullable=False,
        comment="机器码ID",
    )
    permission = Column(String(100), nullable=False, comment="权限标识符")
    granted_by = Column(Integer, comment="授权人ID")
    expires_at = Column(UtcDateTime(), comment="过期时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(
        UtcDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关系
    machine_code = relationship("MachineCode", lazy="select")

    def __repr__(self):
        return f"<MachineCodePermission(machine_code_id={self.machine_code_id}, permission='{self.permission}')>"


# 向后兼容别名
Role = RbacRole
BasicRole = RbacRole
