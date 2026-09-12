# -*- coding: utf-8 -*-
"""E1（架构评估 2026-09-12）：CSRFMiddleware 纯 ASGI 实现的分支覆盖。

原 BaseHTTPMiddleware.dispatch 已改写为 ``__call__(scope, receive, send)``，
本文件逐分支驱动 ASGI 入口：
- 非 HTTP scope / 未启用 / 安全方法 / 豁免路径 / 内部备份密钥 → 放行
- 缺 token / 过期 token / HMAC 匹配 / 明文回退 / 双失败 → 403 或放行
- TRUSTED_PROXIES 透传与不可信降级
"""

import os
import time
from unittest.mock import patch

import pytest

from app.middleware.csrf_middleware import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRFMiddleware,
    _CSRF_EXEMPT_PATH_PREFIXES,
    generate_csrf_token,
    sign_csrf_token,
)


def _make_scope(method="POST", path="/api/v1/funds", cookies=None, headers=None,
                client=("127.0.0.1", 50000)):
    h = [
        (b"host", b"127.0.0.1:8000"),
    ]
    if cookies:
        h.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    for k, v in (headers or {}).items():
        h.append((k.lower().encode(), v.encode()))
    return {"type": "http", "method": method, "path": path, "headers": h, "client": client,
            "query_string": b"", "scheme": "http", "server": ("127.0.0.1", 8000)}


class _Downstream:
    """记录被调用与否的下游 app 替身。"""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True


class _Capture:
    """捕获 JSONResponse 输出的 send 替身。"""

    def __init__(self):
        self.status = None
        self.body = b""

    async def __call__(self, scope, receive, send):
        pass

    async def __call_send(self, message):  # pragma: no cover — 由闭包替代
        pass


async def _run(mw, scope):
    downstream = _Downstream()
    captured = {"status": None, "body": []}

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
        elif message["type"] == "http.response.body":
            captured["body"].append(message.get("body", b""))

    async def app(scope2, receive2, send2):
        downstream.called = True

    mw.app = app
    await mw(scope, receive, send)
    return downstream.called, captured


def _enabled_mw():
    mw = CSRFMiddleware(None)
    # settings 是单例对象，patch 属性对所有模块引用生效
    p = patch("app.core.config.settings.CSRF_ENABLED", True)
    p.start()
    return mw, p


class TestCSRFASGIBranches:
    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self):
        mw, p = _enabled_mw()
        try:
            called, captured = await _run(mw, {"type": "lifespan"})
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_safe_method_passthrough(self):
        mw, p = _enabled_mw()
        try:
            called, _ = await _run(mw, _make_scope(method="GET"))
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_exempt_path_passthrough(self):
        mw, p = _enabled_mw()
        try:
            path = _CSRF_EXEMPT_PATH_PREFIXES[1]
            called, _ = await _run(mw, _make_scope(path=path))
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_internal_backup_key_passthrough(self):
        mw, p = _enabled_mw()
        try:
            with patch.dict(os.environ, {"INTERNAL_BACKUP_KEY": "k123"}):
                called, _ = await _run(
                    mw, _make_scope(headers={"X-Internal-Backup": "k123"})
                )
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_missing_token_returns_403(self):
        mw, p = _enabled_mw()
        try:
            called, captured = await _run(mw, _make_scope())
            assert called is False
            assert captured["status"] == 403
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_expired_token_returns_403(self):
        mw, p = _enabled_mw()
        try:
            stale = f"{int(time.time()) - 90000}.abc"
            signed = sign_csrf_token(stale, "sk")
            called, captured = await _run(
                mw,
                _make_scope(
                    cookies={CSRF_COOKIE_NAME: signed},
                    headers={CSRF_HEADER_NAME: stale},
                ),
            )
            assert called is False
            assert captured["status"] == 403
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_hmac_match_passthrough(self):
        mw, p = _enabled_mw()
        try:
            token = generate_csrf_token()
            signed = sign_csrf_token(token, "sk")
            with patch("app.middleware.csrf_middleware.sign_csrf_token",
                       return_value=signed):
                called, _ = await _run(
                    mw,
                    _make_scope(
                        cookies={CSRF_COOKIE_NAME: signed},
                        headers={CSRF_HEADER_NAME: token},
                    ),
                )
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_plaintext_fallback_passthrough(self):
        mw, p = _enabled_mw()
        try:
            # 旧版明文 token：无 {ts}.{rand} 时间戳前缀（点前非数字 → 不做过期判定）
            token = "legacytoken"
            called, _ = await _run(
                mw,
                _make_scope(
                    cookies={CSRF_COOKIE_NAME: token},
                    headers={CSRF_HEADER_NAME: token},
                ),
            )
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_quoted_cookie_value_is_unquoted(self):
        """RFC 6265 允许带引号的 cookie 值，等价于原 `Request.cookies` 行为。

        E1 改为纯 ASGI 后自行解析 Cookie：若不去引号，`csrftoken="<token>"`
        这一形态会从"通过"变为 403 —— 与原实现不再等价（2026-09-12 逐分支
        走查发现，已在 `_parse_cookies` 中去引号）。
        """
        mw, p = _enabled_mw()
        try:
            token = "legacytoken"
            called, _ = await _run(
                mw,
                _make_scope(
                    cookies={CSRF_COOKIE_NAME: f'"{token}"'},
                    headers={CSRF_HEADER_NAME: token},
                ),
            )
            assert called is True
        finally:
            p.stop()

    @pytest.mark.asyncio
    async def test_mismatch_returns_403(self):
        mw, p = _enabled_mw()
        try:
            called, captured = await _run(
                mw,
                _make_scope(
                    cookies={CSRF_COOKIE_NAME: "aaa.bbb"},
                    headers={CSRF_HEADER_NAME: "ccc.ddd"},
                ),
            )
            assert called is False
            assert captured["status"] == 403
        finally:
            p.stop()


class TestCSRFClientIPScope:
    def test_direct_ip_without_proxies(self):
        from app.middleware.csrf_middleware import get_client_ip

        with patch("app.middleware.csrf_middleware._TRUSTED_PROXIES", []):
            assert get_client_ip(_make_scope()) == "127.0.0.1"

    def test_no_client_entry(self):
        from app.middleware.csrf_middleware import get_client_ip

        scope = _make_scope()
        scope["client"] = None
        with patch("app.middleware.csrf_middleware._TRUSTED_PROXIES", []):
            assert get_client_ip(scope) == "unknown"

    def test_trusted_proxy_forwards_xff(self):
        from app.middleware.csrf_middleware import get_client_ip

        scope = _make_scope(
            client=("10.0.0.1", 1000), headers={"X-Forwarded-For": "9.9.9.9, 8.8.8.8"}
        )
        with patch("app.middleware.csrf_middleware._TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(scope) == "9.9.9.9"

    def test_untrusted_proxy_ignores_xff(self):
        from app.middleware.csrf_middleware import get_client_ip

        scope = _make_scope(
            client=("10.9.9.9", 1000), headers={"X-Forwarded-For": "9.9.9.9"}
        )
        with patch("app.middleware.csrf_middleware._TRUSTED_PROXIES", ["10.0.0.1"]):
            assert get_client_ip(scope) == "10.9.9.9"

    def test_cidr_trusted_proxy(self):
        from app.middleware.csrf_middleware import get_client_ip

        scope = _make_scope(client=("172.16.3.4", 1000), headers={"X-Forwarded-For": "7.7.7.7"})
        with patch("app.middleware.csrf_middleware._TRUSTED_PROXIES", ["172.16.0.0/12"]):
            assert get_client_ip(scope) == "7.7.7.7"
