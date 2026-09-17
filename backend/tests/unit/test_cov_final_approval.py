"""app.api.v1.approval 覆盖补全 — /tasks/pending 兜底查询的非管理员过滤分支 (line 610)."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mocks():
    db = MagicMock(name="db")
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    db.query.return_value = q

    user = MagicMock(name="user")
    user.id = 7
    user.role = "user"
    user.is_superuser = False
    return db, q, user


@pytest.fixture
def client(mocks):
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    db, _, user = mocks
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    tc = TestClient(app, raise_server_exceptions=False)
    yield tc
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


class TestPendingTasksFallback:
    def test_non_admin_fallback_filters_by_submitter(self, client):
        """service 无待办时兜底查全量 pending，非管理员需按 submitter_id 过滤 (line 610)"""
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc_cls:
            svc_cls.return_value.get_pending_tasks.return_value = []
            resp = client.get("/api/v1/approval/tasks/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 0
        assert body["data"]["items"] == []
