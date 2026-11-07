"""恢复后迁移：旧库无 alembic_version 时 stamp 到 head，且只作用于恢复库。"""

import sqlite3
from unittest.mock import MagicMock, patch

from app.services.backup_service import BackupService


def test_migrate_restored_database_stamps_legacy_db(tmp_path):
    db_path = tmp_path / "restored.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.commit()
    conn.close()

    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    svc.database_path = str(db_path)
    svc._migrate_restored_database()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    finally:
        conn.close()
    assert rows, "恢复后应写入 alembic head 版本"


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
