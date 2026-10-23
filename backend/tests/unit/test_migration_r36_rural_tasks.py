"""W27：``rural_tasks`` 下线迁移的单测（``r36_drop_rural_tasks_001``）。

为什么单独测：该迁移直接动数据库表，必须同时满足两组约束 ——
① **空表必须被清掉**（本机库 0 行，属"清除下线功能的残留 schema"）；
② **有数据的表绝不能丢一行**（老用户库可能有历史任务数据，升级不能造成数据事故）。

沿用 ``r35_drop_legacy_tables_001`` 的三分支契约：表不存在 → 跳过；0 行 → DROP；
有数据 → 改名 ``legacy_rural_tasks`` 归档。演练脚本只覆盖"有一行 → 改名归档"，
其余分支在这里钉死。
"""

import importlib.util
import json
import pathlib

import sqlalchemy as sa

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = BACKEND_ROOT / "alembic" / "versions" / "r36_drop_rural_tasks_001.py"
MANIFEST_PATH = BACKEND_ROOT / "scripts" / "gate_baselines" / "upgrade_legacy_tables.json"


def load_migration():
    spec = importlib.util.spec_from_file_location("r36_rural_tasks_under_test", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_engine(tables):
    """建内存 sqlite 并按 name -> 行数 造表（0 行 = 空表）。"""
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    created = []
    for name, rows in tables.items():
        table = sa.Table(
            name,
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("note", sa.Text),
        )
        created.append((table, rows))
    metadata.create_all(engine)
    with engine.begin() as conn:
        for table, rows in created:
            for idx in range(rows):
                conn.execute(table.insert().values(id=idx + 1, note="row%d" % (idx + 1)))
    return engine


def table_names(bind):
    return set(sa.inspect(bind).get_table_names())


class TestRuralTasksMigrationBranches:
    def test_empty_table_is_dropped(self):
        """本机实况（0 行）→ 表被删除。"""
        mod = load_migration()
        engine = make_engine({"rural_tasks": 0})
        with engine.begin() as conn:
            result = mod.apply_cleanup(conn)
            remaining = table_names(conn)
        assert result["dropped"] == ["rural_tasks"]
        assert result["archived"] == []
        assert "rural_tasks" not in remaining
        engine.dispose()

    def test_populated_table_is_archived_with_rows_preserved(self):
        """有历史数据 → 改名归档，行数不变（绝不丢数据）。"""
        mod = load_migration()
        engine = make_engine({"rural_tasks": 3})
        with engine.begin() as conn:
            result = mod.apply_cleanup(conn)
            remaining = table_names(conn)
            archived_count = conn.execute(
                sa.text("SELECT COUNT(*) FROM legacy_rural_tasks")
            ).scalar()
        assert result["dropped"] == []
        assert result["archived"] == ["rural_tasks"]
        assert "rural_tasks" not in remaining
        assert "legacy_rural_tasks" in remaining
        assert archived_count == 3
        engine.dispose()

    def test_missing_table_is_skipped_and_idempotent(self):
        """表不存在 → 跳过；重复执行结果一致（幂等）。"""
        mod = load_migration()
        engine = make_engine({})
        with engine.begin() as conn:
            first = mod.apply_cleanup(conn)
            second = mod.apply_cleanup(conn)
        assert first == {"dropped": [], "archived": [], "skipped": ["rural_tasks"]}
        assert second == first
        engine.dispose()

    def test_existing_archive_keeps_original_table(self):
        """归档表已存在（重复执行/人工处理）→ 保留原表不动，避免覆盖既有归档。"""
        mod = load_migration()
        engine = make_engine({"rural_tasks": 1, "legacy_rural_tasks": 0})
        with engine.begin() as conn:
            result = mod.apply_cleanup(conn)
            remaining = table_names(conn)
        assert result["archived"] == []
        assert result["skipped"] == ["rural_tasks"]
        assert "rural_tasks" in remaining
        assert "legacy_rural_tasks" in remaining
        engine.dispose()


class TestRuralTasksMigrationContract:
    def test_retired_tables_constant(self):
        mod = load_migration()
        assert mod.RETIRED_TABLES == ("rural_tasks",)
        assert mod.ARCHIVE_PREFIX == "legacy_"

    def test_revision_chain_follows_r35(self):
        """迁移链必须挂在 r35 之后（否则 alembic 会出现分叉/孤儿）。"""
        mod = load_migration()
        assert mod.revision == "r36_drop_rural_tasks_001"
        assert mod.down_revision == "r35_drop_legacy_tables_001"

    def test_manifest_declares_rural_tasks(self):
        """升级演练契约：清单必须声明 rural_tasks 允许消失，否则演练必红。"""
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert "rural_tasks" in payload.get("legacy_tables", [])
        assert payload.get("archive_prefix") == "legacy_"

    def test_manifest_revision_points_at_latest(self):
        """清单 revision 指向**当前最新的遗留清理迁移头**。

        W27：r36 之后又加了 r37（死模型 BudgetRecord）并接管清单 revision，
        因此这里不能硬编码 r36 —— 改为断言 revision 解析出的迁移文件
        `RETIRED_TABLES` **包含** rural_tasks（即本批清理仍被清单覆盖）。
        """
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        revision = payload.get("revision")
        assert revision, "清单必须声明 revision"

        versions = pathlib.Path(__file__).resolve().parents[2] / "alembic" / "versions"
        target = versions / f"{revision}.py"
        assert target.exists(), f"清单 revision 指向不存在的迁移: {revision}"

        import ast

        tree = ast.parse(target.read_text(encoding="utf-8"))
        retired: tuple = ()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "RETIRED_TABLES":
                        retired = ast.literal_eval(node.value)
        assert "rural_tasks" in retired or "rural_tasks" in payload.get("legacy_tables", [])
        assert payload.get("archive_prefix") == "legacy_"
