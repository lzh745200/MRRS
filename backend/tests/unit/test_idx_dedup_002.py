# -*- coding: utf-8 -*-
"""idx_dedup_002 的自证测试（迁移自证门禁要求，2026-10-29 审计）。

为什么要手搓库：空库 `alembic upgrade head` 时 001_baseline 已用 create_all() 建好表，
该迁移能否真的删对索引不受标准演练验证（见 check_migration_self_evidence.py）。
这里直接建出「同列多索引 + sqlite_autoindex」的旧结构，驱动 find_redundant 断言：

1. 同列同唯一性的多余索引被删；
2. 模型显式声明的那个被**保留**；
3. sqlite_autoindex_*（表级 UNIQUE）**永不删**；
4. 无重复的表不受影响。
"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine

_MIG = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "idx_dedup_002.py"
_spec = importlib.util.spec_from_file_location("idx_dedup_002", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _engine(tmp_path, name="dedup.db"):
    return create_engine(f"sqlite:///{tmp_path / name}")


def test_drops_duplicate_keeps_declared_one(tmp_path):
    """audit_logs.created_at 有三个索引 → 只保留模型声明的 idx_audit_created。"""
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, created_at TEXT, "
            "user_id INTEGER, action TEXT)"
        )
        conn.exec_driver_sql("CREATE INDEX ix_audit_timestamp ON audit_logs(created_at)")
        conn.exec_driver_sql("CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at)")
        conn.exec_driver_sql("CREATE INDEX idx_audit_created ON audit_logs(created_at)")

    with engine.begin() as conn:
        to_drop = mig.find_redundant(conn)

    assert sorted(to_drop) == ["ix_audit_logs_created_at", "ix_audit_timestamp"]
    assert "idx_audit_created" not in to_drop


def test_never_drops_sqlite_autoindex(tmp_path):
    """表级 UNIQUE 约束生成的 sqlite_autoindex_* 绝不能删（会丢唯一性）。"""
    engine = _engine(tmp_path, "auto.db")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE regions (id INTEGER PRIMARY KEY, code TEXT UNIQUE)"
        )
        conn.exec_driver_sql("CREATE INDEX ix_regions_code ON regions(code)")

    with engine.begin() as conn:
        to_drop = mig.find_redundant(conn)

    assert all("sqlite_autoindex" not in n for n in to_drop)


def test_no_duplicates_noop(tmp_path):
    """没有重复索引的表不该产生任何待删项。"""
    engine = _engine(tmp_path, "clean.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, a TEXT, b TEXT)")
        conn.exec_driver_sql("CREATE INDEX ix_t_a ON t(a)")
        conn.exec_driver_sql("CREATE INDEX ix_t_b ON t(b)")

    with engine.begin() as conn:
        assert mig.find_redundant(conn) == []


def test_different_uniqueness_not_treated_as_duplicate(tmp_path):
    """同列但唯一性不同（普通索引 + 唯一索引）**不**在本迁移删除范围。"""
    engine = _engine(tmp_path, "uniq.db")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE u (id INTEGER PRIMARY KEY, code TEXT)")
        conn.exec_driver_sql("CREATE INDEX ix_u_code ON u(code)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX uq_u_code ON u(code)")

    with engine.begin() as conn:
        assert mig.find_redundant(conn) == []


def test_keep_list_covers_model_declarations():
    """保留清单必须覆盖模型对 7 组索引的显式声明（防止清单与模型脱节）。"""
    expected = {
        "idx_audit_created",
        "idx_audit_user_action",
        "ix_households_village",
        "ix_household_members_household",
        "ix_household_risk_records_household",
        "ix_consumption_records_village",
        "idx_token_blacklist_expires",
    }
    assert expected == set(mig.KEEP_INDEX_NAMES)