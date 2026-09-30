"""OCR 2026-09-17 深审修复回归 —— middleware 层（第 1~6 项）。

覆盖：
1. body_size_limit：不信任 Content-Length（流式真实字节判定）、畸形头 fail-closed
2. cache_headers：仅成功 GET、尊重已有 Cache-Control
3. request_logger：X-Forwarded-For 仅在可信代理场景采信
4. camel_to_snake：重建 JSONResponse 保留 headers/background
5. metrics_middleware：单请求只记录一次（不双计数）
6. slow_request_monitor：慢 SQL 参数脱敏
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.middleware.body_size_limit import BodySizeLimitMiddleware


# ── ASGI 驱动辅助（真实 io 消息流，可控 Content-Length 与分块） ──


async def _drive_asgi(mw, scope, chunks):
    """驱动 ASGI 中间件，返回 (status, sent_messages)；chunks 为请求体分块。"""
    pending = list(chunks)
    sent = []

    async def receive():
        if pending:
            body = pending.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(pending)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await mw(scope, receive, send)
    status = 0
    for message in sent:
        if message["type"] == "http.response.start":
            status = message["status"]
    return status, sent


async def _read_all_body_app(scope, receive, send):
    """下游应用：完整读取请求体后返回 JSON"""
    total = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] == "http.request":
            total += len(message.get("body") or b"")
            if not message.get("more_body", False):
                break
    payload = json.dumps({"received": total}).encode()
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({"type": "http.response.body", "body": payload})


def _http_scope(path, headers):
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }


def _mock_request(path, headers):
    return SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path=path),
        headers=headers,
    )


class TestBodySizeLimitStreaming:
    """第 1 项：按真实流式字节判定，不信任客户端声明。"""

    async def test_declared_content_length_over_limit_rejected(self):
        mw = BodySizeLimitMiddleware(app=MagicMock(), max_body_size=1024)
        call_next = AsyncMock(return_value="response-ok")
        request = _mock_request(
            "/api/v1/dashboard",
            {"content-length": "2048", "content-type": "application/json"},
        )
        result = await mw.dispatch(request, call_next)
        assert result.status_code == 413
        call_next.assert_not_awaited()

    async def test_malformed_content_length_fails_closed_400(self):
        """畸形 Content-Length 不再静默放行（原实现 except: pass）。"""
        mw = BodySizeLimitMiddleware(app=MagicMock(), max_body_size=1024)
        call_next = AsyncMock(return_value="response-ok")
        request = _mock_request(
            "/api/v1/dashboard",
            {"content-length": "not-a-number", "content-type": "application/json"},
        )
        result = await mw.dispatch(request, call_next)
        assert result.status_code == 400
        call_next.assert_not_awaited()

    async def test_negative_content_length_fails_closed_400(self):
        mw = BodySizeLimitMiddleware(app=MagicMock(), max_body_size=1024)
        call_next = AsyncMock(return_value="response-ok")
        request = _mock_request(
            "/api/v1/dashboard",
            {"content-length": "-5", "content-type": "application/json"},
        )
        result = await mw.dispatch(request, call_next)
        assert result.status_code == 400
        call_next.assert_not_awaited()

    async def test_malformed_multipart_content_length_fails_closed_400(self):
        mw = BodySizeLimitMiddleware(app=MagicMock(), max_body_size=1024)
        call_next = AsyncMock(return_value="response-ok")
        request = _mock_request(
            "/api/v1/schools/import/excel",
            {"content-length": "abc", "content-type": "multipart/form-data; boundary=x"},
        )
        result = await mw.dispatch(request, call_next)
        assert result.status_code == 400
        call_next.assert_not_awaited()

    async def test_forged_small_content_length_stream_rejected(self):
        """伪造小 Content-Length（声明 5 字节，实际 4KB）→ 413。"""
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope(
            "/api/v1/dashboard",
            {"content-length": "5", "content-type": "application/json"},
        )
        status, sent = await _drive_asgi(mw, scope, [b"x" * 1024, b"x" * 1024, b"x" * 2048])
        assert status == 413
        assert all(m["type"] != "http.response.body" or b"received" not in m.get("body", b"") for m in sent)

    async def test_forged_multipart_header_on_non_upload_path_rejected(self):
        """非上传路径伪造 multipart 头（默认 512MB），仍按全局上限拒绝。"""
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope(
            "/api/v1/dashboard",
            {"content-type": "multipart/form-data; boundary=x"},
        )
        status, _ = await _drive_asgi(mw, scope, [b"a" * 2048])
        assert status == 413

    async def test_chunked_without_content_length_over_limit_rejected(self):
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope("/api/v1/dashboard", {"content-type": "application/json"})
        status, _ = await _drive_asgi(mw, scope, [b"a" * 600, b"a" * 600])
        assert status == 413

    async def test_stream_within_limit_passes_and_body_arrives(self):
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope("/api/v1/dashboard", {"content-type": "application/json"})
        status, sent = await _drive_asgi(mw, scope, [b"a" * 300, b"b" * 200])
        assert status == 200
        body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        assert json.loads(body.decode())["received"] == 500

    async def test_upload_path_multipart_stream_allows_over_global_limit(self):
        """确实接收上传的路径：multipart 走分级上限（512MB），不受 10MB 全局上限限制。"""
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope(
            "/api/v1/schools/import/excel",
            {"content-type": "multipart/form-data; boundary=x"},
        )
        status, _ = await _drive_asgi(mw, scope, [b"a" * 4096])
        assert status == 200

    async def test_batch_json_path_keeps_unlimited_policy(self):
        """批量 JSON 端点（非 multipart）沿用放行策略，不受 10MB 全局上限限制。"""
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope("/api/v1/batch/operations", {"content-type": "application/json"})
        status, _ = await _drive_asgi(mw, scope, [b"a" * 4096])
        assert status == 200

    async def test_upload_path_multipart_over_multipart_limit_rejected(self):
        """上传路径 multipart 超过分级上限仍拒绝。"""
        mw = BodySizeLimitMiddleware(app=_read_all_body_app, max_body_size=1024)
        scope = _http_scope(
            "/api/v1/permission-packages/import",
            {
                "content-length": str(513 * 1024 * 1024),
                "content-type": "multipart/form-data; boundary=x",
            },
        )
        status, _ = await _drive_asgi(mw, scope, [])
        assert status == 413
