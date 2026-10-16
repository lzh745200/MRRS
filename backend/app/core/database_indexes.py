"""
数据库索引管理

在应用启动时验证模型定义的所有复合索引均已存在于数据库中。
索引定义归属于对应的 ORM 模型 __table_args__，本模块仅负责启动时验证和补建。
"""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# ── 额外运行时索引（未在模型 __table_args__ 中声明，需单独创建）──
# 格式: [(table_name, index_name, [columns])]
# 模型 __table_args__ 中的索引由 SQLAlchemy create_all 自动管理。
# 所有运行时索引已移入对应 ORM 模型 __table_args__（由 SQLAlchemy create_all 管理）
EXTRA_INDEXES = [
    # ── FK 性能索引（审计发现：10+ FK 列缺失索引导致 JOIN 全表扫描）──
    ("fund_budgets", "ix_fund_budgets_organization_id", ["organization_id"]),
    ("fund_budgets", "ix_fund_budgets_created_by", ["created_by"]),
    ("fund_transactions", "ix_fund_transactions_created_by", ["created_by"]),
    ("approval_workflows", "ix_approval_workflows_created_by", ["created_by"]),
    ("approval_nodes", "ix_approval_nodes_workflow_id", ["workflow_id"]),
    ("approval_tasks", "ix_approval_tasks_submitter_id", ["submitter_id"]),
    ("approval_records", "ix_approval_records_task_id", ["task_id"]),
    ("project_files", "ix_project_files_uploaded_by", ["uploaded_by"]),
    ("village_attachments", "ix_village_attachments_created_by", ["created_by"]),
    ("villages", "ix_villages_organization_id", ["organization_id"]),
    # ── 状态/日期查询索引（经常 WHERE/ORDER BY 但无索引）──
    ("approval_workflows", "ix_approval_workflows_is_active", ["is_active"]),
    ("approval_tasks", "ix_approval_tasks_status", ["status"]),
    ("approval_tasks", "ix_approval_tasks_created_at", ["created_at"]),
    ("supported_villages", "ix_supported_villages_county", ["county"]),
    ("supported_villages", "ix_supported_villages_department", ["department"]),
    ("funds", "ix_funds_status", ["status"]),
    ("funds", "ix_funds_fund_type", ["fund_type"]),
    ("projects", "ix_projects_status", ["status"]),
    ("projects", "ix_projects_village_id", ["village_id"]),
    # ── 审计日志索引（测试引用）──
    ("audit_logs", "ix_audit_logs_user_id", ["user_id"]),
]

# 向后兼容别名（测试/system_health 引用）
INDEX_DEFINITIONS = EXTRA_INDEXES
COMPOSITE_INDEXES = []


def _validate_columns(engine, table_name, index_name, columns, inspector=None):
    """验证索引列在目标表中存在，返回缺失列列表。

    Args:
        inspector: 可选的已构建 ``Inspector``。``create_indexes`` 循环内复用
            同一个实例——SQLAlchemy 的 Inspector 自带 reflection 缓存
            （``get_table_names`` / ``get_columns`` 均经 ``@reflection.cache``），
            复用它同时消除 N 次 inspect() 构造与 N 次重复元数据查询
            （R28 低危项）。缺省时自行构建，保持旧签名兼容。
    """
    insp = inspector if inspector is not None else inspect(engine)
    if table_name not in insp.get_table_names():
        return None  # 表不存在
    existing_cols = {c["name"] for c in insp.get_columns(table_name)}
    missing = [c for c in columns if c not in existing_cols]
    return missing


def create_indexes(engine=None):
    """
    创建 EXTRA_INDEXES 中的性能优化索引，并验证列是否存在。

    在应用启动时调用，使用 CREATE INDEX IF NOT EXISTS 确保幂等性。
    """
    if engine is None:
        logger.warning("create_indexes: engine is None, skipping")
        return

    created = 0
    skipped = 0
    errors = 0

    # R28：单次构建 inspector 并全程复用（其 reflection 缓存同时省掉重复
    # get_table_names/get_columns 查询），旧实现每条索引都 inspect(engine) 一次。
    inspector = inspect(engine)

    with engine.connect() as conn:
        for table_name, index_name, columns in EXTRA_INDEXES:
            # 启动时验证列名有效性
            missing = _validate_columns(engine, table_name, index_name, columns, inspector=inspector)
            if missing is None:
                skipped += 1
                continue
            if missing:
                logger.warning("索引 %s 引用不存在的列: %s，跳过创建", index_name, missing)
                errors += 1
                continue

            col_list = ", ".join(columns)
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({col_list})"
            try:
                conn.execute(text(sql))
                created += 1
            except Exception as e:
                logger.warning(f"创建索引 {index_name} 失败: {e}")
                errors += 1
        conn.commit()

    logger.info(f"索引创建完成: {created} 成功, {skipped} 跳过, {errors} 失败")


def drop_indexes(engine=None):
    """删除 EXTRA_INDEXES 中的所有复合索引。"""
    if engine is None:
        logger.warning("drop_indexes: engine is None, skipping")
        return

    dropped = 0
    errors = 0

    with engine.connect() as conn:
        for table_name, index_name, _ in EXTRA_INDEXES:
            sql = f"DROP INDEX IF EXISTS {index_name}"
            try:
                conn.execute(text(sql))
                dropped += 1
            except Exception as e:
                logger.warning(f"删除索引 {index_name} 失败: {e}")
                errors += 1
        conn.commit()

    logger.info(f"索引删除完成: {dropped} 成功, {errors} 失败")


def analyze_table_stats(engine=None):
    """分析表统计信息（SQLite 使用 ANALYZE 命令），返回表统计字典。"""
    if engine is None:
        logger.warning("analyze_table_stats: engine is None, skipping")
        return {}

    stats = {}
    with engine.connect() as conn:
        try:
            conn.execute(text("ANALYZE"))
            conn.commit()
            # 收集所有用户表的行数统计
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            )
            for (table_name,) in result.fetchall():
                try:
                    # nosec B608 — sqlite_master 系统表名
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM [{table_name}]"))  # nosec B608
                    row_count = count_result.scalar()
                    stats[table_name] = {"row_count": row_count}
                except Exception:
                    stats[table_name] = {"row_count": 0}
            logger.info("表统计信息分析完成")
        except Exception as e:
            logger.warning(f"分析表统计信息失败: {e}")
    return stats
