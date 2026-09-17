#!/usr/bin/env python3
"""
SQLite性能基准测试

对比优化前后的查询性能。

使用方式:
  python backend/scripts/performance_benchmark.py [--iterations 10]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import SessionLocal


def benchmark_query(name: str, sql: str, params: dict = None, iterations: int = 5):
    """测试单个查询的性能"""
    db = SessionLocal()
    try:
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = db.execute(text(sql), params or {}).fetchall()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        avg = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        row_count = len(result)

        print(f"{name:.<50} {avg:>8.2f}ms (min:{min_time:.2f}, max:{max_time:.2f}, rows:{row_count})")
        return {"name": name, "avg_ms": avg, "min_ms": min_time, "max_ms": max_time, "rows": row_count}
    except Exception as e:
        print(f"{name:.<50} ERROR: {e}")
        return None
    finally:
        db.close()


def main():
    iterations = 10

    print("=" * 80)
    print(f"SQLite 性能基准测试 (迭代{iterations}次)")
    print("=" * 80)

    results = []

    # 1. 全表查询
    results.append(benchmark_query(
        "SELECT COUNT(*) FROM funds",
        "SELECT COUNT(*) FROM funds",
        iterations=iterations,
    ))

    # 2. 带条件查询
    results.append(benchmark_query(
        "SELECT * FROM funds WHERE status='approved'",
        "SELECT * FROM funds WHERE status = 'approved'",
        iterations=iterations,
    ))

    # 3. JOIN查询
    results.append(benchmark_query(
        "funds JOIN supported_villages",
        """
            SELECT f.id, f.amount, sv.village_name
            FROM funds f
            JOIN supported_villages sv ON f.village_id = sv.id
            LIMIT 100
        """,
        iterations=iterations,
    ))

    # 4. 聚合查询
    results.append(benchmark_query(
        "GROUP BY status COUNT(*)",
        """
            SELECT status, COUNT(*) as cnt, SUM(CAST(amount AS REAL)) as total
            FROM funds GROUP BY status
        """,
        iterations=iterations,
    ))

    # 5. OFFSET分页（深分页）
    results.append(benchmark_query(
        "OFFSET分页(offset=10000)",
        "SELECT * FROM funds ORDER BY id DESC LIMIT 20 OFFSET 10000",
        iterations=iterations,
    ))

    # 6. Keyset分页（等效）
    results.append(benchmark_query(
        "Keyset分页(id<10000)",
        "SELECT * FROM funds WHERE id < 10000 ORDER BY id DESC LIMIT 20",
        iterations=iterations,
    ))

    # 7. 年度数据查询
    results.append(benchmark_query(
        "年度收入查询",
        "SELECT * FROM annual_income WHERE supported_village_id = 1 AND year = 2024",
        iterations=iterations,
    ))

    # 8. Dashboard聚合
    results.append(benchmark_query(
        "Dashboard-按省份梯队统计",
        """
            SELECT province, CASE WHEN is_revitalization_tier THEN '是' ELSE '否' END as tier, COUNT(*) as cnt
            FROM supported_villages
            GROUP BY province, is_revitalization_tier
        """,
        iterations=iterations,
    ))

    # 汇总
    results = [r for r in results if r is not None]
    print("\n" + "=" * 80)
    print("汇总")
    print("=" * 80)
    if results:
        avg_all = sum(r["avg_ms"] for r in results) / len(results)
        slowest = max(results, key=lambda r: r["avg_ms"])
        print(f"平均查询时间: {avg_all:.2f}ms")
        print(f"最慢查询: {slowest['name']} ({slowest['avg_ms']:.2f}ms)")
        print(f"总查询数: {len(results)}")

        # 检查慢查询阈值
        from app.core.config import settings
        threshold = getattr(settings, "SLOW_QUERY_THRESHOLD_MS", 200.0)
        slow_queries = [r for r in results if r["avg_ms"] > threshold]
        if slow_queries:
            print(f"\n⚠️  {len(slow_queries)} 个查询超过慢查询阈值 ({threshold}ms):")
            for sq in slow_queries:
                print(f"   - {sq['name']}: {sq['avg_ms']:.2f}ms")
        else:
            print(f"\n✅ 所有查询在阈值内 ({threshold}ms)")


if __name__ == "__main__":
    main()
