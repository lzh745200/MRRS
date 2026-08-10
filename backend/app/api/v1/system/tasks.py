"""
后台任务API
提供系统后台任务的状态查询、控制和监控功能
用于帮扶管理信息系统的异步任务管理
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["后台任务"])


# ==================== 枚举与模型 ====================

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """任务类型"""
    DATA_IMPORT = "data_import"
    DATA_EXPORT = "data_export"
    BACKUP = "backup"
    REPORT_GENERATION = "report_generation"
    DATA_SYNC = "data_sync"
    MAINTENANCE = "maintenance"
    OTHER = "other"


class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str
    task_type: str
    task_name: str
    status: str
    progress: float = 0.0
    message: str = ""
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: Optional[str] = None
    result: Optional[dict] = None


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    task_type: str = Field("other", description="任务类型")
    task_name: str = Field(..., description="任务名称")
    params: Optional[dict] = Field(None, description="任务参数")


# ==================== 内存任务存储 ====================

_tasks: Dict[str, dict] = {}


def _create_task_record(task_type: str, task_name: str, created_by: str = None, params: dict = None) -> dict:
    """创建任务记录"""
    task_id = str(uuid.uuid4())[:8]
    record = {
        "task_id": task_id,
        "task_type": task_type,
        "task_name": task_name,
        "status": TaskStatus.PENDING.value,
        "progress": 0.0,
        "message": "任务已创建，等待执行...",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "created_by": created_by,
        "params": params or {},
        "result": None,
    }
    _tasks[task_id] = record
    return record


# ==================== API 端点 ====================

@router.get("", summary="获取任务列表")
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选: pending/running/completed/failed"),
    task_type: Optional[str] = Query(None, description="按任务类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
):
    """获取所有后台任务的列表

    支持按状态和类型进行筛选，按创建时间倒序排列。
    """
    tasks = list(_tasks.values())

    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if task_type:
        tasks = [t for t in tasks if t["task_type"] == task_type]

    # 按创建时间倒序
    tasks.sort(key=lambda x: x["created_at"], reverse=True)

    total = len(tasks)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "success": True,
        "data": {
            "items": tasks[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/stats", summary="获取任务统计")
async def get_task_stats(current_user=Depends(get_current_user)):
    """获取后台任务的统计数据

    按状态和类型统计任务数量和占比。
    """
    tasks = list(_tasks.values())
    total = len(tasks)

    by_status = {}
    by_type = {}
    for t in tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        by_type[t["task_type"]] = by_type.get(t["task_type"], 0) + 1

    return {
        "success": True,
        "data": {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "active_count": len([t for t in tasks if t["status"] in ("pending", "running")]),
        },
    }


@router.get("/{task_id}", summary="获取任务详情")
async def get_task(
    task_id: str,
    current_user=Depends(get_current_user),
):
    """获取指定任务的详细信息和执行状态"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"success": True, "data": task}


@router.post("", summary="创建后台任务")
async def create_task(
    request: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """创建并启动一个后台任务

    任务将以异步方式在后台执行，可通过任务ID查询执行状态和结果。
    """
    created_by = getattr(current_user, "username", "system")
    record = _create_task_record(
        task_type=request.task_type,
        task_name=request.task_name,
        created_by=created_by,
        params=request.params,
    )

    # 模拟任务执行
    def _execute_task(task_id: str):
        import time

        task = _tasks.get(task_id)
        if not task:
            return

        task["status"] = TaskStatus.RUNNING.value
        task["started_at"] = datetime.now(timezone.utc).isoformat()
        task["message"] = "任务执行中..."

        try:
            # 模拟执行步骤
            for i in range(1, 6):
                time.sleep(0.5)
                task["progress"] = i * 20.0
                task["message"] = f"正在执行第 {i}/5 步..."

            task["status"] = TaskStatus.COMPLETED.value
            task["progress"] = 100.0
            task["message"] = "任务执行完成"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            task["result"] = {"success": True, "message": "任务执行成功"}
        except Exception as e:
            task["status"] = TaskStatus.FAILED.value
            task["message"] = f"任务执行失败: {str(e)}"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            task["result"] = {"success": False, "error": str(e)}

    background_tasks.add_task(_execute_task, record["task_id"])

    return {
        "success": True,
        "message": "任务已创建并开始执行",
        "data": {"task_id": record["task_id"]},
    }


@router.post("/{task_id}/cancel", summary="取消任务")
async def cancel_task(
    task_id: str,
    current_user=Depends(get_current_user),
):
    """取消指定的后台任务

    仅可取消状态为 pending 或 running 的任务。
    """
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] not in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
        raise HTTPException(status_code=400, detail=f"任务状态为 {task['status']}，无法取消")

    task["status"] = TaskStatus.CANCELLED.value
    task["message"] = "任务已被用户取消"
    task["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "任务 %s 已被用户 %s 取消",
        task_id,
        getattr(current_user, "username", "unknown"),
    )

    return {"success": True, "message": f"任务 {task_id} 已取消"}


@router.delete("/{task_id}", summary="删除任务记录")
async def delete_task(
    task_id: str,
    current_user=Depends(get_current_user),
):
    """删除指定的任务记录

    仅允许删除已完成、已失败或已取消的任务。
    """
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
        raise HTTPException(status_code=400, detail="不能删除正在执行或等待中的任务，请先取消")

    del _tasks[task_id]

    return {"success": True, "message": f"任务 {task_id} 已删除"}


@router.get("/running/count", summary="获取运行中任务数")
async def get_running_task_count():
    """获取当前正在运行中的任务数量"""
    running = [t for t in _tasks.values() if t["status"] == TaskStatus.RUNNING.value]
    pending = [t for t in _tasks.values() if t["status"] == TaskStatus.PENDING.value]

    return {
        "success": True,
        "data": {
            "running": len(running),
            "pending": len(pending),
            "total_active": len(running) + len(pending),
        },
    }
