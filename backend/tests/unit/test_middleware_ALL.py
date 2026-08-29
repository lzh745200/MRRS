"""Tests for app.middleware — Group 1 middleware: 100% coverage target.

Covers: audit_context, auth, camel_to_snake,
csrf_middleware, rbac, utils, prometheus_middleware
"""

import anyio
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


# ==============================================================================
# app.middleware.utils – should_skip_middleware
# ==============================================================================

class TestShouldSkipMiddleware:

    def test_path_matches_prefix(self):
        from app.middleware.utils import should_skip_middleware
        assert should_skip_middleware("/health/check", {"/health"}) is True

    def test_path_exact_match(self):
        from app.middleware.utils import should_skip_middleware
        assert should_skip_middleware("/health", {"/health"}) is True

    def test_no_match(self):
        from app.middleware.utils import should_skip_middleware
        assert should_skip_middleware("/api/data", {"/health"}) is False

    def test_empty_collection(self):
        from app.middleware.utils import should_skip_middleware
        assert should_skip_middleware("/health", set()) is False


# ==============================================================================
class TestAuditContext:

    def test_create_default(self):
        from app.middleware.audit_context import AuditContext
        ctx = AuditContext()
        assert ctx.user_id is None
        assert ctx.request_id is None

    def test_create_with_values(self):
        from app.middleware.audit_context import AuditContext
        ctx = AuditContext(user_id=1, request_id="req-123")
        assert ctx.user_id == 1
        assert ctx.request_id == "req-123"

    def test_set_and_get_current(self):
        from app.middleware.audit_context import AuditContext
        AuditContext(user_id=42, request_id="req-abc").set_current()
        retrieved = AuditContext.get_current()
        assert retrieved.user_id == 42
        assert retrieved.request_id == "req-abc"

    def test_set_current_overwrites(self):
        from app.middleware.audit_context import AuditContext
        AuditContext(user_id=1, request_id="r1").set_current()
        AuditContext(user_id=2, request_id="r2").set_current()
        retrieved = AuditContext.get_current()
        assert retrieved.user_id == 2
        assert retrieved.request_id == "r2"


class TestAuditContextFunctions:

    @pytest.fixture(autouse=True)
    def _clean_contextvars(self):
        """contextvar 是解释器级状态：前面的测试可能设置过值，先归零。"""
        from app.middleware.audit_context import set_current_user, set_request_id
        set_current_user(None)
        set_request_id(None)
        yield
        set_current_user(None)
        set_request_id(None)

    def test_get_current_user_default(self):
        from app.middleware.audit_context import get_current_user
        assert get_current_user() is None

    def test_set_and_get_current_user(self):
        from app.middleware.audit_context import get_current_user, set_current_user
        set_current_user(99)
        assert get_current_user() == 99

    def test_set_current_user_none(self):
        from app.middleware.audit_context import get_current_user, set_current_user
        set_current_user(None)
        assert get_current_user() is None

    def test_get_request_id_default(self):
        from app.middleware.audit_context import get_request_id
        assert get_request_id() is None

    def test_set_and_get_request_id(self):
        from app.middleware.audit_context import get_request_id, set_request_id
        set_request_id("req-test")
        assert get_request_id() == "req-test"

    def test_set_request_id_none(self):
        from app.middleware.audit_context import get_request_id, set_request_id
        set_request_id(None)
        assert get_request_id() is None


# 注：app.middleware.auth 模块已移除（认证改由 app.core.security 的依赖注入实现），
# 原 TestAuthMiddleware / _make_auth_app 死代码已删除。


