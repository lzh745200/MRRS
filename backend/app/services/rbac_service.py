"""
RBAC权限管理服务

所有 ORM 模型已迁移到 models/rbac.py，本文件只包含业务逻辑。
"""

import logging
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.error_handler import NotFoundError
from app.models.base import _utcnow
from app.models.rbac import (
    AccessLog,
    RbacRole,
    ResourceAccessControl,
    RolePermission,
    UserPermission,
    UserRole,
)
from app.models.user import User
from app.services.machine_code_permission_service import MachineCodePermissionService

logger = logging.getLogger(__name__)


def _safe_parse_expires(expires_at):
    """安全解析 ISO 日期时间字符串——无效/缺失输入返回 None。

    MagicMock 或无效类型传入时不会崩溃，测试兼容性好。
    """
    if not isinstance(expires_at, str):
        return None
    try:
        return datetime.fromisoformat(expires_at)
    except (ValueError, TypeError):
        return None


# 请求级权限缓存（避免单次请求中重复查询）
_restricted_perms_cache: ContextVar[Optional[Dict[int, Set[str]]]] = ContextVar("restricted_perms_cache", default=None)


def _required_resource_access_level(permission: str) -> str:
    """把权限标识符映射为资源级授权（rbac_resource_access.access_level）所需级别。

    取值域为 read / write / delete（models/rbac.py:176）：

    - read 类动作只要求 read 级授权。历史实现恒按字面 "write" 判定 →
      只读资源授权**永远无法**满足检查（授权形同不存在）。
    - delete 类动作要求 delete 级授权。历史实现按 "write" 判定 →
      仅授予 write 的资源授权可以满足同资源的 delete 检查（越权放行）。
    - 其余写类动作（write/export/publish/create/restore/download/...）按 write 判定，
      与历史行为一致，不放宽。
    """
    action = (permission or "").rsplit(":", 1)[-1].strip().lower()
    if action == "read":
        return "read"
    if action == "delete":
        return "delete"
    return "write"


# ==================== 权限枚举 ====================


class Permission(str, Enum):
    """权限枚举"""

    # 用户管理
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_MANAGE_ROLES = "user:manage_roles"

    # 组织管理
    ORG_READ = "org:read"
    ORG_WRITE = "org:write"
    ORG_DELETE = "org:delete"

    # 帮扶村管理
    VILLAGE_READ = "village:read"
    VILLAGE_WRITE = "village:write"
    VILLAGE_DELETE = "village:delete"
    VILLAGE_EXPORT = "village:export"

    # 政策管理
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_DELETE = "policy:delete"
    POLICY_PUBLISH = "policy:publish"

    # 备份管理
    BACKUP_CREATE = "backup:create"
    BACKUP_RESTORE = "backup:restore"
    BACKUP_DELETE = "backup:delete"
    BACKUP_DOWNLOAD = "backup:download"

    # 系统管理
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_LOGS = "system:logs"

    # 审计管理
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # 数据分析
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # 管理员权限
    ADMIN_ALL = "admin:all"


# ==================== 权限服务 ====================


