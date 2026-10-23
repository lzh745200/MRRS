"""W27（v1.16.5）：清理死表 ``annual_income``（人均纯收入列式快照）

Revision ID: r38_drop_annual_income_001
Revises: r37_drop_budget_records_001

## 背景（W26-P0-2 的收尾 + P1「死字段/死模型清理」）

``annual_income`` 是**列式**年度收入快照（``per_capita_income_2020..2025`` 每年一列）。
W26 全栈检测确认它是 P0-2「指标口径不一致」的根源：

* 工作台读它、其余 5 处读行式 ``village_income`` → **同一指标两个数字**；
* 该表**全仓 0 处写入**（真实数据一直写 ``village_income``），dev 库 **0 行**；
* 年份列**写死到 2025** —— 2026 年起永远取不到当年值。

第 3 轮已把全部读取方切到 ``village_income``（``services/metrics_service`` 唯一实现），
本轮删除模型与其级联删除清单项，迁移负责数据库侧收尾。

> ⚠️ 注意区分：``households.annual_income``（户年收入，单位**元**）是**另一个字段**，
> 与本次删除无关，未受影响。

## 安全策略（沿用 ``r35`` 三分支契约）

    表不存在        → 跳过（幂等）
    存在且 0 行     → DROP TABLE
    存在且有数据    → ALTER TABLE ... RENAME TO legacy_annual_income（数据保留）

即：空表一定被清掉；**有数据的表绝不丢一行**（若某些历史部署真有数据，
会完整归档为 ``legacy_annual_income`` 供人工比对/迁移）。

## 与升级演练的契约

``backend/scripts/gate_baselines/upgrade_legacy_tables.json`` 的 ``legacy_tables``
必须加入 ``annual_income``，否则 ``scripts/upgrade_rehearsal.py`` 会把
"表消失"判为数据丢失并使演练失败。

## downgrade

把 ``legacy_annual_income`` 改回原名（尽力而为）；已删除的空表不重建
（ORM 模型已移除，重建空表没有意义）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r38_drop_annual_income_001"
down_revision = "r37_drop_budget_records_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r38")

# 表名来自本模块常量（非用户输入），无注入面
RETIRED_TABLES = ("annual_income",)

ARCHIVE_PREFIX = "legacy_"


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def _row_count(bind, name):
    return int(bind.execute(sa.text("SELECT COUNT(*) FROM " + name)).scalar() or 0)  # nosec B608


def apply_cleanup(bind):
    """执行清理，返回 ``{"dropped": [...], "archived": [...], "skipped": [...]}``。

    抽成独立纯函数，便于单测直接喂 sqlite 连接、覆盖三种分支
    （表不存在 / 空表 / 有数据）。
    """
    dropped = []
    archived = []
    skipped = []
    for name in RETIRED_TABLES:
        if not _has_table(bind, name):
            skipped.append(name)
            continue
        count = _row_count(bind, name)
        if count:
            archive = ARCHIVE_PREFIX + name
            if _has_table(bind, archive):
                # 归档表已存在（重复执行/人工处理过）：保持原表不动，避免覆盖既有归档
                logger.warning(
                    "r38：%s 有 %d 行但归档表 %s 已存在，保留原表不处理（需人工确认）",
                    name, count, archive,
                )
                skipped.append(name)
                continue
            bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (name, archive)))  # nosec B608
            archived.append(name)
            logger.warning(
                "r38：%s 有 %d 行历史数据，已改名为 %s 归档（数据保留，退出活跃 schema）",
                name, count, archive,
            )
        else:
            bind.execute(sa.text('DROP TABLE "%s"' % name))  # nosec B608
            dropped.append(name)
    return {"dropped": dropped, "archived": archived, "skipped": skipped}


def upgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        result = apply_cleanup(bind)
        logger.info(
            "r38 迁移完成：删除空表 %s；改名归档 %s；跳过 %s",
            result["dropped"], result["archived"], result["skipped"],
        )
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))


def downgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        restored = []
        for name in RETIRED_TABLES:
            archive = ARCHIVE_PREFIX + name
            if _has_table(bind, archive) and not _has_table(bind, name):
                bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (archive, name)))  # nosec B608
                restored.append(name)
        logger.info("r38 回滚完成：从归档恢复 %s（已删除的空表不重建）", restored)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
