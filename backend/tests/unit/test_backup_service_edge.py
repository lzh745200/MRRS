"""app.services.backup_service 错误/边缘路径覆盖补充测试。

覆盖现有测试未触达的防御性分支：
- _ensure_disk_space 磁盘不足 raise（223-227）
- _create_consistency_snapshot 快照失败回退 + os.remove OSError（254-255）
- _write_backup_zip 写失败删除半成品（304-310）+ finally 清理快照 OSError（316-317）
- create_backup 完整性校验打开失败（355-356）+ 删除半成品 OSError（360-361）
- _create_snapshots 一致性快照异常回退裸拷贝（442-444）
- _restore_database_from_backup 残留 WAL 清理 OSError（473-476）+ 完整性校验未通过（500-501）
- verify_backup 加密备份直接返回 error（1011）
- get_disk_space_info._one 磁盘探测异常兜底（1115-1117）
"""
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.backup_service import (
    BackupIncompleteError,
    BackupRestoreError,
    BackupService,
)


def _make_svc(mock_db, backup_dir, db_path, uploads_dir, incremental="true", level="6"):
    with patch("os.makedirs"), \
         patch("app.utils.paths.get_database_path", return_value=Path(db_path)), \
         patch("app.utils.paths.get_uploads_path", return_value=Path(uploads_dir)), \
         patch("os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda k, d=None: {
            "INCREMENTAL_BACKUP_ENABLED": incremental,
            "BACKUP_COMPRESSION_LEVEL": level,
        }.get(k, d)
        return BackupService(db=mock_db, backup_dir=backup_dir)


def _valid_sqlite_bytes():
    """构造一个真实、完整的 SQLite 库字节串（供 integrity_check=ok）。"""
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(p)
    try:
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.commit()
    finally:
        conn.close()
    data = Path(p).read_bytes()
    os.remove(p)
    return data


class TestEnsureDiskSpace:
    def test_insufficient_raises(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"),
                        str(tmp_path / "d.db"), str(tmp_path / "u"))
        with patch("app.core.database.check_disk_space",
                   return_value={"sufficient": False, "free_mb": 10}):
            with pytest.raises(BackupRestoreError):
                svc._ensure_disk_space()


class TestCreateConsistencySnapshot:
    def test_backup_fail_remove_oserror(self, mock_db, tmp_path):
        db_path = str(tmp_path / "real.db")
        Path(db_path).write_bytes(b"x")
        svc = _make_svc(mock_db, str(tmp_path / "b"), db_path, str(tmp_path / "u"))
        real_remove = os.remove
        attempted = []

        def sel_remove(p, *a, **k):
            if "backup_snapshot_" in str(p):
                attempted.append(str(p))
                raise OSError("denied")
            return real_remove(p, *a, **k)

        src = MagicMock()
        src.backup.side_effect = RuntimeError("boom")
        with patch("app.services.backup_service.sqlite3.connect", return_value=src), \
             patch("os.remove", side_effect=sel_remove):
            result = svc._create_consistency_snapshot()
        assert result is None
        # 清理因 OSError 未删除的快照临时文件，避免残留
        for p in attempted:
            try:
                real_remove(p)
            except OSError:
                pass


class TestWriteBackupZip:
    def test_exception_removes_half_written(self, mock_db, tmp_path):
        bdir = str(tmp_path / "b")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, str(tmp_path / "d.db"), str(tmp_path / "u"))
        backup_file = os.path.join(bdir, "bad.zip")
        with patch("app.services.backup_service.zipfile.ZipFile",
                   side_effect=RuntimeError("disk full")):
            with pytest.raises(RuntimeError):
                svc._write_backup_zip(backup_file, None, "ts", "d", False)
        assert not os.path.exists(backup_file)

    def test_finally_snapshot_remove_oserror(self, mock_db, tmp_path):
        bdir = str(tmp_path / "b")
        os.makedirs(bdir)
        # database_path 不存在 → 跳过写 db；include_uploads=False → 跳过 uploads
        svc = _make_svc(mock_db, bdir, str(tmp_path / "nonexist.db"), str(tmp_path / "u"))
        snap = str(tmp_path / "backup_snapshot_x.db")
        Path(snap).write_bytes(b"s")
        real_remove = os.remove

        def sel_remove(p, *a, **k):
            if str(p) == snap:
                raise OSError("denied")
            return real_remove(p, *a, **k)

        backup_file = os.path.join(bdir, "b.zip")
        try:
            with patch("os.remove", side_effect=sel_remove):
                svc._write_backup_zip(backup_file, snap, "ts", "desc", False)
            assert os.path.exists(backup_file)  # zip 主体写成功
        finally:
            try:
                real_remove(snap)
            except OSError:
                pass


