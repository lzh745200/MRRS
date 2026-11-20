"""account_package_attempts_001 迁移自证：旧库无表 → 台账表 + subject_key 唯一；可重入/可回退。"""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

_MIG = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "account_package_attempts_001.py"
)
_spec = importlib.util.spec_from_file_location("account_package_attempts_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _run(engine, fn):
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


def test_upgrade_creates_attempt_ledger_with_unique_subject(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    _run(engine, mig.upgrade)

    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "account_package_attempts" in tables
        cols = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(account_package_attempts)")}
        assert {"subject_key", "fail_count", "locked_until", "last_error", "last_attempt_at"} <= cols
        # subject_key 必须单独唯一，否则同一作用域会写出多行、计数被绕过
        unique_cols = []
        for row in conn.exec_driver_sql("PRAGMA index_list(account_package_attempts)"):
            if row[2]:
                info = [r[2] for r in conn.exec_driver_sql(f"PRAGMA index_info({row[1]})")]
                if info == ["subject_key"]:
                    unique_cols.append(info)
        assert unique_cols == [["subject_key"]]


def test_upgrade_is_idempotent_and_downgrade_removes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'twice.db'}")
    _run(engine, mig.upgrade)
    _run(engine, mig.upgrade)
    _run(engine, mig.downgrade)
    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "account_package_attempts" not in tables


def test_chain_links_to_previous_head():
    assert mig.revision == "account_package_attempts_001"
    assert mig.down_revision == "account_credential_expiry_001"
