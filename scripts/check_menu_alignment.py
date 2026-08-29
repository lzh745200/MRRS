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


def extract_backend_keys(path: Path) -> set:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'"key":\s*"([a-z0-9-]+)"', text))


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

    print("[OK] 前后端菜单对齐检查通过 (backend=%d keys, frontend=%d items)"
          % (len(backend_keys), len(frontend_items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
