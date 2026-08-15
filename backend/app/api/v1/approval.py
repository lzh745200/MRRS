"""
审批流程API端点

Task 5.7: 实现审批API端点

Endpoints:
- POST /api / v1 / approval / workflows - 创建审批流程
- GET /api / v1 / approval / workflows - 获取审批流程列表
- GET /api / v1 / approval / workflows/{id} - 获取审批流程详情
- PUT /api / v1 / approval / workflows/{id} - 更新审批流程
- DELETE /api / v1 / approval / workflows/{id} - 删除审批流程
- POST /api / v1 / approval / submit - 提交审批
- POST /api / v1 / approval / tasks/{id}/approve - 审批通过
- POST /api / v1 / approval / tasks/{id}/reject - 审批拒绝
- POST /api / v1 / approval / tasks/{id}/transfer - 转交审批
- POST /api / v1 / approval / tasks/{id}/withdraw - 撤回申请
- GET /api / v1 / approval / tasks / pending - 待审批列表
- POST /api / v1 / approval / tasks / batch - 批量审批
- GET /api / v1 / approval / tasks/{id}/diff - 变更对比
- GET /api / v1 / approval / history - 审批历史

Requirements: 3.2, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.3, 4.6
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import is_admin, require_admin
from app.core.response import success_response
from app.core.security import get_current_user
from app.models.message import Message
from app.models.user import User
from app.services.approval_workflow_service import ApprovalWorkflowService
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approval", tags=["审批管理"])


def _notify_submitter(db: Session, task, title: str, content: str) -> None:
    """审批结果通知申请人（提交人≠审批人时同样通知；消息落库失败不阻断审批）"""
    try:
        submitter_id = getattr(task, "submitter_id", None)
        if not submitter_id:
            return
        msg = Message(
            user_id=submitter_id,
            message_type="approval",
            title=title,
            content=content,
            is_read=False,
        )
        db.add(msg)
        safe_commit(db)
    except Exception:  # pragma: no cover - 通知失败不阻断业务
        db.rollback()
        logger.warning("审批结果通知写入失败（非致命）", exc_info=True)


@router.get("")
async def approval_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审批管理模块概览统计（pending/approved/rejected/total/my_pending）

    数据权限：管理员看全局统计；普通用户仅统计与自己相关（提交或待自己审批）的任务。
    """
    from sqlalchemy import func, or_

    from app.models.approval import ApprovalStatus as AS
    from app.models.approval import ApprovalTask as AT

    def _scoped(query):
        """非管理员限定为「提交人=自己 OR 审批人=自己」"""
        if not is_admin(current_user):
            return query.filter(
                or_(
                    AT.submitter_id == current_user.id,
                    AT.current_approver_id == current_user.id,
                )
            )
        return query

    total = _scoped(db.query(func.count(AT.id))).scalar() or 0
    pending = (
        _scoped(db.query(func.count(AT.id)))
        .filter(AT.status == AS.PENDING.value)
        .scalar()
        or 0
    )
    approved = (
        _scoped(db.query(func.count(AT.id)))
        .filter(AT.status == AS.APPROVED.value)
        .scalar()
        or 0
    )
    rejected = (
        _scoped(db.query(func.count(AT.id)))
        .filter(AT.status == AS.REJECTED.value)
        .scalar()
        or 0
    )
    my_pending = (
        db.query(func.count(AT.id))
        .filter(
            AT.status == AS.PENDING.value,
            AT.current_approver_id == current_user.id,
        )
        .scalar()
        or 0
    )
    if my_pending == 0 and not is_admin(current_user):
        my_pending = (
            db.query(func.count(AT.id))
            .filter(
                AT.status == AS.PENDING.value,
                AT.submitter_id == current_user.id,
            )
            .scalar()
            or 0
        )
    return success_response(
        message="审批管理模块概览",
        data={
            "pending_count": pending,
            "approved_count": approved,
            "rejected_count": rejected,
            "total_count": total,
            "my_pending": my_pending,
        },
    )


