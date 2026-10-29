# -*- coding: utf-8 -*-
"""dead_models_001 的三分支自证测试（迁移自证门禁要求，2026-10-29 审计）。

原实现只判断「表存在」就 drop_table，没有行数护栏 —— 一旦生产库这些表里有数据，
升级会**静默丢数据**（违反 r35 三分支契约）。本测试直接建库造出四种场景，
验证清理函数的行为与契约一致。
"""
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine

_MIG = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "dead_models_001_drop_unused_tables.py"
_spec = importlib.util.spec_from_file_location("dead_models_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _table_names(conn):
    return {r[0] for r in conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def test_missing_table_is_skipped(tmp_path):
    """表不存在 → skipped（幂等，可重复执行）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE unrelated (id INTEGER)")
        result = mig.apply_dead_models_cleanup(conn)
        assert set(result["skipped"]) == set(mig.TABLES)
        assert result["dropped"] == [] and result["archived"] == []


def test_empty_table_is_dropped(tmp_path):
    """0 行 → DROP（原行为，安全）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE user_sessions (id INTEGER)")
        result = mig.apply_dead_models_cleanup(conn)
        assert result["dropped"] == ["user_sessions"]
        assert "user_sessions" not in _table_names(conn)


def test_table_with_rows_is_archived_not_dropped(tmp_path):
    """有数据 → 改名 legacy_ 归档，**数据不丢**（这是本次修复的核心）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE user_sessions (id INTEGER)")
        conn.exec_driver_sql("INSERT INTO user_sessions (id) VALUES (1), (2), (3)")
        result = mig.apply_dead_models_cleanup(conn)

        assert result["archived"] == ["user_sessions"]
        assert result["dropped"] == []
        names = _table_names(conn)
        assert "user_sessions" not in names
        assert "legacy_user_sessions" in names
        kept = conn.exec_driver_sql("SELECT COUNT(*) FROM legacy_user_sessions").scalar()
        assert kept == 3, "归档后行数必须不变"


def test_existing_archive_table_keeps_original(tmp_path):
    """归档表已存在时不覆盖既有归档，保留原表待人工确认。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE user_sessions (id INTEGER)")
        conn.exec_driver_sql("INSERT INTO user_sessions (id) VALUES (1)")
        conn.exec_driver_sql("CREATE TABLE legacy_user_sessions (id INTEGER)")
        result = mig.apply_dead_models_cleanup(conn)

        assert "user_sessions" in result["skipped"]
        assert result["archived"] == []
        names = _table_names(conn)
        assert "user_sessions" in names  # 原表保留
        assert "legacy_user_sessions" in names  # 既有归档保留