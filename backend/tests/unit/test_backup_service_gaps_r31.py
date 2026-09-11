"""backup_service 两条"难以自然构造"路径的覆盖率补口（.coveragerc fail_under=100）。

一、C1 恢复性校验（f873fcee 新增 `_verify_backup_recovery`：zip CRC +
`PRAGMA integrity_check`，失败即 fail-loud——"备份成功但不可还原"是最坏故障）
只被测到"库文件非 SQLite"与"正常库"两条路径，以下两处未覆盖：
  · 370：库可读但 integrity_check 返回非 "ok"（页面级不一致）
  · 374-375：校验临时文件清理时 os.remove 抛 OSError（只告警，不得改变结论）

二、快照回退分支：
  · 287：一致性快照不可用（`_create_consistency_snapshot` 返回 None）时
    回退直接打包主库文件。夹具改为真实 SQLite 后快照恒成功，该行失去覆盖。

两处均为真实存在但常规路径难以自然构造的分支，故用最小假体直击。
"""

import os
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import backup_service
from app.services.backup_service import BackupIncompleteError, BackupService


def _make_db(path: str) -> None:
    """建一个可通过 integrity_check 的真实 SQLite 库。"""
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS _t (x TEXT)")
        conn.execute("INSERT INTO _t (x) VALUES ('seed')")
        conn.commit()
    finally:
        conn.close()


def _make_svc(backup_dir: str) -> BackupService:
    with patch("os.getenv", side_effect=lambda k, d=None: d):
        return BackupService(db=MagicMock(), backup_dir=backup_dir)


def _make_bound_svc(mock_db, backup_dir: str, db_path: str, uploads_dir: str) -> BackupService:
    """与 test_backup_service.py::_make_svc 同构：把库/上传目录绑到 tmp_path。"""
    with patch("os.makedirs"), \
         patch("app.utils.paths.get_database_path", return_value=Path(db_path)), \
         patch("app.utils.paths.get_uploads_path", return_value=Path(uploads_dir)), \
         patch("app.utils.paths.get_runtime_uploads_path", return_value=Path(uploads_dir)), \
         patch("os.getenv") as mock_getenv:
        mock_getenv.side_effect = lambda k, d=None: {
            "INCREMENTAL_BACKUP_ENABLED": "true",
            "BACKUP_COMPRESSION_LEVEL": "6",
        }.get(k, d)
        return BackupService(db=mock_db, backup_dir=backup_dir)


def _make_backup_zip(tmp_path, db_bytes: bytes) -> str:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    zip_path = str(backup_dir / "verify.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/rural_revitalization.db", db_bytes)
    return zip_path


class _FakeConn:
    """只实现 _verify_backup_recovery 用到的 execute/fetchone/close。"""

    def __init__(self, result: str) -> None:
        self.result = result
        self.sql: str | None = None
        self.closed = False

    def execute(self, sql: str) -> "_FakeConn":
        self.sql = sql
        return self

    def fetchone(self):
        return (self.result,)

    def close(self) -> None:
        self.closed = True


class TestVerifyRecoveryGaps:
    def test_integrity_check_not_ok_raises(self, tmp_path):
        """370 行：库可读但 integrity_check 返回非 "ok" → fail-loud。"""
        db_path = str(tmp_path / "src.db")
        _make_db(db_path)
        zip_path = _make_backup_zip(tmp_path, Path(db_path).read_bytes())
        svc = _make_svc(str(tmp_path / "backups"))

        broken = _FakeConn("row 5 missing from index idx_t")
        with patch.object(backup_service.sqlite3, "connect", return_value=broken):
            with pytest.raises(BackupIncompleteError) as exc:
                svc._verify_backup_recovery(zip_path)

        assert "row 5 missing from index idx_t" in str(exc.value)
        assert broken.sql == "PRAGMA integrity_check"
        assert broken.closed is True  # 异常路径同样关闭连接，不泄漏句柄

    def test_verify_temp_cleanup_oserror_is_swallowed(self, tmp_path):
        """374-375 行：临时校验文件删除失败（被占用）不得影响校验结论。"""
        db_path = str(tmp_path / "src.db")
        _make_db(db_path)
        zip_path = _make_backup_zip(tmp_path, Path(db_path).read_bytes())
        svc = _make_svc(str(tmp_path / "backups"))

        real_remove = os.remove

        def flaky_remove(path, *args, **kwargs):
            if "backup_verify_" in str(path):
                raise OSError("file is in use by another process")
            return real_remove(path, *args, **kwargs)

        with patch.object(backup_service.os, "remove", side_effect=flaky_remove):
            svc._verify_backup_recovery(zip_path)  # 不得抛出


class TestSnapshotFallback:
    def test_snapshot_unavailable_falls_back_to_main_db(self, mock_db, tmp_path):
        """287 行：一致性快照不可用时回退直接打包主库文件（仍可还原）。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        _make_db(db_path)
        os.makedirs(up_dir)

        svc = _make_bound_svc(mock_db, bdir, db_path, up_dir)
        with patch.object(svc, "_create_consistency_snapshot", return_value=None):
            result = svc.create_backup(include_uploads=False)

        assert result is not None
        with zipfile.ZipFile(os.path.join(bdir, result.file_name)) as zf:
            assert "data/rural_revitalization.db" in zf.namelist()
            # 回退写的是主库本体：SQLite 文件头在场，恢复性校验可读回
            assert zf.read("data/rural_revitalization.db")[:16] == b"SQLite format 3\x00"
