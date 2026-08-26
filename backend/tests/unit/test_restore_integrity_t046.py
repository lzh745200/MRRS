# -*- coding: utf-8 -*-
"""T046：恢复后完整性自检 + WAL 残留清理回归。"""
import os
import sqlite3
from unittest.mock import MagicMock, patch

from app.services.backup_service import BackupService


def _svc(tmp_path):
    db_path = tmp_path / "app.db"
    svc = BackupService.__new__(BackupService)
    svc.database_path = str(db_path)
    svc.uploads_dir = str(tmp_path / "uploads")
    return svc, str(db_path)


def _make_backup_db(tmp_path):
    p = tmp_path / "data"
    p.mkdir(parents=True)
    f = p / "rural_revitalization.db"
    conn = sqlite3.connect(str(f))
    conn.execute("CREATE TABLE t(x INTEGER)")
    conn.commit()
    conn.close()
    return str(f)


class TestRestoreIntegrity:
    def test_healthy_restore_passes_and_clears_wal(self, tmp_path):
        svc, dbp = _svc(tmp_path)
        bk = _make_backup_db(tmp_path)
        # 预置残留 wal/shm
        for suf in ("-wal", "-shm"):
            open(dbp + suf, "w").close()
        assert svc._restore_database_from_backup(str(tmp_path)) is True
        assert not os.path.exists(dbp + "-wal")
        assert not os.path.exists(dbp + "-shm")

    def test_corrupt_restore_fails_closed(self, tmp_path):
        svc, dbp = _svc(tmp_path)
        bad_dir = tmp_path / "data"
        bad_dir.mkdir(parents=True, exist_ok=True)
        bad = bad_dir / "rural_revitalization.db"
        bad.write_bytes(b"not a sqlite file at all" * 100)
        # 损坏库：integrity_check 异常/非 ok → 必须 False（fail-closed）
        assert svc._restore_database_from_backup(str(tmp_path)) is False

    def test_missing_backup_returns_false(self, tmp_path):
        svc, _ = _svc(tmp_path)
        assert svc._restore_database_from_backup(str(tmp_path / "nope")) is False
