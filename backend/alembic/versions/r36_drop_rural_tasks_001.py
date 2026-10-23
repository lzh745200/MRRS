"""W27（v1.16.5）：下线 ``rural_tasks`` 表（空表删除 / 有数据改名归档）

Revision ID: r36_drop_rural_tasks_001
Revises: r35_drop_legacy_tables_001

## 背景（产品决策）

``rural_tasks``（乡村振兴工作任务）是**完整的功能孤岛**，W26 全栈检测实证：

* 前端源码 ``rural-tasks`` / ``ruralTasks`` **零引用** —— 乡村振兴页面
  （``views/ruralWorks/*``）自始至终走 ``/api/v1/rural-works``；
* 本机库该表 **0 行**；
* ``RuralTask`` 模型除自身 API（``api/v1/rural_tasks.py`` 9 个端点）与审计注册外
  **没有任何服务层消费**。

产品决定：**下线**。本批次已删除 ``api/v1/rural_tasks.py``、
``schemas/rural_task.py``、``models/rural_task.py`` 并从两处注册表移除，
故本迁移只负责**数据库侧**收尾。

## 安全策略（沿用 ``r35_drop_legacy_tables_001`` 的三分支契约）

    表不存在        → 跳过（幂等）
    存在且 0 行     → DROP TABLE
    存在且 0 行 < 有数据 → ALTER TABLE ... RENAME TO legacy_rural_tasks（数据保留）

即：空表一定被清掉；有数据的表绝不丢一行；升级永远成功。

## 与升级演练的契约

``backend/scripts/gate_baselines/upgrade_legacy_tables.json`` 的 ``legacy_tables``
必须同时加入 ``rural_tasks``，否则 ``scripts/upgrade_rehearsal.py`` 会把
"表消失"判为数据丢失并使演练失败。

## downgrade

把 ``legacy_rural_tasks`` 改回原名（尽力而为；已删除的空表不重建 —— ORM 模型已移除，
重建空表没有意义）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r36_drop_rural_tasks_001"
down_revision = "r35_drop_legacy_tables_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r36")

# 本迁移只处理这一张表；表名来自本模块常量（非用户输入），无注入面
RETIRED_TABLES = ("rural_tasks",)

ARCHIVE_PREFIX = "legacy_"


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def _row_count(bind, name):
    return int(bind.execute(sa.text("SELECT COUNT(*) FROM " + name)).scalar() or 0)  # nosec B608


def apply_cleanup(bind):
    """执行下线清理，返回 ``{"dropped": [...], "archived": [...], "skipped": [...]}``。

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
                    "r36：%s 有 %d 行但归档表 %s 已存在，保留原表不处理（需人工确认）",
                    name, count, archive,
                )
                skipped.append(name)
                continue
            bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (name, archive)))  # nosec B608
            archived.append(name)
            logger.warning(
                "r36：%s 有 %d 行历史数据，已改名为 %s 归档（数据保留，退出活跃 schema）",
                name, count, archive,
            )
        else:
            bind.execute(sa.text('DROP TABLE "%s"' % name))  # nosec B608
            dropped.append(name)
    return {"dropped": dropped, "archived": archived, "skipped": skipped}


def upgrade():
    bind = op.get_bind()
    # 关闭外键约束，避免删表时被引用关系阻断（SQLite 语义，PRAGMA 仅当前连接有效）
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        result = apply_cleanup(bind)
        logger.info(
            "r36 迁移完成：删除空表 %s；改名归档 %s；跳过 %s",
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
        logger.info("r36 回滚完成：从归档恢复 %s（已删除的空表不重建）", restored)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
