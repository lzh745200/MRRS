"""W24 注册来源门禁回归（P1-5 决策，2026-10-19）。

决策：保留跨机注册产品能力（R9），但「非回环来源 + 未配置 PASS_CODE_SECRET」
fail-closed 403；回环来源（单机桌面开箱 / TestClient）保持原行为；已配置密钥的
部署行为完全不变。
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.v1.auth import auth as auth_module
from app.core.config import settings
from app.utils.audit_logger import AuditLevel

_REGISTER_URL = "/api/v1/auth/register"


def _make_user(**kwargs):
    user = Mock()
    user.id = kwargs.get("id", 9)
    user.username = kwargs.get("username", "newuser")
    user.email = kwargs.get("email", "newuser@local.system")
    user.full_name = kwargs.get("full_name", "newuser")
    user.hashed_password = "hashed"
    user.role = kwargs.get("role", "user")
    user.is_active = True
    user.is_superuser = False
    user.organization_id = None
    user.allowed_menus = None
    user.allowed_menus_list = None
    user.token_version_safe = 1
    return user


def _register_payload(**overrides):
    payload = {
        "username": "newuser",
        "password": "Str0ng!Passw0rd",
        "pass_code": "PASS-CODE-1234",
    }
    payload.update(overrides)
    return payload


class TestRegisterLocalSourceMatrix:
    @pytest.mark.parametrize(
        "host,expected",
        [
            ("127.0.0.1", True),
            ("::1", True),
            ("localhost", True),
            ("testclient", True),
            ("10.20.30.40", False),
            ("192.168.1.5", False),
            ("unknown", False),
        ],
    )
    def test_local_source_matrix(self, host, expected):
        """回环/TestClient 视为本机，其余（含无法判定 unknown）一律非本机。"""
        with patch.object(auth_module, "get_client_ip", return_value=host):
            assert auth_module._is_local_register_source(Mock()) is expected


class TestRegisterSourceGate:
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="10.20.30.40")
    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    def test_non_loopback_without_secret_denied_with_audit(
        self, mock_rate_limit, mock_get_client_ip, mock_audit_logger, mock_user_service,
        monkeypatch, client,
    ):
        """非回环 + 未配置 PASS_CODE_SECRET → 403 + 审计 register_denied_untrusted。"""
        mock_rate_limit.return_value = True
        monkeypatch.setattr(settings, "PASS_CODE_SECRET", "")

        response = client.post(_REGISTER_URL, json=_register_payload())

        assert response.status_code == 403
        assert "PASS_CODE_SECRET" in response.json()["detail"]
        # 门禁在开户之前：不得创建用户
        mock_user_service.assert_not_called()
        # 审计留痕（可追溯的拒绝记录）
        mock_audit_logger.log.assert_called_once()
        call_kwargs = mock_audit_logger.log.call_args.kwargs
        assert call_kwargs["action"] == "register_denied_untrusted"
        assert call_kwargs["ip_address"] == "10.20.30.40"
        assert call_kwargs["details"]["reason"] == "non_loopback_register_without_pass_code_secret"
        assert call_kwargs["level"] == AuditLevel.WARNING

    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    def test_non_loopback_with_secret_passes_gate(self, mock_rate_limit, mock_mc_cls, monkeypatch, client):
        """非回环 + 已配置 PASS_CODE_SECRET → 保持原跨机注册行为（R9）。"""
        mock_rate_limit.return_value = True
        monkeypatch.setattr(settings, "PASS_CODE_SECRET", "shared-secret-for-w24")
        machine = Mock()
        machine.get_machine_code.return_value = "mcode123"
        machine.verify_pass_code.return_value = Mock(organization_id=None)
        mock_mc_cls.return_value = machine

        with patch("app.api.v1.auth.auth.UserService") as mock_usr_cls, patch(
            "app.api.v1.auth.auth.token_manager"
        ) as mock_tm:
            user_service = Mock()
            user_service.get_user_by_username.return_value = None
            user_service.get_user_by_email.return_value = None
            user_service.create_user.return_value = _make_user()
            mock_usr_cls.return_value = user_service
            mock_tm.create_token_pair.return_value = {"access_token": "at", "refresh_token": "rt"}

            response = client.post(_REGISTER_URL, json=_register_payload())

        assert response.status_code == 200, response.text[:300]
        assert response.json()["data"]["access_token"] == "at"
        user_service.create_user.assert_called_once()

    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    def test_testclient_source_without_secret_keeps_existing_flow(
        self, mock_rate_limit, mock_mc_cls, monkeypatch, client,
    ):
        """TestClient 视为回环来源（与 request_logger 的受信集合一致），不拦截。"""
        mock_rate_limit.return_value = True
        monkeypatch.setattr(settings, "PASS_CODE_SECRET", "")
        machine = Mock()
        machine.get_machine_code.return_value = "mcode123"
        machine.verify_pass_code.return_value = None  # 走到「通行码无效」而非来源拦截
        mock_mc_cls.return_value = machine

        response = client.post(_REGISTER_URL, json=_register_payload(pass_code="bad-code"))

        assert response.status_code == 400
        assert "通行码无效" in response.json()["detail"]

    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    def test_loopback_without_secret_keeps_existing_flow(
        self, mock_rate_limit, mock_get_client_ip, mock_mc_cls, monkeypatch, client,
    ):
        """回环来源 + 未配置密钥 → 单机桌面开箱行为不变（不拦来源）。"""
        mock_rate_limit.return_value = True
        monkeypatch.setattr(settings, "PASS_CODE_SECRET", "")
        machine = Mock()
        machine.get_machine_code.return_value = "mcode123"
        machine.verify_pass_code.return_value = None
        mock_mc_cls.return_value = machine

        response = client.post(_REGISTER_URL, json=_register_payload(pass_code="bad-code"))

        assert response.status_code == 400
        assert "通行码无效" in response.json()["detail"]
