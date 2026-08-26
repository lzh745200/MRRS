"""
Tests for init.py — system initialization API.
"""

from unittest.mock import MagicMock, patch

BASE = "/api/v1/system/init"


class TestGetInitChecklist:
    def test_returns_checklist(self, client):
        resp = client.get(f"{BASE}/checklist")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["checklist"]) >= 5


class TestCheckInitStatus:
    def test_not_initialized(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = False
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["initialized"] is False
        assert "version" in data

    def test_initialized(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = True
        mock_svc.get.side_effect = lambda key, default=None: {
            "organization_name": "测试单位",
            "system_name": "测试系统",
            "init_timestamp": "2024-01-01T00:00:00",
        }.get(key, default)
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["initialized"] is True
        assert data["organization_name"] == "测试单位"

    def test_exception_fallback(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.side_effect = RuntimeError("DB error")
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["initialized"] is False
        # W1-T8：内部异常细节不出站
        assert data["error"] == "状态检查失败，请查看服务端日志"


class TestInitializeSystem:
    def test_success(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = False
        with (
            patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc),
            patch("app.core.security.get_password_hash", return_value="hashed"),
        ):
            resp = client.post(
                f"{BASE}/initialize",
                json={
                    "organization_name": "测试单位",
                    "admin_username": "admin",
                    "admin_password": "Str0ng!Passw0rd",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_already_initialized(self, client):
        mock_svc = MagicMock()
        mock_svc.is_initialized.return_value = True
        with patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc):
            resp = client.post(
                f"{BASE}/initialize",
                json={
                    "organization_name": "测试单位",
                    "admin_username": "admin",
                    "admin_password": "Str0ng!Passw0rd",
                },
            )
        assert resp.status_code == 400
        assert "已" in resp.json()["detail"]


class TestResetInitialization:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/reset?confirm=RESET")
        assert resp.status_code == 401

    def test_requires_confirm_string(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/reset?confirm=wrong&admin_password=x"
        )
        assert resp.status_code == 400
        assert "RESET" in resp.json()["detail"]

    def test_success(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        with (
            patch("app.api.v1.system.init.SystemConfigService", return_value=mock_svc),
            patch("app.core.security.verify_password", return_value=True),
        ):
            resp = client_with_mocked_auth.post(
                f"{BASE}/reset?confirm=RESET&admin_password=Str0ng!Pass"
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_svc.set.assert_any_call("initialized", "false")
