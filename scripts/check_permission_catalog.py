# -*- coding: utf-8 -*-
"""动作权限目录门禁（统一权限管理方案 v1.2 §7 第 1 步）。

## 守什么

方案的三级收窄（页面 ⊃ 模块 ⊃ 动作）依赖"动作目录"与"菜单定义"始终对齐。
这两者一旦漂移，勾选界面就会勾到不存在的页面、或声明的动作码永远没人能拿到，
而**运行期不会报错**——只是按钮不出现、权限勾了不生效。这类问题人眼极难发现，
必须靠门禁。

## 断言的 10 条

1. 目录能正常构建（菜单定义 / 写路由映射没有结构性错误）；
2. 每个 `kind == "page"` 的菜单条目都有非空动作集；
3. 动作只允许 `ACTION_ENUM` 里的四个（前端 `modulePermissions` 只认这四个，
   用其它后缀会被推导成 `view=false, edit=false` 进而被 v-permission 隐藏）；
4. 目录里的码不含 `*`（通配只允许出现在别名表里，落库即后门）；
5. `PERMISSION_OPTIONS` 的每一条都在 `LEGACY_ACTION_ALIAS` 里（否则切换后该码 403）；
6. 每条 legacy 别名的目标都真实存在（含 `*:<action>` 展开后非空）——防悬空映射；
7. 单数前缀别名的目标必须是真实页面 key；
8. 模块级动作与页面级动作不重叠（重叠会让同一码有两个来源，判定口径不清）；
9. 前端 `PermissionTreePanel` 的 11 个单数前缀必须仍可解析；
10. `data:*` / `approve:*` 别名不得覆盖敏感模块，且非 legacy 页面必须有 path。

## 用法

    cd backend && python ../scripts/check_permission_catalog.py
    cd backend && python ../scripts/check_permission_catalog.py --json
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("SECRET_KEY", "permission-catalog-gate-secret-32!!")
os.environ.setdefault("ENVIRONMENT", "test")

sys.path.insert(0, ".")

from app.core.permission_catalog import (  # noqa: E402
    ACTION_ENUM,
    DATA_ALIAS_KEYS,
    SENSITIVE_MODULE_KEYS,
    WILDCARD,
    get_catalog,
)


def _permission_option_codes() -> list[str]:
    """读 `PERMISSION_OPTIONS` 的全部 code（单一来源，避免在这里抄一份）。"""
    from app.api.v1.auth.users import PERMISSION_OPTIONS

    return [str(item.get("code")) for item in PERMISSION_OPTIONS if item.get("code")]


def check() -> list[str]:  # noqa: C901 - 10 条断言按方案顺序展开，拆散后更难对照
    """返回问题列表（空 = 通过）。"""
    problems: list[str] = []

    try:
        catalog = get_catalog()
    except Exception as exc:  # noqa: BLE001 - 构建失败本身就是最严重的问题
        return [f"动作目录构建失败: {exc}"]

    # 1. 页面必须有动作
    empty_pages = [k for k, acts in catalog.page_actions.items() if not acts]
    if empty_pages:
        problems.append("以下页面未声明任何动作: " + ", ".join(sorted(empty_pages)))

    # 2. 动作必须在枚举内
    bad_actions = sorted(
        {
            action
            for table in (catalog.page_actions, catalog.module_actions)
            for actions in table.values()
            for action in actions
            if action not in ACTION_ENUM
        }
    )
    if bad_actions:
        problems.append(
            "存在枚举外的动作（前端无法推导，会被 fail-closed 隐藏）: "
            + ", ".join(bad_actions)
        )

    # 3. 目录内不得出现通配符
    wildcard_codes = sorted(c for c in catalog.all_codes if WILDCARD in c)
    if wildcard_codes:
        problems.append("目录内出现通配符码（会变成后门）: " + ", ".join(wildcard_codes[:5]))

    # 4. PERMISSION_OPTIONS 必须被别名表全覆盖
    option_codes = _permission_option_codes()
    uncovered = [c for c in option_codes if c not in catalog.legacy_alias]
    if uncovered:
        problems.append(
            "以下 PERMISSION_OPTIONS 码没有 legacy 别名（切换后会 403）: "
            + ", ".join(uncovered)
        )

    # 5. 别名目标必须存在
    dangling: list[str] = []
    for code, targets in sorted(catalog.legacy_alias.items()):
        for target in targets:
            prefix, _sep, action = target.partition(":")
            if prefix == WILDCARD:
                if not any(c.endswith(f":{action}") for c in catalog.all_codes):
                    dangling.append(f"{code} → {target}")
            elif prefix == "@data":
                if not any(
                    c.endswith(f":{action}") and c.split(":", 1)[0] in DATA_ALIAS_KEYS
                    for c in catalog.all_codes
                ):
                    dangling.append(f"{code} → {target}")
            elif target not in catalog.all_codes:
                dangling.append(f"{code} → {target}")
    if dangling:
        problems.append("别名指向不存在的码: " + ", ".join(dangling[:8]))

    # 6. 前缀别名目标必须是页面或模块级 key（user/org/fund 的目标是模块级）
    valid_targets = set(catalog.page_actions) | set(catalog.module_actions)
    bad_prefix = [
        f"{s} → {p}" for s, p in sorted(catalog.prefix_alias.items()) if p not in valid_targets
    ]
    if bad_prefix:
        problems.append("单数前缀别名指向不存在的页面/模块 key: " + ", ".join(bad_prefix))

    # 7. 前端 PermissionTreePanel 的 11 个单数前缀必须仍可解析，否则现有勾选
    # 写出的 village:read / fund:write 会变成未知码，切换后静默降权。
    frontend_prefixes = (
        "user", "village", "project", "fund", "policy", "school",
        "org", "analytics", "audit", "backup", "system",
    )
    unresolved = [
        p for p in frontend_prefixes
        if not catalog.is_known(f"{p}:read")
    ]
    if unresolved:
        problems.append("前端权限面板单数前缀无法解析: " + ", ".join(unresolved))

    # 8. data/approve 粗粒度别名不得覆盖敏感模块（防止 data:create 变成系统管理员）
    for alias_name in ("data:view", "data:create", "data:edit", "data:delete",
                       "approve:view", "approve:submit", "approve:process"):
        leaked = sorted(
            code for code in catalog.expand([alias_name])
            if code.split(":", 1)[0] in SENSITIVE_MODULE_KEYS
        )
        if leaked:
            problems.append(f"{alias_name} 覆盖敏感模块: " + ", ".join(leaked[:8]))

    # 9. 页面级与模块级不得重叠
    overlap = sorted(set(catalog.page_actions) & set(catalog.module_actions))
    if overlap:
        problems.append("页面级与模块级动作重叠: " + ", ".join(overlap[:8]))

    # 10. 菜单结构：非 legacy 的 page/console 必须有 path；legacy 不得被当成
    # 可导航页面（这正是 v1.2 把 15 个无 path 历史 key 算成页面的根因）。
    from app.api.v1.menus import MENU_DEFINITIONS
    from app.core.permission_catalog import _iter_entries

    for entry in _iter_entries(MENU_DEFINITIONS):
        kind = entry.get("kind")
        if kind not in ("page", "console"):
            continue
        key = entry.get("key") or "<unknown>"
        if not entry.get("legacy") and not entry.get("path"):
            problems.append(f"非 legacy 页面缺少 path: {key}")
        if entry.get("legacy") and entry.get("path"):
            problems.append(f"legacy 页面不应有导航 path: {key}")

    return problems


def main() -> int:
    problems = check()

    if "--json" in sys.argv:
        catalog = get_catalog()
        print(
            json.dumps(
                {
                    "pages": len(catalog.page_actions),
                    "modules": len(catalog.module_actions),
                    "codes": len(catalog.all_codes),
                    "legacy_aliases": len(catalog.legacy_alias),
                    "prefix_aliases": len(catalog.prefix_alias),
                    "problems": problems,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if problems else 0

    catalog = get_catalog()
    print(
        f"动作目录: {len(catalog.page_actions)} 个页面 / {len(catalog.module_actions)} 个模块级 / "
        f"{len(catalog.all_codes)} 个动作码 / {len(catalog.legacy_alias)} 条 legacy 别名"
    )
    if problems:
        print("\n[FAIL] 动作目录与菜单定义不一致：")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("[OK] 动作目录与菜单定义一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
