"""app.api.v1.system.backup 覆盖率攻坚测试（补充既有 test_backup*.py 未覆盖部分）

覆盖点：
- _authenticate_backup_request：内部密钥通道 / JWT 管理员通道
- preview_backup：404/403/成功/无元信息降级/损坏ZIP
- verify_backup：404/403/成功/异常500
- restore_backup：FileNotFoundError → 404
- upload_and_restore：非法文件名/非ZIP/路径逃逸403/成功+临时文件清理/
  ValueError 400/通用异常500+清理/清理失败降级
"""

import json
import os
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.system.backup as backup_mod
from app.core.database import get_db
from app.core.security import get_current_user


# ==================== 公共设施 ====================


def _admin():
    return SimpleNamespace(id=1, role="admin", username="root", is_superuser=False)


@pytest.fixture
def bk_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = _admin
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _svc_patch(**methods):
    svc = MagicMock()
    for name, ret in methods.items():
        setattr(svc, name, MagicMock(**ret) if isinstance(ret, dict) else ret)
    return patch.object(backup_mod, "get_backup_service", return_value=svc), svc


def _force_realpath_escape():
    """让包含 evil 的路径在 realpath 后逃逸出备份目录（触发 403 安全检查）"""
    real = os.path.realpath

    def _realpath(p):
        if "evil" in str(p):
            return "C:\\outside_evil"
        return real(p)

    return patch.object(backup_mod.os.path, "realpath", side_effect=_realpath)


def _valid_zip_bytes() -> bytes:
    """构造包含数据库文件的合法备份包字节流"""
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data/rural_revitalization.db", "sqlite-db")
        zf.writestr("backup_info.json", '{"database_included": true}')
    return buf.getvalue()


def _encrypted_zip_bytes(password: str) -> bytes:
    """构造加密备份包字节流（BackupService 加密格式）"""
    import tempfile

    from app.services.backup_service import BackupService

    fd, tmp = tempfile.mkstemp(suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(_valid_zip_bytes())
        BackupService._encrypt_file(tmp, password)
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ==================== _authenticate_backup_request ====================


class TestBackupAuth:
    def _record(self):
        rec = MagicMock()
        rec.created_at.isoformat.return_value = "2026-07-25T00:00:00"
        return rec

    def test_internal_key_channel(self, bk_client, monkeypatch):
        """Electron 内部密钥通道 → operator 为 internal-backup（覆盖 64 行）"""
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "secret123")
        p, svc = _svc_patch()
        svc.create_backup.return_value = self._record()
        # 端点内 get_config 走真实库,需打桩避免环境依赖
        with p, patch("app.services.system_config_service.get_config", return_value=""):
            resp = bk_client.post(
                "/api/v1/system/backup",
                json={"description": "自动"},
                headers={"X-Internal-Backup": "secret123"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        svc.create_backup.assert_called_once()

    def test_jwt_admin_channel(self, bk_client, monkeypatch):
        """JWT 管理员通道 → 返回用户名（覆盖 76 行）"""
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "different-key")
        p, svc = _svc_patch()
        svc.create_backup.return_value = self._record()
        # 端点内 get_config 走真实库,需打桩避免环境依赖
        with p, patch(
            "app.core.security.get_current_user",
            AsyncMock(return_value=_admin()),
        ), patch("app.services.system_config_service.get_config", return_value=""):
            resp = bk_client.post(
                "/api/v1/system/backup",
                json={"description": "手动"},
                headers={"Authorization": "Bearer tok123"},
            )
        assert resp.status_code == 200
        svc.create_backup.assert_called_once()


# ==================== preview_backup ====================


class TestPreviewBackup:
    def test_not_found_404(self, bk_client, tmp_path):
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path):
            resp = bk_client.get("/api/v1/system/backup/preview/missing.zip")
        assert resp.status_code == 404

    def test_path_escape_403(self, bk_client, tmp_path):
        (tmp_path / "evil.zip").write_bytes(b"x")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), _force_realpath_escape():
            resp = bk_client.get("/api/v1/system/backup/preview/evil.zip")
        assert resp.status_code == 403

    def test_success_with_meta(self, bk_client, tmp_path):
        zp = tmp_path / "good.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("backup_info.json", json.dumps({"app": "test"}))
            zf.writestr("db.sqlite", b"12345")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path):
            resp = bk_client.get("/api/v1/system/backup/preview/good.zip")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["meta"] == {"app": "test"}
        assert len(data["files"]) == 2
        assert data["size"] > 0

    def test_meta_fallback_empty(self, bk_client, tmp_path):
        zp = tmp_path / "nometa.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("db.sqlite", b"1")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path):
            resp = bk_client.get("/api/v1/system/backup/preview/nometa.zip")
        assert resp.status_code == 200
        assert resp.json()["data"]["meta"] == {}

    def test_bad_zip_400(self, bk_client, tmp_path):
        (tmp_path / "bad.zip").write_bytes(b"not a zip at all")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path):
            resp = bk_client.get("/api/v1/system/backup/preview/bad.zip")
        assert resp.status_code == 400


