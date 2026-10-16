from unittest.mock import MagicMock, patch, AsyncMock


class TestGetApiPerformanceStats:
    """R27-M28：SQL 聚合 + 端点过滤 + NULL 防御（真实 SQLite 验证过滤行为）。

    旧实现把 24h 内全部 ORM 行载入内存，且 response_time_ms 为 NULL 时
    ``.sort()`` 抛 TypeError —— mock 断言 filter 调用无法证明返回集口径，
    故此处用真实库插入数据验证。
    """

    @staticmethod
    def _make_db():
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models.monitoring import APIMetric

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        APIMetric.__table__.create(engine)
        return sessionmaker(bind=engine)()

    @staticmethod
    def _add(db, endpoint, response_time_ms, status_code, minutes_ago=0):
        from datetime import datetime, timedelta, timezone

        from app.models.monitoring import APIMetric

        db.add(
            APIMetric(
                endpoint=endpoint,
                method="GET",
                response_time_ms=response_time_ms,
                status_code=status_code,
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            )
        )

    def test_no_metrics(self):
        from app.services.monitoring_service import MonitoringService

        result = MonitoringService.get_api_performance_stats(self._make_db())
        assert result == {
            "total_requests": 0,
            "avg_response_time_ms": 0,
            "p50_response_time_ms": 0,
            "p95_response_time_ms": 0,
            "p99_response_time_ms": 0,
            "error_rate": 0,
        }

    def test_aggregates_and_percentiles(self):
        from app.services.monitoring_service import MonitoringService

        db = self._make_db()
        for rt, code in [(100.0, 200), (200.0, 200), (300.0, 200), (400.0, 500)]:
            self._add(db, "/api/a", rt, code)
        db.commit()

        result = MonitoringService.get_api_performance_stats(db)
        assert result["total_requests"] == 4
        assert result["avg_response_time_ms"] == 250.0
        assert result["p50_response_time_ms"] == 300.0
        assert result["p95_response_time_ms"] == 400.0
        assert result["p99_response_time_ms"] == 400.0
        assert result["error_rate"] == 25.0

    def test_endpoint_filter(self):
        from app.services.monitoring_service import MonitoringService

        db = self._make_db()
        self._add(db, "/api/a", 100.0, 200)
        self._add(db, "/api/b", 500.0, 500)
        db.commit()

        result = MonitoringService.get_api_performance_stats(db, endpoint="/api/a")
        assert result["total_requests"] == 1
        assert result["avg_response_time_ms"] == 100.0
        assert result["error_rate"] == 0.0

    def test_time_window_excludes_old_rows(self):
        from app.services.monitoring_service import MonitoringService

        db = self._make_db()
        self._add(db, "/api/a", 100.0, 200)
        self._add(db, "/api/a", 900.0, 200, minutes_ago=48 * 60)
        db.commit()

        result = MonitoringService.get_api_performance_stats(db, hours=24)
        assert result["total_requests"] == 1
        assert result["avg_response_time_ms"] == 100.0


class TestPercentile:
    def test_empty(self):
        from app.services.monitoring_service import MonitoringService
        assert MonitoringService._percentile([], 50) == 0.0

    def test_single_value(self):
        from app.services.monitoring_service import MonitoringService
        assert MonitoringService._percentile([42.0], 50) == 42.0

    def test_multiple_values(self):
        from app.services.monitoring_service import MonitoringService
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        assert MonitoringService._percentile(values, 50) == 60.0
        assert MonitoringService._percentile(values, 99) == 100.0


def _mock_case(*args, **kwargs):
    return MagicMock()


def _mock_label(self):
    return self


