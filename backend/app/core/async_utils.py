"""Async utility functions.

Provides helpers for async/sync interop, background task scheduling,
and async-safe file/DB operations.
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, Coroutine, Optional, TypeVar

logger = logging.getLogger(__name__)

# Shared thread pool for running blocking I/O without starving the event loop
_EXECUTOR: Optional[ThreadPoolExecutor] = None
_LOCK = threading.Lock()

T = TypeVar("T")


def _get_executor(max_workers: int = 10) -> ThreadPoolExecutor:
    """Return (and lazily create) the shared thread-pool executor."""
    global _EXECUTOR
    if _EXECUTOR is None:
        with _LOCK:
            if _EXECUTOR is None:
                _EXECUTOR = ThreadPoolExecutor(
                    max_workers=max_workers, thread_name_prefix="async_utils"
                )
    return _EXECUTOR


async def run_in_thread(func: Callable[..., T], *args, **kwargs) -> T:
    """Execute a blocking synchronous function in a thread pool.

    Use this to avoid blocking the event loop with CPU-heavy or
    synchronous-I/O calls (e.g. file-system operations, large serialisation).

    Args:
        func: The blocking callable.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        The return value of *func*.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_get_executor(), lambda: func(*args, **kwargs))


async def run_in_executor(func: Callable[..., T], *args, **kwargs) -> T:
    """Alias for :func:`run_in_thread`."""
    return await run_in_thread(func, *args, **kwargs)


def sync(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
    """Decorator that wraps an async function so it can be called from sync code.

    Usage::

        @sync
        async def fetch_data():
            ...
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


async def gather_limited(
    concurrency: int, *coros: Coroutine
) -> list[Any]:
    """Run coroutines with a bounded concurrency (semaphore).

    Args:
        concurrency: Maximum number of concurrently executing coroutines.
        *coros: Coroutines to execute.

    Returns:
        List of results in the same order as *coros*.

    Raises:
        ValueError: *concurrency* 小于 1。0 会让 Semaphore(0) 永久阻塞首个
            acquire()（整个 gather 永不返回）；负数会让构造器直接抛错。
    """
    if concurrency < 1:
        raise ValueError(f"concurrency 必须 >= 1，收到 {concurrency}")
    sem = asyncio.Semaphore(concurrency)

    async def limited(coro: Coroutine) -> Any:
        async with sem:
            return await coro

    return await asyncio.gather(*(limited(c) for c in coros))


async def delay(seconds: float) -> None:
    """Non-blocking sleep helper."""
    await asyncio.sleep(seconds)


_cached_loop: Optional[asyncio.AbstractEventLoop] = None


def get_event_loop_safe():
    """Return running event loop, or a cached reusable loop for sync contexts."""
    global _cached_loop
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        if _cached_loop is None or _cached_loop.is_closed():
            _cached_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_cached_loop)
        return _cached_loop


def create_background_task(coro):
    """在当前运行的事件循环上创建后台任务；无运行循环时返回 None。

    R12-7（遗留风险治理）：原实现在无运行循环时走 get_event_loop_safe()，
    把一个"新建后从不 run"的缓存循环拿去 create_task —— 任务永不执行、
    退出时抛 "Task was destroyed but it is pending!"；而调用方为 None 准备的
    兜底分支（monitoring_service 的线程池发送）永远走不到，告警通知实际
    静默丢失。现在如实返回 None，并 close 协程避免 "never awaited" 噪声，
    由调用方决定兜底策略。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return None
    return loop.create_task(coro)
