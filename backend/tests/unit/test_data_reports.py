"""Tests for data/data_reports.py — data report management API."""
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

import pytest

BASE = "/api/v1/data-reports"


def _make_user(org_id=1, user_id=1, **kwargs):
    user = Mock()
    user.id = user_id
    user.org_id = org_id
    user.organization_id = org_id
    user.username = kwargs.get("username", "admin")
    user.role = kwargs.get("role", "admin")
    user.is_superuser = kwargs.get("is_superuser", True)
    user.is_active = True
    user.permissions_list = ["*"]
    user.email = "admin@test.com"
    user.full_name = "Admin"
    return user


def _make_report(**kwargs):
    r = Mock()
    r.id = kwargs.get("id", 1)
    r.report_code = kwargs.get("report_code", f"RP-{kwargs.get('id', 1):03d}")
    r.title = kwargs.get("title", "Test Report")
    r.report_type = kwargs.get("report_type", "monthly")
    r.status = kwargs.get("status", "draft")
    r.source_org_id = kwargs.get("source_org_id", 1)
    r.target_org_id = kwargs.get("target_org_id", 2)
    r.description = kwargs.get("description", "desc")
    r.package_id = kwargs.get("package_id", None)
    r.created_at = kwargs.get("created_at", None)
    r.updated_at = kwargs.get("updated_at", None)
    r.submitted_at = kwargs.get("submitted_at", None)
    r.reviewed_at = kwargs.get("reviewed_at", None)
    r.reviewed_by = kwargs.get("reviewed_by", None)
    r.comment = kwargs.get("comment", None)
    r._sa_instance_state = kwargs.get("_sa_instance_state", Mock())
    return r


def _setup_user_override(client, org_id=1, user_id=1):
    from app.core.security import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: _make_user(org_id=org_id, user_id=user_id)


def _setup_service_override(client, mock_svc):
    from app.api.v1.data.data.data_reports import get_report_service

    client.app.dependency_overrides[get_report_service] = lambda: mock_svc


def _setup_permission_override(client, mock_perm=None):
    from app.api.v1.data.data.data_reports import get_permission_service

    if mock_perm is None:
        mock_perm = Mock()
    client.app.dependency_overrides[get_permission_service] = lambda: mock_perm
    return mock_perm


# ──────────────────────────────────────────────
# 1. GET /api/v1/data-reports — list_data_reports
# ──────────────────────────────────────────────


