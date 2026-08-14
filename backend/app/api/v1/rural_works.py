"""
乡村工作API路由
Rural Work API Routes
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.response import ok_list
from app.core.security import get_current_user
from app.interfaces.schemas.responses import ResponseModel
from app.models.user import User
from app.schemas.rural_work import (
    RuralWorkCreate,
    RuralWorkUpdate,
)
from app.services.approval_workflow_service import (
    ApprovalWorkflowService,
    submit_entity_change_approval,
)
from app.services.rural_work_service import RuralWorkService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rural-works", tags=["乡村工作"])


def _apply_rural_work_approval_result(db, task) -> None:
    """审批终态回写乡村工作（注册到 ApprovalWorkflowService）

    乡村工作无 pending 状态门，审批通过后无字段需回写；保留处理器接口便于后续扩展。
    """
    _ = (db, task)


ApprovalWorkflowService.register_entity_apply_handler("rural_work", _apply_rural_work_approval_result)


def _parse_query_date(val: Optional[str]) -> Optional[datetime]:
    """将查询参数中的日期字符串安全转换为 datetime"""
    if not val or not val.strip():
        return None
    val = val.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


@router.get("")
async def list_rural_works(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(10, ge=1, le=500, description="每页记录数"),
    status: Optional[str] = Query(None, description="状态筛选"),
    type: Optional[str] = Query(None, description="类型筛选"),
    village_id: Optional[int] = Query(None, description="村庄ID筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    start_date: Optional[str] = Query(None, description="开始日期筛选 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期筛选 (YYYY-MM-DD)"),
    year: Optional[int] = Query(None, description="年度筛选"),
    order_by: str = Query("created_at", description="排序字段"),
    order_desc: bool = Query(True, description="是否降序"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取乡村工作列表"""
    service = RuralWorkService(db)
    works, total = service.get_rural_works(
        skip=skip,
        limit=limit,
        status=status,
        type=type,
        village_id=village_id,
        search=search,
        start_date=_parse_query_date(start_date),
        end_date=_parse_query_date(end_date),
        year=year,
        order_by=order_by,
        order_desc=order_desc,
        current_user=current_user,
    )
    page = (skip // limit + 1) if limit > 0 else 1
    return ok_list(items=works, total=total, page=page, page_size=limit)


@router.get("/statistics/summary", response_model=ResponseModel)
async def get_statistics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取乡村工作统计数据"""
    service = RuralWorkService(db)
    stats = service.get_statistics(current_user=current_user)
    return ResponseModel(code=200, data=stats.model_dump(), message="success")


@router.get("/villages", response_model=ResponseModel)
async def get_villages_for_select(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取村庄列表（用于下拉选择）"""
    service = RuralWorkService(db)
    villages = service.get_villages_for_select(current_user=current_user)
    return ResponseModel(code=200, data=villages, message="success")


@router.get("/report/generate", response_model=ResponseModel)
async def generate_work_report(
    year: Optional[int] = Query(None, description="年度"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成工作报告汇总数据"""
    service = RuralWorkService(db)
    report = service.generate_work_report(
        year=year,
        start_date=_parse_query_date(start_date),
        end_date=_parse_query_date(end_date),
        current_user=current_user,
    )
    return ResponseModel(code=200, data=report, message="success")


@router.get("/years", response_model=ResponseModel)
async def get_available_years(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取可用年份列表"""
    service = RuralWorkService(db)
    years = service.get_available_years()
    return ResponseModel(code=200, data=years, message="success")


@router.get("/{work_id}", response_model=ResponseModel)
async def get_rural_work(
    work_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个乡村工作详情"""
    service = RuralWorkService(db)
    work = service.get_rural_work_by_id(work_id, current_user=current_user)
    if not work:
        raise NotFoundException("工作不存在")
    return ResponseModel(code=200, data=work, message="success")


@router.post("", response_model=ResponseModel)
async def create_rural_work(
    data: RuralWorkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建乡村工作"""
    service = RuralWorkService(db)
    work = service.create_rural_work(
        data, current_user.id,
        organization_id=getattr(current_user, "organization_id", None),
    )
    # 数据变更自动创建审批任务（Requirement 3.2）：乡村工作新增进入待审批板块
    work_id = work.get("id")
    approval_task_id = None
    if work_id:
        approval_task_id = submit_entity_change_approval(
            db,
            entity_type="rural_work",
            entity_id=work_id,
            submitter_id=current_user.id,
            title=f"乡村工作新增：{work.get('name') or f'#{work_id}'}",
            change_data=work,
        )
    work["approval_task_id"] = approval_task_id
    return ResponseModel(code=200, data=work, message="创建成功")


@router.put("/{work_id}", response_model=ResponseModel)
async def update_rural_work(
    work_id: int,
    data: RuralWorkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新乡村工作"""
    service = RuralWorkService(db)
    old = service.get_rural_work_by_id(work_id, current_user=current_user)
    work = service.update_rural_work(work_id, data, current_user.id, current_user=current_user)
    if not work:
        raise NotFoundException("工作不存在")
    # 数据变更自动创建审批任务：乡村工作修改进入待审批板块（含变更对比）
    approval_task_id = submit_entity_change_approval(
        db,
        entity_type="rural_work",
        entity_id=work_id,
        submitter_id=current_user.id,
        title=f"乡村工作变更：{work.get('name') or f'#{work_id}'}",
        change_data=work,
        original_data=old,
    )
    work["approval_task_id"] = approval_task_id
    return ResponseModel(code=200, data=work, message="更新成功")


@router.delete("/{work_id}", response_model=ResponseModel)
async def delete_rural_work(
    work_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除乡村工作"""
    service = RuralWorkService(db)
    old = service.get_rural_work_by_id(work_id, current_user=current_user)
    result = service.delete_rural_work(work_id, current_user.id, current_user=current_user)
    if not result:
        raise NotFoundException("工作不存在")
    # 数据变更自动创建审批任务：乡村工作删除进入待审批板块
    submit_entity_change_approval(
        db,
        entity_type="rural_work",
        entity_id=work_id,
        submitter_id=current_user.id,
        title=f"乡村工作删除：{(old or {}).get('name') or f'#{work_id}'}",
        change_data={"deleted": True, "name": (old or {}).get("name")},
        original_data=old,
    )
    return ResponseModel(code=200, message="删除成功")


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_rural_works(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量删除乡村工作

    前端发送 ``{"ids": [1, 2, 3]}``，此处兼容该格式。
    """
    ids: List[int] = payload.get("ids", []) if isinstance(payload, dict) else []
    if not ids:
        return ResponseModel(code=200, data={"deleted": 0}, message="无待删除记录")
    service = RuralWorkService(db)
    deleted = service.batch_delete(ids, current_user=current_user)

    # 批量记录工作日志
    try:
        from app.services.work_log_service import write_work_log

        write_work_log(
            db, "rural_work", "batch_delete", 0, f"批量删除{deleted}条",
            user_id=current_user.id,
            detail=f"批量删除乡村工作: ids={ids}",
        )
    except Exception:
        logger.debug("记录工作日志失败")

    # 数据变更自动创建审批任务：批量删除进入待审批板块（审计留痕）
    approval_task_id = submit_entity_change_approval(
        db,
        entity_type="rural_work",
        entity_id=0,
        submitter_id=current_user.id,
        title=f"乡村工作批量删除：{deleted} 条",
        change_data={"deleted": True, "deleted_count": deleted, "ids": ids},
    )

    return ResponseModel(
        code=200, data={"deleted": deleted, "approval_task_id": approval_task_id},
        message=f"成功删除{deleted}条记录",
    )
