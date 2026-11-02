"""W27 P1 回归：``annual_industry`` 年份死列清理（``r40_prune_annual_industry_cols_001``）。

与 ``r39``（annual_infrastructure）同批次、同契约：把年份从列名里拿掉，
保留按年的行式表 ``industry_support``。表本身仍用于「当年是否填报」的
``COUNT(id)`` 信号，故只清列、不删表。

锁定要点与 r39 一致（列级三分支），并额外校验：
* 本批 7 列全部是 ``_2025`` / ``_2026`` / ``_total`` 形态（批次特征一致）；
* ``industry_support`` 的行式字段仍在（真正在用的那份）。
"""

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "r40_prune_annual_industry_cols_001.py"
TABLE = "annual_industry"


def load_migration():
    spec = importlib.util.spec_from_file_location(
        "r40_prune_annual_industry_cols_001", MIGRATION_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bind():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        yield conn
    engine.dispose()


def _create_table(conn):
    cols = ['id INTEGER PRIMARY KEY', 'supported_village_id INTEGER', 'year INTEGER']
    cols += [f'"{c}" NUMERIC' for c in load_migration().DEAD_COLUMNS]
    conn.execute(sa.text(f'CREATE TABLE "{TABLE}" ({", ".join(cols)})'))
    conn.execute(sa.text(f'INSERT INTO "{TABLE}" (supported_village_id, year) VALUES (1, 2025)'))


def _cols(conn):
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


class TestColumnThreeBranch:
    def test_absent_table_skips_all(self, bind):
        mod = load_migration()
        result = mod.apply_cleanup(bind)
        assert sorted(result["skipped"]) == sorted(mod.DEAD_COLUMNS)

    def test_all_empty_columns_dropped(self, bind):
        mod = load_migration()
        _create_table(bind)
        result = mod.apply_cleanup(bind)
        assert sorted(result["dropped"]) == sorted(mod.DEAD_COLUMNS)
        assert {"id", "supported_village_id", "year"} <= _cols(bind)

    def test_column_with_data_archived(self, bind):
        mod = load_migration()
        _create_table(bind)
        bind.execute(sa.text(f'UPDATE "{TABLE}" SET "industry_2025_workshops" = 7'))
        result = mod.apply_cleanup(bind)
        assert result["archived"] == ["industry_2025_workshops"]
        assert "legacy_industry_2025_workshops" in _cols(bind)
        kept = bind.execute(sa.text(
            f'SELECT "legacy_industry_2025_workshops" FROM "{TABLE}"'
        )).scalar()
        assert int(kept) == 7

    def test_existing_archive_not_overwritten(self, bind):
        mod = load_migration()
        _create_table(bind)
        bind.execute(sa.text(
            f'ALTER TABLE "{TABLE}" ADD COLUMN "legacy_industry_investment_total" NUMERIC'
        ))
        bind.execute(sa.text(
            f'UPDATE "{TABLE}" SET "industry_investment_total" = 5, '
            f'"legacy_industry_investment_total" = 42'
        ))
        result = mod.apply_cleanup(bind)
        assert "industry_investment_total" in result["skipped"]
        kept = bind.execute(sa.text(
            f'SELECT "legacy_industry_investment_total" FROM "{TABLE}"'
        )).scalar()
        assert float(kept) == 42

    def test_idempotent(self, bind):
        mod = load_migration()
        _create_table(bind)
        mod.apply_cleanup(bind)
        again = mod.apply_cleanup(bind)
        assert again["dropped"] == []
        assert sorted(again["skipped"]) == sorted(mod.DEAD_COLUMNS)


class TestModelAndChain:
    def test_model_no_longer_declares_dead_columns(self):
        from app.models.annual_industry import AnnualIndustry

        cols = {c.name for c in AnnualIndustry.__table__.columns}
        for dead in load_migration().DEAD_COLUMNS:
            assert dead not in cols, f"模型仍声明死列 {dead}"
        assert {"id", "supported_village_id", "year"} <= cols

    def test_row_based_industry_table_still_has_real_fields(self):
        """真正在用的行式表 industry_support 字段必须完好。"""
        from app.models.supported_village import IndustrySupport

        cols = {c.name for c in IndustrySupport.__table__.columns}
        assert {"investment", "planting_breeding", "workshop", "rural_tourism",
                "other_industry", "year"} <= cols

    def test_batch_shape(self):
        """本批 7 列都带「写死的年份」（前缀或后缀形态）或 total 汇总。"""
        mod = load_migration()
        assert len(mod.DEAD_COLUMNS) == 7
        for col in mod.DEAD_COLUMNS:
            has_year = "_2025" in col or "_2026" in col
            assert has_year or col.endswith("_total"), col

    def test_revision_chain(self):
        mod = load_migration()
        assert mod.down_revision == "r39_prune_annual_infra_cols_001"
        assert mod.revision == "r40_prune_annual_industry_cols_001"
