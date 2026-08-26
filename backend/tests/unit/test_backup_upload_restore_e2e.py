"""备份上传恢复 E2E：创建（含加密）→ 上传恢复 → 数据校验。

覆盖真实 BackupService 解密/恢复链路，不 mock 恢复逻辑。
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user


def _admin():
    return SimpleNamespace(id=1, role="admin", username="root", is_superuser=False)


def _make_backup(tmp_path, password=None):
    """在 tmp_path 下构造真实的系统备份包（含数据库文件与上传文件）。"""
    from pathlib import Path

    from app.services.backup_service import BackupService

    db_path = os.path.join(str(tmp_path), "live", "data", "rural_revitalization.db")
    up_dir = os.path.join(str(tmp_path), "live", "uploads")
    os.makedirs(os.path.dirname(db_path))
    os.makedirs(up_dir)
    # T046：恢复后做 SQLite 完整性自检，必须写入真实 SQLite 库文件
    import sqlite3 as _sqlite3

    _conn = _sqlite3.connect(db_path)
    try:
        _conn.execute("CREATE TABLE IF NOT EXISTS _marker (v TEXT)")
        _conn.execute("INSERT INTO _marker (v) VALUES (?)", ("DB-v2",))
        _conn.commit()
    finally:
        _conn.close()
    with open(os.path.join(up_dir, "doc.txt"), "w", encoding="utf-8") as f:
        f.write("file-v2")

    with patch("app.utils.paths.get_database_path", return_value=Path(db_path)), \
         patch("app.utils.paths.get_uploads_path", return_value=Path(up_dir)):
        svc = BackupService(MagicMock(), backup_dir=str(tmp_path))
    rec = svc.create_backup(description="e2e", password=password)
    return svc, rec.file_path, db_path, up_dir


@pytest.fixture
def client(tmp_path):
    from pathlib import Path

    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = _admin
    app.dependency_overrides[get_db] = lambda: MagicMock()
    live_dir = Path(str(tmp_path)) / "live"
    with patch("app.utils.paths.get_backup_path", return_value=os.path.join(str(tmp_path), "uploads")), \
         patch("app.utils.paths.get_database_path", return_value=live_dir / "data" / "rural_revitalization.db"), \
         patch("app.utils.paths.get_uploads_path", return_value=live_dir / "uploads"):
        yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


class TestUploadRestoreE2E:
    def test_restore_plain_backup(self, client, tmp_path):
        svc, backup_path, db_path, up_dir = _make_backup(tmp_path)
        with open(backup_path, "rb") as f:
            content = f.read()
        resp = client.post(
            "/api/v1/system/backup/upload-restore",
            files={"file": ("backup.zip", content, "application/zip")},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["database_restored"] is True
        _chk = __import__("sqlite3").connect(db_path)
        try:
            _row = _chk.execute("SELECT v FROM _marker").fetchone()
            assert _row[0] == "DB-v2"
        finally:
            _chk.close()

    def test_restore_encrypted_backup_with_password(self, client, tmp_path):
        svc, backup_path, db_path, up_dir = _make_backup(tmp_path, password="s3cret!Pass")
        with open(backup_path, "rb") as f:
            content = f.read()
        resp = client.post(
            "/api/v1/system/backup/upload-restore",
            files={"file": ("enc.zip", content, "application/zip")},
            data={"password": "s3cret!Pass"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["database_restored"] is True
        _chk = __import__("sqlite3").connect(db_path)
        try:
            _row = _chk.execute("SELECT v FROM _marker").fetchone()
            assert _row[0] == "DB-v2"
        finally:
            _chk.close()
        assert os.path.exists(os.path.join(up_dir, "doc.txt"))

    def test_restore_encrypted_wrong_password_400(self, client, tmp_path):
        svc, backup_path, db_path, up_dir = _make_backup(tmp_path, password="s3cret!Pass")
        with open(backup_path, "rb") as f:
            content = f.read()
        resp = client.post(
            "/api/v1/system/backup/upload-restore",
            files={"file": ("enc.zip", content, "application/zip")},
            data={"password": "wrong-password"},
        )
        assert resp.status_code == 400
        assert "密码" in resp.json()["detail"]
        # 原数据未被破坏
        _chk = __import__("sqlite3").connect(db_path)
        try:
            _row = _chk.execute("SELECT v FROM _marker").fetchone()
            assert _row[0] == "DB-v2"
        finally:
            _chk.close()

    def test_restore_backup_restore_error_400(self, client, tmp_path):
        """恢复过程中 BackupRestoreError（如加密包内 ZIP 损坏）→ 400 并清理临时文件"""
        import io

        import zipfile as zf_mod

        from app.services.backup_service import BackupRestoreError

        buf = io.BytesIO()
        with zf_mod.ZipFile(buf, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "db")
        svc_mock = MagicMock()
        svc_mock.restore_backup.side_effect = BackupRestoreError("备份内容损坏")
        with patch("app.api.v1.system.backup.get_backup_service", return_value=svc_mock):
            resp = client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
            )
        assert resp.status_code == 400
        assert "备份" in resp.json()["detail"]
        assert list((tmp_path / "uploads").glob("upload_*")) == []
