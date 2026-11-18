"""恢复后迁移：旧库无 alembic_version 时 stamp 基线并重放到 head，且只作用于恢复库。"""

import sqlite3
from unittest.mock import MagicMock, patch

from app.services.backup_service import BackupService


def test_migrate_restored_database_stamps_base_then_upgrades(tmp_path):
    """无版本表的旧库必须先 stamp 基线再重放，不能直接 stamp head。

    直接 stamp head 会把落后几十个版本的库标记成最新、跳过全部迁移，
    恢复后第一次访问新列就 ``no such column``，且 stamp 已成功不会回滚。
    """
    db_path = tmp_path / "restored.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.commit()
    conn.close()

    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    svc.database_path = str(db_path)
    with (
        patch("alembic.command.stamp") as stamp,
        patch("alembic.command.upgrade") as upgrade,
    ):
        svc._migrate_restored_database()

    assert stamp.call_count == 1, "旧库应先 stamp 一次基线"
    assert stamp.call_args[0][1] == "001", "必须 stamp 到迁移链基线而不是 head"
    assert upgrade.call_count == 1, "stamp 基线后必须重放迁移到 head"
    assert upgrade.call_args[0][1] == "head"


def test_migrate_legacy_lost_version_db_reaches_head_with_data(tmp_path):
    """真库回归：schema 已是当前版本但丢了 alembic_version 时，重放必须幂等。"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = __import__("pathlib").Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()

    db_path = tmp_path / "legacy-lost-version.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.execute("INSERT INTO users (username) VALUES ('legacy_admin')")
    conn.commit()
    conn.close()

    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    svc.database_path = str(db_path)
    svc._migrate_restored_database()

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == head
        assert conn.execute("SELECT username FROM users").fetchone()[0] == "legacy_admin"
    finally:
        conn.close()


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

    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    svc.database_path = str(db_path)
    svc._migrate_restored_database()

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == head
    finally:
        conn.close()


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
