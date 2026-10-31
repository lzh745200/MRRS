#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离线单机关键路径的性能基线（批 3 · 只报警不阻断）。

## 为什么

这个系统最容易出问题的现场不是"功能报错"，而是**卡死/白屏**：离线政务本配置低，
导入 5,000 行 Excel、导出同样规模、生成模板，任何一处退化成分钟级都会被视为"系统坏了"。
目前只有功能门禁，没有任何**性能回归**信号。

本脚本以固定数据量测 3 条热路径，输出 JSON 并与基线比较；**默认只报告不阻断**
（CI 机器噪声大，硬阈值会制造假红）；`--strict` 时超基线 50% 才非 0 退出，
用于 nightly 趋势观察。

用法::

    python scripts/bench.py                 # 跑一次并对比基线
    python scripts/bench.py --update        # 人工确认后写回基线
    python scripts/bench.py --rows 2000     # 调整数据量（默认 5000）
    python scripts/bench.py --json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
BASELINE = ROOT / "scripts" / "gate_baselines" / "bench_baseline.json"
SLOW_RATIO = 0.5
# 噪声地板：毫秒级路径（如 5,000 行的 CSV 导出 ~5ms）在任意机器上都可能抖动 50%+，
# 对它报警等于制造假红；只有**两侧都**低于地板时才跳过比较。
MIN_ABS_SECONDS = 0.05

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _build_xlsx(rows: int) -> bytes:
    from openpyxl import Workbook

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Sheet1")
    ws.append(["姓名", "年龄", "金额"])
    for i in range(rows):
        ws.append([f"村民{i}", 20 + i % 60, 100 + i])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _time_it(func) -> float:
    started = time.perf_counter()
    func()
    return round(time.perf_counter() - started, 4)


def run_bench(rows: int = 5000) -> dict:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))

    from app.services.office_reader import read_rows

    payload = _build_xlsx(rows)
    result = {"rows": rows}
    result["xlsx_parse_s"] = _time_it(lambda: read_rows(payload, "bench.xlsx"))

    def _csv() -> None:
        import csv

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["姓名", "年龄", "金额"])
        for i in range(rows):
            writer.writerow([f"村民{i}", 20 + i % 60, 100 + i])
        buffer.getvalue().encode("utf-8-sig")

    result["csv_export_s"] = _time_it(_csv)

    def _template() -> None:
        from app.services.excel_template_service import ExcelTemplateService

        ExcelTemplateService().generate_village_template()

    result["template_build_s"] = _time_it(_template)
    return result


def compare(current: dict, baseline: dict) -> list:
    """与基线比较：≥ 基线 1+SLOW_RATIO 的报告出来（只报警不阻断，除非 --strict）。"""
    problems = []
    for key, value in current.items():
        if key == "rows":
            continue
        base = baseline.get(key)
        if not base:
            continue
        if value < MIN_ABS_SECONDS and base < MIN_ABS_SECONDS:
            continue  # 噪声地板内不比较
        if value > base * (1 + SLOW_RATIO):
            problems.append("%s=%.3fs 比基线 %.3fs 慢 %.0f%%（阈值 +%.0f%%）"
                            % (key, value, base, (value / base - 1) * 100, SLOW_RATIO * 100))
    return problems


def run_tier(rows: int) -> dict:
    return run_bench(rows)


def _tier_key(rows: int) -> str:
    return str(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="关键路径性能基线（只报警不阻断）")
    parser.add_argument("--rows", default="5000",
                        help="基准数据量：单个数字或逗号分隔的多档（如 5000,20000）")
    parser.add_argument("--update", action="store_true", help="把当前各档值写回基线")
    parser.add_argument("--strict", action="store_true", help="超基线 50% 时以非 0 退出")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    try:
        row_sets = [int(x) for x in str(args.rows).split(",") if str(x).strip()]
    except ValueError:
        parser.error("--rows 需要整数或逗号分隔的整数列表")
    if not row_sets:
        parser.error("--rows 至少给一个数据量")

    current_tiers = {_tier_key(n): run_tier(n) for n in row_sets}

    if args.update:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        first_key = _tier_key(row_sets[0])
        payload = {"tiers": current_tiers}
        # 兼容旧读者：把首档同时放在顶层（旧格式 == 单档）
        payload.update(current_tiers[first_key])
        BASELINE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[bench] 基线已更新: " + json.dumps(current_tiers, ensure_ascii=False))
        return 0

    baseline = {}
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            baseline = {}
    baseline_tiers = baseline.get("tiers") or {_tier_key(baseline.get("rows", row_sets[0])): baseline}

    problems = []
    missing_tiers = []
    for key, metrics in current_tiers.items():
        tier_base = baseline_tiers.get(key)
        if not tier_base:
            missing_tiers.append(key)
            continue
        for item in compare(metrics, tier_base):
            problems.append("rows=%s %s" % (key, item))

    if args.json:
        print(json.dumps({"current": current_tiers, "baseline": baseline_tiers,
                          "problems": problems, "missing_tiers": missing_tiers},
                         ensure_ascii=False, indent=2))
    else:
        for key, metrics in current_tiers.items():
            detail = ", ".join("%s=%.3fs" % (k, v) for k, v in metrics.items() if k != "rows")
            print("[bench] rows=%s %s" % (key, detail))
        for item in problems:
            print("  WARN " + item)
        for key in missing_tiers:
            print("  （rows=%s 无基线：跑 --update 记录首次值）" % key)
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())