class RBACService:
    """RBAC权限服务（全部使用 ORM 操作）"""

    def __init__(self):
        self.default_permissions = {
            Permission.USER_READ,
            Permission.ORG_READ,
            Permission.VILLAGE_READ,
            Permission.POLICY_READ,
            Permission.BACKUP_CREATE,
            Permission.ANALYTICS_READ,
        }

        self.role_permissions_map = {
            "admin": [Permission.ADMIN_ALL],
            "user": [
                Permission.USER_READ,
                Permission.ORG_READ,
                Permission.VILLAGE_READ,
                Permission.POLICY_READ,
                Permission.BACKUP_CREATE,
                Permission.ANALYTICS_READ,
            ],
        }

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def check_permission(
        self,
        user_id: str,
        permission: str,
        resource_type: str = None,
        resource_id: str = None,
        db: Session = None,
    ) -> bool:
        """检查用户权限"""
        if db is None:
            return False

        # 检查机器码权限限制（带缓存）
        restricted_perms = self._get_cached_restricted_permissions(int(user_id), db)
        if permission in restricted_perms:
            self._log_access(
                db,
                user_id,
                "permission_check",
                resource_type,
                resource_id,
                False,
                "机器码限制权限",
            )
            return False

        # 管理员权限检查
        if self._has_admin_role(user_id, db):
            self._log_access(
                db,
                user_id,
                "permission_check",
                resource_type,
                resource_id,
                True,
                "管理员权限",
            )
            return True

        # 检查直接权限
        if self._has_direct_permission(user_id, permission, db):
            self._log_access(
                db,
                user_id,
                "permission_check",
                resource_type,
                resource_id,
                True,
                "直接权限",
            )
            return True

        # 检查角色权限
        if self._has_role_permission(user_id, permission, db):
            self._log_access(
                db,
                user_id,
                "permission_check",
                resource_type,
                resource_id,
                True,
                "角色权限",
            )
            return True

        # 检查资源权限（所需级别由请求的 permission 派生，见
        # _required_resource_access_level：历史实现恒传 "write"）
        if resource_type and resource_id:
            required_level = _required_resource_access_level(permission)
            if self._has_resource_access(user_id, resource_type, resource_id, required_level, db):
                self._log_access(
                    db,
                    user_id,
                    "permission_check",
                    resource_type,
                    resource_id,
                    True,
                    "资源权限",
                )
                return True

        # 权限不足
        self._log_access(
            db,
            user_id,
            "permission_check",
            resource_type,
            resource_id,
            False,
            "权限不足",
        )
        return False

    def _get_cached_restricted_permissions(self, user_id: int, db: Session) -> Set[str]:
        """获取用户机器码限制权限（带请求级缓存）"""
        cache = _restricted_perms_cache.get()
        if cache is None:
            cache = {}
            _restricted_perms_cache.set(cache)

        if user_id not in cache:
            mcp_service = MachineCodePermissionService(db)
            cache[user_id] = mcp_service.get_user_restricted_permissions(user_id)

        return cache[user_id]

    async def get_user_permissions(self, user_id: str, db: Session) -> Set[str]:
        """获取用户所有权限（含机器码限制）

        权限计算逻辑：
        1. 获取用户角色默认权限 + 直接权限
        2. 如果用户设置了白名单(allowed_permissions)，取交集
        3. 减去机器码限制的权限
        """
        effective, _ = await self._compute_user_permissions_with_restrictions(user_id, db)
        return effective

    async def get_user_permissions_with_restrictions(self, user_id: str, db: Session) -> tuple[Set[str], Set[str]]:
        """获取用户权限及限制信息（单次查询）

        Returns:
            tuple: (effective_permissions, restricted_permissions)
        """
        return await self._compute_user_permissions_with_restrictions(user_id, db)

    async def _compute_user_permissions_with_restrictions(self, user_id: str, db: Session) -> tuple[Set[str], Set[str]]:
        """内部方法：计算用户权限及限制（只查询一次机器码权限）

        Returns:
            tuple: (effective_permissions, restricted_permissions)
        """
        permissions: Set[str] = set()

        now = _utcnow()

        # 获取直接权限
        direct_rows = (
            db.query(UserPermission.permission)
            .filter(
                UserPermission.user_id == int(user_id),
                (UserPermission.expires_at.is_(None) | (UserPermission.expires_at > now)),
            )
            .all()
        )
        for (perm,) in direct_rows:
            permissions.add(perm)

        # 获取角色权限
        role_perm_rows = (
            db.query(RolePermission.permission)
            .join(UserRole, RolePermission.role_id == UserRole.role_id)
            .join(RbacRole, UserRole.role_id == RbacRole.id)
            .filter(
                UserRole.user_id == int(user_id),
                RbacRole.is_active == True,  # noqa: E712
                (UserRole.expires_at.is_(None) | (UserRole.expires_at > now)),
            )
            .distinct()
            .all()
        )
        for (perm,) in role_perm_rows:
            permissions.add(perm)

        # 如果有管理员权限，返回所有权限
        if Permission.ADMIN_ALL.value in permissions:
            return ({p.value for p in Permission}, set())

        # 检查用户白名单权限
        user_allowed = None
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user_allowed = user.allowed_permissions_list

        if user_allowed:
            # 取白名单与当前权限的交集
            permissions = permissions.intersection(set(user_allowed))

        # 获取并减去机器码限制的权限（使用缓存）
        restricted_perms = self._get_cached_restricted_permissions(int(user_id), db)
        if restricted_perms:
            permissions = permissions - restricted_perms
            logger.info(
                "用户权限受机器码限制: user_id=%s, restricted=%s, remaining=%s",
                user_id,
                restricted_perms,
                permissions,
            )

        return permissions, restricted_perms

    async def assign_role(
        self,
        user_id: str,
        role_id: str,
        granted_by: str,
        db: Session = None,
        expires_at: str = None,
    ) -> dict:
        """分配角色给用户。

        返回 {"success": True, "newly_granted": bool}——
        newly_granted 为 True 表示新建分配，False 表示角色已存在。
        """
        # 检查角色是否存在且激活
        role = db.query(RbacRole).filter(RbacRole.id == role_id, RbacRole.is_active == True).first()  # noqa: E712
        if not role:
            raise NotFoundError("角色", role_id)

        now = _utcnow()
        # 检查是否已有该角色
        existing = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == int(user_id),
                UserRole.role_id == role_id,
                (UserRole.expires_at.is_(None) | (UserRole.expires_at > now)),
            )
            .first()
        )
        if existing:
            return {"success": True, "newly_granted": False}

        # 分配角色
        user_role = UserRole(
            user_id=int(user_id),
            role_id=role_id,
            granted_by=int(granted_by) if granted_by else None,
            expires_at=_safe_parse_expires(expires_at),
        )
        db.add(user_role)
        db.flush()  # flush 而非 commit — 由外层 TransactionManager 统一提交
        return {"success": True, "newly_granted": True}

    async def revoke_role(self, user_id: str, role_id: str, db: Session = None) -> bool:
        """撤销用户角色"""
        rows = (
            db.query(UserRole)
            .filter(UserRole.user_id == int(user_id), UserRole.role_id == role_id)
            .delete(synchronize_session=False)
        )
        db.flush()  # flush 而非 commit — 由外层 TransactionManager 统一提交
        return rows > 0

    async def grant_permission(
        self,
        user_id: str,
        permission: str,
        granted_by: str,
        expires_at: str = None,
        db: Session = None,
    ) -> bool:
        """直接授予权限给用户"""
        now = _utcnow()
        existing = (
            db.query(UserPermission)
            .filter(
                UserPermission.user_id == int(user_id),
                UserPermission.permission == permission,
                (UserPermission.expires_at.is_(None) | (UserPermission.expires_at > now)),
            )
            .first()
        )
        if existing:
            return True

        up = UserPermission(
            user_id=int(user_id),
            permission=permission,
            granted_by=int(granted_by) if granted_by else None,
            expires_at=_safe_parse_expires(expires_at),
        )
        db.add(up)
        db.flush()
        return True

    async def grant_permissions_batch(
        self,
        user_id: str,
        permissions: List[str],
        granted_by: str,
        expires_at: str = None,
        db: Session = None,
    ) -> Dict[str, Any]:
        """批量授予权限。单次预查询 + 批量 INSERT。

        调用方拥有事务边界（通过 TransactionManager.transaction）。
        返回 {"granted": [...], "skipped": [...], "failed": []}——
        skipped 为已存在的权限，failed 当前始终为空（为未来校验预留）。
        """
        uid = int(user_id)
        now = _utcnow()
        granted_by_int = int(granted_by) if granted_by else None
        expires = _safe_parse_expires(expires_at)

        # 第 1 步：预查询哪些权限已存在且未过期
        existing_rows = (
            db.query(UserPermission.permission)
            .filter(
                UserPermission.user_id == uid,
                UserPermission.permission.in_(permissions),
                (UserPermission.expires_at.is_(None) | (UserPermission.expires_at > now)),
            )
            .all()
        )
        existing = {row[0] for row in existing_rows}
        skipped = [p for p in permissions if p in existing]
        to_grant = [p for p in permissions if p not in existing]

        # 第 2 步：批量 INSERT 新增权限
        if to_grant:
            instances = [
                UserPermission(
                    user_id=uid,
                    permission=p,
                    granted_by=granted_by_int,
                    expires_at=expires,
                )
                for p in to_grant
            ]
            db.add_all(instances)
            db.flush()

        return {"granted": to_grant, "skipped": skipped, "failed": []}

    async def revoke_permission(
        self,
        user_id: str,
        permission: str,
        db: Session = None,
    ) -> bool:
        """撤销用户的单个权限。

        .. deprecated::
            使用 ``revoke_permissions_batch`` 代替。此方法保留仅供向后兼容。
            调用方负责通过 TransactionManager.transaction(db) 包裹事务边界——
            此方法仅调用 db.flush()，不提交。
        """
        import warnings
        warnings.warn(
            "RBACService.revoke_permission 已弃用，请使用 revoke_permissions_batch",
            DeprecationWarning,
            stacklevel=2,
        )
        rows = (
            db.query(UserPermission)
            .filter(
                UserPermission.user_id == int(user_id),
                UserPermission.permission == permission,
            )
            .delete(synchronize_session=False)
        )
        db.flush()  # flush 而非 commit — 由外层 TransactionManager 统一提交
        return rows > 0

    async def revoke_permissions_batch(
        self,
        user_id: str,
        permissions: List[str],
        db: Session = None,
    ) -> tuple:
        """批量撤销用户权限。返回 (revoked: List[str], failed: List[str])。

        使用预查询确定哪些权限实际存在，然后单条 DELETE 批量删除。
        调用方拥有事务边界（通过 TransactionManager.transaction）。
        """
        uid = int(user_id)

        # 第 1 步：预查询哪些权限对用户实际存在
        existing_rows = (
            db.query(UserPermission.permission)
            .filter(UserPermission.user_id == uid, UserPermission.permission.in_(permissions))
            .all()
        )
        existing = {row[0] for row in existing_rows}
        missing = [p for p in permissions if p not in existing]

        # 第 2 步：单条批量 DELETE — 仅删除实际存在的权限
        if existing:
            db.query(UserPermission).filter(
                UserPermission.user_id == uid,
                UserPermission.permission.in_(list(existing)),
            ).delete(synchronize_session=False)
            db.flush()

        return list(existing), missing

    async def save_permissions(
        self,
        user_id: str,
        permissions: List[str],
        granted_by: str,
        db: Session = None,
        expires_at: str = None,
    ) -> dict:
        """原子性保存用户权限：在单个事务内完成删除旧权限 + 授予新权限。

        接受目标权限集合，与现有权限比对后：
        - 撤销不再需要的权限
        - 授予新增权限
        - 跳过已存在的权限

        调用方拥有事务边界（通过 TransactionManager.transaction）。

        返回 {"revoked": [...], "granted": [...], "skipped": [...], "failed": []}。
        """
        uid = int(user_id)
        granted_by_int = int(granted_by) if granted_by else None
        expires = _safe_parse_expires(expires_at)
        now = _utcnow()

        # 第 1 步：获取当前有效权限
        existing_rows = (
            db.query(UserPermission.permission)
            .filter(
                UserPermission.user_id == uid,
                (UserPermission.expires_at.is_(None) | (UserPermission.expires_at > now)),
            )
            .all()
        )
        existing = {row[0] for row in existing_rows}
        target = set(permissions)

        to_revoke = existing - target
        to_grant = target - existing
        skipped = existing & target

        # 第 2 步：批量撤销
        if to_revoke:
            db.query(UserPermission).filter(
                UserPermission.user_id == uid,
                UserPermission.permission.in_(list(to_revoke)),
            ).delete(synchronize_session=False)

        # 第 3 步：批量授予
        if to_grant:
            instances = [
                UserPermission(
                    user_id=uid,
                    permission=p,
                    granted_by=granted_by_int,
                    expires_at=expires,
                )
                for p in to_grant
            ]
            db.add_all(instances)

        if to_revoke or to_grant:
            db.flush()

        return {
            "revoked": sorted(to_revoke),
            "granted": sorted(to_grant),
            "skipped": sorted(skipped),
            "failed": [],
        }

    async def create_role(
        self,
        name: str,
        description: str,
        permissions: List[str],
        is_system: bool = False,
        db: Session = None,
    ) -> str:
        """创建角色"""
        role = RbacRole(name=name, description=description, is_system=is_system)
        db.add(role)
        db.flush()  # 获取生成的 id

        for perm in permissions:
            rp = RolePermission(role_id=role.id, permission=perm)
            db.add(rp)

        db.flush()  # flush 而非 commit — 由外层 TransactionManager 统一提交
        return role.id

    async def get_user_roles(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        """获取用户角色列表"""
        now = _utcnow()
        rows = (
            db.query(
                RbacRole.id,
                RbacRole.name,
                RbacRole.description,
                RbacRole.is_system,
                UserRole.granted_by,
                UserRole.expires_at,
            )
            .join(UserRole, RbacRole.id == UserRole.role_id)
            .filter(
                UserRole.user_id == int(user_id),
                RbacRole.is_active == True,  # noqa: E712
                (UserRole.expires_at.is_(None) | (UserRole.expires_at > now)),
            )
            .order_by(RbacRole.priority.asc())
            .all()
        )

        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "is_system": r.is_system,
                "granted_by": r.granted_by,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 内部方法（同步，无需 await）
    # ------------------------------------------------------------------

    def _has_admin_role(self, user_id: str, db: Session) -> bool:
        """检查是否有管理员角色"""
        now = _utcnow()
        count = (
            db.query(sa_func.count(RbacRole.id))
            .join(UserRole, RbacRole.id == UserRole.role_id)
            .filter(
                UserRole.user_id == int(user_id),
                RbacRole.name == "admin",
                RbacRole.is_active == True,  # noqa: E712
                (UserRole.expires_at.is_(None) | (UserRole.expires_at > now)),
            )
            .scalar()
        )
        return (count or 0) > 0

    def _has_direct_permission(self, user_id: str, permission: str, db: Session) -> bool:
        """检查是否有直接权限"""
        now = _utcnow()
        count = (
            db.query(sa_func.count(UserPermission.id))
            .filter(
                UserPermission.user_id == int(user_id),
                UserPermission.permission == permission,
                (UserPermission.expires_at.is_(None) | (UserPermission.expires_at > now)),
            )
            .scalar()
        )
        return (count or 0) > 0

    def _has_role_permission(self, user_id: str, permission: str, db: Session) -> bool:
        """检查是否有角色权限"""
        now = _utcnow()
        count = (
            db.query(sa_func.count(RolePermission.id))
            .join(UserRole, RolePermission.role_id == UserRole.role_id)
            .join(RbacRole, UserRole.role_id == RbacRole.id)
            .filter(
                UserRole.user_id == int(user_id),
                RolePermission.permission == permission,
                RbacRole.is_active == True,  # noqa: E712
                (UserRole.expires_at.is_(None) | (UserRole.expires_at > now)),
            )
            .scalar()
        )
        return (count or 0) > 0

    def _has_resource_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        access_level: str,
        db: Session,
    ) -> bool:
        """检查是否有资源访问权限"""
        now = _utcnow()
        count = (
            db.query(sa_func.count(ResourceAccessControl.id))
            .filter(
                ResourceAccessControl.user_id == int(user_id),
                ResourceAccessControl.resource_type == resource_type,
                ResourceAccessControl.resource_id == resource_id,
                ResourceAccessControl.access_level == access_level,
                (ResourceAccessControl.expires_at.is_(None) | (ResourceAccessControl.expires_at > now)),
            )
            .scalar()
        )
        return (count or 0) > 0

    def _log_access(
        self,
        db: Session,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        access_granted: bool,
        reason: str,
    ):
        """记录访问日志"""
        try:
            log = AccessLog(
                user_id=str(user_id),
                action=action,
                resource_type=resource_type or "",
                resource_id=resource_id or "",
                access_granted=access_granted,
                reason=reason,
                ip_address="unknown",
                user_agent="unknown",
            )
            db.add(log)
            db.flush()
        except Exception as e:
            logger.warning("记录访问日志失败: %s", e)


# 创建全局 RBAC 服务实例
rbac_service = RBACService()
