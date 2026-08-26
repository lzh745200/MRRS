"""
中间件模块综合测试

测试 app/middleware/ 下所有未覆盖模块
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.middleware.utils import should_skip_middleware
from app.middleware.audit_context import (
    AuditContext,
    get_current_user,
    get_request_id,
    set_current_user,
    set_request_id,
)


class TestMiddlewareUtils:
    def test_should_skip_match(self):
        assert should_skip_middleware("/health", {"/health", "/auth"}) is True

    def test_should_skip_partial_match(self):
        assert should_skip_middleware("/health/check", {"/health"}) is True

    def test_should_not_skip(self):
        assert should_skip_middleware("/api/data", {"/health", "/auth"}) is False

    def test_should_skip_empty_collection(self):
        assert should_skip_middleware("/api/data", set()) is False


class TestAuditContext:
    def test_audit_context_creation(self):
        ctx = AuditContext(user_id=1, request_id="abc")
        assert ctx.user_id == 1
        assert ctx.request_id == "abc"

    def test_audit_context_defaults(self):
        ctx = AuditContext()
        assert ctx.user_id is None
        assert ctx.request_id is None

    def test_get_current_defaults(self):
        ctx = AuditContext.get_current()
        assert ctx.user_id is None

    def test_set_and_get_current(self):
        ctx = AuditContext(user_id=42, request_id="req-1")
        ctx.set_current()
        assert get_current_user() == 42
        assert get_request_id() == "req-1"

    def test_set_current_user_func(self):
        set_current_user(99)
        assert get_current_user() == 99

    def test_set_request_id_func(self):
        set_request_id("custom-id")
        assert get_request_id() == "custom-id"

    def test_set_user_none(self):
        set_current_user(None)
        assert get_current_user() is None


class TestAPIVersionMiddleware:
    @patch("app.middleware.api_version.anyio")
    @pytest.mark.asyncio
    async def test_dispatch_sets_version(self, mock_anyio):
        from app.middleware.api_version import APIVersionMiddleware

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "v2"
        mock_request.state = MagicMock()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = APIVersionMiddleware(mock_app)
        result = await mw.dispatch(mock_request, mock_call_next)

        # dispatch 成功返回 response
        assert result is mock_response

    def test_init_defaults(self):
        from app.middleware.api_version import APIVersionMiddleware

        mock_app = MagicMock()
        mw = APIVersionMiddleware(mock_app)
        assert mw.default_version == "v1"
        assert mw.header_name == "X-API-Version"


class TestCacheHeadersMiddleware:
    @pytest.mark.asyncio
    async def test_cache_headers_matched(self):
        from app.middleware.cache_headers import CacheHeadersMiddleware

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/organizations/tree"
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = CacheHeadersMiddleware(mock_app)
        await mw.dispatch(mock_request, mock_call_next)
        assert mock_response.headers.get("Cache-Control") == "public, max-age=300"

    @pytest.mark.asyncio
    async def test_cache_headers_unmatched(self):
        from app.middleware.cache_headers import CacheHeadersMiddleware

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/users/me"
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = CacheHeadersMiddleware(mock_app)
        await mw.dispatch(mock_request, mock_call_next)
        assert "Cache-Control" not in mock_response.headers


class TestCamelToSnakeMiddleware:
    @pytest.mark.asyncio
    async def test_camel_to_snake_conversion(self):
        from app.middleware.camel_to_snake import CamelToSnakeMiddleware

        import json

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "application/json"
        mock_request.body = AsyncMock(return_value=json.dumps({"userName": "test", "age": 25}).encode())
        mock_request._body = b""
        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = CamelToSnakeMiddleware(mock_app)
        await mw.dispatch(mock_request, mock_call_next)
        decoded = json.loads(mock_request._body)
        assert "user_name" in decoded
        assert decoded["user_name"] == "test"

    @pytest.mark.asyncio
    async def test_no_content_type_no_conversion(self):
        from app.middleware.camel_to_snake import CamelToSnakeMiddleware

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "text/plain"
        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = CamelToSnakeMiddleware(mock_app)
        await mw.dispatch(mock_request, mock_call_next)

    @pytest.mark.asyncio
    async def test_empty_body(self):
        from app.middleware.camel_to_snake import CamelToSnakeMiddleware

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "application/json"
        mock_request.body = AsyncMock(return_value=b"")
        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = CamelToSnakeMiddleware(mock_app)
        await mw.dispatch(mock_request, mock_call_next)


class TestCSRFMiddleware:
    def test_generate_csrf_token_format(self):
        """W5-T009: token 格式为 {timestamp}.{hex_random}"""
        from app.middleware.csrf_middleware import generate_csrf_token

        token = generate_csrf_token()
        assert isinstance(token, str)
        assert "." in token, "token 应包含时间戳.随机数格式"
        ts_str, hex_part = token.split(".", 1)
        assert ts_str.isdigit(), "前缀应为数字时间戳"
        assert len(hex_part) == 48, "随机部分应为48字符hex"

    def test_generate_csrf_token_unique(self):
        from app.middleware.csrf_middleware import generate_csrf_token

        tokens = {generate_csrf_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_sign_csrf_token(self):
        from app.middleware.csrf_middleware import sign_csrf_token

        token = "abc123"
        signed = sign_csrf_token(token, "test-secret")
        assert isinstance(signed, str)
        assert len(signed) == 64

    @pytest.mark.asyncio
    async def test_csrf_disabled(self):
        from app.middleware.csrf_middleware import CSRFMiddleware

        mock_app = AsyncMock()
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        mw = CSRFMiddleware(mock_app)
        # CSRF_ENABLED defaults to False in test, so it should pass through
        result = await mw.dispatch(mock_request, mock_call_next)
        assert result is mock_response

    def test_is_path_exempt(self):
        from app.middleware.csrf_middleware import _is_path_exempt

        assert _is_path_exempt("/api/v1/auth/login") is True
        assert _is_path_exempt("/health") is True
        assert _is_path_exempt("/api/v1/funds") is False


class TestRequestIDMiddleware:
    def test_get_request_id_default(self):
        from app.middleware.request_id import get_request_id

        # Default is empty string
        assert get_request_id() == ""

    def test_request_id_log_filter(self):
        from app.middleware.request_id import RequestIDLogFilter

        filt = RequestIDLogFilter()
        record = MagicMock()
        assert filt.filter(record) is True
        assert hasattr(record, "request_id")

    def test_valid_request_id_regex(self):
        from app.middleware.request_id import _VALID_REQUEST_ID_RE

        assert _VALID_REQUEST_ID_RE.match("abc-123_XYZ") is not None
        assert _VALID_REQUEST_ID_RE.match("a" * 64) is not None
        assert _VALID_REQUEST_ID_RE.match("a" * 65) is None
        assert _VALID_REQUEST_ID_RE.match("") is None
        assert _VALID_REQUEST_ID_RE.match("hello world") is None


class TestMetricsStore:
    def test_metrics_store_basic(self):
        from app.middleware.metrics_middleware import _MetricsStore

        store = _MetricsStore()
        assert store.request_count == 0
        assert store.error_count == 0
        assert store.active_requests == 0

    def test_record_success(self):
        from app.middleware.metrics_middleware import _MetricsStore

        store = _MetricsStore()
        store.record("GET", "/api/test", 200, 0.1)
        assert store.request_count == 1
        assert store.error_count == 0
        assert store.total_duration == 0.1

    def test_record_error(self):
        from app.middleware.metrics_middleware import _MetricsStore

        store = _MetricsStore()
        store.record("POST", "/api/test", 500, 0.5)
        assert store.request_count == 1
        assert store.error_count == 1

    def test_active_tracking(self):
        from app.middleware.metrics_middleware import _MetricsStore

        store = _MetricsStore()
        store.inc_active()
        assert store.active_requests == 1
        store.inc_active()
        assert store.active_requests == 2
        store.dec_active()
        assert store.active_requests == 1

    def test_get_summary(self):
        from app.middleware.metrics_middleware import _MetricsStore

        store = _MetricsStore()
        store.record("GET", "/api/test", 200, 1.0)
        store.record("POST", "/api/data", 201, 2.0)
        summary = store.get_summary()
        assert summary["request_count"] == 2
        assert summary["error_count"] == 0
        assert summary["active_requests"] == 0
        assert summary["avg_duration"] == 1.5
        assert "GET_200" in summary["by_method_status"]
        assert "POST_201" in summary["by_method_status"]


class TestRequestLogger:
    def test_get_client_ip_from_forwarded(self):
        from app.middleware.request_logger import _get_client_ip

        scope = {
            "headers": [
                (b"x-forwarded-for", b"10.0.0.1, 10.0.0.2"),
            ]
        }
        assert _get_client_ip(scope) == "10.0.0.1"

    def test_get_client_ip_from_real_ip(self):
        from app.middleware.request_logger import _get_client_ip

        scope = {
            "headers": [
                (b"x-real-ip", b"192.168.1.1"),
            ]
        }
        assert _get_client_ip(scope) == "192.168.1.1"

    def test_get_client_ip_from_client(self):
        from app.middleware.request_logger import _get_client_ip

        scope = {
            "client": ("127.0.0.1", 8000),
            "headers": [],
        }
        assert _get_client_ip(scope) == "127.0.0.1"

    def test_get_client_ip_unknown(self):
        from app.middleware.request_logger import _get_client_ip

        scope = {"headers": []}
        assert _get_client_ip(scope) == "unknown"

    def test_get_user_agent(self):
        from app.middleware.request_logger import _get_user_agent

        scope = {"headers": [(b"user-agent", b"TestAgent/1.0")]}
        assert _get_user_agent(scope) == "TestAgent/1.0"

    def test_get_user_agent_empty(self):
        from app.middleware.request_logger import _get_user_agent

        scope = {"headers": []}
        assert _get_user_agent(scope) == ""


class TestCacheMiddleware:
    def test_init_defaults(self):
        from app.middleware.cache_middleware import CacheMiddleware

        mock_app = MagicMock()
        mw = CacheMiddleware(mock_app)
        assert mw.ttl == 300
        assert "/health" in mw.exclude_paths
        assert "/auth" in mw.exclude_paths
