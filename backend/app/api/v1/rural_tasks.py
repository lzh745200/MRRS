"""
乡村振兴工作任务 API 路由
"""

from datetime import timezone, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import is_admin
from app.core.security import get_current_user
from app.core.transaction import safe_commit
from app.interfaces.schemas.responses import ResponseModel
from app.models.rural_task import RuralTask, TaskStatus
from app.models.rural_work import RuralWork
from app.schemas.rural_task import (
    RuralTaskCreate,
    RuralTaskListResponse,
    RuralTaskStatistics,
    RuralTaskUpdate,
    TaskApproveRequest,
    TaskSubmitRequest,
)

router = APIRouter(prefix="/rural-tasks", tags=["乡村工作任务"])


def _task_to_response(task: RuralTask) -> dict:
    """将 ORM 对象转为响应字典"""
    d = task.to_dict()
    # 关联名称
    d["village_name"] = task.village.name if task.village else None
    d["rural_work_name"] = task.rural_work.name if task.rural_work else None
    return d


def _generate_code(db: Session, year: int) -> str:
    """生成任务编号 TASK-YYYY-NNN"""
    prefix = f"TASK-{year}-"
    # 使用 startswith() 方法查找以指定前缀开头的记录
    last = db.query(RuralTask).filter(RuralTask.code.startswith(prefix)).order_by(RuralTask.id.desc()).first()
    if last and last.code:
        try:
            num = int(last.code.replace(prefix, "")) + 1
        except ValueError:
            num = 1
    else:
        num = 1
    return f"{prefix}{num:03d}"


