"""W24 viewer 只读中间件单元测试（逐分支驱动纯 ASGI 入口）。

覆盖：非 HTTP scope / 安全方法 / 自服务白名单放行 / viewer 写业务路径 403 /
令牌缺失或非法 fail-open / 旧令牌无 role 声明 fail-open / 非 viewer 角色放行 /
403 统一错误格式 / 审计事件写入与审计失败旁路 / 令牌解析异常旁路。
"""

import json
from unittest.mock import patch

import pytest

from app.core.token_manager import create_token_pair
from app.middleware.viewer_readonly import (
    DENIED_MESSAGE,
    ViewerReadOnlyMiddleware,
)


def _token(role=None, uid=None, username="u1"):
    claims = {}
    if role is not None:
        claims["role"] = role
    if uid is not None:
        claims["uid"] = uid
    return create_token_pair(username, extra_claims=claims)["access_token"]


def _scope(method="POST", path="/api/v1/supported-villages", token=None, headers=None):
    raw = [(b"host", b"testserver")]
    if token is not None:
        raw.append((b"authorization", ("Bearer " + token).encode()))
    for name, value in (headers or {}).items():
        raw.append((name.lower().encode(), value.encode()))
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw,
        "client": ("127.0.0.1", 50000),
        "query_string": b"",
        "scheme": "http",
        "server": ("127.0.0.1", 8000),
    }


class _Downstream:
    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True


async def _run(scope):
    downstream = _Downstream()
    captured = {"status": None, "body": []}

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
        elif message["type"] == "http.response.body":
            captured["body"].append(message.get("body", b""))

    middleware = ViewerReadOnlyMiddleware(downstream)
    await middleware(scope, receive, send)
    return downstream.called, captured


class TestViewerReadOnlyMiddleware:
    async def test_non_http_scope_passes(self):
        scope = {"type": "websocket", "path": "/ws", "headers": []}
        called, _ = await _run(scope)
        assert called is True

    async def test_safe_method_passes(self):
        called, _ = await _run(_scope(method="GET", token=_token(role="viewer")))
        assert called is True

    async def test_viewer_write_denied_with_unified_envelope(self):
        called, captured = await _run(_scope(token=_token(role="viewer", uid=7)))
        assert called is False
        assert captured["status"] == 403
        body = json.loads(b"".join(captured["body"]))
        assert body["code"] == 403
        assert body["message"] == DENIED_MESSAGE
        assert body["detail"] == DENIED_MESSAGE
        assert body["success"] is False

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/api/v1/auth/login"),
            ("POST", "/api/v1/auth/logout"),
            ("POST", "/api/v1/auth/refresh"),
            ("POST", "/api/v1/auth/two-factor/verify-login"),
            ("POST", "/api/v1/auth/2fa/verify"),
            ("POST", "/api/v1/auth/verify-passcode"),
            ("PUT", "/api/v1/users/9/password"),
            ("PUT", "/api/v1/notifications/preferences"),
            ("PUT", "/api/v1/notifications/preferences/site-message"),
            ("POST", "/api/v1/feedback"),
        ],
    )
    async def test_self_service_whitelist_passes(self, method, path):
        called, captured = await _run(_scope(method=method, path=path, token=_token(role="viewer")))
        assert called is True
        assert captured["status"] is None

    @pytest.mark.parametrize("path", [
        "/api/v1/supported-villages",
        "/api/v1/schools",
        "/api/v1/policies",
        "/api/v1/funds",
        "/api/v1/households",
        "/api/v1/todos/1/complete",
        "/api/v1/users/me/profile",
    ])
    async def test_viewer_write_business_paths_denied(self, path):
        called, captured = await _run(_scope(path=path, token=_token(role="viewer")))
        assert called is False
        assert captured["status"] == 403

    async def test_missing_token_fail_open(self):
        called, _ = await _run(_scope(token=None))
        assert called is True

    async def test_invalid_token_fail_open(self):
        called, _ = await _run(_scope(token="not-a-jwt"))
        assert called is True

    async def test_non_bearer_scheme_fail_open(self):
        called, _ = await _run(_scope(headers={"Authorization": "Basic abc"}))
        assert called is True

    async def test_empty_bearer_token_fail_open(self):
        called, _ = await _run(_scope(headers={"Authorization": "Bearer   "}))
        assert called is True

    @pytest.mark.parametrize("role", ["user", "admin", "super_admin", "manager"])
    async def test_non_viewer_roles_not_blocked(self, role):
        called, _ = await _run(_scope(token=_token(role=role)))
        assert called is True

    async def test_legacy_token_without_role_claim_fail_open(self):
        called, _ = await _run(_scope(token=_token()))
        assert called is True

    async def test_audit_event_written_with_identity_and_path(self):
        with patch("app.utils.audit_logger.AuditLogger.log") as audit:
            called, captured = await _run(
                _scope(
                    path="/api/v1/policies",
                    token=_token(role="viewer", uid=42, username="viewer42"),
                    headers={"User-Agent": "pytest-agent"},
                )
            )
        assert called is False and captured["status"] == 403
        audit.assert_called_once()
        kwargs = audit.call_args.kwargs
        assert kwargs["action"] == "viewer_write_denied"
        assert kwargs["user_id"] == 42
        assert kwargs["username"] == "viewer42"
        assert kwargs["details"] == {"method": "POST", "path": "/api/v1/policies"}
        assert kwargs["user_agent"] == "pytest-agent"
        assert kwargs["ip_address"] == "127.0.0.1"

    async def test_audit_without_user_agent_header(self):
        with patch("app.utils.audit_logger.AuditLogger.log") as audit:
            await _run(_scope(token=_token(role="viewer")))
        assert audit.call_args.kwargs["user_agent"] is None

    async def test_audit_failure_does_not_change_403(self):
        with patch(
            "app.utils.audit_logger.AuditLogger.log",
            side_effect=RuntimeError("audit down"),
        ):
            called, captured = await _run(_scope(token=_token(role="viewer")))
        assert called is False and captured["status"] == 403

    async def test_token_decode_exception_fail_open(self):
        with patch("app.core.security.decode_token", side_effect=RuntimeError("boom")):
            called, _ = await _run(_scope(token=_token(role="viewer")))
        assert called is True
