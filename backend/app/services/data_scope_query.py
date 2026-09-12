"""服务层统一数据域查询入口（架构评估 B1 下沉 · Phase 1）。

背景（架构评估 B1【P1】）：数据域过滤此前依赖路由层逐点手工调用
``core.data_permission.filter_by_data_scope``，"忘加过滤"只能靠
``scripts/security_audit.py`` 扫描器兜底——结构性上仍是可能的。

本模块把过滤入口**下沉到服务层**：业务/报表代码不再直接 import 核心过滤
原语，而是经由这里的 ``scoped_query`` / ``scoped_filter`` / ``scoped_count``
获取已按数据域隔离的查询。过滤语义**仍是单一真源**
（:mod:`app.core.data_permission`），本模块只做统一入口与文档化，不重复实现。

Phase 1（本期）：迁移评估点名的热点 ``api/v1/data/data/reports.py``；
其余 ~40 个调用点按模块分批迁移（迁移时不改变任何过滤语义，扫描器同步
识别新入口名，作为回归防线保留）。
"""

from typing import Any

from sqlalchemy.orm import Session

__all__ = ["scoped_query", "scoped_filter", "scoped_count"]


def scoped_query(
    db: Session,
    model: Any,
    user: Any,
    *,
    org_field: str = "organization_id",
) -> Any:
    """从零构建一个已按数据域过滤的模型查询。

    Args:
        db: SQLAlchemy Session。
        model: 目标 ORM 模型类。
        user: 当前用户（语义与 :func:`filter_by_data_scope` 一致：
            super_admin → 全量；admin → 仅本组织（S2 红线，不做放行豁免）；
            普通用户 → 仅本人创建）。
        org_field: 组织字段名（默认 ``organization_id``）。
        owner_field: 所有者字段名（默认 ``created_by``）。

    Returns:
        已过滤的 Query。
    """
    from app.core.data_permission import filter_by_data_scope

    return filter_by_data_scope(db.query(model), model, user, org_field=org_field)


def scoped_filter(
    query: Any,
    model: Any,
    user: Any,
    *,
    org_field: str = "organization_id",
) -> Any:
    """对既有查询追加数据域过滤（服务层统一入口）。

    与 :func:`scoped_query` 的差异：调用方已构建好带业务条件（如
    ``is_active``）的 Query，只需补上数据域隔离时使用本函数。
    """
    from app.core.data_permission import filter_by_data_scope

    return filter_by_data_scope(query, model, user, org_field=org_field)


def scoped_count(
    db: Session,
    model: Any,
    user: Any,
    *,
    org_field: str = "organization_id",
) -> int:
    """按数据域过滤后的记录计数（统计口径与列表口径强一致）。"""
    return scoped_query(db, model, user, org_field=org_field).count()
