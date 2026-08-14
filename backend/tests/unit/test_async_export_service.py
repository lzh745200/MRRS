"""TDD: 异步导出服务 — 实例方法 API."""
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestAsyncExportThreshold:
    """should_use_async: 使用 estimate_record_count 判断."""

    def _svc(self, db=None):
        from app.services.async_export_service import AsyncExportService
        return AsyncExportService(db or MagicMock())

    def test_large_dataset_uses_async(self):
        svc = self._svc()
        with patch.object(svc, 'estimate_record_count', return_value=6000):
            assert svc.should_use_async("supported_villages", {}) is True

    def test_small_dataset_uses_sync(self):
        svc = self._svc()
        with patch.object(svc, 'estimate_record_count', return_value=500):
            assert svc.should_use_async("supported_villages", {}) is False

    def test_threshold_boundary(self):
        svc = self._svc()
        with patch.object(svc, 'estimate_record_count', return_value=5000):
            assert svc.should_use_async("supported_villages", {}) is False
        with patch.object(svc, 'estimate_record_count', return_value=5001):
            assert svc.should_use_async("supported_villages", {}) is True


class TestEstimateRecordCount:
    """estimate_record_count: 实例方法全覆盖."""

    def _svc(self, db):
        from app.services.async_export_service import AsyncExportService
        return AsyncExportService(db)

    def test_unknown_entity_returns_zero(self):
        db = MagicMock()
        assert self._svc(db).estimate_record_count("nonexistent", {}) == 0

    @patch("importlib.import_module")
    def test_known_entity_returns_count(self, mock_import):
        db = MagicMock()
        db.query.return_value.count.return_value = 42
        mock_mod = MagicMock()
        mock_import.return_value = mock_mod
        result = self._svc(db).estimate_record_count("supported_villages", {})
        assert result == 42

    @patch("importlib.import_module", side_effect=ImportError("test error"))
    def test_import_exception_returns_zero(self, mock_import):
        db = MagicMock()
        result = self._svc(db).estimate_record_count("supported_villages", {})
        assert result == 0

    @patch("importlib.import_module")
    def test_getattr_exception_returns_zero(self, mock_import):
        db = MagicMock()
        mock_mod = MagicMock()
        del mock_mod.SupportedVillage
        mock_import.return_value = mock_mod
        result = self._svc(db).estimate_record_count("supported_villages", {})
        assert result == 0