class TestListDataReports:
    def test_requires_auth(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 401

    def test_no_org_id_returns_empty(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=None)
        resp = client_with_mocked_auth.get(BASE)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_received_direction(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_subordinate_reports.return_value = [_make_report(id=1, status="submitted", source_org_id=2, target_org_id=1)]
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(BASE, params={"direction": "received"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_submitted_direction(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_submitted_reports.return_value = [_make_report(id=2, status="draft", source_org_id=1, target_org_id=3)]
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(BASE, params={"direction": "submitted", "status": "draft"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        mock_svc.get_submitted_reports.assert_called_once()

    def test_status_filter_received(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_subordinate_reports.return_value = []
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(BASE, params={"direction": "received", "status": "approved"})
        assert resp.status_code == 200
        mock_svc.get_subordinate_reports.assert_called_once()


# ──────────────────────────────────────────────────────
# 2. GET /api/v1/data-reports/statistics — get_report_statistics
# ──────────────────────────────────────────────────────


class TestGetReportStatistics:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/statistics")
        assert resp.status_code == 401

    def test_no_org_id_returns_zero(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=None)
        resp = client_with_mocked_auth.get(f"{BASE}/statistics")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_success(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report_statistics.return_value = {"total": 10, "submitted": 5, "approved": 3, "rejected": 1, "pending": 1}
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(f"{BASE}/statistics")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10


# ──────────────────────────────────────────────────────
# 3. GET /api/v1/data-reports/dashboard — get_subordinate_dashboard
# ──────────────────────────────────────────────────────


class TestGetSubordinateDashboard:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/dashboard")
        assert resp.status_code == 401

    def test_no_org_id_returns_empty(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=None)
        resp = client_with_mocked_auth.get(f"{BASE}/dashboard")
        assert resp.status_code == 200
        assert resp.json()["total_subordinates"] == 0

    def test_success(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_subordinate_dashboard.return_value = {"total_subordinates": 5, "reported_count": 3, "unreported_count": 2}
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(f"{BASE}/dashboard")
        assert resp.status_code == 200
        assert resp.json()["total_subordinates"] == 5


# ──────────────────────────────────────────────────────
# 4. GET /api/v1/data-reports/pending — get_pending_reports
# ──────────────────────────────────────────────────────


class TestGetPendingReports:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/pending")
        assert resp.status_code == 401

    def test_no_org_id_returns_empty(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=None)
        resp = client_with_mocked_auth.get(f"{BASE}/pending")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_success(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_subordinate_reports.return_value = [_make_report(id=1, status="submitted", source_org_id=2, target_org_id=1)]
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(f"{BASE}/pending")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


# ──────────────────────────────────────────────────────
# 5. GET /api/v1/data-reports/{report_id} — get_data_report
# ──────────────────────────────────────────────────────


class TestGetDataReport:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/999")
        assert resp.status_code == 404

    def test_found_as_source_org(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="submitted", source_org_id=1, target_org_id=2)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_found_as_target_org(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=2)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="submitted", source_org_id=1, target_org_id=2)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/1")
        assert resp.status_code == 200

    def test_no_permission(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=3, user_id=999)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, source_org_id=1, target_org_id=2)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        mock_perm = _setup_permission_override(client_with_mocked_auth)
        mock_perm.can_access_organization.return_value = False
        resp = client_with_mocked_auth.get(f"{BASE}/1")
        assert resp.status_code == 403


# ──────────────────────────────────────────────────────
# 6. POST /api/v1/data-reports — create_data_report
# ──────────────────────────────────────────────────────


class TestCreateDataReport:
    def test_requires_auth(self, client):
        resp = client.post(BASE, json={"title": "Test", "report_type": "monthly", "target_org_id": 2})
        assert resp.status_code == 401

    def test_no_org_id(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=None)
        resp = client_with_mocked_auth.post(BASE, json={"title": "Test", "report_type": "monthly", "package_id": 1, "target_org_id": 2})
        assert resp.status_code == 400

    def test_success(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.create_report = AsyncMock(return_value=_make_report(id=1, status="draft", source_org_id=1, target_org_id=2))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(BASE, json={"title": "New Report", "report_type": "monthly", "package_id": 1, "target_org_id": 2})
        assert resp.status_code == 201
        assert resp.json()["id"] == 1

    def test_business_error(self, client_with_mocked_auth):
        from app.core.exceptions import BusinessError

        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.create_report = AsyncMock(side_effect=BusinessError("invalid data"))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(BASE, json={"title": "Bad", "report_type": "monthly", "package_id": 1, "target_org_id": 2})
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────
# 7. POST /api/v1/data-reports/{report_id}/submit — submit_report
# ──────────────────────────────────────────────────────


class TestSubmitReport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/submit")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        from app.services.data_report_service import ReportNotFoundError

        mock_svc = Mock()
        mock_svc.submit_report = AsyncMock(side_effect=ReportNotFoundError(999))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/999/submit")
        assert resp.status_code == 404

    def test_status_error(self, client_with_mocked_auth):
        from app.services.data_report_service import ReportStatusError

        mock_svc = Mock()
        mock_svc.submit_report = AsyncMock(side_effect=ReportStatusError(1, "approved", "draft"))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/submit")
        assert resp.status_code == 400

    def test_success(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.submit_report = AsyncMock(return_value=_make_report(id=1, status="submitted"))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/submit")
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"


# ──────────────────────────────────────────────────────
# 8. POST /api/v1/data-reports/{report_id}/review — review_report
# ──────────────────────────────────────────────────────


class TestReviewReport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/review", json={"status": "approve"})
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.post(f"{BASE}/999/review", json={"status": "approve"})
        assert resp.status_code == 404

    def test_not_target_org(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, source_org_id=1, target_org_id=99)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.post(f"{BASE}/1/review", json={"status": "approve"})
        assert resp.status_code == 403

    def test_success(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="submitted", source_org_id=2, target_org_id=1)
        mock_svc.review_report = AsyncMock(return_value=_make_report(id=1, status="approved", source_org_id=2, target_org_id=1))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.post(f"{BASE}/1/review", json={"status": "approve", "comment": "OK"})
        assert resp.status_code == 200

    def test_status_error(self, client_with_mocked_auth):
        from app.services.data_report_service import ReportStatusError

        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="draft", source_org_id=2, target_org_id=1)
        mock_svc.review_report = AsyncMock(side_effect=ReportStatusError(1, "draft", "submitted"))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.post(f"{BASE}/1/review", json={"status": "approve"})
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────
# 9. POST /api/v1/data-reports/{report_id}/cancel — cancel_report
# ──────────────────────────────────────────────────────


class TestCancelReport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/cancel")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/999/cancel")
        assert resp.status_code == 404

    def test_not_source_org(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="draft", source_org_id=99, target_org_id=1)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/cancel")
        assert resp.status_code == 403

    def test_invalid_status(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="submitted", source_org_id=1, target_org_id=2)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/cancel")
        assert resp.status_code == 400

    def test_success_draft(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        report = _make_report(id=1, status="draft")
        mock_db = Mock()
        mock_svc = Mock()
        mock_svc.get_report.return_value = report
        mock_svc.db = mock_db
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/cancel", params={"reason": "no longer needed"})
        assert resp.status_code == 200
        assert report.status == "cancelled"
        mock_db.commit.assert_called_once()

    def test_success_rejected(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        report = _make_report(id=1, status="rejected")
        mock_db = Mock()
        mock_svc = Mock()
        mock_svc.get_report.return_value = report
        mock_svc.db = mock_db
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/cancel")
        assert resp.status_code == 200
        assert report.status == "cancelled"


# ──────────────────────────────────────────────────────
# 10. POST /api/v1/data-reports/{report_id}/resubmit — resubmit_report
# ──────────────────────────────────────────────────────


class TestResubmitReport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/resubmit")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/999/resubmit")
        assert resp.status_code == 404

    def test_not_source_org(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="rejected", source_org_id=99)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/resubmit")
        assert resp.status_code == 403

    def test_not_rejected_status(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="draft", source_org_id=1)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/resubmit")
        assert resp.status_code == 400

    def test_success(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="rejected", source_org_id=1, target_org_id=2)
        mock_svc.submit_report = AsyncMock(return_value=_make_report(id=1, status="submitted"))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/resubmit")
        assert resp.status_code == 200

    def test_status_error_on_resubmit(self, client_with_mocked_auth):
        from app.services.data_report_service import ReportStatusError

        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, status="rejected", source_org_id=1)
        mock_svc.submit_report = AsyncMock(side_effect=ReportStatusError(1, "rejected", "draft"))
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/resubmit")
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────
# 11. POST /api/v1/data-reports/{report_id}/approve — approve_data_report
# ──────────────────────────────────────────────────────


class TestApproveDataReport:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/1/approve")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.db = Mock()
        mock_svc.db.query.return_value.filter.return_value.first.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/999/approve")
        assert resp.status_code == 404

    def test_not_submitted_status(self, client_with_mocked_auth):
        mock_report_row = Mock()
        mock_report_row.status = "draft"
        mock_svc = Mock()
        mock_svc.db = Mock()
        mock_svc.db.query.return_value.filter.return_value.first.return_value = mock_report_row
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/approve")
        assert resp.status_code == 400

    def test_not_target_org(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_report_row = Mock()
        mock_report_row.status = "submitted"
        mock_report_row.target_org_id = 99
        mock_svc = Mock()
        mock_svc.db = Mock()
        mock_svc.db.query.return_value.filter.return_value.first.return_value = mock_report_row
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.post(f"{BASE}/1/approve")
        assert resp.status_code == 403

    def test_success_without_package(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_report_row = Mock()
        mock_report_row.status = "submitted"
        mock_report_row.target_org_id = 1
        mock_report_row.source_org_id = 2
        mock_report_row.id = 1
        mock_report_row.package_id = None
        mock_report_row.title = "Approved"
        mock_report_row.report_type = "monthly"
        mock_report_row.created_at = None
        mock_report_row.updated_at = None
        mock_report_row.submitted_at = None
        mock_report_row.reviewed_at = None
        mock_report_row.reviewed_by = None
        mock_report_row.comment = None
        mock_report_row._sa_instance_state = Mock()

        mock_svc = Mock()
        mock_svc.db = Mock()
        mock_svc.db.query.return_value.filter.return_value.first.return_value = mock_report_row
        _setup_service_override(client_with_mocked_auth, mock_svc)

        with patch("app.services.data_package_service.DataPackageService") as mock_pkg_cls:
            mock_pkg_cls.return_value.confirm_import = AsyncMock()
            resp = client_with_mocked_auth.post(f"{BASE}/1/approve")
            assert resp.status_code == 200

    def test_success_with_package_import(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_report_row = Mock()
        mock_report_row.id = 1
        mock_report_row.status = "submitted"
        mock_report_row.target_org_id = 1
        mock_report_row.source_org_id = 2
        mock_report_row.package_id = 10
        mock_report_row.title = "Approved With Package"
        mock_report_row.report_type = "monthly"
        mock_report_row.created_at = None
        mock_report_row.updated_at = None
        mock_report_row.submitted_at = None
        mock_report_row.reviewed_at = None
        mock_report_row.reviewed_by = None
        mock_report_row.comment = None
        mock_report_row._sa_instance_state = Mock()

        mock_package = Mock()
        mock_package.id = 10

        mock_svc = Mock()
        mock_svc.db = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_report_row, mock_package]
        mock_query.filter.return_value = mock_filter
        mock_svc.db.query.return_value = mock_query
        _setup_service_override(client_with_mocked_auth, mock_svc)

        mock_pkg_svc = Mock()
        mock_pkg_svc.confirm_import = AsyncMock()

        with patch("app.services.data_package_service.DataPackageService", return_value=mock_pkg_svc):
            resp = client_with_mocked_auth.post(f"{BASE}/1/approve")
            assert resp.status_code == 200
            mock_pkg_svc.confirm_import.assert_awaited_once()

    def test_package_import_failure(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_report_row = Mock()
        mock_report_row.id = 1
        mock_report_row.status = "submitted"
        mock_report_row.target_org_id = 1
        mock_report_row.package_id = 10
        mock_report_row._sa_instance_state = Mock()

        mock_package = Mock()
        mock_package.id = 10

        mock_svc = Mock()
        mock_svc.db = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.side_effect = [mock_report_row, mock_package]
        mock_query.filter.return_value = mock_filter
        mock_svc.db.query.return_value = mock_query
        _setup_service_override(client_with_mocked_auth, mock_svc)

        mock_pkg_svc = Mock()
        mock_pkg_svc.confirm_import = AsyncMock(side_effect=RuntimeError("import failed"))

        with patch("app.services.data_package_service.DataPackageService", return_value=mock_pkg_svc):
            resp = client_with_mocked_auth.post(f"{BASE}/1/approve")
            assert resp.status_code == 500


# ──────────────────────────────────────────────────────
# 12. GET /api/v1/data-reports/received — list_received_reports
# ──────────────────────────────────────────────────────


class TestListReceivedReports:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/received")
        assert resp.status_code == 401

    def test_received_accessible_after_route_fix(self, client_with_mocked_auth):
        """bug#14 修复回归：/received 已前移到 /{report_id} 之前注册，
        不再被路径参数遮蔽，认证+服务就位时应返回 200。"""
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.count.return_value = 0
        q.all.return_value = []
        mock_svc.db.query.return_value = q
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(f"{BASE}/received")
        assert resp.status_code == 200

    def test_received_with_status_filter(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.db = Mock()
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.count.return_value = 0
        q.all.return_value = []
        mock_svc.db.query.return_value = q
        _setup_service_override(client_with_mocked_auth, mock_svc)
        resp = client_with_mocked_auth.get(f"{BASE}/received", params={"status": "approved"})
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────
# 13. GET /api/v1/data-reports/{report_id}/package — get_report_package
# ──────────────────────────────────────────────────────


class TestGetReportPackage:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1/package")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/999/package")
        assert resp.status_code == 404

    def test_success_as_source(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, source_org_id=1, target_org_id=2, package_id=10)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        mock_perm = _setup_permission_override(client_with_mocked_auth)

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=1):
            resp = client_with_mocked_auth.get(f"{BASE}/1/package")
            assert resp.status_code == 200
            assert resp.json()["package_id"] == 10
        mock_perm.can_access_organization.assert_not_called()

    def test_success_as_target(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, source_org_id=1, target_org_id=2, package_id=10)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=2):
            resp = client_with_mocked_auth.get(f"{BASE}/1/package")
            assert resp.status_code == 200

    def test_no_permission(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_svc.get_report.return_value = _make_report(id=1, source_org_id=1, target_org_id=2, package_id=10)
        _setup_service_override(client_with_mocked_auth, mock_svc)
        mock_perm = _setup_permission_override(client_with_mocked_auth)
        mock_perm.can_access_organization.return_value = False

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=3):
            resp = client_with_mocked_auth.get(f"{BASE}/1/package")
            assert resp.status_code == 403


# ──────────────────────────────────────────────────────
# 14. GET /api/v1/data-reports/{report_id}/preview — preview_data_report
# ──────────────────────────────────────────────────────


class TestPreviewDataReport:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1/preview")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/999/preview")
        assert resp.status_code == 404

    def test_success_no_package(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_report = _make_report(id=1, report_code="RP-001", status="submitted",
                                   source_org_id=1, target_org_id=2, package_id=None)
        mock_svc.get_report.return_value = mock_report
        mock_svc.db.query.return_value.filter.return_value.first.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=1):
            resp = client_with_mocked_auth.get(f"{BASE}/1/preview")
            assert resp.status_code == 200
            assert "data" in resp.json()
            assert resp.json()["data"]["report_code"] == "RP-001"

    def test_success_with_package(self, client_with_mocked_auth):
        mock_package = Mock()
        mock_package.id = 10
        mock_package.package_code = "PK-001"
        mock_package.file_name = "data.zip"
        mock_package.file_size = 1024
        mock_package.record_count = 100
        mock_package.data_types = ["villages", "projects"]
        mock_package.status = "completed"

        mock_svc = Mock()
        mock_report = _make_report(id=1, report_code="RP-001", status="submitted",
                                   source_org_id=1, target_org_id=2, package_id=10)
        mock_svc.get_report.return_value = mock_report
        mock_svc.db.query.return_value.filter.return_value.first.return_value = mock_package
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=1):
            resp = client_with_mocked_auth.get(f"{BASE}/1/preview")
            assert resp.status_code == 200
            assert "package" in resp.json()["data"]

    def test_no_permission(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_report = _make_report(id=1, source_org_id=1, target_org_id=2)
        mock_svc.get_report.return_value = mock_report
        _setup_service_override(client_with_mocked_auth, mock_svc)
        mock_perm = _setup_permission_override(client_with_mocked_auth)
        mock_perm.can_access_organization.return_value = False

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=3):
            resp = client_with_mocked_auth.get(f"{BASE}/1/preview")
            assert resp.status_code == 403


# ──────────────────────────────────────────────────────
# 15. GET /api/v1/data-reports/{report_id}/download — download_data_report
# ──────────────────────────────────────────────────────


class TestDownloadDataReport:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/1/download")
        assert resp.status_code == 401

    def test_not_found(self, client_with_mocked_auth):
        _setup_user_override(client_with_mocked_auth, org_id=1)
        mock_svc = Mock()
        mock_svc.get_report.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)
        resp = client_with_mocked_auth.get(f"{BASE}/999/download")
        assert resp.status_code == 404

    def test_success_json_fallback(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_report = _make_report(id=1, report_code="RP-001", status="submitted",
                                   source_org_id=1, target_org_id=2, package_id=None)
        mock_svc.get_report.return_value = mock_report
        mock_svc.db.query.return_value.filter.return_value.first.return_value = None
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=1):
            resp = client_with_mocked_auth.get(f"{BASE}/1/download")
            assert resp.status_code == 200
            assert "application/json" in resp.headers.get("content-type", "")

    def test_success_file_response(self, client_with_mocked_auth, tmp_path):
        tmp_file = tmp_path / "data.zip"
        tmp_file.write_text("fake zip content")

        mock_package = Mock()
        mock_package.id = 10
        mock_package.file_path = str(tmp_file)
        mock_package.file_name = "data.zip"
        mock_package._sa_instance_state = Mock()

        mock_svc = Mock()
        mock_report = _make_report(id=1, report_code="RP-001", status="submitted",
                                   source_org_id=1, target_org_id=2, package_id=10)
        mock_svc.get_report.return_value = mock_report
        mock_svc.db.query.return_value.filter.return_value.first.return_value = mock_package
        _setup_service_override(client_with_mocked_auth, mock_svc)
        _setup_permission_override(client_with_mocked_auth)

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=1):
            resp = client_with_mocked_auth.get(f"{BASE}/1/download")
            assert resp.status_code == 200

    def test_no_permission(self, client_with_mocked_auth):
        mock_svc = Mock()
        mock_report = _make_report(id=1, source_org_id=1, target_org_id=2)
        mock_svc.get_report.return_value = mock_report
        _setup_service_override(client_with_mocked_auth, mock_svc)
        mock_perm = _setup_permission_override(client_with_mocked_auth)
        mock_perm.can_access_organization.return_value = False

        with patch("app.api.v1.data.data.data_reports.get_user_org_id", return_value=3):
            resp = client_with_mocked_auth.get(f"{BASE}/1/download")
            assert resp.status_code == 403
