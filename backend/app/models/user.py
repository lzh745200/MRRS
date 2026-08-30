from datetime import datetime, timezone
from typing import Optional

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
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, EncryptedText
from app.models.two_factor_auth import TwoFactorAuth  # noqa: F401

from .organization import Organization  # noqa: F401 - relationship 字符串引用注册
from .permission_pack import PermissionPack  # noqa: F401 - FK 字符串引用注册（permission_packs.id）

"""用户模型"""


class User(Base):
    """用户表"""

    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_role_active", "role", "is_active"),
        Index("ix_users_department", "department"),
        Index("ix_users_organization_id", "organization_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="加密密码")
    full_name = Column(String(100), comment="姓名")
    role = Column(
        String(20),
        default="user",
        comment="角色: super_admin-超级管理员, admin-管理员, user-普通用户, viewer-访客",
    )
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_superuser = Column(Boolean, default=False, comment="是否超级管理员")
    phone = Column(EncryptedText(64), comment="联系电话(透明加密, ADR-0005)")
    department = Column(String(100), comment="部门")
    position = Column(String(100), comment="职位")
    avatar = Column(String(255), comment="头像")
    gender = Column(String(10), comment="性别: male-男, female-女")
    birthday = Column(String(20), comment="出生日期")
    address = Column(String(255), comment="联系地址")
    remark = Column(Text, comment="备注")
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )
    data_scope = Column(
        String(20),
        default="org",
        comment="数据范围: all-所有, org-本组织, org_children-本组织及下级, self-仅自己",
    )
    permissions = Column(Text, default="", comment="权限列表，逗号分隔")
    machine_binding_required = Column(Boolean, default=False, comment="是否强制机器码绑定")
    allowed_permissions = Column(Text, default="", comment="白名单权限(JSON数组)，为空则使用角色默认权限")
    allowed_menus = Column(Text, nullable=True, comment="用户可见菜单key列表(JSON数组)，NULL表示继承角色默认菜单，空数组[]表示无菜单")
    permission_pack_id = Column(
        Integer,
        ForeignKey("permission_packs.id", ondelete="SET NULL"),
        nullable=True,
        comment="绑定的权限包ID，NULL表示未绑定（菜单解析优先级：allowed_menus > 权限包 > 角色默认）",
    )
    token_version = Column(Integer, default=0, comment="Token版本号，递增后旧token全部失效")
    must_change_password = Column(Boolean, default=False, comment="是否必须修改密码")
    failed_login_count = Column(Integer, default=0, comment="连续登录失败次数")
    locked_until = Column(DateTime(timezone=True), nullable=True, comment="账户锁定截止时间")
    password_changed_at = Column(DateTime(timezone=True), nullable=True, comment="密码最后修改时间")
    last_login = Column(DateTime(timezone=True), comment="最后登录时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    # 关系
    projects = relationship("Project", back_populates="creator", foreign_keys="[Project.created_by]")
    organization = relationship("Organization", foreign_keys=[organization_id], lazy="select")
    two_factor_auth = relationship("TwoFactorAuth", back_populates="user", uselist=False)

    @property
    def org_id(self) -> Optional[int]:
        """兼容旧接口别名：数据上报/数据包接收等模块使用 org_id 读取所属组织"""
        return self.organization_id

    @property
    def permissions_list(self) -> list:
        """返回权限列表"""
        if not self.permissions:
            return []
        return [p.strip() for p in self.permissions.split(",") if p.strip()]

    @property
    def organization_name(self) -> str:
        """返回所属组织名称"""
        if self.organization:
            return self.organization.name
        return ""

    @property
    def allowed_permissions_list(self) -> list:
        """返回白名单权限列表（从JSON解析）"""
        if not self.allowed_permissions:
            return []
        try:
            import json

            return json.loads(self.allowed_permissions)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def allowed_menus_list(self) -> list | None:
        """返回用户可见菜单key列表（从JSON解析）

        Returns:
            - None: 继承角色默认菜单
            - []: 无菜单
            - [key1, key2, ...]: 自定义菜单配置
        """
        if not self.allowed_menus:
            return None  # 继承角色默认
        try:
            import json

            return json.loads(self.allowed_menus)
        except (json.JSONDecodeError, TypeError):
            return None

    @property
    def token_version_safe(self) -> int:
        return self.token_version or 0

    def revoke_all_tokens(self) -> None:
        """递增 token_version 使所有现有 JWT 立即失效，并记录密码修改时间。"""
        self.token_version = self.token_version_safe + 1
        self.password_changed_at = datetime.now(timezone.utc)

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role}', org_id={self.organization_id})>"
