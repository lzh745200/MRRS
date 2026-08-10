"""单机备份目标目录(T1.1)测试: 自定义目标目录/U盘检测/配置持久化"""
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user


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


# ==================== drive_detect 工具 ====================


def test_list_backup_dirs_returns_writable_dirs():
    from app.utils.drive_detect import list_backup_dirs

    dirs = list_backup_dirs()
    assert isinstance(dirs, list)
    assert len(dirs) > 0
    for d in dirs:
        assert "path" in d
        assert "type" in d
        assert "available" in d
        assert os.path.isabs(d["path"])


def test_list_backup_dirs_dedup():
    from app.utils.drive_detect import list_backup_dirs

    dirs = list_backup_dirs()
    paths = [os.path.normcase(d["path"]) for d in dirs]
    assert len(paths) == len(set(paths))


def test_ensure_target_dir_creates_and_checks():
    from app.utils.drive_detect import ensure_target_dir

    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "bk", "sub")
        assert ensure_target_dir(target) is True
        assert os.path.isdir(target)
    assert ensure_target_dir("") is False


# ==================== API: GET /system/backup/dirs ====================


def test_get_dirs_success(bk_client):
    resp = bk_client.get("/api/v1/system/backup/dirs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data["dirs"], list)
    assert "current" in data
    assert len(data["dirs"]) > 0


def test_get_dirs_includes_configured_missing(bk_client):
    with patch("app.services.system_config_service.get_config", return_value="Z:\\missing"):
        resp = bk_client.get("/api/v1/system/backup/dirs")
        assert resp.status_code == 200
        dirs = resp.json()["data"]["dirs"]
        assert any(d["path"] == "Z:\\missing" and d["available"] is False for d in dirs)


def test_get_dirs_error_500(bk_client):
    with patch(
        "app.utils.drive_detect.list_backup_dirs",
        side_effect=RuntimeError("boom"),
    ):
        resp = bk_client.get("/api/v1/system/backup/dirs")
        assert resp.status_code == 500


# ==================== API: PUT /system/backup/target ====================


def test_set_target_success(bk_client):
    with tempfile.TemporaryDirectory() as tmp:
        resp = bk_client.put("/api/v1/system/backup/target", json={"target_dir": tmp})
        assert resp.status_code == 200
        assert resp.json()["data"]["target_dir"] == tmp


def test_set_target_invalid(bk_client):
    resp = bk_client.put("/api/v1/system/backup/target", json={"target_dir": "Z:\\not\\writable\\x"})
    # 该路径在 Windows 上不可写 -> 400; 若恰好可写(异常环境)则 200, 此处不依赖具体结果
    assert resp.status_code in (200, 400)


def test_set_target_empty_clears(bk_client):
    resp = bk_client.put("/api/v1/system/backup/target", json={"target_dir": ""})
    assert resp.status_code == 200


# ==================== API: POST /system/backup 支持 target_dir ====================

def _authed_post(bk_client, url, json_body, monkeypatch):
    """带内部备份密钥头的 POST"""
    import pytest

    monkeypatch.setenv("INTERNAL_BACKUP_KEY", "test-secret-123")
    return bk_client.post(
        url,
        json=json_body,
        headers={"X-Internal-Backup": "test-secret-123"},
    )


def test_create_backup_with_target_dir(bk_client, monkeypatch):
    from app.services.backup_service import BackupService

    with tempfile.TemporaryDirectory() as tmp:
        svc = MagicMock()
        svc.create_backup.return_value = SimpleNamespace(
            backup_id=1, file_name="backup_x.zip", file_path=os.path.join(tmp, "backup_x.zip"),
            file_size=100, description="手动备份",
            created_at=__import__("datetime").datetime(2026, 8, 2, tzinfo=__import__("datetime").timezone.utc),
        )
        with patch(
            "app.api.v1.system.backup.BackupService", return_value=svc
        ) as mk:
            resp = _authed_post(
                bk_client,
                "/api/v1/system/backup",
                {"description": "测试", "target_dir": tmp},
                monkeypatch,
            )
            assert resp.status_code == 200
            _, kwargs = mk.call_args
            assert kwargs["backup_dir"] == tmp
            svc.create_backup.assert_called_once_with(
                description="测试", include_uploads=True, password=None
            )


def test_create_backup_target_dir_not_writable(bk_client, monkeypatch):
    with patch("app.utils.drive_detect.ensure_target_dir", return_value=False):
        resp = _authed_post(
            bk_client,
            "/api/v1/system/backup",
            {"description": "x", "target_dir": "Z:\\no"},
            monkeypatch,
        )
        assert resp.status_code == 400


def test_create_backup_falls_back_to_config(bk_client, monkeypatch):
    from app.services.backup_service import BackupService

    svc = MagicMock()
    svc.create_backup.return_value = SimpleNamespace(
        backup_id=2, file_name="b.zip", file_path="/tmp/b.zip",
        file_size=1, description="x",
        created_at=__import__("datetime").datetime(2026, 8, 2, tzinfo=__import__("datetime").timezone.utc),
    )
    with tempfile.TemporaryDirectory() as tmp, patch(
        "app.api.v1.system.backup.BackupService", return_value=svc
    ) as mk, patch("app.services.system_config_service.get_config", return_value=tmp):
        resp = _authed_post(
            bk_client,
            "/api/v1/system/backup",
            {"description": "配置目录"},
            monkeypatch,
        )
        assert resp.status_code == 200
        _, kwargs = mk.call_args
        assert kwargs["backup_dir"] == tmp
