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

# 无对应页面的模块，其能力只能以"模块级动作码"存在（UI 不渲染，接口可判）。
# 键 = write_route_map 的 module key；值为附加动作（基础 read/write/delete 自动补齐）。
MODULE_ONLY_EXTRA_ACTIONS: dict[str, tuple[str, ...]] = {
    "users-orgs": ("manage_roles",),
    "roles": ("manage_roles",),
}

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
    # 跨模块操作类（通配展开到"所有具备该动作的码"）
    "data:view": (f"{WILDCARD}:read",),
    "data:create": (f"{WILDCARD}:write",),
    "data:edit": (f"{WILDCARD}:write",),
    "data:delete": (f"{WILDCARD}:delete",),
    "data:export": (f"{WILDCARD}:read",),
    "data:import": (f"{WILDCARD}:write",),
    "approve:view": (f"{WILDCARD}:read",),
    "approve:submit": (f"{WILDCARD}:write",),
    "approve:process": (f"{WILDCARD}:write",),
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


# 单数前缀来源：前端 `PermissionTreePanel.vue` 的 MODULE_DEFINITIONS 就写这几个
# （它把 `village:read` 写进 rbac_user_permissions）。只为这些**已知**单数建别名，
# 不用"去掉末尾 s"的朴素规则 —— 那会把 effectiveness 切成 effectivenes、
# 把 work-analysis 切成 work-analysi，产生一堆无意义别名。
KNOWN_SINGULAR_PREFIXES: tuple[str, ...] = (
    "user", "village", "project", "fund", "policy", "school",
    "org", "analytics", "audit", "backup", "system",
)

# 不规则复数（不能靠 +s 推导）。当前只有 policy → policies。
IRREGULAR_PLURALS: dict[str, str] = {"policy": "policies"}


def _build_prefix_alias(page_keys: Iterable[str]) -> dict[str, str]:
    """单数前缀 → 复数页面 key（只针对已知单数，且目标必须真实存在）。

    例：`village` → `villages`、`project` → `projects`、`policy` → `policies`；
    `fund` 没有对应页面（资金页是 `funds-admin` / `funds-user`）→ 不建别名，
    这类码继续按模块级处理。
    """
    keys = set(page_keys)
    alias: dict[str, str] = {}
    for singular in KNOWN_SINGULAR_PREFIXES:
        plural = IRREGULAR_PLURALS.get(singular, f"{singular}s")
        if plural in keys and singular not in keys:
            alias[singular] = plural
    return alias


def build_catalog() -> ActionCatalog:
    """按当前菜单定义与写路由映射构建目录（纯计算）。"""
    from app.api.v1.menus import MENU_DEFINITIONS
    from app.core.write_route_map import MODULE_RULES

    entries = _iter_entries(MENU_DEFINITIONS)
    page_keys = [e["key"] for e in entries if e.get("kind") == "page" and e.get("key")]
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
        prefix_alias=_build_prefix_alias(page_keys),
        legacy_alias=dict(LEGACY_ACTION_ALIAS),
    )


@lru_cache(maxsize=1)
def get_catalog() -> ActionCatalog:
    """进程内单例（菜单定义在运行期不变，构建一次即可）。"""
    return build_catalog()


def reset_catalog_cache() -> None:
    """清空缓存（测试隔离 / 热更新菜单定义后调用）。"""
    get_catalog.cache_clear()
