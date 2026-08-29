"""补充测试 — 目标 100% 覆盖 app/services/backup_service.py。

现有 test_backup_service.py 已覆盖大部分路径。本文件补充未覆盖部分：
- _derive_key / _encrypt_file / _is_encrypted / _decrypt_to_temp / _decrypt_file
  （AES-256 加密/解密工具方法）
- create_backup(password=...) → 加密分支
- _safe_extractall 的 ValueError 分支（target.relative_to 抛异常）
- restore_backup 加密备份检测 + 解密恢复 + engine.dispose 异常 + 临时文件清理 OSError
"""
import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.services.backup_service import (
    BackupService,
)


# ---------------------------------------------------------------------------
# 辅助：构建 BackupService 实例（与现有 test_backup_service.py 相同的模式）
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 加密工具方法
# ---------------------------------------------------------------------------


class TestDeriveKey:
    def test_returns_valid_fernet_key(self):
        """_derive_key 返回的 key 应能构造 Fernet。"""
        salt = b"0123456789abcdef"  # 16 bytes
        key = BackupService._derive_key("my_password", salt)
        assert isinstance(key, bytes)
        # 不抛异常即说明 key 格式正确
        Fernet(key)

    def test_different_passwords_produce_different_keys(self):
        salt = b"0123456789abcdef"
        key1 = BackupService._derive_key("pass1", salt)
        key2 = BackupService._derive_key("pass2", salt)
        assert key1 != key2

    def test_same_inputs_produce_same_key(self):
        salt = b"0123456789abcdef"
        key1 = BackupService._derive_key("pass", salt)
        key2 = BackupService._derive_key("pass", salt)
        assert key1 == key2


class TestEncryptFile:
    def test_encrypt_adds_marker(self, tmp_path):
        """加密后文件头部应包含加密标记。"""
        file_path = str(tmp_path / "plain.zip")
        Path(file_path).write_bytes(b"plaintext backup data")
        BackupService._encrypt_file(file_path, "secret")
        assert BackupService._is_encrypted(file_path)

    def test_encrypted_content_differs_from_original(self, tmp_path):
        file_path = str(tmp_path / "data.zip")
        original = b"plaintext backup data"
        Path(file_path).write_bytes(original)
        BackupService._encrypt_file(file_path, "secret")
        encrypted = Path(file_path).read_bytes()
        assert encrypted != original
        # 加密标记 + salt + 密文
        assert encrypted.startswith(BackupService._ENCRYPTED_MARKER)


class TestIsEncrypted:
    def test_encrypted_file_returns_true(self, tmp_path):
        file_path = str(tmp_path / "enc.zip")
        Path(file_path).write_bytes(b"plaintext")
        BackupService._encrypt_file(file_path, "pass")
        assert BackupService._is_encrypted(file_path) is True

    def test_plain_file_returns_false(self, tmp_path):
        file_path = str(tmp_path / "plain.zip")
        Path(file_path).write_bytes(b"plaintext backup data")
        assert BackupService._is_encrypted(file_path) is False


class TestDecryptToTemp:
    def test_correct_password_decrypts(self, tmp_path):
        """正确密码解密后内容与原始一致。"""
        file_path = str(tmp_path / "enc.zip")
        original = b"secret backup content"
        Path(file_path).write_bytes(original)
        BackupService._encrypt_file(file_path, "mypassword")

        temp_path = BackupService._decrypt_to_temp(file_path, "mypassword")
        assert temp_path != file_path  # 解密到临时文件，不覆盖原文件
        assert Path(temp_path).read_bytes() == original
        # 原文件仍为加密状态
        assert BackupService._is_encrypted(file_path)
        os.unlink(temp_path)

    def test_wrong_password_raises_value_error(self, tmp_path):
        file_path = str(tmp_path / "enc.zip")
        Path(file_path).write_bytes(b"secret data")
        BackupService._encrypt_file(file_path, "correct_pass")

        with pytest.raises(ValueError, match="密码错误或备份文件已损坏"):
            BackupService._decrypt_to_temp(file_path, "wrong_pass")

    def test_non_encrypted_file_raises_value_error(self, tmp_path):
        file_path = str(tmp_path / "plain.zip")
        Path(file_path).write_bytes(b"plain data")

        with pytest.raises(ValueError, match="文件不是加密格式"):
            BackupService._decrypt_to_temp(file_path, "any_password")


