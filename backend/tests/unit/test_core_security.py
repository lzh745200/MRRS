from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request
import jwt as pyjwt















class TestJWTToken:
    def _make_token_data(self):
        return {"sub": "admin", "role": "admin"}


























class TestCheckRateLimit:
    """request stub: 当前实现仅校验非 None, 用 SimpleNamespace 模拟 FastAPI Request。"""

    @staticmethod
    def _req():
        from types import SimpleNamespace

        return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))







class TestGetClientIP:
    """默认不信任 X-Forwarded-For/X-Real-IP（可伪造, 限流键可被轮换绕过）;
    仅 TRUST_PROXY_HEADERS=True（可信反代部署）时读取代理头。"""

    @staticmethod
    def _mkrequest(headers):
        request = MagicMock(spec=Request)
        request.headers = headers
        request.client.host = "9.9.9.9"
        return request
















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


