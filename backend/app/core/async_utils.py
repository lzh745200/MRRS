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
    """
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
    """创建后台任务，自动选择事件循环。"""
    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(coro)
    except RuntimeError:
        loop = get_event_loop_safe()
        return loop.create_task(coro)
