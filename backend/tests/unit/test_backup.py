"""
Tests for system/backup.py — backup management API.
Covers create, list, stats, schedule, delete, download, restore endpoints.
"""
import json
import os
from unittest.mock import MagicMock, patch
import pytest

BASE = "/api/v1/system/backup"


def _override_actor(client, actor="admin"):
    """覆盖备份创建端点的操作人鉴权依赖。

    create_backup 自 2026-07 起改用 Depends(_authenticate_backup_request)
    （内部密钥 / JWT 双通道），测试需直接覆盖该依赖而非 get_current_user。
    """
    from app.api.v1.system.backup import _authenticate_backup_request

    client.app.dependency_overrides[_authenticate_backup_request] = lambda: actor


# ── create_backup ────────────────────────────────────────────────────

class TestCreateBackup:
    def test_requires_auth(self, client):
        resp = client.post(BASE, json={})
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        mock_record = MagicMock()
        mock_record.backup_id = 1
        mock_record.file_name = "backup_2024.zip"
        mock_record.file_path = "/backups/backup_2024.zip"
        mock_record.file_size = 1024
        mock_record.description = "手动备份"
        mock_record.created_at = MagicMock()
        mock_record.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.return_value = mock_record
            mock_get_svc.return_value = mock_svc

            _override_actor(client_with_mocked_auth, "admin")
            resp = client_with_mocked_auth.post(
                BASE,
                json={"description": "test backup", "include_uploads": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["backup_id"] == 1

    def test_with_password(self, client_with_mocked_auth):
        mock_record = MagicMock()
        mock_record.backup_id = 2
        mock_record.file_name = "encrypted.zip"
        mock_record.file_path = "/backups/encrypted.zip"
        mock_record.file_size = 2048
        mock_record.description = "加密备份"
        mock_record.created_at = MagicMock()
        mock_record.created_at.isoformat.return_value = "2024-01-02T00:00:00"

        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.return_value = mock_record
            mock_get_svc.return_value = mock_svc

            _override_actor(client_with_mocked_auth, "admin")
            resp = client_with_mocked_auth.post(
                BASE,
                json={"description": "encrypted", "password": "secret123"},
            )
            assert resp.status_code == 200

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.side_effect = RuntimeError("disk full")
            mock_get_svc.return_value = mock_svc
            _override_actor(client_with_mocked_auth, "admin")
            resp = client_with_mocked_auth.post(BASE, json={})
            assert resp.status_code == 500

    def test_regular_user_cannot_create(self, client_with_regular_user_auth):
        # 端点经 _authenticate_backup_request → get_current_user 解析身份，
        # 此处 patch 模块级 get_current_user 返回普通用户，验证 require_admin 拦截
        regular = MagicMock()
        regular.role = "user"
        regular.is_superuser = False
        regular.username = "user"
        with patch("app.core.security.get_current_user", return_value=regular):
            resp = client_with_regular_user_auth.post(
                BASE, json={}, headers={"Authorization": "Bearer fake-token"}
            )
        assert resp.status_code == 403


# ── list_backups ─────────────────────────────────────────────────────

class TestListBackups:
    def test_success(self, client_with_mocked_auth):
        mock_record = MagicMock()
        mock_record.backup_id = 1
        mock_record.file_name = "b.zip"
        mock_record.file_path = "/backups/b.zip"
        mock_record.file_size = 512
        mock_record.description = "test"
        mock_record.created_at = MagicMock()
        mock_record.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        mock_record.backup_type = "full"

        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.return_value = [mock_record]
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["total"] == 1
            assert data["data"]["items"][0]["file_name"] == "b.zip"

    def test_empty(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.return_value = []
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 200
            assert resp.json()["data"]["total"] == 0

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.side_effect = RuntimeError("fail")
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 500


# ── get_backup_stats ─────────────────────────────────────────────────

class TestGetBackupStats:
    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.get_backup_statistics.return_value = {
                "total_backups": 5, "total_size": 10000, "total_size_mb": 10,
                "full_backups": 3, "incremental_backups": 2,
                "newest_backup": "2024-01-01", "oldest_backup": "2023-12-01",
            }
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/stats")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["totalBackups"] == 5
            assert data["scheduleEnabled"] is False
            assert data["totalSizeMb"] == 10

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.get_backup_statistics.side_effect = RuntimeError("fail")
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/stats")
            assert resp.status_code == 500


# ── get / update backup schedule ─────────────────────────────────────

class TestGetBackupSchedule:
    def test_default_enabled_true(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/schedule")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["enabled"] is True
        assert "禁用" not in data["message"]


class TestUpdateBackupSchedule:
    def test_update_writes_config(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.put(
            f"{BASE}/schedule",
            json={"enabled": True, "keep_count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["enabled"] is True
        assert data["keepCount"] == 5


# ── delete_backup ────────────────────────────────────────────────────

class TestDeleteBackup:
    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.return_value = []
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.delete(f"{BASE}/nonexistent.zip")
            assert resp.status_code == 404

    def test_success(self, client_with_mocked_auth):
        mock_record = MagicMock()
        mock_record.file_name = "test.zip"
        mock_record.backup_id = 1

        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.return_value = [mock_record]
            mock_svc.delete_backup.return_value = True
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.delete(f"{BASE}/test.zip")
            assert resp.status_code == 200
            assert "已删除" in resp.json()["message"]

    def test_delete_fails(self, client_with_mocked_auth):
        mock_record = MagicMock()
        mock_record.file_name = "bad.zip"
        mock_record.backup_id = 1

        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.return_value = [mock_record]
            mock_svc.delete_backup.return_value = False
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.delete(f"{BASE}/bad.zip")
            assert resp.status_code == 500

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.list_backups.side_effect = RuntimeError("fail")
            mock_get_svc.return_value = mock_svc
            resp = client_with_mocked_auth.delete(f"{BASE}/x.zip")
            assert resp.status_code == 500

    def test_regular_user_cannot_delete(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.delete(f"{BASE}/x.zip")
        assert resp.status_code == 403


# ── download_backup ──────────────────────────────────────────────────

class TestDownloadBackup:
    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.os.path.exists", return_value=False):
            resp = client_with_mocked_auth.get(f"{BASE}/download/missing.zip")
            assert resp.status_code == 404

    def test_path_traversal_blocked(self, client_with_mocked_auth):
        with (
            patch("app.api.v1.system.backup.os.path.exists", return_value=True),
            patch("app.api.v1.system.backup.os.path.realpath") as mock_realpath,
            patch("app.utils.paths.get_backup_path") as mock_path,
        ):
            mock_path.return_value = "/safe/backups"
            mock_realpath.side_effect = lambda p: "/safe/backups" if p == "/safe/backups" else "/evil/path"
            resp = client_with_mocked_auth.get(f"{BASE}/download/hack.zip")
            assert resp.status_code == 403

    def test_success(self, client_with_mocked_auth, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        backup_file = backup_dir / "test_backup.zip"
        backup_file.write_text("fake zip content")

        with patch("app.api.v1.system.backup.os.path.exists", return_value=True):
            with patch("app.api.v1.system.backup.os.path.realpath") as mock_realpath:
                mock_realpath.side_effect = lambda p: str(p)
                with patch("app.utils.paths.get_backup_path") as mock_path:
                    mock_path.return_value = backup_dir
                    resp = client_with_mocked_auth.get(f"{BASE}/download/test_backup.zip")
                    assert resp.status_code == 200


# ── restore_backup ───────────────────────────────────────────────────

class TestRestoreBackup:
    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.os.path.exists", return_value=False):
            resp = client_with_mocked_auth.post(
                f"{BASE}/restore",
                json={"filename": "missing.zip"},
            )
            assert resp.status_code == 404

    def test_value_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.os.path.exists", return_value=True):
            with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
                mock_svc = MagicMock()
                mock_svc.restore_backup.side_effect = ValueError("bad backup")
                mock_get_svc.return_value = mock_svc
                with patch("app.utils.paths.get_backup_path") as mock_path:
                    mock_path.return_value = "/backups"
                    resp = client_with_mocked_auth.post(
                        f"{BASE}/restore",
                        json={"filename": "bad.zip"},
                    )
                    assert resp.status_code == 400

    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.os.path.exists", return_value=True):
            with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
                mock_svc = MagicMock()
                mock_svc.restore_backup.return_value = {"restored": True}
                mock_get_svc.return_value = mock_svc
                with patch("app.utils.paths.get_backup_path") as mock_path:
                    mock_path.return_value = "/backups"
                    resp = client_with_mocked_auth.post(
                        f"{BASE}/restore",
                        json={"filename": "good.zip"},
                    )
                    assert resp.status_code == 200
                    assert resp.json()["success"] is True

    def test_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.backup.os.path.exists", return_value=True):
            with patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
                mock_svc = MagicMock()
                mock_svc.restore_backup.side_effect = RuntimeError("fail")
                mock_get_svc.return_value = mock_svc
                with patch("app.utils.paths.get_backup_path") as mock_path:
                    mock_path.return_value = "/backups"
                    resp = client_with_mocked_auth.post(
                        f"{BASE}/restore",
                        json={"filename": "err.zip"},
                    )
                    assert resp.status_code == 500

    def test_regular_user_cannot_restore(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.post(
            f"{BASE}/restore", json={"filename": "x.zip"},
        )
        assert resp.status_code == 403
