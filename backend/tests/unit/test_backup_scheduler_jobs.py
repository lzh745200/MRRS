"""app.services.backup_scheduler 定时任务函数覆盖补充测试。

覆盖各 job 协程（auto_backup / kpi / anomaly / todo / message_cleanup /
weekly_report / database_maintenance / auto_package / reminder_scan /
recycle_retention）、辅助函数（_admin_user_ids / _send_backup_reminder /
_auto_package_with_db）以及 _schedule_interval 的内部 _job 闭包。

约定：所有 job 通过 `with get_db_context() as db` 取会话；db 用 MagicMock，
按被查询的 model 类分派 side_effect，避免链式调用相互污染。
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.backup_scheduler as bm
from app.models.organization import Organization
from app.models.project import Project
from app.models.system_config import SystemConfig
from app.models.user import User


def _db_ctx(db):
    """把 get_db_context 替换为产出给定 mock db 的上下文管理器工厂。"""

    @contextmanager
    def _ctx():
        yield db

    return _ctx


def _cfg(mapping):
    """构造 get_config 的 side_effect：按 key 命中，否则返回默认。"""

    def _get(key, default=None):
        return mapping.get(key, default)

    return _get


# ─────────────────────────── 辅助函数 ───────────────────────────


class TestAdminUserIds:
    def test_returns_ids(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [(1,), (2,)]
        assert bm._admin_user_ids(db) == [1, 2]


class TestSendBackupReminder:
    def test_sends_when_admins_exist(self):
        db = MagicMock()
        with patch.object(bm, "_admin_user_ids", return_value=[1, 2]), \
             patch("app.services.message_service.MessageService") as MS:
            bm._send_backup_reminder(db, "标题", "内容")
        MS.return_value.send_batch_messages.assert_called_once()
        kwargs = MS.return_value.send_batch_messages.call_args.kwargs
        assert kwargs["user_ids"] == [1, 2]
        assert kwargs["title"] == "标题"

    def test_no_send_when_no_admins(self):
        db = MagicMock()
        with patch.object(bm, "_admin_user_ids", return_value=[]), \
             patch("app.services.message_service.MessageService") as MS:
            bm._send_backup_reminder(db, "t", "c")
        MS.return_value.send_batch_messages.assert_not_called()


# ─────────────────────────── auto_backup_job ───────────────────────────


class TestAutoBackupJob:
    async def test_disabled_skips(self):
        db = MagicMock()
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({"auto_backup": "false"})), \
             patch.object(bm, "BackupService") as BS:
            await bm.auto_backup_job()
        BS.assert_not_called()

    async def test_interval_not_reached_skips(self):
        db = MagicMock()
        recent = MagicMock()
        recent.value = datetime.now().isoformat()
        db.query.return_value.filter.return_value.first.return_value = recent
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30"})), \
             patch.object(bm, "BackupService") as BS:
            await bm.auto_backup_job()
        BS.assert_not_called()

    async def test_success_plain_with_retention_and_reminder(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        backup = MagicMock(file_name="b.zip", file_size=2048)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder") as rem:
            BS.return_value.create_backup.return_value = backup
            BS.return_value.cleanup_by_retention_days.return_value = 3
            await bm.auto_backup_job()
        BS.return_value.create_backup.assert_called_once()
        BS.return_value.cleanup_by_retention_days.assert_called_once_with(7)
        rem.assert_called_once()
        assert rem.call_args.args[1] == "自动备份完成"

    async def test_unparseable_last_backup_time_proceeds(self):
        db = MagicMock()
        bad = MagicMock()
        bad.value = "not-an-iso"
        db.query.return_value.filter.return_value.first.return_value = bad
        backup = MagicMock(file_name="b.zip", file_size=0)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder"):
            BS.return_value.create_backup.return_value = backup
            BS.return_value.cleanup_by_retention_days.return_value = 0
            await bm.auto_backup_job()
        BS.return_value.create_backup.assert_called_once()

    async def test_encrypt_branch_uses_runtime_secret(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        backup = MagicMock(file_name="e.zip", file_size=10)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "", "backup_encrypt": "true",
                 "backup_retention_days": "7"})), \
             patch("app.utils.runtime_secrets.get_or_create_secret",
                   return_value="secret-key"), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder"):
            BS.return_value.create_backup.return_value = backup
            BS.return_value.cleanup_by_retention_days.return_value = 0
            await bm.auto_backup_job()
        assert BS.return_value.create_backup.call_args.kwargs["password"] == "secret-key"

    async def test_target_dir_unwritable_falls_back_to_default(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        backup = MagicMock(file_name="b.zip", file_size=0)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "/mnt/usb", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=False), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder"):
            BS.return_value.create_backup.return_value = backup
            BS.return_value.cleanup_by_retention_days.return_value = 0
            await bm.auto_backup_job()
        # 回退默认目录：BackupService(db) 无 backup_dir 关键字
        assert "backup_dir" not in BS.call_args.kwargs

    async def test_target_dir_writable_passes_backup_dir(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        backup = MagicMock(file_name="b.zip", file_size=0)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "/mnt/usb", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder"):
            BS.return_value.create_backup.return_value = backup
            BS.return_value.cleanup_by_retention_days.return_value = 0
            await bm.auto_backup_job()
        assert BS.call_args.kwargs["backup_dir"] == "/mnt/usb"

    async def test_backup_failure_sends_failure_reminder(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder") as rem:
            BS.return_value.create_backup.side_effect = RuntimeError("disk boom")
            await bm.auto_backup_job()
        assert rem.call_args.args[1] == "自动备份失败"

    async def test_success_reminder_failure_is_swallowed(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        backup = MagicMock(file_name="b.zip", file_size=0)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder",
                          side_effect=RuntimeError("msg boom")):
            BS.return_value.create_backup.return_value = backup
            BS.return_value.cleanup_by_retention_days.return_value = 0
            await bm.auto_backup_job()  # 提醒失败被内层 except 吞掉，不抛出

    async def test_failure_reminder_failure_is_swallowed(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "get_config", _cfg({
                 "auto_backup": "true", "backup_interval_days": "30",
                 "backup_target_dir": "", "backup_encrypt": "false",
                 "backup_retention_days": "7"})), \
             patch.object(bm, "BackupService") as BS, \
             patch.object(bm, "_send_backup_reminder",
                          side_effect=RuntimeError("msg boom")):
            BS.return_value.create_backup.side_effect = RuntimeError("backup boom")
            await bm.auto_backup_job()  # 双重失败均被吞掉


# ─────────────────────────── kpi_precalculate_job ───────────────────────────


class TestKpiPrecalculateJob:
    async def test_success_writes_cache(self):
        db = MagicMock()
        cache = MagicMock()
        cache.set = AsyncMock()
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.api.v1.data.data.analytics.compute_kpi_summary_data",
                   return_value={"total": 1}), \
             patch("app.core.cache.get_cache_service",
                   new=AsyncMock(return_value=cache)):
            await bm.kpi_precalculate_job()
        cache.set.assert_awaited_once()

    async def test_exception_is_logged(self):
        db = MagicMock()
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.api.v1.data.data.analytics.compute_kpi_summary_data",
                   side_effect=RuntimeError("kpi boom")):
            await bm.kpi_precalculate_job()  # 不抛出


# ─────────────────────────── anomaly_detection_job ───────────────────────────


class TestAnomalyDetectionJob:
    def _db_with(self, projects, admin_rows):
        db = MagicMock()

        def _query(model):
            m = MagicMock()
            if model is Project:
                m.filter.return_value.all.return_value = projects
            elif model is User:
                m.filter.return_value.all.return_value = admin_rows
            return m

        db.query.side_effect = _query
        return db

    async def test_new_anomalies_send_message(self):
        p1, p2 = MagicMock(id=1), MagicMock(id=2)
        db = self._db_with([p1, p2], [(9,)])

        def _detect(_db, pid):
            if pid == 2:
                raise RuntimeError("per-project boom")  # 触发 continue 分支
            return ["a1", "a2"]

        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.fund_anomaly_detector.detect_anomalies",
                   side_effect=_detect), \
             patch("app.services.message_service.MessageService") as MS:
            await bm.anomaly_detection_job()
        MS.return_value.send_batch_messages.assert_called_once()
        assert "2 条新异常" in MS.return_value.send_batch_messages.call_args.kwargs["title"]

    async def test_no_anomalies_no_message(self):
        db = self._db_with([MagicMock(id=1)], [])
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.fund_anomaly_detector.detect_anomalies",
                   return_value=[]), \
             patch("app.services.message_service.MessageService") as MS:
            await bm.anomaly_detection_job()
        MS.return_value.send_batch_messages.assert_not_called()

    async def test_outer_exception_is_logged(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("query boom")
        with patch.object(bm, "get_db_context", _db_ctx(db)):
            await bm.anomaly_detection_job()  # 不抛出


# ─────────────────────────── todo_reminder_job ───────────────────────────


class TestTodoReminderJob:
    async def test_sends_today_and_tomorrow_skips_none_user(self):
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        t_today = MagicMock(user_id=1, title="A", deadline=today.strftime("%Y-%m-%d"))
        t_tomorrow = MagicMock(user_id=2, title="B", deadline=tomorrow.strftime("%Y-%m-%d"))
        t_none = MagicMock(user_id=None, title="C", deadline=today.strftime("%Y-%m-%d"))
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            t_today, t_none, t_tomorrow]
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.message_service.MessageService") as MS:
            await bm.todo_reminder_job()
        assert MS.return_value.send_task_message.call_count == 2
        titles = [c.kwargs["title"] for c in
                  MS.return_value.send_task_message.call_args_list]
        assert any("今日到期" in t for t in titles)
        assert any("明日到期" in t for t in titles)

    async def test_exception_is_logged(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("todo boom")
        with patch.object(bm, "get_db_context", _db_ctx(db)):
            await bm.todo_reminder_job()  # 不抛出


# ─────────────────────────── message_cleanup_job ───────────────────────────


class TestMessageCleanupJob:
    async def test_success(self):
        db = MagicMock()
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.message_service.MessageService") as MS:
            MS.return_value.cleanup_old_messages.return_value = 5
            await bm.message_cleanup_job()
        MS.return_value.cleanup_old_messages.assert_called_once_with(days=30)

    async def test_exception_is_logged(self):
        db = MagicMock()
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.message_service.MessageService") as MS:
            MS.return_value.cleanup_old_messages.side_effect = RuntimeError("boom")
            await bm.message_cleanup_job()  # 不抛出


# ─────────────────────────── weekly_report_job ───────────────────────────


class TestWeeklyReportJob:
    async def test_success_sends_batch(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 4
        db.query.return_value.filter.return_value.all.return_value = [(1,), (2,)]
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.message_service.MessageService") as MS:
            await bm.weekly_report_job()
        MS.return_value.send_batch_messages.assert_called_once()
        assert "工作周报" in MS.return_value.send_batch_messages.call_args.kwargs["title"]

    async def test_scalar_none_defaults_to_zero(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch("app.services.message_service.MessageService") as MS:
            await bm.weekly_report_job()
        content = MS.return_value.send_batch_messages.call_args.kwargs["content"]
        assert "0 条" in content

    async def test_exception_is_logged(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("weekly boom")
        with patch.object(bm, "get_db_context", _db_ctx(db)):
            await bm.weekly_report_job()  # 不抛出


# ─────────────────────────── database_maintenance_job ───────────────────────────


class TestDatabaseMaintenanceJob:
    async def test_success_on_real_sqlite(self, tmp_path):
        db_file = tmp_path / "maint.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        with patch("app.utils.paths.get_database_path", return_value=db_file):
            await bm.database_maintenance_job()  # 真实 PRAGMA 执行，不抛出

    async def test_missing_db_file_skips(self, tmp_path):
        missing = tmp_path / "nope.db"
        with patch("app.utils.paths.get_database_path", return_value=missing):
            await bm.database_maintenance_job()  # 提前返回

    async def test_exception_is_logged(self):
        with patch("app.utils.paths.get_database_path",
                   side_effect=RuntimeError("path boom")):
            await bm.database_maintenance_job()  # 不抛出


# ─────────────────────────── reminder_scan_job ───────────────────────────


class TestReminderScanJob:
    async def test_created_logs(self):
        with patch("app.services.reminder_orchestrator.run_reminder_scans",
                   return_value=[1, 2]):
            await bm.reminder_scan_job()

    async def test_empty_no_log(self):
        with patch("app.services.reminder_orchestrator.run_reminder_scans",
                   return_value=[]):
            await bm.reminder_scan_job()

    async def test_exception_is_logged(self):
        with patch("app.services.reminder_orchestrator.run_reminder_scans",
                   side_effect=RuntimeError("scan boom")):
            await bm.reminder_scan_job()  # 不抛出


# ─────────────────────────── auto_package_job ───────────────────────────


class TestAutoPackageJob:
    async def test_delegates_and_swallows_exception(self):
        db = MagicMock()
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "_auto_package_with_db",
                          new=AsyncMock(side_effect=RuntimeError("pkg boom"))):
            await bm.auto_package_job()  # 外层 except 吞掉

    async def test_delegates_success(self):
        db = MagicMock()
        inner = AsyncMock(return_value=None)
        with patch.object(bm, "get_db_context", _db_ctx(db)), \
             patch.object(bm, "_auto_package_with_db", new=inner):
            await bm.auto_package_job()
        inner.assert_awaited_once_with(db)


# ─────────────────────────── _auto_package_with_db ───────────────────────────


class TestAutoPackageWithDb:
    async def test_disabled_returns(self):
        db = MagicMock()
        with patch.object(bm, "get_config", _cfg({"auto_package_enabled": "false"})):
            await bm._auto_package_with_db(db)

    async def test_no_target_dir_returns(self):
        db = MagicMock()
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": "  "})):
            await bm._auto_package_with_db(db)

    async def test_unwritable_target_dir_returns(self):
        db = MagicMock()
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": "/mnt/usb"})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=False):
            await bm._auto_package_with_db(db)

    async def test_interval_not_reached_returns(self):
        db = MagicMock()
        recent = MagicMock()
        recent.value = datetime.now().isoformat()
        db.query.return_value.filter.return_value.first.return_value = recent
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": "/mnt/usb"})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
            await bm._auto_package_with_db(db)

    def _db_with_org(self, org, last_row=None):
        db = MagicMock()

        def _query(model):
            m = MagicMock()
            if model is SystemConfig:
                m.filter.return_value.first.return_value = last_row
            elif model is Organization:
                m.order_by.return_value.first.return_value = org
            return m

        db.query.side_effect = _query
        return db

    async def test_no_org_returns(self):
        db = self._db_with_org(None)
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": "/mnt/usb"})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
            await bm._auto_package_with_db(db)

    async def test_unparseable_last_package_time_proceeds(self):
        """last_package_time 非法 ISO → ValueError 被吞掉后继续（走无组织返回）。"""
        bad = MagicMock()
        bad.value = "not-an-iso"
        db = self._db_with_org(None, last_row=bad)
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": "/mnt/usb"})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
            await bm._auto_package_with_db(db)

    async def test_success_copies_and_records_time(self, tmp_path):
        src = tmp_path / "pkg.zip"
        src.write_bytes(b"data")
        target = tmp_path / "target"
        org = MagicMock(id=7)
        db = self._db_with_org(org)
        result = MagicMock(file_path=str(src), total_records=3)
        dps = MagicMock()
        dps.export_package = AsyncMock(return_value=result)
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": str(target)})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.data_package_service.DataPackageService",
                   return_value=dps), \
             patch("app.services.data_package_service.DATA_TYPE_MODELS",
                   {"villages": object}), \
             patch("app.services.system_config_service.set_config") as sc:
            await bm._auto_package_with_db(db)
        assert (target / "pkg.zip").exists()
        sc.assert_called_once()
        assert sc.call_args.args[0] == "last_package_time"

    async def test_missing_source_file_warns(self, tmp_path):
        target = tmp_path / "target"
        org = MagicMock(id=7)
        db = self._db_with_org(org)
        result = MagicMock(file_path=str(tmp_path / "gone.zip"), total_records=0)
        dps = MagicMock()
        dps.export_package = AsyncMock(return_value=result)
        with patch.object(bm, "get_config", _cfg({
                "auto_package_enabled": "true",
                "auto_package_interval_months": "1",
                "auto_package_dir": str(target)})), \
             patch("app.utils.drive_detect.ensure_target_dir", return_value=True), \
             patch("app.services.data_package_service.DataPackageService",
                   return_value=dps), \
             patch("app.services.data_package_service.DATA_TYPE_MODELS",
                   {"villages": object}), \
             patch("app.services.system_config_service.set_config") as sc:
            await bm._auto_package_with_db(db)
        sc.assert_called_once()  # 仍记录时间，仅告警未复制


# ─────────────────────────── recycle_retention_job ───────────────────────────


class TestRecycleRetentionJob:
    def test_success_closes_session(self):
        session = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=session), \
             patch("app.services.retention_service.purge_expired_soft_deleted") as purge:
            bm.recycle_retention_job()
        purge.assert_called_once_with(session)
        session.close.assert_called_once()

    def test_exception_is_logged_and_closed(self):
        session = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=session), \
             patch("app.services.retention_service.purge_expired_soft_deleted",
                   side_effect=RuntimeError("purge boom")):
            bm.recycle_retention_job()  # 不抛出
        session.close.assert_called_once()


# ─────────────────────────── _schedule_interval 内部 _job 闭包 ───────────────────────────


class _FakeTimer:
    instances = []

    def __init__(self, delay, callback, *args, **kwargs):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.name = ""
        _FakeTimer.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        pass


@pytest.fixture
def reset_scheduler():
    bm.stop_backup_scheduler()
    _FakeTimer.instances = []
    yield
    bm.stop_backup_scheduler()
    _FakeTimer.instances = []


class TestIntervalJobClosure:
    def test_interval_job_runs_and_reschedules(self, reset_scheduler):
        now = datetime(2025, 1, 7, 10, 0, 0)

        class FakeDateTime:
            @classmethod
            def now(cls):
                return now

        with patch.object(bm, "datetime", FakeDateTime), \
             patch.object(bm.threading, "Timer", _FakeTimer):
            bm.start_backup_scheduler()

        interval = next(t for t in _FakeTimer.instances
                        if t.name == "scheduler-reminder_scan")
        count_before = len(_FakeTimer.instances)
        with patch.object(bm.threading, "Timer", _FakeTimer), \
             patch.object(bm, "reminder_scan_job"), \
             patch("asyncio.new_event_loop") as new_loop, \
             patch("asyncio.set_event_loop"):
            interval.callback()
        new_loop.assert_called_once_with()
        # _job 内部重新调度了下一次 interval Timer
        assert len(_FakeTimer.instances) == count_before + 1
