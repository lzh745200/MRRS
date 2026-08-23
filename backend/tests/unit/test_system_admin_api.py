"""
Tests for app.api.v1.system.admin — 100% coverage
"""

from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from fastapi import HTTPException


# Patch require_admin to be callable with (user, error_message=...) pattern
@pytest.fixture(autouse=True)
def patch_require_admin():
    with patch("app.api.v1.system.admin.require_admin") as mock_ra:
        def side_effect(user, error_message="Access denied"):
            if not hasattr(user, "role") or user.role not in ("admin", "super_admin"):
                raise HTTPException(status_code=403, detail=error_message)
            return None
        mock_ra.side_effect = side_effect
        yield


@pytest.fixture
def auth_client(client):
    from app.core.security import get_current_user
    user = MagicMock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.organization_id = 1
    user.email = "admin@test.com"
    user.full_name = "Admin"
    user.permissions_list = ["*"]
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def regular_client(client):
    from app.core.security import get_current_user
    user = MagicMock()
    user.id = 2
    user.username = "user"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.organization_id = 2
    user.permissions_list = ["read"]
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides.pop(get_current_user, None)


class TestGetSystemInfo:
    def _fix_query_count(self, mock_db):
        original_query = mock_db.query
        def fixed_query(model):
            q = original_query(model)
            q.count.return_value = len(mock_db._storage.get(model, []))
            return q
        mock_db.query = fixed_query

    def test_success(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        from app.models.user import User
        from app.models.organization import Organization
        from app.models.project import Project
        from app.models.village import Village

        mock_db._storage = {
            User: [MagicMock(id=1)],
            Organization: [MagicMock(id=1)],
            Project: [MagicMock(id=1)],
            Village: [MagicMock(id=1)],
        }
        self._fix_query_count(mock_db)

        with patch("app.api.v1.system.admin.get_database_path") as gdp:
            p = MagicMock(spec=Path)
            p.exists.return_value = True
            p.stat.return_value.st_size = 1024
            gdp.return_value = p
            resp = auth_client.get("/api/v1/system/admin/info")
            assert resp.status_code == 200
            data = resp.json()
            assert data["version"] is not None
            assert data["database_size"] == 1024

    def test_no_db_file(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db
        from app.models.user import User
        mock_db._storage = {User: []}
        self._fix_query_count(mock_db)
        with patch("app.api.v1.system.admin.get_database_path") as gdp:
            p = MagicMock(spec=Path)
            p.exists.return_value = False
            gdp.return_value = p
            resp = auth_client.get("/api/v1/system/admin/info")
            assert resp.status_code == 200
            assert resp.json()["database_size"] == 0


class TestCreateBackup:
    def test_success(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir, \
             patch("shutil.copy2") as copy2:
            db_p = MagicMock(spec=Path); db_p.exists.return_value = True
            bk_dir = MagicMock(spec=Path)
            bk_file = MagicMock(spec=Path)
            bk_file.stat.return_value.st_size = 512
            bk_dir.__truediv__.return_value = bk_file
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/backup")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["size"] == 512

    def test_file_not_found(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir, \
             patch("shutil.copy2", side_effect=FileNotFoundError):
            db_p = MagicMock(spec=Path); db_p.exists.return_value = True
            bk_dir = MagicMock(spec=Path)
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/backup")
            assert resp.status_code == 500
            assert "备份失败" in resp.json()["detail"]

    def test_general_exception(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            db_p = MagicMock(spec=Path); db_p.exists.return_value = True
            bk_dir = MagicMock(spec=Path)
            bk_dir.mkdir.side_effect = PermissionError("access denied")
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/backup")
            assert resp.status_code == 500
            assert "备份失败" in resp.json()["detail"]


class TestListBackups:
    def test_success(self, auth_client):
        with patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            bk_dir = MagicMock(spec=Path)
            bk_dir.exists.return_value = True

            f1 = MagicMock(spec=Path)
            f1.name = "backup_20240101_120000.db"
            f1.stat.return_value.st_size = 100
            f1.stat.return_value.st_mtime = 1704100000.0

            f2 = MagicMock(spec=Path)
            f2.name = "backup_20240102_120000.db"
            f2.stat.return_value.st_size = 200
            f2.stat.return_value.st_mtime = 1704186400.0

            bk_dir.glob.return_value = [f1, f2]
            gbdir.return_value = bk_dir

            resp = auth_client.get("/api/v1/system/admin/backups")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["total"] == 2

    def test_no_backup_dir(self, auth_client):
        with patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            bk_dir = MagicMock(spec=Path)
            bk_dir.exists.return_value = False
            gbdir.return_value = bk_dir

            resp = auth_client.get("/api/v1/system/admin/backups")
            assert resp.status_code == 200
            assert resp.json()["data"]["total"] == 0


class TestRestoreBackup:
    def test_success(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir, \
             patch("shutil.copy2") as copy2:
            db_p = MagicMock(spec=Path)
            db_p.exists.return_value = True
            db_p.parent = MagicMock()
            db_p.stem = "rural_revitalization"
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/backups/backup_2024.db")
            bk_dir.__truediv__.return_value = bk_file
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/restore?filename=backup_2024.db")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_path_traversal(self, auth_client):
        resp = auth_client.post("/api/v1/system/admin/restore?filename=../etc/passwd")
        assert resp.status_code == 400
        assert "无效的文件名" in resp.json()["detail"]

    def test_path_traversal_slash(self, auth_client):
        resp = auth_client.post("/api/v1/system/admin/restore?filename=sub/dir/file.db")
        assert resp.status_code == 400

    def test_path_traversal_backslash(self, auth_client):
        resp = auth_client.post("/api/v1/system/admin/restore?filename=sub\\dir\\file.db")
        assert resp.status_code == 400

    def test_path_traversal_dot(self, auth_client):
        resp = auth_client.post("/api/v1/system/admin/restore?filename=.hidden.db")
        assert resp.status_code == 400

    def test_realpath_check_fail(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            db_p = MagicMock(spec=Path)
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/outside/something.db")
            bk_dir.__truediv__.return_value = bk_file
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/restore?filename=something.db")
            assert resp.status_code == 500
            assert "恢复失败" in resp.json()["detail"]

    def test_backup_not_found(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir, \
             patch("shutil.copy2", side_effect=FileNotFoundError):
            db_p = MagicMock(spec=Path)
            db_p.exists.return_value = False
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/backups/bk.db")
            bk_dir.__truediv__.return_value = bk_file
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/restore?filename=bk.db")
            assert resp.status_code == 500
            assert "恢复失败" in resp.json()["detail"]

    def test_general_exception(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.system.admin.get_database_path") as gdp, \
             patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            db_p = MagicMock(spec=Path)
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.side_effect = PermissionError("blocked")
            bk_dir.__truediv__.return_value = bk_file
            gdp.return_value = db_p
            gbdir.return_value = bk_dir

            resp = auth_client.post("/api/v1/system/admin/restore?filename=bk.db")
            assert resp.status_code == 500
            assert "恢复失败" in resp.json()["detail"]


class TestDeleteBackup:
    def test_success(self, auth_client):
        with patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/backups/bk.db")
            bk_dir.__truediv__.return_value = bk_file
            gbdir.return_value = bk_dir

            resp = auth_client.delete("/api/v1/system/admin/backups/bk.db")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_path_traversal(self, auth_client):
        resp = auth_client.delete("/api/v1/system/admin/backups/..%2Fetc%2Fpasswd")
        assert resp.status_code in (400, 404, 405)

    def test_path_traversal_dots(self, auth_client):
        resp = auth_client.delete("/api/v1/system/admin/backups/test..db")
        assert resp.status_code == 400

    def test_hidden_file(self, auth_client):
        resp = auth_client.delete("/api/v1/system/admin/backups/.hidden.db")
        assert resp.status_code == 400

    def test_realpath_fail(self, auth_client):
        with patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/outside/bk.db")
            bk_dir.__truediv__.return_value = bk_file
            gbdir.return_value = bk_dir

            resp = auth_client.delete("/api/v1/system/admin/backups/bk.db")
            assert resp.status_code == 400

    def test_not_found(self, auth_client):
        with patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/backups/bk.db")
            bk_file.unlink.side_effect = FileNotFoundError
            bk_dir.__truediv__.return_value = bk_file
            gbdir.return_value = bk_dir

            resp = auth_client.delete("/api/v1/system/admin/backups/bk.db")
            assert resp.status_code == 404
            assert "备份文件不存在" in resp.json()["detail"]

    def test_general_error(self, auth_client):
        with patch("app.api.v1.system.admin.get_backup_directory") as gbdir:
            bk_dir = MagicMock(spec=Path)
            bk_dir.resolve.return_value = Path("C:/backups")
            bk_file = MagicMock(spec=Path)
            bk_file.resolve.return_value = Path("C:/backups/bk.db")
            bk_file.unlink.side_effect = PermissionError("denied")
            bk_dir.__truediv__.return_value = bk_file
            gbdir.return_value = bk_dir

            resp = auth_client.delete("/api/v1/system/admin/backups/bk.db")
            assert resp.status_code == 500


class TestSystemConfig:
    def test_get_config(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.services.system_config_service.SystemConfigService") as MockSvc:
            svc = MagicMock()
            svc.get.side_effect = lambda k, d: {"system_name": "Test", "max_login_attempts": "5",
                "session_timeout": "480", "password_expiry_days": "90"}.get(k, d)
            MockSvc.return_value = svc

            resp = auth_client.get("/api/v1/system/admin/config")
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_update_config(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.services.system_config_service.SystemConfigService") as MockSvc:
            svc = MagicMock()
            MockSvc.return_value = svc

            payload = {
                "system_name": "NewName",
                "max_login_attempts": 3,
                "session_timeout": 600,
                "password_expiry_days": 30,
            }
            resp = auth_client.put("/api/v1/system/admin/config", json=payload)
            assert resp.status_code == 200
            assert svc.set.call_count == 4

    def test_update_partial(self, auth_client, mock_db):
        from app.core.database import get_db
        auth_client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.services.system_config_service.SystemConfigService") as MockSvc:
            svc = MagicMock()
            MockSvc.return_value = svc

            resp = auth_client.put("/api/v1/system/admin/config", json={"system_name": "OnlyName"})
            assert resp.status_code == 200
            svc.set.assert_called_once_with("system_name", "OnlyName", "系统名称")


class TestClearCache:
    def test_success(self, auth_client):
        with patch("app.core.cache.cache_manager") as cm:
            resp = auth_client.post("/api/v1/system/admin/clear-cache")
            assert resp.status_code == 200
            cm.clear.assert_called_once()

    def test_with_dashboard_and_map_cache(self, auth_client):
        fake_dashboard = MagicMock()
        fake_dashboard.invalidate_dashboard_cache = MagicMock()
        fake_map = MagicMock()
        fake_map.invalidate_map_cache = MagicMock()

        with patch("app.core.cache.cache_manager") as cm, \
             patch.dict("sys.modules", {
                 "app.api.v1.data.data.dashboard": fake_dashboard,
                 "app.api.v1.map": fake_map,
             }):
            resp = auth_client.post("/api/v1/system/admin/clear-cache")
            assert resp.status_code == 200
            fake_dashboard.invalidate_dashboard_cache.assert_called_once()
            fake_map.invalidate_map_cache.assert_called_once()

    def test_invalidate_map_cache_failure(self, auth_client):
        fake_dashboard = MagicMock()
        fake_dashboard.invalidate_dashboard_cache = MagicMock()
        fake_map = MagicMock()
        fake_map.invalidate_map_cache = MagicMock(side_effect=Exception("map error"))

        with patch("app.core.cache.cache_manager") as cm, \
             patch.dict("sys.modules", {
                 "app.api.v1.data.data.dashboard": fake_dashboard,
                 "app.api.v1.map": fake_map,
             }):
            resp = auth_client.post("/api/v1/system/admin/clear-cache")
            assert resp.status_code == 200
            fake_dashboard.invalidate_dashboard_cache.assert_called_once()
            fake_map.invalidate_map_cache.assert_called_once()

    def test_general_exception(self, auth_client):
        with patch("app.core.cache.cache_manager") as cm:
            cm.clear.side_effect = Exception("cache error")
            resp = auth_client.post("/api/v1/system/admin/clear-cache")
            assert resp.status_code == 500
            assert "清理失败" in resp.json()["detail"]


class TestGetSystemLogs:
    def test_success(self, auth_client):
        log_content = "line1\nline2\nline3\n"
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=log_content)):
            resp = auth_client.get("/api/v1/system/admin/logs?page=1&page_size=50")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["total"] == 3

    def test_no_log_file(self, auth_client):
        with patch("pathlib.Path.exists", return_value=False):
            resp = auth_client.get("/api/v1/system/admin/logs")
            assert resp.status_code == 200
            assert resp.json()["data"]["total"] == 0

    def test_read_error(self, auth_client):
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", side_effect=PermissionError("denied")):
            resp = auth_client.get("/api/v1/system/admin/logs")
            assert resp.status_code == 500
            assert "读取日志失败" in resp.json()["detail"]


class TestNonAdminAccess:
    def test_get_info_forbidden(self, regular_client):
        resp = regular_client.get("/api/v1/system/admin/info")
        assert resp.status_code == 403

    def test_create_backup_forbidden(self, regular_client):
        resp = regular_client.post("/api/v1/system/admin/backup")
        assert resp.status_code == 403

    def test_list_backups_forbidden(self, regular_client):
        resp = regular_client.get("/api/v1/system/admin/backups")
        assert resp.status_code == 403

    def test_restore_forbidden(self, regular_client):
        resp = regular_client.post("/api/v1/system/admin/restore?filename=x.db")
        assert resp.status_code == 403

    def test_delete_backup_forbidden(self, regular_client):
        resp = regular_client.delete("/api/v1/system/admin/backups/x.db")
        assert resp.status_code == 403

    def test_get_config_forbidden(self, regular_client):
        resp = regular_client.get("/api/v1/system/admin/config")
        assert resp.status_code == 403

    def test_update_config_forbidden(self, regular_client):
        resp = regular_client.put("/api/v1/system/admin/config", json={})
        assert resp.status_code == 403

    def test_clear_cache_forbidden(self, regular_client):
        resp = regular_client.post("/api/v1/system/admin/clear-cache")
        assert resp.status_code == 403

    def test_get_logs_forbidden(self, regular_client):
        resp = regular_client.get("/api/v1/system/admin/logs")
        assert resp.status_code == 403
