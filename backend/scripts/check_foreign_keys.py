#!/usr/bin/env python3
"""
外键约束检查和修复脚本
检查数据库中的外键约束是否正确设置了 CASCADE
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, event
from app.core.config import settings


def _configure_sqlite_pragmas(dbapi_conn, connection_record):
    """配置 SQLite PRAGMA 优化参数"""
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-65536")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA mmap_size=268435456")
    finally:
        cursor.close()


def check_foreign_keys():
    """检查外键约束"""
    print("=" * 60)
    print("外键约束检查")
    print("=" * 60)
    print()

    engine = create_engine(settings.DATABASE_URL)

    if settings.DATABASE_URL.startswith("sqlite"):
        event.listens_for(engine, "connect")(_configure_sqlite_pragmas)

    with engine.connect() as conn:
        # 检查外键是否启用
        result = conn.execute(text('PRAGMA foreign_keys'))
        fk_enabled = result.scalar()
        print(f"外键约束状态: {'启用' if fk_enabled else '禁用'}")
        print()

        # 获取所有引用 supported_villages 的外键
        print("引用 supported_villages 的外键:")
        print()

        result = conn.execute(text("""
            SELECT
                m.name as table_name,
                p.id as fk_id,
                p."from" as from_column,
                p."to" as to_column,
                p.on_delete as on_delete_action
            FROM sqlite_master m
            JOIN pragma_foreign_key_list(m.name) p
            WHERE m.type = 'table'
            AND p."table" = 'supported_villages'
            ORDER BY m.name, p.id
        """))

        foreign_keys = list(result)

        if not foreign_keys:
            print("  未找到外键约束")
        else:
            for fk in foreign_keys:
                table_name = fk[0]
                from_col = fk[2]
                to_col = fk[3]
                on_delete = fk[4] or "NO ACTION"

                status = "✓" if on_delete == "CASCADE" else "✗"
                print(f"  {status} {table_name}.{from_col} -> supported_villages.{to_col}")
                print(f"     ON DELETE: {on_delete}")

        print()

        # 检查是否有违反外键约束的数据
        print("检查外键约束违规:")
        result = conn.execute(text('PRAGMA foreign_key_check'))
        violations = list(result)

        if not violations:
            print("  ✓ 无外键约束违规")
        else:
            print(f"  ✗ 发现 {len(violations)} 个违规:")
            for v in violations[:10]:  # 最多显示10个
                print(f"     表: {v[0]}, 行ID: {v[1]}, 引用表: {v[2]}, 外���ID: {v[3]}")

    print()
    print("=" * 60)


def check_village_references(village_id: int):
    """检查指定村庄的引用情况"""
    print()
    print(f"检查村庄 ID={village_id} 的引用情况:")
    print()

    engine = create_engine(settings.DATABASE_URL)

    if settings.DATABASE_URL.startswith("sqlite"):
        event.listens_for(engine, "connect")(_configure_sqlite_pragmas)

    # 需要检查的表（annual_income 已于 W27 删除，见迁移 r38）
    tables_to_check = [
        'annual_population',
        'annual_infrastructure',
        'annual_industry',
        'projects',
        'work_logs',
        'funds',
        'fund_budgets',
        'fund_budget_items',
    ]

    with engine.connect() as conn:
        total_refs = 0
        for table in tables_to_check:
            try:
                # 尝试查询引用
                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE supported_village_id = :village_id OR village_id = :village_id
                """), {"village_id": village_id})
                count = result.scalar()
                if count > 0:
                    print(f"  {table}: {count} 条记录")
                    total_refs += count
            except Exception:
                # 表可能不存在或列名不同
                pass

        print()
        print(f"总计: {total_refs} 条引用记录")

    return total_refs


if __name__ == "__main__":
    # 设置 UTF-8 输出编码
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    try:
        check_foreign_keys()

        # 如果提供了村庄ID参数,检查该村庄的引用
        if len(sys.argv) > 1:
            village_id = int(sys.argv[1])
            check_village_references(village_id)

    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