# ==============================================================================
class TestConvertKeys:
    """Direct tests of the module-level _convert_keys helper."""

    def test_empty_dict(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys({}, lambda x: x)
        assert result == {}
        assert changed is False

    def test_camel_to_snake_dict(self):
        from app.middleware.camel_to_snake import _convert_keys
        from app.utils.common import StringHelper
        result, changed = _convert_keys({"camelCase": "val"}, StringHelper.to_snake_case)
        assert "camel_case" in result
        assert result["camel_case"] == "val"
        assert changed is True

    def test_already_snake_dict(self):
        from app.middleware.camel_to_snake import _convert_keys
        from app.utils.common import StringHelper
        result, changed = _convert_keys({"already_snake": "val"}, StringHelper.to_snake_case)
        assert result == {"already_snake": "val"}
        assert changed is False

    def test_non_string_key(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys({123: "val"}, str)
        assert result == {123: "val"}
        assert changed is False

    def test_nested_dict_conversion(self):
        from app.middleware.camel_to_snake import _convert_keys
        from app.utils.common import StringHelper
        data = {"outer": {"innerCamel": "val"}}
        result, changed = _convert_keys(data, StringHelper.to_snake_case)
        assert result["outer"]["inner_camel"] == "val"
        assert changed is True

    def test_nested_dict_no_change(self):
        from app.middleware.camel_to_snake import _convert_keys
        from app.utils.common import StringHelper
        data = {"outer": {"inner": "val"}}
        result, changed = _convert_keys(data, StringHelper.to_snake_case)
        assert result["outer"]["inner"] == "val"
        assert changed is False

    def test_list_of_dicts(self):
        from app.middleware.camel_to_snake import _convert_keys
        from app.utils.common import StringHelper
        data = [{"firstName": "Alice"}, {"lastName": "Bob"}]
        result, changed = _convert_keys(data, StringHelper.to_snake_case)
        assert result[0]["first_name"] == "Alice"
        assert result[1]["last_name"] == "Bob"
        assert changed is True

    def test_list_no_change(self):
        from app.middleware.camel_to_snake import _convert_keys
        data = [1, 2, 3]
        result, changed = _convert_keys(data, str)
        assert result == [1, 2, 3]
        assert changed is False

    def test_empty_list(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys([], str)
        assert result == []
        assert changed is False

    def test_primitive_string(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys("hello", str)
        assert result == "hello"
        assert changed is False

    def test_primitive_number(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys(42, str)
        assert result == 42
        assert changed is False

    def test_primitive_none(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys(None, str)
        assert result is None
        assert changed is False

    def test_primitive_bool(self):
        from app.middleware.camel_to_snake import _convert_keys
        result, changed = _convert_keys(True, str)
        assert result is True
        assert changed is False

    def test_mixed_nested(self):
        from app.middleware.camel_to_snake import _convert_keys
        from app.utils.common import StringHelper
        data = {
            "userName": "Alice",
            "items": [{"itemName": "Widget"}, 42],
            "metadata": {"createdAt": "now", "count": 3},
        }
        result, changed = _convert_keys(data, StringHelper.to_snake_case)
        assert "user_name" in result
        assert result["items"][0]["item_name"] == "Widget"
        assert result["items"][1] == 42
        assert result["metadata"]["created_at"] == "now"
        assert changed is True


def _make_camel_app():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route
    from app.middleware.camel_to_snake import CamelToSnakeMiddleware

    async def echo_json(request):
        body = await request.json()
        return JSONResponse(body)

    async def echo_body(request):
        raw = (await request.body()).decode("utf-8", errors="replace")
        return PlainTextResponse(raw)

    app = Starlette(routes=[
        Route("/echo", echo_json, methods=["POST"]),
        Route("/raw", echo_body, methods=["POST"]),
    ])
    app.add_middleware(CamelToSnakeMiddleware)
    return app


class TestCamelToSnakeMiddleware:

    def test_converts_camel_case_body(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/echo", json={"firstName": "Alice", "lastName": "Bob"})
        assert resp.status_code == 200
        data = resp.json()
        assert "first_name" in data
        assert "last_name" in data
        assert data["first_name"] == "Alice"

    def test_keeps_snake_case_body(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/echo", json={"first_name": "Alice"})
        assert resp.status_code == 200
        assert resp.json() == {"first_name": "Alice"}

    def test_non_json_content_type(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/raw", content="plain text", headers={"Content-Type": "text/plain"})
        assert resp.status_code == 200
        assert resp.text == "plain text"

    def test_empty_body_with_json_content_type(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/raw", content=b"", headers={"Content-Type": "application/json"})
        assert resp.status_code == 200

    def test_invalid_json_body(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/raw", content=b"not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 200

    def test_unicode_decode_error_body(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/raw", content=b"\x80\x81\x82", headers={"Content-Type": "application/json"})
        assert resp.status_code == 200

    def test_nested_camel_case_body(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/echo", json={"userProfile": {"displayName": "Alice"}})
        assert resp.status_code == 200
        data = resp.json()
        assert "user_profile" in data
        assert data["user_profile"]["display_name"] == "Alice"

    def test_list_at_root(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/echo", json=[{"itemName": "A"}, {"itemName": "B"}])
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["item_name"] == "A"
        assert data[1]["item_name"] == "B"

    def test_non_dict_root_with_json(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/echo", json="just a string")
        assert resp.status_code == 200
        assert resp.json() == "just a string"

    def test_json_body_with_unicode_characters(self):
        client = TestClient(_make_camel_app())
        resp = client.post("/echo", json={"\u00e9cranName": "\u00e9cran"})
        assert resp.status_code == 200
        data = resp.json()
        assert "\u00e9cran_name" in data
        assert data["\u00e9cran_name"] == "\u00e9cran"


# ==============================================================================
# app.middleware.csrf_middleware – utility functions + CSRFMiddleware
# ==============================================================================

class TestCsrfFunctions:

    def test_generate_csrf_token_length(self):
        from app.middleware.csrf_middleware import generate_csrf_token
        token = generate_csrf_token()
        # W5-T009 新格式：{timestamp}.{random_hex(24 bytes -> 48 hex)}
        ts_str, hex_part = token.split(".", 1)
        assert ts_str.isdigit()
        assert len(hex_part) == 48
        assert isinstance(token, str)

    def test_generate_csrf_token_unique(self):
        from app.middleware.csrf_middleware import generate_csrf_token
        assert generate_csrf_token() != generate_csrf_token()

    def test_sign_csrf_token_with_secret_key(self):
        from app.middleware.csrf_middleware import sign_csrf_token
        signature = sign_csrf_token("test-token", secret_key="my-secret")
        assert isinstance(signature, str)
        assert len(signature) == 64

    def test_sign_csrf_token_with_none_key_falls_back_to_settings(self):
        from app.core.config import settings
        original_csrf = settings.CSRF_SECRET_KEY
        original_secret = settings.SECRET_KEY
        settings.CSRF_SECRET_KEY = ""
        settings.SECRET_KEY = "test-fallback-key-32-chars-long!!!!!!!!"
        try:
            from app.middleware.csrf_middleware import sign_csrf_token
            sig = sign_csrf_token("test-token", secret_key=None)
            assert isinstance(sig, str)
            assert len(sig) == 64
        finally:
            settings.CSRF_SECRET_KEY = original_csrf
            settings.SECRET_KEY = original_secret

    def test_sign_csrf_token_different_secrets(self):
        from app.middleware.csrf_middleware import sign_csrf_token
        sig1 = sign_csrf_token("token", secret_key="key1")
        sig2 = sign_csrf_token("token", secret_key="key2")
        assert sig1 != sig2

    def test_is_path_exempt_exact(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("/health") is True

    def test_is_path_exempt_subpath(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("/health/check") is True

    def test_is_path_exempt_with_trailing_slash(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("/health/") is True

    def test_is_path_exempt_exact_prefix_match(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("/health-check") is True

    def test_is_path_exempt_csrf_token_path(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("/api/v1/auth/csrf-token") is True
        assert _is_path_exempt("/api/v1/auth/csrf-token/") is True

    def test_is_path_exempt_not_exempt(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("/api/v1/data") is False

    def test_is_path_exempt_empty_string(self):
        from app.middleware.csrf_middleware import _is_path_exempt
        assert _is_path_exempt("") is False


def _make_csrf_app():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from app.middleware.csrf_middleware import CSRFMiddleware

    async def ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[
        Route("/api/data", ok, methods=["GET", "POST", "HEAD", "OPTIONS"]),
        Route("/api/v1/auth/csrf-token", ok, methods=["GET", "POST"]),
        Route("/health", ok, methods=["GET", "POST"]),
        Route("/api/v1/auth/login", ok, methods=["POST"]),
    ])
    app.add_middleware(CSRFMiddleware)
    return app


class TestCSRFMiddleware:

    def test_disabled_passes_through(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", False):
            client = TestClient(_make_csrf_app())
            resp = client.post("/api/data")
            assert resp.status_code == 200

    def test_safe_method_get(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.get("/api/data")
            assert resp.status_code == 200

    def test_safe_method_head(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.head("/api/data")
            assert resp.status_code == 200

    def test_safe_method_options(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.options("/api/data")
            assert resp.status_code == 200

    def test_exempt_path_post(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.post("/api/v1/auth/csrf-token")
            assert resp.status_code == 200

    def test_exempt_path_health_post(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.post("/health")
            assert resp.status_code == 200

    def test_missing_cookie_and_header_returns_403(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.post("/api/data")
            assert resp.status_code == 403
            body = resp.json()
            assert "CSRF" in body.get("message", "")

    def test_missing_header_only_returns_403(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            client.cookies.set("csrftoken", "tok")
            resp = client.post("/api/data")
            assert resp.status_code == 403

    def test_missing_cookie_only_returns_403(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            resp = client.post("/api/data", headers={"X-CSRF-Token": "tok"})
            assert resp.status_code == 403

    def test_token_mismatch_returns_403(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            client.cookies.set("csrftoken", "tok1")
            resp = client.post(
                "/api/data",
                headers={"X-CSRF-Token": "tok2"},
            )
            assert resp.status_code == 403
            body = resp.json()
            assert "无效" in body.get("message", "")

    def test_valid_token_passes_through(self):
        from app.core.config import settings
        with patch.object(settings, "CSRF_ENABLED", True):
            client = TestClient(_make_csrf_app())
            client.cookies.set("csrftoken", "same-token")
            resp = client.post(
                "/api/data",
                headers={"X-CSRF-Token": "same-token"},
            )
            assert resp.status_code == 200


# 注：app.middleware.rbac 与 app.middleware.prometheus_middleware 模块已移除
# （RBAC 改由 app.core.rbac 依赖注入实现；指标改由 app.middleware.metrics_middleware 提供），
# 原 TestRBACMiddleware / TestPrometheusMiddleware / _make_rbac_app 死代码已删除。
