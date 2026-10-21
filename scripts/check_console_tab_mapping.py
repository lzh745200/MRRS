#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""console Tab 映射完整性门禁（防止「后端下发 tab、前端无组件」导致功能静默消失）。

背景（2026-10-21 实际缺陷）：R33 单位授权两个 tab（system-org-grant / system-grant-import）
早已在后端 menus.py 下发，但 SystemConsole.vue 的 TAB_COMPONENTS 未同步，被
renderableTabs 过滤 → 聚合页完全看不到这两个功能，只能手输 URL。既有门禁
（check_menu_alignment 校验 path 可解析、nav-links 校验导航 path 存在）都查不到这类
"key 有、组件无"的缺口。

规则：
  A. 后端 menus.py 中每个 console 的 tabs[].key 必须在前端 TAB_COMPONENTS 有映射；
  B. 前端 TAB_COMPONENTS 的 key 必须是后端已声明的 console tab key（禁止僵尸映射）。

退出码：0 = 通过；1 = 存在缺口（打印明细）。只读脚本。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MENUS = ROOT / "backend" / "app" / "api" / "v1" / "menus.py"
CONSOLE = ROOT / "frontend" / "src" / "views" / "system" / "console" / "SystemConsole.vue"

CONSOLE_RE = re.compile(r'"key":\s*"(system-console-[a-z]+)"(.*?)(?="key":\s*"system-console-|\Z)', re.S)
TABS_RE = re.compile(r'"tabs":\s*\[(.*?)\n\s*\],', re.S)
TAB_KEY_RE = re.compile(r'"key":\s*"([a-z0-9\-]+)"')


def backend_tab_keys() -> dict[str, list[str]]:
    text = MENUS.read_text(encoding="utf-8")
    result: dict[str, list[str]] = {}
    for match in CONSOLE_RE.finditer(text):
        console_key, body = match.group(1), match.group(2)
        tabs_match = TABS_RE.search(body)
        if not tabs_match:
            continue
        result[console_key] = TAB_KEY_RE.findall(tabs_match.group(1))
    return result


def frontend_component_keys() -> set[str]:
    text = CONSOLE.read_text(encoding="utf-8")
    match = re.search(r"const TAB_COMPONENTS[^{]*\{(.*?)\n\}", text, re.S)
    if not match:
        raise SystemExit("[console-tab-map] 无法解析 SystemConsole.vue 的 TAB_COMPONENTS")
    return set(re.findall(r"['\"]?([a-z0-9\-]+)['\"]?\s*:", match.group(1)))


def main() -> int:
    backend = backend_tab_keys()
    if not backend:
        print("[console-tab-map] FAIL: 无法从 menus.py 解析任何 console tabs", file=sys.stderr)
        return 1
    frontend = frontend_component_keys()
    backend_keys = {k for keys in backend.values() for k in keys}

    errors: list[str] = []
    for console_key, keys in sorted(backend.items()):
        for tab_key in keys:
            if tab_key not in frontend:
                errors.append(
                    "[A] 后端 %s 下发 tab '%s'，但前端 TAB_COMPONENTS 无组件映射"
                    "（聚合页会静默隐藏该功能）" % (console_key, tab_key)
                )
    for tab_key in sorted(frontend - backend_keys):
        errors.append("[B] 前端 TAB_COMPONENTS 声明了后端不存在的 tab '%s'（僵尸映射）" % tab_key)

    total = sum(len(v) for v in backend.values())
    if errors:
        print("[console-tab-map] FAIL: 发现 %d 处不一致" % len(errors), file=sys.stderr)
        for err in errors:
            print("  " + err, file=sys.stderr)
        return 1
    print(
        "[console-tab-map] OK: %d 个 console / %d 个 tab / %d 个前端组件映射，完全一致"
        % (len(backend), total, len(frontend))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
