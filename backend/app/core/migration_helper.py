"""数据库迁移辅助函数。

从 app.main 提取，消除服务层（version_service.py）对应用入口点的反向依赖。
这些函数是纯基础设施代码，不包含业务逻辑。
"""

import os
import logging

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _sqlite_col_spec(col):
    """根据 SQLAlchemy Column 推断 SQLite 列类型和 DEFAULT 子句。

    Returns:
        (sqlite_type, default_clause) - 例如 ("INTEGER", "DEFAULT 0")
    """
    t = str(col.type).upper()

    # 类型映射
    if "INT" in t or "BOOL" in t:
        stype = "INTEGER"
    elif "FLOAT" in t or "REAL" in t or "NUMERIC" in t:
        stype = "REAL"
    else:
        # DATE, DATETIME, JSON, VARCHAR, TEXT, ENUM 等在 SQLite 中均用 TEXT
        stype = "TEXT"

    # 推断 DEFAULT 值
    default_clause = ""
    # 优先使用模型 default（ColumnDefault）
    if (
        col.default is not None
        and hasattr(col.default, "arg")
        and col.default.arg is not None
        and not callable(col.default.arg)
    ):
        raw = col.default.arg
        if isinstance(raw, bool):
            default_clause = f"DEFAULT {1 if raw else 0}"
        elif isinstance(raw, (int, float)):
            default_clause = f"DEFAULT {raw}"
        elif isinstance(raw, str):
            escaped = raw.replace("'", "''")
            default_clause = f"DEFAULT '{escaped}'"
    elif col.server_default is not None:
        # 注意: SQLite ALTER TABLE ADD COLUMN 不支持非常量 DEFAULT
        # (CURRENT_TIMESTAMP 会报错 "Cannot add a column with non-constant default")
        # 对于 server_default=func.now() 这类情况，跳过 DEFAULT，
        # ORM 层的 default=_utcnow 会为新行自动赋值。
        pass
    elif not col.nullable:
        # nullable=False 但没有显式 default → 给一个类型感知的零值
        if stype == "INTEGER":
            default_clause = "DEFAULT 0"
        elif stype == "REAL":
            default_clause = "DEFAULT 0"
        else:
            default_clause = "DEFAULT ''"

    return stype, default_clause


def migrate_missing_columns(engine, model_base):
    """检测列差异并自动添加缺失列 [DEPRECATED: 逐步迁移到纯 Alembic]

    ⚠️ 生产环境警告：此函数在启动时执行自动 DDL，存在风险。
    请尽快完成 Alembic 迁移迁移后，通过环境变量 DISABLE_AUTO_MIGRATION=1 禁用此函数。

    推荐迁移路径：新增字段后先生成 Alembic 迁移脚本，而非依赖此自动补齐。

    改进点：
    - 为 Boolean/Integer/Numeric 列添加 DEFAULT 值，确保已有行获得合理默认值
    - 对 nullable=False 且有默认值的列添加 NOT NULL DEFAULT 约束
    """
    if os.getenv("DISABLE_AUTO_MIGRATION", "").strip() == "1":
        logger.info("DISABLE_AUTO_MIGRATION=1，跳过自动列补齐（请使用 Alembic 迁移）")
        return

    try:
        inspector = sa_inspect(engine)
    except Exception as e:
        logger.warning("Schema migration: failed to create inspector: %s", e)
        return

    total_added = 0
    total_failed = 0
    for table_name, table in model_base.metadata.tables.items():
        try:
            if not inspector.has_table(table_name):
                continue
            db_cols = {c["name"] for c in inspector.get_columns(table_name)}
            model_cols = {c.name for c in table.columns}
            missing = model_cols - db_cols
            if not missing:
                continue
            logger.info(
                "Schema migration: table [%s] has %d missing column(s): %s",
                table_name,
                len(missing),
                sorted(missing),
            )
            with engine.connect() as conn:
                for col_name in sorted(missing):
                    try:
                        col = table.c[col_name]
                        stype, default_clause = _sqlite_col_spec(col)
                        # SQLite: nullable=False 列必须有 DEFAULT 才能 ADD COLUMN
                        not_null = ""
                        if not col.nullable and default_clause:
                            not_null = "NOT NULL "
                        ddl = (
                            f"ALTER TABLE [{table_name}] ADD COLUMN [{col_name}] "
                            f"{stype} {not_null}{default_clause}"
                        ).rstrip()
                        conn.execute(text(ddl))
                        total_added += 1
                        default_info = f" {default_clause}" if default_clause else ""
                        logger.info(
                            "Schema migration: [AUTO-ADD] %s.%s (%s%s)",
                            table_name,
                            col_name,
                            stype,
                            default_info,
                        )
                    except (ValueError, TypeError, AttributeError, SQLAlchemyError) as col_err:
                        total_failed += 1
                        logger.warning(
                            "Schema migration: failed to add %s.%s: %s",
                            table_name,
                            col_name,
                            col_err,
                        )
                conn.commit()
        except (ValueError, TypeError, KeyError, SQLAlchemyError) as tbl_err:
            logger.warning(
                "Schema migration: error processing table %s: %s",
                table_name,
                tbl_err,
            )

    if total_added or total_failed:
        logger.info(
            "Schema migration summary: %d column(s) added, %d failed",
            total_added,
            total_failed,
        )
    else:
        logger.info("Schema migration: all tables up to date, no columns to add")