# ==================== Schemas ====================


class ApprovalNodeCreate(BaseModel):
    """审批节点创建模型"""

    name: str = Field(..., description="节点名称")
    approver_type: str = Field(default="user", description="审批人类型: user / role")
    approver_id: Optional[int] = Field(None, description="审批人ID或角色ID")
    timeout_hours: int = Field(default=24, description="超时时间(小时)")


class WorkflowCreate(BaseModel):
    """审批流程创建模型"""

    name: str = Field(..., description="流程名称")
    entity_type: str = Field(..., description="实体类型")
    description: Optional[str] = Field(None, description="流程描述")
    nodes: List[ApprovalNodeCreate] = Field(default=[], description="审批节点列表")


class WorkflowUpdate(BaseModel):
    """审批流程更新模型"""

    name: Optional[str] = Field(None, description="流程名称")
    description: Optional[str] = Field(None, description="流程描述")
    is_active: Optional[bool] = Field(None, description="是否启用")
    nodes: Optional[List[ApprovalNodeCreate]] = Field(None, description="审批节点列表")


class SubmitApprovalRequest(BaseModel):
    """提交审批请求"""

    entity_type: str = Field(..., description="实体类型")
    entity_id: int = Field(..., description="实体ID")
    change_data: Dict[str, Any] = Field(..., description="变更后的数据")
    original_data: Optional[Dict[str, Any]] = Field(None, description="变更前的数据")
    title: Optional[str] = Field(None, description="审批标题")
    description: Optional[str] = Field(None, description="审批说明")
    priority: int = Field(default=0, description="优先级")


class ApprovalActionRequest(BaseModel):
    """审批操作请求"""

    opinion: Optional[str] = Field(None, description="审批意见")


class TransferRequest(BaseModel):
    """转交请求"""

    transfer_to_id: int = Field(..., description="转交目标用户ID")
    reason: Optional[str] = Field(None, description="转交原因")


class BatchApproveRequest(BaseModel):
    """批量审批请求"""

    task_ids: List[int] = Field(..., description="任务ID列表")
    opinion: Optional[str] = Field(None, description="审批意见")


# ==================== Workflow Endpoints ====================


