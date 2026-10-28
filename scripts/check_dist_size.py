#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前端产物体积棘轮（dist 总字节 / 文件数 / br 数只紧不松）。

## 为什么

安装包体积直接决定"离线分发拷 U 盘"的成本；历史教训是**无意膨胀无人察觉**：
多引一个 echarts 主题、复制一份瓦片、压缩插件重复产物，都是几百 KB 到几 MB 的量级。
2026-10-28 实测基线：frontend/dist 9.2 MB / 约 190 文件 / 114 个 .br。

本门禁在**构建之后**核对三项指标，超过基线 + 容许浮动即失败；人工确认属实后
跑 --update 上调基线（棘轮只紧不松）。dist 不存在时 SKIP（CI 的静态分析作业不建前端）。

用法::

    python scripts/check_dist_size.py                 # 门禁
    python scripts/check_dist_size.py --update        # 人工确认后写回基线
    python scripts/check_dist_size.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
BASELINE = ROOT / "scripts" / "gate_baselines" / "dist_size.json"
TOLERANCE = 0.05  # 允许 5% 浮动：vite 哈希文件名/压缩版本差异会带来小幅抖动

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def measure(dist: Path = DIST) -> dict:
    files = [p for p in dist.rglob("*") if p.is_file()]
    return {
        "total_bytes": sum(p.stat().st_size for p in files),
        "file_count": len(files),
        "br_count": sum(1 for p in files if p.suffix == ".br"),
    }


def compare(current: dict, baseline: dict) -> list:
    problems = []
    for key in ("total_bytes", "file_count", "br_count"):
        allowed = int(baseline.get(key, 0) * (1 + TOLERANCE)) if key == "total_bytes" else baseline.get(key, 0)
        if current[key] > allowed:
            problems.append("%s=%s 超过基线上限 %s（基线 %s）" % (key, current[key], allowed, baseline.get(key)))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="前端产物体积棘轮")
    parser.add_argument("--update", action="store_true", help="把当前测量值写回基线")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    if not DIST.is_dir():
        print("[dist-size] SKIP：frontend/dist 不存在（未构建）")
        return 0

    current = measure()
    if args.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[dist-size] 基线已更新: " + json.dumps(current, ensure_ascii=False))
        return 0

    baseline = {}
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            baseline = {}
    if not baseline:
        print("[dist-size] 缺少基线 " + str(BASELINE.relative_to(ROOT)) + "：先跑 --update 人工确认")
        return 1

    problems = compare(current, baseline)
    if args.json:
        print(json.dumps({"ok": not problems, "current": current, "baseline": baseline,
                          "problems": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print("[dist-size] 产物体积增长超出容许范围：", file=sys.stderr)
        for item in problems:
            print("  - " + item, file=sys.stderr)
        print("  若确属功能需要：python scripts/check_dist_size.py --update（并在 CHANGELOG 说明）",
              file=sys.stderr)
    else:
        mb = current["total_bytes"] / 1024 / 1024
        print("[dist-size] OK：%.1f MB / %d 文件 / %d 个 .br（基线 %.1f MB）"
              % (mb, current["file_count"], current["br_count"], baseline.get("total_bytes", 0) / 1024 / 1024))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
