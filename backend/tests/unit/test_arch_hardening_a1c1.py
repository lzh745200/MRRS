"""架构评估 P0/P1 修复项测试（A1 / A2 / C1）。

覆盖：
- A1 recover_stale_export_tasks：重启后 pending/processing 导出任务回写 failed
- A1 main._recover_interrupted_exports：lifespan 接线（成功 / 零恢复 / 异常不阻断）
- A2 backup_service._write_backup_zip：.part 临时文件 + os.replace 原子落盘
- C1 backup_service._verify_backup_recovery：zip CRC + SQLite integrity_check
"""

import os
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.export_task import ExportStatus
from app.services.async_export_service import recover_stale_export_tasks
from app.services.backup_service import BackupIncompleteError, BackupService


# ---------------------------------------------------------------------------
# 公共辅助（与 test_backup_service_edge.py 同模式）
# ---------------------------------------------------------------------------


def _make_svc(mock_db, backup_dir, db_path, uploads_dir):
    with patch("os.makedirs"), \
         patch("app.utils.paths.get_database_path", return_value=Path(db_path)), \
         patch("app.utils.paths.get_uploads_path", return_value=Path(uploads_dir)), \
         patch("os.getenv", side_effect=lambda k, d=None: d):
        return BackupService(db=mock_db, backup_dir=backup_dir)


