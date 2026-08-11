from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request
import jwt as pyjwt

from app.core.security import (
    ADMIN_ROLES,
    ALGORITHM,
    ALL_ROLES,
    ROLE_ADMIN,
    SECRET_KEY,
    AuditLogService,
    CSRFProtection,
    PasswordPolicy,
    RateLimitExceeded,
    SECURITY_HEADERS,
    SENSITIVE_FIELDS,
    SENSITIVE_PATTERNS,
    SQL_INJECTION_PATTERNS,
    _ensure_secret_key,
    _rate_limit_store,
    _truncate_password,
    check_rate_limit,
    check_sql_injection,
    create_access_token,
    create_access_token_with_machine_code,
    create_refresh_token,
    decode_token,
    decode_token_with_machine_code,
    generate_password,
    get_client_ip,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    hash_password,
    is_local_request,
    require_admin,
    require_roles,
    sanitize_input,
    sanitize_log_data,
    verify_password,
)


class TestEnsureSecretKey:
    # 使用 pytest 的 monkeypatch fixture 而非 patch.dict(os.environ, clear=False)：
    # patch.dict 在 teardown 时会清空整个 environ 再逐个还原，当环境中存在超长
    # 变量（如 WorkBuddy 注入的 ACC_PRODUCT_CONFIG_V3 > 32767 字符）时会触发
    # Windows 的 ValueError。monkeypatch 只动指定变量，teardown 逐个还原，更健壮。
    def test_returns_from_env_jwt_secret_key(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "jwt-key")
        assert _ensure_secret_key() == "jwt-key"

    def test_returns_from_env_secret_key(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "sec-key")
        assert _ensure_secret_key() == "sec-key"

    def test_raises_critical_when_missing(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "")
        monkeypatch.setenv("SECRET_KEY", "")
        with patch("app.core.security.logger.critical") as mock_crit:
            key = _ensure_secret_key()
            assert len(key) == 64
            mock_crit.assert_called_once()


class TestTruncatePassword:
    def test_short_password(self):
        assert _truncate_password("short") == "short"

    def test_long_password(self):
        long = "a" * 100
        result = _truncate_password(long)
        assert len(result.encode("utf-8")) <= 72
        assert result == "a" * 72

    def test_exactly_72_bytes(self):
        pwd = "a" * 72
        assert _truncate_password(pwd) == pwd


