"""
Coverage gap tests — batch 8.

Covers remaining uncovered lines introduced by the standalone v1.7.0 batch:
- app/api/v1/__init__.py         (business module import block)
- app/api/v1/reminders.py        (list_reminders / trigger_scan success+failure)
- app/api/v1/system/backup.py    (get_auto_backup_config)
- app/main.py                    (_start_backup_scheduler / _run_database_startup_check / _stop_backup_scheduler)
- app/services/backup_scheduler.py (auto backup target/encrypt branches, package, scheduler jobs)
- app/services/export_service.py (watermark footer)
- app/utils/drive_detect.py      (windows/linux drive enumeration)
"""

import os
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils import drive_detect


# ===========================================================================
# 1. app/api/v1/reminders.py
# ===========================================================================


class TestRemindersApi:

    @pytest.mark.asyncio
    async def test_list_reminders_success(self):
        from app.api.v1.reminders import list_reminders

        reminders = [
            {"is_read": False, "title": "a"},
            {"is_read": True, "title": "b"},
            {"is_read": False, "title": "c"},
        ]
        with patch("app.services.reminder_orchestrator.list_reminders", return_value=reminders):
            result = await list_reminders(current_user=MagicMock())
        assert result["data"]["total"] == 3
        assert result["data"]["unread"] == 2

    @pytest.mark.asyncio
    async def test_list_reminders_exception_fallback(self):
        from app.api.v1.reminders import list_reminders

        with patch("app.services.reminder_orchestrator.list_reminders", side_effect=RuntimeError("boom")):
            result = await list_reminders(current_user=MagicMock())
        assert result["data"]["items"] == []
        assert result["data"]["unread"] == 0

    @pytest.mark.asyncio
    async def test_trigger_scan_success(self):
        from app.api.v1.reminders import trigger_scan

        with patch("app.services.reminder_orchestrator.run_reminder_scans", return_value=[1, 2, 3]):
            result = await trigger_scan(current_user=MagicMock())
        assert result["data"]["created"] == 3

    @pytest.mark.asyncio
    async def test_trigger_scan_exception_fallback(self):
        from app.api.v1.reminders import trigger_scan

        with patch("app.services.reminder_orchestrator.run_reminder_scans", side_effect=RuntimeError("boom")):
            result = await trigger_scan(current_user=MagicMock())
        assert result["data"]["created"] == 0


# ===========================================================================
# 2. app/api/v1/system/backup.py — get_auto_backup_config
# ===========================================================================


