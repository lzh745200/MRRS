"""业务指标监控服务单元测试"""
import time
import pytest
from unittest.mock import MagicMock, patch
from app.services.business_metrics_service import BusinessMetricsService


@pytest.fixture
def service():
    return BusinessMetricsService()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture(autouse=True)
def patch_data_report_month():
    """DataReport model lacks report_month; add it as a mock descriptor."""
    import app.services.business_metrics_service as svc
    with patch.object(svc.DataReport, "report_month", MagicMock(), create=True):
        yield


class TestCache:
    def test_get_cached_miss(self, service):
        assert service._get_cached("nonexistent") is None

    def test_get_cached_hit(self, service):
        service._set_cached("key1", {"data": 42})
        assert service._get_cached("key1") == {"data": 42}

    def test_get_cached_expired(self, service):
        service._cache["expired_key"] = ({"data": 1}, time.time() - 120)
        assert service._get_cached("expired_key") is None

    def test_set_cached(self, service):
        service._set_cached("key2", "value")
        assert "key2" in service._cache
        value, ts = service._cache["key2"]
        assert value == "value"
        assert time.time() - ts < 1


class TestGetFundApprovalMetrics:
    def test_cache_hit(self, service, mock_db):
        cached_value = {"total_approvals_30d": 10}
        service._set_cached("fund_approval_metrics", cached_value)
        result = service.get_fund_approval_metrics(mock_db)
        assert result == cached_value
        mock_db.query.assert_not_called()

    def test_cache_miss_with_approvals(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [20, 15, 10, 5]
        mock_query.filter.return_value.scalar.return_value = 2.5
        result = service.get_fund_approval_metrics(mock_db)
        assert result["total_approvals_30d"] == 20
        assert result["approved_count_30d"] == 10
        assert result["rejected_count_30d"] == 5
        assert result["pending_count"] == 5
        assert result["approval_success_rate"] == 66.67
        assert result["avg_approval_time_hours"] == 2.5

    def test_no_decided_approvals_returns_zero_rate(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [5, 0, 0, 3]
        mock_query.filter.return_value.scalar.return_value = None
        result = service.get_fund_approval_metrics(mock_db)
        assert result["approval_success_rate"] == 0
        assert result["avg_approval_time_hours"] == 0


class TestGetFundUtilizationMetrics:
    def test_cache_hit(self, service, mock_db):
        cached_value = {"total_funds": 100}
        service._set_cached("fund_utilization_metrics", cached_value)
        result = service.get_fund_utilization_metrics(mock_db)
        assert result == cached_value
        mock_db.query.assert_not_called()

    def test_cache_miss_with_data(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value.all.return_value = [("completed", 5, 50000.0)]
        mock_query.scalar.side_effect = [10, 100000.0]
        result = service.get_fund_utilization_metrics(mock_db)
        assert result["total_funds"] == 10
        assert result["total_amount"] == 100000.0
        assert result["completed_funds"] == 5
        assert result["completed_amount"] == 50000.0
        assert result["allocation_rate"] == 50.0

    def test_no_total_amount_returns_zero_rate(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value.all.return_value = []
        mock_query.scalar.side_effect = [0, 0]
        result = service.get_fund_utilization_metrics(mock_db)
        assert result["total_funds"] == 0
        assert result["total_amount"] == 0
        assert result["allocation_rate"] == 0

    def test_status_distribution_missing_completed(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value.all.return_value = [("pending", 3, 30000.0)]
        mock_query.scalar.side_effect = [3, 30000.0]
        result = service.get_fund_utilization_metrics(mock_db)
        assert result["completed_funds"] == 0
        assert result["completed_amount"] == 0
        assert result["allocation_rate"] == 0

    def test_null_amount_handled(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value.all.return_value = [("completed", 2, None)]
        mock_query.scalar.side_effect = [2, 0]
        result = service.get_fund_utilization_metrics(mock_db)
        assert result["completed_amount"] == 0.0


class TestGetDataReportMetrics:
    def test_cache_hit(self, service, mock_db):
        cached_value = {"expected_reports": 10}
        service._set_cached("data_report_metrics", cached_value)
        result = service.get_data_report_metrics(mock_db)
        assert result == cached_value
        mock_db.query.assert_not_called()

    def test_cache_miss_with_data(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [10, 8, 6]
        result = service.get_data_report_metrics(mock_db)
        assert result["expected_reports"] == 10
        assert result["completed_reports"] == 8
        assert result["report_completion_rate"] == 80.0
        assert result["on_time_reports"] == 6
        assert result["on_time_rate"] == 75.0

    def test_no_expected_reports_returns_zero(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [0, 0, 0]
        result = service.get_data_report_metrics(mock_db)
        assert result["expected_reports"] == 0
        assert result["report_completion_rate"] == 0
        assert result["on_time_rate"] == 0

    def test_no_completed_reports_returns_zero_on_time_rate(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [5, 0, 0]
        result = service.get_data_report_metrics(mock_db)
        assert result["report_completion_rate"] == 0
        assert result["on_time_rate"] == 0


class TestGetUserActivityMetrics:
    def test_cache_hit(self, service, mock_db):
        cached_value = {"active_users_7d": 5}
        service._set_cached("user_activity_metrics", cached_value)
        result = service.get_user_activity_metrics(mock_db)
        assert result == cached_value
        mock_db.query.assert_not_called()

    def test_cache_miss_with_data(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_active_query = MagicMock()
        mock_active_query.filter.return_value.distinct.return_value.count.return_value = 8
        mock_db.query.side_effect = [mock_active_query, mock_query, mock_query]
        mock_query.filter.return_value.count.return_value = 5
        mock_query.scalar.return_value = 100
        result = service.get_user_activity_metrics(mock_db)
        assert result["active_users_7d"] == 8
        assert result["new_users_30d"] == 5
        assert result["total_users"] == 100
        assert result["activity_rate"] == 8.0

    def test_no_total_users_returns_zero_rate(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_active_query = MagicMock()
        mock_active_query.filter.return_value.distinct.return_value.count.return_value = 0
        mock_db.query.side_effect = [mock_active_query, mock_query, mock_query]
        mock_query.filter.return_value.count.return_value = 0
        mock_query.scalar.return_value = 0
        result = service.get_user_activity_metrics(mock_db)
        assert result["activity_rate"] == 0


class TestGetSystemErrorMetrics:
    def test_cache_hit(self, service, mock_db):
        cached_value = {"total_requests_24h": 100}
        service._set_cached("system_error_metrics", cached_value)
        result = service.get_system_error_metrics(mock_db)
        assert result == cached_value
        mock_db.query.assert_not_called()

    def test_cache_miss_with_data(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [200, 10]
        result = service.get_system_error_metrics(mock_db)
        assert result["total_requests_24h"] == 200
        assert result["error_requests_24h"] == 10
        assert result["error_rate"] == 5.0

    def test_no_requests_returns_zero_rate(self, service, mock_db):
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.count.side_effect = [0, 0]
        result = service.get_system_error_metrics(mock_db)
        assert result["total_requests_24h"] == 0
        assert result["error_rate"] == 0


class TestGetAllMetrics:
    def test_creates_session_and_returns_all_metrics(self, service):
        mock_session = MagicMock()
        with patch("app.services.business_metrics_service.SessionLocal", return_value=mock_session):
            with patch.object(service, "get_fund_approval_metrics", return_value={"apr": 1}):
                with patch.object(service, "get_fund_utilization_metrics", return_value={"utl": 2}):
                    with patch.object(service, "get_data_report_metrics", return_value={"drm": 3}):
                        with patch.object(service, "get_user_activity_metrics", return_value={"uam": 4}):
                            with patch.object(service, "get_system_error_metrics", return_value={"sem": 5}):
                                result = service.get_all_metrics()
        assert result["fund_approval"] == {"apr": 1}
        assert result["fund_utilization"] == {"utl": 2}
        assert result["data_report"] == {"drm": 3}
        assert result["user_activity"] == {"uam": 4}
        assert result["system_error"] == {"sem": 5}
        assert "timestamp" in result
        mock_session.close.assert_called_once()

    def test_session_closed_on_exception(self, service):
        mock_session = MagicMock()
        with patch("app.services.business_metrics_service.SessionLocal", return_value=mock_session):
            with patch.object(service, "get_fund_approval_metrics", side_effect=ValueError("test error")):
                with pytest.raises(ValueError):
                    service.get_all_metrics()
        mock_session.close.assert_called_once()


class TestToPrometheusFormat:
    def test_returns_prometheus_format(self, service):
        mock_metrics = {
            "fund_approval": {"approval_success_rate": 85.5, "pending_count": 3, "avg_approval_time_hours": 24.0},
            "fund_utilization": {"allocation_rate": 60.0, "total_amount": 100000.0},
            "data_report": {"report_completion_rate": 90.0, "on_time_rate": 80.0},
            "user_activity": {"active_users_7d": 15, "new_users_30d": 5},
            "system_error": {"error_rate": 2.5, "total_requests_24h": 1000},
            "timestamp": "2025-01-01T00:00:00",
        }
        with patch.object(service, "get_all_metrics", return_value=mock_metrics):
            result = service.to_prometheus_format()
        assert "fund_approval_success_rate 85.5" in result
        assert "fund_pending_count 3" in result
        assert "fund_avg_approval_time_hours 24.0" in result
        assert "fund_allocation_rate 60.0" in result
        assert "fund_total_amount 100000.0" in result
        assert "data_report_completion_rate 90.0" in result
        assert "data_report_on_time_rate 80.0" in result
        assert "active_users_7d 15" in result
        assert "new_users_30d 5" in result
        assert "system_error_rate 2.5" in result
        assert "total_requests_24h 1000" in result

    def test_handles_missing_metrics(self, service):
        with patch.object(service, "get_all_metrics", return_value={}):
            result = service.to_prometheus_format()
        assert "fund_approval_success_rate 0" in result
        assert "fund_pending_count 0" in result
        assert "fund_allocation_rate 0" in result
        assert "data_report_completion_rate 0" in result
        assert "active_users_7d 0" in result
        assert "system_error_rate 0" in result
        assert "total_requests_24h 0" in result
