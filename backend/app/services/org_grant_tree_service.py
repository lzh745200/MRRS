# -*- coding: utf-8 -*-
"""组织策略树的查询与序列化（R48）。

从 ``api/v1/org_grants.py`` 抽出，原因有二：

1. 路由文件只做鉴权/事务/响应封装，树构建是纯查询逻辑（分层更清晰）；
2. 裸 dict 返回门禁（``scan_bare_returns``）只应约束**端点响应**，
   这类内部数据结构不该被当成 envelope 违规。

本模块只返回**显式**矩阵；继承后的有效值由
``effective_grant_service.get_grant_matrix_for_org`` 按选中节点单独计算。
"""

from app.core.data_permission import _get_org_subtree
from app.models.org_grant import OrgGrant
from app.models.organization import Organization


def matrix_of(db, org_id: int) -> dict:
    """该单位自身的显式授权矩阵（未含继承）。"""
    rows = db.query(OrgGrant).filter(OrgGrant.organization_id == org_id).all()
    return {row.module_key: row.level for row in rows}


def subtree_orgs(db, root_id: int) -> list:
    """按组织树顺序返回 root 及其全部下级（深度/环保护由 `_get_org_subtree` 提供）。"""
    org_ids, _names = _get_org_subtree(db, root_id)
    rows = (
        db.query(Organization)
        .filter(Organization.id.in_(org_ids))
        .order_by(Organization.sort_order, Organization.id)
        .all()
    )
    by_id = {org.id: org for org in rows}
    return [by_id[org_id] for org_id in org_ids if org_id in by_id]


def parent_codes(orgs_by_id: dict, org: Organization) -> list:
    """根 → 上级的单位编码链（仅作包内溯源元数据，不参与权限计算）。"""
    codes = []
    seen = set()
    current = orgs_by_id.get(org.parent_id) if org.parent_id else None
    while current is not None and current.id not in seen:
        seen.add(current.id)
        # 调用方已保证子树内每个单位都有 code，这里只做溯源，不再判空。
        codes.append(current.code)
        current = orgs_by_id.get(current.parent_id) if current.parent_id else None
    return list(reversed(codes))


def tree_node(db, org: Organization, children_by_parent: dict) -> dict:
    """组织策略树的单个节点（显式矩阵 + 元信息 + 子节点）。"""
    org_id = org.id
    assert org_id is not None  # 已落库组织必有主键；显式收窄供 mypy 使用
    return {
        "id": org_id,
        "name": org.name,
        "code": org.code,
        "parent_id": org.parent_id,
        "level": org.level,
        "grant_version": org.grant_version or 0,
        "grant_source": org.grant_source,
        "signed": bool(org.grant_signature),
        "inherit_from_parent": bool(org.inherit_from_parent),
        "grants": matrix_of(db, org_id),
        "children": [
            tree_node(db, child, children_by_parent)
            for child in children_by_parent.get(org_id, [])
        ],
    }
