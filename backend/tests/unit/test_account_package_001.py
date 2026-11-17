"""account_package_001 迁移自证：旧库无表 → 两表 + 唯一键；可重入/可回退。"""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

_MIG = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "account_package_001.py"
_spec = importlib.util.spec_from_file_location("account_package_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _run(engine, fn):
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


def test_upgrade_creates_tables_and_unique_package_id(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    _run(engine, mig.upgrade)

    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"account_package_exports", "account_package_receipts"} <= tables
        # 回执唯一键必须只含 package_id
        indexes = list(conn.exec_driver_sql("PRAGMA index_list(account_package_receipts)"))
        unique_cols = []
        for row in indexes:
            if row[2]:
                cols = [r[2] for r in conn.exec_driver_sql(f"PRAGMA index_info({row[1]})")]
                if cols == ["package_id"]:
                    unique_cols.append(cols)
        assert unique_cols == [["package_id"]]


def test_upgrade_is_idempotent_and_downgrade_removes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'twice.db'}")
    _run(engine, mig.upgrade)
    _run(engine, mig.upgrade)
    _run(engine, mig.downgrade)
    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "account_package_exports" not in tables
        assert "account_package_receipts" not in tables