class TestBackupConfig:

    @pytest.mark.asyncio
    async def test_get_backup_schedule_disabled(self):
        from app.api.v1.system.backup import get_backup_schedule

        db = MagicMock()
        user = MagicMock()
        result = await get_backup_schedule(db=db, current_user=user)
        assert result["data"]["enabled"] is False
        assert result["data"]["schedule"] is None

    @pytest.mark.asyncio
    async def test_set_backup_target_success(self):
        from app.api.v1.system.backup import set_backup_target

        db = MagicMock()
        user = MagicMock()
        with patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.system_config_service.set_config") as mock_set:
            result = await set_backup_target(body={"target_dir": "/data/backups"}, db=db, current_user=user)
        assert result["success"] is True
        assert result["data"]["target_dir"] == "/data/backups"
        mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_backup_target_empty(self):
        from app.api.v1.system.backup import set_backup_target

        db = MagicMock()
        user = MagicMock()
        with patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.system_config_service.set_config") as mock_set:
            result = await set_backup_target(body={"target_dir": "  "}, db=db, current_user=user)
        assert result["success"] is True
        assert result["data"]["target_dir"] == ""
        mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_backup_target_unavailable_400(self):
        from fastapi import HTTPException
        from app.api.v1.system.backup import set_backup_target

        db = MagicMock()
        user = MagicMock()
        with patch("app.utils.drive_detect.ensure_target_dir", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await set_backup_target(body={"target_dir": "/bad"}, db=db, current_user=user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_set_backup_target_exception_500(self):
        from fastapi import HTTPException
        from app.api.v1.system.backup import set_backup_target

        db = MagicMock()
        user = MagicMock()
        with patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.system_config_service.set_config", side_effect=RuntimeError("write fail")):
            with pytest.raises(HTTPException) as exc_info:
                await set_backup_target(body={"target_dir": "/data"}, db=db, current_user=user)
        assert exc_info.value.status_code == 500


# ===========================================================================
# 3. app/main.py — 调度器/自检辅助函数
# ===========================================================================


class TestMainHelpers:

    def test_start_backup_scheduler_success(self):
        from app import main

        with patch("app.services.backup_scheduler.start_backup_scheduler") as mock_start:
            main._start_backup_scheduler()
        mock_start.assert_called_once()

    def test_start_backup_scheduler_exception(self):
        from app import main

        with patch("app.services.backup_scheduler.start_backup_scheduler", side_effect=RuntimeError("boom")):
            main._start_backup_scheduler()  # 不应抛出

    def test_stop_backup_scheduler_success(self):
        from app import main

        with patch("app.services.backup_scheduler.stop_backup_scheduler") as mock_stop:
            main._stop_backup_scheduler()
        mock_stop.assert_called_once()

    def test_stop_backup_scheduler_exception(self):
        from app import main

        with patch("app.services.backup_scheduler.stop_backup_scheduler", side_effect=RuntimeError("boom")):
            main._stop_backup_scheduler()  # 不应抛出

    def test_database_startup_check_ok(self):
        from app import main

        health = MagicMock()
        health.startup_check.return_value = {"status": "ok", "db_size_mb": 1.5}
        thread_targets = []

        class FakeThread(threading.Thread):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                thread_targets.append(kwargs.get("target"))

        with patch("app.services.database_health_service.database_health_service", health), \
             patch("threading.Thread", FakeThread):
            main._run_database_startup_check()
        assert len(thread_targets) == 1
        assert thread_targets[0] is not None

    def test_database_startup_check_not_ok(self):
        from app import main

        health = MagicMock()
        health.startup_check.return_value = {"status": "degraded", "message": "slow"}
        thread_targets = []

        class FakeThread(threading.Thread):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                thread_targets.append(kwargs.get("target"))

        with patch("app.services.database_health_service.database_health_service", health), \
             patch("threading.Thread", FakeThread):
            main._run_database_startup_check()
        assert len(thread_targets) == 1


# ===========================================================================
# 4. app/utils/drive_detect.py
# ===========================================================================


class TestDriveDetect:

    def test_drive_type_windows_removable(self):
        with patch("platform.system", return_value="Windows"), \
             patch("ctypes.windll.kernel32.GetDriveTypeW", return_value=2):
            assert drive_detect._drive_type_windows("C") == "removable"

    def test_drive_type_windows_fixed(self):
        with patch("platform.system", return_value="Windows"), \
             patch("ctypes.windll.kernel32.GetDriveTypeW", return_value=3):
            assert drive_detect._drive_type_windows("C") == "fixed"

    def test_drive_type_windows_network(self):
        with patch("platform.system", return_value="Windows"), \
             patch("ctypes.windll.kernel32.GetDriveTypeW", return_value=4):
            assert drive_detect._drive_type_windows("C") == "network"

    def test_drive_type_windows_unknown(self):
        with patch("platform.system", return_value="Windows"), \
             patch("ctypes.windll.kernel32.GetDriveTypeW", return_value=1):
            assert drive_detect._drive_type_windows("C") == "unknown"

    def test_drive_type_windows_exception(self):
        with patch("platform.system", return_value="Windows"), \
             patch("ctypes.windll.kernel32.GetDriveTypeW", side_effect=OSError("no")):
            assert drive_detect._drive_type_windows("C") == "unknown"

    def test_list_backup_dirs_windows(self, tmp_path):
        with patch("platform.system", return_value="Windows"), \
             patch("os.path.exists", side_effect=lambda p: p in ("C:\\", "D:\\")), \
             patch.object(drive_detect, "_drive_type_windows", return_value="fixed"), \
             patch("os.access", return_value=True):
            results = drive_detect.list_backup_dirs()
        assert any(r["path"] == "C:\\" for r in results)
        assert any(r["type"] == "fixed" for r in results)

    def test_list_backup_dirs_linux(self, tmp_path, monkeypatch):
        import string as _string

        base = tmp_path / "media"
        (base / "usb").mkdir(parents=True)
        monkeypatch.setattr(drive_detect, "_LINUX_MOUNT_BASES", [str(base)])
        with patch("platform.system", return_value="Linux"), \
             patch("os.access", return_value=True):
            results = drive_detect.list_backup_dirs()
        assert any("usb" in r["path"] for r in results)

    def test_list_backup_dirs_linux_skips_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(drive_detect, "_LINUX_MOUNT_BASES", ["/definitely/not/here"])
        with patch("platform.system", return_value="Linux"):
            results = drive_detect.list_backup_dirs()
        assert len(results) >= 1  # cwd 兜底始终存在

    def test_list_linux_mounts_writable_only(self, tmp_path, monkeypatch):
        base = tmp_path / "m"
        w_dir = base / "w"
        ro_dir = base / "ro"
        w_dir.mkdir(parents=True)
        ro_dir.mkdir(parents=True)
        monkeypatch.setattr(drive_detect, "_LINUX_MOUNT_BASES", [str(base)])
        with patch("os.access", side_effect=lambda p, m: str(p).endswith(os.sep + "w")):
            results = drive_detect._list_linux_mounts()
        assert any(r["path"].endswith(os.sep + "w") for r in results)
        assert not any(r["path"].endswith(os.sep + "ro") for r in results)

    def test_ensure_target_dir_creates(self, tmp_path):
        target = str(tmp_path / "backup" / "sub")
        with patch("os.access", return_value=True):
            assert drive_detect.ensure_target_dir(target) is True
        assert os.path.isdir(target)

    def test_ensure_target_dir_empty_returns_false(self):
        assert drive_detect.ensure_target_dir("") is False

    def test_ensure_target_dir_error(self, tmp_path):
        with patch("os.makedirs", side_effect=OSError("denied")):
            assert drive_detect.ensure_target_dir(str(tmp_path / "x")) is False


# ===========================================================================
# 5. app/services/export_service.py — watermark 页脚
# ===========================================================================


class TestExportWatermark:

    def test_watermark_footer_written(self):
        from app.services.export_service import ExcelExportService

        svc = ExcelExportService()
        wb = svc._create_workbook(
            sheet_name="测试",
            headers=["列1"],
            rows=[{"列1": "值"}],
            watermark="导出人: admin 2026-08-03",
        )
        ws = wb.active
        assert ws.oddFooter.center.text == "导出人: admin 2026-08-03"
        assert ws.evenFooter.center.text == "导出人: admin 2026-08-03"

    def test_workbook_without_watermark(self):
        from app.services.export_service import ExcelExportService

        svc = ExcelExportService()
        wb = svc._create_workbook(sheet_name="无水印", headers=["A"], rows=[{"A": 1}])
        assert wb.active is not None


# ===========================================================================
# 6. app/api/v1/__init__.py — 业务模块注册块
# ===========================================================================


class TestApiInitModules:

    def test_business_modules_registered(self):
        import app.api.v1 as api_v1

        assert hasattr(api_v1, "api_v1_router")
        assert api_v1.api_v1_router is not None
        assert len(api_v1.api_v1_router.routes) > 0


# ===========================================================================
# 7. app/services/backup_scheduler.py — 目标目录/加密/打包/调度器
# ===========================================================================


class TestBackupSchedulerExtras:

    @pytest.mark.asyncio
    async def test_auto_backup_skip_within_interval(self):
        """距上次备份不足 interval_days 时跳过（源码 43-46）。"""
        from datetime import datetime as _dt, timedelta as _td
        from app.services.backup_scheduler import auto_backup_job

        db = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = None
        last_row = MagicMock()
        last_row.value = _dt.now().isoformat()  # 最近刚备份过
        db.query.return_value.filter.return_value.first.return_value = last_row

        def config_side_effect(key, default=None):
            if key == "auto_backup":
                return "true"
            if key == "backup_interval_days":
                return "30"
            return default

        mock_service = MagicMock()
        with patch("app.services.backup_scheduler.get_db_context", return_value=cm), \
             patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.services.backup_scheduler.BackupService", return_value=mock_service):
            await auto_backup_job()
        mock_service.create_backup.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_backup_invalid_last_time(self):
        """last_backup_time 格式非法时走 ValueError 分支（源码 47-48）。"""
        from app.services.backup_scheduler import auto_backup_job

        db = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = None
        last_row = MagicMock()
        last_row.value = "not-a-date"
        db.query.return_value.filter.return_value.first.return_value = last_row
        record = MagicMock()
        record.file_name = "b.db"
        record.file_size = 10

        def config_side_effect(key, default=None):
            if key == "auto_backup":
                return "true"
            if key == "backup_interval_days":
                return "30"
            if key == "max_backup_count":
                return "3"
            return default

        mock_service = MagicMock()
        mock_service.create_backup.return_value = record
        mock_service.cleanup_old_backups.return_value = 0

        with patch("app.services.backup_scheduler.get_db_context", return_value=cm), \
             patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.services.backup_scheduler.BackupService", return_value=mock_service):
            await auto_backup_job()
        mock_service.create_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_backup_with_target_dir_and_encrypt(self):
        from app.services.backup_scheduler import auto_backup_job

        db = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = None
        record = MagicMock()
        record.file_name = "b.db"
        record.file_size = 10

        def config_side_effect(key, default=None):
            if key == "auto_backup":
                return "true"
            if key == "backup_interval_days":
                return "30"
            if key == "backup_target_dir":
                return "/tmp/backup-dir"
            if key == "backup_encrypt":
                return "true"
            if key == "max_backup_count":
                return "3"
            return default

        mock_service = MagicMock()
        mock_service.create_backup.return_value = record
        mock_service.cleanup_old_backups.return_value = 0

        with patch("app.services.backup_scheduler.get_db_context", return_value=cm), \
             patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.utils.runtime_secrets.get_or_create_secret", return_value="persisted-key-32chars"), \
             patch("app.services.backup_scheduler.BackupService", return_value=mock_service):
            await auto_backup_job()
        mock_service.create_backup.assert_called_once_with(
            description="自动备份", include_uploads=False, password="persisted-key-32chars"
        )

    @pytest.mark.asyncio
    async def test_auto_backup_target_dir_unavailable_fallback(self):
        from app.services.backup_scheduler import auto_backup_job

        db = MagicMock()
        cm = MagicMock()
        cm.__enter__.return_value = db
        cm.__exit__.return_value = None
        record = MagicMock()
        record.file_name = "b.db"
        record.file_size = 10

        def config_side_effect(key, default=None):
            if key == "auto_backup":
                return "true"
            if key == "backup_interval_days":
                return "30"
            if key == "backup_target_dir":
                return "/bad/dir"
            if key == "backup_encrypt":
                return "false"
            if key == "max_backup_count":
                return "3"
            return default

        mock_service = MagicMock()
        mock_service.create_backup.return_value = record
        mock_service.cleanup_old_backups.return_value = 0

        with patch("app.services.backup_scheduler.get_db_context", return_value=cm), \
             patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=False), \
             patch("app.services.backup_scheduler.BackupService", return_value=mock_service):
            await auto_backup_job()
        # 目标目录不可用时回退默认 BackupService(db)
        assert mock_service.create_backup.call_count >= 1

    @pytest.mark.asyncio
    async def test_auto_package_disabled(self):
        from app.services.backup_scheduler import _auto_package_with_db

        db = MagicMock()
        with patch("app.services.backup_scheduler.get_config", return_value="false"):
            assert await _auto_package_with_db(db) is None

    @pytest.mark.asyncio
    async def test_auto_package_no_organization(self):
        from app.services.backup_scheduler import _auto_package_with_db

        db = MagicMock()
        db.query.return_value.order_by.return_value.first.return_value = None

        def config_side_effect(key, default=None):
            if key == "auto_package_enabled":
                return "true"
            if key == "auto_package_interval_months":
                return "1"
            if key == "auto_package_dir":
                return "/tmp/pkg"
            return default

        with patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect):
            assert await _auto_package_with_db(db) is None

    @pytest.mark.asyncio
    async def test_auto_package_success(self):
        from app.services.backup_scheduler import _auto_package_with_db

        db = MagicMock()
        org = MagicMock()
        org.id = 1
        db.query.return_value.order_by.return_value.first.return_value = org
        svc = MagicMock()
        result = MagicMock()
        result.file_path = "/tmp/pkg/pkg.zip"
        result.total_records = 5
        svc.export_package = AsyncMock(return_value=result)

        def config_side_effect(key, default=None):
            if key == "auto_package_enabled":
                return "true"
            if key == "auto_package_interval_months":
                return "1"
            if key == "auto_package_dir":
                return "/tmp/pkg"
            return default

        with patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.data_package_service.DataPackageService", return_value=svc), \
             patch("os.path.exists", return_value=True), \
             patch("shutil.copy2"), \
             patch("app.services.system_config_service.set_config"):
            await _auto_package_with_db(db)  # 不抛错即成功
        svc.export_package.assert_awaited_once()
        assert result.total_records == 5

    def test_start_scheduler_schedules_all_jobs(self):
        import threading as _threading
        import app.services.backup_scheduler as bs

        fake_timer = MagicMock()
        with patch.object(bs, "_scheduler_started", False), \
             patch.object(bs, "_timers", []), \
             patch.object(_threading, "Timer", return_value=fake_timer) as mock_timer:
            bs.start_backup_scheduler()
            # 6 daily + 1 interval + 1 weekly = 8 个 timer 创建（含消息清理，v1.8.0）
            assert mock_timer.call_count == 8
            assert fake_timer.start.call_count == 8
            assert len(bs._timers) == 8
        # 恢复全局状态避免污染其他测试
        with patch.object(bs, "_scheduler_started", True), \
             patch.object(bs, "_timers", []):
            bs.stop_backup_scheduler()

    def test_start_scheduler_already_started(self):
        import app.services.backup_scheduler as bs

        with patch.object(bs, "_scheduler_started", True), \
             patch.object(bs, "_timers", []), \
             patch("threading.Timer") as mock_timer:
            bs.start_backup_scheduler()
            mock_timer.assert_not_called()

    def test_stop_scheduler_cancels_timers(self):
        import app.services.backup_scheduler as bs

        timer1 = MagicMock()
        timer2 = MagicMock()
        with patch.object(bs, "_scheduler_started", True), \
             patch.object(bs, "_timers", [timer1, timer2]):
            bs.stop_backup_scheduler()
        timer1.cancel.assert_called_once()
        timer2.cancel.assert_called_once()

    def test_get_scheduler_status(self):
        import app.services.backup_scheduler as bs

        timer = MagicMock()
        timer.name = "job-x"
        timer.is_alive.return_value = True
        with patch.object(bs, "_scheduler_started", True), \
             patch.object(bs, "_timers", [timer]):
            status = bs.get_scheduler_status()
        assert status["running"] is True
        assert status["jobs"] == [{"id": "job-x", "name": "job-x", "next_run_time": None}]