# ==================== verify_backup ====================


class TestVerifyBackup:
    def test_not_found_404(self, bk_client, tmp_path):
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path):
            resp = bk_client.post("/api/v1/system/backup/verify/missing.zip")
        assert resp.status_code == 404

    def test_path_escape_403(self, bk_client, tmp_path):
        (tmp_path / "evil.zip").write_bytes(b"x")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), _force_realpath_escape():
            resp = bk_client.post("/api/v1/system/backup/verify/evil.zip")
        assert resp.status_code == 403

    def test_success(self, bk_client, tmp_path):
        (tmp_path / "ok.zip").write_bytes(b"PK")
        p, svc = _svc_patch()
        svc.verify_backup.return_value = {"status": "ok"}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post("/api/v1/system/backup/verify/ok.zip")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"status": "ok"}

    def test_service_exception_500(self, bk_client, tmp_path):
        (tmp_path / "err.zip").write_bytes(b"PK")
        p, svc = _svc_patch()
        svc.verify_backup.side_effect = RuntimeError("boom")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post("/api/v1/system/backup/verify/err.zip")
        assert resp.status_code == 500


# ==================== restore_backup 补充分支 ====================


class TestRestoreBackupExtra:
    def test_file_not_found_error_404(self, bk_client, tmp_path):
        """恢复过程中文件消失 → FileNotFoundError → 404（覆盖 454 行）"""
        (tmp_path / "exists.zip").write_bytes(b"PK")
        p, svc = _svc_patch()
        svc.restore_backup.side_effect = FileNotFoundError("gone")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post("/api/v1/system/backup/restore", json={"filename": "exists.zip"})
        assert resp.status_code == 404


# ==================== upload_and_restore ====================


