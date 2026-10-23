"""W27（v1.16.5）：清理死模型 ``BudgetRecord`` 的 ``budget_records`` 表

Revision ID: r37_drop_budget_records_001
Revises: r36_drop_rural_tasks_001

## 背景（W26 P1「死字段/死模型清理」）

``BudgetRecord``（``app/models/fund.py``）是**彻底的死模型**，W27 实证：

* 全仓仅剩 3 处出现：类定义、``models/__init__.py`` 注册、一处注释提及；
* **没有任何端点 / 服务 / 迁移使用它**（真正的预算功能用 ``FundBudget``，
  见 ``api/v1/fund_budgets.py``，后者带 ``organization_id`` 与 ``created_by``）；
* 它本身缺 ``organization_id`` / ``created_by``，即使被用也无法做数据域隔离。

保留它只会误导维护者以为"预算还有第二套表"。产品口径：**删除**。

## 与 ``annual_income`` 的区别（本轮暂不动）

``annual_income`` 自第 3 轮起已**停止读取**（人均纯收入统一到 ``village_income``），
但它的模型仍被 ``village_cascade_delete_service`` 的清理清单引用，
且需同步更新级联删除逻辑与相关测试 —— 属更大一批，留待后续单独迁移。
本迁移**只**处理确认为零引用的 ``budget_records``。

## 安全策略（沿用 ``r35`` 三分支契约）

    表不存在        → 跳过（幂等）
    存在且 0 行     → DROP TABLE
    存在且有数据    → ALTER TABLE ... RENAME TO legacy_budget_records（数据保留）

即：空表一定被清掉；有数据的表绝不丢一行；升级永远成功。

## 与升级演练的契约

``backend/scripts/gate_baselines/upgrade_legacy_tables.json`` 的 ``legacy_tables``
必须加入 ``budget_records``，否则 ``scripts/upgrade_rehearsal.py`` 会把
"表消失"判为数据丢失并使演练失败。

## downgrade

把 ``legacy_budget_records`` 改回原名（尽力而为）；已删除的空表不重建
（ORM 模型已移除，重建空表没有意义）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r37_drop_budget_records_001"
down_revision = "r36_drop_rural_tasks_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r37")

# 表名来自本模块常量（非用户输入），无注入面
RETIRED_TABLES = ("budget_records",)

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
                    "r37：%s 有 %d 行但归档表 %s 已存在，保留原表不处理（需人工确认）",
                    name, count, archive,
                )
                skipped.append(name)
                continue
            bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (name, archive)))  # nosec B608
            archived.append(name)
            logger.warning(
                "r37：%s 有 %d 行历史数据，已改名为 %s 归档（数据保留，退出活跃 schema）",
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
            "r37 迁移完成：删除空表 %s；改名归档 %s；跳过 %s",
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
        logger.info("r37 回滚完成：从归档恢复 %s（已删除的空表不重建）", restored)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
