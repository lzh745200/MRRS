"""W27（v1.16.5）：清理 ``annual_infrastructure`` 的"年份写死"死列

Revision ID: r39_prune_annual_infra_cols_001
Revises: r38_drop_annual_income_001

## 背景（W26-P0-2 同类反模式 + P1 死字段清理）

``annual_infrastructure`` 沿用与已删 ``annual_income`` **同一种反模式**：把年份
写进列名（``road_km_2025``、``infrastructure_investment_2026``、``…_total``…），
于是每过一年就要改一次模型。W27 扫描确认这 9 个列在 ``app/``（模型定义之外）
与 ``frontend/src`` **零引用** —— 真正在用的行式表是 ``infrastructure_improvement``。

> 注意：**表本身仍有使用**（``effectiveness_service`` 用 ``COUNT(id)`` 判断"当年是否
> 填报过"），因此本次只清理列，**不删表**。``AnnualIndustry`` 的 7 个同类列同批
> 情况，留待后续单独迁移（避免单次迁移面过大）。

## 安全策略（沿用 r35/r36 的**三分支**契约，下沉到列级）

    列不存在            → 跳过（幂等）
    列存在且整列为空/0  → DROP COLUMN
    列存在且有数据      → RENAME COLUMN 为 legacy_<列名>（数据保留）

即：完全没填过的列直接清掉（schema 变干净）；**填过数据的列绝不丢一行**，
改名为 ``legacy_*`` 归档，留给人工比对/迁移。

## downgrade

把 ``legacy_<列名>`` 改回原名（尽力而为）；已删除的空列不重建
（模型已无该字段，重建空列没有意义）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r39_prune_annual_infra_cols_001"
down_revision = "r38_drop_annual_income_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r39")

TABLE = "annual_infrastructure"

# 年份写死的死列（表名/列名来自本模块常量，非用户输入，无注入面）
DEAD_COLUMNS = (
    "infrastructure_investment_2025",
    "infrastructure_investment_2026",
    "infrastructure_investment_total",
    "road_km_2025",
    "housing_renovations_2025",
    "water_facilities_2025",
    "cultural_squares_2025",
    "bookhouses_internet_cubs_2025",
    "other_infrastructure_2025",
)

ARCHIVE_PREFIX = "legacy_"


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_data(bind, table, column) -> bool:
    """该列是否有任何"非空且非零"的值。"""
    sql = sa.text(
        f'SELECT COUNT(*) FROM "{table}" '
        f'WHERE "{column}" IS NOT NULL AND "{column}" != 0'
    )  # nosec B608
    return int(bind.execute(sql).scalar() or 0) > 0


def apply_cleanup(bind):
    """执行列级清理，返回 ``{"dropped": [...], "archived": [...], "skipped": [...]}``。

    抽成纯函数便于单测覆盖三种分支（列不存在 / 全空 / 有数据）。
    """
    dropped: list[str] = []
    archived: list[str] = []
    skipped: list[str] = []

    if TABLE not in {t for t in sa.inspect(bind).get_table_names()}:
        # 整表都不存在 → 全部列自然不存在
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
                    "r39：%s.%s 有数据但归档列 %s 已存在，保留原列不处理（需人工确认）",
                    TABLE, column, target,
                )
                skipped.append(column)
                continue
            bind.execute(sa.text(
                f'ALTER TABLE "{TABLE}" RENAME COLUMN "{column}" TO "{target}"'
            ))  # nosec B608
            archived.append(column)
            logger.warning(
                "r39：%s.%s 有历史数据，已改名为 %s 归档（数据保留）",
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
            "r39 迁移完成：删除空列 %d 个 %s；改名归档 %d 个 %s；跳过 %d 个",
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
        logger.info("r39 回滚完成：从归档列恢复 %d 个（已删除的空列不重建）", len(restored))
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