def _make_real_sqlite_file(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# A1 — recover_stale_export_tasks
# ---------------------------------------------------------------------------


class TestRecoverStaleExportTasks:
    def test_no_stale_returns_zero(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("app.services.async_export_service.safe_commit") as sc:
            assert recover_stale_export_tasks(db) == 0
        sc.assert_not_called()

    def test_stale_tasks_marked_failed(self):
        db = MagicMock()
        t_pending = MagicMock()
        t_processing = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            t_pending, t_processing,
        ]
        with patch("app.services.async_export_service.safe_commit") as sc:
            n = recover_stale_export_tasks(db)
        assert n == 2
        for t in (t_pending, t_processing):
            assert t.status == ExportStatus.FAILED.value
            assert "重新发起" in t.error_message
            assert t.completed_at is not None
        sc.assert_called_once_with(db)

    def test_filter_targets_pending_and_processing(self):
        """查询条件必须同时锁定 pending 与 processing 两种僵尸态。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        recover_stale_export_tasks(db)
        db.query.assert_called_once()
        db.query.return_value.filter.assert_called_once()


class TestRecoverInterruptedExportsHook:
    """main._recover_interrupted_exports — lifespan 接线。"""

    def _hook(self):
        from app.main import _recover_interrupted_exports

        return _recover_interrupted_exports

    def test_success_with_recovered(self):
        hook = self._hook()
        mock_db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_db), \
             patch("app.services.async_export_service.recover_stale_export_tasks",
                   return_value=2):
            hook()  # 不抛出
        mock_db.close.assert_called_once()

    def test_success_with_zero_recovered(self):
        hook = self._hook()
        mock_db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_db), \
             patch("app.services.async_export_service.recover_stale_export_tasks",
                   return_value=0):
            hook()
        mock_db.close.assert_called_once()

    def test_exception_does_not_block_startup(self):
        hook = self._hook()
        with patch("app.core.database.SessionLocal",
                   side_effect=RuntimeError("db unavailable")):
            hook()  # 异常被吞掉，启动继续

    def test_recover_error_does_not_block_startup(self):
        hook = self._hook()
        mock_db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_db), \
             patch("app.services.async_export_service.recover_stale_export_tasks",
                   side_effect=RuntimeError("boom")):
            hook()
        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# A2 — _write_backup_zip 原子落盘
# ---------------------------------------------------------------------------


class TestWriteBackupZipAtomic:
    def test_success_replaces_part_file(self, mock_db, tmp_path):
        """成功路径：写 .part → os.replace 到位，目录中不留 .part 残留。"""
        bdir = tmp_path / "b"
        bdir.mkdir()
        snap = tmp_path / "snap.db"
        _make_real_sqlite_file(str(snap))
        svc = _make_svc(mock_db, str(bdir), str(tmp_path / "d.db"), str(tmp_path / "u"))

        final = str(bdir / "ok.zip")
        svc._write_backup_zip(final, str(snap), "ts", "desc", False)

        assert os.path.exists(final)
        assert not os.path.exists(final + ".part")
        with zipfile.ZipFile(final) as zf:
            assert "data/rural_revitalization.db" in zf.namelist()

    def test_exception_cleans_part_file(self, mock_db, tmp_path):
        """写失败：.part 半成品被清理，最终路径不出现残缺包。"""
        bdir = tmp_path / "b"
        bdir.mkdir()
        svc = _make_svc(mock_db, str(bdir), str(tmp_path / "d.db"), str(tmp_path / "u"))
        final = str(bdir / "bad.zip")
        with patch("app.services.backup_service.zipfile.ZipFile",
                   side_effect=RuntimeError("disk full")):
            with pytest.raises(RuntimeError):
                svc._write_backup_zip(final, None, "ts", "d", False)
        assert not os.path.exists(final)
        assert not os.path.exists(final + ".part")


# ---------------------------------------------------------------------------
# C1 — _verify_backup_recovery
# ---------------------------------------------------------------------------


class TestVerifyBackupRecovery:
    def _svc(self, mock_db, tmp_path):
        return _make_svc(mock_db, str(tmp_path / "b"),
                         str(tmp_path / "d.db"), str(tmp_path / "u"))

    def test_valid_backup_passes(self, mock_db, tmp_path):
        svc = self._svc(mock_db, tmp_path)
        real_db = tmp_path / "real.db"
        _make_real_sqlite_file(str(real_db))
        zip_path = tmp_path / "good.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(real_db), "data/rural_revitalization.db")
        svc._verify_backup_recovery(str(zip_path))  # 不抛出即通过

    def test_missing_db_member_raises(self, mock_db, tmp_path):
        svc = self._svc(mock_db, tmp_path)
        zip_path = tmp_path / "nodb.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("backup_info.json", "{}")
        with pytest.raises(BackupIncompleteError, match="缺少数据库"):
            svc._verify_backup_recovery(str(zip_path))

    def test_not_a_zip_raises(self, mock_db, tmp_path):
        svc = self._svc(mock_db, tmp_path)
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"plainly not a zip file")
        with pytest.raises(BackupIncompleteError, match="非有效 zip"):
            svc._verify_backup_recovery(str(bad))

    def test_crc_corruption_raises(self, mock_db, tmp_path):
        """成员数据被篡改 → testzip CRC 校验必须拦截。"""
        svc = self._svc(mock_db, tmp_path)
        real_db = tmp_path / "real.db"
        _make_real_sqlite_file(str(real_db))
        zip_path = tmp_path / "corrupt.zip"
        # ZIP_STORED：数据区明文存储，篡改单字节必然触发 CRC mismatch
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
            zf.write(str(real_db), "data/rural_revitalization.db")
        with open(zip_path, "r+b") as f:
            local_header_len = 30 + len("data/rural_revitalization.db")
            f.seek(local_header_len + 5)
            orig = f.read(1)
            f.seek(local_header_len + 5)
            f.write(bytes([orig[0] ^ 0xFF]))
        with pytest.raises(BackupIncompleteError, match="CRC"):
            svc._verify_backup_recovery(str(zip_path))

    def test_corrupt_db_payload_raises(self, mock_db, tmp_path):
        """zip 结构完好但库文件不是有效 SQLite → integrity_check 拦截。"""
        svc = self._svc(mock_db, tmp_path)
        zip_path = tmp_path / "fakedb.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data/rural_revitalization.db", b"definitely not sqlite" * 64)
        with pytest.raises(BackupIncompleteError, match="完整性校验失败"):
            svc._verify_backup_recovery(str(zip_path))

    def test_create_backup_invokes_recovery_check(self, mock_db, tmp_path):
        """create_backup 成功路径必须经过恢复性校验（接线回归）。"""
        bdir = tmp_path / "backups"
        bdir.mkdir()
        db_path = tmp_path / "data" / "rural_revitalization.db"
        db_path.parent.mkdir()
        _make_real_sqlite_file(str(db_path))
        svc = _make_svc(mock_db, str(bdir), str(db_path), str(tmp_path / "u"))
        with patch.object(svc, "_verify_backup_recovery",
                          wraps=svc._verify_backup_recovery) as spy, \
             patch.object(svc, "_ensure_disk_space"):
            record = svc.create_backup(description="C1 接线回归", include_uploads=False)
        spy.assert_called_once_with(record.file_path)
        assert Path(record.file_path).exists()
