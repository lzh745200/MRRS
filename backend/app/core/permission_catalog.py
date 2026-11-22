# -*- coding: utf-8 -*-
"""动作权限目录（统一权限管理方案 v1.2 §1.2 / §1.3 的落地实现）。

## 这个模块解决什么问题

方案要求"页面级 ⊃ 模块级 ⊃ 动作级"三级收窄，但系统里动作码有**三个来源、三种写法**：

1. `PERMISSION_OPTIONS`（`app/api/v1/auth/users.py`）：17 条**单数前缀 + 粗粒度**，
   如 `village:manage`、`data:create`；
2. `PermissionTreePanel.vue`（前端权限分配面板）：按模块勾选，写 **单数**
   `village:read` / `village:write` 到 `rbac_user_permissions`；
3. `write_route_map.MODULE_RULES`：模块 key 与 `MENU_DEFINITIONS` 的 **page key 同源（复数）**，
   如 `villages`、`projects`。

而 `rbac_role_permissions.permission` / `rbac_user_permissions.permission` 是
**自由字符串**（`String(50)`，非外键），所以库里可能同时存在上述三种写法的历史数据。
若不归一，新裁决器会把 `village:read` 当成未知码 → 存量用户被静默降权。

## 本模块的职责（只做纯计算，不碰数据库）

- 从 `MENU_DEFINITIONS` 派生 **页面级动作目录**（`PAGE_ACTIONS`）；
- 为"没有对应页面的后端模块"派生 **模块级动作目录**（`MODULE_ACTIONS`），
  保证 `system/user/org/role` 这类能力仍有可判定的码；
- 提供 **前缀归一**（单数 → 复数，如 `village` → `villages`）；
- 提供 **legacy 别名展开**（17 条粗粒度码 → 具体动作码，支持 `*` 通配）；
- 对外只暴露 `get_catalog()` 与 `ActionCatalog` 的三个方法，避免调用方各自拼装。

## 为什么不用模块级常量

`MENU_DEFINITIONS` 由 `app/api/v1/menus.py` 定义，而 menus 属于 API 层。本模块放在
`app/core/`，若在 import 期就 `from app.api.v1.menus import ...`，会让 core 依赖 api
（分层倒置），也埋下循环导入的隐患。故改为 **首次调用时惰性构建 + 缓存**。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

# 动作枚举：只允许这四个。
# 依据（v1.2 §1.2）：前端 `authStore.modulePermissions` 只识别
# `read` → view、`write|delete|manage_roles` → edit；用其它后缀会被推导成
# `view=false, edit=false`，进而被 v-permission fail-closed 隐藏。
ACTION_ENUM: tuple[str, ...] = ("read", "write", "delete", "manage_roles")

# 通配前缀：仅用于 legacy 别名展开，**不得**出现在任何落库的码里。
WILDCARD = "*"

# 可导航且承载动作的菜单类型：page 与 console 都有 path、都能挂按钮/接口；
# kind=tab 是父页内部的子视图，不单独作为动作页面；legacy 条目无 path，只是历史
# 权限 key，不能当成“页面”渲进勾选界面（否则勾了也没有导航入口）。
NAVIGABLE_KINDS: tuple[str, ...] = ("page", "console")

# 无对应页面的模块，其能力只能以"模块级动作码"存在（UI 不渲染，接口可判）。
# 键 = write_route_map 的 module key；值为附加动作（基础 read/write/delete 自动补齐）。
MODULE_ONLY_EXTRA_ACTIONS: dict[str, tuple[str, ...]] = {
    "users-orgs": ("manage_roles",),
    "roles": ("manage_roles",),
}

# legacy 的 `data:*` / `approve:*` 是跨模块粗粒度码。这里用**数据域白名单**展开，
# 绝不能用 `*` 扫全部目录：`data:create` 一旦展开到 system/roles/users-orgs，
# 等于把系统管理写权限送给普通数据录入员。新增业务页时必须显式归入此表，
# 门禁第 9 条会检查“敏感模块不得被 data/approve 别名覆盖”。
DATA_ALIAS_KEYS: frozenset[str] = frozenset({
    # 页面（审批与报表模板/导出不在此列：前者只走 approve:*，后者由 data:export 精确授予）
    "analytics-dashboard", "analytics-map", "batch-operations", "bigscreen",
    "comprehensive-entry", "consumption", "data-overview", "data-package",
    "data-package-receive", "data-package-report", "data-package-version",
    "data-sync-export", "data-sync-import", "data-verify", "donation",
    "effectiveness-evaluate", "effectiveness-rankings", "funds-admin",
    "funds-analysis", "funds-anomaly", "funds-budget", "funds-contract",
    "funds-lifecycle", "funds-report", "funds-settlement", "funds-transfer",
    "funds-user", "handover", "households", "media-library", "messages",
    "pairing", "policies", "projects", "reminder", "rural-works",
    "rural-works-list", "schools", "todos", "villages", "work-analysis",
    "work-calendar",
    # 纯后端模块（无独立导航页）
    "analytics", "batch-import", "checkin", "data", "data-tier",
    "effectiveness", "funds", "households", "map-tiles", "sentiment",
})

# 明确的敏感模块：任何 `data:*` / `approve:*` 通配都不得覆盖它们。
SENSITIVE_MODULE_KEYS: frozenset[str] = frozenset({
    "system", "system-permission-packs", "system-console-about",
    "system-console-ops", "system-console-org", "system-console-security",
    "system-console-settings", "system-console-storage", "users-orgs",
    "organizations", "roles", "menus", "audit", "backup", "cache",
    "config-package", "control-package", "encryption", "health-check",
    "machine-code", "monitor", "pass-code", "secrets", "validation-rules",
    "zero-trust",
})

# 17 条 legacy 码 → 具体动作码（v1.2 §1.2 的定稿表）。
# 目标既可以是页面级（`villages:read`），也可以是模块级（`users-orgs:read`）——
# 因为 `user/org/role` 三个能力在菜单里没有独立页面。
LEGACY_ACTION_ALIAS: dict[str, tuple[str, ...]] = {
    # 系统类
    "system:manage": ("system:read", "system:write", "system:delete"),
    "user:manage": ("users-orgs:read", "users-orgs:write", "users-orgs:delete"),
    "org:manage": ("organizations:read", "organizations:write", "organizations:delete"),
    "role:manage": ("roles:read", "roles:write", "roles:delete"),
    # 数据类（单数前缀 → 复数页面）
    "village:manage": ("villages:read", "villages:write", "villages:delete"),
    "project:manage": ("projects:read", "projects:write", "projects:delete"),
    "fund:manage": ("funds:read", "funds:write", "funds:delete"),
    "report:manage": (
        "report-templates:read", "report-templates:write", "report-templates:delete",
        "report-export:read", "report-export:write", "report-export:delete",
    ),
    # 跨模块操作类：只展开到 DATA_ALIAS_KEYS，绝不扫 system/roles/users-orgs。
    "data:view": ("@data:read", "report-export:read", "report-templates:read"),
    "data:create": ("@data:write",),
    "data:edit": ("@data:write",),
    "data:delete": ("@data:delete",),
    # 导出是副作用写操作，但不能因此获得数据编辑权：只给报表导出页的 write。
    "data:export": ("report-export:write",),
    "data:import": ("batch-import:write", "data-sync-import:write", "data-package:write"),
    "approve:view": ("approval:read",),
    "approve:submit": ("approval:write",),
    "approve:process": ("approval:write",),
}


@dataclass(frozen=True)
class ActionCatalog:
    """动作目录快照（不可变，构建一次全程复用）。"""

    page_actions: dict[str, tuple[str, ...]]
    module_actions: dict[str, tuple[str, ...]]
    all_codes: frozenset[str]
    prefix_alias: dict[str, str]
    legacy_alias: dict[str, tuple[str, ...]]

    # ── 归一与判定 ────────────────────────────────────────────

    def normalize(self, code: str) -> str:
        """把单数前缀归一到复数（`village:read` → `villages:read`）。

        已经是复数、或前缀不在别名表里的码**原样返回**（不做猜测性改写）。
        """
        prefix, sep, action = code.partition(":")
        if not sep:
            return code
        mapped = self.prefix_alias.get(prefix)
        return f"{mapped}:{action}" if mapped else code

    def is_known(self, code: str) -> bool:
        """是否为目录内的合法码（含 legacy 码；通配符不算）。"""
        if code in self.legacy_alias:
            return True
        return self.normalize(code) in self.all_codes

    def expand(self, codes: Iterable[str]) -> set[str]:
        """把一组码（可能含单数前缀 / legacy 粗粒度 / 通配）展开成具体动作码集合。

        规则：
        1. 每个码先做前缀归一；
        2. 若命中 legacy 别名，把别名目标再逐个展开（`*:read` → 所有 read 码）；
        3. 未识别的码**保留原样**——由调用方（守卫）决定按"无权限"处理，
           这里不静默丢弃，否则排障时看不到"配置里写了什么"。
        """
        out: set[str] = set()
        for raw in codes:
            if not isinstance(raw, str) or not raw:
                continue
            code = self.normalize(raw)
            alias = self.legacy_alias.get(raw) or self.legacy_alias.get(code)
            if alias:
                for target in alias:
                    out |= self._expand_target(target)
                continue
            out.add(code)
        return out

    def _expand_target(self, target: str) -> set[str]:
        """展开单个别名目标，支持 `*:<action>` 通配。"""
        prefix, sep, action = target.partition(":")
        if sep and prefix == "@data":
            return {
                c for c in self.all_codes
                if c.endswith(f":{action}") and c.split(":", 1)[0] in DATA_ALIAS_KEYS
            }
        if sep and prefix == WILDCARD:
            return {c for c in self.all_codes if c.endswith(f":{action}")}
        return {target}

    # ── 只读视图（供门禁 / UI 使用）────────────────────────────

    def page_keys(self) -> frozenset[str]:
        return frozenset(self.page_actions)

    def actions_of_page(self, page_key: str) -> tuple[str, ...]:
        return self.page_actions.get(page_key, ())


def _iter_entries(definitions: Sequence[dict]) -> list[dict]:
    """扁平化菜单定义（含 children 与 tabs），保持声明顺序。"""
    out: list[dict] = []
    stack = list(reversed(list(definitions)))
    while stack:
        entry = stack.pop()
        if not isinstance(entry, dict):
            continue
        out.append(entry)
        # children 先入后出，保证顺序与文档一致
        stack.extend(reversed([c for c in entry.get("children") or [] if isinstance(c, dict)]))
        for tab in entry.get("tabs") or []:
            if isinstance(tab, dict):
                out.append({"key": tab.get("key"), "kind": "tab"})
    return out


def _build_page_actions(page_keys: Sequence[str], write_modules: set[str]) -> dict[str, tuple[str, ...]]:
    """页面级动作：所有页面可 read；有写接口的页面再加 write/delete。"""
    out: dict[str, tuple[str, ...]] = {}
    for key in page_keys:
        actions = ["read"]
        if key in write_modules:
            actions.extend(("write", "delete"))
        out[key] = tuple(actions)
    return out


def _build_module_actions(write_modules: Iterable[str], page_keys: set[str]) -> dict[str, tuple[str, ...]]:
    """模块级动作：仅覆盖"没有对应页面"的写模块，避免与页面级重复。"""
    out: dict[str, tuple[str, ...]] = {}
    for module in sorted(write_modules):
        if module in page_keys:
            continue
        actions = ["read", "write", "delete"]
        actions.extend(MODULE_ONLY_EXTRA_ACTIONS.get(module, ()))
        out[module] = tuple(actions)
    return out


# 前端 `PermissionTreePanel.vue` 实际写出的单数前缀 → 目录目标。
# 不能按“去尾加 s”推导：user→users-orgs、org→organizations、fund→funds 都是不规则；
# 而 analytics/audit/backup/system 本身就是模块级 key。目标是 page 或 module 均可。
SINGULAR_TARGET: dict[str, str] = {
    "user": "users-orgs",
    "village": "villages",
    "project": "projects",
    "fund": "funds",
    "policy": "policies",
    "school": "schools",
    "org": "organizations",
    "analytics": "analytics",
    "audit": "audit",
    "backup": "backup",
    "system": "system",
}


def _build_prefix_alias(page_keys: Iterable[str], module_keys: Iterable[str]) -> dict[str, str]:
    """单数前缀 → 真实目录目标（页面或模块级）。

    目标不存在时不建别名（宁可让门禁报出未知码，也不把权限悄悄映射到错误模块）。
    单数本身已是目标时无需别名（`system:read` 原样就是合法模块级码）。
    """
    keys = set(page_keys) | set(module_keys)
    alias: dict[str, str] = {}
    for singular, target in SINGULAR_TARGET.items():
        if target in keys and singular not in keys and target != singular:
            alias[singular] = target
    return alias


def build_catalog() -> ActionCatalog:
    """按当前菜单定义与写路由映射构建目录（纯计算）。"""
    from app.api.v1.menus import MENU_DEFINITIONS
    from app.core.write_route_map import MODULE_RULES

    entries = _iter_entries(MENU_DEFINITIONS)
    # 只有“有导航路径且非 legacy”的 page/console 才是动作页面；不要把 15 个
    # legacy key 或无 path 的历史 key 当页面，也不要漏掉 6 个 system console 页。
    page_keys = [
        e["key"] for e in entries
        if e.get("kind") in NAVIGABLE_KINDS
        and e.get("path")
        and not e.get("legacy")
        and e.get("key")
    ]
    write_modules = {module for _prefix, module in MODULE_RULES}

    page_actions = _build_page_actions(page_keys, write_modules)
    module_actions = _build_module_actions(write_modules, set(page_keys))
    all_codes = frozenset(
        f"{key}:{action}"
        for table in (page_actions, module_actions)
        for key, actions in table.items()
        for action in actions
    )
    return ActionCatalog(
        page_actions=page_actions,
        module_actions=module_actions,
        all_codes=all_codes,
        prefix_alias=_build_prefix_alias(page_keys, module_actions),
        legacy_alias=dict(LEGACY_ACTION_ALIAS),
    )


@lru_cache(maxsize=1)
def get_catalog() -> ActionCatalog:
    """进程内单例（菜单定义在运行期不变，构建一次即可）。"""
    return build_catalog()


def reset_catalog_cache() -> None:
    """清空缓存（测试隔离 / 热更新菜单定义后调用）。"""
    get_catalog.cache_clear()
