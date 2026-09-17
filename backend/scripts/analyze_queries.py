"""查询计划分析工具 - 分析慢查询并检测全表扫描"""
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# 需要分析的高频查询列表
HIGH_FREQ_QUERIES = [
    {
        "name": "经费分析-按村庄汇总",
        "sql": """
            SELECT village_id, COUNT(*) as cnt, SUM(CAST(amount AS REAL)) as total
            FROM funds
            WHERE status IN ('approved', 'allocated', 'completed')
            GROUP BY village_id
        """
    },
    {
        "name": "经费分析-按类型汇总",
        "sql": """
            SELECT fund_type, COUNT(*) as cnt, SUM(CAST(amount AS REAL)) as total
            FROM funds GROUP BY fund_type
        """
    },
    {
        "name": "年度收入-按年份查询",
        "sql": """
            SELECT * FROM annual_income
            WHERE supported_village_id = ? AND year = ?
        """
    },
    {
        "name": "帮扶村-按省份梯队统计",
        "sql": """
            SELECT province, CASE WHEN is_revitalization_tier THEN '是' ELSE '否' END as tier, COUNT(*) as cnt
            FROM supported_villages
            GROUP BY province, is_revitalization_tier
        """
    },
    {
        "name": "审批记录-按实体查询",
        "sql": """
            SELECT * FROM approval_records
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY created_at DESC
        """
    },
    {
        "name": "项目-按村庄查询",
        "sql": """
            SELECT * FROM projects
            WHERE village_id = ?
            ORDER BY created_at DESC
        """
    },
    {
        "name": "经费列表-OFFSET分页",
        "sql": """
            SELECT * FROM funds
            WHERE status = ?
            ORDER BY id DESC
            LIMIT 20 OFFSET 10000
        """
    },
]


def analyze_query_plans():
    """对所有高频查询执行EXPLAIN QUERY PLAN"""
    db = SessionLocal()
    try:
        print("=" * 80)
        print("SQLite 查询计划分析报告")
        print("=" * 80)

        issues = []

        for query_info in HIGH_FREQ_QUERIES:
            name = query_info["name"]
            sql = query_info["sql"]
            print(f"\n--- {name} ---")
            print(f"SQL: {sql.strip()[:100]}...")

            try:
                explain_sql = f"EXPLAIN QUERY PLAN {sql}"
                result = db.execute(text(explain_sql)).fetchall()

                has_scan = False
                for row in result:
                    detail = " | ".join(str(v) for v in row)
                    print(f"  计划: {detail}")
                    if "SCAN" in str(row).upper():
                        has_scan = True

                if has_scan:
                    issues.append({
                        "query": name,
                        "problem": "检测到全表扫描(SCAN)，建议添加对应索引",
                        "sql": sql.strip(),
                    })
            except Exception as e:
                # 带参数的查询跳过（?占位符在EXPLAIN中可执行）
                try:
                    result = db.execute(text(explain_sql), {"village_id": 1, "year": 2024, "entity_type": "fund", "entity_id": 1, "status": "approved"}).fetchall()
                    for row in result:
                        print(f"  计划: {' | '.join(str(v) for v in row)}")
                except Exception:
                    print(f"  跳过（需要参数绑定）: {e}")

        # 汇总
        print("\n" + "=" * 80)
        print(f"分析结果: {len(issues)} 个潜在性能问题")
        print("=" * 80)
        for i, issue in enumerate(issues, 1):
            print(f"{i}. [{issue['query']}] {issue['problem']}")
            print(f"   SQL: {issue['sql'][:120]}")

        if not issues:
            print("未发现全表扫描，所有查询已使用索引。")

        return issues

    finally:
        db.close()


def check_table_indexes():
    """检查所有表的索引覆盖情况"""
    db = SessionLocal()
    try:
        print("\n" + "=" * 80)
        print("索引覆盖检查")
        print("=" * 80)

        # 获取所有表
        tables = db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_alembic%'"
        )).fetchall()

        for (table_name,) in tables:
            indexes = db.execute(text(f"PRAGMA index_list('{table_name}')")).fetchall()
            index_names = [idx[1] for idx in indexes]
            print(f"\n{table_name}: {len(indexes)} 个索引")
            for idx in indexes:
                print(f"  - {idx[1]}")

            # 检查外键索引
            fks = db.execute(text(f"PRAGMA foreign_key_list('{table_name}')")).fetchall()
            for fk in fks:
                col_name = fk[3]
                has_idx = any(col_name in idx_name for idx_name in index_names)
                if not has_idx:
                    print(f"  [WARN] 外键 {col_name} 缺少索引!")

    finally:
        db.close()


def generate_index_recommendations():
    """基于查询分析生成索引建议"""
    recommendations = [
        # 经费分析Dashboard聚合
        "CREATE INDEX IF NOT EXISTS ix_funds_status_village_amount ON funds(status, village_id, CAST(amount AS REAL));",
        # 审批记录-高频实体查询
        "CREATE INDEX IF NOT EXISTS ix_approval_records_entity_status ON approval_records(entity_type, entity_id, status);",
        # 年度快照覆盖索引（避免回表）
        "CREATE INDEX IF NOT EXISTS ix_annual_income_covering ON annual_income(supported_village_id, year, per_capita_income_2025, village_collective_income_2025);",
        # 项目-按村庄和状态
        "CREATE INDEX IF NOT EXISTS ix_projects_village_status ON projects(village_id, status);",
    ]

    print("\n" + "=" * 80)
    print("推荐索引创建SQL")
    print("=" * 80)
    for sql in recommendations:
        print(f"  {sql}")

    return recommendations


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyze_query_plans()
    check_table_indexes()
    generate_index_recommendations()
