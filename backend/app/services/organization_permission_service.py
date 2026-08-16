"""
Organization Permission Service
组织级权限服务
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Set

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessError
from app.core.permission_utils import is_superuser
from app.models.organization import Organization
from app.models.user import User
from app.services.organization_service import OrganizationService

logger = logging.getLogger(__name__)


class PermissionDeniedError(BusinessError):
    """权限拒绝错误"""

    def __init__(self, user_id: int, org_id: int, action: str = "access"):
        super().__init__(f"用户 {user_id} 无权{action}组织 {org_id} 的数据")
        self.user_id = user_id
        self.org_id = org_id
        self.action = action


@dataclass
class AccessAttemptLog:
    """访问尝试日志记录"""

    user_id: int
    org_id: int
    action: str
    allowed: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
    details: Optional[str] = None


class OrganizationPermissionService:
    """
    组织级权限服务
    负责基于组织层级的访问控制
    """

    def __init__(self, db: Session):
        self.db = db
        self.org_service = OrganizationService(db)
        self._access_logs: List[AccessAttemptLog] = []

    def _get_user(self, user_id: int) -> Optional[User]:
        """
        获取用户对象（内部方法，用于避免重复查询）

        Args:
            user_id: 用户ID

        Returns:
            用户对象或None
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_organization_id(self, user_id: int = None, user: User = None) -> Optional[int]:
        """
        获取用户所属组织ID

        Args:
            user_id: 用户ID（如果user参数为None则必须提供）
            user: 用户对象（可选，避免重复查询）

        Returns:
            组织ID或None
        """
        if user is None:
            if user_id is None:
                return None
            user = self._get_user(user_id)
            if not user:
                return None

        # 假设User模型有organization_id字段
        # 如果没有，返回None表示超级管理员或未分配组织
        return getattr(user, "organization_id", None)

    def get_accessible_organizations(self, user_id: int, include_inactive: bool = False) -> List[int]:
        """
        获取用户可访问的组织ID列表

        规则:
        - 用户可以访问自己所属的组织
        - 用户可以访问所有下级组织
        - 超级管理员可以访问所有组织
        - 未绑定组织的普通用户无法访问任何组织

        Args:
            user_id: 用户ID
            include_inactive: 是否包含停用的组织

        Returns:
            可访问的组织ID列表
        """
        user = self._get_user(user_id)
        if not user:
            return []

        user_org_id = self.get_user_organization_id(user=user)

        if user_org_id is None:
            # 未绑定组织的普通用户无法访问任何组织
            if not is_superuser(user):
                return []

            # 超级管理员可以访问所有组织
            query = self.db.query(Organization.id)
            if not include_inactive:
                query = query.filter(Organization.is_active == True)  # noqa: E712
            return [org_id for (org_id,) in query.all()]

        # 获取本级及所有下级组织
        return self.org_service.get_subordinate_ids(user_org_id, include_self=True)

    def get_accessible_organization_set(self, user_id: int, include_inactive: bool = False) -> Set[int]:
        """
        获取用户可访问的组织ID集合（用于快速查找）

        Args:
            user_id: 用户ID
            include_inactive: 是否包含停用的组织

        Returns:
            可访问的组织ID集合
        """
        return set(self.get_accessible_organizations(user_id, include_inactive))

    def can_access_organization(
        self,
        user_id: int,
        org_id: int,
        log_attempt: bool = True,
        ip_address: str = None,
    ) -> bool:
        """
        检查用户是否可访问指定组织

        Args:
            user_id: 用户ID
            org_id: 目标组织ID
            log_attempt: 是否记录访问尝试
            ip_address: 访问IP地址

        Returns:
            True表示可以访问，False表示不可以
        """
        accessible_orgs = self.get_accessible_organization_set(user_id)
        allowed = org_id in accessible_orgs

        if log_attempt:
            self._log_access_attempt(
                user_id=user_id,
                org_id=org_id,
                action="access",
                allowed=allowed,
                ip_address=ip_address,
            )

        return allowed

    def require_organization_access(
        self, user_id: int, org_id: int, action: str = "access", ip_address: str = None
    ) -> None:
        """
        要求用户具有组织访问权限，否则抛出异常

        Args:
            user_id: 用户ID
            org_id: 目标组织ID
            action: 操作类型
            ip_address: 访问IP地址

        Raises:
            PermissionDeniedError: 无权访问
        """
        if not self.can_access_organization(user_id, org_id, ip_address=ip_address):
            self._log_access_attempt(
                user_id=user_id,
                org_id=org_id,
                action=action,
                allowed=False,
                ip_address=ip_address,
                details="Access denied - permission check failed",
            )
            raise PermissionDeniedError(user_id, org_id, action)

    def can_manage_organization(self, user_id: int = None, user: User = None, org_id: int = None) -> bool:
        """
        检查用户是否可以管理指定组织（创建、编辑、删除）

        管理权限规则:
        - 超级管理员可以管理所有组织
        - 用户只能管理自己所属组织的下级组织
        - 不能管理自己所属的组织本身（需要上级权限）
        - 未绑定组织的普通用户无法管理任何组织

        Args:
            user_id: 用户ID（如果user参数为None则必须提供）
            user: 用户对象（可选，避免重复查询）
            org_id: 目标组织ID

        Returns:
            True表示可以管理
        """
        if user is None:
            if user_id is None:
                return False
            user = self._get_user(user_id)
            if not user:
                return False

        # 超级管理员可以管理所有组织
        if is_superuser(user):
            return True

        user_org_id = self.get_user_organization_id(user=user)

        if user_org_id is None:
            # 未绑定组织的普通用户无法管理任何组织
            return False

        if user_org_id == org_id:
            # 不能管理自己所属的组织
            return False

        # 检查目标组织是否是用户组织的下级
        subordinate_ids = self.org_service.get_subordinate_ids(user_org_id, include_self=False)
        return org_id in subordinate_ids

    def can_create_subordinate(self, user_id: int = None, user: User = None, parent_org_id: int = None) -> bool:
        """
        检查用户是否可以在指定组织下创建子组织

        Args:
            user_id: 用户ID（如果user参数为None则必须提供）
            user: 用户对象（可选，避免重复查询）
            parent_org_id: 父组织ID

        Returns:
            True表示可以创建
        """
        if user is None:
            if user_id is None:
                return False
            user = self._get_user(user_id)
            if not user:
                return False

        # 超级管理员可以在任何组织下创建
        if is_superuser(user):
            return True

        user_org_id = self.get_user_organization_id(user=user)

        if user_org_id is None:
            # 未绑定组织的普通用户无法创建组织
            return False

        # 用户可以在自己组织或下级组织下创建子组织
        accessible_orgs = self.get_accessible_organization_set(user_id or user.id)
        return parent_org_id in accessible_orgs

    def get_data_scope_filter(self, user_id: int, org_id_column: Any) -> Any:
        """
        获取数据范围过滤条件

        用于在查询中添加组织范围限制

        Args:
            user_id: 用户ID
            org_id_column: 组织ID列（SQLAlchemy Column）

        Returns:
            SQLAlchemy过滤条件
        """
        accessible_orgs = self.get_accessible_organizations(user_id)

        if not accessible_orgs:
            # 没有可访问的组织，返回永假条件
            return org_id_column == -1

        return org_id_column.in_(accessible_orgs)

    def filter_organizations_by_access(self, user_id: int, org_ids: List[int]) -> List[int]:
        """
        过滤出用户可访问的组织ID

        Args:
            user_id: 用户ID
            org_ids: 待过滤的组织ID列表

        Returns:
            用户可访问的组织ID列表
        """
        accessible_orgs = self.get_accessible_organization_set(user_id)
        return [org_id for org_id in org_ids if org_id in accessible_orgs]

    def get_superior_organizations(self, user_id: int) -> List[int]:
        """
        获取用户的上级组织ID列表

        Args:
            user_id: 用户ID

        Returns:
            上级组织ID列表
        """
        user_org_id = self.get_user_organization_id(user_id)

        if user_org_id is None:
            return []

        ancestors = self.org_service.get_ancestors(user_org_id)
        return [org.id for org in ancestors]

    def is_superior_of(self, user_id: int = None, user: User = None, target_org_id: int = None) -> bool:
        """
        检查用户是否是目标组织的上级

        Args:
            user_id: 用户ID（如果user参数为None则必须提供）
            user: 用户对象（可选，避免重复查询）
            target_org_id: 目标组织ID

        Returns:
            True表示用户是目标组织的上级
        """
        if user is None:
            if user_id is None:
                return False
            user = self._get_user(user_id)
            if not user:
                return False

        # 超级管理员是所有组织的上级
        if is_superuser(user):
            return True

        user_org_id = self.get_user_organization_id(user=user)

        if user_org_id is None:
            # 未绑定组织的普通用户不是任何组织的上级
            return False

        # 获取目标组织的所有上级
        target_org = self.org_service.get_organization(target_org_id)
        if not target_org:
            return False

        ancestors = self.org_service.get_ancestors(target_org_id)
        ancestor_ids = [org.id for org in ancestors]

        return user_org_id in ancestor_ids

    def is_subordinate_of(self, user_id: int, target_org_id: int) -> bool:
        """
        检查用户是否是目标组织的下级

        Args:
            user_id: 用户ID
            target_org_id: 目标组织ID

        Returns:
            True表示用户是目标组织的下级
        """
        user_org_id = self.get_user_organization_id(user_id)

        if user_org_id is None:
            return False

        # 获取目标组织的所有下级
        subordinate_ids = self.org_service.get_subordinate_ids(target_org_id, include_self=False)

        return user_org_id in subordinate_ids

    def _log_access_attempt(
        self,
        user_id: int,
        org_id: int,
        action: str,
        allowed: bool,
        ip_address: str = None,
        details: str = None,
    ) -> None:
        """记录访问尝试"""
        log_entry = AccessAttemptLog(
            user_id=user_id,
            org_id=org_id,
            action=action,
            allowed=allowed,
            ip_address=ip_address,
            details=details,
        )
        self._access_logs.append(log_entry)

        # 记录到日志
        if allowed:
            logger.debug(f"Access granted: user={user_id}, org={org_id}, action={action}")
        else:
            logger.warning(
                f"Access denied: user={user_id}, org={org_id}, action={action}, " f"ip={ip_address}, details={details}"
            )

    def get_access_logs(
        self,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        allowed: Optional[bool] = None,
    ) -> List[AccessAttemptLog]:
        """
        获取访问日志

        Args:
            user_id: 按用户ID过滤
            org_id: 按组织ID过滤
            allowed: 按是否允许过滤

        Returns:
            访问日志列表
        """
        logs = self._access_logs

        if user_id is not None:
            logs = [log for log in logs if log.user_id == user_id]

        if org_id is not None:
            logs = [log for log in logs if log.org_id == org_id]

        if allowed is not None:
            logs = [log for log in logs if log.allowed == allowed]

        return logs

    def get_denied_access_logs(self) -> List[AccessAttemptLog]:
        """获取所有被拒绝的访问日志"""
        return self.get_access_logs(allowed=False)
