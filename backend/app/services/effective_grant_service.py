"""单位授权矩阵解析（R33）—— 后端唯一裁决点。

## 语义

下级单位没有超级管理员、完全离线，授权由上级生成授权包下发、下级导入后只读执行。
授权以**单位**为粒度（`org_grants`），单位内用户共享；个例差异仍走
`users.allowed_menus`（优先级最高，本模块不处理，由 `menus.py` 先行判断）。

## 合并规则

从用户所属单位**向上**遍历组织树，**层级越深越优先**：

    省厅 grants(projects=edit) → 市局 grants(projects=view) → 县局无该键
    ⇒ 市局用户看到 view，省厅用户看到 edit，县局用户继承市局的 view

- `inherit_from_parent=False` 的单位**切断**向上继承（独立授权）。
- 遍历带环检测，防止脏数据（parent_id 成环）导致死循环。
- 同一键若最深一层写 `none`，结果即 `none` —— deny 不会被更浅层的 grant 翻回来。

## 未授权 = legacy

单位 `grant_version == 0` 且无任何 `org_grants` 记录时，`GrantMatrix.active` 为 False，
调用方（菜单裁剪 / 写接口守卫）**必须回落到既有逻辑**，从而保证升级不改变存量行为。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.permission_utils import is_superuser
from app.models.organization import Organization
from app.models.org_grant import VALID_GRANT_LEVELS, OrgGrant

logger = logging.getLogger(__name__)

# 可见级别（不含 none）
VISIBLE_LEVELS = frozenset({"view", "edit"})
EDIT_LEVEL = "edit"

# ── 进程内缓存 ──────────────────────────────────────────────
# key = (organization_id, grant_version)。单位授权变更时必须递增 grant_version，
# 否则会命中旧缓存。上限触顶即整体清空（授权矩阵是小对象，清空成本可接受，
# 避免引入额外的 LRU 依赖）。
_CACHE: Dict[tuple, Dict[str, str]] = {}
_CACHE_LIMIT = 512


def clear_cache() -> None:
    """清空授权缓存（导入授权包 / 单元测试隔离用）。"""
    _CACHE.clear()


def _cached_org_grants(db: Session, org: Organization) -> Dict[str, str]:
    """读某单位自身的授权矩阵（带缓存）。"""
    key = (org.id, org.grant_version or 0)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    rows = db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).all()
    levels = {
        row.module_key: row.level
        for row in rows
        if row.level in VALID_GRANT_LEVELS
    }
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.clear()
    _CACHE[key] = levels
    return levels


def _org_chain(db: Session, org: Organization) -> list:
    """自身 → 上级 → … 直到根；`inherit_from_parent=False` 处截断。

    带 visited 集合防御 parent_id 成环（脏数据下不至于死循环）。
    """
    chain = []
    visited = set()
    current: Optional[Organization] = org
    while current is not None and current.id not in visited:
        visited.add(current.id)
        chain.append(current)
        if not current.inherit_from_parent:
            break
        parent_id = current.parent_id
        if not parent_id:
            break
        parent = db.query(Organization).filter(Organization.id == parent_id).first()
        # 同上：Mock 会话 / 脏数据返回非 ORM 实例时终止向上遍历
        if not isinstance(parent, Organization):
            break
        current = parent
    return chain


@dataclass(frozen=True)
class GrantMatrix:
    """解析结果。

    `active=False` 表示该单位尚未下发授权 → 调用方必须回落 legacy 逻辑。
    """

    active: bool
    levels: Dict[str, str] = field(default_factory=dict)

    def level(self, module_key: str) -> str:
        """取某模块的授权级别；未声明即 `none`（fail-closed）。"""
        return self.levels.get(module_key, "none")

    def can_view(self, module_key: str) -> bool:
        """可不可见（菜单下发 / 路由放行）。未激活时恒 False，由调用方自行回落。"""
        return self.active and self.level(module_key) in VISIBLE_LEVELS

    def can_edit(self, module_key: str) -> bool:
        """可不可写（写接口守卫）。未激活时恒 False，由调用方自行回落。"""
        return self.active and self.level(module_key) == EDIT_LEVEL

    def visible_keys(self) -> set:
        """可见模块集合（供菜单裁剪）。"""
        return {k for k, v in self.levels.items() if v in VISIBLE_LEVELS}


INACTIVE = GrantMatrix(active=False)


def get_grant_matrix(db: Session, user) -> GrantMatrix:
    """解析用户所属单位的有效授权矩阵。

    - 超级管理员：返回 inactive —— 超管本就豁免裁剪，由调用方按 `is_superuser` 放行，
      不在此伪造"全量授权"（否则写接口守卫会误以为超管受限于矩阵）。
    - 未绑定单位 / 单位未下发授权：inactive（legacy）。
    """
    if is_superuser(user):
        return INACTIVE

    org_id = getattr(user, "organization_id", None)
    # 防御：仅接受真实 int（Mock 用户 / 脏数据直接视为未授权 → 回落 legacy）。
    # 与 `menus._get_user_bound_pack` 同一风格；否则 Mock 会话下
    # `db.query(...).first()` 返回 MagicMock（truthy）会被误判成"单位已授权"。
    if not isinstance(org_id, int) or isinstance(org_id, bool) or org_id <= 0:
        return INACTIVE

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not isinstance(org, Organization):
        return INACTIVE

    chain = _org_chain(db, org)
    merged: Dict[str, str] = {}
    # 由根到叶 update：越深越后写，天然实现"深者优先"
    for node in reversed(chain):
        merged.update(_cached_org_grants(db, node))

    active = bool(merged) or bool(getattr(org, "grant_version", 0) or 0)
    if not active:
        return INACTIVE
    return GrantMatrix(active=True, levels=merged)


def module_keys_of(grants: Dict[str, str]) -> set:
    """从授权字典取可见 key 集合（便捷函数，供 API 层拼装响应用）。"""
    return {k for k, v in grants.items() if v in VISIBLE_LEVELS}
