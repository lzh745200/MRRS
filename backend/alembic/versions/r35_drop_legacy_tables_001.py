"""R35（v1.15.17）：清理 W22 遗留的 6 张零引用空表

Revision ID: r35_drop_legacy_tables_001
Revises: r34_effectiveness_fk_rebuild_001

## 背景（R34 报告列为后续专项，本次收口）

W22（v1.14.0）下线相关功能时移除了 ORM 模型定义，但数据库表未一并清理。
实测确认这 6 张表：

1. **不在 `app.models.metadata` 中**（`create_all` 不会重建，删了不会复活）；
2. **代码零引用**（全仓 grep 无引用）；
3. **全部 0 行**（本机库实测）。

```
comments / messages_extended / sentiment_keywords /
sentiment_reports / workflow_definitions / workflow_instances
```

保留代价：schema 与模型长期不一致，新人误以为功能仍在；analytics、
备份体积、升级排查都会多出噪音。

## 安全性设计

- 逐表 `EXISTS` 检查 → **幂等**，重复执行安全；
- 删除前**断言表为空**（有数据直接 raise，绝不静默丢数据）；
- 先删子表（`workflow_instances` → `workflow_definitions`），再删其余；
- `comments` 存在自引用外键（`parent_id -> comments.id`），SQLite `DROP TABLE`
  会连带移除，无需先清外键。

## downgrade

**不可逆**：表内数据已确认为空，重建空表没有意义（且无法恢复列级的
历史索引/约束语义）。按 R34 决策显式 raise NotImplementedError。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r35_drop_legacy_tables_001"
down_revision = "r34_effectiveness_fk_rebuild_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r35")

# 顺序敏感：子表在前（workflow_instances 引用 workflow_definitions）
_LEGACY_TABLES = (
    "workflow_instances",
    "workflow_definitions",
    "comments",
    "messages_extended",
    "sentiment_keywords",
    "sentiment_reports",
)


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _row_count(name: str) -> int:
    # 表名取自本模块常量白名单（非用户输入），无注入面
    return int(
        op.get_bind().execute(sa.text("SELECT COUNT(*) FROM " + name)).scalar() or 0  # nosec B608
    )


def upgrade() -> None:
    bind = op.get_bind()
    # 关闭外键约束，避免删父表时被子表引用关系阻断（SQLite 语义，PRAGMA 仅当前连接有效）
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        dropped = []
        for name in _LEGACY_TABLES:
            if not _table_exists(name):
                continue
            count = _row_count(name)
            if count:
                raise RuntimeError(
                    "【r35 中止】legacy 表 %s 仍有 %d 行数据，删除会丢数据。"
                    "请先确认这些数据是否需要迁移到现行表，再从 _LEGACY_TABLES 移除该项。" % (name, count)
                )
            op.drop_table(name)
            dropped.append(name)
        logger.info("r35 迁移完成：清理 %d 张 legacy 空表 %s", len(dropped), dropped)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))


def downgrade() -> None:
    raise NotImplementedError(
        "r35 不可逆：被清理的 6 张表已被确认零引用且无数据，"
        "重建空表无法恢复任何信息。需要回滚请从备份库恢复。"
    )
