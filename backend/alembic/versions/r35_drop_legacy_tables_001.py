"""R35（v1.16.2）：清理 W22 遗留的 6 张零引用表（空表删除 / 有数据改名归档）

Revision ID: r35_drop_legacy_tables_001
Revises: r34_effectiveness_fk_rebuild_001

## 背景

W22（v1.14.0）下线相关功能时移除了 ORM 模型定义，但数据库表未一并清理。
实测确认这 6 张表：① 不在 app.models.metadata 中（create_all 不会重建）；
② 代码零引用；③ 本机库 0 行。

    comments / messages_extended / sentiment_keywords /
    sentiment_reports / workflow_definitions / workflow_instances

保留代价：schema 与模型长期不一致，新人误以为功能仍在；analytics、备份体积、
升级排查都会多出噪声。

## 安全策略（v1.16.2 重做：绝不丢数据、绝不阻断升级）

v1.16.0 的原实现是「表非空即 raise」，升级演练（从上一个 Release 建库并每表播种一行）
直接暴露两个问题：老用户库里这些表可能有历史数据 → 升级中断、新版本起不来；
即便为空，演练的「无表丢失 / 行数不变」基线也判为数据丢失。故重做为：

    表不存在        → 跳过（幂等）
    存在且 0 行     → DROP TABLE（真正的"空表清除"）
    存在且有数据    → ALTER TABLE ... RENAME TO legacy_<表名>
                      （数据完整保留在库里备查，只是退出活跃 schema）

即：空表一定被清掉；有数据的表绝不丢一行；升级永远成功。

## 与升级演练的契约

backend/scripts/gate_baselines/upgrade_legacy_tables.json 声明这 6 张"允许消失"的表：
演练据此接受两种终态 —— 原表名消失（且旧库该表 0 行）或改名为 legacy_<表名>（行数不变）。
新增任何"允许消失"的表都必须同时更新该清单，否则演练照样报"无表丢失"失败。

## downgrade

把 legacy_<表名> 改回原名（尽力而为，仅恢复名字，不重建已删的空表）。
"""

import json
import logging
import os

import sqlalchemy as sa
from alembic import op

revision = "r35_drop_legacy_tables_001"
down_revision = "r34_effectiveness_fk_rebuild_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r35")

# backend/alembic/versions/ 上溯三层 = backend/
LEGACY_TABLES_MANIFEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "gate_baselines",
    "upgrade_legacy_tables.json",
)

# 顺序敏感：子表在前（workflow_instances 引用 workflow_definitions）
LEGACY_TABLES = (
    "workflow_instances",
    "workflow_definitions",
    "comments",
    "messages_extended",
    "sentiment_keywords",
    "sentiment_reports",
)

ARCHIVE_PREFIX = "legacy_"


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def _row_count(bind, name):
    # 表名取自本模块常量白名单（非用户输入），无注入面
    return int(bind.execute(sa.text("SELECT COUNT(*) FROM " + name)).scalar() or 0)  # nosec B608


def apply_cleanup(bind):
    """执行清理，返回 dropped / archived / skipped 三个列表。

    抽成独立函数便于单测直接喂 sqlite 连接，覆盖三种分支。
    """
    dropped = []
    archived = []
    skipped = []
    for name in LEGACY_TABLES:
        if not _has_table(bind, name):
            skipped.append(name)
            continue
        count = _row_count(bind, name)
        if count:
            archive = ARCHIVE_PREFIX + name
            if _has_table(bind, archive):
                # 归档表已存在（重复执行/人工处理过）：保持原表不动，避免覆盖既有归档
                logger.warning(
                    "r35：%s 有 %d 行但归档表 %s 已存在，保留原表不处理（需人工确认）",
                    name, count, archive,
                )
                skipped.append(name)
                continue
            bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (name, archive)))  # nosec B608
            archived.append(name)
            logger.warning(
                "r35：%s 有 %d 行历史数据，已改名为 %s 归档（数据保留，退出活跃 schema）",
                name, count, archive,
            )
        else:
            bind.execute(sa.text('DROP TABLE "%s"' % name))  # nosec B608
            dropped.append(name)
    return {"dropped": dropped, "archived": archived, "skipped": skipped}


def upgrade():
    bind = op.get_bind()
    # 关闭外键约束，避免删父表时被子表引用关系阻断（SQLite 语义，PRAGMA 仅当前连接有效）
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        result = apply_cleanup(bind)
        logger.info(
            "r35 迁移完成：删除空表 %s；改名归档 %s；跳过 %s",
            result["dropped"], result["archived"], result["skipped"],
        )
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))


def downgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        restored = []
        for name in LEGACY_TABLES:
            archive = ARCHIVE_PREFIX + name
            if _has_table(bind, archive) and not _has_table(bind, name):
                bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (archive, name)))  # nosec B608
                restored.append(name)
        logger.info("r35 回滚完成：从归档恢复 %s（已删除的空表不重建）", restored)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))


def manifest_tables():
    """读取演练用清单（供脚本/文档共用），失败时回退到常量。"""
    try:
        with open(LEGACY_TABLES_MANIFEST, encoding="utf-8") as fp:
            payload = json.load(fp)
        tables = payload.get("legacy_tables")
        if isinstance(tables, list) and tables:
            return [str(t) for t in tables]
    except (OSError, ValueError) as exc:  # pragma: no cover - 清单损坏时回退
        logger.warning("r35：读取遗留表清单失败，回退内置常量：%s", exc)
    return list(LEGACY_TABLES)
