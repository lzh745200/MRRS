"""R35：三层对齐 —— ORM 模型与数据库 schema 收口

Revision ID: r42_align_stack_columns_001
Revises: r41_drop_issues_001

## 背景

「前后端及数据库 100% 对齐」审计发现 4 处 **ORM 模型 ↔ 数据库** 漂移。
它们都属于"迁移与模型各说各话"，单测全绿但真机行为与契约声明不一致：

1. ``tea_plantations.village_id`` / ``cactus_fruit_plots.village_id``
   —— W22 迁移（``w22_household_media_consumption_001``）已把列改名为
   ``supported_village_id``，但 ``app/models/industry.py`` 至今仍声明旧的
   ``village_id``（r34 迁移的注释里已记录该漂移，并跳过了这两个表的索引重建）。
   这两张表零业务引用，因此从未暴露。
2. ``household_members.remarks``
   —— W22 迁移建了 ``remarks`` 列，但 ``app/models/household.py`` 的
   ``HouseholdMember`` **没有声明**它：该列对 ORM 完全不可见，
   schema / service / 前端也都没有这个字段（三层全缺，只有数据库是对的）。
3. ``projects.region_code``
   —— ``region_code_001`` 迁移给 ``projects`` 加了 ``region_code``，
   但 ``app/models/project.py`` 未声明（``organizations`` / ``supported_villages``
   两张表都声明了，唯独 ``projects`` 漏了）。零业务引用。

## 处置

统一口径：**以数据库为准，把模型补齐**（不删任何列、不改已有迁移历史）：

- ``tea_plantations`` / ``cactus_fruit_plots``：模型列名改为 ``supported_village_id``，
  索引名同步改为 ``ix_tea_supported_village_id`` / ``ix_cactus_supported_village_id``。
  库里的旧索引名 ``ix_tea_village_id`` / ``ix_cactus_village_id`` 若存在则一并改名。
- ``household_members``：补 ``remarks VARCHAR(500)``（幂等 —— 已有则跳过）。
- ``projects``：补 ``region_code VARCHAR(20)``（幂等 —— 已有则跳过）。

所有改动**幂等**：列/索引已存在则跳过，可在任意旧库上安全重放。

## 与门禁的关系

本迁移完成后，``scripts/check_stack_alignment.py`` 的 B 轴（ORM 模型 ↔
"alembic upgrade head 后的空库"）必须为 0 漂移。

## downgrade

删除本次补齐的列（仅当其无业务数据时才有意义，故一律尽力而为），
并把 ``supported_village_id`` 改回 ``village_id``。
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "r42_align_stack_columns_001"
down_revision = "r41_drop_issues_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration.r42")

# 改名表：旧列名 → 新列名
RENAMED_COLUMNS = (
    ("tea_plantations", "village_id", "supported_village_id"),
    ("cactus_fruit_plots", "village_id", "supported_village_id"),
)

# 改名表对应的索引名
RENAMED_INDEXES = (
    ("tea_plantations", "ix_tea_village_id", "ix_tea_supported_village_id"),
    ("cactus_fruit_plots", "ix_cactus_village_id", "ix_cactus_supported_village_id"),
)

# 补齐列：表名 → (列名, 类型, 长度)
ADDED_COLUMNS = (
    ("household_members", "remarks", sa.String(500)),
    ("projects", "region_code", sa.String(20)),
)


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def _column_names(bind, table):
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_names(bind, table):
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def _index_columns(bind, table, index_name):
    """取某个索引的列名列表；索引不存在时返回空列表。"""
    for idx in sa.inspect(bind).get_indexes(table):
        if idx["name"] == index_name:
            return list(idx.get("column_names") or [])
    return []


def apply_alignment(bind):
    """执行对齐，返回 ``{"renamed_columns": [...], "renamed_indexes": [...], "added_columns": [...]}``。

    抽成纯函数便于单测覆盖三种分支（表不存在 / 已是目标名 / 需要改）。
    """
    renamed_columns = []
    renamed_indexes = []
    added_columns = []

    for table, old_name, new_name in RENAMED_COLUMNS:
        if not _has_table(bind, table):
            continue
        columns = _column_names(bind, table)
        if new_name in columns:
            # 已是目标列名 —— 幂等跳过（但旧索引名仍需处理）
            pass
        elif old_name in columns:
            with op.batch_alter_table(table) as batch:
                batch.alter_column(old_name, new_column_name=new_name)
            renamed_columns.append(f"{table}.{old_name}->{new_name}")
        else:
            logger.warning("r42：%s 既无 %s 也无 %s，跳过列改名", table, old_name, new_name)

    for table, old_name, new_name in RENAMED_INDEXES:
        if not _has_table(bind, table):
            continue
        indexes = _index_names(bind, table)
        if old_name in indexes and new_name not in indexes:
            # SQLite 没有 `ALTER INDEX ... RENAME`（那是 PostgreSQL 语法），
            # 统一走「DROP 旧索引 + CREATE 新索引」，两种方言都能跑。
            # 注：当前迁移链上本分支不可达 —— 新库由基线 create_all 直接按当前模型
            # 建表（索引名已是新名），老库由 w22 在删旧列前已 drop 旧索引；
            # 保留正确的实现是为了「万一可达也不炸」。
            columns = _index_columns(bind, table, old_name)
            bind.execute(sa.text('DROP INDEX "%s"' % old_name))  # nosec B608
            if columns:
                column_sql = ", ".join('"%s"' % column for column in columns)
                bind.execute(
                    sa.text(
                        'CREATE INDEX "%s" ON "%s" (%s)' % (new_name, table, column_sql)
                    )
                )  # nosec B608
            renamed_indexes.append(f"{table}.{old_name}->{new_name}")

    for table, column, column_type in ADDED_COLUMNS:
        if not _has_table(bind, table):
            continue
        if column in _column_names(bind, table):
            continue
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(column, column_type, nullable=True))
        added_columns.append(f"{table}.{column}")

    return {
        "renamed_columns": renamed_columns,
        "renamed_indexes": renamed_indexes,
        "added_columns": added_columns,
    }


def upgrade():
    bind = op.get_bind()
    result = apply_alignment(bind)
    logger.info(
        "r42 对齐完成：改名列 %s；改名索引 %s；补齐列 %s",
        result["renamed_columns"], result["renamed_indexes"], result["added_columns"],
    )


def downgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        for table, column, _ in ADDED_COLUMNS:
            if _has_table(bind, table) and column in _column_names(bind, table):
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(column)
        for table, old_name, new_name in RENAMED_COLUMNS:
            if _has_table(bind, table) and new_name in _column_names(bind, table):
                with op.batch_alter_table(table) as batch:
                    batch.alter_column(new_name, new_column_name=old_name)
    finally:
        bind.execute(sa.text("PRAGMA foreign_keys = ON"))
