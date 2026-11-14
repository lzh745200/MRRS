"""audit_chain_001 迁移自证：旧库（无列）→ 新库（两列 + 索引）。"""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

_MIG_PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "audit_chain_001_add_hashes.py"
_spec = importlib.util.spec_from_file_location("audit_chain_001", _MIG_PATH)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _columns(conn):
    return {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(audit_logs)")}


def test_upgrade_adds_hash_columns_and_index(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, action VARCHAR(50))"
        )
        conn.exec_driver_sql("INSERT INTO audit_logs (action) VALUES ('login')")

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mig.upgrade()
        cols = _columns(conn)
        assert {"prev_hash", "payload_hash"} <= cols
        assert conn.exec_driver_sql("SELECT action FROM audit_logs").scalar() == "login"
        indexes = {r[1] for r in conn.exec_driver_sql("PRAGMA index_list(audit_logs)")}
        assert "ix_audit_logs_payload_hash" in indexes


def test_downgrade_removes_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'down.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, action VARCHAR(50),"
            " prev_hash VARCHAR(64), payload_hash VARCHAR(64))"
        )
        conn.exec_driver_sql(
            "CREATE INDEX ix_audit_logs_payload_hash ON audit_logs(payload_hash)"
        )
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mig.downgrade()
        assert "prev_hash" not in _columns(conn)
        assert "payload_hash" not in _columns(conn)
