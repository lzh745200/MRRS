import pytest
from datetime import datetime
from unittest.mock import MagicMock


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def audit_svc(mock_db):
    from app.services.audit_service import AuditService
    return AuditService(db=mock_db)


@pytest.fixture
def security_svc(mock_db):
    from app.services.audit_service import SecurityEventService
    return SecurityEventService(db=mock_db)


class TestAuditContext:
    def test_create_default(self):
        from app.services.audit_service import AuditContext
        ctx = AuditContext()
        assert ctx.user_id is None
        assert ctx.username is None
        assert ctx.user_ip is None
        assert ctx.user_agent is None
        assert ctx.session_id is None
        assert ctx.trace_id is None
        assert ctx.request_path is None
        assert ctx.request_method is None
        assert isinstance(ctx.start_time, datetime)

    def test_create_with_all_values(self):
        from app.services.audit_service import AuditContext
        ctx = AuditContext(
            user_id=1, username="admin", user_ip="127.0.0.1",
            user_agent="Mozilla/5.0", session_id="sess1",
            trace_id="trace1", request_path="/api/test",
            request_method="POST",
        )
        assert ctx.user_id == 1
        assert ctx.username == "admin"
        assert ctx.user_ip == "127.0.0.1"
        assert ctx.user_agent == "Mozilla/5.0"
        assert ctx.session_id == "sess1"
        assert ctx.trace_id == "trace1"
        assert ctx.request_path == "/api/test"
        assert ctx.request_method == "POST"

    def test_to_dict(self):
        from app.services.audit_service import AuditContext
        ctx = AuditContext(user_id=1, username="admin", user_ip="127.0.0.1")
        d = ctx.to_dict()
        assert d["user_id"] == 1
        assert d["username"] == "admin"
        assert d["user_ip"] == "127.0.0.1"
        assert d["session_id"] is None

    def test_start_time_is_set(self):
        from app.services.audit_service import AuditContext
        ctx = AuditContext()
        assert isinstance(ctx.start_time, datetime)


