"""Tests for VersionService — 100% code coverage."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.version_service import VersionService


@pytest.fixture
def service(tmp_path):
    s = VersionService()
    s.base_dir = tmp_path
    s.version_file = tmp_path / "version.json"
    s.history_file = tmp_path / "data" / "version_history.json"
    s.history_file.parent.mkdir(parents=True, exist_ok=True)
    s.current_version = {"version": "1.0.0", "build": "20240101", "release_date": "2024-01-01"}
    return s


# ---------------------------------------------------------------------------
# _load_current_version
# ---------------------------------------------------------------------------


class TestLoadCurrentVersion:
    def test_file_exists(self, service):
        data = {"version": "2.0.0"}
        service.version_file.write_text(json.dumps(data), encoding="utf-8")
        result = service._load_current_version()
        assert result["version"] == "2.0.0"

    def test_file_not_exists_creates_default(self, service):
        assert not service.version_file.exists()
        with patch("app.services.version_service.settings") as mock_set:
            mock_set.PROJECT_VERSION = "3.0.0"
            result = service._load_current_version()
        assert result["version"] == "3.0.0"
        assert service.version_file.exists()

    def test_file_read_exception(self, service):
        service.version_file.write_text("invalid json", encoding="utf-8")
        with patch("app.services.version_service.settings") as mock_set:
            mock_set.PROJECT_VERSION = "x"
            result = service._load_current_version()
        assert result["version"] == "unknown"


# ---------------------------------------------------------------------------
# _save_version
# ---------------------------------------------------------------------------


class TestSaveVersion:
    def test_success(self, service):
        info = {"version": "4.0.0"}
        service._save_version(info)
        saved = json.loads(service.version_file.read_text(encoding="utf-8"))
        assert saved["version"] == "4.0.0"

    def test_exception(self, service):
        with patch("builtins.open", side_effect=Exception("write fail")):
            service._save_version({"version": "x"})  # should not raise


# ---------------------------------------------------------------------------
# _load_history
# ---------------------------------------------------------------------------


class TestLoadHistory:
    def test_file_exists(self, service):
        service.history_file.write_text('[{"action": "upgrade"}]', encoding="utf-8")
        assert service._load_history() == [{"action": "upgrade"}]

    def test_file_not_exists(self, service):
        assert service._load_history() == []

    def test_exception(self, service):
        service.history_file.write_text("bad json", encoding="utf-8")
        assert service._load_history() == []


# ---------------------------------------------------------------------------
# _save_history
# ---------------------------------------------------------------------------


class TestSaveHistory:
    def test_success(self, service):
        service._save_history([{"action": "rollback"}])
        saved = json.loads(service.history_file.read_text(encoding="utf-8"))
        assert saved == [{"action": "rollback"}]

    def test_exception(self, service):
        with patch("builtins.open", side_effect=Exception("write fail")):
            service._save_history([])  # should not raise


# ---------------------------------------------------------------------------
# get_current_version
# ---------------------------------------------------------------------------


def test_get_current_version(service):
    result = service.get_current_version()
    assert result == service.current_version
    result["version"] = "hacked"
    assert service.current_version["version"] != "hacked"


# ---------------------------------------------------------------------------
# get_version_history
# ---------------------------------------------------------------------------


class TestGetVersionHistory:
    def test_returns_last_n_reversed(self, service):
        with patch.object(service, "_load_history", return_value=[
            {"action": "a"}, {"action": "b"}, {"action": "c"},
        ]):
            result = service.get_version_history(limit=2)
        assert result == [{"action": "c"}, {"action": "b"}]


# ---------------------------------------------------------------------------
# check_version_change
# ---------------------------------------------------------------------------


class TestCheckVersionChange:
    def test_changed(self, service):
        service.current_version["version"] = "1.0.0"
        with patch("app.services.version_service.settings") as mock_set:
            mock_set.PROJECT_VERSION = "2.0.0"
            result = service.check_version_change()
        assert result["changed"] is True

    def test_not_changed(self, service):
        service.current_version["version"] = "3.0.0"
        with patch("app.services.version_service.settings") as mock_set:
            mock_set.PROJECT_VERSION = "3.0.0"
            result = service.check_version_change()
        assert result["changed"] is False

    def test_exception(self, service):
        class FailingSettings:
            def __getattr__(self, name):
                raise Exception("boom")
        with patch("app.services.version_service.settings", FailingSettings()):
            result = service.check_version_change()
        assert result is None


# ---------------------------------------------------------------------------
# _record_update_log_sync
# ---------------------------------------------------------------------------


class TestRecordUpdateLogSync:
    def test_success(self, service):
        mock_db = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_db):
            with patch("app.services.update_log_service.UpdateLogService") as mock_upd_cls:
                service._record_update_log_sync("2.0.0", "desc")
        mock_upd_cls.return_value.record_update.assert_called_once_with(
            version="2.0.0", description="desc", updated_by="system",
        )
        mock_db.close.assert_called_once()

    def test_exception_caught(self, service):
        with patch("app.core.database.SessionLocal", side_effect=Exception("db fail")):
            service._record_update_log_sync("2.0.0", "desc")  # should not raise


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


class TestUpgrade:
    def test_success_with_backup(self, service):
        service._run_migrations = MagicMock(return_value={"status": "ok"})
        service._update_config = MagicMock(return_value={"status": "ok"})
        service._load_history = MagicMock(return_value=[])
        service._save_history = MagicMock()
        mock_backup = MagicMock()
        mock_backup.file_path = "/tmp/backup.zip"
        with patch("app.services.backup_service.get_backup_service") as mock_get:
            mock_get.return_value.create_backup.return_value = mock_backup
            result = service.upgrade("2.0.0", "major upgrade")
        assert result["status"] == "success"
        assert result["new_version"] == "2.0.0"
        assert service.current_version["version"] == "2.0.0"

    def test_success_without_backup(self, service):
        service._run_migrations = MagicMock(return_value={"status": "ok"})
        service._update_config = MagicMock(return_value={"status": "ok"})
        service._load_history = MagicMock(return_value=[])
        service._save_history = MagicMock()
        result = service.upgrade("3.0.0", "no backup", backup_before_upgrade=False)
        assert result["status"] == "success"
        assert result["backup_path"] is None

    def test_backup_returns_none(self, service):
        service._run_migrations = MagicMock(return_value={"status": "ok"})
        service._update_config = MagicMock(return_value={"status": "ok"})
        service._load_history = MagicMock(return_value=[])
        service._save_history = MagicMock()
        with patch("app.services.backup_service.get_backup_service") as mock_get:
            mock_get.return_value.create_backup.return_value = None
            result = service.upgrade("4.0.0", "backup fail", backup_before_upgrade=True)
        assert result["status"] == "success"

    def test_exception(self, service):
        # upgrade() 默认 backup_before_upgrade=True，会触发真实的 create_backup
        # （压缩整个数据库/上传目录），在测试环境下导致超时。此处 mock 掉备份服务，
        # 与 test_backup_returns_none 一致，聚焦验证 _save_version 异常的错误处理路径。
        with patch("app.services.backup_service.get_backup_service") as mock_get, \
                patch.object(service, "_save_version", side_effect=Exception("upgrade fail")):
            mock_get.return_value.create_backup.return_value = None
            result = service.upgrade("5.0.0", "fails")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_no_history(self, service):
        service._load_history = MagicMock(return_value=[])
        result = service.rollback()
        assert result["status"] == "error"
        assert "没有可回滚" in result["message"]

    def test_target_not_found(self, service):
        service._load_history = MagicMock(return_value=[{"new_version": "2.0.0"}])
        result = service.rollback(target_version="99.0.0")
        assert result["status"] == "error"
        assert "未找到" in result["message"]

    def test_backup_file_missing(self, service):
        service._load_history = MagicMock(
            return_value=[{"new_version": "2.0.0", "old_version": "1.0.0", "backup_path": "/nonexistent/backup.zip"}]
        )
        result = service.rollback()
        assert result["status"] == "error"
        assert "备份文件" in result["message"]

    def test_restore_error(self, service):
        history = [{"new_version": "2.0.0", "old_version": "1.0.0", "backup_path": str(Path.cwd() / "test_backup.zip")}]
        Path(history[0]["backup_path"]).write_text("x")
        service._load_history = MagicMock(return_value=history)
        service._save_version = MagicMock()
        service._save_history = MagicMock()
        with patch("app.services.backup_service.get_backup_service") as mock_get:
            mock_get.return_value.restore_backup.return_value = {"status": "error", "message": "restore failed"}
            result = service.rollback()
        assert result["status"] == "error"
        Path(history[0]["backup_path"]).unlink()

    def test_success(self, service):
        history = [{"new_version": "2.0.0", "old_version": "1.0.0", "backup_path": str(Path.cwd() / "test_backup2.zip")}]
        Path(history[0]["backup_path"]).write_text("x")
        service._load_history = MagicMock(return_value=history)
        service._save_version = MagicMock()
        service._save_history = MagicMock()
        with patch("app.services.backup_service.get_backup_service") as mock_get:
            mock_get.return_value.restore_backup.return_value = {"success": True}
            result = service.rollback()
        assert result["status"] == "success"
        assert result["new_version"] == "1.0.0"
        Path(history[0]["backup_path"]).unlink()

    def test_target_version_specified_found(self, service):
        backup_path = str(Path.cwd() / "test_target_backup.zip")
        Path(backup_path).write_text("x")
        history = [{"new_version": "1.0.0", "old_version": "0.9.0", "backup_path": "/gone.zip"},
                   {"new_version": "2.0.0", "old_version": "1.0.0", "backup_path": backup_path}]
        service._load_history = MagicMock(return_value=history)
        service._save_version = MagicMock()
        service._save_history = MagicMock()
        with patch("app.services.backup_service.get_backup_service") as mock_get:
            mock_get.return_value.restore_backup.return_value = {"success": True}
            result = service.rollback(target_version="2.0.0")
        assert result["status"] == "success"
        assert result["new_version"] == "2.0.0"
        Path(backup_path).unlink()

    def test_backup_restore_error_raised(self, service):
        from app.services.backup_service import BackupRestoreError
        backup_path = str(Path.cwd() / "test_backup_error.zip")
        Path(backup_path).write_text("x")
        history = [{"new_version": "2.0.0", "old_version": "1.0.0", "backup_path": backup_path}]
        service._load_history = MagicMock(return_value=history)
        service._save_version = MagicMock()
        service._save_history = MagicMock()
        with patch("app.services.backup_service.get_backup_service") as mock_get:
            mock_get.return_value.restore_backup.side_effect = BackupRestoreError("corrupt backup")
            result = service.rollback()
        assert result["status"] == "error"
        assert "corrupt backup" in result["message"]
        Path(backup_path).unlink()

    def test_exception(self, service):
        service._load_history = MagicMock(side_effect=Exception("boom"))
        result = service.rollback()
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# _run_migrations
# ---------------------------------------------------------------------------


class TestRunMigrations:
    def test_success(self, service):
        with patch("app.core.migration_helper.migrate_missing_columns") as mock_migrate:
            result = service._run_migrations("1.0.0", "2.0.0")
        assert result["status"] == "success"

    def test_exception(self, service):
        with patch("app.core.migration_helper.migrate_missing_columns", side_effect=Exception("mig fail")):
            result = service._run_migrations("1.0.0", "2.0.0")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# _update_config
# ---------------------------------------------------------------------------


class TestUpdateConfig:
    def test_success(self, service):
        result = service._update_config("1.0.0", "2.0.0")
        assert result["status"] == "success"

    def test_exception(self, service):
        with patch("app.services.version_service.logger") as mock_log:
            mock_log.info.side_effect = Exception("log fail")
            result = service._update_config("1.0.0", "2.0.0")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# compare_versions
# ---------------------------------------------------------------------------


class TestCompareVersions:
    def test_greater(self, service):
        assert service.compare_versions("2.0.0", "1.9.9") == 1

    def test_less(self, service):
        assert service.compare_versions("1.0.0", "2.0.0") == -1

    def test_equal(self, service):
        assert service.compare_versions("1.0.0", "1.0.0") == 0

    def test_different_lengths(self, service):
        assert service.compare_versions("1.0", "1.0.0") == 0
        assert service.compare_versions("1.0.1", "1.0") == 1

    def test_exception(self, service):
        result = service.compare_versions("a.b", "1.0")
        assert result == 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


def test_global_instance():
    from app.services.version_service import version_service
    assert isinstance(version_service, VersionService)
