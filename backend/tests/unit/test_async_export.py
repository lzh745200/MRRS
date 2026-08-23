"""Tests for async_export API endpoints."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.export_task import ExportStatus

BASE = "/api/v1/async-export"


class TestExportReports:
    """POST /api/v1/async-export/reports"""

    def test_unauthenticated(self, client):
        resp = client.post(f"{BASE}/reports", json={"report_type": "supported_villages"})
        assert resp.status_code == 401

    def test_export_success(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.export_report_sync.return_value = (b"excel data", "report.xlsx", 10)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/reports",
                json={"report_type": "supported_villages"},
            )

        assert resp.status_code == 200
        assert resp.content == b"excel data"
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "filename*=UTF-8''report.xlsx" in resp.headers["content-disposition"]

    def test_export_with_all_fields(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.export_report_sync.return_value = (b"data", "funds.xlsx", 5)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/reports",
                json={
                    "report_type": "funds",
                    "format": "xlsx",
                    "scope": "all",
                    "include_charts": True,
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "options": {"some": "option"},
                },
            )

        assert resp.status_code == 200
        _, kwargs = mock_svc.export_report_sync.call_args
        assert kwargs["report_type"] == "funds"
        assert kwargs["query_params"]["start_date"] == "2024-01-01"
        assert kwargs["query_params"]["end_date"] == "2024-12-31"
        assert kwargs["query_params"]["options"] == {"some": "option"}

    def test_export_service_error_returns_500(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.export_report_sync.side_effect = ValueError("Export failed")

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/reports",
                json={"report_type": "supported_villages"},
            )

        assert resp.status_code == 500
        # W1-T8：内部异常细节不再直出，统一为通用文案
        assert "报表导出失败" in resp.json()["detail"]


class TestExportVillages:
    """POST /api/v1/async-export/villages"""

    def test_unauthenticated(self, client):
        resp = client.post(f"{BASE}/villages")
        assert resp.status_code == 401

    def test_sync_path_small_dataset(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.should_use_async.return_value = False
        mock_svc.export_supported_villages_sync.return_value = (b"sync data", "villages.xlsx", 100)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/villages",
                json={"village_name": "test"},
            )

        assert resp.status_code == 200
        assert resp.content == b"sync data"
        mock_svc.export_supported_villages_sync.assert_called_once()
        mock_svc.should_use_async.assert_called_once()

    def test_async_path_force_async(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_task = MagicMock()
        mock_task.task_id = "async-task-123"
        mock_svc.export_supported_villages_async = AsyncMock(return_value=mock_task)
        mock_svc.estimate_record_count.return_value = 6000

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/villages?force_async=true",
                json={"village_name": "test"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "async"
        assert data["task_id"] == "async-task-123"
        assert data["record_count"] == 6000
        assert "提示信息" in data["message"] or "message" in data
        mock_svc.export_supported_villages_async.assert_called_once()
        mock_svc.should_use_async.assert_not_called()

    def test_async_path_large_dataset(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.should_use_async.return_value = True
        mock_task = MagicMock()
        mock_task.task_id = "async-task-456"
        mock_svc.export_supported_villages_async = AsyncMock(return_value=mock_task)
        mock_svc.estimate_record_count.return_value = 6000

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(
                f"{BASE}/villages",
                json={},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "async"
        assert data["task_id"] == "async-task-456"
        assert data["record_count"] == 6000
        mock_svc.should_use_async.assert_called_once()

    def test_no_filters_sync(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.should_use_async.return_value = False
        mock_svc.export_supported_villages_sync.return_value = (b"no filter data", "all.xlsx", 0)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.post(f"{BASE}/villages")

        assert resp.status_code == 200
        assert resp.content == b"no filter data"


class TestGetExportStatus:
    """GET /api/v1/async-export/status/{task_id}"""

    def test_unauthenticated(self, client):
        resp = client.get(f"{BASE}/status/task-1")
        assert resp.status_code == 401

    def test_task_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = None

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/status/nonexistent")

        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_other_user_no_permission(self, client_with_regular_user_auth):
        mock_task = MagicMock()
        mock_task.user_id = 999
        mock_task.status = "completed"
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_regular_user_auth.get(f"{BASE}/status/task-other")

        assert resp.status_code == 403

    def test_superuser_can_access_any_task(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 999
        mock_task.id = 1
        mock_task.task_id = "task-any"
        mock_task.export_type = "test"
        mock_task.status = "completed"
        mock_task.record_count = 10
        mock_task.file_name = "test.xlsx"
        mock_task.file_size = 100
        mock_task.error_message = None
        mock_task.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.expires_at = None
        mock_task.is_downloadable = True
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/status/task-any")

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-any"
        assert data["status"] == "completed"
        assert data["id"] == 1

    def test_success(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.id = 1
        mock_task.task_id = "task-success"
        mock_task.export_type = "supported_villages"
        mock_task.status = "completed"
        mock_task.record_count = 42
        mock_task.file_name = "export.xlsx"
        mock_task.file_size = 2048
        mock_task.error_message = None
        mock_task.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_task.started_at = datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc)
        mock_task.completed_at = datetime(2025, 1, 1, 0, 2, tzinfo=timezone.utc)
        mock_task.expires_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        mock_task.is_downloadable = True
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/status/task-success")

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "task-success"
        assert data["status"] == "completed"
        assert data["record_count"] == 42
        assert data["file_name"] == "export.xlsx"
        assert data["file_size"] == 2048
        assert data["is_downloadable"] is True
        assert data["export_type"] == "supported_villages"


class TestDownloadExportFile:
    """GET /api/v1/async-export/download/{task_id}"""

    def test_unauthenticated(self, client):
        resp = client.get(f"{BASE}/download/task-1")
        assert resp.status_code == 401

    def test_task_not_found(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = None

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/nonexistent")

        assert resp.status_code == 404

    def test_other_user_no_permission(self, client_with_regular_user_auth):
        mock_task = MagicMock()
        mock_task.user_id = 999
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_regular_user_auth.get(f"{BASE}/download/task-other")

        assert resp.status_code == 403

    def test_processing_status_returns_400(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.status = ExportStatus.PROCESSING.value
        mock_task.is_downloadable = False
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-processing")

        assert resp.status_code == 400
        assert "正在处理中" in resp.json()["detail"]

    def test_failed_status_returns_400(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.status = ExportStatus.FAILED.value
        mock_task.is_downloadable = False
        mock_task.error_message = "Out of memory"
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-failed")

        assert resp.status_code == 400
        assert "Out of memory" in resp.json()["detail"]

    def test_expired_status_returns_400(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.status = ExportStatus.EXPIRED.value
        mock_task.is_downloadable = False
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-expired")

        assert resp.status_code == 400
        assert "已过期" in resp.json()["detail"]

    def test_not_downloadable_unknown_status(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.status = "pending"
        mock_task.is_downloadable = False
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-pending")

        assert resp.status_code == 400
        assert "不可下载" in resp.json()["detail"]

    def test_file_not_found_after_downloadable_check(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.status = ExportStatus.COMPLETED.value
        mock_task.is_downloadable = True
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task
        mock_svc.get_export_file.return_value = None

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-nofile")

        assert resp.status_code == 404
        assert "文件不存在" in resp.json()["detail"]

    def test_download_success(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 1
        mock_task.status = ExportStatus.COMPLETED.value
        mock_task.is_downloadable = True
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task
        mock_svc.get_export_file.return_value = (b"file content", "export.xlsx")

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-success")

        assert resp.status_code == 200
        assert resp.content == b"file content"
        assert "filename*=UTF-8''export.xlsx" in resp.headers["content-disposition"]

    def test_superuser_can_download_any_task(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.user_id = 999
        mock_task.status = ExportStatus.COMPLETED.value
        mock_task.is_downloadable = True
        mock_svc = MagicMock()
        mock_svc.get_export_task.return_value = mock_task
        mock_svc.get_export_file.return_value = (b"data", "any.xlsx")

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/download/task-any")

        assert resp.status_code == 200
        assert resp.content == b"data"


class TestGetExportTasks:
    """GET /api/v1/async-export/tasks"""

    def test_unauthenticated(self, client):
        resp = client.get(f"{BASE}/tasks")
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.task_id = "task-1"
        mock_task.export_type = "supported_villages"
        mock_task.status = "completed"
        mock_task.record_count = 42
        mock_task.file_name = "export.xlsx"
        mock_task.file_size = 2048
        mock_task.error_message = None
        mock_task.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_task.started_at = None
        mock_task.completed_at = None
        mock_task.expires_at = None
        mock_task.is_downloadable = True

        mock_svc = MagicMock()
        mock_svc.get_user_export_tasks.return_value = ([mock_task], 1)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/tasks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["items"]) == 1
        assert data["items"][0]["task_id"] == "task-1"
        assert data["items"][0]["status"] == "completed"

    def test_with_status_filter_and_pagination(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_user_export_tasks.return_value = ([], 0)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/tasks?status=pending&page=2&page_size=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["page"] == 2
        assert data["page_size"] == 10
        mock_svc.get_user_export_tasks.assert_called_once_with(
            user_id=1, page=2, page_size=10, status="pending",
        )

    def test_empty_list(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_user_export_tasks.return_value = ([], 0)

        with patch("app.api.v1.import_export.async_export.AsyncExportService", return_value=mock_svc):
            resp = client_with_mocked_auth.get(f"{BASE}/tasks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0