class TestDecryptFile:
    def test_decrypt_inplace(self, tmp_path):
        """_decrypt_file 原地替换为明文（已弃用但保留向后兼容）。"""
        file_path = str(tmp_path / "enc.zip")
        original = b"backup data for inplace decrypt"
        Path(file_path).write_bytes(original)
        BackupService._encrypt_file(file_path, "pass")

        BackupService._decrypt_file(file_path, "pass")
        # 原地替换：文件内容恢复为明文
        assert Path(file_path).read_bytes() == original
        assert not BackupService._is_encrypted(file_path)


# ---------------------------------------------------------------------------
# create_backup(password=...) — 加密分支
# ---------------------------------------------------------------------------


class TestCreateBackupWithPassword:
    def test_backup_encrypted_with_password(self, mock_db, tmp_path):
        """create_backup(password=...) 后备份文件应为加密格式。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db content")
        os.makedirs(up_dir)
        Path(os.path.join(up_dir, "f.txt")).write_text("upload")

        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.create_backup(description="加密备份", password="s3cret")

        assert result is not None
        assert result.file_size > 0
        # 备份文件已加密
        assert BackupService._is_encrypted(result.file_path)

    def test_backup_without_password_not_encrypted(self, mock_db, tmp_path):
        """无密码时备份文件不加密。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("db")

        svc = _make_svc(mock_db, bdir, db_path, str(tmp_path / "u"))
        result = svc.create_backup(description="明文备份")
        assert not BackupService._is_encrypted(result.file_path)


# ---------------------------------------------------------------------------
# _safe_extractall ValueError 分支
# ---------------------------------------------------------------------------