class TestAuditService:
    def test_init(self, audit_svc, mock_db):
        assert audit_svc.db is mock_db

    def test_log_without_context(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log(action=AuditAction.CREATE, resource_type="project", resource_id="42")
        assert result is not None
        assert result.action == "create"
        assert result.resource_type == "project"
        assert result.resource_id == "42"
        assert result.user_id is None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(result)

    def test_log_with_context(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction, AuditContext
        ctx = AuditContext(user_id=1, username="admin", user_ip="127.0.0.1",
                           user_agent="agent", session_id="s", trace_id="t",
                           request_path="/p", request_method="GET")
        result = audit_svc.log(action=AuditAction.UPDATE, resource_type="user",
                               resource_id="5", context=ctx, old_value={"a": 1},
                               new_value={"a": 2}, error_message=None, duration_ms=100,
                               response_status=200, metadata={"source": "web"})
        assert result.user_id == 1
        assert result.username == "admin"
        assert result.user_ip == "127.0.0.1"
        assert result.duration_ms == 100
        assert result.response_status == 200
        assert result.metadata == {"source": "web"}
        mock_db.add.assert_called_once()

    def test_log_with_string_values(self, audit_svc, mock_db):
        result = audit_svc.log(action="custom_action", status="failed", level="error",
                               resource_type="test", resource_id="1")
        assert result.action == "custom_action"
        assert result.status == "failed"
        assert result.level == "error"

    def test_log_with_integer_resource_id(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log(action=AuditAction.READ, resource_type="file", resource_id=999)
        assert result.resource_id == "999"

    def test_log_with_none_resource_id(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log(action=AuditAction.READ, resource_type="file", resource_id=None)
        assert result.resource_id is None

    def test_log_create(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log_create(resource_type="project", resource_id=10, new_value={"name": "test"})
        assert result.action == AuditAction.CREATE.value
        assert result.resource_id == "10"
        assert result.new_value == {"name": "test"}

    def test_log_update(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log_update(resource_type="project", resource_id=10,
                                       old_value={"name": "old"}, new_value={"name": "new"})
        assert result.action == AuditAction.UPDATE.value
        assert result.old_value == {"name": "old"}
        assert result.new_value == {"name": "new"}

    def test_log_delete(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log_delete(resource_type="project", resource_id=10,
                                       old_value={"name": "gone"})
        assert result.action == AuditAction.DELETE.value
        assert result.old_value == {"name": "gone"}

    def test_log_read_with_resource_id(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log_read(resource_type="project", resource_id="abc")
        assert result.action == AuditAction.READ.value
        assert result.resource_id == "abc"

    def test_log_read_without_resource_id(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction
        result = audit_svc.log_read(resource_type="project")
        assert result.action == AuditAction.READ.value
        assert result.resource_id is None

    def test_log_login_success(self, audit_svc, mock_db):
        result = audit_svc.log_login(username="admin", success=True, user_id=1,
                                      user_ip="127.0.0.1", user_agent="agent")
        assert result.action == "login"
        assert result.level == "info"
        assert result.status == "success"
        mock_db.add.assert_called()  # called for LoginAttempt + AuditLog

    def test_log_login_failed(self, audit_svc, mock_db):
        result = audit_svc.log_login(username="hacker", success=False,
                                      failure_reason="bad password")
        assert result.action == "login_failed"
        assert result.level == "warning"
        assert result.status == "failed"
        assert result.error_message == "bad password"

    def test_log_api_access_full(self, audit_svc, mock_db):
        result = audit_svc.log_api_access(
            endpoint="/api/projects", method="GET", user_id=1,
            username="admin", ip_address="127.0.0.1", user_agent="agent",
            request_params={"page": 1}, response_status=200,
            response_time_ms=42, session_id="sess1",
        )
        assert result.endpoint == "/api/projects"
        assert result.method == "GET"
        assert result.user_id == 1
        assert result.response_status == 200
        assert result.response_time_ms == 42
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(result)

    def test_log_api_access_minimal(self, audit_svc, mock_db):
        result = audit_svc.log_api_access(endpoint="/health", method="GET")
        assert result.endpoint == "/health"
        assert result.method == "GET"

    def test_log_export_success(self, audit_svc, mock_db):
        from app.services.audit_service import AuditStatus
        result = audit_svc.log_export(
            user_id=1, username="admin", export_type="projects",
            data_types=["name", "budget"], file_format="xlsx",
            record_count=100, status=AuditStatus.SUCCESS,
        )
        assert result.export_type == "projects"
        assert result.file_format == "xlsx"
        assert result.record_count == 100
        assert result.status == "success"
        mock_db.add.assert_called()

    def test_log_export_failed(self, audit_svc, mock_db):
        result = audit_svc.log_export(
            user_id=2, username="user", export_type="funds",
            data_types=["amount"], file_format="csv",
            status="failed", error_message="Out of memory",
        )
        assert result.status == "failed"
        assert result.error_message == "Out of memory"

    def test_log_export_minimal(self, audit_svc, mock_db):
        result = audit_svc.log_export(
            user_id=1, username="op", export_type="report",
            data_types=["x"], file_format="pdf",
        )
        assert result.record_count is None

    def test_query_audit_logs_no_filters(self, audit_svc, mock_db):
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"id": 1, "action": "create"}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_log]
        mock_db.query.return_value.count.return_value = 1

        result = audit_svc.query_audit_logs()
        assert result["total"] == 1
        assert result["page"] == 1
        assert result["page_size"] == 50
        assert len(result["items"]) == 1

    def test_query_audit_logs_all_filters(self, audit_svc, mock_db):
        from app.services.audit_service import AuditAction, AuditStatus, AuditLevel
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"id": 2, "action": "update"}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_log]
        f = mock_db.query.return_value.filter.return_value
        f.filter.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 1

        result = audit_svc.query_audit_logs(
            user_id=1, action=AuditAction.UPDATE, resource_type="project",
            start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31),
            status=AuditStatus.SUCCESS, level=AuditLevel.INFO,
            page=2, page_size=10,
        )
        assert result["total"] == 1
        assert result["page"] == 2
        assert result["page_size"] == 10

    def test_query_audit_logs_string_filters(self, audit_svc, mock_db):
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"id": 3}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_log]
        f = mock_db.query.return_value.filter.return_value
        f.filter.return_value.filter.return_value.count.return_value = 1

        result = audit_svc.query_audit_logs(
            action="delete", status="failed", level="error",
        )
        assert result["total"] == 1

    def test_get_audit_stats_no_dates(self, audit_svc, mock_db):
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"id": 1, "action": "create"}

        mock_q = mock_db.query.return_value
        mock_q.count.return_value = 10

        me1, me2, me3, me4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        me1.group_by.return_value.all.return_value = [("create", 5), ("login", 3)]
        me2.group_by.return_value.all.return_value = [("success", 7), ("failed", 1)]
        me3.group_by.return_value.all.return_value = [("info", 8)]
        me4.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [("admin", 10)]
        mock_q.with_entities.side_effect = [me1, me2, me3, me4]

        mock_q.order_by.return_value.limit.return_value.all.return_value = [mock_log]

        result = audit_svc.get_audit_stats()
        assert result["total_count"] == 10
        assert result["by_action"]["create"] == 5
        assert result["by_status"]["success"] == 7
        assert result["by_level"]["info"] == 8
        assert result["top_users"]["admin"] == 10
        assert len(result["recent_activity"]) == 1

    def test_get_audit_stats_with_dates(self, audit_svc, mock_db):
        mock_log = MagicMock()
        mock_log.to_dict.return_value = {"id": 2}
        mock_q = mock_db.query.return_value
        mock_q.filter.return_value.filter.return_value.count.return_value = 3

        me1, me2, me3, me4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        me1.group_by.return_value.all.return_value = [("read", 3)]
        me2.group_by.return_value.all.return_value = [("success", 3)]
        me3.group_by.return_value.all.return_value = [("info", 3)]
        me4.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [("u", 3)]
        mock_q.with_entities.side_effect = [me1, me2, me3, me4]
        mock_q.order_by.return_value.limit.return_value.all.return_value = [mock_log]

        result = audit_svc.get_audit_stats(
            start_date=datetime(2024, 6, 1), end_date=datetime(2024, 7, 1),
        )
        assert result["total_count"] == 3


class TestSecurityEventService:
    def test_init(self, security_svc, mock_db):
        assert security_svc.db is mock_db

    def test_create_event_full(self, security_svc, mock_db):
        result = security_svc.create_event(
            event_type="unauthorized_access", severity="high",
            description="Access denied", source_ip="10.0.0.1",
            user_id=1, username="admin", details={"path": "/admin"},
            affected_resources=["/admin/config"],
        )
        assert result.event_type == "unauthorized_access"
        assert result.severity == "high"
        assert result.description == "Access denied"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(result)

    def test_create_event_minimal(self, security_svc, mock_db):
        result = security_svc.create_event(
            event_type="info", severity="low", description="Just info",
        )
        assert result.event_type == "info"
        assert result.severity == "low"

    def test_log_failed_login_low(self, security_svc, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        result = security_svc.log_failed_login(
            username="testuser", ip_address="10.0.0.1", reason="Invalid credentials",
        )
        assert result.severity == "low"
        assert result.event_type == "failed_login"
        assert "testuser" in result.description

    def test_log_failed_login_medium(self, security_svc, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 3
        result = security_svc.log_failed_login(
            username="testuser", ip_address="10.0.0.1",
        )
        assert result.severity == "medium"
        assert result.event_type == "multiple_failed_logins"

    def test_log_failed_login_high(self, security_svc, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        result = security_svc.log_failed_login(
            username="testuser", ip_address="10.0.0.1",
        )
        assert result.severity == "high"
        assert result.event_type == "brute_force_attempt"

    def test_resolve_event_found(self, security_svc, mock_db):
        mock_event = MagicMock()
        mock_event.resolved = False
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event

        result = security_svc.resolve_event(event_id=1, resolved_by=42, resolution_notes="Fixed")
        assert result is mock_event
        assert result.resolved is True
        assert result.resolved_by == 42
        assert result.resolution_notes == "Fixed"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_event)

    def test_resolve_event_not_found(self, security_svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = security_svc.resolve_event(event_id=999, resolved_by=1, resolution_notes="N/A")
        assert result is None
        mock_db.commit.assert_not_called()

    def test_get_events_no_filters(self, security_svc, mock_db):
        mock_event = MagicMock()
        mock_event.to_dict.return_value = {"id": 1, "event_type": "test"}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
        mock_db.query.return_value.count.return_value = 1

        result = security_svc.get_events()
        assert result["total"] == 1
        assert len(result["items"]) == 1

    def test_get_events_all_filters(self, security_svc, mock_db):
        mock_event = MagicMock()
        mock_event.to_dict.return_value = {"id": 2}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
        f = mock_db.query.return_value.filter.return_value
        f.filter.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 1

        result = security_svc.get_events(
            severity="high", event_type="breach", resolved=True,
            start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31),
            page=2, page_size=10,
        )
        assert result["total"] == 1
        assert result["page"] == 2

    def test_get_events_with_resolved_false(self, security_svc, mock_db):
        mock_event = MagicMock()
        mock_event.to_dict.return_value = {"id": 3}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 1

        result = security_svc.get_events(resolved=False, severity="low")
        assert result["total"] == 1

    def test_get_events_with_resolved_none(self, security_svc, mock_db):
        mock_event = MagicMock()
        mock_event.to_dict.return_value = {"id": 4}
        mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]
        mock_db.query.return_value.count.return_value = 1

        result = security_svc.get_events(resolved=None)
        assert result["total"] == 1

    def test_get_security_stats(self, security_svc, mock_db):
        mock_event = MagicMock()
        mock_event.to_dict.return_value = {"id": 1}
        mock_q = mock_db.query.return_value

        mock_q.group_by.return_value.all.return_value = [("high", 5), ("low", 3)]
        mock_q.filter.return_value.group_by.return_value.all.return_value = [("high", 2)]
        mock_q.order_by.return_value.limit.return_value.all.return_value = [mock_event]
        mock_q.count.return_value = 8
        mock_q.filter.return_value.count.return_value = 2

        result = security_svc.get_security_stats()
        assert result["total_events"] == 8
        assert result["unresolved_count"] == 2
        assert result["by_severity"]["high"] == 5
        assert result["by_severity"]["low"] == 3
        assert result["unresolved_by_severity"]["high"] == 2
        assert len(result["recent_events"]) == 1
