"""Data permission / scope utilities — SINGLE SOURCE OF TRUTH.

This module consolidates what used to be **four** parallel data-scoping
implementations (removed 2026-09):

* ``core/data_permission.py``        — role-based :class:`DataScope`
  (``get_data_scope`` / ``apply_scope_to_query`` / ``filter_by_data_scope``).
* ``core/unified_data_scope.py``     — org-tree :class:`OrgScopeFilter`
  (``_get_org_subtree`` / ``get_org_scope``).
* ``core/data_scope_adapter.py``     — Select/Query adapter
  (``apply_scope_filter`` / ``get_accessible_org_ids``).
* ``services/village/data_permission.py`` — thin forwarder.

All callers must import from **this** module.

Semantics:

* :func:`get_data_scope` maps roles to scopes: super-admin→ALL, admin→OWN_DEPT,
  others→OWN.
* :func:`filter_by_data_scope` (internal list/export paths, ~40 callers) follows
  the role semantics **strictly**: a department-level admin (``role="admin"``,
  ``is_superuser=False``) is limited to its own organization — this preserves the
  military audit **S2 export-isolation red-line** (cross-org data must not leak).
* :func:`apply_scope_filter` / :func:`get_org_scope` (org-tree endpoints:
  map / dashboard / effectiveness / statistics) grant administrators full access
  (admin sees all) — the org-tree visibility model.
"""

import logging
from enum import Enum
from typing import Any, List, Optional, Tuple

from fastapi import Depends, HTTPException
from sqlalchemy import Select, false as sa_false, or_
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN, normalize_role
from app.core.database import get_db
from app.core.permission_utils import is_admin, is_superuser
from app.core.security import get_current_user
from app.models.organization import Organization

logger = logging.getLogger(__name__)

# Max depth when expanding the org tree (guards against cyclic parent refs).
_ORG_TREE_MAX_DEPTH = 10


# ════════════════════════════════════════════════════════════════════
#  PART 1 — Role-based DataScope
# ════════════════════════════════════════════════════════════════════

class DataScope(str, Enum):
    """Data visibility scopes."""

    ALL = "all"
    """See all records – super admin / administrator (see is_admin)."""

    OWN_DEPT = "own_dept"
    """See records belonging to the user's own department/organization."""

    OWN = "own"
    """See only the user's own records."""


def get_data_scope(user: Any) -> DataScope:
    """Determine the data scope for a given user.

    Uses :func:`normalize_role` to map deprecated roles (``approval_leader``,
    ``manager``) to their current equivalents, ensuring consistent data
    scoping for legacy user accounts.

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
        if user_dept is not None and hasattr(model, dept_field):
            return query.filter(getattr(model, dept_field) == user_dept)
        # 部门/组织未设置，或模型缺组织列时回退到 OWN 范围（ADR-0002）
        logger.debug(
            "User has no organization or model lacks %s; falling back to OWN scope", dept_field
        )
        scope = DataScope.OWN  # 显式回退

    if scope == DataScope.OWN:
        owner_col = getattr(model, owner_field, None)
        if owner_col is None:
            # fail-closed（ADR-0002）：模型连 owner 字段都没有时无法安全限定，
            # 返回空集而非 AttributeError→500（如 legacy villages 表）
            logger.warning(
                "Model %s lacks owner field '%s'; data scope fail-closed to empty set",
                getattr(model, "__name__", model), owner_field,
            )
            return query.filter(sa_false())
        return query.filter(owner_col == getattr(user, "id", None))

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
    """按数据权限过滤查询（角色语义，与 :func:`get_data_scope` 一致）。

    * ``super_admin``（或 ``is_superuser``）→ ``DataScope.ALL``，不过滤；
    * ``admin`` → ``DataScope.OWN_DEPT``：**仅本组织**，跨组织记录被隔离；
    * 普通用户 → ``DataScope.OWN``：仅本人创建。

    ⚠️ 安全语义（军事审计红线 S2，见 ``test_import_export_permission_security``）：
    部门级管理员（``role="admin"`` 且 ``is_superuser=False``）导出资金/学校/项目时
    **必须**限定在本组织范围，**不得**跨组织泄漏。因此本函数**不做** admin 放行豁免
    ——它委托 :func:`apply_scope_to_query`，由 :func:`get_data_scope` 决定范围。

    注：本函数服务于内部列表/导出（async_export_service、data_quality 等约 40 处
    调用点），对部门级 admin 严格限定本组织；面向组织树端点（map/dashboard 等）的
    :func:`apply_scope_filter` / :func:`get_org_scope` 另有 admin 全量语义。
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


