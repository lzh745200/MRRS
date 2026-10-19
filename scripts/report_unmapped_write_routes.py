# -*- coding: utf-8 -*-
"""列出"归属不到模块"的写接口 —— R33 授权守卫上线前的清零清单。

用法（需能 import app，故在 backend 下执行）：
    cd backend
    set PYTHONPATH=<repo>\\backend;<repo>\\backend\\.venv313\\Lib\\site-packages
    <python> ..\\scripts\\report_unmapped_write_routes.py

退出码：0 = 全部已归属；1 = 存在未归属（CI 可据此阻断）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.write_route_map import (  # noqa: E402
    MODULE_RULES,
    WRITE_METHODS,
    is_exempt,
    resolve_module,
    unmapped_write_routes,
)


def main() -> int:
    from app.main import app  # noqa: PLC0415 — 延迟导入，避免 --help 也拉起整个应用

    rows = unmapped_write_routes(app.routes)
    total_write = 0
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if path and any(m.upper() in WRITE_METHODS for m in methods) and not is_exempt(path):
            total_write += 1

    mapped = total_write - len(rows)
    print("=== R33 写接口模块归属 ===")
    print("规则条数: %d" % len(MODULE_RULES))
    print("写接口总数: %d" % total_write)
    print("已归属: %d" % mapped)
    print("未归属: %d" % len(rows))
    if rows:
        print("")
        print("--- 未归属清单（需补 MODULE_RULES 或加 EXEMPT_PREFIXES）---")
        for methods, path in sorted(rows, key=lambda r: r[1]):
            print("  %-24s %-60s -> %s" % (",".join(methods), path, resolve_module(path)))
    return 0 if not rows else 1


if __name__ == "__main__":
    sys.exit(main())
