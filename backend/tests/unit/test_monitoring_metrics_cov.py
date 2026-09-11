"""app.api.v1.monitoring.metrics 覆盖率攻坚测试

直接 async 调用端点函数，覆盖业务指标、Prometheus 导出、性能面板三个端点。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.monitoring.metrics as m


class TestGetBusinessMetrics:
    async def test_returns_service_metrics(self):
        fake = {"fund_approval_rate": 0.9, "user_activity": {"dau": 5}}
        svc = MagicMock()
        svc.get_all_metrics.return_value = fake
        with patch.object(m, "business_metrics_service", svc):
            result = await m.get_business_metrics(db=MagicMock(), current_user=MagicMock())
        assert result == fake
        svc.get_all_metrics.assert_called_once_with()


class TestGetPrometheusMetrics:
    async def test_plain_text_response(self):
        svc = MagicMock()
        svc.to_prometheus_format.return_value = "fund_approval_rate 0.9\n"
        with patch.object(m, "business_metrics_service", svc):
            result = await m.get_prometheus_metrics()
        assert result.media_type == "text/plain; charset=utf-8"
        assert result.body == b"fund_approval_rate 0.9\n"
        svc.to_prometheus_format.assert_called_once_with()


class TestGetPerformanceDashboard:
    async def test_non_superuser_forbidden(self):
        user = SimpleNamespace(is_superuser=False)
        with pytest.raises(HTTPException) as exc_info:
            await m.get_performance_dashboard(current_user=user)
        assert exc_info.value.status_code == 403
        assert "需要管理员权限" in exc_info.value.detail

    async def test_superuser_collects_db_stats(self):
        user = SimpleNamespace(is_superuser=True)
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 5
        session_local = MagicMock(return_value=db)
        with patch("app.core.database.SessionLocal", session_local):
            result = await m.get_performance_dashboard(current_user=user)
        assert result["code"] == 200
        assert result["success"] is True
        data = result["data"]
        assert "http_metrics" in data
        # P2-3：慢请求/慢 SQL 可观测字段
        assert "slow_api" in data
        assert "slow_sql" in data
        assert "slow_stats" in data
        assert isinstance(data["slow_api"], list)
        assert "total_requests" in data["slow_stats"]
        # 白名单 6 张表均统计为 scalar 值
        for table in ("users", "funds", "projects", "supported_villages", "schools", "audit_logs"):
            assert data["db_stats"][table] == 5
        # SQLite 下额外统计库文件大小
        assert "db_size_mb" in data["db_stats"]
        db.close.assert_called_once_with()

    async def test_db_failure_returns_empty_stats(self):
        user = SimpleNamespace(is_superuser=True)
        with patch("app.core.database.SessionLocal", side_effect=RuntimeError("db down")):
            result = await m.get_performance_dashboard(current_user=user)
        assert result["code"] == 200
        assert result["data"]["db_stats"] == {}
        assert "http_metrics" in result["data"]
