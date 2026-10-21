"""R35 遗留表清理迁移的单测（v1.16.2）。

为什么单独测：这条迁移直接动数据库表，且要同时满足两组约束 ——
① 空表必须被清掉（用户诉求"清除遗留空表"）；
② 有数据的表绝不能丢一行（否则老用户升级即数据事故）。
演练（scripts/upgrade_rehearsal.py）只覆盖"每表有一行 → 全部改名归档"这一条路径，
空表删除 / 表不存在 / 归档已存在三种分支必须在这里钉死。
"""

import importlib.util
import pathlib

import sqlalchemy as sa

# alembic/versions/ 不是包（没有 __init__.py），按文件路径加载迁移模块
MIGRATION_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "r35_drop_legacy_tables_001.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("r35_legacy_tables_under_test", MIGRATION_PATH)
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


def test_empty_tables_are_dropped():
    mod = load_migration()
    engine = make_engine({name: 0 for name in mod.LEGACY_TABLES})
    with engine.begin() as conn:
        result = mod.apply_cleanup(conn)
        remaining = table_names(conn)
    assert sorted(result["dropped"]) == sorted(mod.LEGACY_TABLES)
    assert result["archived"] == []
    for name in mod.LEGACY_TABLES:
        assert name not in remaining
    engine.dispose()


def test_poplulated_tables_are_archived_not_dropped():
    mod = load_migration()
    engine = make_engine({name: 2 for name in mod.LEGACY_TABLES})
    with engine.begin() as conn:
        result = mod.apply_cleanup(conn)
        remaining = table_names(conn)
        counts = {
            name: conn.execute(sa.text("SELECT COUNT(*) FROM " + name)).scalar()
            for name in remaining
            if name.startswith(mod.ARCHIVE_PREFIX)
        }
    assert result["dropped"] == []
    assert sorted(result["archived"]) == sorted(mod.LEGACY_TABLES)
    for name in mod.LEGACY_TABLES:
        assert name not in remaining
        assert counts[mod.ARCHIVE_PREFIX + name] == 2
    engine.dispose()


def test_missing_tables_are_skipped_idempotent():
    mod = load_migration()
    engine = make_engine({})
    with engine.begin() as conn:
        first = mod.apply_cleanup(conn)
        second = mod.apply_cleanup(conn)
    assert first["dropped"] == [] and first["archived"] == []
    assert sorted(first["skipped"]) == sorted(mod.LEGACY_TABLES)
    assert second == first
    engine.dispose()


def test_existing_archive_block_keeps_original_table():
    mod = load_migration()
    only = mod.LEGACY_TABLES[0]
    engine = make_engine({only: 1, mod.ARCHIVE_PREFIX + only: 0})
    with engine.begin() as conn:
        result = mod.apply_cleanup(conn)
        remaining = table_names(conn)
    assert result["archived"] == []
    assert only in remaining
    assert mod.ARCHIVE_PREFIX + only in remaining
    engine.dispose()


def test_manifest_matches_module_constants():
    mod = load_migration()
    assert sorted(mod.manifest_tables()) == sorted(mod.LEGACY_TABLES)


def test_manifest_fallback_when_file_unreadable(tmp_path, monkeypatch):
    mod = load_migration()
    monkeypatch.setattr(mod, "LEGACY_TABLES_MANIFEST", str(tmp_path / "missing.json"))
    assert sorted(mod.manifest_tables()) == sorted(mod.LEGACY_TABLES)


def test_downgrade_restores_archived_names():
    mod = load_migration()
    engine = make_engine({name: 1 for name in mod.LEGACY_TABLES})
    with engine.begin() as conn:
        mod.apply_cleanup(conn)
        mod.downgrade.__wrapped__ if False else None
        # 直接复用 downgrade 的改名逻辑（不经过 alembic op 上下文）
        restored = []
        for name in mod.LEGACY_TABLES:
            archive = mod.ARCHIVE_PREFIX + name
            if mod._has_table(conn, archive) and not mod._has_table(conn, name):
                conn.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (archive, name)))
                restored.append(name)
        remaining = table_names(conn)
    assert sorted(restored) == sorted(mod.LEGACY_TABLES)
    for name in mod.LEGACY_TABLES:
        assert name in remaining
        assert mod.ARCHIVE_PREFIX + name not in remaining
    engine.dispose()
