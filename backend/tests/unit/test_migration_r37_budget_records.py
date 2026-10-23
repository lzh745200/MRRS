"""W27 P1 回归：死模型 ``BudgetRecord`` 清理迁移（``r37_drop_budget_records_001``）。

## 背景（W26 P1「死字段/死模型清理」）
``BudgetRecord``（表 ``budget_records``）全仓零引用：只有类定义、``models/__init__``
注册与一处注释，**没有任何端点/服务使用**；真正的预算功能是 ``FundBudget``
（带 ``organization_id``/``created_by``，可做数据域隔离）。
保留它会让维护者误以为"预算还有第二套表"。

## 本文件锁定
1. **三分支契约**（沿用 r35/r36）：表不存在→跳过；0 行→DROP；有数据→改名
   ``legacy_budget_records`` 归档（数据一行不丢）；
2. 归档表已存在时**不覆盖**（重复执行/人工处理过的场景）；
3. **ORM 已移除**：`app.models` 不再导出 `BudgetRecord`（防"迁移删了表、模型还在"）；
4. 升级演练清单已登记 ``budget_records``（否则演练把"表消失"判为数据丢失）。
"""

import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "r37_drop_budget_records_001.py"
MANIFEST_PATH = ROOT / "scripts" / "gate_baselines" / "upgrade_legacy_tables.json"
TABLE = "budget_records"
ARCHIVE = "legacy_budget_records"


def load_migration():
    spec = importlib.util.spec_from_file_location("r37_drop_budget_records_001", MIGRATION_PATH)
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
        f'CREATE TABLE "{TABLE}" (id INTEGER PRIMARY KEY, year INTEGER, category TEXT)'
    ))
    for i in range(with_rows):
        conn.execute(sa.text(
            f'INSERT INTO "{TABLE}" (year, category) VALUES (2024, \'c{i}\')'
        ))


class TestThreeBranchContract:
    def test_absent_table_is_skipped(self, bind):
        mod = load_migration()
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [TABLE]
        assert result["dropped"] == []
        assert result["archived"] == []

    def test_empty_table_is_dropped(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=0)
        result = mod.apply_cleanup(bind)
        assert result["dropped"] == [TABLE]
        assert not sa.inspect(bind).has_table(TABLE)

    def test_table_with_rows_is_archived_not_lost(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=3)
        result = mod.apply_cleanup(bind)
        assert result["archived"] == [TABLE]
        assert not sa.inspect(bind).has_table(TABLE)
        assert sa.inspect(bind).has_table(ARCHIVE)
        # 数据一行不丢
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{ARCHIVE}"')).scalar()
        assert count == 3

    def test_existing_archive_is_not_overwritten(self, bind):
        """归档表已存在时不覆盖既有归档，也不删原表（需人工确认）。"""
        mod = load_migration()
        _create_table(bind, with_rows=2)
        bind.execute(sa.text(f'CREATE TABLE "{ARCHIVE}" (id INTEGER PRIMARY KEY, year INTEGER, category TEXT)'))
        bind.execute(sa.text(f'INSERT INTO "{ARCHIVE}" (year, category) VALUES (2020, \'old\')'))
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [TABLE]
        assert sa.inspect(bind).has_table(TABLE)          # 原表保留
        kept = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{ARCHIVE}"')).scalar()
        assert kept == 1                                   # 既有归档未被覆盖

    def test_idempotent_second_run(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=0)
        mod.apply_cleanup(bind)
        again = mod.apply_cleanup(bind)
        assert again["skipped"] == [TABLE]                 # 第二次已无表可删


class TestModelRemoved:
    def test_model_no_longer_exported(self):
        import app.models as models

        for name in models.__all__:
            try:
                getattr(models, name)
            except Exception:
                pass
        assert not hasattr(models, "BudgetRecord")
        assert "BudgetRecord" not in models.__all__

    def test_fund_module_has_no_budget_record(self):
        from app.models import fund as fund_mod

        assert not hasattr(fund_mod, "BudgetRecord")

    def test_real_budget_model_still_present(self):
        """真正的预算模型 FundBudget 必须还在（别把有用的也删了）。"""
        from app.models.fund_budget import FundBudget

        cols = {c.name for c in FundBudget.__table__.columns}
        assert {"budget_amount", "organization_id", "created_by"} <= cols


class TestManifestContract:
    def test_manifest_lists_budget_records(self):
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert TABLE in payload.get("legacy_tables", []), (
            "升级演练清单未登记 budget_records —— 演练会把表消失判为数据丢失"
        )
        assert payload.get("archive_prefix") == "legacy_"

    def test_migration_is_single_head_after_r36(self):
        mod = load_migration()
        assert mod.down_revision == "r36_drop_rural_tasks_001"
        assert mod.revision == "r37_drop_budget_records_001"
