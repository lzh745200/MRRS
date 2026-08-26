"""app.api.v1.auth.auth 覆盖率攻坚测试 — 双因素认证（2FA）全路径

既有 test_auth_auth_api.py 未覆盖：
- 登录时 TwoFactorService.is_enabled=True → 签发临时令牌（206-219）
- /two-factor/verify-login 端点全部分支（290-443）

Mock 风格与 test_auth_auth_api.py 保持一致。
"""

from unittest.mock import AsyncMock, Mock, patch


def _make_user(**kwargs):
    user = Mock()
    user.id = kwargs.get("id", 1)
    user.username = kwargs.get("username", "testuser")
    user.email = kwargs.get("email", "test@example.com")
    user.full_name = kwargs.get("full_name", "Test User")
    user.hashed_password = kwargs.get("hashed_password", "hashed_pwd")
    user.role = kwargs.get("role", "user")
    user.is_active = kwargs.get("is_active", True)
    user.is_superuser = kwargs.get("is_superuser", False)
    user.organization_id = kwargs.get("organization_id", 1)
    user.organization_name = kwargs.get("organization_name", "TestOrg")
    user.permissions_list = kwargs.get("permissions_list", ["read"])
    user.allowed_menus = kwargs.get("allowed_menus", None)
    user.allowed_menus_list = kwargs.get("allowed_menus_list", None)
    user.failed_login_count = kwargs.get("failed_login_count", 3)
    user.locked_until = kwargs.get("locked_until", None)
    user.must_change_password = kwargs.get("must_change_password", False)
    user.password_changed_at = kwargs.get("password_changed_at", None)
    user.last_login = kwargs.get("last_login", None)
    user.token_version_safe = kwargs.get("token_version_safe", 1)
    return user


