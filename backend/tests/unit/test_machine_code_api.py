"""Comprehensive tests for machine_code.py — all endpoints, full branch coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app


# ── Disable camel-to-snake middleware for tests ──
@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch("app.middleware.camel_to_snake._convert_keys",
               side_effect=lambda obj, converter: (obj, False)):
        yield


@pytest.fixture
def mock_db():
    db = MagicMock()
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.first.return_value = None
    db.query.return_value = q
    return db


@pytest.fixture
def super_admin():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    u.is_active = True
    return u


@pytest.fixture
def regular_user():
    u = MagicMock()
    u.id = 2
    u.username = "user"
    u.role = "operator"
    u.is_superuser = False
    u.organization_id = 1
    u.is_active = True
    return u


@pytest.fixture
def client_admin(mock_db, super_admin):
    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: super_admin
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original_overrides


@pytest.fixture
def client_regular(mock_db, regular_user):
    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original_overrides


@pytest.fixture
def mock_machine_code():
    mc = MagicMock()
    mc.id = 1
    mc.machine_code = "ABC123"
    mc.pass_code = "1234"
    mc.status = "pending"
    mc.user_id = None
    mc.username = None
    mc.description = "test"
    mc.created_at = None
    mc.activated_at = None
    mc.allow_subordinate_generation = False
    mc.organization_id = 1
    mc.created_by = 1
    mc.organization = MagicMock()
    mc.organization.id = 1
    mc.organization.name = "测试组织"
    mc.user = None
    return mc


def _make_mock_record(
    id_=1, machine_code="MC001", pass_code="1234",
    status="pending", user=None, description="desc",
    created_at_field=None, activated_at_field=None,
):
    r = MagicMock()
    r.id = id_
    r.machine_code = machine_code
    r.pass_code = pass_code
    r.status = status
    r.user_id = user.id if user else None
    r.user = user
    r.description = description
    r.created_at = created_at_field
    r.activated_at = activated_at_field
    r.organization = None
    r.allow_subordinate_generation = False
    r.created_by = 1
    return r


# ---------------------------------------------------------------------------
#  GET /machine-code/get-machine-code (public)
# ---------------------------------------------------------------------------

class TestGetMachineCode:
    def test_success(self, client_admin):
        svc = MagicMock()
        svc.get_machine_code.return_value = "MACHINE001"
        svc.generate_verification_code.return_value = "VERIFY001"
        svc.get_machine_info.return_value = {"os": "windows"}
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/get-machine-code")
        assert resp.status_code == 200
        assert resp.json()["code"] == 200
        assert resp.json()["data"]["machine_code"] == "MACHINE001"

    def test_exception(self, client_admin):
        svc = MagicMock()
        svc.get_machine_code.side_effect = ValueError("HW error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/get-machine-code")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  POST /machine-code/admin/create
# ---------------------------------------------------------------------------

class TestAdminCreate:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/machine-code/admin/create", json={
            "machine_code": "TEST001",
        })
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        svc = MagicMock()
        record = MagicMock()
        record.id = 1
        record.machine_code = "TEST001"
        record.pass_code = "5678"
        record.status = "pending"
        record.created_at = None
        svc.create_machine_code_record.return_value = record

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/create", json={
                "machine_code": "TEST001",
                "description": "test",
                "pass_code": "4321",
            })
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_value_error(self, client_admin, mock_db):
        svc = MagicMock()
        svc.create_machine_code_record.side_effect = ValueError("已存在")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/create", json={
                "machine_code": "DUP",
            })
        assert resp.status_code == 400

    def test_generic_error(self, client_admin, mock_db):
        svc = MagicMock()
        svc.create_machine_code_record.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/create", json={
                "machine_code": "ERR",
            })
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  GET /machine-code/admin/list
# ---------------------------------------------------------------------------

class TestAdminList:
    def test_permission_denied(self, client_regular):
        resp = client_regular.get("/api/v1/machine-code/admin/list")
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        svc = MagicMock()
        record = _make_mock_record(1)
        svc.list_machine_codes.return_value = ([record], 1)

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/admin/list")
        assert resp.status_code == 200
        assert resp.json()["code"] == 200
        assert resp.json()["data"]["total"] == 1

    def test_with_user(self, client_admin, mock_db):
        svc = MagicMock()
        user = MagicMock()
        user.username = "测试用户"
        record = _make_mock_record(1, user=user)
        svc.list_machine_codes.return_value = ([record], 1)

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/admin/list?status_filter=active")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["username"] == "测试用户"

    def test_without_user(self, client_admin, mock_db):
        svc = MagicMock()
        record = _make_mock_record(1, user=None)
        svc.list_machine_codes.return_value = ([record], 1)

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/admin/list")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["username"] is None

    def test_exception(self, client_admin, mock_db):
        svc = MagicMock()
        svc.list_machine_codes.side_effect = RuntimeError("List error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/admin/list")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  POST /machine-code/admin/revoke/{machine_code_id}
# ---------------------------------------------------------------------------

class TestAdminRevoke:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/machine-code/admin/revoke/1")
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        svc = MagicMock()
        svc.revoke_machine_code.return_value = True
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/revoke/1")
        assert resp.status_code == 200

    def test_not_found(self, client_admin, mock_db):
        svc = MagicMock()
        svc.revoke_machine_code.return_value = False
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/revoke/999")
        assert resp.status_code == 404

    def test_exception(self, client_admin, mock_db):
        svc = MagicMock()
        svc.revoke_machine_code.side_effect = RuntimeError("Revoke error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/revoke/1")
        assert resp.status_code == 500

    def test_http_exception_re_raised(self, client_admin, mock_db):
        from fastapi import HTTPException
        svc = MagicMock()
        svc.revoke_machine_code.side_effect = HTTPException(400, "custom")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/admin/revoke/1")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  POST /machine-code/verify-machine-code (public)
# ---------------------------------------------------------------------------

class TestVerifyMachineCode:
    def test_valid(self, client_admin):
        svc = MagicMock()
        svc.verify_machine_code.return_value = True
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/verify-machine-code", json={
                "machine_code": "MC001", "verification_code": "VC001"
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["is_valid"] is True

    def test_invalid(self, client_admin):
        svc = MagicMock()
        svc.verify_machine_code.return_value = False
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/verify-machine-code", json={
                "machine_code": "BAD", "verification_code": "XXX"
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["is_valid"] is False


# ---------------------------------------------------------------------------
#  POST /machine-code/generate-initial-password
# ---------------------------------------------------------------------------

class TestGenerateInitialPassword:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/machine-code/generate-initial-password", json={
            "username": "user", "verification_code": "VC001"
        })
        assert resp.status_code == 403

    def test_user_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None

        resp = client_admin.post("/api/v1/machine-code/generate-initial-password", json={
            "username": "nonexistent", "verification_code": "VC001"
        })
        assert resp.status_code == 404

    def test_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        user = MagicMock()
        user.username = "testuser"
        user.hashed_password = "oldhash"
        q.first.return_value = user

        svc = MagicMock()
        svc.generate_initial_password.return_value = "NewPwd123!"

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/generate-initial-password", json={
                "username": "testuser", "verification_code": "VC001"
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["initial_password"] == "NewPwd123!"
        assert user.must_change_password is True

    def test_exception(self, client_admin, mock_db):
        q = mock_db.query.return_value
        user = MagicMock()
        q.first.return_value = user

        svc = MagicMock()
        svc.generate_initial_password.side_effect = RuntimeError("Gen error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/generate-initial-password", json={
                "username": "testuser", "verification_code": "VC001"
            })
        assert resp.status_code == 500

    def test_http_exception_re_raised(self, client_admin, mock_db):
        from fastapi import HTTPException
        q = mock_db.query.return_value
        user = MagicMock()
        q.first.return_value = user

        svc = MagicMock()
        svc.generate_initial_password.side_effect = HTTPException(400, "custom")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/generate-initial-password", json={
                "username": "testuser", "verification_code": "VC001"
            })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  POST /machine-code/reset-password-with-machine-code (public, rate limited)
# ---------------------------------------------------------------------------

class TestResetPasswordWithMachineCode:
    @pytest.fixture(autouse=True)
    def _loopback(self):
        """本类聚焦业务逻辑；loopback 门禁行为由
        tests/unit/api/test_machine_code_reset_security.py 覆盖。"""
        with patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            yield

    def test_rate_limited(self, client_admin):
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=False)):
            with patch("app.api.v1.machine_code.get_client_ip", return_value="127.0.0.1"):
                resp = client_admin.post(
                    "/api/v1/machine-code/reset-password-with-machine-code",
                    json={"username": "testuser", "machine_code": "MC001", "verification_code": "VC001"},
                )
        assert resp.status_code == 429

    def test_machine_code_mismatch(self, client_admin):
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)):
            with patch("app.api.v1.machine_code.get_client_ip", return_value="127.0.0.1"):
                svc = MagicMock()
                svc.get_machine_code.return_value = "DIFFERENT_MC"
                with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
                    resp = client_admin.post(
                        "/api/v1/machine-code/reset-password-with-machine-code",
                        json={"username": "testuser", "machine_code": "MC001", "verification_code": "VC001"},
                    )
        assert resp.status_code == 400
        assert "机器码不匹配" in resp.json()["detail"]

    def test_verification_code_invalid(self, client_admin):
        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)):
            with patch("app.api.v1.machine_code.get_client_ip", return_value="127.0.0.1"):
                svc = MagicMock()
                svc.get_machine_code.return_value = "MC001"
                svc.verify_machine_code.return_value = False
                with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
                    resp = client_admin.post(
                        "/api/v1/machine-code/reset-password-with-machine-code",
                        json={"username": "testuser", "machine_code": "MC001", "verification_code": "BAD"},
                    )
        assert resp.status_code == 400
        assert "校验码不正确" in resp.json()["detail"]

    def test_user_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)):
            with patch("app.api.v1.machine_code.get_client_ip", return_value="127.0.0.1"):
                svc = MagicMock()
                svc.get_machine_code.return_value = "MC001"
                svc.verify_machine_code.return_value = True
                with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
                    resp = client_admin.post(
                        "/api/v1/machine-code/reset-password-with-machine-code",
                        json={"username": "nouser", "machine_code": "MC001", "verification_code": "VC001"},
                    )
        assert resp.status_code == 404

    def test_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        user = MagicMock()
        user.username = "testuser"
        user.hashed_password = "oldhash"
        user.failed_login_count = 3
        user.locked_until = "some"
        q.first.return_value = user

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)):
            with patch("app.api.v1.machine_code.get_client_ip", return_value="127.0.0.1"):
                svc = MagicMock()
                svc.get_machine_code.return_value = "MC001"
                svc.verify_machine_code.return_value = True
                with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
                    with patch("app.core.security.generate_password", return_value="NewPwd123!"):
                        resp = client_admin.post(
                            "/api/v1/machine-code/reset-password-with-machine-code",
                            json={"username": "testuser", "machine_code": "MC001", "verification_code": "VC001"},
                        )
        assert resp.status_code == 200
        assert user.must_change_password is True
        assert user.failed_login_count == 0
        assert user.locked_until is None

    def test_exception(self, client_admin, mock_db):
        svc = MagicMock()
        svc.get_machine_code.side_effect = RuntimeError("Reset error")

        with patch("app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)):
            with patch("app.api.v1.machine_code.get_client_ip", return_value="127.0.0.1"):
                with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
                    resp = client_admin.post(
                        "/api/v1/machine-code/reset-password-with-machine-code",
                        json={"username": "testuser", "machine_code": "MC001", "verification_code": "VC001"},
                    )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  GET /machine-code/machine-info
# ---------------------------------------------------------------------------

class TestGetMachineInfo:
    def test_success(self, client_admin):
        svc = MagicMock()
        svc.get_machine_info.return_value = {"os": "windows", "cpu": "x86"}
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/machine-info")
        assert resp.status_code == 200
        assert resp.json()["data"]["os"] == "windows"

    def test_exception(self, client_admin):
        svc = MagicMock()
        svc.get_machine_info.side_effect = RuntimeError("Info error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/machine-info")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  GET /machine-code/organization/{org_id}/verification-code
# ---------------------------------------------------------------------------

class TestGetOrgVerificationCode:
    def test_permission_denied(self, client_regular):
        resp = client_regular.get("/api/v1/machine-code/organization/1/verification-code")
        assert resp.status_code == 403

    def test_org_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client_admin.get("/api/v1/machine-code/organization/999/verification-code")
        assert resp.status_code == 404

    def test_success(self, client_admin, mock_db):
        org = MagicMock()
        org.id = 1
        org.name = "测试组织"
        q = mock_db.query.return_value
        q.first.return_value = org

        svc = MagicMock()
        svc.generate_organization_verification_code.return_value = "ORG_VC001"
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/1/verification-code")
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_exception(self, client_admin, mock_db):
        org = MagicMock()
        org.id = 1
        org.name = "测试组织"
        q = mock_db.query.return_value
        q.first.return_value = org

        svc = MagicMock()
        svc.generate_organization_verification_code.side_effect = RuntimeError("Gen error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/1/verification-code")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  POST /machine-code/organization/create
# ---------------------------------------------------------------------------

class TestCreateOrgPassCode:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/machine-code/organization/create", json={
            "organization_id": 1, "verification_code": "VC001",
        })
        assert resp.status_code == 403

    def test_org_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client_admin.post("/api/v1/machine-code/organization/create", json={
            "organization_id": 999, "verification_code": "VC001",
        })
        assert resp.status_code == 404

    def test_verification_code_mismatch(self, client_admin, mock_db):
        org = MagicMock()
        org.id = 1
        org.name = "测试组织"
        q = mock_db.query.return_value
        q.first.return_value = org

        svc = MagicMock()
        svc.generate_organization_verification_code.return_value = "EXPECTED"
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/organization/create", json={
                "organization_id": 1, "verification_code": "WRONG",
            })
        assert resp.status_code == 400

    def test_success(self, client_admin, mock_db):
        org = MagicMock()
        org.id = 1
        org.name = "测试组织"
        q = mock_db.query.return_value
        q.first.return_value = org

        record = MagicMock()
        record.id = 1
        record.organization_id = 1
        record.pass_code = "PASS001"
        record.allow_subordinate_generation = True
        record.created_at = None

        svc = MagicMock()
        svc.generate_organization_verification_code.return_value = "VC001"
        svc.create_organization_pass_code.return_value = record
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/organization/create", json={
                "organization_id": 1, "verification_code": "VC001",
                "allow_subordinate_generation": True,
                "description": "test",
            })
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_exception(self, client_admin, mock_db):
        org = MagicMock()
        org.id = 1
        org.name = "测试组织"
        q = mock_db.query.return_value
        q.first.return_value = org

        svc = MagicMock()
        svc.generate_organization_verification_code.return_value = "VC001"
        svc.create_organization_pass_code.side_effect = RuntimeError("Create error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.post("/api/v1/machine-code/organization/create", json={
                "organization_id": 1, "verification_code": "VC001",
            })
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  GET /machine-code/organization/list
# ---------------------------------------------------------------------------

class TestListOrgPassCodes:
    def test_permission_denied(self, client_regular):
        resp = client_regular.get("/api/v1/machine-code/organization/list")
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        record = MagicMock()
        record.id = 1
        record.organization_id = 1
        record.pass_code = "PASS001"
        record.allow_subordinate_generation = False
        record.status = "active"
        record.created_at = None
        record.created_by = 1
        record.organization = MagicMock()
        record.organization.id = 1
        record.organization.name = "测试组织"

        svc = MagicMock()
        svc.get_organization_pass_codes.return_value = ([record], 1)
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/list")
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_no_org(self, client_admin, mock_db):
        record = MagicMock()
        record.id = 1
        record.organization_id = 0
        record.pass_code = "PASS001"
        record.allow_subordinate_generation = False
        record.status = "active"
        record.created_at = None
        record.created_by = 1
        record.organization = None

        svc = MagicMock()
        svc.get_organization_pass_codes.return_value = ([record], 1)
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/list")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["organization_name"] is None
        assert resp.json()["data"]["items"][0]["verification_code"] == ""

    def test_exception(self, client_admin, mock_db):
        svc = MagicMock()
        svc.get_organization_pass_codes.side_effect = RuntimeError("List error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/list")
        assert resp.status_code == 500

    def test_http_exception_re_raised(self, client_admin, mock_db):
        from fastapi import HTTPException as FastAPIHTTPException
        svc = MagicMock()
        svc.get_organization_pass_codes.side_effect = FastAPIHTTPException(400, "custom")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/list")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  GET /machine-code/organization/export
# ---------------------------------------------------------------------------
#  GET /machine-code/organization/export
# ---------------------------------------------------------------------------

class TestExportOrgPassCodes:
    def test_permission_denied(self, client_regular):
        resp = client_regular.get("/api/v1/machine-code/organization/export")
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        record = MagicMock()
        record.id = 1
        record.organization_id = 1
        record.pass_code = "PASS001"
        record.allow_subordinate_generation = False
        record.status = "active"
        record.created_at = None
        record.organization = MagicMock()
        record.organization.id = 1
        record.organization.name = "测试组织"

        svc = MagicMock()
        svc.get_organization_pass_codes.return_value = ([record], 1)
        svc.generate_organization_verification_code.return_value = "VC001"

        export_svc = MagicMock()
        export_svc.export_organization_pass_codes.return_value = b"excel data"

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            with patch("app.services.export_service.ExcelExportService", return_value=export_svc):
                resp = client_admin.get("/api/v1/machine-code/organization/export")
        assert resp.status_code == 200
        assert "application/vnd.openxmlformats" in resp.headers.get("content-type", "")

    def test_no_org(self, client_admin, mock_db):
        record = MagicMock()
        record.id = 1
        record.organization_id = 0
        record.pass_code = "PASS001"
        record.allow_subordinate_generation = False
        record.status = "active"
        record.created_at = None
        record.organization = None

        svc = MagicMock()
        svc.get_organization_pass_codes.return_value = ([record], 1)

        export_svc = MagicMock()
        export_svc.export_organization_pass_codes.return_value = b"excel data"

        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            with patch("app.services.export_service.ExcelExportService", return_value=export_svc):
                resp = client_admin.get("/api/v1/machine-code/organization/export")
        assert resp.status_code == 200

    def test_exception(self, client_admin, mock_db):
        svc = MagicMock()
        svc.get_organization_pass_codes.side_effect = RuntimeError("Export error")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/export")
        assert resp.status_code == 500

    def test_export_http_exception_re_raised(self, client_admin, mock_db):
        from fastapi import HTTPException as FastAPIHTTPException
        svc = MagicMock()
        svc.get_organization_pass_codes.side_effect = FastAPIHTTPException(400, "custom")
        with patch("app.api.v1.machine_code.MachineCodeService", return_value=svc):
            resp = client_admin.get("/api/v1/machine-code/organization/export")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  Endpoints using require_admin (known bug: require_admin takes 1 arg, called with 2)
#  These endpoints will raise TypeError when called.
# ---------------------------------------------------------------------------

class TestMachineCodePermissions:
    def test_get_permissions_success(self, client_admin, mock_db):
        """获取机器码权限列表 — 管理员调用应成功返回 200"""
        resp = client_admin.get("/api/v1/machine-code/1/permissions")
        assert resp.status_code == 200

    def test_grant_permissions_success(self, client_admin, mock_db):
        """批量授予机器码权限 — 管理员调用应成功返回 200"""
        resp = client_admin.post("/api/v1/machine-code/1/permissions", json={
            "permissions": ["village:read"],
        })
        assert resp.status_code == 200

    def test_revoke_permissions_success(self, client_admin, mock_db):
        """批量撤销机器码权限 — 管理员调用应成功返回 200"""
        resp = client_admin.request("DELETE", "/api/v1/machine-code/1/permissions", json={
            "permissions": ["village:read"],
        })
        assert resp.status_code == 200

    def test_revoke_single_permission_not_found(self, client_admin, mock_db):
        """撤销单个权限 — mock DB 中不存在记录时应返回 404"""
        resp = client_admin.delete("/api/v1/machine-code/1/permissions/village:read")
        assert resp.status_code == 404

    def test_user_effective_permissions_success(self, client_admin, mock_db):
        """获取用户实际生效权限 — 管理员调用应成功返回 200"""
        resp = client_admin.get("/api/v1/machine-code/user/1/effective-permissions")
        assert resp.status_code == 200
