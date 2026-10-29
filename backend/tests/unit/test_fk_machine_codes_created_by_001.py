# -*- coding: utf-8 -*-
"""fk_machine_codes_created_by_001 的自证测试（迁移自证门禁要求，2026-10-29 审计）。

为什么要手搓库：空库跑 `upgrade head` 时 `001_baseline` 的 `create_all()` 已用**新模型**
建表，外键一开始就带 `ondelete=SET NULL`，迁移直接 skip —— 逻辑根本不被执行。
这里手工建出「无 ondelete 的旧外键」，驱动迁移函数，断言外键真的被换成 SET NULL。
"""
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine

_MIG = (
    Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "fk_machine_codes_created_by_001.py"
)
_spec = importlib.util.spec_from_file_location("fk_machine_codes_created_by_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _fk_ondelete(conn, table="machine_codes"):
    """返回 created_by 外键的 ondelete 值（SQLite PRAGMA）。"""
    rows = conn.exec_driver_sql("PRAGMA foreign_key_list(" + table + ")").fetchall()
    for row in rows:
        # 列序：id, seq, table, from, to, on_update, on_delete, match
        if row[3] == "created_by":
            return row[6]
    return None


def _make_legacy_table(conn):
    """造出「旧外键无 ondelete」的 machine_codes 表。"""
    conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
    conn.exec_driver_sql(
        "CREATE TABLE machine_codes ("
        "  id INTEGER PRIMARY KEY,"
        "  code VARCHAR(64) NOT NULL,"
        "  created_by INTEGER,"
        "  FOREIGN KEY(created_by) REFERENCES users(id)"
        ")"
    )


def test_detects_missing_ondelete(tmp_path):
    """find_target_fk + needs_fix 必须识别出「有外键但无 ondelete」。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        _make_legacy_table(conn)
        fk = mig.find_target_fk(conn)
        assert fk is not None
        assert mig.needs_fix(fk) is True
        assert _fk_ondelete(conn) in (None, "NO ACTION")


def test_missing_table_returns_none(tmp_path):
    """表不存在 → None（迁移 skip，不炸）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    with engine.begin() as conn:
        assert mig.find_target_fk(conn) is None
        assert mig.needs_fix(None) is False


def test_already_fixed_is_noop(tmp_path):
    """已有 ondelete 的外键不需要再修（幂等）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'fixed.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql(
            "CREATE TABLE machine_codes ("
            "  id INTEGER PRIMARY KEY, code VARCHAR(64) NOT NULL, created_by INTEGER,"
            "  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL"
            ")"
        )
        fk = mig.find_target_fk(conn)
        assert fk is not None
        assert mig.needs_fix(fk) is False
        assert _fk_ondelete(conn) == "SET NULL"


def test_upgrade_rewrites_fk_to_set_null(tmp_path, monkeypatch):
    """真跑 upgrade：旧外键被换成 ON DELETE SET NULL。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'up.db'}")
    with engine.begin() as conn:
        _make_legacy_table(conn)

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        monkeypatch.setattr(mig.op, "get_bind", lambda: conn)
        with Operations.context(ctx):
            mig.upgrade()
        assert _fk_ondelete(conn) == "SET NULL", "外键必须改成 SET NULL"

    # 级联行为验证：SQLite 的 PRAGMA foreign_keys 是**连接级且默认 OFF**，
    # 必须显式开启，否则 ON DELETE SET NULL 不生效（这不是迁移的问题）。
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.exec_driver_sql("INSERT INTO users (id) VALUES (1)")
        conn.exec_driver_sql("INSERT INTO machine_codes (code, created_by) VALUES ('C1', 1)")
        conn.exec_driver_sql("DELETE FROM users WHERE id = 1")
        left = conn.exec_driver_sql("SELECT created_by FROM machine_codes").scalar()
        assert left is None, "开了 foreign_keys 后，删用户应把 created_by 置 NULL"