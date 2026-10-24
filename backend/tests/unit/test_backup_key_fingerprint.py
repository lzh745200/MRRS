"""备份包 PII 密钥指纹：写入 / 恢复校验 / 强制放行 / 审计（跨机迁移防护）。

背景（历史 P1）：换机或重装后 ENCRYPTION_KEY 不同，备份包里的 9 列 AES-SIV
密文将永久不可解，而旧备份包不含任何密钥线索。本模块验证：

1. 生成备份时在 ``backup_info.json`` 写入 ``key_fingerprint``（不写密钥本身）；
2. 恢复时指纹不一致 → 拒绝自动恢复（``BackupKeyMismatchError``），且**不碰现场库**；
3. ``allow_key_mismatch=True`` 可显式强制继续；
4. 旧备份（无该字段 / 无 backup_info.json / 历史 ``str(dict)`` 写法）仍可正常恢复；
5. 拒绝与强制都写审计（``AuditLogger``，动作名 ``system_restore_key_mismatch``）；
6. HTTP 层：``/restore``、``/upload-restore`` 参数透传 + 409 语义。
"""

import json
import os
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.system.backup as backup_mod
from app.core.database import get_db
from app.core.security import get_current_user
from app.services.backup_service import (
    BackupKeyMismatchError,
    BackupRestoreError,
    BackupService,
)

CURRENT_FP = "0123456789abcdef"
OTHER_FP = "fedcba9876543210"


# ==================== 夹具 / 工具 ====================


def _make_svc(mock_db, backup_dir, db_path, uploads_dir):
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


def _real_sqlite_bytes(tmp_path, marker="seed"):
    p = Path(tmp_path) / f"_src_{marker}_{os.urandom(4).hex()}.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS data (v TEXT)")
        conn.execute("INSERT INTO data (v) VALUES (?)", (marker,))
        conn.commit()
    finally:
        conn.close()
    raw = p.read_bytes()
    p.unlink()
    return raw


def _write_db(db_path, marker="orig"):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS data (v TEXT)")
        conn.execute("DELETE FROM data")
        conn.execute("INSERT INTO data (v) VALUES (?)", (marker,))
        conn.commit()
    finally:
        conn.close()


