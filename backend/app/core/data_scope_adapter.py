"""
统一数据权限适配层

项目中存在三种数据权限过滤实现（历史原因）：
1. apply_data_scope()                - SQLAlchemy 2.0 select 风格 (funds.py, fund_lifecycle.py, fund_budgets.py)
                                       来源: app.core.data_permission.apply_scope_to_query
2. OrgScopeFilter.filter_by_org_ids() - 旧式 query + 组织树风格 (school.py, map.py, dashboard.py)
                                       来源: app.core.unified_data_scope (原 app.api.v1.data_scope)
3. filter_by_data_scope()            - 混合风格 (supported_village.py, assessment.py, effectiveness.py)
                                       来源: app.core.data_permission

本模块提供统一入口，新代码应使用此适配器。
旧代码逐步迁移，不强制重写。

三种实现的语义差异（迁移时需注意）：
- 实现 1/3 基于"角色"判定范围：super_admin/admin -> 全部；manager/approval_leader -> 本组织；
  其他角色 -> 仅本人创建的数据。
- 实现 2 基于"组织树"判定范围：读取 user.data_scope 字段
  ("all" / "org_children" / "org" / "self")，org_children 会递归包含下级组织。

本适配器默认采用角色语义（与实现 1/3 一致）；传入 db 会话时可启用组织树展开
（与实现 2 的 org_children 语义一致）。

用法示例（新代码）::

    from app.core.data_scope_adapter import apply_scope_filter

    # SQLAlchemy 2.0 select 风格
    stmt = apply_scope_filter(select(Fund), current_user, Fund)
    rows = db.execute(stmt).scalars().all()

    # 旧式 Query 风格
    query = apply_scope_filter(db.query(School), current_user, School)

    # 需要包含下级组织时传入 db（组织树语义）
    stmt = apply_scope_filter(select(School), current_user, School, db=db)

设计说明：
    最初设计中假设存在 ``DataScopeService.get_accessible_org_ids()``，
    但项目中并无该服务。本模块改为直接复用现有实现：
    - 角色/范围判定: app.core.data_permission.get_data_scope
    - 管理员判定:    app.core.permission_utils.is_admin
    - 组织树展开:    app.core.unified_data_scope._get_org_subtree (仅当传入 db)
"""

import logging
from typing import Any, List, Optional

from sqlalchemy import Select

logger = logging.getLogger(__name__)


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
        db: 可选的 SQLAlchemy Session。提供时按组织树展开（包含下级组织，
            对应实现 2 的 org_children 语义）；不提供时仅返回用户本组织 ID。

    注意：
        当用户范围为"仅本人"(OWN / data_scope="self") 时，本函数返回 ``[]``，
        因为该范围无法用组织 ID 表达；:func:`apply_scope_filter` 会据此回退到
        ``created_by == user.id`` 的所有者过滤。
    """
    from app.core.data_permission import DataScope, get_data_scope
    from app.core.permission_utils import is_admin

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
            from app.core.unified_data_scope import _get_org_subtree

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

    行为说明（与现有实现保持一致）：
        * 管理员 / super_admin / data_scope="all" -> 不过滤；
        * 部门范围(OWN_DEPT) -> ``model.org_id_field IN (可访问组织IDs)``；
          用户无组织归属时回退到"仅本人"（与 apply_scope_to_query 行为一致）；
        * 仅本人(OWN / data_scope="self") -> ``model.owner_field == user.id``；
        * 模型缺少组织字段 -> fail-closed（ADR-0002）：降级为"仅本人"并记
          error 日志，绝不静默放行全量；连 owner 字段也缺失则抛错拒绝。
    """
    from app.core.data_permission import DataScope, get_data_scope
    from app.core.permission_utils import is_admin

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
