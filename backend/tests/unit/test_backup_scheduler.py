import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_db_context(mock_db):
    cm = MagicMock()
    cm.__enter__.return_value = mock_db
    cm.__exit__.return_value = None
    return cm


class TestSchedulerFunctionsExist:
    def test_imports(self):
        from app.services.backup_scheduler import (
            auto_backup_job, kpi_precalculate_job, anomaly_detection_job,
            todo_reminder_job, weekly_report_job, database_maintenance_job,
            start_backup_scheduler, stop_backup_scheduler, get_scheduler_status
        )
        assert callable(auto_backup_job)
        assert callable(kpi_precalculate_job)
        assert callable(anomaly_detection_job)
        assert callable(todo_reminder_job)
        assert callable(weekly_report_job)
        assert callable(database_maintenance_job)
        assert callable(start_backup_scheduler)
        assert callable(stop_backup_scheduler)
        assert callable(get_scheduler_status)

    def test_scheduler_state_variables(self):
        from app.services.backup_scheduler import _scheduler_started, _timers
        assert isinstance(_scheduler_started, bool)
        assert isinstance(_timers, list)


class TestAutoBackupJob:
    @pytest.mark.asyncio
    async def test_auto_backup_disabled(self, mock_db_context, mock_db):
        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.backup_scheduler.get_config", return_value="false") as mock_config:
                from app.services.backup_scheduler import auto_backup_job
                await auto_backup_job()
                mock_config.assert_called_once_with("auto_backup", "false")

    @pytest.mark.asyncio
    async def test_auto_backup_success(self, mock_db_context, mock_db):
        mock_backup_service = MagicMock()
        mock_backup_record = MagicMock()
        mock_backup_record.file_name = "backup_2025.db"
        mock_backup_record.file_size = 1024
        mock_backup_service.create_backup.return_value = mock_backup_record
        mock_backup_service.cleanup_old_backups.return_value = 2

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.backup_scheduler.get_config") as mock_config:
                def config_side_effect(key, default=None):
                    if key == "auto_backup":
                        return "true"
                    if key == "max_backup_count":
                        return "5"
                    return default
                mock_config.side_effect = config_side_effect
                with patch("app.services.backup_scheduler.BackupService", return_value=mock_backup_service):
                    from app.services.backup_scheduler import auto_backup_job
                    await auto_backup_job()
                    mock_backup_service.create_backup.assert_called_once_with(
                        description="自动备份", include_uploads=False
                    )
                    mock_backup_service.cleanup_old_backups.assert_called_once_with(keep_count=5)

    @pytest.mark.asyncio
    async def test_auto_backup_no_cleanup(self, mock_db_context, mock_db):
        mock_backup_service = MagicMock()
        mock_backup_record = MagicMock()
        mock_backup_record.file_name = "backup_2025.db"
        mock_backup_record.file_size = 2048
        mock_backup_service.create_backup.return_value = mock_backup_record
        mock_backup_service.cleanup_old_backups.return_value = 0

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.backup_scheduler.get_config") as mock_config:
                def config_side_effect(key, default=None):
                    if key == "auto_backup":
                        return "true"
                    if key == "max_backup_count":
                        return "5"
                    return default
                mock_config.side_effect = config_side_effect
                with patch("app.services.backup_scheduler.BackupService", return_value=mock_backup_service):
                    from app.services.backup_scheduler import auto_backup_job
                    await auto_backup_job()
                    mock_backup_service.cleanup_old_backups.assert_called_once_with(keep_count=5)

    @pytest.mark.asyncio
    async def test_auto_backup_exception(self, mock_db_context, mock_db):
        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.backup_scheduler.get_config", side_effect=Exception("Config error")):
                from app.services.backup_scheduler import auto_backup_job
                await auto_backup_job()


class TestKpiPrecalculateJob:
    @pytest.mark.asyncio
    async def test_kpi_success(self, mock_db_context, mock_db):
        mock_db.query.return_value.scalar.return_value = 50
        mock_db.query.return_value.group_by.return_value.all.return_value = [
            ("completed", 30),
            ("approved", 10),
            ("active", 10),
        ]
        mock_cache_service = AsyncMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.core.cache.get_cache_service", return_value=mock_cache_service):
                with patch("app.core.constants.ANALYTICS_CACHE_PREFIX", "analytics:"):
                    from app.services.backup_scheduler import kpi_precalculate_job
                    await kpi_precalculate_job()
                    mock_cache_service.set.assert_called_once()
                    args, _ = mock_cache_service.set.call_args
                    assert args[0] == "analytics:kpi_summary_month"

    @pytest.mark.asyncio
    async def test_kpi_no_projects(self, mock_db_context, mock_db):
        mock_db.query.return_value.scalar.return_value = 50
        mock_db.query.return_value.group_by.return_value.all.return_value = []
        mock_cache_service = AsyncMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.core.cache.get_cache_service", return_value=mock_cache_service):
                from app.services.backup_scheduler import kpi_precalculate_job
                await kpi_precalculate_job()
                mock_cache_service.set.assert_called_once()
                data = mock_cache_service.set.call_args[0][1]
                assert data["completion_rate"] == 0

    @pytest.mark.asyncio
    async def test_kpi_exception(self, mock_db_context, mock_db):
        mock_db.query.side_effect = Exception("KPI error")

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            from app.services.backup_scheduler import kpi_precalculate_job
            await kpi_precalculate_job()


