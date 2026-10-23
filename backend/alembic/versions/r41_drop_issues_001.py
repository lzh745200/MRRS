"""W27（v1.16.5）：清理死表 ``issues``（问题追踪骨架）

Revision ID: r41_drop_issues_001
Revises: r40_prune_annual_industry_cols_001

## 背景（W26 P1「死字段/死模型清理」）

``Issue`` 模型（表 ``issues``）是**只做了一半的功能骨架**，W27 实测全仓零生产引用：

* **无任何端点/服务使用** —— `api/v1/feedback.py` 的 `GET/POST /api/v1/feedback`
  只用同文件的 `Feedback` 模型；
* **前端无对应页面**；
* 它自带的 6 个扩展字段（``steps_to_reproduce`` / ``expected_behavior`` /
  ``actual_behavior`` / ``version_found`` / ``version_fixed`` / ``assignee``）
  本就零引用 —— 那正是"问题追踪"功能做到一半留下的痕迹。

处置：删表（而不是只删 6 个字段）。理由：剩下的 ``title``/``description``/
``priority``/``status``/``category``/``reporter``/``tags``/``severity``/
``environment`` 也**没有任何写入路径** —— 保留一张永远为空的表，只会让人误以为
"问题追踪"功能可用。

> **同文件的 ``Feedback``（表 ``feedback``）保留** —— 它是**活的功能**
> （``/api/v1/feedback`` 已注册并在用），其未接线的扩展字段是"可扩展点"而非死字段。

## 安全策略（沿用 r35 三分支契约）

    表不存在        → 跳过（幂等）
    存在且 0 行     → DROP TABLE
    存在且有数据    → RENAME TO legacy_issues（数据保留，退出活跃 schema）

## 与升级演练的契约

``backend/scripts/gate_baselines/upgrade_legacy_tables.json`` 的 ``legacy_tables``
必须加入 ``issues``。

## downgrade

把 ``legacy_issues`` 改回原名（尽力而为）；已删除的空表不重建
（ORM 模型已移除，重建空表没有意义）。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r41_drop_issues_001"
down_revision = "r40_prune_annual_industry_cols_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r41")

# 表名来自本模块常量（非用户输入），无注入面
RETIRED_TABLES = ("issues",)

ARCHIVE_PREFIX = "legacy_"


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def _row_count(bind, name):
    return int(bind.execute(sa.text("SELECT COUNT(*) FROM " + name)).scalar() or 0)  # nosec B608


def apply_cleanup(bind):
    """执行清理，返回 ``{"dropped": [...], "archived": [...], "skipped": [...]}``。"""
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
                logger.warning(
                    "r41：%s 有 %d 行但归档表 %s 已存在，保留原表不处理（需人工确认）",
                    name, count, archive,
                )
                skipped.append(name)
                continue
            bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (name, archive)))  # nosec B608
            archived.append(name)
            logger.warning(
                "r41：%s 有 %d 行历史数据，已改名为 %s 归档（数据保留，退出活跃 schema）",
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
            "r41 迁移完成：删除空表 %s；改名归档 %s；跳过 %s",
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
        logger.info("r41 回滚完成：从归档恢复 %s（已删除的空表不重建）", restored)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
