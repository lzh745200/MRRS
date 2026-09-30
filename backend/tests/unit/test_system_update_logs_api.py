"""
Tests for update_logs.py — system update logs API.
"""

from unittest.mock import MagicMock, patch

BASE = "/api/v1/system/update-logs"


class TestGetUpdateLogs:
    def test_returns_paginated(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_update_logs.return_value = []
        mock_svc.get_update_count.return_value = 0
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(BASE)
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_filter_by_version(self, client_with_mocked_auth):
        rec = MagicMock()
        rec.to_dict.return_value = {"version": "1.0.0"}
        mock_svc = MagicMock()
        mock_svc.get_update_by_version.return_value = rec
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}?version=1.0.0")
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 1

    def test_requires_auth(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 401


class TestGetLatest:
    def test_with_records(self, client_with_mocked_auth):
        rec = MagicMock()
        rec.to_dict.return_value = {"version": "1.0.0"}
        mock_svc = MagicMock()
        mock_svc.get_latest_update.return_value = rec
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/latest")
        assert resp.status_code == 200
        assert resp.json()["data"]["version"] == "1.0.0"

    def test_no_records(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_latest_update.return_value = None
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/latest")
        assert resp.status_code == 200
        assert resp.json()["data"]["has_records"] is False


class TestGetDetail:
    def test_found(self, client_with_mocked_auth):
        from app.core.database import get_db
        rec = MagicMock()
        rec.to_dict.return_value = {"id": "1", "version": "1.0.0"}
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = rec
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        with patch("app.api.v1.system.update_logs.UpdateLogService"):
            resp = client_with_mocked_auth.get(f"{BASE}/1")
        assert resp.status_code == 200

    def test_not_found(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        original_overrides = client_with_mocked_auth.app.dependency_overrides.copy()
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        with patch("app.api.v1.system.update_logs.UpdateLogService"):
            resp = client_with_mocked_auth.get(f"{BASE}/999")
        client_with_mocked_auth.app.dependency_overrides = original_overrides
        assert resp.status_code == 404


class TestCreate:
    def test_success(self, client_with_mocked_auth):
        rec = MagicMock()
        rec.to_dict.return_value = {"version": "1.1.0"}
        mock_svc = MagicMock()
        mock_svc.record_update.return_value = rec
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                BASE, json={"version": "1.1.0", "description": "Bug fixes"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_requires_auth(self, client):
        resp = client.post(
            BASE, json={"version": "1.1.0", "description": "test"},
        )
        assert resp.status_code == 401


class TestDelete:
    def test_success(self, client_with_mocked_auth):
        from app.core.database import get_db
        rec = MagicMock()
        rec.version = "1.0.0"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = rec
        original_overrides = client_with_mocked_auth.app.dependency_overrides.copy()
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        resp = client_with_mocked_auth.delete(f"{BASE}/1")
        client_with_mocked_auth.app.dependency_overrides = original_overrides
        assert resp.status_code == 200

    def test_not_found(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        original_overrides = client_with_mocked_auth.app.dependency_overrides.copy()
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        resp = client_with_mocked_auth.delete(f"{BASE}/999")
        client_with_mocked_auth.app.dependency_overrides = original_overrides
        assert resp.status_code == 404


class TestDeleteRealSession:
    """删除端点走真实 SQLite 会话（含 commit 后的实例状态）。

    深审 #91 声称"db.delete + commit 后再读 record.version → ObjectDeletedError
    （500）"。实测 SQLAlchemy 2.0.50 + expire_on_commit=True：被删除实例在 commit
    时被 expunge、属性保持已加载，读取不会抛错，故该 500 不可复现（误报）。
    用例保留为删除路径的行为锁定：真库下必须 200 且版本号可用于审计日志。
    """

    def test_delete_returns_200_and_row_gone(self, client_with_mocked_auth, caplog):
        import logging

        from app.core.database import get_db
        from app.models.base import Base
        from app.models.system_config import SystemUpdateLog
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        session.add(SystemUpdateLog(id="v1", version="1.0.0", description="首个版本"))
        session.commit()

        client = client_with_mocked_auth
        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_db] = lambda: session
        try:
            with caplog.at_level(logging.INFO, logger="app.api.v1.system.update_logs"):
                resp = client.delete(f"{BASE}/v1")
        finally:
            client.app.dependency_overrides = original
        assert resp.status_code == 200
        assert session.query(SystemUpdateLog).count() == 0
        assert "1.0.0" in caplog.text
        session.close()
        engine.dispose()


class TestCheckVersion:
    def test_changed(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.check_and_record_version_change.return_value = {"version": "1.1.0"}
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/check/version")
        assert resp.status_code == 200
        assert "已记录" in resp.json()["message"]

    def test_unchanged(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.check_and_record_version_change.return_value = None
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/check/version")
        assert resp.status_code == 200
        assert "未变更" in resp.json()["message"]

    def test_exception_reports_failure(self, client_with_mocked_auth):
        """深审 LIVE：异常时曾返回 success:True 且回显 str(e)，调用方无法区分失败。"""
        mock_svc = MagicMock()
        mock_svc.check_and_record_version_change.side_effect = RuntimeError("oops")
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/check/version")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "失败" in body["message"]
        assert "oops" not in resp.text  # 不外泄内部异常文本
        assert "check_error" not in body["data"]
        assert body["data"]["current_version"]


class TestInitialize:
    def test_success(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.initialize_version_history.return_value = {"message": "done"}
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(f"{BASE}/initialize", json={})
        assert resp.status_code == 200

    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/initialize", json={})
        assert resp.status_code == 401


class TestSync:
    def test_success(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.sync_version_history.return_value = {"message": "synced"}
        with patch("app.api.v1.system.update_logs.UpdateLogService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(f"{BASE}/sync")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
