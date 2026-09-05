import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from io import BytesIO
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_settings():
    import os
    os.environ["SECRET_KEY"] = "test-secret-key-32-chars-long!!!!!"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    os.environ["CSRF_ENABLED"] = "false"
    from app.core.config import settings
    settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
    settings.ENVIRONMENT = "testing"
    settings.DEBUG = True
    settings.DATABASE_URL = "sqlite:///./test.db"
    settings.CSRF_ENABLED = False
    yield
    for k in ["SECRET_KEY", "ENVIRONMENT", "DEBUG", "DATABASE_URL", "CSRF_ENABLED"]:
        os.environ.pop(k, None)


@pytest.fixture
def client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db

    _mock_user = Mock(id=1, username="admin", role="admin", is_superuser=True, is_active=True,
                      permissions_list=["*"], organization_id=1, email="admin@test.com")
    app.dependency_overrides[get_current_user] = lambda: _mock_user

    yield TestClient(app, raise_server_exceptions=False), db

    app.dependency_overrides = _original_overrides
    db.close()
    engine.dispose()


class TestExportData:
    URL = "/api/v1/data-sync/export"

    def test_success(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_incremental = AsyncMock(return_value={"success": True, "package_name": "export.zip"})
            resp = test_client.post(self.URL)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_with_since(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_incremental = AsyncMock(return_value={"success": True})
            resp = test_client.post(self.URL + "?since=2024-01-01T00:00:00")
        assert resp.status_code == 200

    def test_with_modules_and_include_files(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_incremental = AsyncMock(return_value={"success": True})
            resp = test_client.post(self.URL + "?modules=village,population&include_files=true")
        assert resp.status_code == 200

    def test_invalid_since_format(self, client):
        test_client, db = client
        resp = test_client.post(self.URL + "?since=not-a-date")
        assert resp.status_code == 400

    def test_exception(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_incremental = AsyncMock(side_effect=RuntimeError("export failed"))
            resp = test_client.post(self.URL)
        assert resp.status_code == 400
        assert "失败" in resp.json()["message"]


class TestExportEncrypted:
    URL = "/api/v1/data-sync/export-encrypted"

    def test_success(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_encrypted = AsyncMock(return_value={"success": True, "package_name": "enc.rrs"})
            resp = test_client.post(self.URL, json={"password": "secret123", "export_type": "full"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_selective_with_modules(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_encrypted = AsyncMock(return_value={"success": True})
            resp = test_client.post(self.URL, json={
                "password": "secret123", "export_type": "selective", "modules": ["village"]
            })
        assert resp.status_code == 200

    def test_with_since(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_encrypted = AsyncMock(return_value={"success": True})
            resp = test_client.post(self.URL, json={
                "password": "pw", "export_type": "full", "since": "2024-06-01T00:00:00"
            })
        assert resp.status_code == 200

    def test_invalid_export_type(self, client):
        test_client, db = client
        resp = test_client.post(self.URL, json={"password": "pw", "export_type": "invalid"})
        assert resp.status_code == 400

    def test_invalid_since_format(self, client):
        test_client, db = client
        resp = test_client.post(self.URL, json={
            "password": "pw", "export_type": "full", "since": "bad-date"
        })
        assert resp.status_code == 400

    def test_exception(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.export_encrypted = AsyncMock(side_effect=RuntimeError("enc export failed"))
            resp = test_client.post(self.URL, json={"password": "pw", "export_type": "full"})
        assert resp.status_code == 400
        assert "失败" in resp.json()["message"]


class TestDownloadExport:
    URL = "/api/v1/data-sync/export/download"

    def test_invalid_package_name(self, client):
        test_client, db = client
        resp = test_client.get(self.URL + "/invalid<package>")
        assert resp.status_code == 400

    def _bind_sync_dir(self, monkeypatch, tmp_path):
        """把端点与服务的 sync_dir 一起指到 tmp_path（路径同源接缝）。

        2026-09-05 前：下载端点用相对 Path("data_sync")，测试以 monkeypatch.chdir
        绑定；端点改用 data_sync_service.sync_dir 后必须 patch 同一属性。
        """
        from app.services.data_sync_service import data_sync_service

        sync_dir = tmp_path / "data_sync"
        sync_dir.mkdir(parents=True)
        monkeypatch.setattr(data_sync_service, "sync_dir", sync_dir)
        return sync_dir

    def test_not_found(self, client, tmp_path, monkeypatch):
        test_client, db = client
        self._bind_sync_dir(monkeypatch, tmp_path)
        resp = test_client.get(self.URL + "/nonexistent")
        assert resp.status_code == 400
        assert "失败" in resp.json()["message"]

    def test_download_zip(self, client, tmp_path, monkeypatch):
        test_client, db = client
        sync_dir = self._bind_sync_dir(monkeypatch, tmp_path)
        (sync_dir / "test_package.zip").write_bytes(b"zip content")
        resp = test_client.get(self.URL + "/test_package")
        assert resp.status_code == 200
        assert resp.content == b"zip content"

    def test_download_rrs(self, client, tmp_path, monkeypatch):
        test_client, db = client
        sync_dir = self._bind_sync_dir(monkeypatch, tmp_path)
        (sync_dir / "test_package.rrs").write_bytes(b"rrs content")
        resp = test_client.get(self.URL + "/test_package")
        assert resp.status_code == 200
        assert resp.content == b"rrs content"

    def test_path_traversal(self, client, tmp_path, monkeypatch):
        test_client, db = client
        monkeypatch.chdir(tmp_path)
        sync_dir = tmp_path / "data_sync"
        sync_dir.mkdir(parents=True)
        outside = tmp_path / "outside" / "test.zip"
        outside.parent.mkdir(parents=True)
        outside.write_bytes(b"evil")

        orig_resolve = Path.resolve
        def mock_resolve(self):
            if "test_package" in str(self):
                return outside
            return orig_resolve(self)
        monkeypatch.setattr(Path, "resolve", mock_resolve)

        resp = test_client.get(self.URL + "/test_package")
        assert resp.status_code == 400

    def test_exception(self, client, tmp_path, monkeypatch):
        test_client, db = client
        monkeypatch.chdir(tmp_path)

        orig_resolve = Path.resolve
        def bad_resolve(self):
            raise PermissionError("access denied")
        monkeypatch.setattr(Path, "resolve", bad_resolve)

        resp = test_client.get(self.URL + "/test_package")
        assert resp.status_code == 400


class TestImportData:
    URL = "/api/v1/data-sync/import"

    @patch("app.api.v1.data_sync._save_upload_file", new_callable=AsyncMock)
    def test_success(self, mock_save, client):
        mock_save.return_value = Path("/tmp/test.zip")
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.import_package = AsyncMock(return_value={"success": True})
            resp = test_client.post(self.URL, files={"file": ("test.zip", BytesIO(b"zip data"))}, data={"strategy": "skip"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_bad_extension(self, client):
        test_client, db = client
        resp = test_client.post(self.URL, files={"file": ("test.exe", BytesIO(b"evil"))}, data={"strategy": "skip"})
        assert resp.status_code == 400

    @patch("app.api.v1.data_sync._save_upload_file", new_callable=AsyncMock)
    def test_exception(self, mock_save, client):
        mock_save.return_value = Path("/tmp/test.zip")
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.import_package = AsyncMock(side_effect=RuntimeError("import failed"))
            resp = test_client.post(self.URL, files={"file": ("test.zip", BytesIO(b"zip data"))}, data={"strategy": "skip"})
        assert resp.status_code == 400
        assert "失败" in resp.json()["message"]


class TestImportEncrypted:
    URL = "/api/v1/data-sync/import-encrypted"

    @patch("app.api.v1.data_sync._save_upload_file", new_callable=AsyncMock)
    def test_success(self, mock_save, client):
        mock_save.return_value = Path("/tmp/test.rrs")
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.import_encrypted = AsyncMock(return_value={"success": True})
            resp = test_client.post(
                self.URL,
                files={"file": ("test.rrs", BytesIO(b"rrs data"))},
                data={"password": "secret123", "strategy": "merge"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_bad_extension(self, client):
        test_client, db = client
        resp = test_client.post(
            self.URL,
            files={"file": ("test.exe", BytesIO(b"evil"))},
            data={"password": "pw", "strategy": "merge"},
        )
        assert resp.status_code == 400

    @patch("app.api.v1.data_sync._save_upload_file", new_callable=AsyncMock)
    def test_exception(self, mock_save, client):
        mock_save.return_value = Path("/tmp/test.rrs")
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.import_encrypted = AsyncMock(side_effect=RuntimeError("import enc failed"))
            resp = test_client.post(
                self.URL,
                files={"file": ("test.rrs", BytesIO(b"rrs data"))},
                data={"password": "pw", "strategy": "merge"},
            )
        assert resp.status_code == 400
        assert "失败" in resp.json()["message"]


class TestGetConflicts:
    URL = "/api/v1/data-sync/conflicts"

    def test_success(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.get_conflicts = AsyncMock(return_value=[{"id": 1, "field": "name"}])
            resp = test_client.get(self.URL + "/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["count"] == 1

    def test_empty(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.get_conflicts = AsyncMock(return_value=[])
            resp = test_client.get(self.URL + "/99")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_exception(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.get_conflicts = AsyncMock(side_effect=RuntimeError("failed"))
            resp = test_client.get(self.URL + "/1")
        assert resp.status_code == 400


class TestResolveConflict:
    URL = "/api/v1/data-sync/resolve-conflict"

    def test_success_local(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.resolve_conflict = AsyncMock(return_value={"success": True, "resolution": "use_local"})
            resp = test_client.post(self.URL + "?conflict_id=1&resolution=use_local")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_success_remote(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.resolve_conflict = AsyncMock(return_value={"success": True, "resolution": "use_remote"})
            resp = test_client.post(self.URL + "?conflict_id=2&resolution=use_remote")
        assert resp.status_code == 200

    def test_success_merge(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.resolve_conflict = AsyncMock(return_value={"success": True, "resolution": "merge"})
            resp = test_client.post(self.URL + "?conflict_id=3&resolution=merge")
        assert resp.status_code == 200

    def test_exception(self, client):
        test_client, db = client
        with patch("app.api.v1.data_sync.data_sync_service", new_callable=AsyncMock) as mock_svc:
            mock_svc.resolve_conflict = AsyncMock(side_effect=RuntimeError("resolve failed"))
            resp = test_client.post(self.URL + "?conflict_id=1&resolution=use_local")
        assert resp.status_code == 400


class TestGetSyncLogs:
    URL = "/api/v1/data-sync/logs"

    def _gen_mock_db(self):
        mock_db = MagicMock()
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.sync_type = "export"
        mock_log.status = "success"
        mock_log.package_name = "test.zip"
        mock_log.total_records = 10
        mock_log.success_records = 10
        mock_log.failed_records = 0
        mock_log.conflicts_count = 0
        mock_log.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        mock_log.completed_at = None
        mock_log.user_name = "admin"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_log]
        mock_db.query.return_value = mock_query
        return mock_db

    def test_success_without_filter(self, client):
        test_client, db = client
        mock_db = self._gen_mock_db()

        with patch("app.core.database.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            resp = test_client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert body["data"]["items"][0]["sync_type"] == "export"

    def test_success_with_filter(self, client):
        test_client, db = client
        mock_db = self._gen_mock_db()

        with patch("app.core.database.get_db") as mock_get_db:
            mock_get_db.return_value = iter([mock_db])
            resp = test_client.get(self.URL + "?sync_type=import")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_exception(self, client):
        test_client, db = client
        with patch("app.core.database.get_db") as mock_get_db:
            mock_get_db.side_effect = RuntimeError("db error")
            resp = test_client.get(self.URL)
        assert resp.status_code == 400
