import pytest
from unittest.mock import MagicMock, AsyncMock
import asyncio
import time


class TestTaskProgress:
    def test_percent_zero_total(self):
        from app.services.task_queue import TaskProgress
        p = TaskProgress()
        assert p.percent == 0.0

    def test_percent_calculated(self):
        from app.services.task_queue import TaskProgress
        p = TaskProgress(current=25, total=100)
        assert p.percent == 25.0

    def test_to_dict(self):
        from app.services.task_queue import TaskProgress
        p = TaskProgress(current=5, total=10, message="working")
        d = p.to_dict()
        assert d["current"] == 5
        assert d["message"] == "working"
        assert d["percent"] == 50.0


class TestTaskPriority:
    def test_values(self):
        from app.services.task_queue import TaskPriority
        assert TaskPriority.HIGH == 1
        assert TaskPriority.NORMAL == 5
        assert TaskPriority.LOW == 10


class TestTaskStatus:
    def test_values(self):
        from app.services.task_queue import TaskStatus
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"


class TestTask:
    def test_create_defaults(self):
        from app.services.task_queue import Task
        t = Task(func=lambda: None)
        assert t.id is not None
        assert t.status.value == "pending"
        assert t.error is None
        assert t.result is None
        assert t._cancelled is False

    def test_create_custom_id(self):
        from app.services.task_queue import Task
        t = Task(func=lambda: None, task_id="myid", name="myname", priority=1)
        assert t.id == "myid"
        assert t.name == "myname"
        assert t.priority == 1

    def test_name_defaults_to_func_name(self):
        from app.services.task_queue import Task
        def my_func():
            pass
        t = Task(func=my_func)
        assert t.name == "my_func"

    def test_is_cancelled(self):
        from app.services.task_queue import Task
        t = Task(func=lambda: None)
        assert t.is_cancelled is False
        t._cancelled = True
        assert t.is_cancelled is True

    def test_cancel_pending(self):
        from app.services.task_queue import Task, TaskStatus
        t = Task(func=lambda: None)
        assert t.cancel() is True
        assert t.status == TaskStatus.CANCELLED
        assert t._cancelled is True

    def test_cancel_running(self):
        from app.services.task_queue import Task, TaskStatus
        t = Task(func=lambda: None)
        t.status = TaskStatus.RUNNING
        assert t.cancel() is True

    def test_cancel_completed_fails(self):
        from app.services.task_queue import Task, TaskStatus
        t = Task(func=lambda: None)
        t.status = TaskStatus.COMPLETED
        assert t.cancel() is False

    def test_cancel_failed_fails(self):
        from app.services.task_queue import Task, TaskStatus
        t = Task(func=lambda: None)
        t.status = TaskStatus.FAILED
        assert t.cancel() is False

    def test_lt_different_priority(self):
        from app.services.task_queue import Task, TaskPriority
        high = Task(func=lambda: None, priority=TaskPriority.HIGH)
        low = Task(func=lambda: None, priority=TaskPriority.LOW)
        assert (high < low) is True

    def test_lt_same_priority(self):
        from app.services.task_queue import Task, TaskPriority
        t1 = Task(func=lambda: None, priority=TaskPriority.NORMAL)
        t2 = Task(func=lambda: None, priority=TaskPriority.NORMAL)
        assert (t1 < t2) == (t1.created_at < t2.created_at)

    def test_to_dict(self):
        from app.services.task_queue import Task
        t = Task(func=lambda: 42, name="test")
        d = t.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "pending"
        assert d["result"] is None
        assert d["error"] is None

    def test_to_dict_with_result(self):
        from app.services.task_queue import Task
        t = Task(func=lambda: 42)
        t.result = 42
        t.error = "err"
        d = t.to_dict()
        assert d["result"] == "42"
        assert d["error"] == "err"


