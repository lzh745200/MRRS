"""
本地任务队列模块
提供简单的内存任务队列（单机版，无需Redis/Celery）
支持优先级、进度追踪、任务取消
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """任务优先级（数值越小优先级越高）"""

    HIGH = 1
    NORMAL = 5
    LOW = 10


@dataclass
class TaskProgress:
    """任务进度信息"""

    current: int = 0
    total: int = 0
    message: str = ""
    updated_at: float = 0.0

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(self.current / self.total * 100, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": self.current,
            "total": self.total,
            "percent": self.percent,
            "message": self.message,
            "updated_at": self.updated_at,
        }


class Task:
    """任务对象"""

    def __init__(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        task_id: Optional[str] = None,
        name: Optional[str] = None,
        priority: int = TaskPriority.NORMAL,
    ):
        self.id = task_id or str(uuid.uuid4())
        self.name = name or func.__name__
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.progress = TaskProgress()
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> bool:
        """取消任务（仅 PENDING 或 RUNNING 状态可取消）"""
        if self.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            self._cancelled = True
            self.status = TaskStatus.CANCELLED
            self.completed_at = time.time()
            return True
        return False

    def __lt__(self, other: "Task") -> bool:
        """优先级比较，用于 PriorityQueue"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority,
            "progress": self.progress.to_dict(),
            "result": str(self.result) if self.result else None,
            "error": str(self.error) if self.error else None,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class LocalTaskQueue:
    """本地内存任务队列（支持优先级调度）"""

    def __init__(self, max_workers: int = 3):
        self._tasks: Dict[str, Task] = {}
        self._queue: asyncio.PriorityQueue = None
        self._max_workers = max_workers
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """启动任务队列"""
        if self._running:
            return
        self._queue = asyncio.PriorityQueue()
        self._running = True
        self._worker_tasks = [asyncio.create_task(self._worker(f"worker-{i}")) for i in range(self._max_workers)]
        logger.info(f"任务队列已启动 (workers={self._max_workers})")

    async def stop(self) -> None:
        """停止任务队列并清理 worker 协程"""
        self._running = False
        # 取消所有 worker 协程以避免事件循环关闭后报错
        for wt in self._worker_tasks:
            wt.cancel()
        # 等待所有 worker 结束（忽略 CancelledError）
        for wt in self._worker_tasks:
            try:
                await wt
            except (asyncio.CancelledError, Exception):
                pass
        self._worker_tasks.clear()
        logger.info("任务队列已停止")

    async def submit(
        self,
        func: Callable,
        *args: Any,
        name: Optional[str] = None,
        priority: int = TaskPriority.NORMAL,
        **kwargs: Any,
    ) -> str:
        """
        提交任务

        Args:
            func: 待执行的函数
            name: 任务名
            priority: 优先级（TaskPriority.HIGH/NORMAL/LOW）

        Returns:
            任务ID
        """
        task = Task(func, args, kwargs, name=name, priority=priority)
        self._tasks[task.id] = task

        # 队列未启动时自动启动 worker（自愈：应用未显式调用 start() 也能执行任务）
        if self._queue is None:
            await self.start()

        if self._queue is not None:
            await self._queue.put(task)

        logger.info(f"提交任务: {task.name} (id={task.id}, priority={priority})")
        return task.id

    def update_progress(self, task_id: str, current: int, total: int, message: str = "") -> bool:
        """更新任务进度"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.progress.current = current
        task.progress.total = total
        task.progress.message = message
        task.progress.updated_at = time.time()
        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        cancelled = task.cancel()
        if cancelled:
            logger.info(f"任务已取消: {task.name} (id={task_id})")
        return cancelled

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict]:
        """获取任务列表"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        all_tasks = list(self._tasks.values())
        return {
            "total": len(all_tasks),
            "pending": sum(1 for t in all_tasks if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in all_tasks if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in all_tasks if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in all_tasks if t.status == TaskStatus.CANCELLED),
            "max_workers": self._max_workers,
            "is_running": self._running,
        }

    def cleanup(self, max_age: float = 3600) -> int:
        """清理已完成的旧任务（默认1小时前的）"""
        cutoff = time.time() - max_age
        to_remove = [
            tid
            for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            and t.completed_at
            and t.completed_at < cutoff
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)

    async def _worker(self, name: str) -> None:
        """工作协程"""
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

            # 检查任务是否已被取消
            if task.is_cancelled:
                continue

            task.status = TaskStatus.RUNNING
            task.started_at = time.time()

            try:
                if asyncio.iscoroutinefunction(task.func):
                    task.result = await task.func(*task.args, **task.kwargs)
                else:
                    task.result = await loop.run_in_executor(None, lambda: task.func(*task.args, **task.kwargs))

                # 执行完再次检查取消状态
                if not task.is_cancelled:
                    task.status = TaskStatus.COMPLETED
            except Exception as e:
                if not task.is_cancelled:
                    task.error = str(e)
                    task.status = TaskStatus.FAILED
                    logger.error(f"任务 {task.name} 失败: {e}")
            finally:
                task.completed_at = time.time()


# 全局任务队列实例
task_queue = LocalTaskQueue()


class TaskQueue:
    """向后兼容包装器 - 代理到 LocalTaskQueue"""

    def __init__(self, db: Session = None):
        self.db = db
        self._queue = task_queue

    async def submit_task(self, func, *args, name: Optional[str] = None, priority: int = 5, **kwargs):
        return await self._queue.submit(func, *args, name=name, priority=priority, **kwargs)

    def get_status(self, task_id: str):
        return self._queue.get_task(task_id)

    @staticmethod
    def create(db: Session = None) -> "TaskQueue":
        return TaskQueue(db)
