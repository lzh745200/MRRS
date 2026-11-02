# -*- coding: utf-8 -*-
"""org_data_scope_001 迁移的自证证据（C1：迁移基线自证）。

为什么需要这个测试：空库 ``alembic upgrade head`` 时该迁移可能因为
``001_baseline`` 的 ``create_all()`` 已按当前模型建表而直接跳过
（``skip（organizations.data_scope 已存在）``），迁移逻辑本身在标准演练里
不会被执行。所以要直接构造「旧库」状态（有 ``organizations`` 表、无
``data_scope`` 列）来驱动迁移函数。

锁定契约：
1. 旧库升级后 ``organizations.data_scope`` 为 ``VARCHAR(16) NULL``，数据行不丢；
2. 重复执行幂等（第二次打印 skip，不报错）；
3. 表不存在时跳过而不炸；
4. 回滚删除该列、保留数据；
5. 无该列时回滚幂等；
6. 迁移链指向 ``fk_machine_codes_created_by_001``。
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "org_data_scope_001.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("org_data_scope_001", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mig():
    return _load()


def _table_info(conn, table):
    return {row[1]: row[2] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


@pytest.fixture()
def engine(tmp_path):
    eng = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    yield eng
    eng.dispose()


class TestUpgrade:
    def test_adds_nullable_column_and_keeps_rows(self, mig, engine):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE organizations (id INTEGER PRIMARY KEY, name VARCHAR(100))"
            )
            conn.exec_driver_sql("INSERT INTO organizations (id, name) VALUES (1, '省级')")

        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                mig.upgrade()

        with engine.connect() as conn:
            assert _table_info(conn, mig.TABLE)[mig.COLUMN] == "VARCHAR(16)"
            assert conn.exec_driver_sql(
                f"SELECT name FROM {mig.TABLE} WHERE id = 1"
            ).scalar() == "省级"
            assert conn.exec_driver_sql(
                f"SELECT {mig.COLUMN} FROM {mig.TABLE} WHERE id = 1"
            ).scalar() is None

    def test_idempotent_when_column_exists(self, mig, engine, capsys):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE organizations (id INTEGER PRIMARY KEY, data_scope VARCHAR(16))"
            )
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                mig.upgrade()
                mig.upgrade()

        out = capsys.readouterr().out
        assert "skip" in out
        with engine.connect() as conn:
            assert mig.COLUMN in _table_info(conn, mig.TABLE)

    def test_missing_table_is_skipped(self, mig, engine, capsys):
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                mig.upgrade()  # 不抛异常

        assert "skip" in capsys.readouterr().out


class TestDowngrade:
    def test_drops_column_and_keeps_rows(self, mig, engine):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE organizations (id INTEGER PRIMARY KEY, "
                "name VARCHAR(100), data_scope VARCHAR(16))"
            )
            conn.exec_driver_sql(
                "INSERT INTO organizations (id, name, data_scope) VALUES (1, '省级', 'subtree')"
            )

        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                mig.downgrade()

        with engine.connect() as conn:
            assert mig.COLUMN not in _table_info(conn, mig.TABLE)
            assert conn.exec_driver_sql(
                f"SELECT name FROM {mig.TABLE} WHERE id = 1"
            ).scalar() == "省级"

    def test_idempotent_without_column(self, mig, engine):
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE organizations (id INTEGER PRIMARY KEY)")
        with engine.begin() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                mig.downgrade()  # 不抛异常

        with engine.connect() as conn:
            assert mig.COLUMN not in _table_info(conn, mig.TABLE)


def test_revision_chain(mig):
    assert mig.revision == "org_data_scope_001"
    assert mig.down_revision == "fk_machine_codes_created_by_001"
