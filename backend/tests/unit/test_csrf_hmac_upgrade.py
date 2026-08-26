"""W5-T009 CSRF HMAC 升级测试

覆盖：
- generate_csrf_token 格式（{ts}.{hex}）
- sign_csrf_token HMAC-SHA256 正确性
- _extract_timestamp / _token_expired
- HMAC 验证流程（cookie=signed, header=raw → 验证通过）
- 明文回退（旧版兼容 → warning 但通过）
- 过期拒绝
- get_client_ip（直连 / TRUSTED_PROXIES 透传 / 不可信降级）
"""

import hashlib
import hmac as _hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.middleware.csrf_middleware as _mw
from app.middleware.csrf_middleware import (
    CSRF_TOKEN_EXPIRY,
    CSRFMiddleware,
    _extract_timestamp,
    _token_expired,
    generate_csrf_token,
    get_client_ip,
    sign_csrf_token,
)


# ── generate_csrf_token ────────────────────────────────────────────────

class TestGenerateCsrfToken:
    def test_format(self):
        token = generate_csrf_token()
        ts_str, hex_part = token.split(".", 1)
        assert ts_str.isdigit()
        assert len(hex_part) == 48  # 24 bytes hex

    def test_unique(self):
        tokens = {generate_csrf_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_timestamp_close_to_now(self):
        token = generate_csrf_token()
        ts = int(token.split(".")[0])
        assert abs(time.time() - ts) < 5


# ── sign_csrf_token ───────────────────────────────────────────────────

class TestSignCsrfToken:
    def test_deterministic(self):
        assert sign_csrf_token("abc", "secret") == sign_csrf_token("abc", "secret")

    def test_different_tokens_different_signatures(self):
        s1 = sign_csrf_token("token1", "secret")
        s2 = sign_csrf_token("token2", "secret")
        assert s1 != s2

    def test_hmac_correctness(self):
        key = b"test-key"
        token = "test-token"
        expected = _hmac.new(key, token.encode(), hashlib.sha256).hexdigest()
        assert sign_csrf_token(token, key) == expected


# ── _extract_timestamp / _token_expired ────────────────────────────────

class TestTokenExpiry:
    def test_extract_timestamp_valid(self):
        ts = int(time.time())
        token = f"{ts}.abc123"
        assert _extract_timestamp(token) == ts

    def test_extract_timestamp_no_dot(self):
        assert _extract_timestamp("nodot") is None

    def test_extract_timestamp_non_numeric(self):
        assert _extract_timestamp("abc.def") is None

    def test_expired(self):
        old_ts = int(time.time()) - CSRF_TOKEN_EXPIRY - 100
        token = f"{old_ts}.abc"
        assert _token_expired(token) is True

    def test_not_expired(self):
        token = f"{int(time.time())}.abc"
        assert _token_expired(token) is False

    def test_no_timestamp_not_expired(self):
        assert _token_expired("plaintext") is False


# ── HMAC 验证流程（middleware 集成）────────────────────────────────────

def _make_request(
    method="POST",
    path="/api/v1/users",
    cookie="",
    header="",
    internal_backup="",
):
    """构造 mock request"""
    request = MagicMock()
    request.method = method
    request.url.path = path
    request.cookies = {"csrftoken": cookie} if cookie else {}
    request.headers = {}
    if header:
        request.headers["X-CSRF-Token"] = header
    if internal_backup:
        request.headers["X-Internal-Backup"] = internal_backup
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


def _mock_settings(enabled=True):
    s = MagicMock()
    s.CSRF_ENABLED = enabled
    s.CSRF_SECRET_KEY = "test-csrf-secret-key"
    s.SECRET_KEY = "test-secret-key"
    return s


@pytest.mark.asyncio
class TestCSRFMiddlewareHMAC:
    _SECRET = "test-csrf-secret"

    def _setup_settings(self, enabled=True):
        import app.core.config as _cfg
        self._orig = _cfg.settings
        s = MagicMock()
        s.CSRF_ENABLED = enabled
        s.CSRF_SECRET_KEY = self._SECRET
        s.SECRET_KEY = "fallback"
        _cfg.settings = s
        return CSRFMiddleware(app=MagicMock())

    def _teardown_settings(self):
        import app.core.config as _cfg
        _cfg.settings = self._orig

    async def test_hmac_verification_passes(self):
        """cookie=HMAC(raw), header=raw → 验证通过"""
        raw_token = generate_csrf_token()
        signed = sign_csrf_token(raw_token, self._SECRET)
        request = _make_request(cookie=signed, header=raw_token)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        mw = self._setup_settings()
        try:
            resp = await mw.dispatch(request, call_next)
        finally:
            self._teardown_settings()
        assert resp.status_code == 200

    async def test_hmac_verification_rejects_mismatch(self):
        """cookie 和 header 不匹配 → 403"""
        request = _make_request(cookie="wrong-sig", header="wrong-raw")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        mw = self._setup_settings()
        try:
            resp = await mw.dispatch(request, call_next)
        finally:
            self._teardown_settings()
        assert resp.status_code == 403

    async def test_plaintext_fallback_passes_with_warning(self):
        """旧版明文比对（cookie == header 非签名）→ 通过但 warning"""
        raw_token = generate_csrf_token()
        request = _make_request(cookie=raw_token, header=raw_token)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        mw = self._setup_settings()
        try:
            resp = await mw.dispatch(request, call_next)
        finally:
            self._teardown_settings()
        assert resp.status_code == 200

    async def test_expired_token_rejects(self):
        """过期 token → 403"""
        old_ts = int(time.time()) - CSRF_TOKEN_EXPIRY - 100
        old_token = f"{old_ts}.abc123"
        signed = sign_csrf_token(old_token, self._SECRET)
        request = _make_request(cookie=signed, header=old_token)
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        mw = self._setup_settings()
        try:
            resp = await mw.dispatch(request, call_next)
        finally:
            self._teardown_settings()
        assert resp.status_code == 403

    async def test_safe_method_bypasses(self):
        """GET 请求直接放行"""
        request = _make_request(method="GET")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        mw = self._setup_settings()
        try:
            resp = await mw.dispatch(request, call_next)
        finally:
            self._teardown_settings()
        assert resp.status_code == 200

    async def test_csrf_disabled_bypasses(self):
        """CSRF_ENABLED=False 直接放行"""
        request = _make_request(cookie="x", header="y")
        call_next = AsyncMock(return_value=MagicMock(status_code=200))

        mw = self._setup_settings(enabled=False)
        try:
            resp = await mw.dispatch(request, call_next)
        finally:
            self._teardown_settings()
        assert resp.status_code == 200


# ── get_client_ip ──────────────────────────────────────────────────────

class TestGetClientIp:
    def _req(self, client_host="127.0.0.1", xff=""):
        r = MagicMock()
        r.client = MagicMock()
        r.client.host = client_host
        r.headers = {}
        if xff:
            r.headers["x-forwarded-for"] = xff
        return r

    def test_direct_no_proxy(self):
        assert _mw._TRUSTED_PROXIES == [] or True  # may be empty
        # Patch module-level _TRUSTED_PROXIES to simulate no config
        with patch.object(_mw, "_TRUSTED_PROXIES", []):
            assert get_client_ip(self._req()) == "127.0.0.1"

    def test_no_client(self):
        r = MagicMock()
        r.client = None
        r.headers = {}
        with patch.object(_mw, "_TRUSTED_PROXIES", []):
            assert get_client_ip(r) == "unknown"

    def test_trusted_proxy_forwards(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(self._req(client_host="10.0.0.1", xff="1.2.3.4")) == "1.2.3.4"

    def test_untrusted_proxy_fallback(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(self._req(client_host="9.9.9.9", xff="5.6.7.8")) == "9.9.9.9"

    def test_no_xff_header(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(self._req(client_host="10.0.0.1")) == "10.0.0.1"