@router.post("/workflows", summary="创建审批流程")
def create_workflow(
    data: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建审批流程

    Requirements: 3.1 - 支持配置多级审批流程（最多支持5级）
    """
    service = ApprovalWorkflowService(db)

    try:
        nodes = [node.model_dump() for node in data.nodes]
        workflow = service.create_workflow(
            name=data.name,
            entity_type=data.entity_type,
            description=data.description,
            nodes=nodes,
            created_by=current_user.id,
        )
        return {
            "code": 200,
            "success": True,
            "message": "创建成功",
            "data": {
                "id": workflow.id,
                "name": workflow.name,
                "entity_type": workflow.entity_type,
                "level_count": len(nodes),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflows", summary="获取审批流程列表")
def list_workflows(
    entity_type: Optional[str] = Query(None, description="实体类型"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审批流程列表"""
    service = ApprovalWorkflowService(db)
    workflows = service.list_workflows(entity_type=entity_type, is_active=is_active, skip=skip, limit=limit)
    if not is_admin(current_user):
        workflows = [w for w in workflows if w.created_by == current_user.id]
    return {
        "code": 200,
        "success": True,
        "data": [
            {
                "id": w.id,
                "name": w.name,
                "entity_type": w.entity_type,
                "description": w.description,
                "is_active": w.is_active,
                "level_count": w.level_count,
            }
            for w in workflows
        ],
    }


@router.get("/workflows/{workflow_id}", summary="获取审批流程详情")
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审批流程详情"""
    service = ApprovalWorkflowService(db)
    workflow = service.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="审批流程不存在")

    return {
        "code": 200,
        "success": True,
        "data": {
            "id": workflow.id,
            "name": workflow.name,
            "entity_type": workflow.entity_type,
            "description": workflow.description,
            "is_active": workflow.is_active,
            "nodes": [
                {
                    "id": n.id,
                    "level": n.level,
                    "name": n.name,
                    "approver_type": n.approver_type,
                    "approver_id": n.approver_id,
                    "timeout_hours": n.timeout_hours,
                }
                for n in workflow.nodes
            ],
        },
    }


@router.put("/workflows/{workflow_id}", summary="更新审批流程")
def update_workflow(
    workflow_id: int,
    data: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审批流程"""
    service = ApprovalWorkflowService(db)

    try:
        workflow = service.update_workflow(
            workflow_id=workflow_id,
            name=data.name,
            description=data.description,
            is_active=data.is_active,
        )

        if not workflow:
            raise HTTPException(status_code=404, detail="审批流程不存在")

        return {"code": 200, "success": True, "message": "更新成功", "data": {"id": workflow.id}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/workflows/{workflow_id}", summary="删除审批流程")
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除审批流程"""
    service = ApprovalWorkflowService(db)
    success = service.delete_workflow(workflow_id)

    if not success:
        raise HTTPException(status_code=404, detail="审批流程不存在")

    return {"code": 200, "success": True, "message": "删除成功"}


# ==================== Task Endpoints ====================


@router.post("/submit", summary="提交审批")
def submit_approval(
    data: SubmitApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交审批申请

    Requirements: 3.2 - 数据变更自动创建审批任务
    """
    service = ApprovalWorkflowService(db)
    task = service.submit_approval(
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        submitter_id=current_user.id,
        change_data=data.change_data,
        original_data=data.original_data,
        title=data.title,
    )

    if not task:
        raise HTTPException(status_code=400, detail="无法创建审批任务，请检查是否存在对应的审批流程")

    return {
        "code": 200,
        "success": True,
        "message": "提交成功",
        "data": {
            "task_id": task.id,
            "status": task.status,
            "current_level": task.current_level,
        },
    }


@router.post("/tasks/{task_id}/approve", summary="审批通过")
def approve_task(
    task_id: int,
    data: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    审批通过

    Requirements:
    - 3.4: 记录审批意见和审批时间
    - 3.6: 审批通过后执行数据变更

    单机版优化：允许当前用户直接审批（跳过审批人校验）
    """
    service = ApprovalWorkflowService(db)
    task = service.approve_task(task_id, current_user.id, data.opinion)

    if not task:
        raise HTTPException(status_code=403, detail="无权限审批此任务或任务不存在")

    _notify_submitter(db, task, "审批通过", f"您提交的「{task.title or task.entity_type}」已审批通过。"
                      + (f"审批意见：{data.opinion}" if data.opinion else ""))

    return {
        "code": 200,
        "success": True,
        "message": "审批通过",
        "data": {
            "task_id": task.id,
            "status": task.status,
            "current_level": task.current_level,
        },
    }


@router.post("/tasks/{task_id}/reject", summary="审批拒绝")
def reject_task(
    task_id: int,
    data: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    审批拒绝

    Requirements: 3.5 - 审批拒绝后终止流程

    单机版优化：允许当前用户直接拒绝（跳过审批人校验）
    安全要求：驳回必须填写原因（与前端必填校验对齐，防止绕过前端空原因驳回）
    """
    if not data.opinion or not data.opinion.strip():
        raise HTTPException(status_code=400, detail="驳回必须填写原因")
    service = ApprovalWorkflowService(db)
    task = service.reject_task(task_id, current_user.id, data.opinion)

    if not task:
        raise HTTPException(status_code=403, detail="无权限拒绝此任务或任务不存在")

    _notify_submitter(db, task, "审批驳回", f"您提交的「{task.title or task.entity_type}」已被驳回。驳回原因：{data.opinion}")

    return {
        "code": 200,
        "success": True,
        "message": "已拒绝",
        "data": {"task_id": task.id, "status": task.status},
    }


@router.post("/tasks/{task_id}/transfer", summary="转交审批")
def transfer_task(
    task_id: int,
    data: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    转交审批

    Requirements: 3.7 - 支持审批转交
    管理员可代为转交任意待审批任务；普通用户仅能转交指派给自己（或未分配）的任务。
    """
    service = ApprovalWorkflowService(db)
    task = service.transfer_task(
        task_id,
        current_user.id,
        data.transfer_to_id,
        data.reason,
        standalone=is_admin(current_user),
    )

    if not task:
        raise HTTPException(status_code=400, detail="无法转交该任务，请检查任务状态或目标用户")

    return {
        "code": 200,
        "success": True,
        "message": "转交成功",
        "data": {"task_id": task.id, "current_approver_id": task.current_approver_id},
    }


@router.post("/tasks/{task_id}/withdraw", summary="撤回申请")
def withdraw_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    撤回申请

    Requirements: 3.8 - 支持撤回申请
    """
    service = ApprovalWorkflowService(db)
    task = service.withdraw_task(task_id, current_user.id)

    if not task:
        raise HTTPException(status_code=400, detail="无法撤回该任务，请检查任务状态或提交人权限")

    return {
        "code": 200,
        "success": True,
        "message": "撤回成功",
        "data": {"task_id": task.id, "status": task.status},
    }


class ResubmitRequest(BaseModel):
    """重新提交请求（可选携带更新后的变更数据）"""

    change_data: Optional[Dict[str, Any]] = Field(None, description="更新后的变更数据")


@router.post("/tasks/{task_id}/resubmit", summary="重新提交审批")
def resubmit_task(
    task_id: int,
    data: Optional[ResubmitRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    驳回后重新提交审批（可携带更新后的变更数据）

    Requirements: 3.8 - 支持驳回后重新提交
    """
    service = ApprovalWorkflowService(db)
    change_data = data.change_data if data else None
    task = service.resubmit_approval(task_id, current_user.id, change_data=change_data)

    if not task:
        raise HTTPException(status_code=400, detail="无法重新提交，请检查任务状态或提交人权限")

    return {
        "code": 200,
        "success": True,
        "message": "已重新提交",
        "data": {"task_id": task.id, "status": task.status},
    }


# ==================== 单机版优化接口 ====================


class AutoApproveRequest(BaseModel):
    """自动审批请求"""

    opinion: Optional[str] = Field(None, description="审批意见")


class SubmitAutoApproveRequest(BaseModel):
    """提交并自动审批请求"""

    entity_type: str = Field(..., description="实体类型")
    entity_id: int = Field(..., description="实体ID")
    change_data: Dict[str, Any] = Field(..., description="变更后的数据")
    original_data: Optional[Dict[str, Any]] = Field(None, description="变更前的数据")
    title: Optional[str] = Field(None, description="审批标题")
    description: Optional[str] = Field(None, description="审批说明")
    opinion: Optional[str] = Field(None, description="审批意见")


@router.post("/submit-auto", summary="提交并自动审批（单机版）")
def submit_and_auto_approve(
    data: SubmitAutoApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交审批并自动通过

    单机版优化：一键提交并自动完成审批，无需等待其他用户审批。
    自动创建默认审批流程（如果不存在）。
    """

    require_admin(current_user, error_message="仅管理员可执行自动审批")
    service = ApprovalWorkflowService(db)
    task = service.submit_and_auto_approve(
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        submitter_id=current_user.id,
        change_data=data.change_data,
        original_data=data.original_data,
    )

    if not task:
        raise HTTPException(status_code=400, detail="自动审批失败")

    return {
        "code": 200,
        "success": True,
        "message": "提交并自动审批通过",
        "data": {"task_id": task.id, "status": task.status},
    }


@router.post("/tasks/{task_id}/auto-approve", summary="单机版快速审批")
def auto_approve_single_task(
    task_id: int,
    data: AutoApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    单机版快速审批单个任务

    跳过审批人校验，直接通过所有审批级别。
    """

    require_admin(current_user, error_message="仅管理员可执行自动审批")
    service = ApprovalWorkflowService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="仅待审批任务可执行此操作")

    opinion = data.opinion or "单机版快速审批通过"
    while task and task.status == "pending":
        task = service.approve_task(task.id, current_user.id, opinion, standalone=True)

    if not task:
        raise HTTPException(status_code=400, detail="审批失败")

    return {
        "code": 200,
        "success": True,
        "message": "审批通过",
        "data": {"task_id": task.id, "status": task.status},
    }


@router.post("/tasks/auto-approve-all", summary="一键审批所有待处理任务（单机版）")
def auto_approve_all(
    data: AutoApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    一键审批所有待处理任务

    单机版优化：遍历所有 pending 状态的审批任务并全部通过。
    """
    require_admin(current_user, error_message="仅管理员可执行自动审批")
    service = ApprovalWorkflowService(db)
    results = service.auto_approve_all_pending(current_user.id)

    return {
        "code": 200,
        "success": True,
        "message": f"批量审批完成: 共 {results['total_pending']} 条待审批, 成功 {results['approved']} 条",
        "data": results,
    }


@router.get("/tasks/all", summary="所有审批任务(管理员)")
def get_all_tasks(
    status: Optional[str] = Query(None, description="状态: pending/approved/rejected/withdrawn"),
    entity_type: Optional[str] = Query(None, description="实体类型"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    管理员获取所有审批任务（含分页 total）

    Requirements: 4.1 - 管理员审批总览
    """
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    service = ApprovalWorkflowService(db)
    result = service.get_all_tasks_with_count(status=status, entity_type=entity_type, skip=skip, limit=limit)
    tasks = result["items"]
    total = result["total"]

    return {
        "code": 200,
        "success": True,
        "total": total,
        "data": [
            {
                "id": t.id,
                "title": t.title,
                "entity_type": t.entity_type,
                "entity_id": t.entity_id,
                "status": t.status,
                "current_level": t.current_level,
                "priority": t.priority,
                "submitter_id": t.submitter_id,
                "applicant_name": t.submitter.username if t.submitter else None,
                "type": t.entity_type,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "reviewer_name": (t.current_approver.username if t.current_approver else None),
                "reviewed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/tasks/pending", summary="待审批列表")
def get_pending_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取待审批任务列表

    Requirements: 4.1 - 待审批任务列表（按优先级和时间排序）

    单机版优化：
    - 管理员返回所有 pending 任务（不仅限当前用户为审批人的任务）
    - 普通用户返回「分配给自己 OR 自己提交」的 pending 任务
    - 附带变更数据摘要（change_data），供前端展示经费等业务实体信息
    """
    service = ApprovalWorkflowService(db)
    include_all = is_admin(current_user)
    tasks = service.get_pending_tasks(current_user.id, skip, limit, include_all=include_all)

    # 单机版兜底：服务返回空时（如审批人未分配），管理员仍能看到所有 pending 任务
    if not tasks:
        from app.models.approval import ApprovalStatus as AS
        from app.models.approval import ApprovalTask as AT

        query = db.query(AT).filter(AT.status == AS.PENDING.value)
        if not include_all:
            from sqlalchemy import or_

            query = query.filter(
                or_(AT.current_approver_id == current_user.id, AT.submitter_id == current_user.id)
            )
        tasks = query.order_by(AT.priority.desc(), AT.created_at.asc()).offset(skip).limit(limit).all()

    # 总数（用于前端分页；服务 mocked 时回退为当前页长度）
    try:
        total_value = service.count_pending_tasks(current_user.id, include_all=include_all)
        # MagicMock 的 __int__ 默认返回 1，必须用 isinstance 校验真实类型
        total = total_value if isinstance(total_value, int) and not isinstance(total_value, bool) else len(tasks)
    except (TypeError, ValueError, AttributeError):
        total = len(tasks)

    # 提交人姓名映射（前端列表「提交人」列）
    submitter_ids = {t.submitter_id for t in tasks if getattr(t, "submitter_id", None)}
    name_map = (
        dict(db.query(User.id, User.username).filter(User.id.in_(submitter_ids)).all())
        if submitter_ids
        else {}
    )

    def _safe_change_data(t) -> Optional[dict]:
        cd = getattr(t, "change_data", None)
        return cd if isinstance(cd, dict) else None

    return {
        "code": 200,
        "success": True,
        "total": total,
        "data": [
            {
                "id": t.id,
                "title": t.title,
                "entity_type": t.entity_type,
                "entity_id": t.entity_id,
                "current_level": t.current_level,
                "priority": t.priority,
                "status": t.status,
                "submitter_id": t.submitter_id,
                "submitter_name": name_map.get(t.submitter_id),
                "created_at": t.created_at.isoformat() if t.created_at else None,
                # 变更数据摘要：让待审批板块直接展示经费/项目等业务信息
                "change_data": _safe_change_data(t),
            }
            for t in tasks
        ],
    }


@router.post("/tasks/batch", summary="批量审批")
def batch_approve(
    data: BatchApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    批量审批

    Requirements: 4.4 - 批量审批功能
    安全：非管理员仅能批量处理指派给自己的待审批任务（其余任务记入 failed）。
    """
    service = ApprovalWorkflowService(db)
    if not is_admin(current_user):
        from app.models.approval import ApprovalStatus as _AS
        from app.models.approval import ApprovalTask as _AT

        allowed_ids = {
            row[0]
            for row in db.query(_AT.id)
            .filter(
                _AT.id.in_(data.task_ids),
                _AT.current_approver_id == current_user.id,
                _AT.status == _AS.PENDING.value,
            )
            .all()
        }
        allowed = [tid for tid in data.task_ids if tid in allowed_ids]
        denied = [tid for tid in data.task_ids if tid not in allowed_ids]
        results = (
            service.batch_approve(allowed, current_user.id, data.opinion)
            if allowed
            else {"success": [], "failed": []}
        )
        for tid in denied:
            results["failed"].append({"id": tid, "reason": "无权限审批此任务"})
    else:
        results = service.batch_approve(data.task_ids, current_user.id, data.opinion)

    return {
        "code": 200,
        "success": True,
        "message": f"成功: {len(results['success'])}, 失败: {len(results['failed'])}",
        "data": results,
    }


# ==================== 任务列表序列化辅助 ====================


def _task_to_dict(t) -> Dict[str, Any]:
    """审批任务序列化（供 tasks/mine、tasks/history 等列表端点复用）"""
    change_data = getattr(t, "change_data", None)
    records = getattr(t, "records", None) or []
    opinion = None
    if records:
        last_record = records[-1] if records else None
        if last_record is not None:
            opinion = getattr(last_record, "opinion", None)
    return {
        "id": t.id,
        "title": t.title,
        "entity_type": t.entity_type,
        "entity_id": t.entity_id,
        "status": t.status,
        "current_level": t.current_level,
        "priority": t.priority,
        "submitter_id": t.submitter_id,
        "submitter_name": t.submitter.username if getattr(t, "submitter", None) else None,
        "current_approver_id": t.current_approver_id,
        "reviewer_name": (
            t.current_approver.username if getattr(t, "current_approver", None) else None
        ),
        "opinion": opinion,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "change_data": change_data if isinstance(change_data, dict) else None,
    }


@router.get("/tasks/mine", summary="我的申请列表")
def get_my_tasks(
    status: Optional[str] = Query(None, description="状态: pending/approved/rejected/withdrawn"),
    date_from: Optional[str] = Query(None, description="提交时间起始 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="提交时间截止 (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户提交的审批任务（我的申请页）"""
    service = ApprovalWorkflowService(db)
    result = service.get_tasks_with_count(
        submitter_id=current_user.id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "code": 200,
        "success": True,
        "total": result["total"],
        "data": [_task_to_dict(t) for t in result["items"]],
    }


@router.get("/tasks/history", summary="审批任务历史列表")
def get_task_history(
    entity_type: Optional[str] = Query(None, description="实体类型"),
    status: Optional[str] = Query(None, description="状态"),
    completed: Optional[bool] = Query(None, description="仅已办结(非pending)任务"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """审批任务历史（管理员可见全部；普通用户仅可见自己提交的任务）"""
    service = ApprovalWorkflowService(db)
    submitter_id = None if is_admin(current_user) else current_user.id
    result = service.get_tasks_with_count(
        entity_type=entity_type,
        status=status,
        submitter_id=submitter_id,
        completed=completed,
        skip=skip,
        limit=limit,
    )
    return {
        "code": 200,
        "success": True,
        "total": result["total"],
        "data": [_task_to_dict(t) for t in result["items"]],
    }


@router.get("/tasks/{task_id}/diff", summary="变更对比")
def get_task_diff(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取变更对比数据

    Requirements: 4.3 - 变更对比视图
    """
    service = ApprovalWorkflowService(db)
    diff = service.get_task_diff(task_id)

    if not diff:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {"code": 200, "success": True, "data": diff}


@router.post("/tasks/{task_id}/remind", summary="发送审批提醒")
def remind_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送审批超时提醒（创建站内消息）

    Requirements: 3.2 - 超时提醒机制
    """
    service = ApprovalWorkflowService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="仅待审批任务可发送提醒")
    if not task.current_approver_id:
        raise HTTPException(status_code=400, detail="该任务未分配审批人，无法发送提醒")

    # 防重复：检查 1 小时内是否已发送过同任务的提醒
    from datetime import timedelta
    recent = (
        db.query(Message)
        .filter(
            Message.user_id == task.current_approver_id,
            Message.title == f"审批提醒：{task.title}",
            Message.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
        )
        .first()
    )
    if recent:
        raise HTTPException(status_code=409, detail="一小时内已发送过提醒，请勿重复操作")

    # 创建站内消息
    try:
        msg = Message(
            user_id=task.current_approver_id,
            title=f"审批提醒：{task.title}",
            content=f"您有一条待审批任务【{task.title}】已超时，请尽快处理。",
            message_type="system",
            link=f"/approval/tasks/{task.id}",
            is_read=False,
        )
        db.add(msg)
        safe_commit(db)
    except Exception as e:
        db.rollback()
        logger.error(f"创建提醒消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提醒发送失败: {str(e)}")

    return {"code": 200, "success": True, "message": "提醒已发送"}


@router.get("/history", summary="审批历史")
def get_approval_history(
    entity_type: Optional[str] = Query(None, description="实体类型"),
    entity_id: Optional[int] = Query(None, description="实体ID"),
    submitter_id: Optional[int] = Query(None, description="提交人ID"),
    status: Optional[str] = Query(None, description="状态"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取审批历史

    Requirements: 4.6 - 审批历史查询
    """
    # 非管理员只能查看自己提交的历史
    if submitter_id is None and current_user.role not in ("admin", "super_admin"):
        submitter_id = current_user.id

    service = ApprovalWorkflowService(db)
    # 所有过滤在 DB 层执行，保证分页正确（不会因为 Python 过滤导致少返回记录）
    records = service.get_approval_history(
        entity_type=entity_type,
        entity_id=entity_id,
        submitter_id=submitter_id,
        status=status,
        skip=skip,
        limit=limit,
    )

    return {
        "code": 200,
        "success": True,
        "data": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "action": r.action,
                "opinion": r.opinion,
                "level": r.level,
                "approver": r.approver.username if r.approver else None,
                "title": t.title if (t := r.task) else None,
                "entity_type": t.entity_type if t else None,
                "entity_id": t.entity_id if t else None,
                "status": t.status if t else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
