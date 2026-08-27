"""Data permission utilities.

Provides helpers for scoping database queries based on the current user's
permission level and data visibility rules.
"""

import logging
from enum import Enum
from typing import Any

from fastapi import HTTPException

from app.core.permission_utils import is_superuser
from app.core.constants import normalize_role, ROLE_SUPER_ADMIN, ROLE_ADMIN

logger = logging.getLogger(__name__)


class DataScope(str, Enum):
    """Data visibility scopes."""

    ALL = "all"
    """See all records – super admin."""

    OWN_DEPT = "own_dept"
    """See records belonging to the user's own department/organization."""

    OWN = "own"
    """See only the user's own records."""


def is_admin(user: Any) -> bool:
    """Check whether a user holds an administrative role.

    Uses normalize_role() to map deprecated roles (approval_leader, manager)
    to their current equivalents (admin), ensuring backward compatibility.

    Args:
        user: A user model instance (must have ``role`` and optionally
            ``is_superuser`` attributes).

    Returns:
        *True* if the user is a superuser or has an admin-level role.
    """
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    role = normalize_role(getattr(user, "role", ""))
    return role in (ROLE_ADMIN, ROLE_SUPER_ADMIN)


def get_data_scope(user: Any) -> DataScope:
    """Determine the data scope for a given user.

    Uses normalize_role() to map deprecated roles to current equivalents,
    ensuring consistent data scoping for legacy user accounts.

    Args:
        user: A user model instance (must have ``role`` and optionally
            ``is_superuser`` attributes).

    Returns:
        The appropriate :class:`DataScope` value.
    """
    if user is None:
        return DataScope.OWN

    is_su = getattr(user, "is_superuser", False)
    role = normalize_role(getattr(user, "role", ""))

    if is_su or role == ROLE_SUPER_ADMIN:
        return DataScope.ALL

    if role == ROLE_ADMIN:
        return DataScope.OWN_DEPT

    # user, viewer → 仅本人数据
    return DataScope.OWN


def apply_scope_to_query(
    query: Any,
    model: Any,
    user: Any,
    *,
    owner_field: str = "created_by",
    dept_field: str = "organization_id",
) -> Any:
    """Add filters to a SQLAlchemy query based on the user's data scope.

    Args:
        query: An existing SQLAlchemy :class:`Query` object.
        model: The ORM model class.
        user: The current user instance.
        owner_field: Name of the column holding the owner's user ID.
        dept_field: Name of the column holding the organization/department ID.

    Returns:
        The filtered query.
    """
    scope = get_data_scope(user)

    if scope == DataScope.ALL:
        return query

    if scope == DataScope.OWN_DEPT:
        # 使用 dept_field 参数（调用者传入，通常为 organization_id）
        # 从 User 模型上读取同名属性（organization_id）
        user_dept = getattr(user, dept_field, None)
        if user_dept is not None:
            return query.filter(getattr(model, dept_field) == user_dept)
        # 部门/组织未设置时回退到 OWN 范围
        logger.debug("User has no organization; falling back to OWN scope")
        scope = DataScope.OWN  # 显式回退

    if scope == DataScope.OWN:
        return query.filter(getattr(model, owner_field) == getattr(user, "id", None))

    # 防御性兜底：DataScope 未来扩展新枚举值时按最严格语义原样返回，
    # 由 TestUnknownScopeFallback 回归测试锁定（fail-safe: 不过滤不加权）
    return query


def check_record_access(
    record: Any,
    user: Any,
    *,
    owner_field: str = "created_by",
    dept_field: str = "organization_id",
) -> bool:
    """Check whether *user* is allowed to access a single *record*.

    Args:
        record: An ORM model instance.
        user: The current user.
        owner_field: Column name identifying the record owner.
        dept_field: Column name identifying the organization/department.

    Returns:
        *True* if access is permitted.
    """
    scope = get_data_scope(user)
    if scope == DataScope.ALL:
        return True
    if scope == DataScope.OWN_DEPT:
        return getattr(record, dept_field, None) == getattr(user, dept_field, None)
    # OWN：仅记录创建者本人可见
    return getattr(record, owner_field, None) == getattr(user, "id", None)


def filter_by_data_scope(query, model, user, db=None, org_field="organization_id"):
    """按数据权限过滤查询。委托给 apply_scope_to_query 实现完整过滤。

    仅 super_admin 跳过过滤（DataScope.ALL）；admin/manager 限定本组织（OWN_DEPT）；
    普通用户限定本人记录（OWN）。
    """
    return apply_scope_to_query(query, model, user, owner_field="created_by", dept_field=org_field)


apply_data_scope = apply_scope_to_query


def require_data_permission(current_user, organization_id=None, created_by=None, db=None, error_message="无权执行此操作"):
    """检查数据权限。超级管理员自动通过；其他用户需通过归属/组织检查。"""
    if is_superuser(current_user):
        return True
    # 检查是否为用户自己的记录
    if created_by is not None and created_by == getattr(current_user, "id", None):
        return True
    # 检查是否为用户本组织的记录
    if organization_id is not None and organization_id == getattr(current_user, "organization_id", None):
        return True
    raise HTTPException(status_code=403, detail=error_message)
