"""app.api.v1.system.error_report 覆盖率攻坚测试（含 models.error_report.to_dict）

6 个端点全部直接使用 SessionLocal（非 get_db 注入）→ patch 模块级 SessionLocal。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.system.error_report as er_mod
from app.core.security import get_current_user
from app.models.error_report import ErrorReport

BASE = "/api/v1/system/error-reports"


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit", "group_by"):
        getattr(q, attr).return_value = q
    q.count.return_value = kw.get("count", 0)
    q.scalar.return_value = kw.get("scalar")
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


def _db_with(queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


@pytest.fixture
def er_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="root", role="admin"
    )
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _sess_patch(sess):
    return patch.object(er_mod, "SessionLocal", return_value=sess)


# ==================== POST /error-reports ====================


class TestReportError:
    def test_success_with_context(self, er_client):
        sess = MagicMock()

        def _refresh(rec):
            rec.id = 42

        sess.refresh.side_effect = _refresh
        with _sess_patch(sess):
            resp = er_client.post(
                BASE,
                json={
                    "source": "frontend",
                    "error_type": "TypeError",
                    "message": "无法读取属性",
                    "stack_trace": "at line 1",
                    "context": {"page": "/dashboard"},
                    "severity": "error",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["report_id"] == 42
        record = sess.add.call_args.args[0]
        assert record.status == "open"
        assert record.reporter == "root"
        assert record.context == '{"page": "/dashboard"}'
        sess.commit.assert_called_once()
        sess.close.assert_called_once()

    def test_success_without_context(self, er_client):
        sess = MagicMock()
        sess.refresh.side_effect = lambda rec: setattr(rec, "id", 43)
        with _sess_patch(sess):
            resp = er_client.post(
                BASE,
                json={"source": "backend", "error_type": "ValueError", "message": "x"},
            )
        assert resp.status_code == 200
        record = sess.add.call_args.args[0]
        assert record.context is None
        assert record.severity == "warning"  # 默认值

    def test_db_failure_500(self, er_client):
        sess = MagicMock()
        sess.commit.side_effect = Exception("db down")
        with _sess_patch(sess):
            resp = er_client.post(
                BASE,
                json={"source": "s", "error_type": "t", "message": "m"},
            )
        assert resp.status_code == 500
        # safe_commit 内部回滚 + 外层回滚
        assert sess.rollback.call_count >= 1
        sess.close.assert_called_once()


# ==================== GET /error-reports ====================


class TestListErrorReports:
    def test_list_with_all_filters(self, er_client):
        rec = ErrorReport(source="frontend", error_type="t", message="m", severity="error")
        rec.id = 1
        q = _q(count=1, all=[rec])
        sess = _db_with([q])
        with _sess_patch(sess):
            resp = er_client.get(f"{BASE}?source=frontend&severity=error&status=open&page=1&page_size=20")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["source"] == "frontend"

    def test_list_status_all_skips_filter(self, er_client):
        q = _q(count=0, all=[])
        sess = _db_with([q])
        with _sess_patch(sess):
            resp = er_client.get(f"{BASE}?status=all")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


# ==================== GET /error-reports/stats ====================


class TestErrorStats:
    def test_stats(self, er_client):
        sess = _db_with([
            _q(scalar=10),                              # total
            _q(scalar=4),                               # open
            _q(scalar=1),                               # critical
            _q(all=[("frontend", 6), ("backend", 4)]),  # by_source
            _q(all=[("error", 7), ("warning", 3)]),     # by_severity
        ])
        with _sess_patch(sess):
            resp = er_client.get(f"{BASE}/stats")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {
            "total": 10,
            "open": 4,
            "critical": 1,
            "by_source": {"frontend": 6, "backend": 4},
            "by_severity": {"error": 7, "warning": 3},
        }
        sess.close.assert_called_once()


# ==================== GET /error-reports/{id} ====================


class TestGetErrorReport:
    def test_found(self, er_client):
        rec = ErrorReport(source="frontend", error_type="t", message="m", context='{"a": 1}')
        rec.id = 7
        sess = _db_with([_q(first=rec)])
        with _sess_patch(sess):
            resp = er_client.get(f"{BASE}/7")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["source"] == "frontend"
        assert data["context"] == {"a": 1}  # JSON 被解析为对象

    def test_not_found_404(self, er_client):
        sess = _db_with([_q(first=None)])
        with _sess_patch(sess):
            resp = er_client.get(f"{BASE}/99")
        assert resp.status_code == 404


# ==================== PUT /error-reports/{id} ====================


class TestUpdateErrorReport:
    def test_resolve_sets_resolved_at(self, er_client):
        rec = ErrorReport(source="s", error_type="t", message="m", status="open")
        rec.id = 1
        sess = _db_with([_q(first=rec)])
        with _sess_patch(sess):
            resp = er_client.put(f"{BASE}/1", json={"status": "resolved", "resolution_note": "已修复"})
        assert resp.status_code == 200
        assert rec.status == "resolved"
        assert rec.resolution_note == "已修复"
        assert rec.resolved_at is not None
        sess.commit.assert_called_once()

    def test_non_resolved_no_resolved_at(self, er_client):
        rec = ErrorReport(source="s", error_type="t", message="m", status="open")
        rec.id = 1
        sess = _db_with([_q(first=rec)])
        with _sess_patch(sess):
            resp = er_client.put(f"{BASE}/1", json={"status": "ignored"})
        assert resp.status_code == 200
        assert rec.resolved_at is None

    def test_not_found_404(self, er_client):
        sess = _db_with([_q(first=None)])
        with _sess_patch(sess):
            resp = er_client.put(f"{BASE}/99", json={"status": "resolved"})
        assert resp.status_code == 404

    def test_non_owner_non_admin_403(self, er_client):
        # 覆盖 error_report.py:204 —— 记录归属他人且当前用户非管理员 → 403
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=5, username="other", role="user"
        )
        rec = ErrorReport(source="s", error_type="t", message="m", status="open")
        rec.id = 1
        rec.user_id = 999  # 归属他人
        sess = _db_with([_q(first=rec)])
        with _sess_patch(sess):
            resp = er_client.put(f"{BASE}/1", json={"status": "resolved"})
        assert resp.status_code == 403

    def test_commit_failure_500(self, er_client):
        rec = ErrorReport(source="s", error_type="t", message="m", status="open")
        rec.id = 1
        sess = _db_with([_q(first=rec)])
        sess.commit.side_effect = Exception("db down")
        with _sess_patch(sess):
            resp = er_client.put(f"{BASE}/1", json={"status": "resolved"})
        assert resp.status_code == 500
        # safe_commit 内部回滚 + 外层回滚
        assert sess.rollback.call_count >= 1


# ==================== POST /error-reports/report-exception ====================


class TestReportCurrentException:
    def test_success(self, er_client):
        sess = MagicMock()
        sess.refresh.side_effect = lambda rec: setattr(rec, "id", 50)
        with _sess_patch(sess):
            resp = er_client.post(f"{BASE}/report-exception?source=import&message=解析失败")
        assert resp.status_code == 200
        assert resp.json()["data"]["report_id"] == 50
        record = sess.add.call_args.args[0]
        assert record.error_type == "runtime_exception"
        assert record.severity == "error"
        assert record.reporter == "root"

    def test_db_failure_500(self, er_client):
        sess = MagicMock()
        sess.commit.side_effect = Exception("db down")
        with _sess_patch(sess):
            resp = er_client.post(f"{BASE}/report-exception?source=s&message=m")
        assert resp.status_code == 500
        # safe_commit 内部回滚 + 外层回滚
        assert sess.rollback.call_count >= 1


# ==================== models.error_report.to_dict ====================


class TestErrorReportModelToDict:
    def test_invalid_json_context_kept_as_is(self):
        rec = ErrorReport(source="s", error_type="t", message="m", context="not-json")
        result = rec.to_dict()
        assert result["context"] == "not-json"

    def test_none_context(self):
        rec = ErrorReport(source="s", error_type="t", message="m", context=None)
        result = rec.to_dict()
        assert result["context"] is None

    def test_camel_case_false(self):
        rec = ErrorReport(source="s", error_type="t", message="m")
        result = rec.to_dict(camel_case=False)
        assert "error_type" in result