class TestAnomalyDetectionJob:
    @pytest.mark.asyncio
    async def test_anomaly_found(self, mock_db_context, mock_db):
        mock_project = MagicMock()
        mock_project.id = 1
        project_query = MagicMock()
        project_query.filter.return_value.all.return_value = [mock_project]
        user_query = MagicMock()
        user_query.filter.return_value.all.return_value = [(1,), (2,)]
        mock_db.query.side_effect = [project_query, user_query]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.fund_anomaly_detector.detect_anomalies", return_value=["anomaly1"]) as mock_detect:
                with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                    from app.services.backup_scheduler import anomaly_detection_job
                    await anomaly_detection_job()
                    mock_detect.assert_called_once()
                    mock_message_service.send_batch_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_anomaly_not_found(self, mock_db_context, mock_db):
        mock_project = MagicMock()
        mock_project.id = 1
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project]

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.fund_anomaly_detector.detect_anomalies", return_value=[]) as mock_detect:
                from app.services.backup_scheduler import anomaly_detection_job
                await anomaly_detection_job()
                mock_detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_anomaly_no_active_projects(self, mock_db_context, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.fund_anomaly_detector.detect_anomalies") as mock_detect:
                from app.services.backup_scheduler import anomaly_detection_job
                await anomaly_detection_job()
                mock_detect.assert_not_called()

    @pytest.mark.asyncio
    async def test_anomaly_detect_raises(self, mock_db_context, mock_db):
        mock_project = MagicMock()
        mock_project.id = 1
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project]

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.fund_anomaly_detector.detect_anomalies", side_effect=Exception("detect error")):
                from app.services.backup_scheduler import anomaly_detection_job
                await anomaly_detection_job()

    @pytest.mark.asyncio
    async def test_anomaly_exception(self, mock_db_context, mock_db):
        mock_db.query.side_effect = Exception("Anomaly error")

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            from app.services.backup_scheduler import anomaly_detection_job
            await anomaly_detection_job()


class TestTodoReminderJob:
    @pytest.mark.asyncio
    async def test_todo_today(self, mock_db_context, mock_db):
        mock_todo = MagicMock()
        mock_todo.user_id = 1
        mock_todo.title = "Complete report"
        mock_todo.deadline = datetime.now().date().strftime("%Y-%m-%d")
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_todo]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import todo_reminder_job
                await todo_reminder_job()
                mock_message_service.send_task_message.assert_called_once()
                args = mock_message_service.send_task_message.call_args[1]
                assert "今日到期" in args["title"]

    @pytest.mark.asyncio
    async def test_todo_tomorrow(self, mock_db_context, mock_db):
        mock_todo = MagicMock()
        mock_todo.user_id = 1
        mock_todo.title = "Submit proposal"
        tomorrow = (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        mock_todo.deadline = tomorrow
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_todo]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import todo_reminder_job
                await todo_reminder_job()
                mock_message_service.send_task_message.assert_called_once()
                args = mock_message_service.send_task_message.call_args[1]
                assert "明日到期" in args["title"]

    @pytest.mark.asyncio
    async def test_todo_no_user_id(self, mock_db_context, mock_db):
        mock_todo = MagicMock()
        mock_todo.user_id = None
        mock_todo.title = "Orphan todo"
        mock_todo.deadline = datetime.now().date().strftime("%Y-%m-%d")
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_todo]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import todo_reminder_job
                await todo_reminder_job()
                mock_message_service.send_task_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_todo_no_todos(self, mock_db_context, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import todo_reminder_job
                await todo_reminder_job()
                mock_message_service.send_task_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_todo_multiple(self, mock_db_context, mock_db):
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        mock_todo1 = MagicMock()
        mock_todo1.user_id = 1
        mock_todo1.title = "Task 1"
        mock_todo1.deadline = today_str
        mock_todo2 = MagicMock()
        mock_todo2.user_id = 2
        mock_todo2.title = "Task 2"
        mock_todo2.deadline = today_str
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_todo1, mock_todo2]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import todo_reminder_job
                await todo_reminder_job()
                assert mock_message_service.send_task_message.call_count == 2

    @pytest.mark.asyncio
    async def test_todo_exception(self, mock_db_context, mock_db):
        mock_db.query.side_effect = Exception("Todo error")

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            from app.services.backup_scheduler import todo_reminder_job
            await todo_reminder_job()


