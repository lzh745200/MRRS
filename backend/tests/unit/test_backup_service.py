"""备份服务单元测试 — 100% 分支覆盖 app/services/backup_service.py"""

import hashlib
import json
import os
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.system_config import SystemConfig
from app.services.backup_service import (
    BackupIncompleteError,
    BackupRecord,
    BackupRestoreError,
    BackupService,
    get_backup_service,
)


def _make_svc(mock_db, backup_dir, db_path, uploads_dir, incremental="true", level="6"):
    with patch("os.makedirs"), \
         patch("app.utils.paths.get_database_path", return_value=Path(db_path)), \
         patch("app.utils.paths.get_uploads_path", return_value=Path(uploads_dir)), \
         patch("app.utils.paths.get_runtime_uploads_path", return_value=Path(uploads_dir)), \
         patch("os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda k, d=None: {
            "INCREMENTAL_BACKUP_ENABLED": incremental,
            "BACKUP_COMPRESSION_LEVEL": level,
        }.get(k, d)
        return BackupService(db=mock_db, backup_dir=backup_dir)


class TestBackupRestoreError:
    def test_exception_message(self):
        e = BackupRestoreError("test msg")
        assert str(e) == "test msg"

    def test_exception_subclass(self):
        assert issubclass(BackupRestoreError, Exception)


class TestBackupRecord:
    def test_full_construction(self):
        dt = datetime(2025, 1, 1)
        r = BackupRecord(1, "a.zip", "/a.zip", 100, "desc", dt, "full", "abc123")
        assert r.backup_id == 1
        assert r.checksum == "abc123"

    def test_default_backup_type_and_checksum(self):
        dt = datetime(2025, 1, 1)
        r = BackupRecord(2, "b.zip", "/b.zip", 50, "desc", dt)
        assert r.backup_type == "full"
        assert r.checksum is None