# ════════════════════════════════════════════════════════════════════
#  PART 2 — Org-tree based OrgScopeFilter
# ════════════════════════════════════════════════════════════════════

class OrgScopeFilter:
    """Org-based data scope filter.

    Used by map endpoints, dashboards, and any endpoint that filters
    by organization tree membership.
    """

    def __init__(
        self,
        is_admin: bool,
        org_ids: Optional[List[int]] = None,
        org_names: Optional[List[str]] = None,
        self_only: bool = False,
        user_id: Optional[int] = None,
    ):
        self.is_admin = is_admin
        self.org_ids = org_ids or []
        self.org_names = org_names or []
        self.self_only = self_only
        self.user_id = user_id

    def has_full_access(self) -> bool:
        """Return True if this scope grants access to all records."""
        return self.is_admin

    def filter_by_org_ids(self, query, *id_columns, created_by_column=None):
        """Apply precise org-ID–based filtering to *query*.

        Args:
            query: SQLAlchemy query object.
            *id_columns: One or more ``organization_id`` columns to filter on.
            created_by_column: Optional ``created_by`` column for ``self_only`` mode.

        Returns:
            The filtered query.
        """
        if self.is_admin:
            return query

        if self.self_only:
            if created_by_column is not None and self.user_id is not None:
                return query.filter(created_by_column == self.user_id)
            return query.filter(False)

        if not self.org_ids:
            return query.filter(False)

        conditions = [col.in_(self.org_ids) for col in id_columns]
        if conditions:
            return query.filter(or_(*conditions))
        return query.filter(False)


def _get_org_subtree(
    db: Session,
    org_id: int,
    _depth: int = 0,
    _visited: Optional[set] = None,
) -> Tuple[List[int], List[str]]:
    """Single-pass traversal: get IDs and names of *org_id* and all descendants.

    Returns:
        (ids, names) tuple.
    """
    if _depth > _ORG_TREE_MAX_DEPTH:
        logger.warning("Org tree recursion exceeded max depth %d, truncated at org_id=%d", _ORG_TREE_MAX_DEPTH, org_id)
        return [], []
    if _visited is None:
        _visited = set()
    if org_id in _visited:
        logger.warning("Org tree cycle detected, org_id=%d", org_id)
        return [], []
    _visited.add(org_id)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return [], []

    ids = [org.id]
    names = [org.name]
    for child in db.query(Organization).filter(Organization.parent_id == org_id).all():
        child_ids, child_names = _get_org_subtree(db, child.id, _depth + 1, _visited)
        ids.extend(child_ids)
        names.extend(child_names)
    return ids, names


