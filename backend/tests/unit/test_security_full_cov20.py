"""app.core.security 覆盖率补测（task#20）。

针对 81% → 100% 缺口，补齐：_ensure_secret_key / _truncate_password /
verify_password 异常路径 / generate_password 边界 / sanitize_log_data /
create_refresh_token / decode_token 失败 / get_current_user 早退分支 /
get_current_active_user / require_admin checker / sanitize_input /
get_client_ip 代理头 / is_local_request / validate_username / AuditLogService.log。

模块导入期的 settings 加载兜底（security.py 行 85-88）另由源码 pragma 声明豁免。
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security as sec


# ─────────────────────────── _ensure_secret_key (67-77) ───────────────────────────


class TestEnsureSecretKey:
    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "env-jwt-key")
        assert sec._ensure_secret_key() == "env-jwt-key"  # 行 70

    def test_fallback_secret_key_env(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("SECRET_KEY", "env-secret-key")
        assert sec._ensure_secret_key() == "env-secret-key"

    def test_generates_when_all_sources_empty(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        key = sec._ensure_secret_key()  # 行 71-77 生成 + critical 日志
        assert isinstance(key, str) and len(key) == 64  # token_hex(32)


# ─────────────────────────── _truncate_password (126) ───────────────────────────


class TestTruncatePassword:
    def test_short_password_unchanged(self):
        assert sec._truncate_password("short") == "short"

    def test_long_password_truncated_to_72_bytes(self):
        result = sec._truncate_password("a" * 100)  # 行 125-126
        assert len(result.encode("utf-8")) == 72


# ─────────────────────────── verify_password 异常 (146-148) ───────────────────────────


class TestVerifyPasswordException:
    def test_value_error_returns_false(self):
        with patch.object(sec.pwd_context, "verify", side_effect=ValueError("bad")):
            assert sec.verify_password("x", "y") is False  # 行 144-145

    def test_generic_exception_reraises(self):
        with patch.object(sec.pwd_context, "verify", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                sec.verify_password("x", "y")  # 行 146-148 critical + raise


# ─────────────────────────── generate_password (154,156) ───────────────────────────


class TestGeneratePassword:
    def test_min_length_clamped(self):
        pwd = sec.generate_password(length=4)  # 行 153-154 → 8
        assert len(pwd) >= 8

    def test_exclude_ambiguous_alphabet(self):
        pwd = sec.generate_password(length=12, exclude_ambiguous=True)  # 行 155-156
        assert len(pwd) == 12
        # 排除的歧义字符不应出现
        for ch in "Il1O0":
            assert ch not in pwd

    def test_contains_all_classes(self):
        pwd = sec.generate_password(length=14)
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(not c.isalnum() for c in pwd)


# ─────────────────────────── sanitize_log_data (195-202) ───────────────────────────


class TestSanitizeLogData:
    def test_redacts_sensitive_keys(self):
        data = {"username": "bob", "password": "p", "api_key": "k", "normal": "v"}
        result = sec.sanitize_log_data(data)
        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert result["normal"] == "v"
        assert result["username"] == "bob"

    def test_does_not_mutate_original(self):
        data = {"token": "abc"}
        sec.sanitize_log_data(data)
        assert data["token"] == "abc"  # deepcopy


# ─────────────────────────── JWT (222-225, 233-235) ───────────────────────────


class TestJwtTokens:
    def test_create_refresh_token(self):
        token = sec.create_refresh_token({"sub": "alice"})  # 行 222-225
        payload = sec.decode_token(token)
        assert payload["type"] == "refresh" and payload["sub"] == "alice"

    def test_decode_invalid_token_returns_none(self):
        assert sec.decode_token("not.a.valid.token") is None  # 行 233-235


# ─────────────────────────── get_current_user 早退 (260, 289) ───────────────────────────


class TestGetCurrentUserEarlyExit:
    async def test_invalid_token_raises_401(self):
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token.here")
        with pytest.raises(HTTPException) as exc:
            await sec.get_current_user(credentials=cred)  # 行 259-264
        assert exc.value.status_code == 401

    async def test_no_credentials_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await sec.get_current_user(credentials=None)  # 行 251-256
        assert exc.value.status_code == 401

    async def test_missing_sub_raises_401(self):
        cred = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        with patch("app.core.security.decode_token", return_value={"type": "access"}):
            with pytest.raises(HTTPException) as exc:
                await sec.get_current_user(credentials=cred)  # 行 287-292
            assert exc.value.status_code == 401
            assert exc.value.detail == "无效的令牌内容"


# ─────────────────────────── get_current_active_user (344, 346) ───────────────────────────


class TestGetCurrentActiveUser:
    async def test_none_user_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await sec.get_current_active_user(current_user=None)  # 行 343-344
        assert exc.value.status_code == 401

    async def test_inactive_user_raises_403(self):
        user = MagicMock(is_active=False)
        with pytest.raises(HTTPException) as exc:
            await sec.get_current_active_user(current_user=user)  # 行 345-346
        assert exc.value.status_code == 403

    async def test_active_user_returned(self):
        user = MagicMock(is_active=True)
        assert await sec.get_current_active_user(current_user=user) is user


# ─────────────────────────── require_admin checker (361) ───────────────────────────


class TestRequireAdminChecker:
    async def test_none_user_raises_401(self):
        checker = sec.require_admin()
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=None)  # 行 360-361
        assert exc.value.status_code == 401

    async def test_non_admin_raises_403(self):
        checker = sec.require_admin()
        user = MagicMock(role="user", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=user)
        assert exc.value.status_code == 403

    async def test_admin_passes(self):
        checker = sec.require_admin()
        user = MagicMock(role="admin", is_superuser=False)
        assert await checker(current_user=user) is user


# ─────────────────────────── sanitize_input (403-411) ───────────────────────────


class TestSanitizeInput:
    def test_empty_string(self):
        assert sec.sanitize_input("") == ""  # falsy 快捷路径

    def test_none_value(self):
        assert sec.sanitize_input(None) == ""

    def test_non_string(self):
        # 修复后：真值非 str 输入先转 str 再净化，恒返回 str
        # （原缺陷：`value or ""` 原样透传 int，违反返回类型契约）
        result = sec.sanitize_input(123)
        assert result == "123"
        assert isinstance(result, str)

    def test_falsy_non_string(self):
        # falsy 非 str 输入（如 0）→ 与旧行为一致返回 ""
        assert sec.sanitize_input(0) == ""

    def test_non_string_sanitized(self):
        # bool 输入转 str 后走同一净化逻辑（无危险字符，结果不变）
        assert sec.sanitize_input(True) == "True"

    def test_removes_dangerous_chars(self):
        result = sec.sanitize_input("a'b;c--d/*e*/")  # 行 406-411
        assert "''" in result and ";" not in result
        assert "--" not in result and "/*" not in result and "*/" not in result


# ─────────────────────────── get_client_ip / is_local_request (504-516) ───────────────────────────


class TestGetClientIpProxy:
    def _req(self, host="1.2.3.4", xff=None, real_ip=None):
        r = MagicMock()
        r.client = MagicMock()
        r.client.host = host
        headers = {}
        if xff:
            headers["X-Forwarded-For"] = xff
        if real_ip:
            headers["X-Real-IP"] = real_ip
        r.headers = headers
        return r

    def test_trust_proxy_xff(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True, raising=False)
        req = self._req(xff="9.9.9.9, 8.8.8.8")
        assert sec.get_client_ip(req) == "9.9.9.9"  # 行 503-506

    def test_trust_proxy_real_ip(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True, raising=False)
        req = self._req(real_ip="7.7.7.7")
        assert sec.get_client_ip(req) == "7.7.7.7"  # 行 507-509

    def test_no_trust_proxy_uses_direct(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False, raising=False)
        req = self._req(host="5.5.5.5", xff="9.9.9.9")
        assert sec.get_client_ip(req) == "5.5.5.5"  # 行 510

    def test_is_local_request_true(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False, raising=False)
        req = self._req(host="127.0.0.1")
        assert sec.is_local_request(req) is True  # 行 515-516

    def test_is_local_request_false(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False, raising=False)
        req = self._req(host="8.8.8.8")
        assert sec.is_local_request(req) is False


# ─────────────────────────── validate_username (585, 589) ───────────────────────────


class TestValidateUsername:
    def test_too_long(self):
        ok, msg = sec.PasswordPolicy.validate_username("a" * 21)  # 行 584-585
        assert ok is False and "不能超过20" in msg

    def test_invalid_chars(self):
        ok, msg = sec.PasswordPolicy.validate_username("user@name")  # 行 588-589
        assert ok is False and "只能包含" in msg

    def test_valid(self):
        ok, _ = sec.PasswordPolicy.validate_username("valid_user-1")
        assert ok is True


# ─────────────────────────── AuditLogService.log (663, 681-686) ───────────────────────────


class TestAuditLogService:
    async def test_none_db_returns_early(self):
        # 行 662-663：db 为 None 直接返回，不抛异常
        assert await sec.AuditLogService.log(db=None, action="x") is None

    async def test_write_failure_rolls_back(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("db down")  # 触发 681-684
        await sec.AuditLogService.log(db=db, user_id=1, action="login")
        db.rollback.assert_called_once()

    async def test_rollback_failure_swallowed(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("db down")
        db.rollback.side_effect = RuntimeError("rollback failed")  # 触发 685-686
        # 不应抛出——内层 except 吞掉回滚异常
        await sec.AuditLogService.log(db=db, user_id=1, action="login")