def _db_marker(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT v FROM data LIMIT 1").fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


def _make_backup_zip(zip_path, db_bytes, info=None):
    """写一个最小可恢复备份包；info 为 None 时不写 backup_info.json。"""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/rural_revitalization.db", db_bytes)
        if info is not None:
            zf.writestr("backup_info.json", json.dumps(info, ensure_ascii=False))
    return zip_path


def _read_info(zip_path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        return json.loads(zf.read("backup_info.json").decode("utf-8"))


def _audit_calls(mock_log):
    return [c for c in mock_log.call_args_list]


@pytest.fixture
def patched_fingerprint():
    """让本机的 PII 密钥指纹可控（不依赖真实 ENCRYPTION_KEY）。"""
    with patch("app.core.pii_crypto.key_fingerprint", return_value=CURRENT_FP):
        yield CURRENT_FP


# ==================== 1. 写入 ====================


class TestFingerprintWrittenIntoBackup:
    def test_full_backup_info_contains_key_fingerprint(self, mock_db, tmp_path, patched_fingerprint):
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        _write_db(db_path)
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        os.makedirs(tmp_path / "backups")
        svc = _make_svc(mock_db, str(tmp_path / "backups"), db_path, up_dir)

        record = svc.create_backup(description="指纹用例")

        info = _read_info(record.file_path)
        assert info["key_fingerprint"] == CURRENT_FP
        # 只落指纹，绝不落密钥材料
        assert "encryption_key" not in info
        assert "key" not in {k for k in info if k != "key_fingerprint"}

    def test_backup_info_is_valid_json(self, mock_db, tmp_path, patched_fingerprint):
        """历史实现用 str(dict) 写入，preview/verify 解析必然失败；改为合法 JSON。"""
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        _write_db(db_path)
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        os.makedirs(tmp_path / "backups")
        svc = _make_svc(mock_db, str(tmp_path / "backups"), db_path, up_dir)

        record = svc.create_backup()

        with zipfile.ZipFile(record.file_path, "r") as zf:
            raw = zf.read("backup_info.json").decode("utf-8")
        assert json.loads(raw)["key_fingerprint"] == CURRENT_FP

    def test_incremental_backup_info_contains_key_fingerprint(self, mock_db, tmp_path, patched_fingerprint):
        svc = _make_svc(
            mock_db, str(tmp_path / "backups"),
            str(tmp_path / "data" / "rural_revitalization.db"),
            str(tmp_path / "uploads"),
        )
        zip_path = str(tmp_path / "backups" / "backup_incremental_x.zip")
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        svc._write_incremental_backup_zip(zip_path, [], {}, "20260101_000000", "增量", True)

        assert _read_info(zip_path)["key_fingerprint"] == CURRENT_FP

    def test_fingerprint_failure_does_not_break_backup(self, mock_db, tmp_path):
        """指纹读不到（密钥未初始化等）时备份仍应成功，只是不带该字段。"""
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        _write_db(db_path)
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        os.makedirs(tmp_path / "backups")
        svc = _make_svc(mock_db, str(tmp_path / "backups"), db_path, up_dir)

        with patch("app.core.pii_crypto.key_fingerprint", side_effect=RuntimeError("no key")):
            record = svc.create_backup()

        assert "key_fingerprint" not in _read_info(record.file_path)


# ==================== 2. 恢复：不一致拒绝 / 一致放行 / 旧包兼容 ====================


class TestRestoreFingerprintGate:
    def _setup(self, mock_db, tmp_path, backup_fp=CURRENT_FP):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        info = {"timestamp": "20260101_000000", "include_uploads": True}
        if backup_fp is not None:
            info["key_fingerprint"] = backup_fp
        zip_path = _make_backup_zip(
            os.path.join(bdir, "backup.zip"), _real_sqlite_bytes(tmp_path, "restored"), info
        )
        return svc, zip_path, db_path

    def test_matching_fingerprint_restores(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path, db_path = self._setup(mock_db, tmp_path, CURRENT_FP)

        result = svc.restore_backup(zip_path)

        assert result["success"] is True
        assert _db_marker(db_path) == "restored"

    def test_mismatch_rejected_and_database_untouched(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path, db_path = self._setup(mock_db, tmp_path, OTHER_FP)

        with pytest.raises(BackupKeyMismatchError) as ei:
            svc.restore_backup(zip_path)

        # 明确的中文提示：说明后果与两条放行路径
        msg = str(ei.value)
        assert "不同密钥" in msg
        assert "敏感字段" in msg and "不可读" in msg
        assert "allow_key_mismatch" in msg
        assert ei.value.backup_fingerprint == OTHER_FP
        assert ei.value.current_fingerprint == CURRENT_FP
        # 拒绝发生在覆盖现场库之前：库内容必须原样
        assert _db_marker(db_path) == "orig"

    def test_force_allows_restore(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path, db_path = self._setup(mock_db, tmp_path, OTHER_FP)

        result = svc.restore_backup(zip_path, allow_key_mismatch=True)

        assert result["success"] is True
        assert result["key_mismatch"]["forced"] is True
        assert result["key_mismatch"]["backup_fingerprint"] == OTHER_FP
        assert _db_marker(db_path) == "restored"

    def test_old_backup_without_field_restores(self, mock_db, tmp_path, patched_fingerprint):
        """向后兼容：旧备份无 key_fingerprint → 正常恢复。"""
        svc, zip_path, db_path = self._setup(mock_db, tmp_path, None)

        result = svc.restore_backup(zip_path)

        assert result["success"] is True
        assert "key_mismatch" not in result
        assert _db_marker(db_path) == "restored"

    def test_backup_without_info_file_restores(self, mock_db, tmp_path, patched_fingerprint):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        zip_path = _make_backup_zip(
            os.path.join(bdir, "noinfo.zip"), _real_sqlite_bytes(tmp_path, "restored"), None
        )

        assert svc.restore_backup(zip_path)["success"] is True
        assert _db_marker(db_path) == "restored"

    def test_legacy_python_dict_backup_info_is_parsed(self, mock_db, tmp_path, patched_fingerprint):
        """历史全量备份用 ``str(dict)``（单引号）写 backup_info.json，也必须能比对。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        zip_path = os.path.join(bdir, "legacy.zip")
        legacy_info = str({"timestamp": "20200101", "key_fingerprint": OTHER_FP})
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", _real_sqlite_bytes(tmp_path, "restored"))
            zf.writestr("backup_info.json", legacy_info)

        with pytest.raises(BackupKeyMismatchError):
            svc.restore_backup(zip_path)
        assert _db_marker(db_path) == "orig"

    def test_unparseable_backup_info_is_treated_as_legacy(self, mock_db, tmp_path, patched_fingerprint):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        zip_path = os.path.join(bdir, "broken_info.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", _real_sqlite_bytes(tmp_path, "restored"))
            zf.writestr("backup_info.json", "not-json-at-all")

        assert svc.restore_backup(zip_path)["success"] is True

    def test_backup_info_non_object_json_is_treated_as_legacy(self, mock_db, tmp_path, patched_fingerprint):
        """backup_info.json 是合法 JSON 但非对象（如数组）→ 视为无元信息。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        zip_path = os.path.join(bdir, "list_info.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/rural_revitalization.db", _real_sqlite_bytes(tmp_path, "restored"))
            zf.writestr("backup_info.json", "[1, 2, 3]")

        assert svc._read_backup_key_fingerprint(zip_path) is None
        assert svc.restore_backup(zip_path)["success"] is True

    def test_current_fingerprint_unavailable_allows_restore(self, mock_db, tmp_path):
        """本机指纹不可用时无法判定：放行（不因"算不出来"而锁死恢复通道）。"""
        svc, zip_path, db_path = self._setup(mock_db, tmp_path, OTHER_FP)

        with patch("app.core.pii_crypto.key_fingerprint", side_effect=RuntimeError("no key")):
            result = svc.restore_backup(zip_path)

        assert result["success"] is True
        assert _db_marker(db_path) == "restored"

    def test_encrypted_backup_mismatch_rejected(self, mock_db, tmp_path, patched_fingerprint):
        """加密备份：指纹从解密后的临时包读取，同样拦截。"""
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        _write_db(db_path)
        up_dir = str(tmp_path / "uploads")
        os.makedirs(up_dir)
        os.makedirs(tmp_path / "backups")
        svc = _make_svc(mock_db, str(tmp_path / "backups"), db_path, up_dir)
        record = svc.create_backup(password="pwd123")
        # 加密包不是 zip：先解密到临时包再读元信息（指纹在加密之前写入）
        assert svc._is_encrypted(record.file_path)
        decrypted = svc._decrypt_to_temp(record.file_path, "pwd123")
        try:
            assert _read_info(decrypted)["key_fingerprint"] == CURRENT_FP
        finally:
            os.remove(decrypted)

        with patch("app.core.pii_crypto.key_fingerprint", return_value=OTHER_FP):
            with pytest.raises(BackupKeyMismatchError):
                svc.restore_backup(record.file_path, password="pwd123")

    def test_restore_error_still_wraps_non_mismatch_failures(self, mock_db, tmp_path, patched_fingerprint):
        """既有失败语义不被新分支改变：缺库仍是 BackupRestoreError。"""
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        zip_path = os.path.join(bdir, "no_db.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("uploads/f.txt", "x")

        with pytest.raises(BackupRestoreError):
            svc.restore_backup(zip_path)

    def test_read_backup_key_fingerprint_helper(self, mock_db, tmp_path):
        svc = _make_svc(
            mock_db, str(tmp_path / "b"),
            str(tmp_path / "data" / "rural_revitalization.db"), str(tmp_path / "u"),
        )
        zip_path = _make_backup_zip(
            str(tmp_path / "fp.zip"), b"x", {"key_fingerprint": "  spaced-fp  "}
        )
        assert svc._read_backup_key_fingerprint(zip_path) == "spaced-fp"
        blank = _make_backup_zip(str(tmp_path / "blank.zip"), b"x", {"key_fingerprint": "   "})
        assert svc._read_backup_key_fingerprint(blank) is None


# ==================== 3. 审计 ====================


class TestMismatchAudit:
    def _setup(self, mock_db, tmp_path, backup_fp=OTHER_FP):
        bdir = str(tmp_path / "backups")
        db_path = str(tmp_path / "data" / "rural_revitalization.db")
        up_dir = str(tmp_path / "uploads")
        os.makedirs(bdir)
        os.makedirs(up_dir)
        _write_db(db_path, "orig")
        svc = _make_svc(mock_db, bdir, db_path, up_dir)
        zip_path = _make_backup_zip(
            os.path.join(bdir, "backup.zip"),
            _real_sqlite_bytes(tmp_path, "restored"),
            {"timestamp": "20260101_000000", "key_fingerprint": backup_fp},
        )
        return svc, zip_path

    def test_reject_writes_audit(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path = self._setup(mock_db, tmp_path)

        with patch("app.utils.audit_logger.AuditLogger.log") as audit:
            with pytest.raises(BackupKeyMismatchError):
                svc.restore_backup(zip_path, operator="admin")

        calls = _audit_calls(audit)
        assert len(calls) == 1
        kwargs = calls[0].kwargs
        assert kwargs["action"] == "system_restore_key_mismatch"
        assert kwargs["username"] == "admin"
        assert kwargs["resource_type"] == "backup"
        details = kwargs["details"]
        assert details["forced"] is False
        assert details["backup_fingerprint"] == OTHER_FP
        assert details["current_fingerprint"] == CURRENT_FP
        # 只出指纹，不出任何密钥材料
        assert set(details) == {
            "filename", "backup_fingerprint", "current_fingerprint", "forced",
        }

    def test_force_writes_audit(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path = self._setup(mock_db, tmp_path)

        with patch("app.utils.audit_logger.AuditLogger.log") as audit:
            result = svc.restore_backup(zip_path, allow_key_mismatch=True, operator="admin")

        assert result["success"] is True
        calls = _audit_calls(audit)
        assert len(calls) == 1
        assert calls[0].kwargs["details"]["forced"] is True

    def test_matching_fingerprint_writes_no_audit(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path = self._setup(mock_db, tmp_path, CURRENT_FP)

        with patch("app.utils.audit_logger.AuditLogger.log") as audit:
            svc.restore_backup(zip_path)

        audit.assert_not_called()

    def test_audit_failure_does_not_break_rejection(self, mock_db, tmp_path, patched_fingerprint):
        svc, zip_path = self._setup(mock_db, tmp_path)

        with patch("app.utils.audit_logger.AuditLogger.log", side_effect=RuntimeError("db down")):
            with pytest.raises(BackupKeyMismatchError):
                svc.restore_backup(zip_path)


# ==================== 4. HTTP 层 ====================


def _admin():
    return SimpleNamespace(id=1, role="admin", username="root", is_superuser=False)


def _valid_zip_bytes():
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/rural_revitalization.db", b"SQLite format 3\x00")
    return buf.getvalue()


@pytest.fixture
def bk_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = _admin
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


class TestApiKeyMismatch:
    def _patch_svc(self, **kwargs):
        svc = MagicMock()
        for name, value in kwargs.items():
            setattr(svc, name, value)
        return patch.object(backup_mod, "get_backup_service", return_value=svc), svc

    def test_restore_409_on_mismatch(self, bk_client, tmp_path):
        (tmp_path / "backup.zip").write_bytes(b"PK")
        p, svc = self._patch_svc()
        svc.restore_backup.side_effect = BackupKeyMismatchError(
            "备份来自不同密钥的机器，恢复后敏感字段将不可读；"
            "如确认使用旧密钥，请先导入密钥或使用强制恢复（allow_key_mismatch=true）。"
        )
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/restore", json={"filename": "backup.zip"}
            )
        assert resp.status_code == 409
        assert "不同密钥" in resp.json()["detail"]

    def test_restore_default_rejects_mismatch(self, bk_client, tmp_path):
        (tmp_path / "backup.zip").write_bytes(b"PK")
        p, svc = self._patch_svc()
        svc.restore_backup.return_value = {"success": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/restore", json={"filename": "backup.zip"}
            )
        assert resp.status_code == 200
        assert svc.restore_backup.call_args.kwargs["allow_key_mismatch"] is False

    def test_restore_forwards_allow_key_mismatch(self, bk_client, tmp_path):
        (tmp_path / "backup.zip").write_bytes(b"PK")
        p, svc = self._patch_svc()
        svc.restore_backup.return_value = {"success": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/restore",
                json={"filename": "backup.zip", "allow_key_mismatch": True},
            )
        assert resp.status_code == 200
        assert svc.restore_backup.call_args.kwargs["allow_key_mismatch"] is True

    def test_upload_restore_409_on_mismatch(self, bk_client, tmp_path):
        p, svc = self._patch_svc()
        svc.restore_backup.side_effect = BackupKeyMismatchError("备份来自不同密钥的机器")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("b.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 409
        assert "不同密钥" in resp.json()["detail"]
        assert list(tmp_path.glob("upload_*")) == []  # 失败也要清理临时文件

    def test_upload_restore_forwards_allow_key_mismatch(self, bk_client, tmp_path):
        p, svc = self._patch_svc()
        svc.restore_backup.return_value = {"success": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("b.zip", _valid_zip_bytes(), "application/zip")},
                data={"allow_key_mismatch": "true"},
            )
        assert resp.status_code == 200
        assert svc.restore_backup.call_args.kwargs["allow_key_mismatch"] is True

    def test_upload_restore_default_is_strict(self, bk_client, tmp_path):
        p, svc = self._patch_svc()
        svc.restore_backup.return_value = {"success": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("b.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 200
        assert svc.restore_backup.call_args.kwargs["allow_key_mismatch"] is False