class TestSafeExtractallValueError:
    def test_value_error_skips_member(self, mock_db, tmp_path):
        """target.relative_to(dest_path) 抛 ValueError 时跳过该成员。

        通过 mock Path.relative_to 模拟路径逃逸（正常情况下前面的 ".." 检查
        会拦截大多数攻击，此分支是深度防御）。
        """
        svc = _make_svc(mock_db, "/b", "/d/db", "/u")
        dest = str(tmp_path / "extract")
        os.makedirs(dest)
        zip_path = str(tmp_path / "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("safe.txt", "ok")
        with zipfile.ZipFile(zip_path, "r") as zf:
            # mock relative_to 抛 ValueError 模拟路径逃逸
            with patch.object(Path, "relative_to", side_effect=ValueError("outside")):
                svc._safe_extractall(zf, dest)
        # 成员被跳过，文件不存在
        assert not os.path.exists(os.path.join(dest, "safe.txt"))


# ---------------------------------------------------------------------------
# restore_backup — 加密备份恢复
# ---------------------------------------------------------------------------


class TestRestoreEncryptedBackup:
    def _make_zip(self, zip_path, db_content="new_db", upload_content="new_upload"):
        """创建包含数据库和上传文件的 zip。"""
        import sqlite3 as _sqlite3
        import tempfile as _tempfile

        # T046 恢复后做 SQLite 完整性自检，必须写入真实 SQLite 库文件
        _fd, _db_file = _tempfile.mkstemp(suffix=".db")
        os.close(_fd)
        _conn = _sqlite3.connect(_db_file)
        try:
            _conn.execute("CREATE TABLE IF NOT EXISTS _marker (v TEXT)")
            _conn.execute("INSERT INTO _marker (v) VALUES (?)", (db_content,))
            _conn.commit()
        finally:
            _conn.close()
        with open(_db_file, "rb") as _f:
            _db_bytes = _f.read()
        os.remove(_db_file)

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", _db_bytes)
            zf.writestr("uploads/f.txt", upload_content)

    def test_restore_encrypted_backup(self, mock_db, tmp_path):
        """加密备份 + 正确密码 → 成功恢复。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig_db")
        os.makedirs(up_dir)

        zip_path = os.path.join(bdir, "backup.zip")
        self._make_zip(zip_path)
        BackupService._encrypt_file(zip_path, "restore_pass")

        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        result = svc.restore_backup(zip_path, password="restore_pass")

        assert result["success"] is True
        assert result["database_restored"] is True
        assert result["uploads_restored"] is True
        # T046：恢复后做完整性自检，必须恢复为真实 SQLite 库
        _chk = __import__("sqlite3").connect(db_path)
        try:
            _row = _chk.execute("SELECT v FROM _marker").fetchone()
            assert _row[0] == "new_db"
        finally:
            _chk.close()

    def test_restore_encrypted_no_password_raises(self, mock_db, tmp_path):
        """加密备份但未提供密码 → ValueError。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")

        zip_path = os.path.join(bdir, "enc.zip")
        self._make_zip(zip_path)
        BackupService._encrypt_file(zip_path, "pass")

        svc = _make_svc(mock_db, bdir, db_path, str(tmp_path / "u"))
        with pytest.raises(ValueError, match="备份文件已加密，请提供密码"):
            svc.restore_backup(zip_path)

    def test_restore_non_encrypted_with_password_warns(self, mock_db, tmp_path):
        """非加密备份 + 提供密码 → 记录警告，密码被忽略，正常恢复。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")

        zip_path = os.path.join(bdir, "plain.zip")
        self._make_zip(zip_path)

        svc = _make_svc(mock_db, bdir, db_path, str(tmp_path / "u"))
        # 不应抛异常（密码被忽略）
        result = svc.restore_backup(zip_path, password="unnecessary")
        assert result["success"] is True
        assert result["database_restored"] is True


# ---------------------------------------------------------------------------
# restore_backup — engine.dispose 异常分支
# ---------------------------------------------------------------------------


class TestRestoreEngineDisposeFailure:
    def test_engine_dispose_exception_logged(self, mock_db, tmp_path):
        """engine.dispose() 抛异常时记录警告但不影响恢复。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")

        zip_path = os.path.join(bdir, "b.zip")
        import sqlite3 as _sqlite3
        import tempfile as _tempfile

        _fd, _db_file = _tempfile.mkstemp(suffix=".db")
        os.close(_fd)
        _conn = _sqlite3.connect(_db_file)
        try:
            _conn.execute("CREATE TABLE IF NOT EXISTS _marker (v TEXT)")
            _conn.execute("INSERT INTO _marker (v) VALUES (?)", ("new",))
            _conn.commit()
        finally:
            _conn.close()
        with open(_db_file, "rb") as _f:
            _db_bytes = _f.read()
        os.remove(_db_file)
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", _db_bytes)

        svc = _make_svc(mock_db, bdir, db_path, str(tmp_path / "u"))

        # mock engine.dispose 抛异常
        mock_engine = MagicMock()
        mock_engine.dispose.side_effect = RuntimeError("pool closed")
        with patch.dict("sys.modules", {"app.core.database": MagicMock(engine=mock_engine)}):
            result = svc.restore_backup(zip_path)

        assert result["success"] is True
        assert result["database_restored"] is True
        # 2026-08-29 恢复写协调改造后 dispose 两次:
        # 1) copy 前释放旧句柄; 2) copy 后清理恢复窗口期间新建的池连接
        assert mock_engine.dispose.call_count == 2


# ---------------------------------------------------------------------------
# restore_backup — 解密临时文件清理 OSError
# ---------------------------------------------------------------------------


class TestRestoreDecryptedTempCleanup:
    def test_decrypted_temp_unlink_oserror_ignored(self, mock_db, tmp_path):
        """finally 中清理解密临时文件时 OSError 被忽略。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        os.makedirs(bdir)
        os.makedirs(os.path.dirname(db_path))
        Path(db_path).write_text("orig")

        zip_path = os.path.join(bdir, "enc.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", "new")
        BackupService._encrypt_file(zip_path, "pass")

        svc = _make_svc(mock_db, bdir, db_path, str(tmp_path / "u"))

        # mock os.unlink 对 decrypted temp 路径抛 OSError
        orig_unlink = os.unlink
        call_paths = []

        def selective_unlink(p, *a, **kw):
            call_paths.append(str(p))
            # 对 decrypted_backup_ 临时文件抛 OSError
            if "decrypted_backup_" in str(p):
                raise OSError("permission denied")
            return orig_unlink(p, *a, **kw)

        with patch("os.unlink", side_effect=selective_unlink):
            result = svc.restore_backup(zip_path, password="pass")

        assert result["success"] is True
        # 验证确实尝试了清理 decrypted_backup 临时文件
        assert any("decrypted_backup_" in p for p in call_paths)
