"""
Unified data permission / scope module.

Consolidates two previously-parallel data-scoping systems:

*   System 1 (``core/data_permission.py``) — used by CRUD endpoints (villages,
    projects, schools, etc.).  Role-based via ``DataScope`` enum with
    ``apply_scope_to_query`` / ``filter_by_data_scope``.

*   System 2 (``api/v1/data_scope.py``) — used by map & dashboard endpoints.
    Org-tree–based via ``OrgScopeFilter`` and ``filter_by_org_ids``.

Both pathways now live here.  All callers should import from this module.
"""

import logging
from enum import Enum
from typing import Any, List, Optional, Tuple

from fastapi import Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import is_admin, is_superuser
from app.core.security import get_current_user
from app.models.organization import Organization

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
#  Re-export helpers so callers don't need to chase the import chain
# ────────────────────────────────────────────────────────────────────
# (kept in-line — no star imports)

_ORG_TREE_MAX_DEPTH = 10  # prevent infinite recursion on cyclic refs


# ════════════════════════════════════════════════════════════════════
#  PART 1 — Role-based DataScope (from core/data_permission.py)
# ════════════════════════════════════════════════════════════════════

class DataScope(str, Enum):
    """Data visibility scopes — role-based."""

    ALL = "all"
    """See all records – super admin."""

    OWN_DEPT = "own_dept"
    """See records belonging to the user's own department / organization."""

    OWN = "own"
    """See only the user's own records."""


def get_data_scope(user: Any) -> DataScope:
    """Determine the *role-based* data scope for a given user.

    Args:
        user: A user model instance (must have ``role`` and optionally
            ``is_superuser`` attributes).

    Returns:
        The appropriate :class:`DataScope` value.
    """
    if user is None:
        return DataScope.OWN

    from app.core.constants import normalize_role

    is_su = getattr(user, "is_superuser", False)
    # 归一化角色：历史角色值（manager/approval_leader/operator）映射到精简角色，
    # 保证存量用户的数据范围不因角色精简而降级
    role = normalize_role(getattr(user, "role", ""))

    if is_su or role == "super_admin":
        return DataScope.ALL

    if role == "admin":
        return DataScope.OWN_DEPT

    return DataScope.OWN


def apply_scope_to_query(
    query: Any,
    model: Any,
    user: Any,
    *,
    owner_field: str = "created_by",
    dept_field: str = "organization_id",
) -> Any:
    """Add filters to a SQLAlchemy query based on the user's *role-based* data scope.

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
        user_dept = getattr(user, dept_field, None)
        if user_dept is not None:
            return query.filter(getattr(model, dept_field) == user_dept)
        logger.debug("User has no organization; falling back to OWN scope")
        scope = DataScope.OWN

    if scope == DataScope.OWN:
        return query.filter(getattr(model, owner_field) == getattr(user, "id", None))

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
    if scope == DataScope.OWN:
        return getattr(record, owner_field, None) == getattr(user, "id", None)
    return False


def filter_by_data_scope(query, model, user, db=None, org_field="organization_id"):
    """Filter a query by the user's role-based data scope.

    Delegates to :func:`apply_scope_to_query` for the actual filtering.
    Admin users see all records.
    """
    if is_admin(user):
        return query
    return apply_scope_to_query(query, model, user, owner_field="created_by", dept_field=org_field)


# Backward-compat alias
apply_data_scope = apply_scope_to_query


def require_data_permission(
    current_user,
    organization_id=None,
    created_by=None,
    db=None,
    error_message="无权执行此操作",
):
    """Check data permission.

    Admin users auto-pass; others must own the record or belong to the same org.
    """
    if is_admin(current_user):
        return True
    if not db:
        logger.warning("require_data_permission called without db session — denying access")
        raise HTTPException(status_code=403, detail=error_message)
    if created_by is not None and created_by == getattr(current_user, "id", None):
        return True
    raise HTTPException(status_code=403, detail=error_message)


# ════════════════════════════════════════════════════════════════════
#  PART 2 — Org-tree–based OrgScopeFilter (from api/v1/data_scope.py)
# ════════════════════════════════════════════════════════════════════

class OrgScopeFilter:
    """Org-based data scope filter.

    Replaces the old ``DataScope`` class from ``api/v1/data_scope.py``.
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
