"""W27（v1.16.5）：清理 ``annual_industry`` 的"年份写死"死列

Revision ID: r40_prune_annual_industry_cols_001
Revises: r39_prune_annual_infra_cols_001

## 背景
与 ``r39_prune_annual_infra_cols_001`` 同批次：``annual_industry`` 把年份写进列名
（``industry_investment_2025/2026/total``、``industry_2025_*``），
每过一年就要改一次模型。W27 扫描确认这 7 列在 ``app/``（模型外）与
``frontend/src`` **零引用**；真正的行式明细在 ``industry_support``
（``investment`` / ``planting_breeding`` / ``workshop`` / ``rural_tourism`` / ``other_industry``，按 year 分行）。

> 表本身仍被 ``effectiveness_service`` 用作「当年是否填报」的 ``COUNT(id)`` 信号，
> 因此**只清列、不删表**。

## 安全策略（列级三分支，同 r39）
    列不存在            → 跳过（幂等）
    列存在且整列为空/0  → DROP COLUMN
    列存在且有数据      → RENAME COLUMN 为 legacy_<列名>（数据保留）
    归档列已存在        → 保留原列不处理（防覆盖既有归档）
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r40_prune_annual_industry_cols_001"
down_revision = "r39_prune_annual_infra_cols_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r40")

TABLE = "annual_industry"

# 年份写死的死列（本模块常量，无注入面）
DEAD_COLUMNS = (
    "industry_investment_2025",
    "industry_investment_2026",
    "industry_investment_total",
    "industry_2025_planting_and_breeding",
    "industry_2025_workshops",
    "industry_2025_rural_tourism",
    "industry_2025_other",
)

ARCHIVE_PREFIX = "legacy_"


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_data(bind, table, column) -> bool:
    sql = sa.text(
        f'SELECT COUNT(*) FROM "{table}" '
        f'WHERE "{column}" IS NOT NULL AND "{column}" != 0'
    )  # nosec B608
    return int(bind.execute(sql).scalar() or 0) > 0


def apply_cleanup(bind):
    """执行列级清理，返回 ``{"dropped": [...], "archived": [...], "skipped": [...]}``。"""
    dropped: list[str] = []
    archived: list[str] = []
    skipped: list[str] = []

    if TABLE not in {t for t in sa.inspect(bind).get_table_names()}:
        return {"dropped": [], "archived": [], "skipped": list(DEAD_COLUMNS)}

    existing = _columns(bind, TABLE)
    for column in DEAD_COLUMNS:
        if column not in existing:
            skipped.append(column)
            continue
        if _has_data(bind, TABLE, column):
            target = ARCHIVE_PREFIX + column
            if target in existing:
                logger.warning(
                    "r40：%s.%s 有数据但归档列 %s 已存在，保留原列不处理（需人工确认）",
                    TABLE, column, target,
                )
                skipped.append(column)
                continue
            bind.execute(sa.text(
                f'ALTER TABLE "{TABLE}" RENAME COLUMN "{column}" TO "{target}"'
            ))  # nosec B608
            archived.append(column)
            logger.warning(
                "r40：%s.%s 有历史数据，已改名为 %s 归档（数据保留）",
                TABLE, column, target,
            )
        else:
            bind.execute(sa.text(f'ALTER TABLE "{TABLE}" DROP COLUMN "{column}"'))  # nosec B608
            dropped.append(column)
    return {"dropped": dropped, "archived": archived, "skipped": skipped}


def upgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        result = apply_cleanup(bind)
        logger.info(
            "r40 迁移完成：删除空列 %d 个 %s；改名归档 %d 个 %s；跳过 %d 个",
            len(result["dropped"]), result["dropped"],
            len(result["archived"]), result["archived"],
            len(result["skipped"]),
        )
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))


def downgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        if TABLE not in {t for t in sa.inspect(bind).get_table_names()}:
            return
        existing = _columns(bind, TABLE)
        restored = []
        for column in DEAD_COLUMNS:
            archive = ARCHIVE_PREFIX + column
            if archive in existing and column not in existing:
                bind.execute(sa.text(
                    f'ALTER TABLE "{TABLE}" RENAME COLUMN "{archive}" TO "{column}"'
                ))  # nosec B608
                restored.append(column)
        logger.info("r40 回滚完成：从归档列恢复 %d 个（已删除的空列不重建）", len(restored))
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