class TestGetEndpointStats:
    def test_no_results(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_q = MagicMock()
        mock_query.filter.return_value = mock_q
        mock_q.group_by.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = []
        with patch("app.services.monitoring_service.func.case", side_effect=_mock_case):
            with patch("app.services.monitoring_service.func.count", return_value=MagicMock()):
                with patch("app.services.monitoring_service.func.avg", return_value=MagicMock()):
                    with patch("app.services.monitoring_service.func.sum") as mock_sum:
                        mock_sum.return_value.label = _mock_label
                        result = MonitoringService.get_endpoint_stats(mock_db)
                        assert result == []

    def test_with_results(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_q = MagicMock()
        mock_query.filter.return_value = mock_q
        mock_q.group_by.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_stat = MagicMock()
        mock_stat.endpoint = "/api/test"
        mock_stat.total_requests = 10
        mock_stat.avg_response_time = 150.5
        mock_stat.error_count = 2
        mock_q.all.return_value = [mock_stat]
        with patch("app.services.monitoring_service.func.case", side_effect=_mock_case):
            with patch("app.services.monitoring_service.func.count", return_value=MagicMock()):
                with patch("app.services.monitoring_service.func.avg", return_value=MagicMock()):
                    with patch("app.services.monitoring_service.func.sum") as mock_sum:
                        mock_sum.return_value.label = _mock_label
                        result = MonitoringService.get_endpoint_stats(mock_db)
                        assert len(result) == 1
                        assert result[0]["endpoint"] == "/api/test"
                        assert result[0]["error_rate"] == 20.0


class TestGetErrorStats:
    def test_no_errors(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        result = MonitoringService.get_error_stats(mock_db)
        assert result["total_errors"] == 0
        assert result["error_by_code"] == {}

    def test_with_errors(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        stat1 = MagicMock()
        stat1.status_code = 500
        stat1.count = 3
        stat2 = MagicMock()
        stat2.status_code = 404
        stat2.count = 2
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [stat1, stat2]
        result = MonitoringService.get_error_stats(mock_db)
        assert result["total_errors"] == 5
        assert result["error_by_code"]["500"] == 3
        assert result["error_by_code"]["404"] == 2


class TestGetResourceStats:
    @patch("app.services.monitoring_service.psutil")
    def test_success(self, mock_psutil):
        from app.services.monitoring_service import MonitoringService
        mock_psutil.cpu_percent.return_value = 45.5
        mock_mem = MagicMock()
        mock_mem.percent = 60.0
        mock_mem.used = 2 * 1024 * 1024 * 1024
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_disk = MagicMock()
        mock_disk.percent = 70.0
        mock_disk.used = 100 * 1024 * 1024 * 1024
        mock_disk.total = 500 * 1024 * 1024 * 1024
        mock_psutil.disk_usage.return_value = mock_disk
        result = MonitoringService.get_resource_stats()
        assert result["cpu_percent"] == 45.5
        assert result["memory_percent"] == 60.0
        assert result["disk_percent"] == 70.0

    @patch("app.services.monitoring_service.psutil")
    def test_exception(self, mock_psutil):
        from app.services.monitoring_service import MonitoringService
        mock_psutil.cpu_percent.side_effect = Exception("psutil error")
        result = MonitoringService.get_resource_stats()
        assert result == {}


class TestCheckAlerts:
    def test_no_rules(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        MonitoringService.check_alerts(mock_db)

    def test_rule_check_exception(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.name = "test_rule"
        mock_db.query.return_value.filter.return_value.all.return_value = [rule]
        with patch.object(MonitoringService, "_check_rule", side_effect=Exception("check error")):
            MonitoringService.check_alerts(mock_db)


class TestCheckRule:
    def test_response_time_below_threshold(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "response_time"
        rule.threshold = 500.0
        rule.duration_seconds = 60
        mock_db.query.return_value.filter.return_value.scalar.return_value = None
        MonitoringService._check_rule(mock_db, rule)

    def test_response_time_above_threshold(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "response_time"
        rule.threshold = 200.0
        rule.duration_seconds = 60
        rule.id = 1
        rule.name = "RT Rule"
        mock_db.query.return_value.filter.return_value.scalar.return_value = 300.0
        with patch.object(MonitoringService, "_trigger_alert") as mock_trigger:
            MonitoringService._check_rule(mock_db, rule)
            mock_trigger.assert_called_once()

    def test_error_rate_below_threshold(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "error_rate"
        rule.threshold = 10.0
        rule.duration_seconds = 60
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [100, 5]
        MonitoringService._check_rule(mock_db, rule)

    def test_error_rate_above_threshold(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "error_rate"
        rule.threshold = 10.0
        rule.duration_seconds = 60
        rule.id = 1
        rule.name = "ER Rule"
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [100, 50]
        with patch.object(MonitoringService, "_trigger_alert") as mock_trigger:
            MonitoringService._check_rule(mock_db, rule)
            mock_trigger.assert_called_once()

    def test_error_rate_zero_total(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "error_rate"
        rule.threshold = 10.0
        rule.duration_seconds = 60
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [0, 0]
        MonitoringService._check_rule(mock_db, rule)

    def test_resource_usage_below_threshold(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "resource"
        rule.threshold = 90.0
        rule.duration_seconds = 60
        with patch.object(MonitoringService, "get_resource_stats", return_value={"cpu_percent": 50.0}):
            MonitoringService._check_rule(mock_db, rule)

    def test_resource_usage_above_threshold(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "resource"
        rule.threshold = 80.0
        rule.duration_seconds = 60
        rule.id = 1
        rule.name = "CPU Rule"
        with patch.object(MonitoringService, "get_resource_stats", return_value={"cpu_percent": 95.0}):
            with patch.object(MonitoringService, "_trigger_alert") as mock_trigger:
                MonitoringService._check_rule(mock_db, rule)
                mock_trigger.assert_called_once()

    def test_unknown_metric_type(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.metric_type = "unknown_type"
        rule.duration_seconds = 60
        MonitoringService._check_rule(mock_db, rule)


class TestTriggerAlert:
    def test_existing_unresolved_alert(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.id = 1
        existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        MonitoringService._trigger_alert(mock_db, rule, "msg", 50.0)
        mock_db.add.assert_not_called()

    def test_triggers_new_alert(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.id = 1
        rule.name = "Test Rule"
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(MonitoringService, "_send_alert_notification", return_value=AsyncMock()) as mock_send:
            with patch("app.services.monitoring_service.create_background_task") as mock_create_task:
                mock_create_task.return_value = MagicMock()
                MonitoringService._trigger_alert(mock_db, rule, "test message", 75.0)
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
                mock_create_task.assert_called_once()

    def test_triggers_no_event_loop(self):
        from app.services.monitoring_service import MonitoringService
        mock_db = MagicMock()
        rule = MagicMock()
        rule.id = 1
        rule.name = "Test Rule"
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(MonitoringService, "_send_alert_notification") as mock_send:
            with patch("app.services.monitoring_service.create_background_task", return_value=None) as mock_create:
                with patch("app.services.monitoring_service.threading.Thread") as mock_thread:
                    MonitoringService._trigger_alert(mock_db, rule, "test message", 75.0)
                    mock_create.assert_called_once()
                    mock_thread.assert_called_once()


class TestSendAlertNotification:
    def test_no_settings(self):
        from app.services.monitoring_service import MonitoringService
        rule = MagicMock()
        rule.name = "Rule"
        import asyncio
        asyncio.run(MonitoringService._send_alert_notification(rule, "msg"))

    @patch("app.services.monitoring_service.settings")
    def test_email_alert_error(self, mock_settings):
        from app.services.monitoring_service import MonitoringService
        mock_settings.ALERT_EMAIL_RECIPIENTS = ["admin@test.com"]
        from app.services.alert_service import AlertService
        rule = MagicMock()
        rule.name = "Rule"
        with patch.object(AlertService, "send_email_alert", side_effect=Exception("SMTP error")):
            import asyncio
            asyncio.run(MonitoringService._send_alert_notification(rule, "msg"))

    @patch("app.services.monitoring_service.settings")
    def test_webhook_alert_error(self, mock_settings):
        from app.services.monitoring_service import MonitoringService
        mock_settings.ALERT_WEBHOOK_URL = "http://hook.test"
        mock_settings.ALERT_WEBHOOK_TYPE = "dingtalk"
        from app.services.alert_service import AlertService
        rule = MagicMock()
        rule.name = "Rule"
        with patch.object(AlertService, "send_webhook_alert", side_effect=Exception("Webhook error")):
            import asyncio
            asyncio.run(MonitoringService._send_alert_notification(rule, "msg"))
