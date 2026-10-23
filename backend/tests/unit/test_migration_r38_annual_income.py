"""W27 P1 回归：死表 ``annual_income`` 清理迁移（``r38_drop_annual_income_001``）。

## 背景
``annual_income`` 是 W26-P0-2「指标口径不一致」的根源：列式年度快照
（``per_capita_income_2020..2025``），**全仓 0 处写入**、dev 库 0 行、
年份列写死到 2025。第 3 轮已把全部读取方切到行式 ``village_income``，
本轮删除模型并迁移收尾。

## 本文件锁定
1. **三分支契约**（沿用 r35/r36/r37）：不存在→跳过；0 行→DROP；
   有数据→改名 ``legacy_annual_income`` 归档（一行不丢）；归档已存在→不覆盖；
2. **ORM 已移除**：`app.models` 不再导出 `AnnualIncome`，模块文件不存在；
3. **同期仍在的模型未被误删**（`AnnualPopulation`/`AnnualIndustry`/
   `AnnualInfrastructure`/`VillageIncome`）；
4. **`households.annual_income` 是另一个字段**（户年收入，单位元），必须仍在
   —— 本轮只删表，不动户档案的列；
5. 升级演练清单已登记；单 head 链正确（r37 → r38）。
"""

import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "r38_drop_annual_income_001.py"
MANIFEST_PATH = ROOT / "scripts" / "gate_baselines" / "upgrade_legacy_tables.json"
TABLE = "annual_income"
ARCHIVE = "legacy_annual_income"


def load_migration():
    spec = importlib.util.spec_from_file_location("r38_drop_annual_income_001", MIGRATION_PATH)
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


def _create_table(conn, with_rows=0):
    conn.execute(sa.text(
        f'CREATE TABLE "{TABLE}" (id INTEGER PRIMARY KEY, supported_village_id INTEGER, year INTEGER)'
    ))
    for i in range(with_rows):
        conn.execute(sa.text(
            f'INSERT INTO "{TABLE}" (supported_village_id, year) VALUES (1, {2020 + i})'
        ))


class TestThreeBranchContract:
    def test_absent_table_is_skipped(self, bind):
        mod = load_migration()
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [TABLE]

    def test_empty_table_is_dropped(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=0)
        result = mod.apply_cleanup(bind)
        assert result["dropped"] == [TABLE]
        assert not sa.inspect(bind).has_table(TABLE)

    def test_table_with_rows_is_archived_not_lost(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=4)
        result = mod.apply_cleanup(bind)
        assert result["archived"] == [TABLE]
        assert not sa.inspect(bind).has_table(TABLE)
        assert sa.inspect(bind).has_table(ARCHIVE)
        assert bind.execute(sa.text(f'SELECT COUNT(*) FROM "{ARCHIVE}"')).scalar() == 4

    def test_existing_archive_is_not_overwritten(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=2)
        bind.execute(sa.text(
            f'CREATE TABLE "{ARCHIVE}" (id INTEGER PRIMARY KEY, supported_village_id INTEGER, year INTEGER)'
        ))
        bind.execute(sa.text(f'INSERT INTO "{ARCHIVE}" (year) VALUES (2019)'))
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [TABLE]
        assert sa.inspect(bind).has_table(TABLE)
        assert bind.execute(sa.text(f'SELECT COUNT(*) FROM "{ARCHIVE}"')).scalar() == 1

    def test_idempotent_second_run(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=0)
        mod.apply_cleanup(bind)
        assert mod.apply_cleanup(bind)["skipped"] == [TABLE]


class TestModelRemoved:
    def test_model_no_longer_exported(self):
        import app.models as models

        for name in models.__all__:
            try:
                getattr(models, name)
            except Exception:
                pass
        assert not hasattr(models, "AnnualIncome")
        assert "AnnualIncome" not in models.__all__

    def test_model_module_file_removed(self):
        assert not (ROOT / "app" / "models" / "annual_income.py").exists()

    def test_sibling_annual_models_survive(self):
        from app.models.annual_industry import AnnualIndustry
        from app.models.annual_infrastructure import AnnualInfrastructure
        from app.models.annual_population import AnnualPopulation
        from app.models.supported_village import VillageIncome

        assert all(m is not None for m in (
            AnnualIndustry, AnnualInfrastructure, AnnualPopulation, VillageIncome,
        ))

    def test_household_annual_income_column_untouched(self):
        """⚠️ household.annual_income 是**户年收入(元)**，与本次删除的表无关。"""
        from app.models.household import Household

        cols = {c.name for c in Household.__table__.columns}
        assert "annual_income" in cols, "误删了户档案的年收入列！"

    def test_cascade_cleanup_list_no_longer_references_table(self):
        from app.services.village_cascade_delete_service import VillageCascadeDeleteService

        names = [t for t, _col in VillageCascadeDeleteService.DEPENDENT_TABLES]
        assert TABLE not in names


class TestManifestContract:
    def test_manifest_lists_annual_income(self):
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert TABLE in payload.get("legacy_tables", [])
        # 前几批登记的表必须保留（清单是累积的，不能因为改 revision 而丢历史）
        for earlier in ("rural_tasks", "budget_records"):
            assert earlier in payload.get("legacy_tables", []), f"清单丢了历史表 {earlier}"

    def test_migration_chain(self):
        mod = load_migration()
        assert mod.down_revision == "r37_drop_budget_records_001"
        assert mod.revision == "r38_drop_annual_income_001"
