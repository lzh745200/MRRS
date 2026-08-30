# -*- coding: utf-8 -*-
"""
用户权限管理服务
提供完整的用户权限管理功能，包括组织关联、角色分配、权限验证等
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from datetime import timezone, datetime

from app.models.user import User
from app.models.organization import Organization
from app.models.user_organization import UserOrganization
from app.models.rbac import RbacRole, UserRole, RolePermission, UserPermission
from app.core.error_handler import BusinessLogicError
from app.core.permission_utils import is_admin, is_superuser
from app.core.transaction import safe_commit


class UserPermissionService:
    """用户权限管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def _get_user(self, user_id: int) -> Optional[User]:
        """
        获取用户对象（内部方法，避免重复查询）

        Args:
            user_id: 用户ID

        Returns:
            用户对象或None
        """
        return self.db.query(User).filter(User.id == user_id).first()

    # ==================== 用户-组织管理 ====================

    def assign_user_to_organization(
        self,
        user_id: int,
        organization_id: int,
        role: str = "member",
        is_primary: bool = False,
    ) -> UserOrganization:
        """
        将用户分配到组织

        Args:
            user_id: 用户ID
            organization_id: 组织ID
            role: 在组织中的角色（admin, member, viewer）
            is_primary: 是否为主组织
        """
        # 验证用户和组织是否存在
        user = self._get_user(user_id)
        if not user:
            raise BusinessLogicError("用户不存在")

        org = self.db.query(Organization).filter(Organization.id == organization_id).first()
        if not org:
            raise BusinessLogicError("组织不存在")

        # 检查是否已存在关联
        existing = (
            self.db.query(UserOrganization)
            .filter(
                and_(
                    UserOrganization.user_id == user_id,
                    UserOrganization.organization_id == organization_id,
                )
            )
            .first()
        )

        if existing:
            # 更新现有关联
            existing.role = role
            existing.updated_at = datetime.now(timezone.utc)
            safe_commit(self.db)
            self.db.refresh(existing)
            return existing

        # 创建新关联
        user_org = UserOrganization(user_id=user_id, organization_id=organization_id, role=role)
        self.db.add(user_org)

        # 如果是主组织，更新用户的 organization_id
        if is_primary:
            user.organization_id = organization_id

        safe_commit(self.db)
        self.db.refresh(user_org)
        return user_org

    def remove_user_from_organization(self, user_id: int, organization_id: int) -> bool:
        """
        将用户从组织中移除

        Args:
            user_id: 用户ID
            organization_id: 组织ID
        """
        user_org = (
            self.db.query(UserOrganization)
            .filter(
                and_(
                    UserOrganization.user_id == user_id,
                    UserOrganization.organization_id == organization_id,
                )
            )
            .first()
        )

        if not user_org:
            return False

        self.db.delete(user_org)

        # 如果是主组织，清除用户的 organization_id
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.organization_id == organization_id:
            user.organization_id = None

        safe_commit(self.db)
        return True

    def get_user_organizations(self, user_id: int) -> List[Dict[str, Any]]:
        """
        获取用户所属的所有组织

        Args:
            user_id: 用户ID
        """
        # 一次性查询用户对象，避免在循环中重复查询
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # 使用 join 一次性获取所有数据，避免 N+1 查询
        user_orgs = (
            self.db.query(UserOrganization, Organization)
            .join(Organization, UserOrganization.organization_id == Organization.id)
            .filter(UserOrganization.user_id == user_id)
            .all()
        )

        result = []
        for user_org, org in user_orgs:
            result.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "code": org.code,
                    "role": user_org.role,
                    "is_primary": org.id == user.organization_id,
                }
            )

        return result

    def get_organization_users(self, organization_id: int, include_children: bool = False) -> List[Dict[str, Any]]:
        """
        获取组织下的所有用户

        Args:
            organization_id: 组织ID
            include_children: 是否包含下级组织的用户
        """
        if include_children:
            # 获取所有下级组织ID
            org_ids = self._get_child_organization_ids(organization_id)
            org_ids.append(organization_id)

            # 使用 join 一次性获取所有数据，避免 N+1 查询
            user_orgs = (
                self.db.query(UserOrganization, User)
                .join(User, UserOrganization.user_id == User.id)
                .filter(UserOrganization.organization_id.in_(org_ids))
                .all()
            )
        else:
            # 使用 join 一次性获取所有数据，避免 N+1 查询
            user_orgs = (
                self.db.query(UserOrganization, User)
                .join(User, UserOrganization.user_id == User.id)
                .filter(UserOrganization.organization_id == organization_id)
                .all()
            )

        result = []
        for user_org, user in user_orgs:
            if user:
                result.append(
                    {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.full_name,
                        "email": user.email,
                        "role": user.role,
                        "org_role": user_org.role,
                        "is_active": user.is_active,
                    }
                )

        return result

    def _get_child_organization_ids(self, parent_id: int) -> List[int]:
        """递归获取所有下级组织ID"""
        children = self.db.query(Organization).filter(Organization.parent_id == parent_id).all()

        result = []
        for child in children:
            result.append(child.id)
            result.extend(self._get_child_organization_ids(child.id))

        return result

    # ==================== 角色管理 ====================

    def assign_role_to_user(
        self,
        user_id: int,
        role_id: str,
        granted_by: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> UserRole:
        """
        为用户分配角色

        Args:
            user_id: 用户ID
            role_id: 角色ID
            granted_by: 授权人ID
            expires_at: 过期时间
        """
        # 验证用户和角色是否存在
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessLogicError("用户不存在")

        role = self.db.query(RbacRole).filter(RbacRole.id == role_id).first()
        if not role:
            raise BusinessLogicError("角色不存在")

        # 检查是否已存在
        existing = (
            self.db.query(UserRole).filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id)).first()
        )

        if existing:
            # 更新现有关联
            existing.granted_by = granted_by
            existing.expires_at = expires_at
            existing.updated_at = datetime.now(timezone.utc)
            safe_commit(self.db)
            self.db.refresh(existing)
            return existing

        # 创建新关联
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            granted_by=granted_by,
            expires_at=expires_at,
        )
        self.db.add(user_role)
        safe_commit(self.db)
        self.db.refresh(user_role)
        return user_role

    def remove_role_from_user(self, user_id: int, role_id: str) -> bool:
        """
        移除用户的角色

        Args:
            user_id: 用户ID
            role_id: 角色ID
        """
        user_role = (
            self.db.query(UserRole).filter(and_(UserRole.user_id == user_id, UserRole.role_id == role_id)).first()
        )

        if not user_role:
            return False

        self.db.delete(user_role)
        safe_commit(self.db)
        return True

    def get_user_roles(self, user_id: int) -> List[Dict[str, Any]]:
        """
        获取用户的所有角色

        Args:
            user_id: 用户ID
        """
        user_roles = (
            self.db.query(UserRole).options(joinedload(UserRole.role)).filter(UserRole.user_id == user_id).all()
        )

        result = []
        for user_role in user_roles:
            if user_role.role:
                result.append(
                    {
                        "id": user_role.role.id,
                        "name": user_role.role.name,
                        "description": user_role.role.description,
                        "is_system": user_role.role.is_system,
                        "granted_by": user_role.granted_by,
                        "expires_at": (user_role.expires_at.isoformat() if user_role.expires_at else None),
                    }
                )

        return result

    # ==================== 权限管理 ====================

    def grant_permission_to_user(
        self,
        user_id: int,
        permission: str,
        granted_by: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> UserPermission:
        """
        直接授予用户权限

        Args:
            user_id: 用户ID
            permission: 权限标识
            granted_by: 授权人ID
            expires_at: 过期时间
        """
        # 验证用户是否存在
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessLogicError("用户不存在")

        # 检查是否已存在
        existing = (
            self.db.query(UserPermission)
            .filter(
                and_(
                    UserPermission.user_id == user_id,
                    UserPermission.permission == permission,
                )
            )
            .first()
        )

        if existing:
            # 更新现有权限
            existing.granted_by = granted_by
            existing.expires_at = expires_at
            existing.updated_at = datetime.now(timezone.utc)
            safe_commit(self.db)
            self.db.refresh(existing)
            return existing

        # 创建新权限
        user_perm = UserPermission(
            user_id=user_id,
            permission=permission,
            granted_by=granted_by,
            expires_at=expires_at,
        )
        self.db.add(user_perm)
        safe_commit(self.db)
        self.db.refresh(user_perm)
        return user_perm

    def revoke_permission_from_user(self, user_id: int, permission: str) -> bool:
        """
        撤销用户的权限

        Args:
            user_id: 用户ID
            permission: 权限标识
        """
        user_perm = (
            self.db.query(UserPermission)
            .filter(
                and_(
                    UserPermission.user_id == user_id,
                    UserPermission.permission == permission,
                )
            )
            .first()
        )

        if not user_perm:
            return False

        self.db.delete(user_perm)
        safe_commit(self.db)
        return True

    def get_user_permissions(self, user_id: int) -> List[str]:
        """
        获取用户的所有权限（包括角色权限和直接权限）

        Args:
            user_id: 用户ID
        """
        permissions = set()

        # 1. 获取用户的直接权限
        user_perms = self.db.query(UserPermission).filter(UserPermission.user_id == user_id).all()

        for perm in user_perms:
            # 检查是否过期
            if not perm.expires_at or perm.expires_at > datetime.now(timezone.utc):
                permissions.add(perm.permission)

        # 2. 获取用户角色的权限
        user_roles = self.db.query(UserRole).filter(UserRole.user_id == user_id).all()

        for user_role in user_roles:
            # 检查角色是否过期
            if user_role.expires_at and user_role.expires_at <= datetime.now(timezone.utc):
                continue

            # 获取角色的权限
            role_perms = self.db.query(RolePermission).filter(RolePermission.role_id == user_role.role_id).all()

            for role_perm in role_perms:
                permissions.add(role_perm.permission)

        return list(permissions)

    def check_user_permission(self, user_id: int, permission: str) -> bool:
        """
        检查用户是否拥有指定权限

        Args:
            user_id: 用户ID
            permission: 权限标识
        """
        user_permissions = self.get_user_permissions(user_id)
        return permission in user_permissions

    def check_user_data_scope(self, user_id: int, target_org_id: Optional[int] = None) -> bool:
        """
        检查用户的数据范围权限

        Args:
            user_id: 用户ID
            target_org_id: 目标组织ID
        """
        user = self._get_user(user_id)
        if not user:
            return False

        # 超级管理员拥有所有权限
        if is_superuser(user):
            return True

        # 未绑定组织的管理员不受组织限制（ADR-0002，单机模式）
        if is_admin(user) and user.organization_id is None:
            return True

        # 如果没有指定目标组织，检查用户是否有组织
        if target_org_id is None:
            return user.organization_id is not None

        # 根据数据范围检查
        if user.data_scope == "all":
            # 所有数据
            return True
        elif user.data_scope == "org":
            # 本组织
            return user.organization_id == target_org_id
        elif user.data_scope == "org_children":
            # 本组织及下级
            if user.organization_id == target_org_id:
                return True
            # 检查是否为下级组织
            child_ids = self._get_child_organization_ids(user.organization_id)
            return target_org_id in child_ids
        elif user.data_scope == "self":
            # 仅自己
            return False

        return False

    # ==================== 组织树管理 ====================

    def get_organization_tree(
        self, parent_id: Optional[int] = None, user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取组织树

        Args:
            parent_id: 父组织ID（None表示根节点）
            user_id: 用户ID（用于权限过滤）
        """
        # 如果指定了用户，检查数据范围
        if user_id:
            user = self._get_user(user_id)
            if not user:
                return []

            # 超级管理员/管理员（未绑定组织时）可以看到所有组织（ADR-0002）
            if not is_superuser(user) and not (is_admin(user) and user.organization_id is None):
                # 根据数据范围过滤
                if user.data_scope == "org":
                    # 只能看到自己的组织
                    if parent_id and parent_id != user.organization_id:
                        return []
                elif user.data_scope == "org_children":
                    # 可以看到自己的组织及下级
                    if parent_id:
                        allowed_ids = [user.organization_id] + self._get_child_organization_ids(user.organization_id)
                        if parent_id not in allowed_ids:
                            return []
                elif user.data_scope == "self":
                    # 不能看到组织树
                    return []

        # 查询组织
        query = self.db.query(Organization).filter(Organization.is_active == True)  # noqa: E712

        if parent_id is None:
            query = query.filter(Organization.parent_id.is_(None))
        else:
            query = query.filter(Organization.parent_id == parent_id)

        orgs = query.order_by(Organization.sort_order, Organization.id).all()

        result = []
        for org in orgs:
            # 递归获取子组织
            children = self.get_organization_tree(org.id, user_id)

            result.append(
                {
                    "id": str(org.id),  # 字符串 ID — 防止 el-tree DOM 异常
                    "name": org.name,
                    "code": org.code,
                    "parent_id": str(org.parent_id) if org.parent_id is not None else None,
                    "level": org.level,
                    "type": org.type,
                    "org_type": org.org_type,
                    "sort_order": org.sort_order,
                    "description": org.description,
                    "contact_person": org.contact_person,
                    "contact_phone": org.contact_phone,
                    "is_active": org.is_active,
                    "children": children,
                    "has_children": len(children) > 0,
                }
            )

        return result

    def get_user_accessible_organizations(self, user_id: int) -> List[int]:
        """
        获取用户可访问的所有组织ID列表

        Args:
            user_id: 用户ID
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # 超级管理员/管理员（未绑定组织时）可以访问所有组织（ADR-0002）
        if is_superuser(user) or (is_admin(user) and user.organization_id is None):
            all_orgs = self.db.query(Organization.id).filter(Organization.is_active == True).all()  # noqa: E712
            return [org.id for org in all_orgs]

        # 根据数据范围返回可访问的组织
        if user.data_scope == "all":
            all_orgs = self.db.query(Organization.id).filter(Organization.is_active == True).all()  # noqa: E712
            return [org.id for org in all_orgs]
        elif user.data_scope == "org":
            return [user.organization_id] if user.organization_id else []
        elif user.data_scope == "org_children":
            if not user.organization_id:
                return []
            child_ids = self._get_child_organization_ids(user.organization_id)
            return [user.organization_id] + child_ids
        elif user.data_scope == "self":
            return []

        return []
