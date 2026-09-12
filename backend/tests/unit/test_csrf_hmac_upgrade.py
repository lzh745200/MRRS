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
from unittest.mock import MagicMock, patch

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

def _make_scope(
    method="POST",
    path="/api/v1/users",
    cookie="",
    header="",
    internal_backup="",
    client=("127.0.0.1", 50000),
):
    """构造 ASGI scope（E1：纯 ASGI 实现的测试替身）"""
    h = [(b"host", b"127.0.0.1:8000")]
    if cookie:
        h.append((b"cookie", f"csrftoken={cookie}".encode()))
    if header:
        h.append((b"x-csrf-token", header.encode()))
    if internal_backup:
        h.append((b"x-internal-backup", internal_backup.encode()))
    return {
        "type": "http", "method": method, "path": path, "headers": h,
        "client": client, "query_string": b"", "scheme": "http",
        "server": ("127.0.0.1", 8000),
    }


async def _call_mw(mw, scope):
    """驱动 ASGI 中间件，返回 (downstream_called, status_code)。"""
    called = [False]
    captured = {"status": None}

    async def downstream(scope, receive, send):
        called[0] = True

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]

    mw.app = downstream
    await mw(scope, receive, send)
    return called[0], captured["status"]


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
        mw = self._setup_settings()
        try:
            called, status = await _call_mw(
                mw, _make_scope(cookie=signed, header=raw_token)
            )
        finally:
            self._teardown_settings()
        assert called is True

    async def test_hmac_verification_rejects_mismatch(self):
        """cookie 和 header 不匹配 → 403"""
        mw = self._setup_settings()
        try:
            called, status = await _call_mw(
                mw, _make_scope(cookie="wrong-sig", header="wrong-raw")
            )
        finally:
            self._teardown_settings()
        assert called is False
        assert status == 403

    async def test_plaintext_fallback_passes_with_warning(self):
        """旧版明文比对（cookie == header 非签名）→ 通过但 warning"""
        raw_token = generate_csrf_token()
        mw = self._setup_settings()
        try:
            called, status = await _call_mw(
                mw, _make_scope(cookie=raw_token, header=raw_token)
            )
        finally:
            self._teardown_settings()
        assert called is True

    async def test_expired_token_rejects(self):
        """过期 token → 403"""
        old_ts = int(time.time()) - CSRF_TOKEN_EXPIRY - 100
        old_token = f"{old_ts}.abc123"
        signed = sign_csrf_token(old_token, self._SECRET)
        mw = self._setup_settings()
        try:
            called, status = await _call_mw(
                mw, _make_scope(cookie=signed, header=old_token)
            )
        finally:
            self._teardown_settings()
        assert called is False
        assert status == 403

    async def test_safe_method_bypasses(self):
        """GET 请求直接放行"""
        mw = self._setup_settings()
        try:
            called, _ = await _call_mw(mw, _make_scope(method="GET"))
        finally:
            self._teardown_settings()
        assert called is True

    async def test_csrf_disabled_bypasses(self):
        """CSRF_ENABLED=False 直接放行"""
        mw = self._setup_settings(enabled=False)
        try:
            called, _ = await _call_mw(mw, _make_scope(cookie="x", header="y"))
        finally:
            self._teardown_settings()
        assert called is True


# ── get_client_ip ──────────────────────────────────────────────────────

class TestGetClientIp:
    """E1：get_client_ip 改为 scope 版，语义不变。"""

    def _scope(self, client_host="127.0.0.1", xff=""):
        h = [(b"host", b"x")]
        if xff:
            h.append((b"x-forwarded-for", xff.encode()))
        return {
            "type": "http", "method": "GET", "path": "/",
            "headers": h, "client": (client_host, 1000),
            "query_string": b"", "scheme": "http", "server": ("127.0.0.1", 8000),
        }

    def test_direct_no_proxy(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", []):
            assert get_client_ip(self._scope()) == "127.0.0.1"

    def test_no_client(self):
        scope = self._scope()
        scope["client"] = None
        with patch.object(_mw, "_TRUSTED_PROXIES", []):
            assert get_client_ip(scope) == "unknown"

    def test_trusted_proxy_forwards(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(self._scope(client_host="10.0.0.1", xff="1.2.3.4")) == "1.2.3.4"

    def test_untrusted_proxy_fallback(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(self._scope(client_host="9.9.9.9", xff="5.6.7.8")) == "9.9.9.9"

    def test_no_xff_header(self):
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(self._scope(client_host="10.0.0.1")) == "10.0.0.1"

    def test_cidr_trusted_proxy_forwards(self):
        """CIDR 网段匹配：直连 IP 落在可信网段内 → 透传 XFF 首段。"""
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.0/8"]):
            assert get_client_ip(
                self._scope(client_host="10.1.2.3", xff="1.2.3.4")
            ) == "1.2.3.4"

    def test_cidr_not_matched_falls_back(self):
        """CIDR 网段不匹配：直连 IP 不在可信网段 → 降级为直连 IP。"""
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.0/8"]):
            assert get_client_ip(
                self._scope(client_host="192.168.1.1", xff="5.6.7.8")
            ) == "192.168.1.1"

    def test_cidr_invalid_direct_ip_swallowed(self):
        """直连 IP 非法时 ipaddress 抛 ValueError 被吞掉，降级为直连 IP。"""
        with patch.object(_mw, "_TRUSTED_PROXIES", ["10.0.0.0/8"]):
            assert get_client_ip(
                self._scope(client_host="not-an-ip", xff="5.6.7.8")
            ) == "not-an-ip"
