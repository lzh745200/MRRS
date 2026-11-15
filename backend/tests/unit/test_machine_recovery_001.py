# -*- coding: utf-8 -*-
"""machine_recovery_001 迁移的收口证据（C1 迁移自证棘轮）。

为什么需要这个测试：空库 `alembic upgrade head` 时 `machine_recovery_codes`
由模型建表脚本创建，迁移里的 `op.create_table` 在标准演练中可能从未真正执行。
这里直接构造「旧库」状态（没有该表）并驱动迁移函数，断言表与查询索引确实被创建，
同时验证幂等（重复 upgrade 不报错）与 downgrade 能干净删除。
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIG_PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "machine_recovery_001.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("machine_recovery_001", _MIG_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _table_names(conn):
    return set(sa.inspect(conn).get_table_names())


def _index_names(conn, table):
    return {idx["name"] for idx in sa.inspect(conn).get_indexes(table)}


def _run(conn, fn):
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        fn()


def test_upgrade_creates_table_and_lookup_index(tmp_path):
    """旧库无该表 → upgrade 后表存在，且包含联合查询索引。"""
    mig = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        assert "machine_recovery_codes" not in _table_names(conn)
        _run(conn, mig.upgrade)
        assert "machine_recovery_codes" in _table_names(conn)
        cols = {c["name"] for c in sa.inspect(conn).get_columns("machine_recovery_codes")}
        assert {"machine_code", "code_hash", "purpose", "expires_at", "used_at", "attempts"} <= cols
        idx = _index_names(conn, "machine_recovery_codes")
        assert "ix_machine_recovery_lookup" in idx
        assert "ix_machine_recovery_codes_machine_code" in idx


def test_upgrade_is_idempotent(tmp_path):
    """重复 upgrade（表已存在）必须安全跳过，不抛异常。"""
    mig = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'twice.db'}")
    with engine.begin() as conn:
        _run(conn, mig.upgrade)
        _run(conn, mig.upgrade)
        assert "machine_recovery_codes" in _table_names(conn)


def test_downgrade_drops_table(tmp_path):
    """downgrade 后表被移除，且可再次 upgrade 回滚。"""
    mig = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'down.db'}")
    with engine.begin() as conn:
        _run(conn, mig.upgrade)
        assert "machine_recovery_codes" in _table_names(conn)
        _run(conn, mig.downgrade)
        assert "machine_recovery_codes" not in _table_names(conn)
        _run(conn, mig.upgrade)
        assert "machine_recovery_codes" in _table_names(conn)