class TestWeeklyReportJob:
    @pytest.mark.asyncio
    async def test_weekly_report_success(self, mock_db_context, mock_db):
        log_q = MagicMock()
        log_q.filter.return_value.scalar.return_value = 15
        todo_q = MagicMock()
        todo_q.filter.return_value.scalar.return_value = 5
        user_q = MagicMock()
        user_q.filter.return_value.all.return_value = [(1,), (2,), (3,)]
        mock_db.query.side_effect = [log_q, todo_q, user_q]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import weekly_report_job
                await weekly_report_job()
                mock_message_service.send_batch_messages.assert_called_once()
                args = mock_message_service.send_batch_messages.call_args[1]
                assert args["user_ids"] == [1, 2, 3]
                assert "工作周报" in args["title"]

    @pytest.mark.asyncio
    async def test_weekly_report_no_users(self, mock_db_context, mock_db):
        log_q = MagicMock()
        log_q.filter.return_value.scalar.return_value = 0
        todo_q = MagicMock()
        todo_q.filter.return_value.scalar.return_value = 0
        user_q = MagicMock()
        user_q.filter.return_value.all.return_value = []
        mock_db.query.side_effect = [log_q, todo_q, user_q]

        mock_message_service = MagicMock()

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            with patch("app.services.message_service.MessageService", return_value=mock_message_service):
                from app.services.backup_scheduler import weekly_report_job
                await weekly_report_job()
                mock_message_service.send_batch_messages.assert_called_once()
                assert mock_message_service.send_batch_messages.call_args[1]["user_ids"] == []

    @pytest.mark.asyncio
    async def test_weekly_report_exception(self, mock_db_context, mock_db):
        mock_db.query.side_effect = Exception("Weekly error")

        with patch("app.services.backup_scheduler.get_db_context", return_value=mock_db_context):
            from app.services.backup_scheduler import weekly_report_job
            await weekly_report_job()


class TestDatabaseMaintenanceJob:
    @pytest.mark.asyncio
    async def test_maintenance_success(self, mock_db_context):
        with patch("app.services.backup_scheduler.os.path.exists", return_value=True):
            with patch("app.services.backup_scheduler.os.path.getsize", side_effect=[10000, 8000]):
                with patch("app.utils.paths.get_database_path") as mock_path:
                    mock_path.return_value.absolute.return_value = "C:\\test.db"
                    with patch("sqlite3.connect") as mock_connect:
                        mock_conn = MagicMock()
                        mock_connect.return_value = mock_conn
                        from app.services.backup_scheduler import database_maintenance_job
                        await database_maintenance_job()
                        assert mock_conn.execute.call_count == 3
                        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_maintenance_db_not_found(self, mock_db_context):
        with patch("app.services.backup_scheduler.os.path.exists", return_value=False):
            with patch("app.utils.paths.get_database_path") as mock_path:
                mock_path.return_value.absolute.return_value = "C:\\nonexistent.db"
                from app.services.backup_scheduler import database_maintenance_job
                await database_maintenance_job()

    @pytest.mark.asyncio
    async def test_maintenance_exception(self, mock_db_context):
        with patch("app.services.backup_scheduler.os.path.exists", side_effect=Exception("Maintenance error")):
            from app.services.backup_scheduler import database_maintenance_job
            await database_maintenance_job()


class TestSchedulerControl:
    def test_start_backup_scheduler(self):
        import app.services.backup_scheduler as bm
        bm._scheduler_started = False
        bm._timers.clear()
        bm.start_backup_scheduler()
        assert bm._scheduler_started is True
        assert len(bm._timers) == 8  # KPI/异常检测/自动备份/自动打包/提醒扫描/待办提醒/周报/消息清理
        bm.stop_backup_scheduler()

    def test_stop_backup_scheduler_running(self):
        import app.services.backup_scheduler as bm
        bm._scheduler_started = True
        bm.stop_backup_scheduler()
        assert bm._scheduler_started is False
        assert len(bm._timers) == 0

    def test_stop_backup_scheduler_not_running(self):
        import app.services.backup_scheduler as bm
        bm._scheduler_started = False
        bm._timers.clear()
        bm.stop_backup_scheduler()
        assert bm._scheduler_started is False

    def test_get_scheduler_status_running(self):
        import app.services.backup_scheduler as bm
        bm._scheduler_started = True
        result = bm.get_scheduler_status()
        assert result["running"] is True
        assert isinstance(result["jobs"], list)
        bm._scheduler_started = False

    def test_get_scheduler_status_not_running(self):
        import app.services.backup_scheduler as bm
        bm._scheduler_started = False
        bm._timers.clear()
        result = bm.get_scheduler_status()
        assert result["running"] is False
        assert result["jobs"] == []
