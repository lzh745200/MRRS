# -*- coding: utf-8 -*-
"""有效权限裁决点（统一权限管理方案 §2.5 / §4.1 的运行时实现）。

## 定位

本模块把现有三层积木收敛成**一个只读解析器**：

1. RBAC 角色/直接权限 + `allowed_permissions` 白名单 + 机器码扣减
   （复用 `RBACService.get_user_permissions_with_restrictions`，不重写）；
2. 单位授权矩阵 `get_grant_matrix`（active 时作为模块级上限）；
3. 菜单可见性 `_get_user_accessible_menu_keys`（**直接复用**，不在本模块重写
   两条矩阵分支，避免 §2.5.1 那类“权限改了菜单没变”的漂移）；
4. 动作目录 `permission_catalog`（legacy 双读、单数前缀归一、模块级动作）。

## 重要边界

- 本模块目前**只提供解析结果**，没有接入任何路由/中间件；在完成
  `require_permission` 路由覆盖之前，不能把它当成已经生效的运行时守卫。
- `matrix.active=False` 时保持 legacy 语义：不做模块级裁剪，只做别名展开。
- `matrix.active=True` 时模块级是硬上限（**即使 levels 为空也必须裁剪**，
  否则“授权被清空但版本已启用”会退回 RBAC 全量，形成越权）：页面动作映射到
  `page_modules`；页面 `read` 跟随 L1 页面可见性保留；模块级 `read` 要求
  `view|edit`；`write/delete/manage_roles` 要求至少一个映射模块 `edit`；
  没有映射模块的只读页（如 dashboard）保留 `read`，不被误删。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from app.core.permission_catalog import ActionCatalog, get_catalog

# 进程内小缓存：键 = 用户 + `permissions_version` + 组织 + 单位授权版本。
# 只有用户对象**确实暴露** `permissions_version` 时才启用缓存 —— 该列要等方案
# 第 4 步落地，当前 `User` 没有它；若仍缓存，角色/直接权限变更不会改键，会读到
# 过期快照。不用 TTL：权限解析是小对象，显式版本失效比“等 60 秒”更符合现场预期。
_CACHE: Dict[tuple, "EffectivePermissions"] = {}
_CACHE_LIMIT = 512


def clear_cache() -> None:
    """清空缓存（权限变更 / 测试隔离）。"""
    _CACHE.clear()


@dataclass(frozen=True)
class EffectivePermissions:
    """一次解析的不可变快照。"""

    pages: frozenset[str]
    modules: Dict[str, str]
    actions: frozenset[str]
    denied: frozenset[str]
    version: str
    catalog: ActionCatalog = field(repr=False, compare=False)

    def has(self, code: str) -> bool:
        """动作码是否有效（含 legacy 展开；未知码 fail-closed）。"""
        normalized = self.catalog.normalize(code)
        if normalized in self.actions:
            return True
        aliases = self.catalog.legacy_alias.get(normalized) or self.catalog.legacy_alias.get(code)
        return bool(aliases and self.catalog.expand([code]) & self.actions)

    def can_view_page(self, page_key: str) -> bool:
        """页面是否可见（L1）。"""
        return page_key in self.pages

    def can_edit_page(self, page_key: str) -> bool:
        """页面是否可写（L2，仅 matrix active 时有意义）。"""
        modules = self.catalog.modules_of_page(page_key)
        if not modules:
            return False
        return any(self.modules.get(module) == "edit" for module in modules)


def _cache_key(user: Any, matrix_version: int) -> tuple:
    return (
        getattr(user, "id", None),
        getattr(user, "permissions_version", 0) or 0,
        getattr(user, "organization_id", None),
        matrix_version,
    )


def _module_levels(matrix: Any) -> Dict[str, str]:
    """矩阵 levels 的安全副本；inactive 时返回空（表示不做 L2 裁剪）。"""
    if not getattr(matrix, "active", False):
        return {}
    levels = getattr(matrix, "levels", {}) or {}
    return {str(k): str(v) for k, v in levels.items() if v in ("view", "edit", "none")}


def _page_modules(catalog: ActionCatalog, page_key: str) -> tuple[str, ...]:
    """页面显式映射的模块；无映射返回空（dashboard 等只读页）。"""
    return catalog.modules_of_page(page_key)


def _filter_by_modules(
    catalog: ActionCatalog,
    actions: Set[str],
    pages: Set[str],
    levels: Dict[str, str],
) -> Set[str]:
    """矩阵 active 时把动作收窄到模块级上限。

    - 有模块映射的页面：read 需 view/edit，write/delete/manage_roles 需 edit；
    - 无模块映射的只读页（dashboard 等）：保留 read；
    - 模块级动作（users-orgs:* 等）按其自身 level 判定；
    - 未知前缀不因矩阵存在而获得额外权限。
    """
    kept: Set[str] = set()
    for code in actions:
        prefix, _, action = code.partition(":")
        if not prefix or not action:
            continue
        mapped = _page_modules(catalog, prefix) if prefix in pages else (prefix,)
        if not mapped:
            # 没有模块映射的可见页（dashboard / bigscreen）只保留 read，
            # 不能因为矩阵没有这个 key 就把页面本身误删。
            if prefix in pages and action == "read":
                kept.add(code)
            continue
        if action == "read":
            # 页面可见性由 L1 决定；页面 read 不因矩阵缺该模块而被删。
            if prefix in pages or any(levels.get(m) in ("view", "edit") for m in mapped):
                kept.add(code)
        elif any(levels.get(m) == "edit" for m in mapped):
            kept.add(code)
    return kept


async def resolve(db: Session, user: Any) -> EffectivePermissions:
    """解析用户有效权限（不写库、不改变任何请求行为）。"""
    if user is None:
        return EffectivePermissions(
            pages=frozenset(), modules={}, actions=frozenset(), denied=frozenset(),
            version="0.0", catalog=get_catalog(),
        )

    from app.api.v1.menus import _get_user_accessible_menu_keys
    from app.services.effective_grant_service import get_grant_matrix
    from app.services.rbac_service import RBACService

    matrix_version = int(
        getattr(getattr(user, "organization", None), "grant_version", 0) or 0
    )
    cache_key = _cache_key(user, matrix_version)
    # 缓存键含 permissions_version，但该列尚未落地（方案第 4 步）。真实 User
    # 没有这个属性时禁用缓存：否则角色/直接权限变更不会改键，读到过期快照。
    cacheable = hasattr(user, "permissions_version")
    if cacheable:
        cached = _CACHE.get(cache_key)
        if cached is not None:
            return cached

    matrix = get_grant_matrix(db, user)
    matrix_active = bool(getattr(matrix, "active", False))
    levels = _module_levels(matrix)
    user_id = getattr(user, "id", 0)
    permissions, restricted = await RBACService().get_user_permissions_with_restrictions(
        str(user_id), db
    )
    # 复用上面已解析的矩阵，避免菜单解析内部再查一次（同一次请求两次 DB 读）。
    pages = set(_get_user_accessible_menu_keys(user, db, matrix=matrix) or ())

    catalog = get_catalog()
    actions = set(permissions) | catalog.expand(permissions)
    # active 是硬开关：active 但 levels 为空（授权被清空 / 账号包只激活版本）
    # 同样必须裁剪，否则会退回 RBAC 全量。
    if matrix_active:
        actions = _filter_by_modules(catalog, actions, pages, levels)

    version = f"{getattr(user, 'permissions_version', 0) or 0}.{matrix_version}"
    snapshot = EffectivePermissions(
        pages=frozenset(pages),
        modules=levels,
        actions=frozenset(actions),
        denied=frozenset(restricted or ()),
        version=version,
        catalog=catalog,
    )

    if cacheable:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.clear()
        _CACHE[cache_key] = snapshot
    return snapshot


def get_cached(db: Session, user: Any) -> Optional[EffectivePermissions]:
    """只查缓存（供请求级依赖使用；未命中返回 None，不回源）。"""
    org = getattr(user, "organization", None)
    key = _cache_key(user, int(getattr(org, "grant_version", 0) or 0))
    return _CACHE.get(key)
