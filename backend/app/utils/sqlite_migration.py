"""SQLite 迁移兼容助手（R57）。

打包环境的 SQLite 可能低于 3.35（不支持 DROP COLUMN）或低于 3.25
（不支持 RENAME COLUMN）。迁移脚本里的 ``apply_cleanup(bind)`` 又会
被单测直接调用（没有 Alembic ``op`` 代理），所以不能无条件使用
``op.batch_alter_table``。

策略：
- 非 SQLite 或 SQLite 版本足够 → 原生 ALTER，保持原行为；
- SQLite 版本不足且传入了 ``op`` → ``op.batch_alter_table`` 重建表；
- 没有 ``op``（单测/异常上下文）→ 退回原生 ALTER，由调用方保证环境。
"""

from __future__ import annotations

import sqlite3

import sqlalchemy as sa


def _is_sqlite(bind) -> bool:
    return getattr(getattr(bind, "dialect", None), "name", "") == "sqlite"


def _supports_drop_column(bind) -> bool:
    return (not _is_sqlite(bind)) or sqlite3.sqlite_version_info >= (3, 35)


def _supports_rename_column(bind) -> bool:
    return (not _is_sqlite(bind)) or sqlite3.sqlite_version_info >= (3, 25)


def drop_column(bind, table: str, column: str, op=None) -> None:
    if _supports_drop_column(bind) or op is None:
        bind.execute(sa.text(f'ALTER TABLE "{table}" DROP COLUMN "{column}"'))  # nosec B608 - 表名/列名来自迁移脚本常量，非用户输入
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_column(column)


def rename_column(bind, table: str, old: str, new: str, op=None) -> None:
    if _supports_rename_column(bind) or op is None:
        bind.execute(sa.text(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"'))  # nosec B608 - 表名/列名来自迁移脚本常量，非用户输入
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(old, new_column_name=new)