class TestLoginTwoFactorRequired:
    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_2fa_required_returns_temp_token(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        """密码与机器码通过后启用2FA → 返回 two_factor_required + temp_token"""
        mock_rl.return_value = True
        user = _make_user(failed_login_count=0)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True), patch(
            "app.services.machine_code_service.MachineCodeService"
        ) as mock_mc_cls, patch(
            "app.services.two_factor_service.TwoFactorService"
        ) as mock_2fa_cls, patch(
            "app.api.v1.auth.auth.token_manager"
        ) as mock_tm:
            mc_instance = Mock()
            mc_instance.get_machine_code.return_value = "mcode123"
            mc_instance.verify_user_machine.return_value = True
            mock_mc_cls.return_value = mc_instance
            mock_2fa_cls.is_enabled.return_value = True
            mock_tm.create_token_pair.return_value = {"access_token": "temp-token-1"}

            response = client.post(
                f"{self.prefix}/login",
                json={"username": "testuser", "password": "testpass"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["two_factor_required"] is True
        assert body["temp_token"] == "temp-token-1"
        assert body["data"] is None
        assert body["message"] == "需要双因素认证"
        # 临时令牌带 two_factor_pending 声明且短时效
        kwargs = mock_tm.create_token_pair.call_args.kwargs
        assert kwargs["extra_claims"] == {"two_factor_pending": True}
        assert kwargs["access_ttl_minutes"] == 5


class TestTwoFactorVerifyLogin:
    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    def test_rate_limit_429(self, mock_ip, mock_rl, client):
        mock_rl.return_value = False
        response = client.post(
            f"{self.prefix}/two-factor/verify-login",
            json={"temp_token": "t", "code": "123456"},
        )
        assert response.status_code == 429

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_decode_raises_401(self, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.side_effect = Exception("bad token")
        response = client.post(
            f"{self.prefix}/two-factor/verify-login",
            json={"temp_token": "t", "code": "123456"},
        )
        assert response.status_code == 401
        assert "临时令牌无效或已过期" in response.json()["detail"]

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_not_pending_token_401(self, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser"}  # 无 two_factor_pending
        response = client.post(
            f"{self.prefix}/two-factor/verify-login",
            json={"temp_token": "t", "code": "123456"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "无效的临时令牌"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_no_sub_401(self, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"two_factor_pending": True}  # 无 sub
        response = client.post(
            f"{self.prefix}/two-factor/verify-login",
            json={"temp_token": "t", "code": "123456"},
        )
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_user_not_found_401(self, mock_tm, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "ghost", "two_factor_pending": True}
        inst = Mock()
        inst.get_user_by_username.return_value = None
        mock_usr_svc.return_value = inst
        response = client.post(
            f"{self.prefix}/two-factor/verify-login",
            json={"temp_token": "t", "code": "123456"},
        )
        assert response.status_code == 401
        assert "用户不存在或已被禁用" in response.json()["detail"]

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_user_inactive_401(self, mock_tm, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser", "two_factor_pending": True}
        inst = Mock()
        inst.get_user_by_username.return_value = _make_user(is_active=False)
        mock_usr_svc.return_value = inst
        response = client.post(
            f"{self.prefix}/two-factor/verify-login",
            json={"temp_token": "t", "code": "123456"},
        )
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_wrong_code_401(self, mock_tm, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser", "two_factor_pending": True}
        inst = Mock()
        inst.get_user_by_username.return_value = _make_user()
        mock_usr_svc.return_value = inst
        with patch("app.services.two_factor_service.TwoFactorService") as mock_2fa_cls:
            mock_2fa_cls.verify_login.return_value = False
            response = client.post(
                f"{self.prefix}/two-factor/verify-login",
                json={"temp_token": "t", "code": "000000"},
            )
        assert response.status_code == 401
        assert "验证码错误" in response.json()["detail"]
        mock_audit.log_login.assert_called_once()

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_success(self, mock_tm, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        """验证通过 → 吊销临时令牌、重置失败计数、签发正式令牌"""
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser", "two_factor_pending": True}
        mock_tm.create_token_pair.return_value = {"access_token": "at2", "refresh_token": "rt2"}
        user = _make_user(failed_login_count=3)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.services.two_factor_service.TwoFactorService") as mock_2fa_cls:
            mock_2fa_cls.verify_login.return_value = True
            response = client.post(
                f"{self.prefix}/two-factor/verify-login",
                json={"temp_token": "temp-token-1", "code": "123456"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["access_token"] == "at2"
        assert body["refresh_token"] == "rt2"
        assert body["message"] == "登录成功"
        mock_tm.revoke_token.assert_called_once_with("temp-token-1")
        assert user.failed_login_count == 0
        assert user.locked_until is None

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_success_superuser_role_fix_and_password_expired(
        self, mock_tm, mock_audit, mock_usr_svc, mock_ip, mock_rl, client
    ):
        """is_superuser 角色修正 + 密码过期（naive 时间戳）→ must_change"""
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser", "two_factor_pending": True}
        mock_tm.create_token_pair.return_value = {"access_token": "at2", "refresh_token": "rt2"}
        user = _make_user(
            is_superuser=True,
            role="user",
            failed_login_count=0,
            password_changed_at=datetime.now() - timedelta(days=3650),  # naive，远超期
        )
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.services.two_factor_service.TwoFactorService") as mock_2fa_cls:
            mock_2fa_cls.verify_login.return_value = True
            response = client.post(
                f"{self.prefix}/two-factor/verify-login",
                json={"temp_token": "t", "code": "123456"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["user"]["role"] == "super_admin"
        assert body["must_change_password"] is True
        assert body["message"] == "密码已过期，请修改密码"


# ==================== 补充：既有测试因 coverage CTracer 在线程内协程恢复时 ====================
# ==================== 丢失行事件而漏记的缺口（行为已由 TestClient 用例证明，直接调用补测） ====================

from datetime import datetime, timedelta, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import app.api.v1.auth.auth as auth_mod  # noqa: E402
from app.core.exceptions import UserAlreadyExistsError  # noqa: E402


class TestHandleFailedLoginLockout:
    """_handle_failed_login 达到锁定阈值分支（84、88 行）"""

    def test_lockout_threshold_reached(self):
        user = Mock()
        user.failed_login_count = auth_mod._MAX_FAILED_ATTEMPTS - 1
        user.locked_until = None
        db = Mock()
        now = datetime.now(timezone.utc)
        # W2-T6：lockout_service 接管计数，需 mock 其 record_failed 返回阈值
        mock_lockout = Mock()
        mock_lockout.record_failed.return_value = auth_mod._MAX_FAILED_ATTEMPTS
        with patch.object(auth_mod, "AuditLogger"), \
             patch("app.services.lockout_service.get_lockout_service", return_value=mock_lockout):
            auth_mod._handle_failed_login(user, "testuser", db, now, "127.0.0.1", "ua")
        assert mock_lockout.record_failed.called
        assert mock_lockout.record_failed.call_count == 1


class TestLoginResetFailedCount:
    """登录成功后重置失败计数（222-224 行，非 2FA 路径）"""

    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_resets_failed_count(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user(failed_login_count=3, locked_until=None)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True), patch(
            "app.services.machine_code_service.MachineCodeService"
        ) as mock_mc_cls, patch(
            "app.services.two_factor_service.TwoFactorService"
        ) as mock_2fa_cls, patch(
            "app.api.v1.auth.auth.token_manager"
        ) as mock_tm:
            mc_instance = Mock()
            mc_instance.get_machine_code.return_value = "mcode123"
            mc_instance.verify_user_machine.return_value = True
            mock_mc_cls.return_value = mc_instance
            mock_2fa_cls.is_enabled.return_value = False
            mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}

            response = client.post(
                f"{self.prefix}/login",
                json={"username": "testuser", "password": "testpass"},
            )

        assert response.status_code == 200
        assert user.failed_login_count == 0
        assert user.locked_until is None


class TestLogoutDirectCall:
    """logout 端点直接调用：541-544 请求体吊销、549-561 审计与返回、532-533 解码异常"""

    def _request(self, body):
        req = Mock()
        req.json = AsyncMock(return_value=body)
        req.headers = {"user-agent": "ua-test"}
        return req

    async def test_full_flow_revokes_and_audits(self):
        credentials = SimpleNamespace(credentials="sometoken")
        with patch.object(auth_mod, "token_manager") as mock_tm, patch(
            "app.api.v1.auth.auth.UserService"
        ) as mock_usr_svc, patch(
            "app.api.v1.auth.auth.AuditLogger"
        ) as mock_audit, patch(
            "app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1"
        ):
            mock_tm.decode_token.return_value = {"sub": "testuser"}
            db_user = Mock()
            db_user.id = 42
            inst = Mock()
            inst.get_user_by_username.return_value = db_user
            mock_usr_svc.return_value = inst

            result = await auth_mod.logout(self._request({"refresh_token": "rt123"}), credentials, Mock())

        assert result == {"code": 200, "message": "登出成功"}
        mock_tm.revoke_token.assert_any_call("sometoken")
        mock_tm.revoke_token.assert_any_call("rt123")
        mock_audit.log.assert_called_once()
        kwargs = mock_audit.log.call_args.kwargs
        assert kwargs["user_id"] == 42
        assert kwargs["username"] == "testuser"

    async def test_decode_raises_still_revokes_body_token(self):
        credentials = SimpleNamespace(credentials="badtoken")
        with patch.object(auth_mod, "token_manager") as mock_tm, patch(
            "app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1"
        ):
            mock_tm.decode_token.side_effect = Exception("bad token")
            result = await auth_mod.logout(self._request({"refresh_token": "rt2"}), credentials, Mock())

        assert result == {"code": 200, "message": "登出成功"}
        mock_tm.revoke_token.assert_any_call("badtoken")
        mock_tm.revoke_token.assert_any_call("rt2")


class TestRegisterCreateUserReraise:
    """try 块内 create_user 抛 UserAlreadyExistsError → except 透传（836 行）"""

    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.UserService")
    def test_create_user_raises_reraises(
        self, mock_usr_svc, mock_mc_cls, mock_policy, mock_ip, mock_rl, client
    ):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (True, "")
        mc_instance = Mock()
        mc_instance.get_machine_code.return_value = "mcode123"
        mc_instance.verify_pass_code.return_value = Mock()
        mock_mc_cls.return_value = mc_instance
        usr_instance = Mock()
        usr_instance.get_user_by_username.return_value = None
        usr_instance.get_user_by_email.return_value = None
        usr_instance.create_user.side_effect = UserAlreadyExistsError("newuser")
        mock_usr_svc.return_value = usr_instance

        response = client.post(
            f"{self.prefix}/register",
            json={"username": "newuser", "password": "Str0ng!Pass123", "pass_code": "code123"},
        )
        assert response.status_code == 409