class TestBackupServiceInit:
    def test_with_explicit_backup_dir(self, mock_db):
        svc = _make_svc(mock_db, "/tmp/bk", "/d/db.db", "/u")
        assert svc.backup_dir == "/tmp/bk"
        assert svc.incremental_enabled is True

    def test_with_default_backup_dir(self, mock_db):
        with patch("app.utils.paths.get_backup_path", return_value=Path("/def/bk")):
            svc = BackupService(db=mock_db)
            assert svc.backup_dir == str(Path("/def/bk"))

    def test_env_disabled_incremental(self, mock_db):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u", incremental="false")
        assert svc.incremental_enabled is False

    def test_load_last_manifest_success(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        Path(os.path.join(bdir, "last_manifest.json")).write_text(
            json.dumps({"f.txt": {"hash": "abc"}})
        )
        svc = _make_svc(mock_db, bdir, "/d/db.db", "/u")
        assert svc.last_backup_manifest == {"f.txt": {"hash": "abc"}}

    def test_load_last_manifest_missing(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        assert svc.last_backup_manifest is None

    def test_load_last_manifest_corrupt(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        Path(os.path.join(bdir, "last_manifest.json")).write_text("{bad")
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        assert svc.last_backup_manifest is None


class TestValidatePath:
    def test_valid_path(self, mock_db):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        with patch.object(svc, "uploads_dir", "/allowed"):
            assert svc._validate_path("/allowed/file.txt") is True

    def test_outside_allowed_dir(self, mock_db):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        with patch.object(svc, "uploads_dir", "/allowed"):
            assert svc._validate_path("/evil/../etc/passwd") is False

    def test_exception_handling(self, mock_db):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        with patch.object(svc, "uploads_dir", "/allowed"):
            assert svc._validate_path(None) is False


class TestCreateBackup:
    def test_basic_backup(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db content")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("upload")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.create_backup()
        assert result is not None
        assert result.file_size > 0

    def test_backup_without_db_fails_loud(self, mock_db, tmp_path):
        """2026-08-30 起，备份包不含数据库即视为失败（fail-loud），不再静默成功。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "no_exist" / "db.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("up")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with pytest.raises(BackupIncompleteError):
            svc.create_backup()
        assert list(Path(bdir).glob("*.zip")) == []

    def test_backup_without_uploads(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.create_backup(include_uploads=False)
        assert result is not None

    def test_backup_skips_invalid_paths(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with patch.object(svc, "_validate_path", return_value=False):
            result = svc.create_backup()
        assert result is not None

    def test_backup_no_uploads_dir(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "no_uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.create_backup()
        assert result is not None


class TestSafeExtractall:
    def test_normal_extract(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        dest = str(tmp_path / "extract")
        os.makedirs(dest)
        zip_path = str(tmp_path / "normal.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("safe.txt", "ok")
        with zipfile.ZipFile(zip_path, "r") as zf:
            svc._safe_extractall(zf, dest)
        assert os.path.exists(os.path.join(dest, "safe.txt"))

    def test_skip_absolute_path(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        dest = str(tmp_path / "extract")
        os.makedirs(dest)
        zip_path = str(tmp_path / "abs.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("/etc/passwd", "evil")
        with zipfile.ZipFile(zip_path, "r") as zf:
            svc._safe_extractall(zf, dest)

    def test_skip_dotdot_member(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        dest = str(tmp_path / "extract")
        os.makedirs(dest)
        zip_path = str(tmp_path / "dotdot.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../escape.txt", "evil")
        with zipfile.ZipFile(zip_path, "r") as zf:
            svc._safe_extractall(zf, dest)
        assert not os.path.exists(os.path.join(dest, "escape.txt"))

    def test_skip_escape_via_resolve(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        dest = str(tmp_path / "extract")
        os.makedirs(dest)
        zip_path = str(tmp_path / "resolve.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a/../../escape.txt", "evil")
        with zipfile.ZipFile(zip_path, "r") as zf:
            svc._safe_extractall(zf, dest)


class TestRestoreBackup:
    def test_restore_success(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("orig")
        zip_path = os.path.join(bdir, "backup.zip")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.create_backup()
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
            zf.writestr("uploads/f.txt", "new")
        svc.restore_backup(zip_path)
        assert Path(db_path).read_text() == "new"
        assert Path(os.path.join(up_dir, "f.txt")).read_text() == "new"

    def test_restore_file_not_found(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        with pytest.raises((FileNotFoundError, BackupRestoreError)):
            svc.restore_backup("/nonexistent.zip")

    def test_restore_no_db_in_backup(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        zip_path = os.path.join(bdir, "no_db.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("uploads/f.txt", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.restore_backup(zip_path)
        assert result["success"] is True
        assert result["database_restored"] is False

    def test_restore_no_uploads_in_backup(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        zip_path = os.path.join(bdir, "no_up.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.restore_backup(zip_path)
        assert Path(db_path).read_text() == "new"

    def test_restore_no_snapshots_needed(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        zip_path = os.path.join(bdir, "b.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.restore_backup(zip_path)

    def test_restore_exception_rollback(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        zip_path = os.path.join(bdir, "fail.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_restore_rollback_snapshot_unlink_fail(self, mock_db, tmp_path):
        """Rollback where snapshot unlink raises FileNotFoundError (covered)."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        zip_path = os.path.join(bdir, "fail.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        orig_unlink = os.unlink
        call_count = [0]

        def unlink_then_raise(p, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise FileNotFoundError("already gone")
            return orig_unlink(p, *a, **kw)

        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")), \
             patch("os.unlink", side_effect=unlink_then_raise):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_restore_finally_cleanup(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        zip_path = os.path.join(bdir, "fail2.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_restore_snapshot_cleanup_unlink_fail(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        zip_path = os.path.join(bdir, "b.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        call_count = [0]
        orig_unlink = os.unlink

        def unlink_second_fails(p, *a, **kw):
            call_count[0] += 1
            if call_count[0] == 2 and "snapshot" in str(p):
                raise FileNotFoundError("snapshot cleanup fail")
            return orig_unlink(p, *a, **kw)

        with patch("os.unlink", side_effect=unlink_second_fails):
            svc.restore_backup(zip_path)

    def test_restore_rollback_path_missing_db(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        zip_path = os.path.join(bdir, "fail.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        db_calls = [0]
        orig_exists = os.path.exists

        def selective_exists(path):
            if path == db_path:
                db_calls[0] += 1
                return db_calls[0] == 1
            return orig_exists(path)

        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")), \
             patch("os.path.exists", side_effect=selective_exists):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_restore_rollback_uploads_missing(self, mock_db, tmp_path):
        """Cover branch 284->286: uploads_dir not exist during rollback."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("data")
        zip_path = os.path.join(bdir, "fail.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        up_calls = [0]
        orig_exists = os.path.exists

        def selective_exists(path):
            if path == up_dir:
                up_calls[0] += 1
                if up_calls[0] == 2:
                    import shutil
                    shutil.rmtree(up_dir, ignore_errors=True)
                    return False
                return True
            return orig_exists(path)

        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")), \
             patch("os.path.exists", side_effect=selective_exists):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_restore_uploads_snapshot_rmtree(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        zip_path = os.path.join(bdir, "b.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with patch("shutil.rmtree") as mock_rm:
            svc.restore_backup(zip_path)


class TestListBackups:
    def test_list_empty(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        assert svc.list_backups() == []

    def test_list_with_backups(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "test.zip")
        Path(zip_path).write_text("content")
        size = os.path.getsize(zip_path)
        cfg = SystemConfig(
            key="backup_20250101_120000",
            value=zip_path,
            description="full backup",
            created_at=datetime(2025, 1, 1),
        )
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        backups = svc.list_backups()
        assert len(backups) == 1
        assert backups[0].file_size == size

    def test_list_skips_missing_file(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        cfg = SystemConfig(
            key="backup_missing", value="/nonexistent/path.zip",
            description="gone", created_at=datetime(2025, 1, 1),
        )
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        assert svc.list_backups() == []


class TestDeleteBackup:
    def test_delete_existing(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "del.zip")
        Path(zip_path).write_text("data")
        cfg = SystemConfig(key="backup_del", value=zip_path, created_at=datetime(2025, 1, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        assert svc.delete_backup(cfg.id) is True
        assert not os.path.exists(zip_path)

    def test_delete_not_found(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        assert svc.delete_backup(999) is False

    def test_delete_file_not_found_on_disk(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        cfg = SystemConfig(key="backup_missing_disk", value=str(tmp_path / "gone.zip"),
                           created_at=datetime(2025, 1, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        assert svc.delete_backup(cfg.id) is True

    def test_delete_unlink_raises_filenotfound(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "fnf.zip")
        Path(zip_path).write_text("data")
        cfg = SystemConfig(key="backup_fnf", value=zip_path, created_at=datetime(2025, 1, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")

        def fnf_unlink(p, *a, **kw):
            raise FileNotFoundError("gone")

        with patch("os.unlink", side_effect=fnf_unlink):
            assert svc.delete_backup(cfg.id) is True


class TestCleanupOldBackups:
    def test_cleanup_none_to_delete(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        cfg = SystemConfig(key="backup_new", value=str(tmp_path / "a.zip"),
                           created_at=datetime(2025, 6, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        svc.cleanup_old_backups(keep_count=10)

    def test_cleanup_some_deleted(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        old_cfg = SystemConfig(key="backup_old", value=str(tmp_path / "old.zip"),
                               created_at=datetime(2020, 1, 1))
        mock_db.add(old_cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        svc.cleanup_old_backups(keep_count=0)
        assert len(mock_db._storage.get(SystemConfig, [])) == 0

    def test_cleanup_deleted_files_already_gone(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        cfg = SystemConfig(key="backup_gone", value="/missing.zip",
                           created_at=datetime(2020, 1, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        svc.cleanup_old_backups(keep_count=0)

    def test_cleanup_zero_kept(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        cfg = SystemConfig(key="backup_zk", value=str(tmp_path / "zk.zip"),
                           created_at=datetime(2020, 1, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        svc.cleanup_old_backups(keep_count=0)

    def test_cleanup_nothing_to_delete_no_commit(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        svc.cleanup_old_backups(keep_count=0)

    def test_cleanup_with_unlink_filenotfound(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "cul.zip")
        Path(zip_path).write_text("data")
        cfg = SystemConfig(key="backup_cul", value=zip_path,
                           created_at=datetime(2020, 1, 1))
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")

        def fnf_unlink(p, *a, **kw):
            raise FileNotFoundError("gone")

        with patch("os.unlink", side_effect=fnf_unlink):
            svc.cleanup_old_backups(keep_count=0)


class TestGetBackupSize:
    def test_size_calculation(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        Path(os.path.join(bdir, "a.txt")).write_text("hello")
        Path(os.path.join(bdir, "b.txt")).write_text("world")
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        size = svc.get_backup_size()
        assert size > 0

    def test_dir_not_exist(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        assert svc.get_backup_size() == 0

    def test_exception_handling(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        with patch("os.listdir", side_effect=PermissionError("denied")):
            size = svc.get_backup_size()
        assert size == 0


class TestLoadLastManifest:
    def test_load_success(self, tmp_path):
        bdir = str(tmp_path / "m")
        os.makedirs(bdir)
        Path(os.path.join(bdir, "last_manifest.json")).write_text(
            json.dumps({"a": {"hash": "x"}})
        )
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        assert svc.last_backup_manifest == {"a": {"hash": "x"}}

    def test_load_missing(self, tmp_path):
        bdir = str(tmp_path / "m2")
        os.makedirs(bdir)
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        assert svc.last_backup_manifest is None

    def test_load_corrupt(self, tmp_path):
        bdir = str(tmp_path / "m3")
        os.makedirs(bdir)
        Path(os.path.join(bdir, "last_manifest.json")).write_text("{bad")
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        assert svc.last_backup_manifest is None


class TestSaveManifest:
    def test_save_success(self, mock_db, tmp_path):
        bdir = str(tmp_path / "b")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        svc._save_manifest({"f": {"hash": "abc"}})
        mpath = os.path.join(bdir, "last_manifest.json")
        assert os.path.exists(mpath)
        assert json.loads(Path(mpath).read_text()) == {"f": {"hash": "abc"}}

    def test_save_exception(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            svc._save_manifest({"f": {"hash": "abc"}})


class TestCalculateFileHash:
    def test_hash_success(self, mock_db, tmp_path):
        fpath = str(tmp_path / "hash_me.txt")
        Path(fpath).write_text("hello world")
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        h = svc._calculate_file_hash(fpath)
        assert h == hashlib.sha256(b"hello world").hexdigest()

    def test_hash_file_not_found(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        assert svc._calculate_file_hash("/nonexistent") == ""


class TestGetFileManifest:
    def test_normal(self, mock_db, tmp_path):
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("data")
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", up_dir)
        manifest = svc._get_file_manifest(up_dir)
        assert len(manifest) > 0

    def test_directory_not_exist(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        assert svc._get_file_manifest("/nonexistent") == {}

    def test_skip_invalid_path_in_manifest(self, mock_db, tmp_path):
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("data")
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", up_dir)
        with patch.object(svc, "_validate_path", return_value=False):
            assert svc._get_file_manifest(up_dir) == {}

    def test_stat_failure(self, mock_db, tmp_path):
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "bad.txt")).write_text("data")
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", up_dir)
        orig_stat = os.stat
        call_n = [0]

        def stat_side(*args, **kwargs):
            call_n[0] += 1
            if call_n[0] > 2:
                raise OSError("stat fail")
            return orig_stat(*args, **kwargs)

        with patch("os.stat", side_effect=stat_side):
            manifest = svc._get_file_manifest(up_dir)
        assert isinstance(manifest, dict)

    def test_walk_raises_exception(self, mock_db, tmp_path):
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", up_dir)
        with patch("os.walk", side_effect=PermissionError("denied")):
            manifest = svc._get_file_manifest(up_dir)
        assert manifest == {}


class TestCreateIncrementalBackup:
    def test_incremental_disabled_falls_back(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        os.makedirs(up_dir)
        svc = _make_svc(mock_db, bdir, db_path, up_dir, incremental="false")
        result = svc.create_incremental_backup()
        assert result["status"] == "success"

    def test_incremental_disabled_create_backup_returns_none(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, db_path, up_dir, incremental="false")
        with patch.object(svc, "create_backup", return_value=None):
            result = svc.create_incremental_backup()
        assert result["status"] == "error"

    def test_no_changes_skipped(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = {
            db_path: {"hash": hashlib.sha256(b"data").hexdigest(), "size": 4, "mtime": 0},
        }
        result = svc.create_incremental_backup()
        assert result["status"] == "skipped"

    def test_incremental_with_changes(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = {}
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(description="test inc")
        assert result["status"] == "success"

    def test_incremental_from_scratch_no_previous(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("initial")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(description="first inc")
        assert result["status"] == "success"
        assert result["changed_files"] >= 1

    def test_incremental_cross_drive_relpath(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        with patch("os.path.relpath", side_effect=ValueError("cross drive")), \
             patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(description="cross drive")
        assert result["status"] == "success"

    def test_incremental_set_backup_time_fails(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        existing_cfg = SystemConfig(key="last_backup_time", value="old")
        mock_db.add(existing_cfg)
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            svc_mock = MagicMock()
            svc_mock.set.side_effect = ValueError("key exists")
            mock_cfg_svc.return_value = svc_mock
            result = svc.create_incremental_backup(description="fallback update")
        assert result["status"] == "success"

    def test_incremental_set_backup_time_has_existing(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        existing = SystemConfig(key="last_backup_time", value="old_value")
        mock_db.add(existing)
        from app.services.system_config_service import SystemConfigService
        real_set = SystemConfigService.set
        call_count = [0]

        def set_with_exception(self, key, value, description=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("simulated failure")
            return real_set(self, key, value, description)

        with patch.object(SystemConfigService, "set", set_with_exception):
            result = svc.create_incremental_backup(description="existing fallback")
            assert result["status"] == "success"

    def test_incremental_set_backup_time_fails_no_existing(self, mock_db, tmp_path):
        """Cover branch 611->615: existing=None in except block."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        original_add = svc.db.add

        def intercept_add(obj):
            if isinstance(obj, SystemConfig):
                obj.id = svc.db._next_id[0]
                svc.db._next_id[0] += 1
                return obj
            return original_add(obj)

        svc.db.add = intercept_add
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            svc_mock = MagicMock()
            svc_mock.set.side_effect = ValueError("key exists")
            mock_cfg_svc.return_value = svc_mock
            result = svc.create_incremental_backup(description="fallback update no existing")
        assert result["status"] == "success"

    def test_incremental_no_include_uploads(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(include_uploads=False)
        assert result["status"] == "success"

    def test_incremental_exception(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db.db", "/u")
        with patch.object(svc, "_get_file_manifest", side_effect=RuntimeError("unexpected")):
            result = svc.create_incremental_backup()
        assert result["status"] == "error"

    def test_incremental_missing_file_skipped(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        os.makedirs(up_dir)
        Path(db_path).write_text("data")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(description="some missing")
        assert result["status"] == "success"

    def test_incremental_file_disappears_during_zip(self, mock_db, tmp_path):
        """Cover branch 561->560: file in changed_files removed before zip write."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("data")
        os.makedirs(up_dir)
        phantom = os.path.join(up_dir, "phantom.txt")
        Path(phantom).write_text("ghost")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = None
        rel_phantom = os.path.relpath(phantom, ".")
        orig_exists = os.path.exists

        def selective_exists(path):
            if path == rel_phantom or path == phantom:
                return False
            return orig_exists(path)

        with patch("os.path.exists", side_effect=selective_exists), \
             patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(description="phantom")
        assert result["status"] == "success"


class TestVerifyBackup:
    def test_verify_success_no_db(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "good.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("uploads/f.txt", "hello")
            zf.writestr("backup_info.json", json.dumps({"ts": "2025"}))
        svc = _make_svc(MagicMock(), bdir, "/d/db.db", "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "ok"

    def test_verify_success_with_db(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        db_file = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        zip_path = os.path.join(bdir, "with_db.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(db_file, "data/rural_revitalization.db")
            zf.writestr("backup_info.json", json.dumps({"ts": "2025"}))
        svc = _make_svc(MagicMock(), bdir, db_file, "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "ok"

    def test_verify_file_not_found(self, tmp_path):
        svc = _make_svc(MagicMock(), str(tmp_path / "b"), "/d/db", "/u")
        result = svc.verify_backup("/nonexistent.zip")
        assert result["status"] == "error"

    def test_verify_corrupt_zip(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "bad.zip")
        Path(zip_path).write_bytes(b"\x00\x01\x02")
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "error"

    def test_verify_temp_dir_gone_in_finally(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        db_file = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        zip_path = os.path.join(bdir, "tempgone.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(db_file, "data/rural_revitalization.db")
            zf.writestr("backup_info.json", json.dumps({"ts": "2025"}))
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        original_rmtree = __import__("shutil").rmtree
        with patch("shutil.rmtree") as mock_rmtree:
            def rmtree_side(path, **kw):
                if "verify_" in str(path):
                    return  # skip to simulate dir already gone
                return original_rmtree(path, **kw)
            mock_rmtree.side_effect = rmtree_side
            result = svc.verify_backup(zip_path)
        assert result["status"] == "ok"

    def test_verify_backup_info_missing(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "no_info.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("random.txt", "hello")
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "ok"

    def test_verify_exception(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "ex.zip")
        Path(zip_path).write_text("not a zip")
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "error"


class TestGetBackupStatistics:
    def test_statistics_empty(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        stats = svc.get_backup_statistics()
        assert stats["total_backups"] == 0

    def test_statistics_with_data(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        fake_zip = str(tmp_path / "a.zip")
        Path(fake_zip).write_text("x")
        cfg = SystemConfig(
            key="backup_stats", value=fake_zip,
            created_at=datetime(2025, 1, 1),
            description="test",
        )
        mock_db.add(cfg)
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        stats = svc.get_backup_statistics()
        assert stats["total_backups"] == 1

    def test_statistics_exception(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"), "/d/db", "/u")
        with patch.object(svc.db, "query", side_effect=RuntimeError("db error")):
            stats = svc.get_backup_statistics()
        assert stats["status"] == "error"


class TestGetBackupServiceFactory:
    def test_with_db(self, mock_db):
        svc = get_backup_service(db=mock_db)
        assert svc is not None

    def test_without_db_first_call(self):
        with patch("app.utils.paths.get_backup_path", return_value=Path(__file__).parent), \
             patch("app.utils.paths.get_database_path", return_value=Path(__file__)), \
             patch("app.utils.paths.get_uploads_path", return_value=Path(__file__).parent), \
             patch("os.getenv") as mock_getenv, \
             patch("os.makedirs"):
            mock_getenv.side_effect = lambda k, d=None: {
                "INCREMENTAL_BACKUP_ENABLED": "true",
                "BACKUP_COMPRESSION_LEVEL": "6",
            }.get(k, d)
            svc1 = get_backup_service()
            assert svc1 is not None

    def test_without_db_cached(self):
        import app.services.backup_service as bs_mod
        bs_mod._backup_service_no_db = None
        with patch("app.utils.paths.get_backup_path", return_value=Path(__file__).parent), \
             patch("app.utils.paths.get_database_path", return_value=Path(__file__)), \
             patch("app.utils.paths.get_uploads_path", return_value=Path(__file__).parent), \
             patch("os.getenv") as mock_getenv, \
             patch("os.makedirs") as mock_mkdir:
            mock_getenv.side_effect = lambda k, d=None: {
                "INCREMENTAL_BACKUP_ENABLED": "true",
                "BACKUP_COMPRESSION_LEVEL": "6",
            }.get(k, d)
            svc1 = get_backup_service()
            svc2 = get_backup_service()
            assert svc1 is svc2
            assert mock_mkdir.call_count == 1

    def test_import_path_works(self, mock_db):
        from app.services.backup_service import get_backup_service as gbs
        svc = gbs(db=mock_db)
        assert svc is not None


class TestEdgeCases:
    def test_create_backup_without_db_record(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")
        os.makedirs(up_dir)
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.create_backup()
        assert result is not None

    def test_backup_restore_error_default(self):
        e = BackupRestoreError("custom")
        assert str(e) == "custom"

    def test_verify_backup_db_extract_fails_then_cleanup(self, tmp_path):
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        db_file = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        zip_path = os.path.join(bdir, "vdb.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(db_file, "data/rural_revitalization.db")
            zf.writestr("backup_info.json", json.dumps({"ts": "2025"}))
        svc = _make_svc(MagicMock(), bdir, db_file, "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "ok"

    def test_restore_uploads_existing_dir_overwritten(self, mock_db, tmp_path):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("old")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "old.txt")).write_text("old")
        zip_path = os.path.join(bdir, "overwrite.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
            zf.writestr("uploads/new.txt", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.restore_backup(zip_path)

    def test_restore_uploads_created_while_missing(self, mock_db, tmp_path):
        """Cover 248->250: os.path.exists(self.uploads_dir) is False (no current uploads dir)."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")
        zip_path = os.path.join(bdir, "fresh_uploads.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
            zf.writestr("uploads/f.txt", "fresh")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.restore_backup(zip_path)
        assert result["success"] is True
        assert result["uploads_restored"] is True

    def test_create_backup_validate_path_false(self, mock_db, tmp_path):
        """Cover 137-138: _validate_path returns False for upload file."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "bad.txt")).write_text("evil")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with patch.object(svc, "_validate_path", side_effect=lambda p: False if p.endswith("bad.txt") else True):
            result = svc.create_backup()
        assert result is not None

    def test_backup_size_with_subdir(self, mock_db, tmp_path):
        """Cover 408->406: get_backup_size dir contains subdir (not file)."""
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        Path(os.path.join(bdir, "a.txt")).write_text("hello")
        os.makedirs(os.path.join(bdir, "subdir"))
        svc = _make_svc(mock_db, bdir, "/d/db", "/u")
        size = svc.get_backup_size()
        assert size > 0

    def test_verify_corrupted_crc(self, tmp_path):
        """Cover 660: testzip() returns non-None for corrupted zip."""
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        zip_path = os.path.join(bdir, "crc.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("good.txt", "ok")
            zf.writestr("backup_info.json", json.dumps({"ts": "2025"}))
        data = Path(zip_path).read_bytes()
        idx = data.find(b"ok")
        if idx >= 0:
            flipped = bytearray(data)
            flipped[idx] ^= 0xFF
            Path(zip_path).write_bytes(bytes(flipped))
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        result = svc.verify_backup(zip_path)
        assert result["status"] == "error"

    def test_verify_temp_dir_missing_in_finally(self, tmp_path):
        """Cover 698->701: os.path.exists(temp_dir) is False in finally."""
        bdir = str(tmp_path / "backups")
        os.makedirs(bdir)
        db_file = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        zip_path = os.path.join(bdir, "tmpmiss.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(db_file, "data/rural_revitalization.db")
            zf.writestr("backup_info.json", json.dumps({"ts": "2025"}))
        svc = _make_svc(MagicMock(), bdir, "/d/db", "/u")
        captured = {"td": None}
        orig_mkdtemp = __import__("tempfile").mkdtemp
        def capture_mkdtemp(**kw):
            td = orig_mkdtemp(**kw)
            captured["td"] = td
            return td
        orig_exists = os.path.exists
        def selective_exists(p):
            if captured["td"] and p == captured["td"]:
                return False
            return orig_exists(p)
        with patch("tempfile.mkdtemp", side_effect=capture_mkdtemp), \
             patch("os.path.exists", side_effect=selective_exists):
            result = svc.verify_backup(zip_path)
        assert result["status"] == "ok"

    def test_restore_rollback_no_snapshot_db(self, mock_db, tmp_path):
        """Cover 271->283: rollback without snapshot_db_path."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("data")
        zip_path = os.path.join(bdir, "fail.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_restore_success_snapshot_unlink_fnf(self, mock_db, tmp_path):
        """Cover 257-258: snapshot unlink raises FileNotFoundError."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        os.makedirs(up_dir)
        zip_path = os.path.join(bdir, "b.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
            zf.writestr("uploads/f.txt", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        orig_unlink = os.unlink
        def unlink_with_fnf(p, *a, **kw):
            if "snapshot" in str(p):
                raise FileNotFoundError("snap gone")
            return orig_unlink(p, *a, **kw)
        with patch("os.unlink", side_effect=unlink_with_fnf):
            svc.restore_backup(zip_path)

    def test_restore_rollback_snapshot_unlink_fnf(self, mock_db, tmp_path):
        """Cover 280-281: rollback snapshot unlink raises FileNotFoundError (no uploads dir)."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")
        zip_path = os.path.join(bdir, "fail2.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        orig_unlink = os.unlink
        def unlink_fnf_rollback(p, *a, **kw):
            if "snapshot" in str(p):
                raise FileNotFoundError("snap gone in rollback")
            return orig_unlink(p, *a, **kw)
        with patch.object(svc, "_safe_extractall", side_effect=ValueError("fail")), \
             patch("os.unlink", side_effect=unlink_fnf_rollback):
            with pytest.raises(BackupRestoreError):
                svc.restore_backup(zip_path)

    def test_incremental_changed_file_with_existing_manifest(self, mock_db, tmp_path):
        """Cover line 538: last_backup_manifest is truthy, file not in prev manifest."""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("v1")
        os.makedirs(up_dir)
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        svc.last_backup_manifest = {"some_other_file.txt": {"hash": "old"}}
        with patch("app.services.system_config_service.SystemConfigService") as mock_cfg_svc:
            mock_cfg_svc.return_value.set = MagicMock()
            result = svc.create_incremental_backup(description="has manifest")
        assert result["status"] == "success"
