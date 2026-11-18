"""account_credential_expiry_001 迁移自证：旧 users 无列 → 加列 → 回退。"""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

_MIG = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "account_credential_expiry_001.py"
_spec = importlib.util.spec_from_file_location("account_credential_expiry_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _cols(conn):
    return {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)")}


def test_upgrade_and_downgrade(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50))")
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mig.upgrade()
        assert "credential_expires_at" in _cols(conn)
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mig.downgrade()
        assert "credential_expires_at" not in _cols(conn)
