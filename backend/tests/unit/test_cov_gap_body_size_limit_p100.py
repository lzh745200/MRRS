"""app.middleware.body_size_limit 缺口补口（.coveragerc fail_under=100）。

缺失行：
- 128：_is_body_too_large 对"与本中间件无关"的异常返回 False —— 下游任何其它
  异常都必须原样抛出，不能被误判成请求体超限而改成 413（掩盖真实故障）；
- 145：_StreamingBodyGuard.received 只读属性（真实到达字节计数，与
  Content-Length 声明无关）；
- 196：dispatch 慢路径中下游抛出的无关异常原样 re-raise。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.middleware.body_size_limit import (
    BodySizeLimitMiddleware,
    _BodyTooLarge,
    _StreamingBodyGuard,
    _is_body_too_large,
)


class TestIsBodyTooLarge:
    """异常归因：只认自家超限信号（含 ExceptionGroup 包装）。"""

    def test_own_signal_is_recognized(self):
        assert _is_body_too_large(_BodyTooLarge(10, 5)) is True

    def test_unrelated_exception_is_not_ours(self):
        """128 行：普通异常 → False（不得当成超限 → 不得回 413）。"""
        assert _is_body_too_large(ValueError("downstream boom")) is False

    def test_exception_group_without_own_signal(self):
        """126-128 行：ExceptionGroup 内无自家信号 → False。"""
        group = BaseExceptionGroup("wrapped", [ValueError("a"), OSError("b")])
        assert _is_body_too_large(group) is False

    def test_exception_group_with_own_signal(self):
        """对照组：anyio TaskGroup 包装后仍能识别自家信号。"""
        group = BaseExceptionGroup("wrapped", [ValueError("a"), _BodyTooLarge(10, 5)])
        assert _is_body_too_large(group) is True


class TestStreamingBodyGuardReceived:
    """145 行：只累计 http.request 的真实 body 字节。"""

    async def test_received_counts_only_request_body_bytes(self):
        pending = [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.disconnect"},
            {"type": "http.request"},  # 无 body 字段 → 按 0 计
        ]

        async def receive():
            return pending.pop(0)

        guard = _StreamingBodyGuard(receive, limit=1024)
        assert guard.received == 0

        assert await guard.receive() == {"type": "http.request", "body": b"abc", "more_body": True}
        assert guard.received == 3

        assert (await guard.receive())["type"] == "http.disconnect"
        assert guard.received == 3  # 非 http.request 消息不计字节

        await guard.receive()
        assert guard.received == 3


class TestDispatchReraisesUnrelatedErrors:
    """196 行：慢路径中无关异常原样抛出（只有本中间件的超限信号才转 413）。"""

    async def test_unrelated_exception_propagates(self):
        mw = BodySizeLimitMiddleware(app=MagicMock(name="app"), max_body_size=1024)
        request = SimpleNamespace(
            method="POST",
            url=SimpleNamespace(path="/api/v1/dashboard"),
            headers={"content-type": "application/json"},
            _receive=AsyncMock(return_value={"type": "http.request", "body": b"x"}),
        )
        call_next = AsyncMock(side_effect=ValueError("downstream boom"))

        with pytest.raises(ValueError, match="downstream boom"):
            await mw.dispatch(request, call_next)

        call_next.assert_awaited_once()

    async def test_own_signal_still_becomes_413(self):
        """对照组：自家超限信号 → 413（不被 re-raise）。"""
        mw = BodySizeLimitMiddleware(app=MagicMock(name="app"), max_body_size=1024)
        request = SimpleNamespace(
            method="POST",
            url=SimpleNamespace(path="/api/v1/dashboard"),
            headers={"content-type": "application/json"},
            _receive=AsyncMock(return_value={"type": "http.request", "body": b"x"}),
        )
        call_next = AsyncMock(side_effect=_BodyTooLarge(2048, 1024))

        response = await mw.dispatch(request, call_next)

        assert response.status_code == 413
