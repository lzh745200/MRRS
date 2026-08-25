"""app/utils/win_proactor_fix.py 单元测试。

覆盖 3 层纵深防御修复的所有分支：
- apply_windows_proactor_fix：幂等性 + 平台判断
- _patch_proactor_transport：ImportError / 已修补 / 正常包装 / 包装函数的异常捕获
- _silent_close：sock 缺失 / close 抛 OSError / 正常关闭
- _patch_event_loop_policy：get_event_loop_policy 抛异常 / 非 Default 策略 / 正常替换
- _patch_running_loop：无运行 loop / 有运行 loop
- _make_exception_handler：各类异常/消息分支 + 默认处理器委托
"""
import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from app.utils import win_proactor_fix
from app.utils.win_proactor_fix import (
    _make_exception_handler,
    _patch_event_loop_policy,
    _patch_proactor_transport,
    _patch_running_loop,
    _silent_close,
    apply_windows_proactor_fix,
)

# ProactorEventLoop 仅存在于 Windows；Linux CI 上 asyncio 无此属性
# （nightly #13 实测 4 失败），整模块跳过非 Windows 平台。
pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("win"),
    reason="Windows-only asyncio.ProactorEventLoop",
)


# ─────────────────────────────────────────────────────────────
# 全局 fixture：每个测试前重置 _applied 标志
# ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _reset_applied_flag(monkeypatch):
    """apply_windows_proactor_fix 用模块级 _applied 保证幂等；测试间需重置。"""
    monkeypatch.setattr(win_proactor_fix, "_applied", False)


# ─────────────────────────────────────────────────────────────
# fixture：保存/还原 _ProactorBasePipeTransport 修补状态
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def fresh_transport_state():
    """将 _ProactorBasePipeTransport 还原到未修补状态，结束后恢复原状。"""
    from asyncio.proactor_events import _ProactorBasePipeTransport as _Transport

    saved_method = _Transport._call_connection_lost
    saved_patched = getattr(_Transport, "_mrrms_patched", False)
    saved_original = getattr(saved_method, "_mrrms_original", None)

    # 还原到真正原始方法
    if saved_patched and saved_original is not None:
        _Transport._call_connection_lost = saved_original
    if hasattr(_Transport, "_mrrms_patched"):
        del _Transport._mrrms_patched

    yield _Transport

    # 恢复测试前的状态
    _Transport._call_connection_lost = saved_method
    if saved_patched:
        _Transport._mrrms_patched = True
    elif hasattr(_Transport, "_mrrms_patched"):
        del _Transport._mrrms_patched


# ─────────────────────────────────────────────────────────────
# fixture：保存/还原全局 EventLoopPolicy
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def restore_event_loop_policy():
    original = asyncio.get_event_loop_policy()
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(original)