class TestUploadAndRestore:
    def test_illegal_filename_400(self, bk_client):
        resp = bk_client.post(
            "/api/v1/system/backup/upload-restore",
            files={"file": ("a/b.zip", b"x", "application/zip")},
        )
        assert resp.status_code == 400

    def test_dotdot_filename_400(self, bk_client):
        resp = bk_client.post(
            "/api/v1/system/backup/upload-restore",
            files={"file": ("evil..zip", b"x", "application/zip")},
        )
        assert resp.status_code == 400

    def test_non_zip_400(self, bk_client):
        resp = bk_client.post(
            "/api/v1/system/backup/upload-restore",
            files={"file": ("data.txt", b"x", "text/plain")},
        )
        assert resp.status_code == 400

    def test_path_escape_403(self, bk_client, tmp_path):
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), _force_realpath_escape():
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("evil.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 403

    def test_success_and_temp_cleanup(self, bk_client, tmp_path):
        p, svc = _svc_patch()
        svc.restore_backup.return_value = {"restored": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"restored": True}
        svc.restore_backup.assert_called_once()
        assert svc.restore_backup.call_args.kwargs.get("password") is None  # 未提供密码
        assert list(tmp_path.glob("upload_*")) == []  # 临时文件已清理

    def test_list_reports_is_encrypted(self, bk_client, tmp_path, monkeypatch):
        """备份列表返回 is_encrypted（加密/明文/读取失败三态）"""
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "secret123")
        enc_path = os.path.join(str(tmp_path), "enc.zip")
        plain_path = os.path.join(str(tmp_path), "plain.zip")
        with open(plain_path, "wb") as f:
            f.write(_valid_zip_bytes())
        with open(enc_path, "wb") as f:
            f.write(_encrypted_zip_bytes("pwd123"))

        def make_record(name, path):
            rec = MagicMock()
            rec.backup_id = 1
            rec.file_name = name
            rec.file_path = path
            rec.file_size = 10
            rec.description = "d"
            rec.backup_type = "full"
            rec.created_at.isoformat.return_value = "2024-01-01T00:00:00"
            return rec

        records = [
            make_record("enc.zip", enc_path),
            make_record("plain.zip", plain_path),
            make_record("missing.zip", os.path.join(str(tmp_path), "nope.zip")),
        ]
        p, svc = _svc_patch()
        svc.list_backups.return_value = records
        with p:
            # 列表端点鉴权已改为"内部密钥或 JWT"(JWT 通道不经 dependency_overrides),
            # 走内部密钥通道模拟 Electron 保留策略清理的读取路径。
            resp = bk_client.get(
                "/api/v1/system/backup", headers={"X-Internal-Backup": "secret123"}
            )
        assert resp.status_code == 200
        by_name = {it["file_name"]: it["is_encrypted"] for it in resp.json()["data"]["items"]}
        assert by_name == {"enc.zip": True, "plain.zip": False, "missing.zip": False}

    def test_encrypted_requires_password_400(self, bk_client, tmp_path):
        """加密备份未提供密码且自动备份密钥不可用 → 400（覆盖预校验分支），磁盘零残留"""
        p, svc = _svc_patch()
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), \
             patch("app.utils.runtime_secrets.get_or_create_secret", side_effect=RuntimeError("no secrets")), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("enc.zip", _encrypted_zip_bytes("pwd123"), "application/zip")},
            )
        assert resp.status_code == 400
        assert "password" in resp.json()["detail"] or "密码" in resp.json()["detail"]
        svc.restore_backup.assert_not_called()
        assert list(tmp_path.glob("upload_*")) == []

    def test_encrypted_auto_key_fallback_success(self, bk_client, tmp_path):
        """加密备份未提供密码但本机存在自动备份密钥 → 自动兜底解密并恢复"""
        p, svc = _svc_patch()
        svc.restore_backup.return_value = {"restored": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), \
             patch("app.utils.runtime_secrets.get_or_create_secret", return_value="auto-backup-secret"), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("enc.zip", _encrypted_zip_bytes("pwd123"), "application/zip")},
            )
        assert resp.status_code == 200
        svc.restore_backup.assert_called_once()
        assert svc.restore_backup.call_args.kwargs.get("password") == "auto-backup-secret"
        assert list(tmp_path.glob("upload_*")) == []

    def test_encrypted_with_password_success(self, bk_client, tmp_path):
        """加密备份提供密码 → 200 且密码透传给恢复服务"""
        p, svc = _svc_patch()
        svc.restore_backup.return_value = {"restored": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("enc.zip", _encrypted_zip_bytes("pwd123"), "application/zip")},
                data={"password": "pwd123"},
            )
        assert resp.status_code == 200
        svc.restore_backup.assert_called_once()
        assert svc.restore_backup.call_args.kwargs.get("password") == "pwd123"

    def test_corrupted_zip_400(self, bk_client, tmp_path):
        """损坏的 ZIP → 400 不进入恢复流程"""
        p, svc = _svc_patch()
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("bad.zip", b"not-a-zip", "application/zip")},
            )
        assert resp.status_code == 400
        assert "ZIP" in resp.json()["detail"]
        svc.restore_backup.assert_not_called()
        assert list(tmp_path.glob("upload_*")) == []

    def test_zip_without_db_400(self, bk_client, tmp_path):
        """ZIP 内缺少数据库文件 → 400"""
        import io

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("uploads/f.txt", "x")
        p, svc = _svc_patch()
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("nodb.zip", buf.getvalue(), "application/zip")},
            )
        assert resp.status_code == 400
        assert "数据库" in resp.json()["detail"]
        svc.restore_backup.assert_not_called()

    def test_cleanup_failure_degrades(self, bk_client, tmp_path):
        """恢复成功后临时文件删除失败 → 仅告警不影响结果（覆盖 524-526）"""
        p, svc = _svc_patch()
        svc.restore_backup.return_value = {"restored": True}
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p, patch.object(
            backup_mod.os, "remove", side_effect=OSError("locked")
        ):
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 200

    def test_value_error_400_and_cleanup(self, bk_client, tmp_path):
        p, svc = _svc_patch()
        svc.restore_backup.side_effect = ValueError("备份损坏")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 400
        assert list(tmp_path.glob("upload_*")) == []

    def test_generic_error_500_and_cleanup(self, bk_client, tmp_path):
        p, svc = _svc_patch()
        svc.restore_backup.side_effect = RuntimeError("boom")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p:
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 500
        assert list(tmp_path.glob("upload_*")) == []