class TestPasswordHash:
    def test_get_password_hash(self):
        hashed = get_password_hash("test_password")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_alias(self):
        result = hash_password("test")
        assert result.startswith("$2b$") or result.startswith("$2a$")

    def test_verify_password_success(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_password_failure(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_value_error(self):
        with patch("app.core.security.pwd_context.verify", side_effect=ValueError):
            assert verify_password("any", "invalid_hash") is False

    def test_verify_password_general_exception(self):
        with patch(
            "app.core.security.pwd_context.verify", side_effect=RuntimeError("critical")
        ):
            with patch("app.core.security.logger.critical") as mock_crit:
                with pytest.raises(RuntimeError):
                    verify_password("any", "any")
                mock_crit.assert_called_once()


class TestGeneratePassword:
    def test_minimum_length(self):
        pwd = generate_password(4)
        assert len(pwd) >= 8

    def test_default_length(self):
        pwd = generate_password()
        assert len(pwd) == 12

    def test_exclude_ambiguous(self):
        pwd = generate_password(16, exclude_ambiguous=True)
        assert len(pwd) == 16
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(not c.isalnum() for c in pwd)

    def test_includes_all_char_types(self):
        for _ in range(20):
            pwd = generate_password(12)
            assert any(c.isupper() for c in pwd), f"No upper in {pwd}"
            assert any(c.islower() for c in pwd), f"No lower in {pwd}"
            assert any(c.isdigit() for c in pwd), f"No digit in {pwd}"
            assert any(not c.isalnum() for c in pwd), f"No special in {pwd}"


class TestSanitizeLogData:
    def test_redacts_sensitive_fields(self):
        data = {"username": "alice", "password": "secret123", "email": "a@b.com"}
        result = sanitize_log_data(data)
        assert result["username"] == "alice"
        assert result["password"] == "[REDACTED]"
        assert result["email"] == "[REDACTED]"

    def test_case_insensitive_matching(self):
        data = {"PASSWORD": "secret", "Token": "abc"}
        result = sanitize_log_data(data)
        assert result["PASSWORD"] == "[REDACTED]"
        assert result["Token"] == "[REDACTED]"

    def test_non_sensitive_data_unchanged(self):
        data = {"name": "test", "count": 42}
        result = sanitize_log_data(data)
        assert result == data


class TestCSRFProtection:
    def test_generate_token(self):
        token = CSRFProtection.generate_token()
        assert len(token) == 64

    def test_validate_token_match(self):
        token = CSRFProtection.generate_token()
        assert CSRFProtection.validate_token(token, token) is True

    def test_validate_token_mismatch(self):
        assert CSRFProtection.validate_token("abc", "def") is False

    def test_validate_token_empty(self):
        assert CSRFProtection.validate_token("", "token") is False
        assert CSRFProtection.validate_token("token", "") is False
        assert CSRFProtection.validate_token("", "") is False


class TestJWTToken:
    def _make_token_data(self):
        return {"sub": "admin", "role": "admin"}

    def test_create_access_token(self):
        data = self._make_token_data()
        token = create_access_token(data)
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_with_expires_delta(self):
        data = self._make_token_data()
        token = create_access_token(data, expires_delta=timedelta(minutes=5))
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "access"

    def test_create_access_token_with_machine_code(self):
        data = self._make_token_data()
        token = create_access_token_with_machine_code(data, "machine-123")
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["machine_code"] == "machine-123"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        data = self._make_token_data()
        token = create_refresh_token(data)
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_decode_token_success(self):
        data = self._make_token_data()
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload["sub"] == "admin"

    def test_decode_token_invalid(self):
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_token_with_machine_code_match(self):
        data = self._make_token_data()
        token = create_access_token_with_machine_code(data, "mc-001")
        payload = decode_token_with_machine_code(token, "mc-001")
        assert payload["sub"] == "admin"

    def test_decode_token_with_machine_code_none(self):
        data = self._make_token_data()
        token = create_access_token(data)
        payload = decode_token_with_machine_code(token, None)
        assert payload["sub"] == "admin"

    def test_decode_token_with_machine_code_mismatch(self):
        data = self._make_token_data()
        token = create_access_token_with_machine_code(data, "mc-001")
        with pytest.raises(ValueError, match="设备绑定校验失败"):
            decode_token_with_machine_code(token, "mc-002")

    def test_decode_token_without_machine_code_in_token(self):
        data = self._make_token_data()
        token = create_access_token(data)
        payload = decode_token_with_machine_code(token, "some-mc")
        assert payload["sub"] == "admin"


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=None)
        assert exc.value.status_code == 401
        assert "未提供认证凭证" in exc.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        creds = MagicMock()
        creds.credentials = "bad.token.here"
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=creds)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_sub_in_payload_raises_401(self):
        token = create_access_token({"not_sub": "value"})
        creds = MagicMock()
        creds.credentials = token
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=creds)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self):
        token = create_access_token({"sub": "nonexistent"})
        creds = MagicMock()
        creds.credentials = token

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch("app.core.database.SessionLocal", return_value=mock_db):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(credentials=creds)
            assert exc.value.status_code == 401
            assert "用户不存在" in exc.value.detail

    @pytest.mark.asyncio
    async def test_token_version_mismatch_raises_401(self):
        mock_user = MagicMock()
        mock_user.username = "admin"
        mock_user.token_version_safe = 2

        token = create_access_token({"sub": "admin", "token_version": "1"})
        creds = MagicMock()
        creds.credentials = token

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch("app.core.database.SessionLocal", return_value=mock_db):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(credentials=creds)
            assert exc.value.status_code == 401
            assert "令牌已失效" in exc.value.detail

    @pytest.mark.asyncio
    async def test_token_version_none_continues(self):
        mock_user = MagicMock()
        mock_user.username = "admin"
        mock_user.token_version_safe = 2

        token = create_access_token({"sub": "admin"})
        creds = MagicMock()
        creds.credentials = token

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch("app.core.database.SessionLocal", return_value=mock_db):
            user = await get_current_user(credentials=creds)
            assert user is mock_user
            mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_auth(self):
        mock_user = MagicMock()
        mock_user.username = "admin"
        mock_user.token_version_safe = 1

        token = create_access_token({"sub": "admin", "token_version": "1"})
        creds = MagicMock()
        creds.credentials = token

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_user
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch("app.core.database.SessionLocal", return_value=mock_db):
            user = await get_current_user(credentials=creds)
            assert user is mock_user
            mock_db.close.assert_called_once()