# ═════════════════════════════════════════════════════════════
# apply_windows_proactor_fix
# ═════════════════════════════════════════════════════════════
class TestApplyWindowsProactorFix:
    def test_first_call_on_windows_applies_and_returns_true(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        calls = {"transport": 0, "policy": 0, "loop": 0}
        monkeypatch.setattr(
            win_proactor_fix, "_patch_proactor_transport", lambda: calls.__setitem__("transport", 1)
        )
        monkeypatch.setattr(
            win_proactor_fix, "_patch_event_loop_policy", lambda: calls.__setitem__("policy", 1)
        )
        monkeypatch.setattr(
            win_proactor_fix, "_patch_running_loop", lambda: calls.__setitem__("loop", 1)
        )

        result = apply_windows_proactor_fix()

        assert result is True
        assert win_proactor_fix._applied is True
        assert calls == {"transport": 1, "policy": 1, "loop": 1}

    def test_second_call_on_windows_is_idempotent(self, monkeypatch):
        """已应用后再调用：直接返回 True，不重复执行 3 层修补。"""
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(win_proactor_fix, "_applied", True)

        calls = []
        monkeypatch.setattr(
            win_proactor_fix, "_patch_proactor_transport", lambda: calls.append("t")
        )
        monkeypatch.setattr(
            win_proactor_fix, "_patch_event_loop_policy", lambda: calls.append("p")
        )
        monkeypatch.setattr(
            win_proactor_fix, "_patch_running_loop", lambda: calls.append("l")
        )

        result = apply_windows_proactor_fix()
        assert result is True
        assert calls == []  # 未重复执行

    def test_already_applied_on_non_windows_returns_false(self, monkeypatch):
        """已应用 + 非 Windows：返回 False（与 sys.platform 一致）。"""
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(win_proactor_fix, "_applied", True)
        assert apply_windows_proactor_fix() is False

    def test_first_call_on_non_windows_returns_false(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        calls = []
        monkeypatch.setattr(
            win_proactor_fix, "_patch_proactor_transport", lambda: calls.append("t")
        )
        result = apply_windows_proactor_fix()
        assert result is False
        # 非 Windows 上不应触发修补，也不应设置 _applied
        assert win_proactor_fix._applied is False
        assert calls == []


# ═════════════════════════════════════════════════════════════
# _patch_proactor_transport
# ═════════════════════════════════════════════════════════════
class TestPatchProactorTransport:
    def test_import_error_returns_silently(self, monkeypatch):
        """asyncio.proactor_events 不可导入时应早返回，不抛异常。"""
        # 将 sys.modules 中该模块设为 None → from ... import 触发 ImportError
        monkeypatch.setitem(sys.modules, "asyncio.proactor_events", None)

        # 核心断言：不抛异常即为通过（caplog 在 xdist 并行模式下不可靠）
        _patch_proactor_transport()

    def test_already_patched_returns_early(self, fresh_transport_state):
        """_mrrms_patched=True 时应早返回，不重复包装。"""
        fresh_transport_state._mrrms_patched = True
        original = fresh_transport_state._call_connection_lost

        _patch_proactor_transport()

        # 方法未被替换
        assert fresh_transport_state._call_connection_lost is original

    def test_normal_wrap_replaces_method_and_sets_flags(
        self, fresh_transport_state
    ):
        _Transport = fresh_transport_state
        original_method = _Transport._call_connection_lost

        _patch_proactor_transport()

        wrapped = _Transport._call_connection_lost
        assert wrapped is not original_method
        assert getattr(wrapped, "_mrrms_original", None) is original_method
        assert getattr(_Transport, "_mrrms_patched", False) is True

    def test_wrapped_function_passes_through_when_original_succeeds(
        self, fresh_transport_state
    ):
        _Transport = fresh_transport_state
        call_log = []

        def fake_original(self, exc):
            call_log.append(("called", self, exc))

        _Transport._call_connection_lost = fake_original
        if hasattr(_Transport, "_mrrms_patched"):
            del _Transport._mrrms_patched

        _patch_proactor_transport()

        transport = MagicMock(name="transport")
        exc = RuntimeError("test")
        _Transport._call_connection_lost(transport, exc)

        assert call_log == [("called", transport, exc)]

    def test_wrapped_function_swallows_connection_reset_and_closes(
        self, fresh_transport_state, monkeypatch
    ):
        _Transport = fresh_transport_state

        def raising_original(self, exc):
            raise ConnectionResetError("peer reset")

        _Transport._call_connection_lost = raising_original
        if hasattr(_Transport, "_mrrms_patched"):
            del _Transport._mrrms_patched

        silent_calls = []
        monkeypatch.setattr(
            win_proactor_fix,
            "_silent_close",
            lambda t, e: silent_calls.append((t, e)),
        )

        _patch_proactor_transport()

        transport = MagicMock(name="transport")
        test_exc = RuntimeError("orig")
        # 不应抛异常
        _Transport._call_connection_lost(transport, test_exc)

        assert len(silent_calls) == 1
        assert silent_calls[0][0] is transport
        # 第二个参数应是 ConnectionResetError 实例
        assert isinstance(silent_calls[0][1], ConnectionResetError)

    def test_wrapped_function_swallows_oserror(
        self, fresh_transport_state, monkeypatch
    ):
        _Transport = fresh_transport_state

        def raising_original(self, exc):
            raise OSError("generic")

        _Transport._call_connection_lost = raising_original
        if hasattr(_Transport, "_mrrms_patched"):
            del _Transport._mrrms_patched

        monkeypatch.setattr(
            win_proactor_fix, "_silent_close", lambda t, e: None
        )

        _patch_proactor_transport()

        transport = MagicMock(name="transport")
        # OSError 应被吞掉，不向上抛
        _Transport._call_connection_lost(transport, None)

    def test_wrapped_function_swallows_broken_pipe(
        self, fresh_transport_state, monkeypatch
    ):
        _Transport = fresh_transport_state

        def raising_original(self, exc):
            raise BrokenPipeError("broken")

        _Transport._call_connection_lost = raising_original
        if hasattr(_Transport, "_mrrms_patched"):
            del _Transport._mrrms_patched

        monkeypatch.setattr(
            win_proactor_fix, "_silent_close", lambda t, e: None
        )

        _patch_proactor_transport()
        _Transport._call_connection_lost(MagicMock(), None)  # 不抛


# ═════════════════════════════════════════════════════════════
# _silent_close
# ═════════════════════════════════════════════════════════════
class TestSilentClose:
    def test_no_sock_attribute_logs_only(self):
        """transport 无 _sock 属性时不应抛错。"""
        transport = object()  # 简单对象无 _sock
        _silent_close(transport, ConnectionResetError("reset"))

    def test_sock_none_logs_only(self):
        transport = MagicMock()
        transport._sock = None
        _silent_close(transport, ConnectionResetError("reset"))

    def test_sock_close_called(self):
        transport = MagicMock()
        sock = MagicMock()
        transport._sock = sock
        _silent_close(transport, ConnectionResetError("reset"))
        sock.close.assert_called_once_with()

    def test_sock_close_oserror_swallowed(self):
        """sock.close() 抛 OSError 时应被静默吞掉。"""
        transport = MagicMock()
        sock = MagicMock()
        sock.close.side_effect = OSError("fail")
        transport._sock = sock
        # 不应抛异常
        _silent_close(transport, ConnectionResetError("reset"))
        sock.close.assert_called_once_with()


# ═════════════════════════════════════════════════════════════
# _patch_event_loop_policy
# ═════════════════════════════════════════════════════════════
class TestPatchEventLoopPolicy:
    def test_replaces_default_policy_with_patched_one(
        self, restore_event_loop_policy
    ):
        """当前为 DefaultEventLoopPolicy 时应替换为带异常处理器的版本。"""
        # 确保起点是默认策略
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        original = asyncio.get_event_loop_policy()
        assert isinstance(original, asyncio.DefaultEventLoopPolicy)

        _patch_event_loop_policy()

        new_policy = asyncio.get_event_loop_policy()
        assert isinstance(new_policy, asyncio.DefaultEventLoopPolicy)
        assert new_policy is not original

    def test_new_policy_creates_loop_with_handler(
        self, restore_event_loop_policy
    ):
        """替换后的 policy 创建的 loop 自带异常处理器。"""
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        _patch_event_loop_policy()

        new_loop = asyncio.new_event_loop()
        try:
            assert new_loop.get_exception_handler() is not None
        finally:
            new_loop.close()

    def test_get_event_loop_policy_raising_falls_back_to_install(
        self, monkeypatch, restore_event_loop_policy
    ):
        """asyncio.get_event_loop_policy 抛异常 → current_policy=None → 仍安装。"""
        original_get_policy = asyncio.get_event_loop_policy

        def raise_exc():
            raise RuntimeError("policy boom")

        monkeypatch.setattr(asyncio, "get_event_loop_policy", raise_exc)

        _patch_event_loop_policy()  # 不应抛

        # 恢复后再读取策略以验证
        monkeypatch.undo()
        new_policy = original_get_policy()
        assert isinstance(new_policy, asyncio.DefaultEventLoopPolicy)

    def test_non_default_policy_is_not_replaced(
        self, restore_event_loop_policy
    ):
        """当前策略非 DefaultEventLoopPolicy 时不应替换。"""

        class _CustomPolicy(asyncio.AbstractEventLoopPolicy):
            def get_event_loop(self):
                raise NotImplementedError

            def set_event_loop(self, loop):
                pass

            def new_event_loop(self):
                raise NotImplementedError

        custom = _CustomPolicy()
        asyncio.set_event_loop_policy(custom)

        _patch_event_loop_policy()

        assert asyncio.get_event_loop_policy() is custom


# ═════════════════════════════════════════════════════════════
# _patch_running_loop
# ═════════════════════════════════════════════════════════════
class TestPatchRunningLoop:
    def test_no_running_loop_returns_silently(self):
        """在同步上下文中调用：无运行中的 loop，应早返回。"""
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()  # 前置断言：当前确实无运行 loop
        _patch_running_loop()  # 不应抛异常

    async def test_running_loop_gets_handler_set(self):
        """在 async 测试中：存在运行 loop，应设置异常处理器。"""
        loop = asyncio.get_running_loop()
        original_handler = loop.get_exception_handler()
        try:
            _patch_running_loop()
            assert loop.get_exception_handler() is not None
        finally:
            loop.set_exception_handler(original_handler)


# ═════════════════════════════════════════════════════════════
# _make_exception_handler
# ═════════════════════════════════════════════════════════════
class TestMakeExceptionHandler:
    @pytest.mark.parametrize(
        "exc_cls",
        [ConnectionResetError, ConnectionAbortedError, BrokenPipeError],
    )
    def test_known_connection_exceptions_are_silenced(self, exc_cls):
        handler = _make_exception_handler()
        loop = MagicMock(name="loop")
        exc = exc_cls("test")
        context = {"exception": exc}

        handler(loop, context)

        # 不应调用 default_exception_handler
        loop.default_exception_handler.assert_not_called()

    def test_message_with_connection_reset_keyword_is_silenced(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "Connection reset by peer"}
        handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_message_with_connection_aborted_keyword_is_silenced(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "Connection aborted"}
        handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_message_with_broken_pipe_keyword_is_silenced(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "Broken pipe on socket"}
        handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_message_with_winerror_10054_is_silenced(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "WinError 10054 from socket"}
        handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_message_with_errno_10054_is_silenced(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "Errno 10054"}
        handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_message_case_insensitive_match(self):
        """message 大小写不敏感。"""
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "CONNECTION RESET"}
        handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_non_string_message_falls_through_to_default(self):
        """message 非 str（如 None）时应跳过消息匹配，委托默认处理器。"""
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": None, "exception": ValueError("x")}
        handler(loop, context)
        loop.default_exception_handler.assert_called_once_with(context)

    def test_other_exception_delegates_to_default_handler(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"exception": ValueError("not connection-related")}
        handler(loop, context)
        loop.default_exception_handler.assert_called_once_with(context)

    def test_other_message_delegates_to_default_handler(self):
        handler = _make_exception_handler()
        loop = MagicMock()
        context = {"message": "some unrelated error"}
        handler(loop, context)
        loop.default_exception_handler.assert_called_once_with(context)

    def test_default_handler_cached_across_calls(self):
        """_default_handler 闭包变量首次访问后缓存，后续不再重新获取。"""
        handler = _make_exception_handler()
        loop = MagicMock()
        # 第一次调用触发缓存（other 路径）
        handler(loop, {"exception": ValueError("a")})
        first_default = loop.default_exception_handler
        assert first_default.call_count == 1
        # 第二次调用应复用同一个缓存对象，而非重新读取 loop.default_exception_handler
        # 通过让 default_exception_handler 返回新的 Mock 来验证缓存生效
        loop.default_exception_handler = MagicMock(name="second")
        second_context = {"exception": ValueError("b")}
        handler(loop, second_context)
        # first_default 被调用 2 次（第一次 + 缓存命中的第二次）
        assert first_default.call_count == 2
        # 第二个 mock 不应被触碰 → 证明走的是缓存
        loop.default_exception_handler.assert_not_called()

    def test_empty_context_delegates_to_default(self):
        """空 context（无 exception 也无 message）应委托默认处理器。"""
        handler = _make_exception_handler()
        loop = MagicMock()
        handler(loop, {})
        loop.default_exception_handler.assert_called_once_with({})
