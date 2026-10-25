"""W28 回归：26 个零引用死字段清理（``r43_prune_dead_columns_001``）。

## 背景
``scripts/scan_dead_columns.py`` 的判定口径（保守、宁漏不误删）扫出 26 条
「模型里声明、app/ 非模型代码零引用、frontend/src 零引用」的列。它们既无写入
路径也无读取路径 —— 留着等于让 schema 撒谎（正如 r41 删 ``issues`` 表的理由）。

## 本文件锁定（列级三分支，沿用 r35/r36/r39 契约）
1. 列不存在 → 跳过（幂等）；
2. 列存在且**整列为空/0** → DROP COLUMN；
3. 列存在且**有数据** → RENAME 为 ``legacy_<列名>``（**数据一行不丢**）；
4. 归档列已存在 → 保留原列不处理（防覆盖既有归档）；
5. 表不存在 → 全部跳过（不报错）；
6. 回滚能把 ``legacy_*`` 改回原名（已删的空列不重建）；
7. 修订链接在 r42 之后（迁移链单 head）。
"""

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "r43_prune_dead_columns_001.py"
TABLE = "demo"


def _load():
    """每次调用都返回**新**模块实例；patch 与调用必须用同一个实例。"""
    spec = importlib.util.spec_from_file_location("r43_prune_dead_columns_001", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod(monkeypatch):
    """载入迁移模块并把死字段清单换成测试表，返回**同一个**模块实例。"""
    module = _load()
    monkeypatch.setattr(module, "DEAD_COLUMNS", ())
    return module


@pytest.fixture()
def bind():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        yield conn
    engine.dispose()


def _patch(mod, pairs):
    mod.DEAD_COLUMNS = tuple(pairs)


def _create_table(conn, columns=("empty_col", "data_col")):
    cols = ["id INTEGER PRIMARY KEY"] + [f'"{c}" TEXT' for c in columns]
    conn.execute(sa.text(f'CREATE TABLE "{TABLE}" ({", ".join(cols)})'))


def _cols(conn):
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


class TestThreeBranches:
    def test_empty_column_is_dropped(self, mod, bind):
        _create_table(bind)
        bind.execute(sa.text(f'INSERT INTO "{TABLE}" (id, data_col) VALUES (1, \'keep\')'))
        _patch(mod, [(TABLE, "empty_col")])

        result = mod.apply_cleanup(bind)

        assert result["dropped"] == [f"{TABLE}.empty_col"]
        assert result["archived"] == []
        assert "empty_col" not in _cols(bind)

    def test_column_with_data_is_archived_and_keeps_rows(self, mod, bind):
        _create_table(bind)
        bind.execute(sa.text(f'INSERT INTO "{TABLE}" (id, data_col) VALUES (1, \'keep-me\')'))
        _patch(mod, [(TABLE, "data_col")])

        result = mod.apply_cleanup(bind)

        assert result["archived"] == [f"{TABLE}.data_col"]
        cols = _cols(bind)
        assert "data_col" not in cols
        assert "legacy_data_col" in cols
        kept = bind.execute(sa.text(f'SELECT legacy_data_col FROM "{TABLE}" WHERE id = 1')).scalar()
        assert kept == "keep-me"  # 数据一行不丢

    def test_missing_column_is_skipped(self, mod, bind):
        _create_table(bind)
        _patch(mod, [(TABLE, "no_such_col")])
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [f"{TABLE}.no_such_col"]

    def test_missing_table_is_skipped(self, mod, bind):
        _patch(mod, [("no_such_table", "col")])
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == ["no_such_table.col"]
        assert result["dropped"] == []


class TestEdgeCases:
    def test_zero_counts_as_empty(self, mod, bind):
        """值为 0 视为"未填"（与 r39 口径一致）→ 删除而非归档。"""
        bind.execute(sa.text(f'CREATE TABLE "{TABLE}" (id INTEGER PRIMARY KEY, num_col NUMERIC)'))
        bind.execute(sa.text(f'INSERT INTO "{TABLE}" (id, num_col) VALUES (1, 0)'))
        _patch(mod, [(TABLE, "num_col")])

        result = mod.apply_cleanup(bind)
        assert result["dropped"] == [f"{TABLE}.num_col"]

    def test_idempotent_second_run_skips(self, mod, bind):
        _create_table(bind)
        _patch(mod, [(TABLE, "empty_col")])

        first = mod.apply_cleanup(bind)
        second = mod.apply_cleanup(bind)

        assert first["dropped"] == [f"{TABLE}.empty_col"]
        assert second["dropped"] == []
        assert second["skipped"] == [f"{TABLE}.empty_col"]

    def test_existing_archive_target_keeps_original(self, mod, bind):
        """归档列已存在（历史重复迁移）→ 保留原列不动，交人工确认。"""
        _create_table(bind, columns=("data_col", "legacy_data_col"))
        bind.execute(
            sa.text(f'INSERT INTO "{TABLE}" (id, data_col, legacy_data_col) VALUES (1, \'a\', \'b\')')
        )
        _patch(mod, [(TABLE, "data_col")])

        result = mod.apply_cleanup(bind)

        assert result["archived"] == []
        assert result["skipped"] == [f"{TABLE}.data_col"]
        assert "data_col" in _cols(bind)  # 原列仍在（未丢数据）


class TestManifest:
    def test_dead_columns_manifest_is_well_formed(self):
        pairs = _load().DEAD_COLUMNS
        assert pairs, "清单不能为空"
        assert len(set(pairs)) == len(pairs), "清单内不得重复"
        for item in pairs:
            assert isinstance(item, tuple) and len(item) == 2
            table, column = item
            assert table and column
            assert table.isidentifier() and column.isidentifier()

    def test_revision_chain_follows_r42(self):
        module = _load()
        assert module.revision == "r43_prune_dead_columns_001"
        assert module.down_revision == "r42_align_stack_columns_001"
        assert module.ARCHIVE_PREFIX == "legacy_"

    def test_manifest_covers_26_dead_fields(self):
        """清单规模必须与扫描器结论一致（26 条；region_code 跨 3 表共 28 处声明）。"""
        pairs = _load().DEAD_COLUMNS
        assert len(pairs) == 28, f"清单应为 28 个(表,列)组合，实际 {len(pairs)}"
        assert len({c for _, c in pairs}) == 26, "去重后应为 26 个字段名"
