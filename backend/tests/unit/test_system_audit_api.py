"""Tests for app.api.v1.system.audit"""

from unittest import mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.unit

BASE = "/api/v1/system/audit"


def _delete_json(client, url, data):
    return client.request("DELETE", url, json=data)


@pytest.fixture()
def _mock_services():
    with mock.patch('app.api.v1.system.audit.AuditService') as as_mock, \
         mock.patch('app.api.v1.system.audit.SecurityEventService') as ses_mock:
        yield as_mock, ses_mock


def _normal_user():
    u = mock.MagicMock()
    u.role = "user"
    u.id = 2
    u.is_superuser = False
    return u


# ── Real-DB client (for endpoints that use db.query directly) ──


@pytest.fixture
def db_client():
    """TestClient + real SQLite session for direct-db routes."""
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.models import Base
    from fastapi.testclient import TestClient
    import app.core.database as _db_module

    # Ensure AuditLog is the real class, not a MagicMock from test pollution
    import app.models.audit as audit_mod
    saved_audit = getattr(audit_mod, 'AuditLog', None)
    if saved_audit is not None and not isinstance(saved_audit, type):
        # AuditLog was polluted - restore from SQLAlchemy registry
        # Find the real AuditLog in the registry
        for mapper in Base.registry.mappers:
            if mapper.class_.__name__ == 'AuditLog':
                audit_mod.AuditLog = mapper.class_
                break

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # 同时覆盖模块级 engine/SessionLocal，确保审计中间件等绕过 get_db 的代码路径
    # 也使用内存数据库，避免 "no such table: api_access_logs" 错误
    _original_engine = _db_module.engine
    _original_session_local = _db_module.SessionLocal
    _db_module.engine = engine
    _db_module.SessionLocal = TestingSessionLocal

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: mock.MagicMock(
        id=1, username="admin", role="admin", is_superuser=True,
    )

    try:
        yield TestClient(app, raise_server_exceptions=False), session
    finally:
        app.dependency_overrides = original_overrides
        _db_module.engine = _original_engine
        _db_module.SessionLocal = _original_session_local
        session.close()
        engine.dispose()


# ── Tests ──


