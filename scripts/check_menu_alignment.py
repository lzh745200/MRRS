#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前后端菜单对齐检查 (CI 门禁)

规则:
1. 前端 menu-config.ts 中的每个菜单 key 必须存在于后端 MENU_DEFINITIONS
   (已知废弃 key 例外——这些页面路由已移除,配置残留待清理)
2. 前端 menu-config.ts 中的每个 path 必须存在于前端 router/index.ts
3. 后端 MENU_DEFINITIONS 中的每个 path 应在前端路由中存在

用法: python scripts/check_menu_alignment.py
退出码: 0=通过, 1=存在不一致
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_MENUS = ROOT / "backend" / "app" / "api" / "v1" / "menus.py"
FRONTEND_MENU_CONFIG = ROOT / "frontend" / "src" / "config" / "menu-config.ts"
FRONTEND_ROUTER = ROOT / "frontend" / "src" / "router" / "index.ts"

# 历史豁免清单已清零: 此前豁免的废弃键(validation-rules / system-overview /
# admin-dashboard / system-security 等)现已全部收录进后端 MENU_DEFINITIONS。
# 新增前端键而不同步后端将直接 FAIL,不再提供豁免通道。
DEPRECATED_KEYS: set[str] = set()

# 规则 3 的后端 path 豁免清单(键 -> 豁免理由)。
# 除下列条目外,后端 MENU_DEFINITIONS 的 path 必须能解析到前端已注册路由
# (含 alias 与可选参数段),否则本门禁 FAIL —— 历史事故: users-orgs 下发的
# /system/users-orgs 前端无此路由,管理员面板照抄该 path 后用户管理页 404。
# 2026-09-14：原豁免的 health / task-package-admin 两项已从 MENU_DEFINITIONS 移除
# （均为无 UI 出口的死项），豁免清单清零 —— 后端菜单 path 现为**零豁免**全量校验。
BACKEND_PATH_EXEMPT: dict[str, str] = {}


def extract_backend_keys(path: Path) -> set:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'"key":\s*"([a-z0-9-]+)"', text))


def extract_backend_items(path: Path) -> list:
    """提取后端 MENU_DEFINITIONS 中所有带 path 的 (key, path)。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    items = []
    for m in re.finditer(r'"key":\s*"([a-z0-9-]+)"(.*?)(?=\n\s*\},|\n\s*\],)', text, re.S):
        pm = re.search(r'"path":\s*"([^"]*)"', m.group(2))
        if pm:
            items.append((m.group(1), pm.group(1)))
    return items


def _route_regex(route: str):
    """把前端路由 path 编译为匹配正则: :id -> 一段, :id? -> 可选段。"""
    route = route.rstrip("/")
    out = ""
    for seg in route.split("/"):
        if not seg:
            continue
        if seg.startswith(":"):
            out += "(?:/[^/]+)?" if seg[1:].endswith("?") else "/[^/]+"
        else:
            out += "/" + re.escape(seg)
    return re.compile("^" + (out or "/") + "/?$")


def extract_router_matchers(text: str) -> list:
    """前端已注册路由(含 alias)的匹配器;排除 404 通配路由。"""
    raw = set(re.findall(r"\bpath:\s*['\"]([^'\"]+)['\"]", text))
    raw |= set(re.findall(r"\balias:\s*['\"]([^'\"]+)['\"]", text))
    matchers = []
    for r in raw:
        if not r.startswith("/") or "(" in r or "*" in r:
            continue
        matchers.append(_route_regex(r))
    return matchers


def extract_frontend_items(text: str):
    # 提取所有 { key: 'k', ..., path: '/p' } 条目
    items = []
    for m in re.finditer(
        r"key:\s*['\"]([a-z0-9-]+)['\"]\s*,\s*label:\s*['\"][^'\"]*['\"]\s*,\s*path:\s*['\"](/[^'\"]+)['\"]",
        text,
    ):
        items.append((m.group(1), m.group(2)))
    return items


def extract_router_paths(text: str) -> set:
    return set(re.findall(r"path:\s*['\"](/[a-zA-Z0-9/:_-]+)['\"]", text))


def main() -> int:
    errors = []
    backend_keys = extract_backend_keys(BACKEND_MENUS)
    menu_text = FRONTEND_MENU_CONFIG.read_text(encoding="utf-8", errors="replace")
    router_text = FRONTEND_ROUTER.read_text(encoding="utf-8", errors="replace")
    frontend_items = extract_frontend_items(menu_text)
    router_paths = extract_router_paths(router_text)

    # 归一化路由(去动态段)
    normalized_router = set()
    for rp in router_paths:
        seg = [s for s in rp.split("/") if s and not s.startswith(":")]
        normalized_router.add("/" + "/".join(seg))

    for key, path in frontend_items:
        if key in DEPRECATED_KEYS:
            continue
        if key not in backend_keys:
            errors.append(f"前端菜单 key '{key}' 在后端 MENU_DEFINITIONS 中不存在")
        base = "/" + "/".join(s for s in path.split("/") if s)
        if base not in router_paths and base not in normalized_router:
            if not any(base == r or base.startswith(r + "/") for r in router_paths):
                errors.append(f"前端菜单 '{key}' 的 path '{path}' 无对应路由")

    # ── 规则 3: 后端 MENU_DEFINITIONS 的 path 必须解析到前端已注册路由(含 alias/可选参数) ──
    # 此前该规则只写在文档字符串里、代码从未实现,导致 users-orgs 的
    # /system/users-orgs 长期漂移并在管理员面板触发 404(2026-09-14 补齐)。
    router_matchers = extract_router_matchers(router_text)
    backend_items = extract_backend_items(BACKEND_MENUS)
    checked_paths = 0
    for key, bpath in backend_items:
        if not bpath or "{" in bpath or key in BACKEND_PATH_EXEMPT:
            continue
        checked_paths += 1
        if not any(m.match(bpath) for m in router_matchers):
            errors.append(f"后端菜单 '{key}' 的 path '{bpath}' 在前端路由中不存在(点击将 404)")

    # 反向漂移仅提示不阻塞: 后端可为侧边栏预留前端尚未使用的键
    backend_only = backend_keys - {k for k, _ in frontend_items} - DEPRECATED_KEYS
    if backend_only:
        print("[INFO] 仅存在于后端 MENU_DEFINITIONS 的键(预留/遗留, 不阻塞):")
        for k in sorted(backend_only):
            print("  -", k)

    if errors:
        print("[FAIL] 前后端菜单不一致:")
        for e in errors:
            print("  -", e)
        return 1

    if BACKEND_PATH_EXEMPT:
        print("[INFO] 后端 path 豁免 %d 项:" % len(BACKEND_PATH_EXEMPT))
        for k in sorted(BACKEND_PATH_EXEMPT):
            print("  -", k, "->", BACKEND_PATH_EXEMPT[k])
    print("[OK] 前后端菜单对齐检查通过 (backend=%d keys, frontend=%d items, 后端 path 校验 %d 项)"
          % (len(backend_keys), len(frontend_items), checked_paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
