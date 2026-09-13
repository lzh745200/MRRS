from unittest.mock import MagicMock, patch


def _make_approval_task(id_val, title, approver_id, created_at):
    task = MagicMock()
    task.id = id_val
    task.title = title
    task.current_approver_id = approver_id
    task.created_at = created_at
    task.status = "pending"
    return task


class TestApprovalReminderService:
    def test_init_defaults(self):
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService()
        assert svc._check_interval == 30 * 60
        assert svc._thread is None
        assert svc._running is False

    def test_init_custom_interval(self):
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService(check_interval_minutes=10)
        assert svc._check_interval == 600

    def test_start_already_running(self):
        # 直接 patch 模块 logger，避免全量运行时全局 logging 被其他测试重配
        # 导致 caplog 捕获不到（隔离性修复，生产行为不变）。
        import app.services.reminder_service as mod
        svc = mod.ApprovalReminderService()
        svc._running = True
        with patch.object(mod, "logger") as mock_logger:
            svc.start()
        assert any("已在运行" in str(call.args) for call in mock_logger.warning.call_args_list)

    def test_start_success(self):
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService()
        svc.start()
        assert svc._running is True
        assert svc._thread is not None
        assert svc._thread.name == "approval-reminder"
        svc._stop_event.set()
        svc._thread.join(timeout=1)

    def test_stop_not_running(self):
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService()
        svc.stop()
        assert svc._running is False

    def test_stop_success(self):
        # R12-4：join 上限由 1s 延长到 STOP_JOIN_TIMEOUT_SECONDS，且仅在线程
        # 确已退出（is_alive() False）时才复位运行标记。
        from app.services.reminder_service import (
            STOP_JOIN_TIMEOUT_SECONDS,
            ApprovalReminderService,
        )
        svc = ApprovalReminderService()
        svc._running = True
        thread = MagicMock()
        thread.is_alive.return_value = False
        svc._thread = thread
        svc.stop()
        assert svc._running is False
        assert svc._stopped_event.is_set()
        thread.join.assert_called_once_with(timeout=STOP_JOIN_TIMEOUT_SECONDS)

    def test_stop_alive_thread_keeps_running_flag(self):
        """R12-4：join 超时（线程仍在收尾）时不复位 _running。

        否则紧接着的 start() 会再起一个扫描线程，两个循环并存：提醒重复创建、
        DB 连接翻倍。
        """
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService()
        svc._running = True
        thread = MagicMock()
        thread.is_alive.return_value = True
        svc._thread = thread
        svc.stop()
        assert svc._running is True
        # 运行标记与存活线程共同构成 start() 的判据 → 不会起第二个线程
        svc.start()
        assert svc._thread is thread

    def test_scan_loop_stop_event(self):
        # 源码 _scan_loop 使用 self._stop_event.wait()（而非 time.sleep），
        # 因此通过 mock _stop_event 来控制循环：
        #   wait(30) 首次返回 False → 进入循环；
        #   is_set 首次 False → 执行一次 check；
        #   wait(interval) 再次返回 False；
        #   is_set 第二次 True → 退出循环。
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService()
        svc._check_overdue_approvals = MagicMock()
        svc._stop_event = MagicMock()
        svc._stop_event.is_set.side_effect = [False, True]
        svc._stop_event.wait.return_value = False
        svc._scan_loop()
        svc._check_overdue_approvals.assert_called_once()

    def test_scan_loop_exception_handled(self):
        # 同上：_scan_loop 内异常被捕获且循环继续，最终因 stop 事件退出。
        from app.services.reminder_service import ApprovalReminderService
        svc = ApprovalReminderService()
        svc._check_overdue_approvals = MagicMock(side_effect=Exception("test error"))
        svc._stop_event = MagicMock()
        svc._stop_event.is_set.side_effect = [False, True]
        svc._stop_event.wait.return_value = False
        svc._scan_loop()
        svc._check_overdue_approvals.assert_called_once()

    def test_check_overdue_approvals_no_results(self):
        from app.services.reminder_service import ApprovalReminderService

        mock_db = MagicMock()

        def query_side(model):
            q = MagicMock()
            f = MagicMock()
            f2 = MagicMock()
            f2.all.return_value = []
            f.filter.return_value = f2
            f.all.return_value = []
            q.filter.return_value = f
            return q
        mock_db.query.side_effect = query_side

        with patch("app.core.database.SessionLocal", return_value=mock_db):
            svc = ApprovalReminderService()
            svc._create_reminder_message = MagicMock()
            svc._check_overdue_approvals()
            svc._create_reminder_message.assert_not_called()
            mock_db.close.assert_called_once()

    def test_check_with_overdue_and_approaching(self):
        from app.services.reminder_service import ApprovalReminderService
        from datetime import datetime, timezone, timedelta

        mock_db = MagicMock()
        now = datetime.now(timezone.utc)
        overdue_task = _make_approval_task(1, "Overdue", 5, now - timedelta(hours=50))
        approaching_task = _make_approval_task(2, "Approaching", 6, now - timedelta(hours=40))

        call_count = [0]

        def query_side(model):
            q = MagicMock()

            def filter_side(*args, **kwargs):
                call_count[0] += 1
                f = MagicMock()
                f.filter = lambda *a, **kw: f
                if call_count[0] == 1:
                    f.all.return_value = [overdue_task]
                elif call_count[0] == 2:
                    f.all.return_value = [approaching_task]
                else:
                    f.all.return_value = []
                return f
            q.filter = filter_side
            return q
        mock_db.query.side_effect = query_side

        with patch("app.core.database.SessionLocal", return_value=mock_db):
            svc = ApprovalReminderService()
            svc._create_reminder_message = MagicMock()
            svc._check_overdue_approvals()
            assert svc._create_reminder_message.call_count == 2


