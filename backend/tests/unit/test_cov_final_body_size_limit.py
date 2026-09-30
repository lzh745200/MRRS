"""覆盖 app.middleware.body_size_limit：非法 content-length 头 fail-closed。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.middleware.body_size_limit import BodySizeLimitMiddleware


class TestInvalidContentLength:
    async def test_non_numeric_content_length_fails_closed(self):
        # OCR-2026-09-17：content-length 无法解析 → 不再静默放行，返回 400
        mw = BodySizeLimitMiddleware(app=MagicMock(), max_body_size=1024)
        request = SimpleNamespace(
            method="POST",
            url=SimpleNamespace(path="/api/v1/dashboard"),
            headers={"content-length": "not-a-number", "content-type": "application/json"},
        )
        call_next = AsyncMock(return_value="response-ok")

        result = await mw.dispatch(request, call_next)

        assert result.status_code == 400
        call_next.assert_not_awaited()

    async def test_oversize_content_length_returns_413(self):
        # 对照组：超限但合法的 content-length 仍返回 413
        mw = BodySizeLimitMiddleware(app=MagicMock(), max_body_size=1024)
        request = SimpleNamespace(
            method="POST",
            url=SimpleNamespace(path="/api/v1/dashboard"),
            headers={"content-length": "2048", "content-type": "application/json"},
        )
        call_next = AsyncMock(return_value="response-ok")

        result = await mw.dispatch(request, call_next)

        assert result.status_code == 413
        call_next.assert_not_awaited()