class TestCreateBackupIntegrity:
    def test_corrupt_zip_integrity_and_remove_oserror(self, mock_db, tmp_path):
        bdir = str(tmp_path / "b")
        os.makedirs(bdir)
        svc = _make_svc(mock_db, bdir, str(tmp_path / "d.db"), str(tmp_path / "u"))

        def fake_write(backup_file_path, *a, **k):
            Path(backup_file_path).write_bytes(b"not a zip")

        def deny_remove(p, *a, **k):
            raise OSError("denied")

        with patch.object(svc, "_ensure_disk_space"), \
             patch.object(svc, "_create_consistency_snapshot", return_value=None), \
             patch.object(svc, "_write_backup_zip", side_effect=fake_write), \
             patch("os.remove", side_effect=deny_remove):
            with pytest.raises(BackupIncompleteError):
                svc.create_backup()
        # 清理损坏半成品
        for f in os.listdir(bdir):
            try:
                os.remove(os.path.join(bdir, f))
            except OSError:
                pass


class TestCreateSnapshots:
    def test_consistency_exception_fallback_copy(self, mock_db, tmp_path):
        db_path = str(tmp_path / "real.db")
        Path(db_path).write_bytes(b"dbdata")
        svc = _make_svc(mock_db, str(tmp_path / "b"), db_path, str(tmp_path / "u"))
        with patch.object(svc, "_create_consistency_snapshot",
                          side_effect=RuntimeError("boom")):
            snap_db, snap_up = svc._create_snapshots()
        # 核心：一致性快照异常时回退为裸拷贝（.snapshot_ 后缀）
        try:
            assert snap_db and ".snapshot_" in snap_db
            assert os.path.exists(snap_db)
        finally:
            if snap_db and os.path.exists(snap_db):
                os.remove(snap_db)
            if snap_up and os.path.exists(snap_up):
                import shutil as _sh
                _sh.rmtree(snap_up, ignore_errors=True)


class TestRestoreDatabase:
    def test_stale_wal_unlink_oserror(self, mock_db, tmp_path):
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_bytes(b"orig")
        temp_dir = str(tmp_path / "extract")
        os.makedirs(os.path.join(temp_dir, "data"))
        Path(os.path.join(temp_dir, "data", "rural_revitalization.db")).write_bytes(
            _valid_sqlite_bytes()
        )
        wal = db_path + "-wal"
        Path(wal).write_text("stale")
        svc = _make_svc(mock_db, str(tmp_path / "b"), db_path, str(tmp_path / "u"))
        real_unlink = os.unlink

        def sel_unlink(p, *a, **k):
            if str(p).endswith("-wal"):
                raise OSError("locked")
            return real_unlink(p, *a, **k)

        mock_dbmod = MagicMock()
        mock_dbmod.engine = MagicMock()
        mock_dbmod.db_coordinator = None
        try:
            with patch.dict("sys.modules", {"app.core.database": mock_dbmod}), \
                 patch("os.unlink", side_effect=sel_unlink):
                result = svc._restore_database_from_backup(temp_dir)
            assert result is True
        finally:
            if os.path.exists(wal):
                try:
                    real_unlink(wal)
                except OSError:
                    pass

    def test_integrity_check_fail_returns_false(self, mock_db, tmp_path):
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_bytes(b"orig")
        temp_dir = str(tmp_path / "extract")
        os.makedirs(os.path.join(temp_dir, "data"))
        Path(os.path.join(temp_dir, "data", "rural_revitalization.db")).write_bytes(
            _valid_sqlite_bytes()
        )
        svc = _make_svc(mock_db, str(tmp_path / "b"), db_path, str(tmp_path / "u"))
        mock_dbmod = MagicMock()
        mock_dbmod.engine = MagicMock()
        mock_dbmod.db_coordinator = None
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ("corrupt",)
        with patch.dict("sys.modules", {"app.core.database": mock_dbmod}), \
             patch("app.services.backup_service.sqlite3.connect",
                   return_value=mock_conn):
            result = svc._restore_database_from_backup(temp_dir)
        assert result is False


class TestVerifyEncrypted:
    def test_verify_backup_encrypted_returns_error(self, mock_db, tmp_path):
        zp = str(tmp_path / "enc.zip")
        Path(zp).write_bytes(b"data")
        BackupService._encrypt_file(zp, "p")
        svc = _make_svc(mock_db, str(tmp_path / "b"),
                        str(tmp_path / "d.db"), str(tmp_path / "u"))
        result = svc.verify_backup(zp)
        assert result["status"] == "error"
        assert result["encrypted"] is True


class TestDiskSpaceInfo:
    def test_probe_exception_fallback(self, mock_db, tmp_path):
        svc = _make_svc(mock_db, str(tmp_path / "b"),
                        str(tmp_path / "d.db"), str(tmp_path / "u"))
        with patch("app.core.database.check_disk_space",
                   side_effect=RuntimeError("boom")):
            info = svc.get_disk_space_info()
        assert info["backup_dir"]["sufficient"] is True
        assert info["backup_dir"]["free_mb"] == -1