class TestExportSync:
    """同步导出方法 — 真实查库，返回 (content, filename, count)."""

    def _svc(self, db=None):
        from app.services.async_export_service import AsyncExportService
        return AsyncExportService(db or MagicMock())

    def _assert_is_tuple3(self, result):
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 3, f"Expected tuple of 3, got {len(result)}"

    @patch("app.services.async_export_service._fetch_village_records", return_value=[{"name": "test"}])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_supported_villages_sync(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_village_list.return_value = b"excel data"
        content, filename, count = svc.export_supported_villages_sync(MagicMock(), None, {"keyword": "x"})
        self._assert_is_tuple3((content, filename, count))
        assert content == b"excel data"
        assert isinstance(filename, str)
        assert count == 1
        instance.export_village_list.assert_called_once_with([{"name": "test"}])

    @patch("app.services.async_export_service._fetch_village_records", return_value=[{"name": "a"}, {"name": "b"}])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_report_sync_supported_villages(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_village_list.return_value = b"data"
        content, filename, count = svc.export_report_sync(
            "supported_villages", {"keyword": "x"}, MagicMock(), None
        )
        assert content == b"data"
        assert count == 2

    @patch("app.services.async_export_service._fetch_fund_records", return_value=[{"ID": 1}])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_report_sync_funds(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_fund_list.return_value = b"data"
        content, _, count = svc.export_report_sync("funds", {}, MagicMock(), None)
        assert content == b"data"
        assert count == 1

    @patch("app.services.async_export_service._fetch_project_records", return_value=[{"ID": 1}])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_report_sync_projects(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_project_list.return_value = b"data"
        content, _, count = svc.export_report_sync("projects", {}, MagicMock(), None)
        assert content == b"data"
        assert count == 1

    @patch("app.services.async_export_service._fetch_school_records", return_value=[{"ID": 1}])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_report_sync_schools(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_school_list.return_value = b"data"
        content, _, count = svc.export_report_sync("schools", {}, MagicMock(), None)
        assert content == b"data"
        assert count == 1

    @patch("app.services.async_export_service._build_comprehensive_workbook", return_value=b"data")
    def test_export_report_sync_comprehensive(self, _mock_build):
        svc = self._svc()
        content, _, count = svc.export_report_sync("comprehensive", {}, MagicMock(), None)
        assert content == b"data"
        assert count == 0

    @patch("app.services.async_export_service._fetch_village_records", return_value=[{"ID": 1}])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_report_sync_default_fallback(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_village_list.return_value = b"data"
        content, _, count = svc.export_report_sync("unknown_type", {}, MagicMock(), None)
        assert content == b"data"
        assert count == 1

    @patch("app.services.async_export_service._fetch_village_records", return_value=[])
    @patch("app.services.async_export_service.ExcelExportService")
    def test_export_report_sync_default_when_items_missing(self, MockSvc, _mock_fetch):
        svc = self._svc()
        instance = MockSvc.return_value
        instance.export_village_list.return_value = b"data"
        content, _, count = svc.export_report_sync("unknown_type", {}, MagicMock(), None)
        assert content == b"data"
        assert count == 0


class TestExportAsync:
    """异步导出任务启动 — 实例方法（提交任务队列）."""

    @patch("app.services.async_export_service.task_queue.submit", new_callable=AsyncMock)
    @patch("app.services.async_export_service.AsyncExportService.estimate_record_count")
    @patch("app.services.async_export_service._uuid")
    @patch("app.services.async_export_service.datetime")
    def test_export_supported_villages_async(self, mock_dt, mock_uuid, mock_est, mock_submit):
        # Ensure all lazy models are loaded to avoid mapper resolution errors
        import app.models
        for _name in app.models.__all__:
            try:
                getattr(app.models, _name)
            except Exception:
                pass
        from app.services.async_export_service import AsyncExportService
        from app.models.export_task import ExportTask

        mock_uuid.uuid4.return_value = "task-uuid-123"
        mock_dt.now.return_value = datetime(2025, 1, 1, 12, 0, 0)
        mock_est.return_value = 42

        db = MagicMock()
        svc = AsyncExportService(db)
        import asyncio

        task = asyncio.run(svc.export_supported_villages_async(1, {"filter": "test"}))

        assert isinstance(task, ExportTask)
        assert task.task_id == "task-uuid-123"
        assert task.user_id == 1
        assert task.export_type == "supported_villages"
        assert task.record_count == 42
        assert task.status == "pending"
        assert task.file_name == "帮扶村导出_20250101120000.xlsx"
        assert task.expires_at == datetime(2025, 1, 2, 12, 0, 0)
        db.add.assert_called_once_with(task)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(task)
        mock_submit.assert_called_once()


class TestGetExportTask:
    """get_export_task — 实例方法，通过 task_id 字符串查询."""

    def test_task_found(self):
        from app.services.async_export_service import AsyncExportService
        db = MagicMock()
        task_mock = MagicMock(id=1, status="completed")
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = task_mock
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        svc = AsyncExportService(db)
        result = svc.get_export_task("task-uuid-1")
        assert result is task_mock

    def test_task_not_found(self):
        from app.services.async_export_service import AsyncExportService
        db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        svc = AsyncExportService(db)
        assert svc.get_export_task("nonexistent") is None


class TestGetExportFile:
    """get_export_file — 实例方法，返回 (bytes, filename) 或 None."""

    def _svc(self, db):
        from app.services.async_export_service import AsyncExportService
        return AsyncExportService(db)

    def _setup_db_query(self, db, return_value):
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = return_value
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

    def test_task_not_found_returns_none(self):
        db = MagicMock()
        self._setup_db_query(db, None)
        assert self._svc(db).get_export_file("task-1") is None

    def test_task_no_file_path_returns_none(self):
        db = MagicMock()
        task = MagicMock()
        task.file_path = None
        task.file_name = "x.xlsx"
        self._setup_db_query(db, task)
        assert self._svc(db).get_export_file("task-1") is None

    def test_file_read_success(self, tmp_path):
        f = tmp_path / "export.xlsx"
        f.write_bytes(b"excel binary content")
        db = MagicMock()
        task = MagicMock()
        task.file_path = str(f)
        task.file_name = "export.xlsx"
        self._setup_db_query(db, task)
        result = self._svc(db).get_export_file("task-1")
        assert result is not None
        assert result[0] == b"excel binary content"
        assert result[1] == "export.xlsx"

    def test_file_not_found_error(self):
        db = MagicMock()
        task = MagicMock()
        task.file_path = os.path.join(
            os.environ.get("TEMP", "/tmp"), "nonexistent_export_12345.xlsx"
        )
        self._setup_db_query(db, task)
        assert self._svc(db).get_export_file("task-1") is None


class TestGetUserExportTasks:
    """get_user_export_tasks — 实例方法，返回 (tasks, total)."""

    def _svc(self, db):
        from app.services.async_export_service import AsyncExportService
        return AsyncExportService(db)

    def _make_query_chain(self, db, result, with_status=False):
        mock_limit = MagicMock()
        mock_limit.all.return_value = result
        mock_offset = MagicMock()
        mock_offset.limit.return_value = mock_limit
        mock_order = MagicMock()
        mock_order.offset.return_value = mock_offset

        if with_status:
            mock_status_filter = MagicMock()
            mock_status_filter.order_by.return_value = mock_order
            mock_user_filter = MagicMock()
            mock_user_filter.filter.return_value = mock_status_filter
        else:
            mock_user_filter = MagicMock()
            mock_user_filter.order_by.return_value = mock_order

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_user_filter
        db.query.return_value = mock_query

    def test_without_status_filter(self):
        db = MagicMock()
        expected = [MagicMock(id=1), MagicMock(id=2)]
        mock_query = MagicMock()
        mock_query.count.return_value = 2
        self._make_query_chain(db, expected)
        tasks, total = self._svc(db).get_user_export_tasks(1)
        assert len(tasks) == 2

    def test_with_status_filter(self):
        db = MagicMock()
        expected = [MagicMock(id=1)]
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        self._make_query_chain(db, expected, with_status=True)
        tasks, total = self._svc(db).get_user_export_tasks(1, status="pending")
        assert len(tasks) == 1

    def test_pagination_applied(self):
        db = MagicMock()
        expected = []
        mock_query = MagicMock()
        mock_query.count.return_value = 0
        self._make_query_chain(db, expected)
        tasks, total = self._svc(db).get_user_export_tasks(1, page=2, page_size=10)
        assert tasks == expected
