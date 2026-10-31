#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前端 API 使用率棘轮门禁（2026-10-31 巡检新增）。

## 它解决什么问题

前端 `src/api/*.ts` 里存在大量「定义了但产品代码从不调用」的函数：它们**只被测试调用**，
于是前端覆盖率轻松到 100%，但产品从未接入 —— 覆盖率成了「自证」而非「质量证据」。

巡检实测（2026-10-31）：303 个具名导出函数中，186 个被 src 直接引用、47 个经聚合对象
（`export const xxxApi = { foo }`，页面写 `xxxApi.foo()`）暴露，**70 个既不被直接引用也被不
经对象暴露**（仅测试使用）。

这本身不是功能缺陷（不影响在用功能），但会：
  1. 让覆盖率虚高，掩盖真正的「未接入」；
  2. 增加维护面（改接口时要一起改一堆死函数）。

## 判定口径（三态）

对每个具名导出函数 `X`：
  1. **src 直接引用**：非 `src/api/` 的 `.ts`/`.vue` 中出现标识符 `X`；
  2. **经聚合对象暴露**：同文件内出现 `[:{,{]` + 空白 + `X` + 空白 + `[,}]`（被对象字面量引用）；
  3. 否则计为**未使用**（only-tests）。

## 棘轮口径

基线登记当前 70 个（`gate_baselines/frontend_api_usage.json`），**只许减少**：
新增未使用函数即失败（防止继续堆测试专用代码）。

用法：

    python scripts/check_frontend_api_usage.py
    ... --json / --update
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE_SRC = ROOT / "frontend" / "src"
API_DIR = FE_SRC / "api"
BASELINE = ROOT / "backend" / "scripts" / "gate_baselines" / "frontend_api_usage.json"

_NAMED_EXPORT = re.compile(r"export\s+(?:async\s+)?function\s+(\w+)")


def collect_named_exports() -> dict:
    out = {}
    if not API_DIR.is_dir():
        return out
    for f in API_DIR.rglob("*.ts"):
        text = f.read_text(encoding="utf-8", errors="replace")
        try:
            rel = str(f.relative_to(ROOT)).replace("\\", "/")
        except ValueError:  # 单测用 tmp_path 沙箱时文件不在 ROOT 下
            rel = str(f).replace("\\", "/")
        for m in _NAMED_EXPORT.finditer(text):
            out[m.group(1)] = (rel, text)
    return out


def src_blob() -> str:
    parts = []
    for f in list(FE_SRC.rglob("*.ts")) + list(FE_SRC.rglob("*.vue")):
        p = str(f).replace("\\", "/")
        if "/api/" in p:
            continue
        parts.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def find_unused() -> list:
    exports = collect_named_exports()
    blob = src_blob()
    unused = []
    for name, (rel, text) in sorted(exports.items()):
        if re.search(r"\b" + re.escape(name) + r"\b", blob):
            continue
        if re.search(r"[:{,{]\s*" + re.escape(name) + r"\s*[,}]", text):
            continue
        unused.append({"name": name, "module": rel})
    return unused


def _load_baseline() -> set:
    if not BASELINE.is_file():
        return set()
    try:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("known", []))


def _save_baseline(names: set) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps({"known": sorted(names)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="前端 API 使用率棘轮")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--update", action="store_true", help="把当前未使用项登记为基线")
    args = ap.parse_args(argv)

    unused = find_unused()
    names = {u["name"] for u in unused}
    known = _load_baseline()
    added = sorted(names - known)
    fixed = sorted(known - names)

    if args.update:
        _save_baseline(names)
        print(f"[frontend-api-usage] 基线已更新为 {len(names)} 项")
        return 0

    payload = {
        "unused_count": len(names),
        "baseline_count": len(known),
        "added": added,
        "fixed": fixed,
        "unused": unused,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return 1 if added else 0

    print(
        f"[frontend-api-usage] 未被 src 使用的具名导出 {len(names)} 个（基线 {len(known)}）"
    )
    if fixed:
        print(f"  ✓ 已清掉 {len(fixed)} 个（可 --update 收紧基线）: {fixed[:8]}")
    if added:
        print(f"  ✗ 新增 {len(added)} 个未使用导出:")
        for n in added:
            print(f"      {n}")
        print()
        print("修复方式：把函数接入页面，或在 api 模块里删除并同步删除其测试；")
        print("确属对外/预留 API 时，登记进 gate_baselines/frontend_api_usage.json 并说明理由。")
        return 1
    print("[frontend-api-usage] OK：未使用导出未超出基线")
    return 0


if __name__ == "__main__":
    sys.exit(main())
