"""Tests for app/core/async_utils.py — 100% coverage."""
import asyncio


class TestGetExecutor:
    """_get_executor — lazy ThreadPoolExecutor singleton."""

    def test_returns_thread_pool_executor(self):
        from app.core.async_utils import _get_executor
        from concurrent.futures import ThreadPoolExecutor
        ex = _get_executor()
        assert isinstance(ex, ThreadPoolExecutor)

    def test_singleton(self):
        from app.core.async_utils import _get_executor
        ex1 = _get_executor()
        ex2 = _get_executor()
        assert ex1 is ex2

    def test_lazy_initialization(self):
        from app.core.async_utils import _get_executor
        from app.core.async_utils import _EXECUTOR as old
        import app.core.async_utils as m
        try:
            m._EXECUTOR = None
            ex = _get_executor(max_workers=5)
            assert ex._max_workers == 5
        finally:
            m._EXECUTOR = old

    def test_double_checked_locking_skips_lock_when_initialized(self):
        """When _EXECUTOR is already initialized, the lock is not entered."""
        from app.core.async_utils import _get_executor
        # First call initializes it
        ex1 = _get_executor()
        # Second call should skip the lock block entirely
        ex2 = _get_executor()
        assert ex1 is ex2


class TestRunInThread:
    """run_in_thread — execute sync function in thread pool."""

    async def test_successful_execution(self):
        from app.core.async_utils import run_in_thread

        def sync_add(a, b):
            return a + b

        result = await run_in_thread(sync_add, 2, 3)
        assert result == 5

    async def test_with_kwargs(self):
        from app.core.async_utils import run_in_thread

        def sync_kwargs(a, b=10):
            return a * b

        result = await run_in_thread(sync_kwargs, 5, b=20)
        assert result == 100


class TestRunInExecutor:
    """run_in_executor — alias for run_in_thread."""

    async def test_alias(self):
        from app.core.async_utils import run_in_executor

        result = await run_in_executor(lambda: 99)
        assert result == 99


class TestSyncDecorator:
    """sync — wraps async function so it can be called from sync code."""

    def test_sync_decorator(self):
        from app.core.async_utils import sync

        @sync
        async def async_func(x):
            return x * 2

        result = async_func(5)
        assert result == 10

    def test_sync_preserves_name(self):
        from app.core.async_utils import sync

        @sync
        async def my_custom_func():
            return 42

        assert my_custom_func.__name__ == "my_custom_func"


class TestGatherLimited:
    """gather_limited — bounded concurrency semaphore."""

    async def test_all_results_in_order(self):
        from app.core.async_utils import gather_limited

        async def make(val):
            return val

        results = await gather_limited(2, make(1), make(2), make(3))
        assert results == [1, 2, 3]

    async def test_concurrency_one(self):
        from app.core.async_utils import gather_limited

        async def make(val):
            return val

        results = await gather_limited(1, make(10), make(20))
        assert results == [10, 20]

    async def test_empty_coros(self):
        from app.core.async_utils import gather_limited

        results = await gather_limited(5)
        assert results == []


class TestDelay:
    """delay — non-blocking sleep."""

    async def test_delay(self):
        from app.core.async_utils import delay
        start = asyncio.get_running_loop().time()
        await delay(0.05)
        elapsed = asyncio.get_running_loop().time() - start
        assert elapsed >= 0.01


class TestGetEventLoopSafe:
    """get_event_loop_safe — return running or cached loop."""

    def test_returns_running_loop(self):
        """Inside an async context, returns the running loop."""
        async def inner():
            from app.core.async_utils import get_event_loop_safe
            loop = get_event_loop_safe()
            assert loop is asyncio.get_running_loop()

        asyncio.run(inner())

    def test_no_running_loop_creates_new(self):
        """Outside async context, creates and caches a new loop."""
        from app.core.async_utils import get_event_loop_safe
        from app.core.async_utils import _cached_loop as old_cache
        import app.core.async_utils as m
        try:
            m._cached_loop = None
            loop = get_event_loop_safe()
            assert loop is not None
            assert not loop.is_closed()
            # Calling again returns the same cached loop
            loop2 = get_event_loop_safe()
            assert loop2 is loop
        finally:
            m._cached_loop = old_cache

    def test_closed_loop_recreated(self):
        """If cached loop is closed, a new one is created."""
        from app.core.async_utils import get_event_loop_safe
        from app.core.async_utils import _cached_loop as old_cache
        import app.core.async_utils as m
        try:
            m._cached_loop = None
            loop1 = get_event_loop_safe()
            loop1.close()
            loop2 = get_event_loop_safe()
            assert loop2 is not loop1
            assert not loop2.is_closed()
        finally:
            m._cached_loop = old_cache


class TestCreateBackgroundTask:
    """create_background_task — auto-select event loop."""

    async def test_with_running_loop(self):
        from app.core.async_utils import create_background_task

        results = []

        async def record():
            results.append("ran")

        task = create_background_task(record())
        assert isinstance(task, asyncio.Task)
        await task
        assert "ran" in results

    def test_no_running_loop(self):
        """无运行循环时返回 None（R12-7），且协程被显式 close。

        旧行为把任务挂到 get_event_loop_safe() 的缓存循环上：该循环在生产
        路径从不 run —— 任务永不执行、退出时抛 "Task was destroyed but it is
        pending!"，而调用方为 None 准备的兜底分支（monitoring_service 线程池
        发告警）永远走不到。**行为语义变更，已由架构评审（遗留风险治理计划
        R12-7）裁定。**
        """
        import inspect

        from app.core.async_utils import create_background_task

        async def record():  # pragma: no cover - 新契约下不应被执行
            return "ran"

        coro = record()
        assert create_background_task(coro) is None
        # close 掉协程：避免 CPython "coroutine was never awaited" 噪声
        assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
