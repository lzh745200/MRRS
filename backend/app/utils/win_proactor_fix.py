"""Windows ProactorEventLoop ConnectionResetError 彻底修复。

问题根因：
   Windows 上 Python ≥3.8 默认使用 ProactorEventLoop。当客户端（浏览器/Electron）
   异常断开连接时，TCP 层发送 RST 包。ProactorEventLoop 在清理传输层时调用
   ``self._sock.shutdown(socket.SHUT_RDWR)``，但此 socket 已被对端重置，
   Windows 抛出 ConnectionResetError: [WinError 10054]。

   虽然 CPython 3.10.8+ / 3.11.0+ 已在上层 try/except OSError 中捕获此异常，
   但某些 Python 构建版本或 uvicorn 自定义传输层中仍会泄漏此异常。

修复策略（纵深防御）：
   Layer 1 — Monkey-patch: 包装 ProactorBasePipeTransport._call_connection_lost，
            在 finally 块的 shutdown 调用外层再套一层 try/except，确保即使
            Python 标准库的 try/except 未覆盖到，我们的补丁也能兜底。
   Layer 2 — Event loop policy handler: 在全局 DefaultEventLoopPolicy 上
            设置异常处理器，uvicorn 创建的任何新 loop 都自动继承此处理器。
   Layer 3 — Runtime loop handler: 对当前正在运行的 loop 也设置处理器。

使用方式：
    # 在任何 asyncio 操作之前调用（import 即生效）
    from app.utils.win_proactor_fix import apply_windows_proactor_fix
    apply_windows_proactor_fix()

参考：
   - https://bugs.python.org/issue39010
   - https://github.com/encode/uvicorn/issues/998
"""

from __future__ import annotations

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)

_applied = False


def apply_windows_proactor_fix() -> bool:
    """应用 Windows ProactorEventLoop ConnectionResetError 修复。

    此函数是幂等的 — 多次调用仅生效一次。

    Returns:
        True 如果在 Windows 上应用了修复，False 如果不在 Windows 上。
    """
    global _applied
    if _applied:
        return sys.platform == "win32"

    if sys.platform != "win32":
        return False

    _applied = True

    # ── Layer 1: Monkey-patch 传输层 _call_connection_lost ──
    _patch_proactor_transport()

    # ── Layer 2: 全局 Policy 异常处理器 ──
    _patch_event_loop_policy()

    # ── Layer 3: 当前运行时 loop 处理器 ──
    _patch_running_loop()

    logger.debug(
        "Windows ProactorEventLoop ConnectionResetError 修复已应用 "
        "(3 层纵深防御: transport patch + policy handler + runtime handler)"
    )
    return True


# ──────────────────────────────────────────────────────────────────────
# Layer 1: Monkey-patch _ProactorBasePipeTransport
# ──────────────────────────────────────────────────────────────────────


def _patch_proactor_transport() -> None:
    """对 _ProactorBasePipeTransport._call_connection_lost 进行安全包装。

    原始的 _call_connection_lost 在 finally 块中调用 sock.shutdown()，
    但 try/except OSError 可能在某些 Python 版本/构建中缺失或未完全覆盖。
    我们通过包装原始方法来增加一层额外的保护。
    """
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
    except ImportError:  # pragma: no cover
        logger.debug("无法导入 _ProactorBasePipeTransport，跳过 transport patch")
        return

    # 检测是否已经被修补过
    if getattr(_ProactorBasePipeTransport, "_mrrms_patched", False):
        return

    _original = _ProactorBasePipeTransport._call_connection_lost

    def _safe_call_connection_lost(self: _ProactorBasePipeTransport, exc: BaseException | None) -> None:
        """包裹原始方法，在最外层兜底捕获连接重置异常。"""
        try:
            _original(self, exc)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as e:
            # 连接已被对端重置，socket 已不可用 → 静默关闭
            _silent_close(self, e)

    _safe_call_connection_lost._mrrms_original = _original  # type: ignore[attr-defined]
    _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost  # type: ignore[assignment]
    _ProactorBasePipeTransport._mrrms_patched = True  # type: ignore[attr-defined]

    logger.debug("ProactorBasePipeTransport._call_connection_lost 已包装 (Layer 1)")


