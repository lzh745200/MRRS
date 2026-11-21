"""perf_facet_indexes_001 迁移自证：旧库两列无索引 → 升级补索引且可重入/可回退。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

_MIG = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "perf_facet_indexes_001.py"
)
_spec = importlib.util.spec_from_file_location("perf_facet_indexes_001", _MIG)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _run(engine, fn):
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()


def _indexes(conn, table):
    return {
        row[1]: [info[2] for info in conn.exec_driver_sql(f"PRAGMA index_info({row[1]})")]
        for row in conn.exec_driver_sql(f"PRAGMA index_list({table})")
    }


def test_upgrade_adds_facet_indexes_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE supported_villages (id INTEGER PRIMARY KEY, support_unit TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, responsible_unit TEXT)"
        )

    _run(engine, mig.upgrade)
    _run(engine, mig.upgrade)

    with engine.connect() as conn:
        village_idx = _indexes(conn, "supported_villages")
        project_idx = _indexes(conn, "projects")
        assert village_idx["ix_supported_villages_support_unit"] == ["support_unit"]
        assert project_idx["ix_projects_responsible_unit"] == ["responsible_unit"]


def test_downgrade_removes_facet_indexes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE supported_villages (id INTEGER PRIMARY KEY, support_unit TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE projects (id INTEGER PRIMARY KEY, responsible_unit TEXT)"
        )
    _run(engine, mig.upgrade)
    _run(engine, mig.downgrade)
    with engine.connect() as conn:
        assert "ix_supported_villages_support_unit" not in _indexes(conn, "supported_villages")
        assert "ix_projects_responsible_unit" not in _indexes(conn, "projects")


def test_chain_links_to_previous_head():
    assert mig.revision == "perf_facet_indexes_001"
    assert mig.down_revision == "account_package_attempts_001"
