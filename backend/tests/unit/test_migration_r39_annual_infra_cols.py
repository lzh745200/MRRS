"""W27 P1 回归：``annual_infrastructure`` 年份死列清理（``r39_prune_annual_infra_cols_001``）。

## 背景
该表沿用与已删 ``annual_income`` **同一反模式**：把年份写进列名
（``road_km_2025`` / ``infrastructure_investment_2026`` …），每过一年要改一次模型。
W27 扫描确认这 9 列在 ``app/``（模型外）与 ``frontend/src`` **零引用**；
真正的行式明细在 ``infrastructure_improvement``。

表本身仍有使用（``effectiveness_service`` 用 ``COUNT(id)``），故**只清列、不删表**。

## 本文件锁定（列级三分支，沿用表级 r35 契约的同类精神）
1. 列不存在 → 跳过（幂等）；
2. 列存在且**整列为空/0** → DROP COLUMN；
3. 列存在且**有数据** → RENAME 为 ``legacy_<列名>``（**数据绝不丢**）；
4. 归档列已存在 → 保留原列不处理（防覆盖既有归档）；
5. 表不存在 → 全部跳过（不报错）；
6. **模型侧已移除这些字段**，但 ``supported_village_id``/``year`` 仍在
   （表还承担"当年是否填报"的信号）；
7. 回滚能把 ``legacy_*`` 改回原名。
"""

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "r39_prune_annual_infra_cols_001.py"
TABLE = "annual_infrastructure"


def load_migration():
    spec = importlib.util.spec_from_file_location("r39_prune_annual_infra_cols_001", MIGRATION_PATH)
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


def _create_table(conn, extra_cols=True):
    cols = ['id INTEGER PRIMARY KEY', 'supported_village_id INTEGER', 'year INTEGER']
    if extra_cols:
        cols += [f'"{c}" NUMERIC' for c in load_migration().DEAD_COLUMNS]
    conn.execute(sa.text(f'CREATE TABLE "{TABLE}" ({", ".join(cols)})'))
    conn.execute(sa.text(f'INSERT INTO "{TABLE}" (supported_village_id, year) VALUES (1, 2025)'))


def _cols(conn):
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


class TestColumnThreeBranch:
    def test_absent_table_skips_all(self, bind):
        mod = load_migration()
        result = mod.apply_cleanup(bind)
        assert result["dropped"] == []
        assert result["archived"] == []
        assert sorted(result["skipped"]) == sorted(mod.DEAD_COLUMNS)

    def test_all_empty_columns_are_dropped(self, bind):
        mod = load_migration()
        _create_table(bind, extra_cols=True)
        result = mod.apply_cleanup(bind)
        assert sorted(result["dropped"]) == sorted(mod.DEAD_COLUMNS)
        remaining = _cols(bind)
        for col in mod.DEAD_COLUMNS:
            assert col not in remaining
        # 业务基础列必须保留（表仍用于"是否填报"判定）
        assert {"id", "supported_village_id", "year"} <= remaining

    def test_column_with_data_is_archived_not_dropped(self, bind):
        mod = load_migration()
        _create_table(bind, extra_cols=True)
        bind.execute(sa.text(
            f'UPDATE "{TABLE}" SET "road_km_2025" = 12.5'
        ))
        result = mod.apply_cleanup(bind)
        assert "road_km_2025" in result["archived"]
        remaining = _cols(bind)
        assert "road_km_2025" not in remaining
        assert "legacy_road_km_2025" in remaining
        # 数据一行不丢
        value = bind.execute(sa.text(
            f'SELECT "legacy_road_km_2025" FROM "{TABLE}"'
        )).scalar()
        assert float(value) == 12.5

    def test_mixed_columns_take_both_branches(self, bind):
        """同一张表里"有数据"和"全空"的列分别走归档/删除。"""
        mod = load_migration()
        _create_table(bind, extra_cols=True)
        bind.execute(sa.text(f'UPDATE "{TABLE}" SET "water_facilities_2025" = 3'))
        result = mod.apply_cleanup(bind)
        assert result["archived"] == ["water_facilities_2025"]
        assert len(result["dropped"]) == len(mod.DEAD_COLUMNS) - 1
        remaining = _cols(bind)
        assert "legacy_water_facilities_2025" in remaining

    def test_existing_archive_column_is_not_overwritten(self, bind):
        mod = load_migration()
        _create_table(bind, extra_cols=True)
        bind.execute(sa.text(f'ALTER TABLE "{TABLE}" ADD COLUMN "legacy_road_km_2025" NUMERIC'))
        bind.execute(sa.text(f'UPDATE "{TABLE}" SET "road_km_2025" = 5, "legacy_road_km_2025" = 99'))
        result = mod.apply_cleanup(bind)
        assert "road_km_2025" in result["skipped"]
        remaining = _cols(bind)
        assert "road_km_2025" in remaining           # 原列保留
        kept = bind.execute(sa.text(f'SELECT "legacy_road_km_2025" FROM "{TABLE}"')).scalar()
        assert float(kept) == 99                      # 既有归档未被覆盖

    def test_idempotent_second_run(self, bind):
        mod = load_migration()
        _create_table(bind, extra_cols=True)
        mod.apply_cleanup(bind)
        again = mod.apply_cleanup(bind)
        assert again["dropped"] == []
        assert sorted(again["skipped"]) == sorted(mod.DEAD_COLUMNS)

    def test_partial_columns_skipped(self, bind):
        """表存在但只有部分死列时，缺少的那些列为 skipped。"""
        mod = load_migration()
        conn = bind
        conn.execute(sa.text(
            f'CREATE TABLE "{TABLE}" (id INTEGER PRIMARY KEY, '
            f'supported_village_id INTEGER, year INTEGER, "road_km_2025" NUMERIC)'
        ))
        result = mod.apply_cleanup(conn)
        assert result["dropped"] == ["road_km_2025"]
        assert len(result["skipped"]) == len(mod.DEAD_COLUMNS) - 1


class TestModelSide:
    def test_model_no_longer_declares_dead_columns(self):
        from app.models.annual_infrastructure import AnnualInfrastructure

        cols = {c.name for c in AnnualInfrastructure.__table__.columns}
        mod = load_migration()
        for dead in mod.DEAD_COLUMNS:
            assert dead not in cols, f"模型仍声明死列 {dead}"

    def test_model_keeps_identity_columns(self):
        from app.models.annual_infrastructure import AnnualInfrastructure

        cols = {c.name for c in AnnualInfrastructure.__table__.columns}
        assert {"id", "supported_village_id", "year"} <= cols

    def test_effectiveness_service_still_works_with_trimmed_model(self):
        """表仍被 effectiveness_service 用作"当年是否填报"信号，不能连带删表。"""
        import inspect

        from app.services import effectiveness_service as eff

        src = inspect.getsource(eff.EffectivenessService._compute_indicators)
        assert "AnnualInfrastructure" in src


class TestMigrationChain:
    def test_revision_chain(self):
        mod = load_migration()
        assert mod.down_revision == "r38_drop_annual_income_001"
        assert mod.revision == "r39_prune_annual_infra_cols_001"

    def test_dead_columns_list_is_the_documented_nine(self):
        mod = load_migration()
        assert len(mod.DEAD_COLUMNS) == 9
        # 全部是"年份写死"或 "total" 形态（本批次的一致特征）
        for col in mod.DEAD_COLUMNS:
            assert col.endswith(("_2025", "_2026", "_total")), col