def _silent_close(transport: object, error: BaseException) -> None:
    """关闭 transport socket 并补全 _call_connection_lost 的 finally 拆解。

    原实现的 finally 里 shutdown()/close() 一旦抛异常，其后的
    self._sock=None / _protocol=None / _loop=None / server._detach() / _server=None
    全部被跳过，transport 停在"半拆解"态：仍持有已关闭的 socket 与活着的
    protocol（深审 #9）。这里逐项兜底，任何一步失败都不阻断后续拆解。
    """
    sock = getattr(transport, '_sock', None)
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass

    for attr in ("_sock", "_protocol", "_loop"):
        try:
            setattr(transport, attr, None)
        except Exception:  # pragma: no cover - 只读/无 __dict__ 的替身对象兜底
            logger.debug("transport 属性 %s 无法置空（忽略）", attr)

    server = getattr(transport, "_server", None)
    if server is not None:
        try:
            server._detach()
        except Exception:  # pragma: no cover - 已 detach 的 server 兜底
            logger.debug("server._detach() 失败（忽略）")
        try:
            setattr(transport, "_server", None)
        except Exception:  # pragma: no cover - 只读属性兜底
            logger.debug("transport._server 无法置空（忽略）")

    logger.debug("静默关闭已重置的连接: %s", error)


# ──────────────────────────────────────────────────────────────────────
# Layer 2: 全局 Event Loop Policy 异常处理器
# ──────────────────────────────────────────────────────────────────────


def _patch_event_loop_policy() -> None:
    """在 DefaultEventLoopPolicy 层设置异常处理器。

    通过继承 DefaultEventLoopPolicy 并重写 new_event_loop()，
    确保 uvicorn 等框架创建的任何新事件循环都自动获得异常处理器。

    参考: asyncio 文档关于 Custom Event Loop Policies 的说明。
    """
    _HANDLER = _make_exception_handler()

    class _PatchedProactorEventLoop(asyncio.ProactorEventLoop):
        """ProactorEventLoop with ConnectionResetError suppression built-in."""

        def __init__(self) -> None:
            super().__init__()
            self.set_exception_handler(_HANDLER)

    # 安装自定义 Policy
    try:
        current_policy = asyncio.get_event_loop_policy()
    except Exception as e:
        logger.warning(f"获取事件循环策略失败: {e}")
        current_policy = None

    # 仅替换 Windows 上的默认策略
    if current_policy is None or isinstance(current_policy, asyncio.DefaultEventLoopPolicy):
        _PatchedPolicy = type(
            '_PatchedWindowsProactorPolicy',
            (asyncio.DefaultEventLoopPolicy,),
            {'_loop_factory': _PatchedProactorEventLoop},
        )
        asyncio.set_event_loop_policy(_PatchedPolicy())
        logger.debug("全局 EventLoopPolicy 已替换为带异常处理的版本 (Layer 2)")


# ──────────────────────────────────────────────────────────────────────
# Layer 3: 当前运行时 loop
# ──────────────────────────────────────────────────────────────────────


def _patch_running_loop() -> None:
    """对当前正在运行的事件循环设置异常处理器（如果存在）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # 无运行中的 loop，Layer 2 会覆盖后续创建的

    handler = _make_exception_handler()
    loop.set_exception_handler(handler)
    logger.debug("当前运行时事件循环已设置异常处理器 (Layer 3)")


# ──────────────────────────────────────────────────────────────────────
# 共享：异常处理器工厂
# ──────────────────────────────────────────────────────────────────────


def _make_exception_handler():
    """创建静默处理连接重置的异常处理器。

    同时捕获：
    - ConnectionResetError / ConnectionAbortedError / BrokenPipeError 异常对象
    - 无异常对象但 message 包含 "connection reset" 字符串的 context
    """
    _default_handler = None

    def _silent_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        nonlocal _default_handler

        exc = context.get('exception')
        # 已知的无害网络异常 → 静默
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            logger.debug(
                "静默处理连接重置 (loop=%s): %s",
                id(loop),
                exc,
            )
            return

        # 无异常对象但消息中提及连接重置（可能来自 SSL 层或底层 C 扩展）
        message = context.get('message', '')
        if isinstance(message, str):
            lower_msg = message.lower()
            if any(
                keyword in lower_msg
                for keyword in (
                    'connection reset',
                    'connection aborted',
                    'broken pipe',
                    'winerror 10054',
                    'errno 10054',
                )
            ):
                logger.debug(
                    "静默处理连接重置消息 (loop=%s): %s",
                    id(loop),
                    message,
                )
                return

        # 其他异常 → 委托给默认处理器
        if _default_handler is None:
            _default_handler = loop.default_exception_handler
        _default_handler(context)

    return _silent_handler
