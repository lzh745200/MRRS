"""app.api.v1.system.backup 二轮覆盖补全（补 test_backup_api_cov.py 未覆盖部分）

覆盖缺口（基线 miss）：
- 82：_resolve_auto_backup_password(provided) 直接透传
- 225-227：create_backup 抛 BackupIncompleteError → 500（细节不出站）
- 240-266：request-download 端点全部（通知全部超管）
- 456：update_backup_schedule 写入 cron 配置
- 729-735：upload-restore 磁盘预检不足 → 409
- 779：上传流超过 10GB 上限 → 413（mock open 不落盘）
- 846-847：HTTPException 清理临时文件时 OSError → 静默降级
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.api.v1.system.backup as backup_mod
from app.core.database import get_db
from app.core.security import get_current_user


def _admin():
    return SimpleNamespace(id=1, role="admin", username="root", is_superuser=False)


@pytest.fixture
def client2():
    """带可控 db 的客户端（get_db 每次返回同一个 MagicMock）"""
    from app.main import app

    original = app.dependency_overrides.copy()
    db = MagicMock(name="db")
    app.dependency_overrides[get_current_user] = _admin
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=False), db
    app.dependency_overrides = original


def _svc_patch():
    svc = MagicMock()
    return patch.object(backup_mod, "get_backup_service", return_value=svc), svc


# ==================== _resolve_auto_backup_password ====================


class TestResolveAutoBackupPassword:
    def test_provided_password_passthrough(self):
        # 覆盖 backup.py:82 —— 已提供密码直接返回，不再读运行时密钥
        assert backup_mod._resolve_auto_backup_password("mypw") == "mypw"


# ==================== create_backup: BackupIncompleteError ====================


class TestCreateBackupIncomplete:
    def test_incomplete_backup_500(self, client2, monkeypatch):
        # 覆盖 backup.py:225-227 —— 备份完整性校验失败 → 500，异常细节不出站
        client, _ = client2
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "k")
        from app.services.backup_service import BackupIncompleteError

        p, svc = _svc_patch()
        svc.create_backup.side_effect = BackupIncompleteError("校验未通过")
        with p, patch("app.services.system_config_service.get_config", return_value=""):
            resp = client.post(
                "/api/v1/system/backup",
                json={"description": "x"},
                headers={"X-Internal-Backup": "k"},
            )
        assert resp.status_code == 500
        assert "完整性校验未通过" in resp.json()["detail"]


# ==================== request-download ====================


class TestRequestDownload:
    def test_notifies_all_superadmins(self, client2):
        # 覆盖 backup.py:240-266 —— 普通用户申请下载 → 站内消息通知全部超管
        client, db = client2
        db.execute.return_value.fetchall.return_value = [(1,), (2,)]
        with patch("app.services.message_service.MessageService") as msvc:
            resp = client.post(
                "/api/v1/system/backup/request-download",
                json={"filename": "b.zip", "reason": "审计需要"},
            )
        assert resp.status_code == 200
        assert "申请已提交" in resp.json()["message"]
        send = msvc.return_value.send_system_message
        assert send.call_count == 2
        kwargs = send.call_args_list[0].kwargs
        assert kwargs["receiver_id"] == 1
        assert "b.zip" in kwargs["content"]
        assert "审计需要" in kwargs["content"]
        assert kwargs["link"] == "/system/backup"

    def test_no_admins_still_succeeds(self, client2):
        # 无超管时空发（循环零次），仍提交成功
        client, db = client2
        db.execute.return_value.fetchall.return_value = []
        with patch("app.services.message_service.MessageService") as msvc:
            resp = client.post("/api/v1/system/backup/request-download", json={})
        assert resp.status_code == 200
        msvc.return_value.send_system_message.assert_not_called()


# ==================== update_backup_schedule ====================


class TestUpdateBackupSchedule:
    def test_schedule_cron_written(self, client2):
        # 覆盖 backup.py:456 —— schedule 字段写入 backup_schedule_cron 配置
        client, _ = client2
        cfg = {
            "auto_backup": "true",
            "backup_retention_days": "5",
            "backup_schedule_cron": "0 3 * * *",
        }
        set_calls = []

        def fake_set(key, value, _desc=None):
            set_calls.append((key, value))

        with (
            patch.object(backup_mod, "set_config", side_effect=fake_set),
            patch.object(
                backup_mod, "get_config",
                side_effect=lambda key, default=None: cfg.get(key, default),
            ),
        ):
            resp = client.put(
                "/api/v1/system/backup/schedule",
                json={"enabled": True, "schedule": "0 3 * * *", "keep_count": 5},
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {"enabled": True, "schedule": "0 3 * * *", "keepCount": 5}
        assert ("backup_schedule_cron", "0 3 * * *") in set_calls
        assert ("backup_retention_days", "5") in set_calls
        assert ("auto_backup", "true") in set_calls


# ==================== _jwt_user_from_request: awaitable override ====================


class TestJwtAwaitableOverride:
    async def test_awaitable_dependency_override_user(self):
        # 覆盖 backup.py:122 —— dependency override 返回协程时 await 结果
        from app.main import app

        app.dependency_overrides[get_current_user] = AsyncMock(return_value=_admin())
        try:
            req = SimpleNamespace(app=app, headers={})
            user = await backup_mod._jwt_user_from_request(req)
            assert user.username == "root"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ==================== set_backup_target: 通用异常 500 ====================


class TestSetBackupTargetError:
    def test_generic_error_500(self, client2):
        # 覆盖 backup.py:403-405 —— set_config 异常 → 500
        client, _ = client2
        with patch(
            "app.services.system_config_service.set_config",
            side_effect=RuntimeError("db down"),
        ):
            resp = client.put("/api/v1/system/backup/target", json={"target_dir": ""})
        assert resp.status_code == 500
        assert "设置备份目标失败" in resp.json()["detail"]


# ==================== upload-restore: 磁盘预检 409 ====================


class TestUploadDiskPrecheck:
    def test_insufficient_disk_409(self, client2):
        # 覆盖 backup.py:729-735 —— 备份目录所在盘 <500MB → 409
        client, _ = client2
        with patch(
            "app.core.database.check_disk_space",
            return_value={"sufficient": False, "free_mb": 100},
        ):
            resp = client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("data.zip", b"PK", "application/zip")},
            )
        assert resp.status_code == 409
        assert "磁盘剩余空间不足" in resp.json()["detail"]


# ==================== upload-restore: 超限 413 ====================


class TestUploadOversize:
    async def test_oversize_stream_413(self, tmp_path):
        # 覆盖 backup.py:779 —— 分块流式上传超过 10GB 上限 → 413
        # mock open 避免真实落盘 10GB；read 无限返回 8MB 块直至触发上限
        chunk = b"x" * (8 * 1024 * 1024)
        fake_file = SimpleNamespace(
            filename="big.zip", read=AsyncMock(side_effect=lambda _size=None: chunk)
        )
        with (
            patch("app.utils.paths.get_backup_path", return_value=tmp_path),
            patch("builtins.open", mock_open()),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await backup_mod.upload_and_restore(
                    file=fake_file, password=None,
                    db=MagicMock(), current_user=_admin(),
                )
        assert exc_info.value.status_code == 413
        assert "10GB" in exc_info.value.detail


# ==================== upload-restore: 清理 OSError 降级 ====================


class TestUploadCleanupOSError:
    def test_http_exception_cleanup_oserror_degrades(self, client2, tmp_path):
        # 覆盖 backup.py:846-847 —— HTTPException 清理临时文件 OSError → 静默仍 400
        client, _ = client2
        marker = b"MRRMS_BACKUP_ENCRYPTED_V1"
        with (
            patch("app.utils.paths.get_backup_path", return_value=tmp_path),
            patch.object(backup_mod, "_resolve_auto_backup_password", return_value=None),
            patch.object(backup_mod.os, "remove", side_effect=OSError("locked")),
        ):
            resp = client.post(
                "/api/v1/system/backup/upload-restore",
                files={"file": ("enc.zip", marker + b"junk", "application/zip")},
            )
        assert resp.status_code == 400
        assert "密码" in resp.json()["detail"]
