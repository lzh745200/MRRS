"""W28（v1.18.6）：清理 26 个「模型里声明、全仓零引用」的死字段

Revision ID: r43_prune_dead_columns_001
Revises: r42_align_stack_columns_001

## 背景

`backend/scripts/scan_dead_columns.py` 的判定口径（保守、宁漏不误删）：

1. 列名在 `app/`（模型定义文件之外）**零次**出现；
2. 列名在 `frontend/src` 下**零次**出现；
3. 不是主键/外键/审计列/软删列。

扫出 **26 条**。这 26 条既无写入路径、也无读取路径 —— 留着它们等于让 schema
撒谎（让人以为「预期效益」「告警渠道」「配置漂移检测」这些功能存在）。这正是
r41 删 `issues` 表时的同一条理由：**做了一半的骨架比没有更危险**。

## 安全策略（沿用 r35/r36/r39 的**三分支**契约，列级）

    列不存在            → 跳过（幂等）
    列存在且整列为空/0  → DROP COLUMN（schema 变干净）
    列存在且有数据      → RENAME COLUMN 为 legacy_<列名>（**数据一行不丢**）

迁移自身会按数据实况分支，因此**不需要产品先拍板删哪条**：
真正填过数据的列会被自动归档改名，留待人工确认是否补功能。

以开发库实测（2026-10-25）为例：
`funds.budget_status` 12 行有值、`machine_codes.restrict_permissions` 1 行有值
→ 这两列会被归档为 `legacy_*`；其余 24 列为空 → 直接删除。

## 为什么一次性处理 26 条而不是逐条发版

它们同属一次扫描结论、同一种处置方式、同一套三分支逻辑；拆成 26 个迁移会让
`alembic upgrade head` 多 25 次全表检查，且升级演练的失败面变大。
表名/列名全部来自本模块常量（非用户输入），`# nosec B608` 已按 r39 同理标注。

## downgrade

把 `legacy_<列名>` 改回原名（尽力而为）；已删除的空列不重建
（模型已无该字段，重建空列只会再造一次死字段）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r43_prune_dead_columns_001"
down_revision = "r42_align_stack_columns_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r43")

# (表名, 列名)：来自 scripts/scan_dead_columns.py 的实测输出。
# 全部为字面量常量，无用户输入拼接。
DEAD_COLUMNS: tuple[tuple[str, str], ...] = (
    # ── 经费 ──
    ("allocation_order_items", "account"),
    ("allocation_order_items", "transferred_at"),
    ("fund_allocation_orders", "received_by"),
    ("funds", "budget_status"),
    ("fund_transfer_vouchers", "local_project_code"),
    ("fund_transfer_vouchers", "military_project_code"),
    # ── 告警 / 监控 ──
    ("alert_rules", "channels"),
    ("alert_rules", "email_recipients"),
    ("system_monitor", "db_query_time"),
    # ── 项目 ──
    ("projects", "expected_economic_benefit"),
    ("projects", "expected_military_benefit"),
    ("projects", "fund_source_category"),
    ("projects", "region_code"),
    ("projects", "total_budget_estimate"),
    # ── 审计 ──
    ("data_export_logs", "file_size_bytes"),
    ("api_access_logs", "request_body"),
    # ── 工作台 ──
    ("hidden_dashboard_activities", "hidden_at"),
    # ── 产业 ──
    ("cactus_fruit_plots", "karst_adaptation_score"),
    ("cactus_fruit_plots", "plant_density"),
    ("tea_plantations", "quality_score"),
    # ── 下级实例（配置漂移检测未接线）──
    ("subordinate_instances", "last_config_applied_at"),
    ("subordinate_instances", "last_config_hash"),
    # ── 组织 / 帮扶村 ──
    ("organizations", "region_code"),
    ("supported_villages", "region_code"),
    ("village_populations", "veteran_village_committee"),
    ("village_populations", "veteran_village_secretary"),
    # ── 成效评估 ──
    ("effectiveness_evaluations", "report_path"),
    # ── 机器码 ──
    ("machine_codes", "restrict_permissions"),
)

ARCHIVE_PREFIX = "legacy_"


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_data(bind, table: str, column: str) -> bool:
    """该列是否有任何"非空且非零"的值（0/空串视为未填）。"""
    sql = sa.text(
        f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NOT NULL AND "{column}" != 0'
    )  # nosec B608
    return int(bind.execute(sql).scalar() or 0) > 0


def apply_cleanup(bind) -> dict:
    """执行列级清理。

    返回 ``{"dropped": [...], "archived": [...], "skipped": [...]}``，
    元素形如 ``"表.列"``。抽成纯函数便于单测覆盖三种分支。
    """
    dropped: list[str] = []
    archived: list[str] = []
    skipped: list[str] = []

    tables = _table_names(bind)
    for table, column in DEAD_COLUMNS:
        label = f"{table}.{column}"
        if table not in tables:
            skipped.append(label)
            continue
        existing = _columns(bind, table)
        if column not in existing:
            skipped.append(label)
            continue
        if _has_data(bind, table, column):
            target = ARCHIVE_PREFIX + column
            if target in existing:
                logger.warning(
                    "r43：%s.%s 有数据但归档列 %s 已存在，保留原列不处理（需人工确认）",
                    table, column, target,
                )
                skipped.append(label)
                continue
            bind.execute(sa.text(
                f'ALTER TABLE "{table}" RENAME COLUMN "{column}" TO "{target}"'
            ))  # nosec B608
            archived.append(label)
            logger.warning(
                "r43：%s.%s 有历史数据，已改名为 %s 归档（数据保留）", table, column, target
            )
        else:
            bind.execute(sa.text(f'ALTER TABLE "{table}" DROP COLUMN "{column}"'))  # nosec B608
            dropped.append(label)
    return {"dropped": dropped, "archived": archived, "skipped": skipped}


def upgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        result = apply_cleanup(bind)
        logger.info(
            "r43 迁移完成：删除空列 %d 个；改名归档 %d 个 %s；跳过 %d 个",
            len(result["dropped"]), len(result["archived"]), result["archived"],
            len(result["skipped"]),
        )
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))


def downgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        tables = _table_names(bind)
        restored: list[str] = []
        for table, column in DEAD_COLUMNS:
            if table not in tables:
                continue
            existing = _columns(bind, table)
            archive = ARCHIVE_PREFIX + column
            if archive in existing and column not in existing:
                bind.execute(sa.text(
                    f'ALTER TABLE "{table}" RENAME COLUMN "{archive}" TO "{column}"'
                ))  # nosec B608
                restored.append(f"{table}.{column}")
        logger.info("r43 回滚完成：从归档列恢复 %d 个（已删除的空列不重建）", len(restored))
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
