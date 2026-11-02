"""备份恢复：历史包数据库路径回退（R57）。"""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from app.services.backup_service import BackupService


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SQLite format 3\x00")
    return path


def test_locate_canonical_path(tmp_path):
    db = _touch(tmp_path / "data" / "rural_revitalization.db")
    assert BackupService._locate_backup_db(str(tmp_path)) == str(db)


def test_locate_legacy_data_filename(tmp_path):
    db = _touch(tmp_path / "data" / "assistance.db")
    assert BackupService._locate_backup_db(str(tmp_path)) == str(db)


def test_locate_legacy_root_filename(tmp_path):
    db = _touch(tmp_path / "rural_revitalization.db")
    assert BackupService._locate_backup_db(str(tmp_path)) == str(db)


def test_locate_single_db_under_data(tmp_path):
    db = _touch(tmp_path / "data" / "old_name.sqlite")
    assert BackupService._locate_backup_db(str(tmp_path)) == str(db)


def test_locate_ambiguous_returns_none(tmp_path):
    _touch(tmp_path / "data" / "a.db")
    _touch(tmp_path / "data" / "b.db")
    assert BackupService._locate_backup_db(str(tmp_path)) is None


def test_locate_missing_returns_none(tmp_path):
    assert BackupService._locate_backup_db(str(tmp_path)) is None


def test_current_schema_revision_reads_alembic_version(tmp_path):
    db = tmp_path / "schema.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32))")
    conn.execute("INSERT INTO alembic_version VALUES ('rev_001')")
    conn.commit()
    conn.close()
    svc = SimpleNamespace(database_path=str(db))
    assert BackupService._current_schema_revision(svc) == "rev_001"


def test_current_schema_revision_missing_db_returns_none(tmp_path):
    svc = SimpleNamespace(database_path=str(tmp_path / "missing.db"))
    assert BackupService._current_schema_revision(svc) is None