# ==================== 补盲：401 与清理降级 ====================


class TestBackupAuthAndCleanupEdge:
    def test_no_credentials_401(self, bk_client, monkeypatch):
        """内部密钥不匹配且无 Bearer 凭证 → 401（覆盖 73 行）

        bk_client 默认 override get_current_user, 需临时移除以验证真实无凭证路径。
        """
        from app.core.security import get_current_user
        from app.main import app

        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "secret123")
        saved = app.dependency_overrides.pop(get_current_user, None)
        try:
            resp = bk_client.post("/api/v1/system/backup", json={"description": "x"})
        finally:
            if saved is not None:
                app.dependency_overrides[get_current_user] = saved
        assert resp.status_code == 401

    def test_list_delete_401_without_credentials(self, bk_client, monkeypatch):
        """GET/DELETE 列表/删除端点: 内部密钥不匹配且无 Bearer → 401

        bk_client 默认 override get_current_user 模拟已登录用户, 此处临时
        移除 override 以验证真实无凭证路径(JWT 通道手动解析)。
        """
        from app.core.security import get_current_user
        from app.main import app

        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "secret123")
        saved = app.dependency_overrides.pop(get_current_user, None)
        try:
            assert bk_client.get("/api/v1/system/backup").status_code == 401
            assert bk_client.delete("/api/v1/system/backup/whatever.zip").status_code == 401
        finally:
            if saved is not None:
                app.dependency_overrides[get_current_user] = saved

    def test_internal_key_can_list_and_delete(self, bk_client, monkeypatch, tmp_path):
        """Electron 7 天保留策略: 内部密钥通道可读取列表并删除过期备份(回归锁定)

        回归背景: 清理请求原先无任何凭证, GET/DELETE 恒 401,
        旧备份无限累积占满磁盘。
        """
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "secret123")
        headers = {"X-Internal-Backup": "secret123"}

        rec = MagicMock()
        rec.backup_id = 7
        rec.file_name = "backup_old.zip"
        rec.file_path = os.path.join(str(tmp_path), "backup_old.zip")
        rec.file_size = 1
        rec.description = "auto"
        rec.backup_type = "full"
        rec.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        p, svc = _svc_patch()
        svc.list_backups.return_value = [rec]
        svc.delete_backup.return_value = True
        with p:
            resp_list = bk_client.get("/api/v1/system/backup", headers=headers)
            resp_del = bk_client.delete("/api/v1/system/backup/backup_old.zip", headers=headers)
        assert resp_list.status_code == 200
        assert [it["file_name"] for it in resp_list.json()["data"]["items"]] == ["backup_old.zip"]
        assert resp_del.status_code == 200
        svc.delete_backup.assert_called_once_with(7)

    def test_generic_error_cleanup_oserror_degrades(self, bk_client, tmp_path):
        """通用异常清理临时文件时 OSError → 静默跳过仍 500（覆盖 544-545 行）"""
        p, svc = _svc_patch()
        svc.restore_backup.side_effect = RuntimeError("boom")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p, patch.object(
            backup_mod.os, "remove", side_effect=OSError("locked")
        ):
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 500

    def test_value_error_cleanup_oserror_degrades(self, bk_client, tmp_path):
        """ValueError 路径清理临时文件时 OSError → 静默跳过仍 400（覆盖 539-540 行）"""
        p, svc = _svc_patch()
        svc.restore_backup.side_effect = ValueError("备份损坏")
        with patch("app.utils.paths.get_backup_path", return_value=tmp_path), p, patch.object(
            backup_mod.os, "remove", side_effect=OSError("locked")
        ):
            resp = bk_client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", _valid_zip_bytes(), "application/zip")},
            )
        assert resp.status_code == 400