class TestGetCurrentActiveUser:
    @pytest.mark.asyncio
    async def test_none_user_raises(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_active_user(current_user=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_user_raises(self):
        user = MagicMock()
        user.is_active = False
        with pytest.raises(HTTPException) as exc:
            await get_current_active_user(current_user=user)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_active_user_returns(self):
        user = MagicMock()
        user.is_active = True
        result = await get_current_active_user(current_user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_user_without_is_active_attr(self):
        user = MagicMock(spec=[])
        result = await get_current_active_user(current_user=user)
        assert result is user


class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_none_user_raises(self):
        checker = require_admin()
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_admin_raises(self):
        user = MagicMock()
        user.role = "viewer"
        user.is_superuser = False
        checker = require_admin()
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=user)
        assert exc.value.status_code == 403
        assert "需要管理员权限" in exc.value.detail

    @pytest.mark.asyncio
    async def test_superuser_bypasses(self):
        user = MagicMock()
        user.role = "viewer"
        user.is_superuser = True
        checker = require_admin()
        result = await checker(current_user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_admin_role_allowed(self):
        user = MagicMock()
        user.role = "admin"
        user.is_superuser = False
        checker = require_admin()
        result = await checker(current_user=user)
        assert result is user


class TestRequireRoles:
    @pytest.mark.asyncio
    async def test_none_user_raises(self):
        checker = require_roles("admin", "manager")
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_role_allowed(self):
        user = MagicMock()
        user.role = "manager"
        user.is_superuser = False
        checker = require_roles("admin", "manager")
        result = await checker(current_user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_role_not_allowed_raises(self):
        user = MagicMock()
        user.role = "viewer"
        user.is_superuser = False
        checker = require_roles("admin", "manager")
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=user)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_superuser_allowed_any_role(self):
        user = MagicMock()
        user.role = "viewer"
        user.is_superuser = True
        checker = require_roles("admin")
        result = await checker(current_user=user)
        assert result is user


class TestRateLimitExceeded:
    def test_default_message(self):
        exc = RateLimitExceeded()
        assert str(exc) == "请求过于频繁，请稍后再试"

    def test_custom_message(self):
        exc = RateLimitExceeded("custom")
        assert str(exc) == "custom"


class TestSQLInjection:
    def test_detect_union_select(self):
        assert check_sql_injection("' UNION SELECT * FROM users") is True

    def test_detect_drop_table(self):
        assert check_sql_injection("DROP TABLE users") is True

    def test_detect_sql_comment(self):
        assert check_sql_injection("admin' -- ") is True

    def test_detect_semicolon_end(self):
        assert check_sql_injection("';") is True

    def test_detect_block_comment(self):
        assert check_sql_injection("/* secret */") is True

    def test_clean_passes(self):
        assert check_sql_injection("hello world") is False

    def test_empty_string(self):
        assert check_sql_injection("") is False


class TestSanitizeInput:
    def test_empty_value_returns_empty(self):
        assert sanitize_input("") == ""

    def test_none_returns_empty(self):
        assert sanitize_input(None) == ""

    def test_non_string_returns_itself(self):
        result = sanitize_input(123)
        assert result == 123

    def test_removes_dangerous_chars(self):
        result = sanitize_input("test' OR '1'='1'; -- /* */")
        assert ";" not in result
        assert "--" not in result
        assert "/*" not in result
        assert "*/" not in result
        assert "''" in result

    def test_normal_input_unchanged(self):
        result = sanitize_input("hello world")
        assert result == "hello world"


class TestCheckRateLimit:
    @pytest.mark.asyncio
    async def test_key_is_none_returns_true(self):
        result = await check_rate_limit(key=None)
        assert result is True

    @pytest.mark.asyncio
    async def test_under_limit(self):
        _rate_limit_store.clear()
        result = await check_rate_limit(key="test_key", limit=5, window=60)
        assert result is True

    @pytest.mark.asyncio
    async def test_over_limit(self):
        _rate_limit_store.clear()
        for _ in range(5):
            await check_rate_limit(key="limited_key", limit=5, window=60)
        result = await check_rate_limit(key="limited_key", limit=5, window=60)
        assert result is False

    @pytest.mark.asyncio
    async def test_window_expiry(self):
        _rate_limit_store.clear()
        with patch("time.monotonic", side_effect=[100, 100, 100, 100, 100, 300]):
            for _ in range(5):
                await check_rate_limit(key="expiry_key", limit=5, window=60)
            result = await check_rate_limit(key="expiry_key", limit=5, window=60)
            assert result is True


class TestGetClientIP:
    def test_x_forwarded_for(self):
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert get_client_ip(request) == "1.2.3.4"

    def test_x_real_ip(self):
        request = MagicMock(spec=Request)
        request.headers = {"X-Real-IP": "10.0.0.1"}
        assert get_client_ip(request) == "10.0.0.1"

    def test_client_host(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client.host = "192.168.1.1"
        assert get_client_ip(request) == "192.168.1.1"

    def test_no_client(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None
        assert get_client_ip(request) == "unknown"


class TestIsLocalRequest:
    def test_localhost_ipv4(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client.host = "127.0.0.1"
        assert is_local_request(request) is True

    def test_localhost_ipv6(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client.host = "::1"
        assert is_local_request(request) is True

    def test_non_local(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client.host = "10.0.0.1"
        assert is_local_request(request) is False


class TestPasswordPolicy:
    def test_valid_password(self):
        valid, msg = PasswordPolicy.validate("ValidPass1!abc")
        assert valid is True
        assert msg == ""

    def test_too_short(self):
        valid, msg = PasswordPolicy.validate("Ab1!")
        assert valid is False
        assert "长度" in msg

    def test_missing_upper(self):
        valid, msg = PasswordPolicy.validate("lowercase1!abc")
        assert valid is False
        assert "大写" in msg

    def test_missing_lower(self):
        valid, msg = PasswordPolicy.validate("UPPERCASE1!ABC")
        assert valid is False
        assert "小写" in msg

    def test_missing_digit(self):
        valid, msg = PasswordPolicy.validate("Uppercase!abc")
        assert valid is False
        assert "数字" in msg

    def test_missing_special(self):
        valid, msg = PasswordPolicy.validate("Uppercase1abc")
        assert valid is False
        assert "特殊字符" in msg

    def test_empty_password(self):
        valid, msg = PasswordPolicy.validate("")
        assert valid is False
        assert "长度" in msg

    def test_validate_username_valid(self):
        valid, msg = PasswordPolicy.validate_username("test_user")
        assert valid is True
        assert msg == ""

    def test_validate_username_chinese(self):
        valid, msg = PasswordPolicy.validate_username("管理员")
        assert valid is True

    def test_validate_username_empty(self):
        valid, msg = PasswordPolicy.validate_username("")
        assert valid is False
        assert "不能为空" in msg

    def test_validate_username_none(self):
        valid, msg = PasswordPolicy.validate_username(None)
        assert valid is False
        assert "不能为空" in msg

    def test_validate_username_too_short(self):
        valid, msg = PasswordPolicy.validate_username("ab")
        assert valid is False
        assert "至少" in msg

    def test_validate_username_too_long(self):
        valid, msg = PasswordPolicy.validate_username("a" * 21)
        assert valid is False
        assert "不能超过" in msg

    def test_validate_username_invalid_chars(self):
        valid, msg = PasswordPolicy.validate_username("user@name!")
        assert valid is False
        assert "只能包含" in msg


class TestSecurityConstants:
    def test_all_roles_defined(self):
        assert ROLE_ADMIN in ALL_ROLES
        assert len(ALL_ROLES) == 4

    def test_admin_roles(self):
        assert "super_admin" in ADMIN_ROLES
        assert "admin" in ADMIN_ROLES

    def test_sensitive_fields(self):
        assert "password" in SENSITIVE_FIELDS
        assert "token" in SENSITIVE_FIELDS

    def test_sensitive_patterns(self):
        assert len(SENSITIVE_PATTERNS) > 0

    def test_sql_injection_patterns(self):
        assert len(SQL_INJECTION_PATTERNS) > 0

    def test_security_headers(self):
        assert "X-Content-Type-Options" in SECURITY_HEADERS
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"


class TestAuditLogService:
    def test_init_stores_db(self):
        mock_db = MagicMock()
        svc = AuditLogService(db=mock_db)
        assert svc.db is mock_db

    def test_init_no_db(self):
        svc = AuditLogService()
        assert svc.db is None

    @pytest.mark.asyncio
    async def test_no_db_returns_early(self):
        result = await AuditLogService.log(db=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_log_success(self):
        mock_db = MagicMock()
        mock_audit_log_cls = MagicMock()
        mock_audit_log_instance = MagicMock()
        mock_audit_log_cls.return_value = mock_audit_log_instance

        # 直接 patch 真模块属性（patch.object 自动恢复）。
        # 注意：不可在此用 patch.dict(sys.modules, {"app.models.audit": MagicMock()})——
        # `import app.models.audit as audit_mod` 会经父包属性链拿到真模块，
        # audit_mod.AuditLog = mock 将永久改写真模块属性，污染后续所有
        # 函数内 `from app.models.audit import AuditLog`（如 statistics overview）。
        import app.models.audit as audit_mod

        with patch.object(audit_mod, "AuditLog", mock_audit_log_cls):
            await AuditLogService.log(
                db=mock_db,
                user_id=1,
                action="login",
                resource_id="1",
                details="User logged in",
                ip_address="127.0.0.1",
            )
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_exception_rollback(self):
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB error")
        with patch("app.core.security.logger.warning") as mock_warn:
            await AuditLogService.log(
                db=mock_db,
                user_id=1,
                action="test",
            )
            mock_warn.assert_called_once()
            # safe_commit 内部回滚 + 外层 except 回滚，至少回滚一次即可
            assert mock_db.rollback.call_count >= 1

    @pytest.mark.asyncio
    async def test_log_exception_rollback_fails(self):
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB error")
        mock_db.rollback.side_effect = Exception("Rollback error")
        with patch("app.core.security.logger.warning") as mock_warn:
            await AuditLogService.log(
                db=mock_db,
                user_id=1,
                action="test",
            )
            # safe_commit 内部 rollback 失败 → 抛出 "Rollback error"
            # 外层 except 捕获后记录 warning，再次 rollback 又失败再记录一条
            assert mock_warn.call_count >= 2


class TestSecurityHeadersMiddleware:
    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        from app.core.security import SecurityHeadersMiddleware

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(mock_app)
        send_calls = []

        async def capture_send(msg):
            send_calls.append(msg)

        await middleware({"type": "other"}, None, capture_send)
        assert len(send_calls) > 0

    @pytest.mark.asyncio
    async def test_adds_security_headers(self):
        from app.core.security import SecurityHeadersMiddleware

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(mock_app)
        headers = {}

        async def capture_send(msg):
            if msg["type"] == "http.response.start":
                for k, v in msg.get("headers", []):
                    headers[k] = v

        await middleware(
            {"type": "http", "path": "/test", "method": "GET"},
            None,
            capture_send,
        )
        assert b"X-Content-Type-Options" in headers
        assert headers[b"X-Content-Type-Options"] == b"nosniff"
        assert b"X-Frame-Options" in headers

    @pytest.mark.asyncio
    async def test_cache_control_static(self):
        from app.core.security import SecurityHeadersMiddleware

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(mock_app)
        headers = {}

        async def capture_send(msg):
            if msg["type"] == "http.response.start":
                for k, v in msg.get("headers", []):
                    headers[k] = v

        await middleware(
            {"type": "http", "path": "/static/app.js", "method": "GET"},
            None,
            capture_send,
        )
        assert b"Cache-Control" in headers
        assert headers[b"Cache-Control"] == b"public, max-age=86400"

    @pytest.mark.asyncio
    async def test_cache_control_api_data(self):
        from app.core.security import SecurityHeadersMiddleware

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(mock_app)
        headers = {}

        async def capture_send(msg):
            if msg["type"] == "http.response.start":
                for k, v in msg.get("headers", []):
                    headers[k] = v

        await middleware(
            {"type": "http", "path": "/api/v1/data/projects", "method": "GET"},
            None,
            capture_send,
        )
        assert b"Cache-Control" in headers
        assert headers[b"Cache-Control"] == b"private, max-age=300"

    @pytest.mark.asyncio
    async def test_no_cache_control_for_post(self):
        from app.core.security import SecurityHeadersMiddleware

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(mock_app)
        headers = {}

        async def capture_send(msg):
            if msg["type"] == "http.response.start":
                for k, v in msg.get("headers", []):
                    headers[k] = v

        await middleware(
            {"type": "http", "path": "/api/v1/data/projects", "method": "POST"},
            None,
            capture_send,
        )
        assert b"Cache-Control" not in headers

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_headers(self):
        from app.core.security import SecurityHeadersMiddleware

        async def mock_app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "headers": [(b"X-Content-Type-Options", b"sniff")],
            })
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = SecurityHeadersMiddleware(mock_app)
        headers = {}

        async def capture_send(msg):
            if msg["type"] == "http.response.start":
                for k, v in msg.get("headers", []):
                    headers[k] = v

        await middleware(
            {"type": "http", "path": "/test", "method": "GET"},
            None,
            capture_send,
        )
        assert headers[b"X-Content-Type-Options"] == b"sniff"


class TestBcryptCompatInjection:
    def _reimport_security(self, mock_bcrypt, import_side_effect=None):
        import sys
        orig = sys.modules.pop('app.core.security', None)
        try:
            with patch.dict('sys.modules', {'bcrypt': mock_bcrypt}, clear=False):
                if import_side_effect:
                    orig_import = __import__
                    def side_effect_import(name, *args, **kwargs):
                        if name in import_side_effect:
                            raise import_side_effect[name]
                        return orig_import(name, *args, **kwargs)
                    with patch('builtins.__import__', side_effect=side_effect_import):
                        import app.core.security as sec
                        return sec
                else:
                    import app.core.security as sec
                    return sec
        finally:
            if orig:
                sys.modules['app.core.security'] = orig

    def test_inject_about_when_missing(self):
        mock_bcrypt = MagicMock()
        mock_bcrypt.__version__ = '4.0.1'
        mock_bcrypt.__about__ = None
        del mock_bcrypt.__about__
        sec = self._reimport_security(mock_bcrypt)
        assert hasattr(mock_bcrypt, '__about__')
        assert mock_bcrypt.__about__.__version__ == '4.0.1'

    def test_bcrypt_version_4_1_patch(self):
        import passlib.handlers.bcrypt as _pb
        orig_finalize = _pb._BcryptCommon._finalize_backend_mixin
        mock_bcrypt = MagicMock()
        mock_bcrypt.__version__ = '4.1.0'
        try:
            sec = self._reimport_security(mock_bcrypt)
            patched = _pb._BcryptCommon._finalize_backend_mixin
            assert patched is not orig_finalize
            result = patched.__func__(None, "test", True)
            assert result is True
        finally:
            _pb._BcryptCommon._finalize_backend_mixin = orig_finalize

    def test_bcrypt_exception_during_patch(self):
        mock_bcrypt = MagicMock()
        mock_bcrypt.__version__ = '4.1.0'
        with patch('app.core.security.logger.error') as mock_error:
            self._reimport_security(
                mock_bcrypt,
                import_side_effect={'passlib.handlers.bcrypt': Exception("mocked")}
            )
            mock_error.assert_called_once()


class TestSettingsSecretKeyFallback:
    def test_settings_import_failure(self):
        import sys
        orig = sys.modules.pop('app.core.security', None)
        try:
            orig_import = __import__
            def mock_import(name, *args, **kwargs):
                if name == 'app.core.config':
                    raise ImportError("mocked settings fail")
                return orig_import(name, *args, **kwargs)
            with patch('builtins.__import__', side_effect=mock_import):
                import app.core.security as sec
                assert sec.SECRET_KEY is not None
                assert sec.ALGORITHM == "HS256"
        finally:
            if orig:
                sys.modules['app.core.security'] = orig
