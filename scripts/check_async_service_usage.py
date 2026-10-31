#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AsyncSession 服务棘轮门禁（2026-10-31 巡检新增）。

## 背景

本项目主链路是**同步 SQLAlchemy**：app/core/database.get_db 产出同步 Session，
全部路由用 db: Session = Depends(get_db)；app/api/ 下**没有任何** AsyncSession。

但巡检发现 4 个 service 仍以 AsyncSession 为构造参数：

- services/supported_village_service.py（9 个 async 方法）
- services/fund_health_service.py（1 个 async 方法，其余已同步）
- services/funding/phase_budget_service.py（3 个 async 方法）
- services/funding/phase_init_service.py（3 个 async 方法）

核查结论：**它们无法被生产链路使用** ——
  * 没有 async 版 get_db，路由拿不到 AsyncSession；
  * 全仓除自身定义与 funding/__init__.py 的 re-export 外，**无任何调用点**；
  * 只被测试调用（用 AsyncMock），因此覆盖率仍显示 100%。

services/fund_service.py 的 docstring 记载过一次架构回退：
「将 AsyncSession 修正为同步 Session，与 database.py 和 API 层保持一致」——
这 4 个文件是那次回退的**遗漏**。

## 本门禁做什么 / 不做什么

**做**：把现状登记为基线（只许减少），禁止**新增** AsyncSession 服务。
**不做**：不强制重构既有 4 个（改同步需同步改 13 个测试文件的 mock，且它们当前无生产
调用、不产生运行时故障 —— 属架构清理专项，见 CHANGELOG 说明）。

用法：

    python scripts/check_async_service_usage.py
    ... --json / --update
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"
BASELINE = ROOT / "backend" / "scripts" / "gate_baselines" / "async_services.json"

_ASYNC_IMPORT = re.compile(r"^\s*from\s+sqlalchemy\.ext\.asyncio\s+import\s+AsyncSession", re.M)
_ASYNC_ANNOT = re.compile(r"db:\s*AsyncSession")
_CLASS = re.compile(r"^class\s+(\w+)", re.M)


def find_async_services() -> list:
    out = []
    for f in sorted(APP.rglob("*.py")):
        text = f.read_text(encoding="utf-8", errors="replace")
        if not _ASYNC_IMPORT.search(text):
            continue
        if not _ASYNC_ANNOT.search(text):
            continue
        names = [m.group(1) for m in _CLASS.finditer(text)]
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        out.append({"file": rel, "classes": names})
    return out


def _load_baseline() -> set:
    if not BASELINE.is_file():
        return set()
    try:
        return set(json.loads(BASELINE.read_text(encoding="utf-8")).get("known", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_baseline(files: set) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps({"known": sorted(files)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AsyncSession 服务棘轮")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args(argv)

    items = find_async_services()
    files = {i["file"] for i in items}
    known = _load_baseline()
    added = sorted(files - known)
    fixed = sorted(known - files)

    if args.update:
        _save_baseline(files)
        print(f"[async-svc] 基线已更新为 {len(files)} 个文件")
        return 0

    if args.json:
        print(json.dumps(
            {"count": len(files), "baseline": len(known), "added": added, "fixed": fixed,
             "items": items},
            ensure_ascii=False))
        return 1 if added else 0

    print(f"[async-svc] 以 AsyncSession 为构造参数的服务：{len(files)} 个文件（基线 {len(known)}）")
    if fixed:
        print(f"  ✓ 已消除 {len(fixed)} 个（可 --update 收紧基线）: {fixed}")
    if added:
        print(f"  ✗ 新增 {len(added)} 个 AsyncSession 服务：")
        for f in added:
            print(f"      {f}")
        print()
        print("本项目主链路是同步 Session（get_db），路由无法注入 AsyncSession。")
        print("新增此类服务无法被生产调用，只被测试覆盖而虚高覆盖率。")
        print("若确需引入，请先提供 async get_db 并更新基线；否则改用同步 Session。")
        return 1
    print("[async-svc] OK：未超出基线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