class TestLocalTaskQueue:
    @pytest.mark.asyncio
    async def test_start(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue(max_workers=2)
        await q.start()
        assert q._running is True
        assert len(q._worker_tasks) == 2
        await q.stop()

    @pytest.mark.asyncio
    async def test_start_twice(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        await q.start()
        await q.start()
        await q.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        await q.stop()

    @pytest.mark.asyncio
    async def test_submit_before_start(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        async def dummy():
            return 1
        task_id = await q.submit(dummy)
        assert task_id is not None
        assert task_id in q._tasks

    @pytest.mark.asyncio
    async def test_submit_and_execute(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        await q.start()

        async def dummy():
            return 42

        task_id = await q.submit(dummy, name="dummy")
        await asyncio.sleep(0.2)
        task = q.get_task(task_id)
        assert task["status"] == "completed"
        assert task["result"] == "42"
        await q.stop()

    @pytest.mark.asyncio
    async def test_submit_sync_func(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        await q.start()

        def sync_func():
            return 99

        task_id = await q.submit(sync_func, name="sync")
        await asyncio.sleep(0.2)
        task = q.get_task(task_id)
        assert task["status"] == "completed"
        await q.stop()

    @pytest.mark.asyncio
    async def test_cancelled_task_skipped(self):
        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus
        q = LocalTaskQueue()
        q._queue = asyncio.PriorityQueue()
        q._running = True
        t = Task(func=lambda: 1, name="cancelled")
        t._cancelled = True
        await q._queue.put(t)
        q._worker_tasks = [asyncio.create_task(q._worker("w1"))]
        await asyncio.sleep(0.1)
        await q.stop()
        assert t.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_worker_task_failure(self):
        from app.services.task_queue import LocalTaskQueue, Task
        q = LocalTaskQueue()
        q._queue = asyncio.PriorityQueue()
        q._running = True

        async def failing():
            raise ValueError("fail")

        t = Task(func=failing, name="failing")
        q._tasks[t.id] = t
        await q._queue.put(t)
        q._worker_tasks = [asyncio.create_task(q._worker("w1"))]
        await asyncio.sleep(0.1)
        await q.stop()
        task_dict = q.get_task(t.id)
        assert task_dict["status"] == "failed"
        assert "fail" in task_dict["error"]

    @pytest.mark.asyncio
    async def test_worker_cancelled_during_exec(self):
        from app.services.task_queue import LocalTaskQueue, Task
        q = LocalTaskQueue()
        q._queue = asyncio.PriorityQueue()
        q._running = True

        async def slow_task():
            await asyncio.sleep(5)
            return "done"

        t = Task(func=slow_task, name="slow")
        t.cancel()
        await q._queue.put(t)
        q._worker_tasks = [asyncio.create_task(q._worker("w1"))]
        await asyncio.sleep(0.1)
        await q.stop()

    @pytest.mark.asyncio
    async def test_queue_timeout(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        q._queue = asyncio.PriorityQueue()
        q._running = True
        q._worker_tasks = [asyncio.create_task(q._worker("w1"))]
        await asyncio.sleep(0.1)
        await q.stop()

    @pytest.mark.asyncio
    async def test_worker_timeout_error_continue(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        q._running = True
        mock_queue = AsyncMock()

        async def _timeout_after_yield():
            # 必须真正让出一次事件循环再抛：若 side_effect 同步抛出 TimeoutError，
            # asyncio.wait_for 不会挂起，_worker 的 `while self._running` 会退化成
            # 不 yield 的紧循环 → 本用例的 asyncio.sleep/q.stop() 永不执行 → 死锁，
            # 且 pytest-timeout(thread) 会 dump 全部线程栈后直接杀掉整个全量进程。
            await asyncio.sleep(0)
            raise asyncio.TimeoutError()

        mock_queue.get.side_effect = _timeout_after_yield
        q._queue = mock_queue
        q._worker_tasks = [asyncio.create_task(q._worker("w1"))]
        await asyncio.sleep(0.05)
        # 连续超时后 worker 必须仍存活（走的是 continue 分支，而不是 break 退出）
        assert not q._worker_tasks[0].done()
        assert mock_queue.get.await_count >= 2
        await q.stop()

    @pytest.mark.asyncio
    async def test_worker_generic_exception_break(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        q._running = True
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = RuntimeError("unexpected")
        q._queue = mock_queue
        q._worker_tasks = [asyncio.create_task(q._worker("w1"))]
        await asyncio.sleep(0.05)
        assert q._worker_tasks[0].done()
        await q.stop()

    def test_update_progress_not_found(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        assert q.update_progress("nonexistent", 50, 100, "msg") is False

    def test_update_progress_success(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        t = MagicMock()
        t.progress = MagicMock()
        q._tasks["tid"] = t
        assert q.update_progress("tid", 50, 100, "msg") is True
        assert t.progress.current == 50
        assert t.progress.total == 100
        assert t.progress.message == "msg"

    def test_cancel_task_not_found(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        assert q.cancel_task("nonexistent") is False

    def test_cancel_task_success(self):
        from app.services.task_queue import LocalTaskQueue, Task
        q = LocalTaskQueue()
        t = Task(func=lambda: None)
        q._tasks[t.id] = t
        assert q.cancel_task(t.id) is True

    def test_get_task_not_found(self):
        from app.services.task_queue import LocalTaskQueue
        q = LocalTaskQueue()
        assert q.get_task("nonexistent") is None

    def test_get_task_found(self):
        from app.services.task_queue import LocalTaskQueue, Task
        q = LocalTaskQueue()
        t = Task(func=lambda: None, name="test")
        q._tasks[t.id] = t
        result = q.get_task(t.id)
        assert result["name"] == "test"

    def test_list_tasks_no_filter(self):
        from app.services.task_queue import LocalTaskQueue, Task
        q = LocalTaskQueue()
        q._tasks["1"] = Task(func=lambda: None, name="a")
        q._tasks["2"] = Task(func=lambda: None, name="b")
        assert len(q.list_tasks()) == 2

    def test_list_tasks_with_filter(self):
        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus
        q = LocalTaskQueue()
        t = Task(func=lambda: None)
        t2 = Task(func=lambda: None)
        t2.status = TaskStatus.COMPLETED
        q._tasks["1"] = t
        q._tasks["2"] = t2
        result = q.list_tasks(TaskStatus.PENDING)
        assert len(result) == 1

    def test_get_queue_stats(self):
        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus
        q = LocalTaskQueue()
        t = Task(func=lambda: None)
        t2 = Task(func=lambda: None)
        t2.status = TaskStatus.COMPLETED
        q._tasks["1"] = t
        q._tasks["2"] = t2
        stats = q.get_queue_stats()
        assert stats["total"] == 2
        assert stats["pending"] == 1
        assert stats["completed"] == 1

    def test_cleanup(self):
        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus
        q = LocalTaskQueue()
        t = Task(func=lambda: None)
        t.status = TaskStatus.COMPLETED
        t.completed_at = time.time() - 7200
        q._tasks["old"] = t
        t2 = Task(func=lambda: None)
        t2.status = TaskStatus.RUNNING
        q._tasks["new"] = t2
        count = q.cleanup(max_age=3600)
        assert count == 1
        assert "new" in q._tasks
        assert "old" not in q._tasks

    def test_cleanup_no_completed_at(self):
        from app.services.task_queue import LocalTaskQueue, Task, TaskStatus
        q = LocalTaskQueue()
        t = Task(func=lambda: None)
        t.status = TaskStatus.COMPLETED
        t.completed_at = None
        q._tasks["t"] = t
        count = q.cleanup()
        assert count == 0


class TestTaskQueueWrapper:
    def test_create(self):
        from app.services.task_queue import TaskQueue
        q = TaskQueue.create()
        assert q is not None
        assert q.db is None

    def test_init_with_db(self):
        from app.services.task_queue import TaskQueue
        mock_db = MagicMock()
        q = TaskQueue(mock_db)
        assert q.db is mock_db

    @pytest.mark.asyncio
    async def test_submit_task(self):
        from app.services.task_queue import TaskQueue
        q = TaskQueue()

        async def dummy():
            return 1

        task_id = await q.submit_task(dummy)
        assert task_id is not None

    def test_get_status_not_found(self):
        from app.services.task_queue import TaskQueue
        q = TaskQueue()
        assert q.get_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_status_found(self):
        from app.services.task_queue import TaskQueue
        q = TaskQueue()

        async def dummy():
            return 1

        task_id = await q.submit_task(dummy)
        status = q.get_status(task_id)
        assert status is not None
        assert status["id"] == task_id
        assert status["status"] == "pending"
