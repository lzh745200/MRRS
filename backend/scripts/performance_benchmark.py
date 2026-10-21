#!/usr/bin/env python3
"""SQLite 性能基准与回归比较（R34-5 / 4.3-12）。

## 定位

这是**本地/夜间**性能回归工具，不进 PR 阻塞门禁：本机开发库数据量很小
（funds 十余行、households 常为 0 行），绝对耗时在亚毫秒级、噪声占比高，
在 CI 上按时间阈值卡红会变成"随机红灯"。正确用法是：

    # 1) 基线由一台稳定机器在安静状态下采集，提交进仓库
    python backend/scripts/performance_benchmark.py --update-baseline

    # 2) 日常改动后对比（明显劣化才失败）
    python backend/scripts/performance_benchmark.py --compare

    # 3) 只跑不比较（看表格）
    python backend/scripts/performance_benchmark.py

## 回归判定（为什么不是简单的 +10%）

小数据集下毫秒级查询的相对波动可达数倍，但绝对值无意义。故采用
「相对放宽 + 绝对下限」双闸：
    劣化 = current > max(baseline * (1 + tolerance), baseline + min_delta_ms)
默认 tolerance=2.0（允许 3 倍内波动）、min_delta_ms=50（50ms 以内不判失败）。
这两个值刻意宽松——它们拦的是**数量级**退化（如漏建索引导致全表扫描 10 倍），
而不是抖动。

## 为何补 houseshold / 导出 查询

4.3-12 明确要求重点覆盖「导出」与「一户一档聚合」：这两条链路是 W22 新增且
数据量增长最快的路径，也是历史上最容易因缺索引而退化的地方。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402

BASELINE_FILE = Path(__file__).resolve().parent / "gate_baselines" / "perf_baseline.json"

# (名称, SQL, 参数)
QUERIES = [
    ("全表 COUNT funds", "SELECT COUNT(*) FROM funds", {}),
    ("条件查询 funds.status", "SELECT * FROM funds WHERE status = 'approved'", {}),
    (
        "JOIN funds × supported_villages",
        """
        SELECT f.id, f.amount, sv.village_name
        FROM funds f
        JOIN supported_villages sv ON f.village_id = sv.id
        LIMIT 100
        """,
        {},
    ),
    (
        "GROUP BY funds.status 聚合",
        "SELECT status, COUNT(*) cnt, SUM(CAST(amount AS REAL)) total FROM funds GROUP BY status",
        {},
    ),
    ("深分页 OFFSET 10000", "SELECT * FROM funds ORDER BY id DESC LIMIT 20 OFFSET 10000", {}),
    ("Keyset 分页", "SELECT * FROM funds WHERE id < 10000 ORDER BY id DESC LIMIT 20", {}),
    (
        "年度收入查询",
        "SELECT * FROM annual_income WHERE supported_village_id = 1 AND year = 2024",
        {},
    ),
    (
        "Dashboard 按省份/梯队统计",
        """
        SELECT province,
               CASE WHEN is_revitalization_tier THEN '是' ELSE '否' END tier,
               COUNT(*) cnt
        FROM supported_villages
        GROUP BY province, is_revitalization_tier
        """,
        {},
    ),
    # ── 一户一档（W22 新增，4.3-12 要求重点覆盖）──
    (
        "一户一档 列表+组织过滤",
        "SELECT * FROM households WHERE organization_id IS NOT NULL LIMIT 200",
        {},
    ),
    (
        "一户一档 成员聚合",
        """
        SELECT h.id, COUNT(m.id) member_count
        FROM households h
        LEFT JOIN household_members m ON m.household_id = h.id
        GROUP BY h.id
        LIMIT 200
        """,
        {},
    ),
    (
        "一户一档 风险预警扫描",
        """
        SELECT COUNT(*) FROM household_risk_records
        WHERE status = 'open'
        """,
        {},
    ),
    # ── 导出链路（4.3-12 要求重点覆盖）──
    (
        "导出 经费台账（全量排序）",
        "SELECT * FROM funds ORDER BY date DESC, id DESC",
        {},
    ),
    (
        "导出 帮扶村年度数据 JOIN",
        """
        SELECT sv.id, sv.village_name, vi.year, vi.per_capita_income
        FROM supported_villages sv
        LEFT JOIN village_income vi ON vi.supported_village_id = sv.id
        ORDER BY sv.id, vi.year DESC
        """,
        {},
    ),
    (
        "工作日志按时间倒序分页",
        "SELECT * FROM work_logs ORDER BY created_at DESC LIMIT 50",
        {},
    ),
]


def _percentile(values, pct):
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100) * len(ordered) - 1))))
    return ordered[idx]


def benchmark(name, sql, params, iterations):
    db = SessionLocal()
    times = []
    rows = None
    try:
        # 预热一次（跳过冷缓存/首次 prepare 的一次性成本）
        rows = len(db.execute(text(sql), params).fetchall())
        for _ in range(iterations):
            start = time.perf_counter()
            db.execute(text(sql), params).fetchall()
            times.append((time.perf_counter() - start) * 1000)
    except Exception as exc:
        print(f"{name:.<52} ERROR: {exc}")
        return None
    finally:
        db.close()

    avg = statistics.fmean(times)
    result = {
        "name": name,
        "avg_ms": round(avg, 3),
        "p95_ms": round(_percentile(times, 95), 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "rows": rows,
    }
    print(
        f"{name:.<52} avg {avg:>8.3f}ms  p95 {result['p95_ms']:>8.3f}ms  rows {rows}"
    )
    return result


def load_baseline():
    if not BASELINE_FILE.exists():
        return {}
    try:
        data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {item["name"]: item for item in data.get("queries", [])}


def write_baseline(results):
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": "本地/夜间性能基线；小数据集噪声大，仅用于数量级回归判定",
        "tolerance_ratio": 2.0,
        "min_delta_ms": 50.0,
        "queries": results,
    }
    BASELINE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n[baseline] {len(results)} 个查询 -> {BASELINE_FILE.relative_to(BACKEND.parent)}")


def compare(results, baseline, tolerance, min_delta_ms):
    regressions = []
    missing_baseline = []
    for item in results:
        base = baseline.get(item["name"])
        if not base:
            missing_baseline.append(item["name"])
            continue
        allowed = max(base["avg_ms"] * (1 + tolerance), base["avg_ms"] + min_delta_ms)
        if item["avg_ms"] > allowed:
            regressions.append(
                (item["name"], base["avg_ms"], item["avg_ms"], allowed)
            )
    return regressions, missing_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite 性能基准与回归")
    parser.add_argument("--iterations", type=int, default=10, help="每个查询重复次数（默认 10）")
    parser.add_argument("--compare", action="store_true", help="与基线比较，劣化则退出 1")
    parser.add_argument("--update-baseline", action="store_true", help="用本次结果重写基线")
    parser.add_argument("--tolerance", type=float, default=2.0, help="允许的相对劣化倍数（默认 2.0）")
    parser.add_argument("--min-delta-ms", type=float, default=50.0, help="免判失败的最小绝对增量（默认 50ms）")
    args = parser.parse_args()

    print("=" * 96)
    print(f"SQLite 性能基准（迭代 {args.iterations} 次，含预热）")
    print("=" * 96)

    results = [r for r in (
        benchmark(name, sql, params, args.iterations) for name, sql, params in QUERIES
    ) if r]

    if not results:
        print("\n无有效结果（数据库不可用或查询全部失败）")
        return 1

    avg_all = statistics.fmean(r["avg_ms"] for r in results)
    slowest = max(results, key=lambda r: r["avg_ms"])
    print("-" * 96)
    print(f"平均 {avg_all:.3f}ms | 最慢 {slowest['name']} ({slowest['avg_ms']:.3f}ms) | 查询数 {len(results)}")

    if args.update_baseline:
        write_baseline(results)
        return 0

    if args.compare:
        baseline = load_baseline()
        if not baseline:
            print("\n[skip] 无基线文件；先跑 --update-baseline")
            return 0
        regressions, missing = compare(results, baseline, args.tolerance, args.min_delta_ms)
        if missing:
            print(f"\n[warn] {len(missing)} 个查询无基线（新增项）：")
            for name in missing:
                print(f"  - {name}")
        if regressions:
            print(f"\n性能回归（{len(regressions)} 项）：")
            for name, base_ms, cur_ms, allowed in regressions:
                print(f"  - {name}: 基线 {base_ms:.3f}ms → 当前 {cur_ms:.3f}ms（允许 ≤{allowed:.3f}ms）")
            return 1
        print(f"\n性能回归检查通过（容差 ×{1 + args.tolerance:.1f} 或 +{args.min_delta_ms}ms）")
        return 0

    print("\n（未指定 --compare / --update-baseline，仅展示结果）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