async def get_org_scope(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrgScopeFilter:
    """FastAPI dependency — resolves the org-based data scope for *current_user*.

    Uses the user's ``role``, ``data_scope`` field and ``organization_id``
    to build an :class:`OrgScopeFilter`.
    """
    role = getattr(current_user, "role", "user")
    user_data_scope = getattr(current_user, "data_scope", "org") or "org"

    # Admin roles or explicit "all" scope → full access
    if role in ("admin", "super_admin") or is_superuser(current_user) or user_data_scope == "all":
        return OrgScopeFilter(is_admin=True)

    org_id = getattr(current_user, "organization_id", None)

    def _no_org_self_only() -> OrgScopeFilter:
        """无组织归属 fail-closed（ADR-0002）：回退"仅本人"，绝不 is_admin 放行全量"""
        return OrgScopeFilter(
            is_admin=False,
            org_ids=[],
            org_names=[],
            self_only=True,
            user_id=getattr(current_user, "id", None),
        )

    # Self only
    if user_data_scope == "self":
        return OrgScopeFilter(
            is_admin=False,
            org_ids=[],
            org_names=[],
            self_only=True,
            user_id=getattr(current_user, "id", None),
        )

    # Single org
    if user_data_scope == "org":
        if not org_id:
            dept = getattr(current_user, "department", None)
            if dept:
                return OrgScopeFilter(is_admin=False, org_names=[dept], org_ids=[])
            return _no_org_self_only()
        org = db.query(Organization).filter(Organization.id == org_id).first()
        org_names = [org.name] if org else []
        return OrgScopeFilter(is_admin=False, org_names=org_names, org_ids=[org_id])

    # org_children (default): current org + all descendants
    if not org_id:
        dept = getattr(current_user, "department", None)
        if dept:
            return OrgScopeFilter(is_admin=False, org_names=[dept], org_ids=[])
        return _no_org_self_only()

    org_ids, org_names = _get_org_subtree(db, org_id)
    if not org_names:
        dept = getattr(current_user, "department", None)
        if dept:
            return OrgScopeFilter(is_admin=False, org_names=[dept], org_ids=org_ids)
        return _no_org_self_only()

    return OrgScopeFilter(is_admin=False, org_names=org_names, org_ids=org_ids)


# ════════════════════════════════════════════════════════════════════
#  PART 3 — Select/Query unified adapter
# ════════════════════════════════════════════════════════════════════

class DataScopeFilterError(RuntimeError):
    """模型缺少数据范围过滤字段且无法安全降级时抛出（fail-closed, ADR-0002）"""


def get_accessible_org_ids(user: Any, db: Any = None) -> Optional[List[int]]:
    """计算用户可访问的组织 ID 列表（统一权限计算入口）。

    返回值约定：
        * ``None``      -- 不限制（管理员 / 全局权限）
        * ``[]``        -- 无组织级访问权限（调用方应回退到"仅本人"过滤或返回空结果）
        * ``[id, ...]`` -- 可访问的组织 ID 列表

    Args:
        user: 当前用户对象（需有 role / is_superuser / organization_id 等属性）。
        db: 可选的 SQLAlchemy Session。提供时按组织树展开（包含下级组织）；
            不提供时仅返回用户本组织 ID。

    注意：
        当用户范围为"仅本人"(OWN / data_scope="self") 时，本函数返回 ``[]``，
        因为该范围无法用组织 ID 表达；:func:`apply_scope_filter` 会据此回退到
        ``created_by == user.id`` 的所有者过滤。
    """
    if user is None:
        return []

    # 管理员（含超级管理员）不受数据权限限制
    if is_admin(user):
        return None

    # 兼容 user.data_scope 字段（组织树体系的显式配置）
    user_data_scope = getattr(user, "data_scope", None)
    if user_data_scope == "all":
        return None
    if user_data_scope == "self":
        return []

    scope = get_data_scope(user)
    if scope == DataScope.ALL:
        return None

    org_id = getattr(user, "organization_id", None)
    if org_id is None:
        org_id = getattr(user, "org_id", None)

    if scope == DataScope.OWN_DEPT and org_id is not None:
        if db is not None:
            # 组织树展开：本组织 + 所有下级（与 OrgScopeFilter 语义一致）
            org_ids, _names = _get_org_subtree(db, org_id)
            return org_ids if org_ids else [org_id]
        return [org_id]

    # OWN 范围或无组织归属：无组织级权限
    return []


def apply_scope_filter(
    query: Any,  # sqlalchemy.orm.Query 或 sqlalchemy.Select
    user: Any,
    model: Any,
    org_id_field: str = "organization_id",
    *,
    owner_field: str = "created_by",
    db: Any = None,
) -> Any:
    """统一数据权限过滤入口。

    自动检测 query 类型（SQLAlchemy 2.0 ``Select`` vs 旧式 ``Query``）
    并应用对应的过滤方式：``Select`` 用 ``.where()``，``Query`` 用 ``.filter()``。

    Args:
        query: SQLAlchemy ``Query`` 或 ``Select`` 对象。
        user: 当前用户对象。
        model: 目标 ORM 模型类（用于解析过滤字段）。
        org_id_field: 组织 ID 字段名（默认 ``organization_id``）。
        owner_field: 所有者字段名（默认 ``created_by``，用于"仅本人"范围）。
        db: 可选 Session。提供时按组织树展开可访问组织（含下级）。

    Returns:
        过滤后的 query 对象（与入参同类型）。

    行为说明：
        * 管理员 / super_admin / data_scope="all" -> 不过滤；
        * 部门范围(OWN_DEPT) -> ``model.org_id_field IN (可访问组织IDs)``；
          用户无组织归属时回退到"仅本人"；
        * 仅本人(OWN / data_scope="self") -> ``model.owner_field == user.id``；
        * 模型缺少组织字段 -> fail-closed（ADR-0002）：降级为"仅本人"并记
          error 日志，绝不静默放行全量；连 owner 字段也缺失则抛错拒绝。
    """
    # 管理员（含超级管理员）不受数据权限限制
    if is_admin(user):
        return query

    # 显式 data_scope 字段优先（兼容组织树体系的用户配置）
    user_data_scope = getattr(user, "data_scope", None)
    if user_data_scope == "all":
        return query
    if user_data_scope == "self":
        return _apply_owner_filter(query, model, owner_field, user)

    scope = get_data_scope(user)
    if scope == DataScope.ALL:
        return query

    if scope == DataScope.OWN_DEPT:
        org_ids = get_accessible_org_ids(user, db=db)
        if org_ids is None:
            return query
        if not org_ids:
            # 无组织归属 -> 回退到"仅本人"（与 apply_scope_to_query 行为一致）
            logger.debug("User has no organization; falling back to OWN scope")
            return _apply_owner_filter(query, model, owner_field, user)
        if _has_field(model, org_id_field):
            return _apply_org_filter(query, model, org_id_field, org_ids)
        # fail-closed（ADR-0002）：模型缺组织字段时禁止静默放行全量，
        # 降级为"仅本人"；连 owner 字段也缺失则抛错拒绝
        logger.error(
            "Model %s 缺少组织字段 '%s'，数据范围降级为仅本人(fail-closed)", model, org_id_field
        )
        return _apply_owner_filter(query, model, owner_field, user)

    # OWN 范围（或 OWN_DEPT 回退）
    return _apply_owner_filter(query, model, owner_field, user)


# ────────────────────────────────────────────────────────────────────
#  内部工具函数
# ────────────────────────────────────────────────────────────────────

def _is_select(query: Any) -> bool:
    """判断是否为 SQLAlchemy 2.0 Select 对象。"""
    return isinstance(query, Select)


def _has_field(model: Any, field: str) -> bool:
    return getattr(model, field, None) is not None


def _apply_org_filter(query: Any, model: Any, org_id_field: str, org_ids: List[int]) -> Any:
    """按组织 ID 列表过滤（IN 条件）。调用方须先用 _has_field 确认字段存在。"""
    org_field = getattr(model, org_id_field, None)
    if org_field is None:
        # 不可达：apply_scope_filter 已做 _has_field 前置检查（fail-closed 降级）
        raise DataScopeFilterError(f"Model {model.__name__} 缺少组织字段 '{org_id_field}'")
    if _is_select(query):
        return query.where(org_field.in_(org_ids))
    return query.filter(org_field.in_(org_ids))


def _apply_owner_filter(query: Any, model: Any, owner_field: str, user: Any) -> Any:
    """按所有者过滤（仅本人创建的数据）。

    模型缺少 owner 字段时 fail-closed 抛错（ADR-0002）——绝不允许静默放行全量。
    """
    owner_col = getattr(model, owner_field, None)
    if owner_col is None:
        raise DataScopeFilterError(
            f"Model {getattr(model, '__name__', model)} 缺少数据范围过滤字段 "
            f"'{owner_field}'，无法安全限定数据范围（fail-closed, ADR-0002）"
        )
    user_id = getattr(user, "id", None)
    if _is_select(query):
        return query.where(owner_col == user_id)
    return query.filter(owner_col == user_id)