class TestGetActions:
    URL = f"{BASE}/actions"

    def test_returns_list(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        assert len(data["actions"]) > 0


class TestGetLevels:
    URL = f"{BASE}/levels"

    def test_returns_list(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert "levels" in data
        assert len(data["levels"]) > 0


class TestGetAuditLogs:
    URL = f"{BASE}/logs"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_paginated_results(self, client_with_mocked_auth, _mock_services):
        as_mock, _ = _mock_services
        expected = {"items": [{"id": 1, "action": "create"}], "total": 1, "page": 1, "page_size": 50}
        as_mock.return_value.query_audit_logs.return_value = expected
        resp = client_with_mocked_auth.get(self.URL)
        assert resp.status_code == 200
        assert resp.json() == expected

    def test_passes_filters(self, client_with_mocked_auth, _mock_services):
        as_mock, _ = _mock_services
        as_mock.return_value.query_audit_logs.return_value = {"items": [], "total": 0, "page": 1, "page_size": 50}
        client_with_mocked_auth.get(self.URL, params={
            "user_id": 1, "action": "create", "resource_type": "user",
            "status": "success", "level": "info",
            "start_date": "2024-01-01T00:00:00", "end_date": "2024-12-31T23:59:59",
            "page": 1, "page_size": 20,
        })
        as_mock.return_value.query_audit_logs.assert_called_once_with(
            user_id=1, action=mock.ANY, resource_type="user",
            start_date=mock.ANY, end_date=mock.ANY, status=mock.ANY, level=mock.ANY,
            page=1, page_size=20,
        )

    def test_invalid_action_returns_400(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(self.URL, params={"action": "INVALID_ACTION"})
        assert resp.status_code == 400


class TestGetAuditLogDetail:
    URL = f"{BASE}/logs"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(f"{self.URL}/1")
        assert resp.status_code == 403

    def test_returns_log_detail(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin", resource_type="user", status="success"))
        session.commit()
        resp = client.get(f"{self.URL}/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_404_when_not_found(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{self.URL}/999")
        assert resp.status_code == 404


class TestBatchDeleteAuditLogs:
    URL = f"{BASE}/logs/batch"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = _delete_json(client, self.URL, {"ids": [1]})
        assert resp.status_code == 403

    def test_delete_by_ids(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        for i in range(3):
            session.add(AuditLog(id=i + 1, action="create", username="admin"))
        session.commit()
        resp = _delete_json(client, self.URL, {"ids": [1, 3]})
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 2

    def test_delete_by_actions(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        for a in ["create", "delete", "create"]:
            session.add(AuditLog(action=a, username="admin"))
        session.commit()
        resp = _delete_json(client, self.URL, {"actions": ["create"]})
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 2

    def test_delete_by_single_action(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(action="create", username="admin"))
        session.add(AuditLog(action="delete", username="admin"))
        session.commit()
        resp = _delete_json(client, self.URL, {"action": "delete"})
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 1

    def test_no_filters_returns_zero(self, db_client):
        client, _ = db_client
        resp = _delete_json(client, self.URL, {})
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 0

    def test_delete_with_before_date(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(action="create", username="admin"))
        session.commit()
        resp = _delete_json(client, self.URL, {
            "action": "create", "before_date": "2099-01-01T00:00:00",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 1

    def test_invalid_before_date_still_deletes_by_action(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(action="create", username="admin"))
        session.add(AuditLog(action="delete", username="admin"))
        session.commit()
        resp = _delete_json(client, self.URL, {
            "action": "create", "before_date": "not-a-date",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 1

    def test_ids_rejects_bad_string(self, client_with_mocked_auth):
        resp = _delete_json(client_with_mocked_auth, self.URL, {"ids": ["abc"]})
        assert resp.status_code == 422

    def test_actions_with_whitespace(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(action="create", username="admin"))
        session.commit()
        resp = _delete_json(client, self.URL, {"actions": [" create "]})
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 1

    def test_only_before_date_without_action_returns_zero(self, client_with_mocked_auth):
        resp = _delete_json(client_with_mocked_auth, self.URL, {"before_date": "2020-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 0

    def test_explicit_null_ids(self, client_with_mocked_auth):
        resp = _delete_json(client_with_mocked_auth, self.URL, {"ids": None, "action": "create"})
        assert resp.status_code == 200

    def test_explicit_null_actions(self, client_with_mocked_auth):
        resp = _delete_json(
            client_with_mocked_auth, self.URL,
            {"actions": None, "ids": [999], "before_date": "2020-01-01T00:00:00"},
        )
        assert resp.status_code == 200


class TestDeleteAuditLog:
    URL = f"{BASE}/logs"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.delete(f"{self.URL}/1")
        assert resp.status_code == 403

    def test_delete_success(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin"))
        session.commit()
        resp = client.delete(f"{self.URL}/1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"

    def test_404_when_not_found(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.delete(f"{self.URL}/999")
        assert resp.status_code == 404


class TestUpdateAuditLogRemark:
    URL = f"{BASE}/logs"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.patch(f"{self.URL}/1/remark", json={"remark": "test"})
        assert resp.status_code == 403

    def test_update_success(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin"))
        session.commit()
        resp = client.patch(f"{self.URL}/1/remark", json={"remark": "test note"})
        assert resp.status_code == 200
        assert resp.json()["data"]["remark"] == "test note"

    def test_404_when_not_found(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.patch(f"{self.URL}/999/remark", json={"remark": "test"})
        assert resp.status_code == 404

    def test_handles_str_metadata(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        log = AuditLog(id=1, action="create", username="admin")
        log.metadata_ = '{"existing": "data"}'
        session.add(log)
        session.commit()
        resp = client.patch(f"{self.URL}/1/remark", json={"remark": "new note"})
        assert resp.status_code == 200

    def test_handles_invalid_json_metadata(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        log = AuditLog(id=1, action="create", username="admin")
        log.metadata_ = "not-json"
        session.add(log)
        session.commit()
        resp = client.patch(f"{self.URL}/1/remark", json={"remark": "note"})
        assert resp.status_code == 200


class TestExportAuditLogs:
    URL = f"{BASE}/logs/export"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_export_all(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin", resource_type="user", status="success"))
        session.commit()
        resp = client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["action"] == "create"

    def test_filters_by_action(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin"))
        session.add(AuditLog(id=2, action="delete", username="admin"))
        session.commit()
        resp = client.get(self.URL, params={"action": "delete"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_start_date(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin"))
        session.commit()
        resp = client.get(self.URL, params={"start_date": "2020-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_end_date(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, action="create", username="admin"))
        session.commit()
        resp = client.get(self.URL, params={"end_date": "2099-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


class TestGetAuditStats:
    URL = f"{BASE}/stats"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_stats(self, client_with_mocked_auth, _mock_services):
        as_mock, _ = _mock_services
        as_mock.return_value.get_audit_stats.return_value = {
            "total_count": 10, "by_action": {"create": 5, "delete": 3},
            "by_status": {"success": 8, "failed": 2},
            "by_level": {"info": 7, "warning": 2, "error": 1},
            "top_users": {"admin": 10}, "recent_activity": [],
        }
        resp = client_with_mocked_auth.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 10


class TestSecurityEvents:
    URL = f"{BASE}/security/events"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_events(self, client_with_mocked_auth, _mock_services):
        _, ses_mock = _mock_services
        ses_mock.return_value.get_events.return_value = {
            "items": [{"id": 1, "event_type": "brute_force", "severity": "high"}],
            "total": 1, "page": 1, "page_size": 50,
        }
        resp = client_with_mocked_auth.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_passes_filters(self, client_with_mocked_auth, _mock_services):
        _, ses_mock = _mock_services
        ses_mock.return_value.get_events.return_value = {"items": [], "total": 0, "page": 1, "page_size": 50}
        client_with_mocked_auth.get(self.URL, params={
            "severity": "high", "event_type": "brute_force", "resolved": False,
            "start_date": "2024-01-01T00:00:00", "end_date": "2024-12-31T23:59:59",
            "page": 1, "page_size": 20,
        })
        ses_mock.return_value.get_events.assert_called_once_with(
            severity="high", event_type="brute_force", resolved=False,
            start_date=mock.ANY, end_date=mock.ANY, page=1, page_size=20,
        )


class TestSecurityStats:
    URL = f"{BASE}/security/stats"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_stats(self, client_with_mocked_auth, _mock_services):
        _, ses_mock = _mock_services
        ses_mock.return_value.get_security_stats.return_value = {
            "total_events": 10, "unresolved_count": 3,
            "by_severity": {"high": 2, "medium": 3, "low": 5},
            "unresolved_by_severity": {"high": 1, "medium": 2}, "recent_events": [],
        }
        resp = client_with_mocked_auth.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["total_events"] == 10


class TestResolveSecurityEvent:
    URL = f"{BASE}/security/events"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.post(f"{self.URL}/1/resolve?resolution_notes=fixed")
        assert resp.status_code == 403

    def test_resolve_success(self, client_with_mocked_auth, _mock_services):
        _, ses_mock = _mock_services
        ses_mock.return_value.resolve_event.return_value = mock.MagicMock(
            id=1, event_type="brute_force", resolved=True,
        )
        resp = client_with_mocked_auth.post(f"{self.URL}/1/resolve?resolution_notes=fixed")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Event resolved"
        ses_mock.return_value.resolve_event.assert_called_once_with(event_id=1, resolved_by=1, resolution_notes="fixed")

    def test_404_when_not_found(self, client_with_mocked_auth, _mock_services):
        _, ses_mock = _mock_services
        ses_mock.return_value.resolve_event.return_value = None
        resp = client_with_mocked_auth.post(f"{self.URL}/999/resolve?resolution_notes=notfound")
        assert resp.status_code == 404


class TestGetLoginAttempts:
    URL = f"{BASE}/login-attempts"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_paginated_results(self, db_client):
        client, session = db_client
        from app.models.audit import LoginAttempt
        session.add(LoginAttempt(id=1, username="admin", success=True))
        session.commit()
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_username(self, db_client):
        client, session = db_client
        from app.models.audit import LoginAttempt
        session.add(LoginAttempt(id=1, username="admin", ip_address="127.0.0.1"))
        session.add(LoginAttempt(id=2, username="user", ip_address="10.0.0.1"))
        session.commit()
        resp = client.get(self.URL, params={"username": "admin"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_ip(self, db_client):
        client, session = db_client
        from app.models.audit import LoginAttempt
        session.add(LoginAttempt(id=1, username="admin", ip_address="127.0.0.1"))
        session.add(LoginAttempt(id=2, username="user", ip_address="10.0.0.1"))
        session.commit()
        resp = client.get(self.URL, params={"ip_address": "127.0.0.1"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_start_date(self, db_client):
        client, session = db_client
        from app.models.audit import LoginAttempt
        session.add(LoginAttempt(id=1, username="admin", success=True))
        session.commit()
        resp = client.get(self.URL, params={"start_date": "2020-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_end_date(self, db_client):
        client, session = db_client
        from app.models.audit import LoginAttempt
        session.add(LoginAttempt(id=1, username="admin", success=True))
        session.commit()
        resp = client.get(self.URL, params={"end_date": "2099-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


class TestGetApiAccessLogs:
    URL = f"{BASE}/api-access"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_paginated_results(self, db_client):
        client, session = db_client
        from app.models.audit import APIAccessLog
        session.add(APIAccessLog(id=1, user_id=1, endpoint="/api/test", method="GET"))
        session.commit()
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_user_id(self, db_client):
        client, session = db_client
        from app.models.audit import APIAccessLog
        session.add(APIAccessLog(id=1, user_id=1, endpoint="/api/test", method="GET"))
        session.add(APIAccessLog(id=2, user_id=2, endpoint="/api/other", method="POST"))
        session.commit()
        resp = client.get(self.URL, params={"user_id": 1})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_endpoint(self, db_client):
        client, session = db_client
        from app.models.audit import APIAccessLog
        session.add(APIAccessLog(id=1, user_id=1, endpoint="/api/test", method="GET"))
        session.add(APIAccessLog(id=2, user_id=2, endpoint="/api/other", method="POST"))
        session.commit()
        resp = client.get(self.URL, params={"endpoint": "test"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_start_date(self, db_client):
        client, session = db_client
        from app.models.audit import APIAccessLog
        session.add(APIAccessLog(id=1, user_id=1, endpoint="/api/test", method="GET"))
        session.commit()
        resp = client.get(self.URL, params={"start_date": "2020-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_end_date(self, db_client):
        client, session = db_client
        from app.models.audit import APIAccessLog
        session.add(APIAccessLog(id=1, user_id=1, endpoint="/api/test", method="GET"))
        session.commit()
        resp = client.get(self.URL, params={"end_date": "2099-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


class TestGetExportLogs:
    URL = f"{BASE}/exports"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: _normal_user()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_returns_paginated_results(self, db_client):
        client, session = db_client
        from app.models.audit import DataExportLog
        session.add(DataExportLog(id=1, user_id=1, export_type="csv"))
        session.commit()
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_export_type(self, db_client):
        client, session = db_client
        from app.models.audit import DataExportLog
        session.add(DataExportLog(id=1, user_id=1, export_type="csv"))
        session.add(DataExportLog(id=2, user_id=2, export_type="pdf"))
        session.commit()
        resp = client.get(self.URL, params={"export_type": "csv"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_user_id(self, db_client):
        client, session = db_client
        from app.models.audit import DataExportLog
        session.add(DataExportLog(id=1, user_id=1, export_type="csv"))
        session.add(DataExportLog(id=2, user_id=2, export_type="pdf"))
        session.commit()
        resp = client.get(self.URL, params={"user_id": 1})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_start_date(self, db_client):
        client, session = db_client
        from app.models.audit import DataExportLog
        session.add(DataExportLog(id=1, user_id=1, export_type="csv"))
        session.commit()
        resp = client.get(self.URL, params={"start_date": "2020-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filters_by_end_date(self, db_client):
        client, session = db_client
        from app.models.audit import DataExportLog
        session.add(DataExportLog(id=1, user_id=1, export_type="csv"))
        session.commit()
        resp = client.get(self.URL, params={"end_date": "2099-01-01T00:00:00"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


class TestGetUserActivity:
    URL = f"{BASE}/user-activity"

    def test_requires_admin(self, client):
        from app.core.security import get_current_user
        u = _normal_user()
        u.id = 2
        client.app.dependency_overrides[get_current_user] = lambda: u
        resp = client.get(f"{self.URL}/1")
        assert resp.status_code == 403

    def test_own_activity_allowed_for_regular_user(self, client):
        from app.core.security import get_current_user
        u = _normal_user()
        u.id = 5
        client.app.dependency_overrides[get_current_user] = lambda: u
        resp = client.get(f"{self.URL}/5")
        assert resp.status_code == 200

    def test_other_user_denied_for_regular_user(self, client):
        from app.core.security import get_current_user
        u = _normal_user()
        u.id = 5
        client.app.dependency_overrides[get_current_user] = lambda: u
        resp = client.get(f"{self.URL}/1")
        assert resp.status_code == 403

    def test_returns_activity(self, db_client):
        client, session = db_client
        from app.models.audit import AuditLog
        session.add(AuditLog(id=1, user_id=1, action="create", username="admin"))
        session.add(AuditLog(id=2, user_id=1, action="update", username="admin"))
        session.add(AuditLog(id=3, user_id=1, action="delete", username="admin"))
        session.commit()
        resp = client.get(f"{self.URL}/1?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert data["total_actions"] == 3
        assert data["action_breakdown"]["create"] == 1
        assert data["action_breakdown"]["update"] == 1
        assert data["action_breakdown"]["delete"] == 1
        assert len(data["recent_activity"]) == 3
