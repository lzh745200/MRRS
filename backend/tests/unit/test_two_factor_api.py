"""Tests for app.api.v1.auth.two_factor - zero coverage → 100%"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def mock_user():
    user = MagicMock(name="User")
    user.id = 1
    user.username = "testuser"
    return user


@pytest.fixture
def mock_db():
    return MagicMock(name="Session")


@pytest.fixture
def two_factor_app(mock_user, mock_db):
    """Create a minimal FastAPI app with the two-factor router and overridden dependencies."""
    from app.api.v1 import deps
    app = FastAPI()

    app.dependency_overrides[deps.get_current_active_user] = lambda: mock_user
    app.dependency_overrides[deps.get_db] = lambda: mock_db

    from app.api.v1.auth.two_factor import router
    app.include_router(router)
    return app


@pytest.fixture
def client(two_factor_app):
    return TestClient(two_factor_app)


# Patch at the service level (the source of TwoFactorService)
SVC_PATH = "app.services.two_factor_service.TwoFactorService"


class TestEnableTwoFactor:
    def test_success(self, client):
        with patch(f"{SVC_PATH}.enable_two_factor", return_value={
            "secret": "JBSWY3DPEHPK3PXP",
            "qr_code": "otpauth://...",
            "backup_codes": ["111111", "222222"],
        }):
            resp = client.post("/two-factor/enable")
            assert resp.status_code == 200
            data = resp.json()
            assert data["secret"] == "JBSWY3DPEHPK3PXP"
            assert len(data["backup_codes"]) == 2

    def test_value_error(self, client):
        with patch(f"{SVC_PATH}.enable_two_factor", side_effect=ValueError("已启用")):
            resp = client.post("/two-factor/enable")
            assert resp.status_code == 400
            assert "已启用" in resp.json()["detail"]

    def test_generic_exception(self, client):
        with patch(f"{SVC_PATH}.enable_two_factor", side_effect=RuntimeError("broke")):
            resp = client.post("/two-factor/enable")
            assert resp.status_code == 500
            assert "启用双因素认证失败" in resp.json()["detail"]


class TestVerifyAndEnable:
    def test_success(self, client):
        with patch(f"{SVC_PATH}.verify_and_enable", return_value=True):
            resp = client.post("/two-factor/verify", json={"token": "123456"})
            assert resp.status_code == 200
            assert resp.json()["message"] == "双因素认证已启用"

    def test_wrong_token(self, client):
        with patch(f"{SVC_PATH}.verify_and_enable", return_value=False):
            resp = client.post("/two-factor/verify", json={"token": "000000"})
            assert resp.status_code == 400
            assert "验证码错误" in resp.json()["detail"]

    def test_value_error(self, client):
        with patch(f"{SVC_PATH}.verify_and_enable", side_effect=ValueError("未初始化")):
            resp = client.post("/two-factor/verify", json={"token": "123456"})
            assert resp.status_code == 400

    def test_generic_exception(self, client):
        with patch(f"{SVC_PATH}.verify_and_enable", side_effect=Exception("db down")):
            resp = client.post("/two-factor/verify", json={"token": "123456"})
            assert resp.status_code == 500
            assert "验证失败" in resp.json()["detail"]


class TestDisableTwoFactor:
    def test_success(self, client):
        with patch(f"{SVC_PATH}.disable_two_factor", return_value=None):
            resp = client.post("/two-factor/disable")
            assert resp.status_code == 200
            assert resp.json()["message"] == "双因素认证已禁用"

    def test_exception(self, client):
        with patch(f"{SVC_PATH}.disable_two_factor", side_effect=Exception("err")):
            resp = client.post("/two-factor/disable")
            assert resp.status_code == 500
            assert "禁用失败" in resp.json()["detail"]


class TestGetTwoFactorStatus:
    def test_enabled(self, client):
        with patch(f"{SVC_PATH}.is_enabled", return_value=True):
            resp = client.get("/two-factor/status")
            assert resp.status_code == 200
            assert resp.json()["enabled"] is True

    def test_disabled(self, client):
        with patch(f"{SVC_PATH}.is_enabled", return_value=False):
            resp = client.get("/two-factor/status")
            assert resp.status_code == 200
            assert resp.json()["enabled"] is False