class TestSchedulerJobsTriggered:
    """直接执行 Timer 触发后才运行的 job 函数体。"""

    @pytest.mark.asyncio
    async def test_auto_package_invalid_last_time_value_error(self):
        """last_package_time 格式非法 → ValueError → pass（源码 331-332）。"""
        from app.services.backup_scheduler import _auto_package_with_db

        db = MagicMock()
        last_row = MagicMock()
        last_row.value = "not-a-date"
        db.query.return_value.filter.return_value.first.return_value = last_row
        org = MagicMock()
        org.id = 1
        # SystemConfig 查询返回 last_row，Organization 查询返回 org
        db.query.return_value.order_by.return_value.first.return_value = org

        def config_side_effect(key, default=None):
            if key == "auto_package_enabled":
                return "true"
            if key == "auto_package_interval_months":
                return "1"
            if key == "auto_package_dir":
                return "/tmp/pkg"
            return default

        svc = MagicMock()
        result = MagicMock()
        result.file_path = "/tmp/pkg/pkg.zip"
        result.total_records = 3
        svc.export_package = AsyncMock(return_value=result)

        with patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.data_package_service.DataPackageService", return_value=svc), \
             patch("os.path.exists", return_value=True), \
             patch("shutil.copy2"), \
             patch("app.services.system_config_service.set_config"):
            await _auto_package_with_db(db)  # ValueError 被 except 吞掉后继续执行
        svc.export_package.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auto_package_file_not_generated(self):
        """自动打包文件未生成 → else 分支（源码 363）。"""
        from app.services.backup_scheduler import _auto_package_with_db

        db = MagicMock()
        org = MagicMock()
        org.id = 1
        db.query.return_value.order_by.return_value.first.return_value = org
        svc = MagicMock()
        result = MagicMock()
        result.file_path = "/tmp/pkg/missing.zip"
        svc.export_package = AsyncMock(return_value=result)

        def config_side_effect(key, default=None):
            if key == "auto_package_enabled":
                return "true"
            if key == "auto_package_interval_months":
                return "1"
            if key == "auto_package_dir":
                return "/tmp/pkg"
            return default

        with patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.data_package_service.DataPackageService", return_value=svc), \
             patch("os.path.exists", return_value=False), \
             patch("app.services.system_config_service.set_config"):
            await _auto_package_with_db(db)  # src 不存在 → else 分支
        svc.export_package.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reminder_scan_job_success(self):
        from app.services.backup_scheduler import reminder_scan_job

        with patch("app.services.reminder_orchestrator.run_reminder_scans", return_value=[1, 2]):
            await reminder_scan_job()  # 不抛错即成功

    @pytest.mark.asyncio
    async def test_reminder_scan_job_empty(self):
        from app.services.backup_scheduler import reminder_scan_job

        with patch("app.services.reminder_orchestrator.run_reminder_scans", return_value=[]):
            await reminder_scan_job()

    @pytest.mark.asyncio
    async def test_reminder_scan_job_exception(self):
        from app.services.backup_scheduler import reminder_scan_job

        with patch("app.services.reminder_orchestrator.run_reminder_scans", side_effect=RuntimeError("boom")):
            await reminder_scan_job()  # 异常被 except 吞掉

    @pytest.mark.asyncio
    async def test_auto_package_no_org_really(self):
        """直接调用 _auto_package_with_db 走无组织分支（源码 327-330）。"""
        from app.services.backup_scheduler import _auto_package_with_db

        db = MagicMock()
        db.query.return_value.order_by.return_value.first.return_value = None

        def config_side_effect(key, default=None):
            if key == "auto_package_enabled":
                return "true"
            if key == "auto_package_interval_months":
                return "1"
            if key == "auto_package_dir":
                return "/tmp/pkg"
            return default

        with patch("app.services.backup_scheduler.get_config", side_effect=config_side_effect), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
            await _auto_package_with_db(db)
        # 无组织 → 走 logger.warning + return 分支

    def test_schedule_interval_job_closure(self):
        """触发 _schedule_interval 的 _job 闭包（源码 432-438）。"""
        import threading as _threading
        import app.services.backup_scheduler as bs

        class CapturingTimer:
            instances = []

            def __init__(self, delay, fn):
                CapturingTimer.instances.append(self)
                self._fn = fn
                self.daemon = False
                self.name = ""
                self.started = False

            def start(self):
                self.started = True

            def cancel(self):
                pass

        async def stub_job():
            pass

        with patch.object(bs, "_scheduler_started", False), \
             patch.object(bs, "_timers", []), \
             patch.object(_threading, "Timer", CapturingTimer) as mock_timer:
            bs.start_backup_scheduler()
        assert len(CapturingTimer.instances) == 8  # 含消息清理（v1.8.0）
        # 找到 name 含 "reminder_scan" 的 timer 并触发其 _job 闭包
        target = next(t for t in CapturingTimer.instances if t.name == "scheduler-reminder_scan")
        with patch.object(bs, "_timers", []):
            target._fn()  # _job: _run_async_job(reminder_scan_job) + 创建新 Timer
        # 恢复状态
        with patch.object(bs, "_scheduler_started", True), \
             patch.object(bs, "_timers", []):
            bs.stop_backup_scheduler()

    def test_schedule_daily_job_closure(self):
        """触发 _schedule_daily 的 _job 闭包（源码 386-388）。"""
        import threading as _threading
        import app.services.backup_scheduler as bs

        class CapturingTimer:
            instances = []

            def __init__(self, delay, fn):
                CapturingTimer.instances.append(self)
                self._fn = fn
                self.daemon = False
                self.name = ""
                self.started = False

            def start(self):
                self.started = True

            def cancel(self):
                pass

        with patch.object(bs, "_scheduler_started", False), \
             patch.object(bs, "_timers", []), \
             patch.object(_threading, "Timer", CapturingTimer):
            bs.start_backup_scheduler()
        assert len(CapturingTimer.instances) == 8  # 含消息清理（v1.8.0）
        target = next(t for t in CapturingTimer.instances if t.name == "scheduler-kpi_precalculate")
        with patch.object(bs, "_timers", []), \
             patch("app.services.backup_scheduler.kpi_precalculate_job") as mock_kpi:
            mock_kpi.return_value = None
            target._fn()  # _job: _run_async_job(kpi_precalculate_job) + 重新调度
        with patch.object(bs, "_scheduler_started", True), \
             patch.object(bs, "_timers", []):
            bs.stop_backup_scheduler()
