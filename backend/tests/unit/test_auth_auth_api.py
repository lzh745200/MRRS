import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone, timedelta


from app.core.database import get_db
from app.core.security import get_current_user as _get_current_user



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
    user.failed_login_count = kwargs.get("failed_login_count", 0)
    user.locked_until = kwargs.get("locked_until", None)
    user.must_change_password = kwargs.get("must_change_password", False)
    user.password_changed_at = kwargs.get("password_changed_at", None)
    user.last_login = kwargs.get("last_login", None)
    user.token_version_safe = kwargs.get("token_version_safe", 1)
    return user


class TestLogin:
    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    def test_login_rate_limit_exceeded(self, mock_ip, mock_rl, client):
        mock_rl.return_value = False
        response = client.post(
            f"{self.prefix}/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 429

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_user_not_found(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        inst = Mock()
        inst.get_user_by_username.return_value = None
        mock_usr_svc.return_value = inst

        response = client.post(
            f"{self.prefix}/login",
            json={"username": "unknown", "password": "testpass"},
        )
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_user_not_active(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user(is_active=False)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        response = client.post(
            f"{self.prefix}/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 403

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_locked_expired_cleanup(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        expired_lock = datetime.now(timezone.utc) - timedelta(minutes=10)
        user = _make_user(locked_until=expired_lock, failed_login_count=3)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode123"
                mc_instance.verify_user_machine.return_value = True
                mock_mc_cls.return_value = mc_instance
                with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
                    mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
                    response = client.post(
                        f"{self.prefix}/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
                    assert response.status_code == 200
                    assert user.locked_until is None
                    assert user.failed_login_count == 0

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_still_locked(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        future_lock = datetime.now(timezone.utc) + timedelta(minutes=30)
        user = _make_user(locked_until=future_lock, failed_login_count=5)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        response = client.post(
            f"{self.prefix}/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 423

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_locked_exception(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user()

        class BadLockedUntil:
            tzinfo = None
            def __gt__(self, other):
                raise RuntimeError("boom")
            def __ge__(self, other):
                raise RuntimeError("boom")
            def __sub__(self, other):
                raise RuntimeError("boom")

        user.locked_until = BadLockedUntil()
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        response = client.post(
            f"{self.prefix}/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 500

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_wrong_password(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user(failed_login_count=1)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=False):
            with patch("app.api.v1.auth.auth.AuditLogger.log_login") as mock_log:
                response = client.post(
                    f"{self.prefix}/login",
                    json={"username": "testuser", "password": "wrongpass"},
                )
                assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_wrong_password_lockout(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        from app.core.config import settings
        max_attempts = settings.MAX_FAILED_LOGIN_ATTEMPTS
        user = _make_user(failed_login_count=max_attempts - 1)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=False):
            response = client.post(
                f"{self.prefix}/login",
                json={"username": "testuser", "password": "wrongpass"},
            )
            assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_wrong_password_update_exception(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user(failed_login_count=2)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        mock_db = Mock()
        mock_db.execute.side_effect = RuntimeError("DB write fail")
        mock_db.query = Mock()

        old_overrides = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch("app.api.v1.auth.auth.verify_password", return_value=False):
            response = client.post(
                f"{self.prefix}/login",
                json={"username": "testuser", "password": "wrongpass"},
            )
            assert response.status_code in [401, 500]

        client.app.dependency_overrides = old_overrides

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_machine_code_denied(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user()
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode456"
                mc_instance.verify_user_machine.return_value = False
                mock_mc_cls.return_value = mc_instance
                response = client.post(
                    f"{self.prefix}/login",
                    json={"username": "testuser", "password": "testpass"},
                )
                assert response.status_code == 403

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_success_superadmin_role_fix(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user(is_superuser=True, role="user")
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode123"
                mc_instance.verify_user_machine.return_value = True
                mock_mc_cls.return_value = mc_instance
                with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
                    mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
                    response = client.post(
                        f"{self.prefix}/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
                    assert response.status_code == 200
                    assert response.json()["data"]["user"]["role"] == "super_admin"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_password_expired(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        old_date = datetime.now(timezone.utc) - timedelta(days=999)
        user = _make_user(password_changed_at=old_date, must_change_password=False)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode123"
                mc_instance.verify_user_machine.return_value = True
                mock_mc_cls.return_value = mc_instance
                with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
                    mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
                    response = client.post(
                        f"{self.prefix}/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
                    assert response.status_code == 200
                    assert response.json()["must_change_password"] is True
                    assert "密码已过期" in response.json()["message"]

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_first_login_must_change(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user(must_change_password=True, password_changed_at=None)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode123"
                mc_instance.verify_user_machine.return_value = True
                mock_mc_cls.return_value = mc_instance
                with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
                    mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
                    response = client.post(
                        f"{self.prefix}/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
                    assert response.status_code == 200
                    assert "首次登录" in response.json()["message"]

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_success_normal(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        user = _make_user()
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode123"
                mc_instance.verify_user_machine.return_value = True
                mock_mc_cls.return_value = mc_instance
                with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
                    mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
                    response = client.post(
                        f"{self.prefix}/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["code"] == 200
                    assert data["data"]["access_token"] == "at1"
                    assert data["refresh_token"] == "rt1"
                    assert data["must_change_password"] is False

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_locked_tz_naive(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        naive_lock = datetime.now() + timedelta(hours=1)
        user = _make_user(locked_until=naive_lock, failed_login_count=5)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        response = client.post(
            f"{self.prefix}/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 423

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_login_password_tz_naive(self, mock_audit, mock_usr_svc, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        old_date = datetime.now() - timedelta(days=999)
        user = _make_user(password_changed_at=old_date, must_change_password=False)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst

        with patch("app.api.v1.auth.auth.verify_password", return_value=True):
            with patch("app.services.machine_code_service.MachineCodeService") as mock_mc_cls:
                mc_instance = Mock()
                mc_instance.get_machine_code.return_value = "mcode123"
                mc_instance.verify_user_machine.return_value = True
                mock_mc_cls.return_value = mc_instance
                with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
                    mock_tm.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
                    response = client.post(
                        f"{self.prefix}/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
                    assert response.status_code == 200
                    assert response.json()["must_change_password"] is True


class TestMe:
    prefix = "/api/v1/auth"

    def _override_gcu(self, client, user):
        async def mock_gcu():
            return user
        client.app.dependency_overrides[_get_current_user] = mock_gcu

    def _clear_gcu(self, client):
        client.app.dependency_overrides.pop(_get_current_user, None)

    def test_me_user_not_found(self, client):
        current = Mock()
        current.username = "nonexistent"
        self._override_gcu(client, current)

        with patch("app.api.v1.auth.auth.UserService") as mock_usr_svc:
            inst = Mock()
            inst.get_user_by_username.return_value = None
            mock_usr_svc.return_value = inst
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 401

        self._clear_gcu(client)

    def test_me_success(self, client):
        current = Mock()
        current.username = "testuser"
        self._override_gcu(client, current)

        db_user = _make_user(is_superuser=True, role="user")
        with patch("app.api.v1.auth.auth.UserService") as mock_usr_svc:
            inst = Mock()
            inst.get_user_by_username.return_value = db_user
            mock_usr_svc.return_value = inst
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 200
            assert response.json()["data"]["role"] == "super_admin"

        self._clear_gcu(client)

    def test_me_superuser_by_role(self, client):
        current = Mock()
        current.username = "adminuser"
        self._override_gcu(client, current)

        db_user = _make_user(is_superuser=False, role="admin")
        with patch("app.api.v1.auth.auth.UserService") as mock_usr_svc:
            inst = Mock()
            inst.get_user_by_username.return_value = db_user
            mock_usr_svc.return_value = inst
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 200
            assert response.json()["data"]["is_superuser"] is True

        self._clear_gcu(client)


class TestLogout:
    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    def test_logout_no_credentials(self, mock_ip, client):
        response = client.post(f"{self.prefix}/logout")
        assert response.status_code == 200

    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.UserService")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_logout_with_token_and_audit(self, mock_audit, mock_usr_svc, mock_ip, mock_tm, client):
        mock_tm.decode_token.return_value = {"sub": "testuser"}
        db_user = Mock()
        db_user.id = 1
        inst = Mock()
        inst.get_user_by_username.return_value = db_user
        mock_usr_svc.return_value = inst

        response = client.post(
            f"{self.prefix}/logout",
            json={"refresh_token": "rt123"},
            headers={"Authorization": "Bearer sometoken"},
        )
        assert response.status_code == 200
        mock_tm.revoke_token.assert_any_call("sometoken")
        mock_tm.revoke_token.assert_any_call("rt123")

    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_logout_token_decode_fails(self, mock_audit, mock_ip, mock_tm, client):
        mock_tm.decode_token.return_value = None
        response = client.post(
            f"{self.prefix}/logout",
            headers={"Authorization": "Bearer badtoken"},
        )
        assert response.status_code == 200
        mock_tm.revoke_token.assert_called_once_with("badtoken")

    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_logout_body_not_json(self, mock_audit, mock_ip, mock_tm, client):
        mock_tm.decode_token.return_value = {"sub": "testuser"}
        response = client.post(
            f"{self.prefix}/logout",
            content=b"not json",
            headers={"Authorization": "Bearer sometoken", "Content-Type": "application/json"},
        )
        assert response.status_code == 200

    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.AuditLogger")
    def test_logout_refresh_token_non_dict_body(self, mock_audit, mock_ip, mock_tm, client):
        mock_tm.decode_token.return_value = {"sub": "testuser"}
        response = client.post(
            f"{self.prefix}/logout",
            json=[],
            headers={"Authorization": "Bearer sometoken"},
        )
        assert response.status_code == 200


class TestRefresh:
    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    def test_refresh_rate_limit_exceeded(self, mock_ip, mock_rl, client):
        mock_rl.return_value = False
        response = client.post(f"{self.prefix}/refresh", json={"token": "sometoken"})
        assert response.status_code == 429

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_refresh_invalid_token(self, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = None
        response = client.post(f"{self.prefix}/refresh", json={"token": "badtoken"})
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    def test_refresh_no_username(self, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": ""}
        response = client.post(f"{self.prefix}/refresh", json={"token": "sometoken"})
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.UserService")
    def test_refresh_user_not_found(self, mock_usr_svc, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "unknown"}
        inst = Mock()
        inst.get_user_by_username.return_value = None
        mock_usr_svc.return_value = inst
        response = client.post(f"{self.prefix}/refresh", json={"token": "sometoken"})
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.UserService")
    def test_refresh_user_inactive(self, mock_usr_svc, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser"}
        user = _make_user(is_active=False)
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst
        response = client.post(f"{self.prefix}/refresh", json={"token": "sometoken"})
        assert response.status_code == 403

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.UserService")
    def test_refresh_success(self, mock_usr_svc, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.return_value = {"sub": "testuser"}
        user = _make_user()
        inst = Mock()
        inst.get_user_by_username.return_value = user
        mock_usr_svc.return_value = inst
        mock_tm.create_token_pair.return_value = {"access_token": "new_at", "refresh_token": "new_rt"}
        response = client.post(f"{self.prefix}/refresh", json={"token": "valid_rt"})
        assert response.status_code == 200
        assert response.json()["data"]["access_token"] == "new_at"
        assert response.json()["refresh_token"] == "new_rt"
        mock_tm.revoke_token.assert_called_once_with("valid_rt")

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.UserService")
    def test_refresh_value_error(self, mock_usr_svc, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.side_effect = ValueError("bad")
        response = client.post(f"{self.prefix}/refresh", json={"token": "badtoken"})
        assert response.status_code == 401

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.token_manager")
    @patch("app.api.v1.auth.auth.UserService")
    def test_refresh_generic_exception(self, mock_usr_svc, mock_tm, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_tm.decode_token.side_effect = RuntimeError("unexpected")
        response = client.post(f"{self.prefix}/refresh", json={"token": "badtoken"})
        assert response.status_code == 401


class TestCsrfToken:
    prefix = "/api/v1/auth"

    @patch("app.middleware.csrf_middleware.generate_csrf_token")
    @patch("app.middleware.csrf_middleware.sign_csrf_token")
    def test_get_csrf_token(self, mock_sign, mock_gen, client):
        mock_gen.return_value = "raw_csrf_token"
        mock_sign.return_value = "signed_csrf_token"

        response = client.get(f"{self.prefix}/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["csrf_token"] == "raw_csrf_token"
        assert data["data"]["csrf_signed_token"] == "signed_csrf_token"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    def test_csrf_token_rate_limit(self, mock_rl, client):
        mock_rl.return_value = False
        response = client.get(f"{self.prefix}/csrf-token")
        assert response.status_code == 429


class TestRegister:
    prefix = "/api/v1/auth"

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    def test_register_rate_limit_exceeded(self, mock_ip, mock_rl, client):
        mock_rl.return_value = False
        response = client.post(
            f"{self.prefix}/register",
            json={"username": "newuser", "password": "Str0ng!Pass", "pass_code": "code123"},
        )
        assert response.status_code == 429

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    def test_register_invalid_username(self, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (False, "用户名不合法")
        response = client.post(
            f"{self.prefix}/register",
            json={"username": "ab", "password": "Str0ng!Pass", "pass_code": "code123"},
        )
        assert response.status_code == 400

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    def test_register_invalid_password(self, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (False, "密码强度不足")
        response = client.post(
            f"{self.prefix}/register",
            json={"username": "newuser", "password": "weak", "pass_code": "code123"},
        )
        assert response.status_code == 400

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    def test_register_invalid_pass_code(self, mock_mc_cls, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (True, "")
        mc_instance = Mock()
        mc_instance.get_machine_code.return_value = "mcode123"
        mc_instance.verify_pass_code.return_value = None
        mock_mc_cls.return_value = mc_instance

        response = client.post(
            f"{self.prefix}/register",
            json={"username": "newuser", "password": "Str0ng!Pass", "pass_code": "badcode"},
        )
        assert response.status_code == 400

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.UserService")
    def test_register_username_exists(self, mock_usr_svc, mock_mc_cls, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (True, "")
        mc_instance = Mock()
        mc_instance.get_machine_code.return_value = "mcode123"
        mc_instance.verify_pass_code.return_value = Mock()
        mock_mc_cls.return_value = mc_instance
        usr_instance = Mock()
        usr_instance.get_user_by_username.return_value = _make_user()
        mock_usr_svc.return_value = usr_instance

        response = client.post(
            f"{self.prefix}/register",
            json={"username": "existing", "password": "Str0ng!Pass", "pass_code": "code123"},
        )
        assert response.status_code == 409

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.UserService")
    def test_register_email_exists(self, mock_usr_svc, mock_mc_cls, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (True, "")
        mc_instance = Mock()
        mc_instance.get_machine_code.return_value = "mcode123"
        mc_instance.verify_pass_code.return_value = Mock()
        mock_mc_cls.return_value = mc_instance
        usr_instance = Mock()
        usr_instance.get_user_by_username.return_value = None
        usr_instance.get_user_by_email.return_value = _make_user()
        mock_usr_svc.return_value = usr_instance

        response = client.post(
            f"{self.prefix}/register",
            json={"username": "newuser", "password": "Str0ng!Pass", "pass_code": "code123", "email": "used@example.com"},
        )
        assert response.status_code == 400

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.UserService")
    def test_register_exception_during_creation(self, mock_usr_svc, mock_mc_cls, mock_policy, mock_ip, mock_rl, client):
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
        usr_instance.create_user.side_effect = RuntimeError("failed")
        mock_usr_svc.return_value = usr_instance

        response = client.post(
            f"{self.prefix}/register",
            json={"username": "newuser", "password": "Str0ng!Pass", "pass_code": "code123"},
        )
        assert response.status_code == 400

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.UserService")
    def test_register_success(self, mock_usr_svc, mock_mc_cls, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (True, "")
        mc_instance = Mock()
        mc_instance.get_machine_code.return_value = "mcode123"
        mc_instance.verify_pass_code.return_value = Mock()
        mock_mc_cls.return_value = mc_instance
        created_user = _make_user(username="newuser", role="viewer")
        usr_instance = Mock()
        usr_instance.get_user_by_username.return_value = None
        usr_instance.get_user_by_email.return_value = None
        usr_instance.create_user.return_value = created_user
        mock_usr_svc.return_value = usr_instance

        with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
            mock_tm.create_token_pair.return_value = {"access_token": "new_at", "refresh_token": "new_rt"}
            response = client.post(
                f"{self.prefix}/register",
                json={"username": "newuser", "password": "Str0ng!Passw0rd", "pass_code": "validcode"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["access_token"] == "new_at"
            # 注册即登录契约：必须返回可轮换 refresh_token（记住登录持久化依赖）
            assert body["refresh_token"] == "new_rt"
            mock_tm.create_token_pair.assert_called_once()

    @patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock)
    @patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.auth.auth.PasswordPolicy")
    @patch("app.services.machine_code_service.MachineCodeService")
    @patch("app.api.v1.auth.auth.UserService")
    def test_register_success_with_all_fields(self, mock_usr_svc, mock_mc_cls, mock_policy, mock_ip, mock_rl, client):
        mock_rl.return_value = True
        mock_policy.validate_username.return_value = (True, "")
        mock_policy.validate.return_value = (True, "")
        mc_instance = Mock()
        mc_instance.get_machine_code.return_value = "mcode123"
        mc_instance.verify_pass_code.return_value = Mock()
        mock_mc_cls.return_value = mc_instance
        created_user = _make_user(username="newuser2", email="new@example.com", full_name="New User")
        usr_instance = Mock()
        usr_instance.get_user_by_username.return_value = None
        usr_instance.get_user_by_email.return_value = None
        usr_instance.create_user.return_value = created_user
        mock_usr_svc.return_value = usr_instance

        with patch("app.api.v1.auth.auth.token_manager") as mock_tm:
            mock_tm.create_token_pair.return_value = {"access_token": "new_at", "refresh_token": "new_rt"}
            response = client.post(
                f"{self.prefix}/register",
                json={
                    "username": "newuser2",
                    "password": "Str0ng!Passw0rd",
                    "pass_code": "validcode",
                    "full_name": "New User",
                    "email": "new@example.com",
                },
            )
            assert response.status_code == 200
            assert response.json()["refresh_token"] == "new_rt"


class TestVerifyToken:
    @patch("app.api.v1.auth.auth.token_manager")
    def test_verify_token_success(self, mock_tm):
        from app.api.v1.auth.auth import verify_token
        mock_tm.decode_token.return_value = {"sub": "testuser"}
        result = asyncio.run(verify_token("valid_token"))
        assert result == {"username": "testuser", "token_type": "access_token"}

    @patch("app.api.v1.auth.auth.token_manager")
    def test_verify_token_none_payload(self, mock_tm):
        from app.api.v1.auth.auth import verify_token
        mock_tm.decode_token.return_value = None
        result = asyncio.run(verify_token("some_token"))
        assert result is None

    @patch("app.api.v1.auth.auth.token_manager")
    def test_verify_token_no_username(self, mock_tm):
        from app.api.v1.auth.auth import verify_token
        mock_tm.decode_token.return_value = {"sub": None}
        result = asyncio.run(verify_token("some_token"))
        assert result is None

    @patch("app.api.v1.auth.auth.token_manager")
    def test_verify_token_exception(self, mock_tm):
        from app.api.v1.auth.auth import verify_token
        mock_tm.decode_token.side_effect = RuntimeError("decode failed")
        result = asyncio.run(verify_token("bad_token"))
        assert result is None


class TestCreateAccessToken:
    @patch("app.api.v1.auth.auth.token_manager")
    def test_create_access_token(self, mock_tm):
        from app.api.v1.auth.auth import create_access_token
        mock_tm.create_access_token.return_value = "new_at"
        result = create_access_token({"sub": "testuser"}, expires_delta=None)
        assert result == "new_at"
        mock_tm.create_access_token.assert_called_once_with("testuser", expires_delta=None)