def _get_task_or_403(task_id: int, current_user, db: Session) -> RuralTask:
    """按 ID 取任务并校验属主。

    列表端点对非管理员按 created_by 过滤，详情/写操作必须做同样的
    属主校验，否则任意登录用户可读/改/删他人任务（IDOR）。
    """
    task = db.query(RuralTask).filter(RuralTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not is_admin(current_user) and task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return task


# ---------- CRUD ----------


@router.get("", response_model=RuralTaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    rural_work_id: Optional[int] = Query(None, description="关联工作ID"),
    status: Optional[str] = Query(None, description="状态筛选"),
    category: Optional[str] = Query(None, description="分类筛选"),
    year: Optional[int] = Query(None, description="年度筛选"),
    village_id: Optional[int] = Query(None, description="帮扶村ID"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    order_by: str = Query("created_at", description="排序字段"),
    order_desc: bool = Query(True, description="是否降序"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取任务列表"""
    query = db.query(RuralTask)
    if not is_admin(current_user):
        query = query.filter(RuralTask.created_by == current_user.id)

    if rural_work_id:
        query = query.filter(RuralTask.rural_work_id == rural_work_id)
    if status:
        query = query.filter(RuralTask.status == status)
    if category:
        query = query.filter(RuralTask.category == category)
    if year:
        query = query.filter(RuralTask.year == year)
    if village_id:
        query = query.filter(RuralTask.village_id == village_id)
    if search:
        query = query.filter(RuralTask.title.contains(search))

    total = query.count()

    # 排序
    sort_col = getattr(RuralTask, order_by, RuralTask.created_at)
    query = query.order_by(sort_col.desc() if order_desc else sort_col.asc())

    tasks = query.offset(skip).limit(limit).all()
    items = [_task_to_response(t) for t in tasks]

    return RuralTaskListResponse(total=total, items=items, skip=skip, limit=limit)


@router.get("/statistics", response_model=ResponseModel)
async def get_statistics(
    year: Optional[int] = Query(None, description="年度"),
    rural_work_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取任务统计"""
    query = db.query(RuralTask)
    if not is_admin(current_user):
        query = query.filter(RuralTask.created_by == current_user.id)
    if year:
        query = query.filter(RuralTask.year == year)
    if rural_work_id:
        query = query.filter(RuralTask.rural_work_id == rural_work_id)

    all_tasks = query.all()
    total = len(all_tasks)
    status_counts = {}
    category_counts = {}
    total_budget = 0.0
    total_actual = 0.0

    for t in all_tasks:
        s = t.status.value if t.status else "draft"
        status_counts[s] = status_counts.get(s, 0) + 1
        c = t.category.value if t.category else "other"
        category_counts[c] = category_counts.get(c, 0) + 1
        total_budget += t.budget or 0
        total_actual += t.actual_cost or 0

    completed = status_counts.get("completed", 0)
    stats = RuralTaskStatistics(
        total=total,
        draft=status_counts.get("draft", 0),
        pending_approval=status_counts.get("pending_approval", 0),
        in_progress=status_counts.get("in_progress", 0),
        completed=completed,
        rejected=status_counts.get("rejected", 0),
        by_category=category_counts,
        total_budget=round(total_budget, 2),
        total_actual_cost=round(total_actual, 2),
        completion_rate=round(completed / total * 100, 1) if total > 0 else 0,
    )
    return ResponseModel(code=200, data=stats.model_dump(), message="success")


@router.get("/{task_id}", response_model=ResponseModel)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取任务详情"""
    task = _get_task_or_403(task_id, current_user, db)
    return ResponseModel(code=200, data=_task_to_response(task), message="success")


@router.post("", response_model=ResponseModel)
async def create_task(
    data: RuralTaskCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """创建任务"""
    # 校验关联工作存在
    work = db.query(RuralWork).filter(RuralWork.id == data.rural_work_id).first()
    if not work:
        raise HTTPException(status_code=404, detail="关联的乡村工作不存在")

    year = data.year or datetime.now().year
    code = _generate_code(db, year)

    task = RuralTask(
        rural_work_id=data.rural_work_id,
        title=data.title,
        code=code,
        category=data.category,
        priority=data.priority,
        year=year,
        quarter=data.quarter,
        description=data.description,
        target=data.target,
        budget=data.budget or 0.0,
        responsible_unit=data.responsible_unit,
        responsible_person=data.responsible_person,
        contact_phone=data.contact_phone,
        planned_start=data.planned_start,
        planned_end=data.planned_end,
        village_id=data.village_id,
        status=TaskStatus.draft,
        created_by=current_user.id,
    )
    db.add(task)
    safe_commit(db)
    db.refresh(task)

    return ResponseModel(code=200, data=_task_to_response(task), message="创建成功")


@router.put("/{task_id}", response_model=ResponseModel)
async def update_task(
    task_id: int,
    data: RuralTaskUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新任务"""
    task = _get_task_or_403(task_id, current_user, db)

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(task, key, val)
    task.updated_by = current_user.id

    safe_commit(db)
    db.refresh(task)
    return ResponseModel(code=200, data=_task_to_response(task), message="更新成功")


@router.delete("/{task_id}", response_model=ResponseModel)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除任务"""
    task = _get_task_or_403(task_id, current_user, db)
    db.delete(task)
    safe_commit(db)
    return ResponseModel(code=200, message="删除成功")


# ---------- 审批流程 ----------


@router.post("/{task_id}/submit", response_model=ResponseModel)
async def submit_task(
    task_id: int,
    body: TaskSubmitRequest = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """提交任务审批"""
    task = _get_task_or_403(task_id, current_user, db)
    if task.status not in (TaskStatus.draft, TaskStatus.rejected):
        raise HTTPException(status_code=400, detail="仅草稿或被驳回的任务可提交")

    task.status = TaskStatus.pending_approval
    task.submitted_by = current_user.id
    task.submitted_at = datetime.now(timezone.utc)
    safe_commit(db)
    return ResponseModel(code=200, message="提交成功")


@router.post("/{task_id}/approve", response_model=ResponseModel)
async def approve_task(
    task_id: int,
    body: TaskApproveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """审批任务"""
    task = _get_task_or_403(task_id, current_user, db)
    if task.status != TaskStatus.pending_approval:
        raise HTTPException(status_code=400, detail="仅待审批的任务可审批")

    task.approved_by = current_user.id
    task.approved_at = datetime.now(timezone.utc)
    task.approval_comment = body.comment

    if body.approved:
        task.status = TaskStatus.approved
    else:
        task.status = TaskStatus.rejected

    safe_commit(db)
    action = "批准" if body.approved else "驳回"
    return ResponseModel(code=200, message=f"任务已{action}")


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_tasks(
    ids: List[int],
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """批量删除任务（非管理员仅能删除自己创建的任务）"""
    query = db.query(RuralTask).filter(RuralTask.id.in_(ids))
    if not is_admin(current_user):
        query = query.filter(RuralTask.created_by == current_user.id)
    deleted = query.delete(synchronize_session=False)
    safe_commit(db)
    return ResponseModel(code=200, data={"deleted": deleted}, message=f"成功删除{deleted}条记录")