class TestCreateReminderMessage:
    def test_existing_skipped(self):
        from app.services.reminder_service import ApprovalReminderService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        task = MagicMock()
        task.id = 1
        svc = ApprovalReminderService()
        svc._create_reminder_message(mock_db, task, "overdue")

    def test_new_overdue(self):
        from app.services.reminder_service import ApprovalReminderService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        task = MagicMock()
        task.id = 42
        task.title = "Important"
        task.current_approver_id = 7
        svc = ApprovalReminderService()
        svc._create_reminder_message(mock_db, task, "overdue")
        mock_db.add.assert_called_once()

    def test_new_approaching(self):
        from app.services.reminder_service import ApprovalReminderService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        task = MagicMock()
        task.id = 99
        task.title = "Task"
        task.current_approver_id = 3
        svc = ApprovalReminderService()
        svc._create_reminder_message(mock_db, task, "approaching")
        mock_db.add.assert_called_once()

    def test_task_no_title(self):
        from app.services.reminder_service import ApprovalReminderService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        task = MagicMock()
        task.id = 1
        task.title = None
        task.current_approver_id = 1
        svc = ApprovalReminderService()
        svc._create_reminder_message(mock_db, task, "overdue")
        mock_db.add.assert_called_once()


class TestGlobalFunctions:
    def test_start_new(self):
        import app.services.reminder_service as mod
        old = mod._reminder_service
        try:
            mod._reminder_service = None
            svc = mod.start_approval_reminder(1)
            assert svc is not None
            assert mod._reminder_service is svc
            svc.stop()
            mod._reminder_service = None
        finally:
            mod._reminder_service = old

    def test_start_already_exists(self):
        # 直接 patch 模块 logger，避免全量运行时全局 logging 被其他测试重配
        # 导致 caplog 捕获不到（隔离性修复，生产行为不变）。
        import app.services.reminder_service as mod
        old = mod._reminder_service
        try:
            existing = MagicMock()
            mod._reminder_service = existing
            with patch.object(mod, "logger") as mock_logger:
                result = mod.start_approval_reminder(1)
            assert result is existing
            assert any("已存在" in str(call.args) for call in mock_logger.warning.call_args_list)
        finally:
            mod._reminder_service = old

    def test_stop_with_service(self):
        import app.services.reminder_service as mod
        svc = MagicMock()
        mod.stop_approval_reminder(svc)
        svc.stop.assert_called_once()

    def test_stop_none(self):
        import app.services.reminder_service as mod
        old = mod._reminder_service
        try:
            mod._reminder_service = None
            mod.stop_approval_reminder()
            assert True
        finally:
            mod._reminder_service = old

    def test_stop_global(self):
        import app.services.reminder_service as mod
        old = mod._reminder_service
        try:
            svc = MagicMock()
            mod._reminder_service = svc
            mod.stop_approval_reminder()
            svc.stop.assert_called_once()
            assert mod._reminder_service is None
        finally:
            mod._reminder_service = old
