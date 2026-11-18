"""恢复后迁移：无 alembic_version 的旧库要区分「表齐全」与「真落后」两种情况。"""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from app.services.backup_service import BackupService


def _svc(db_path, tmp_path):
    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    svc.database_path = str(db_path)
    return svc


def test_migrate_legacy_with_missing_tables_replays_from_base(tmp_path):
    """真正落后的旧库（表不全）必须重放迁移链，不能直接 stamp head。

    直接 stamp head 会把落后几十个版本的库标记成最新、跳过全部迁移，
    恢复后第一次访问新列就 ``no such column``，且 stamp 已成功不会回滚。
    """
    db_path = tmp_path / "legacy-sparse.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.commit()
    conn.close()

    with (
        patch("alembic.command.stamp") as stamp,
        patch("alembic.command.upgrade") as upgrade,
    ):
        _svc(db_path, tmp_path)._migrate_restored_database()

    assert upgrade.call_count == 1, "表不全的旧库必须重放迁移"
    assert upgrade.call_args[0][1] == "head"
    assert stamp.call_count == 0, "表不全时 stamp head 会跳过全部迁移"


def test_migrate_legacy_with_full_tables_stamps_head(tmp_path):
    """schema 已是当前版本但丢了 alembic_version 时，直接 stamp head 即可。"""
    from app.models.base import Base
    import app.models  # noqa: F401

    db_path = tmp_path / "modern-lost-version.db"
    engine = __import__("sqlalchemy").create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    with (
        patch("alembic.command.stamp") as stamp,
        patch("alembic.command.upgrade") as upgrade,
    ):
        _svc(db_path, tmp_path)._migrate_restored_database()

    assert stamp.call_count == 1
    assert stamp.call_args[0][1] == "head"
    assert upgrade.call_count == 0, "表已齐全时重放历史迁移会撞已存在对象"


def test_migrate_restored_database_upgrades_when_version_present(tmp_path):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = __import__("pathlib").Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()

    db_path = tmp_path / "restored-versioned.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    conn.execute("INSERT INTO alembic_version VALUES (?)", (head,))
    conn.commit()
    conn.close()

    with patch("alembic.command.upgrade") as upgrade:
        _svc(db_path, tmp_path)._migrate_restored_database()

    assert upgrade.call_count == 1
    assert upgrade.call_args[0][1] == "head"


def test_migrate_skips_when_alembic_ini_missing(tmp_path):
    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("alembic.command.upgrade") as upgrade,
        patch("alembic.command.stamp") as stamp,
    ):
        svc._migrate_restored_database()
    # alembic.ini 缺失时必须安静跳过，不得触发任何迁移或 stamp。
    upgrade.assert_not_called()
    stamp.assert_not_called()


@pytest.mark.parametrize("tables", ["users"])
def test_svc_helper_is_isolated(tmp_path, tables):
    """冒烟：测试辅助函数不依赖全局配置。"""
    db_path = tmp_path / f"{tables}.db"
    sqlite3.connect(db_path).execute(f"CREATE TABLE {tables} (id INTEGER PRIMARY KEY)").connection.commit()
    assert _svc(db_path, tmp_path).database_path.endswith(f"{tables}.db")


def test_migrate_no_version_partial_modern_db_reconciles_not_replays(tmp_path):
    """无版本号但表很多：必须按模型补表补列 + stamp，不能重放撞已有索引。"""
    db_path = tmp_path / "partial-modern.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    for i in range(20):
        conn.execute(f"CREATE TABLE dummy_{i} (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    with (
        patch("alembic.command.stamp") as stamp,
        patch("alembic.command.upgrade") as upgrade,
    ):
        _svc(db_path, tmp_path)._migrate_restored_database()

    assert stamp.call_count == 1
    assert stamp.call_args[0][1] == "head"
    assert upgrade.call_count == 0
    # 缺的当前表/列必须真的被补上，而不是只改版本号
    chk = sqlite3.connect(db_path)
    tables = {r[0] for r in chk.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cols = {r[1] for r in chk.execute("PRAGMA table_info(users)")}
    chk.close()
    assert "account_package_exports" in tables
    assert "credential_expires_at" in cols
