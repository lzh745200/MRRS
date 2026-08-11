"""项目里程碑、变更记录与状态流转 API"""

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.response import ok_list, success_response
from app.models.project import Project
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log
from app.core.data_permission import filter_by_data_scope
from app.models.project_milestone import (
    TRANSITION_REQUIREMENTS,
    VALID_TRANSITIONS,
    ProjectChangeLog,
    ProjectMilestone,
    calculate_milestone_progress,
    validate_status_transition,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["项目里程碑"])


# ==================== Pydantic 模型 ====================


class MilestoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    planned_date: date
    responsible_person: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[int] = 0


class MilestoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    planned_date: Optional[date] = None
    actual_date: Optional[date] = None
    responsible_person: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = None
    sort_order: Optional[int] = None


class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    planned_date: date
    actual_date: Optional[date] = None
    responsible_person: Optional[str] = None
    status: str
    sort_order: int


class StatusTransitionRequest(BaseModel):
    new_status: str
    reason: Optional[str] = None
    # 用于满足准入条件的可选字段
    actual_start_date: Optional[str] = None
    actual_end_date: Optional[str] = None
    achievements: Optional[str] = None


class StatusTransitionResponse(BaseModel):
    valid: bool
    error: Optional[str] = None
    missing_fields: Optional[list] = None
    new_status: Optional[str] = None


class ChangeLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    change_type: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    operator: Optional[str] = None
    created_at: Optional[datetime] = None


class TransitionRulesResponse(BaseModel):
    current_status: str
    allowed_transitions: list
    requirements: dict


# ==================== 里程碑 API ====================


@router.get("/{project_id}/milestones", response_model=List[MilestoneResponse])
async def get_milestones(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取项目里程碑列表"""
    milestones = (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.sort_order, ProjectMilestone.planned_date)
        .all()
    )
    return milestones


@router.post("/{project_id}/milestones", response_model=MilestoneResponse)
async def create_milestone(
    project_id: int,
    data: MilestoneCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建项目里程碑"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    milestone = ProjectMilestone(project_id=project_id, **data.model_dump())
    db.add(milestone)
    safe_commit(db)
    db.refresh(milestone)
    write_work_log(db, "project", "create_milestone", milestone.id,
                   f"创建里程碑: {milestone.name}", user_id=current_user.id,
                   username=getattr(current_user, "username", ""))
    return milestone


@router.put("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: int,
    milestone_id: int,
    data: MilestoneUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新项目里程碑"""
    milestone = (
        db.query(ProjectMilestone)
        .filter(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == project_id,
        )
        .first()
    )
    if not milestone:
        raise HTTPException(status_code=404, detail="里程碑不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(milestone, key, value)

    # 如果标记为完成且未设置实际日期，自动填充
    if update_data.get("status") == "completed" and not milestone.actual_date:
        milestone.actual_date = date.today()

    safe_commit(db)
    db.refresh(milestone)
    write_work_log(db, "project", "update_milestone", milestone.id,
                   f"更新里程碑: {milestone.name}", user_id=current_user.id,
                   username=getattr(current_user, "username", ""), detail=str(update_data))

    # 自动更新项目进度
    _auto_update_project_progress(db, project_id)

    return milestone


@router.delete("/{project_id}/milestones/{milestone_id}")
async def delete_milestone(
    project_id: int,
    milestone_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除项目里程碑"""
    milestone = (
        db.query(ProjectMilestone)
        .filter(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == project_id,
        )
        .first()
    )
    if not milestone:
        raise HTTPException(status_code=404, detail="里程碑不存在")

    milestone_title = milestone.name
    db.delete(milestone)
    safe_commit(db)
    write_work_log(db, "project", "delete_milestone", milestone_id,
                   f"删除里程碑: {milestone_title}", user_id=current_user.id,
                   username=getattr(current_user, "username", ""))

    # 自动更新项目进度
    _auto_update_project_progress(db, project_id)

    return success_response(message="删除成功")


# ==================== 状态流转 API ====================


@router.get("/{project_id}/transition-rules", response_model=TransitionRulesResponse)
async def get_transition_rules(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取项目当前可用的状态流转规则"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    current = project.status or "draft"
    allowed = VALID_TRANSITIONS.get(current, [])

    # 构建每个目标状态的准入条件
    requirements = {}
    for target in allowed:
        key = (current, target)
        req = TRANSITION_REQUIREMENTS.get(key)
        if req:
            requirements[target] = req
        else:
            requirements[target] = {"required_fields": [], "description": "无额外要求"}

    return TransitionRulesResponse(
        current_status=current,
        allowed_transitions=allowed,
        requirements=requirements,
    )


@router.post("/{project_id}/transition", response_model=StatusTransitionResponse)
async def transition_status(
    project_id: int,
    data: StatusTransitionRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行项目状态流转"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    old_status = project.status or "draft"

    # 先把请求中携带的字段写入项目（用于满足准入条件校验）
    if data.actual_start_date:
        try:
            project.actual_start_date = date.fromisoformat(data.actual_start_date)
        except ValueError:
            logger.warning("Invalid actual_start_date format: %s", data.actual_start_date)
    if data.actual_end_date:
        try:
            project.actual_end_date = date.fromisoformat(data.actual_end_date)
        except ValueError:
            logger.warning("Invalid actual_end_date format: %s", data.actual_end_date)
    if data.achievements:
        project.achievements = data.achievements

    # 校验流转
    result = validate_status_transition(project, data.new_status)
    if not result["valid"]:
        # 回滚临时写入的字段
        db.rollback()
        return StatusTransitionResponse(
            valid=False,
            error=result["error"],
            missing_fields=result.get("missing_fields", []),
        )

    # 执行流转
    project.status = data.new_status
    db.flush()

    # 记录变更日志
    change_log = ProjectChangeLog(
        project_id=project_id,
        change_type="status",
        field_name="status",
        old_value=old_status,
        new_value=data.new_status,
        reason=data.reason,
        operator=getattr(current_user, "username", None) or getattr(current_user, "full_name", ""),
        operator_id=getattr(current_user, "id", None),
    )
    db.add(change_log)
    safe_commit(db)

    return StatusTransitionResponse(valid=True, new_status=data.new_status)


# ==================== 变更记录 API ====================


@router.get("/{project_id}/change-logs", response_model=List[ChangeLogResponse])
async def get_change_logs(
    project_id: int,
    change_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取项目变更记录

    数据隔离：验证用户是否有权访问该项目。
    """
    # 验证项目存在且用户有访问权限
    project_query = db.query(Project).filter(Project.id == project_id)
    project_query = filter_by_data_scope(project_query, Project, current_user, db=db)
    if not project_query.first():
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    query = db.query(ProjectChangeLog).filter(ProjectChangeLog.project_id == project_id)
    if change_type:
        query = query.filter(ProjectChangeLog.change_type == change_type)

    logs = query.order_by(ProjectChangeLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return logs


# ==================== 首页仪表板：即将到期里程碑 ====================


@router.get("/dashboard/upcoming-milestones")
async def get_upcoming_milestones(
    days: int = Query(7, ge=1, le=30, description="未来N天内到期"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取即将到期的里程碑（首页仪表板用）

    数据隔离：仅返回当前用户数据范围内的项目里程碑。
    """
    from datetime import timedelta

    today = date.today()
    deadline = today + timedelta(days=days)

    query = (
        db.query(ProjectMilestone)
        .join(Project, Project.id == ProjectMilestone.project_id)
        .filter(
            ProjectMilestone.status.in_(["pending", "in_progress"]),
            ProjectMilestone.planned_date <= deadline,
            ProjectMilestone.planned_date >= today,
            Project.status.notin_(["completed", "cancelled"]),
        )
    )
    # 应用数据范围过滤，确保非管理员只能看到自己组织范围内的项目里程碑
    query = filter_by_data_scope(query, Project, current_user, db=db)

    milestones = (
        query
        .order_by(ProjectMilestone.planned_date)
        .limit(20)
        .all()
    )

    # 批量获取项目名称（避免 N+1 查询，JOIN 已过滤，直接从关联加载）
    project_ids = list({m.project_id for m in milestones})
    projects_map = {p.id: p.name for p in db.query(Project.id, Project.name).filter(Project.id.in_(project_ids)).all()}

    result = []
    for m in milestones:
        remaining_days = (m.planned_date - today).days
        result.append(
            {
                "id": m.id,
                "project_id": m.project_id,
                "project_name": projects_map.get(m.project_id, ""),
                "milestone_name": m.name,
                "planned_date": m.planned_date.isoformat(),
                "responsible_person": m.responsible_person,
                "remaining_days": remaining_days,
                "is_overdue": remaining_days < 0,
                "status": m.status,
            }
        )

    return ok_list(result, len(result))


# ==================== 逾期里程碑检测 ====================


@router.get("/dashboard/overdue-milestones")
async def get_overdue_milestones(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取已逾期的里程碑

    数据隔离：仅返回当前用户数据范围内的项目里程碑。
    """
    today = date.today()

    query = (
        db.query(ProjectMilestone)
        .join(Project, Project.id == ProjectMilestone.project_id)
        .filter(
            ProjectMilestone.status.in_(["pending", "in_progress"]),
            ProjectMilestone.planned_date < today,
            Project.status.notin_(["completed", "cancelled"]),
        )
    )
    # 应用数据范围过滤
    query = filter_by_data_scope(query, Project, current_user, db=db)

    milestones = (
        query
        .order_by(ProjectMilestone.planned_date)
        .all()
    )

    # 批量获取项目名称（避免 N+1 查询）
    project_ids = list({m.project_id for m in milestones})
    projects_map = {p.id: p.name for p in db.query(Project.id, Project.name).filter(Project.id.in_(project_ids)).all()}

    result = []
    for m in milestones:
        overdue_days = (today - m.planned_date).days
        result.append(
            {
                "id": m.id,
                "project_id": m.project_id,
                "project_name": projects_map.get(m.project_id, ""),
                "milestone_name": m.name,
                "planned_date": m.planned_date.isoformat(),
                "responsible_person": m.responsible_person,
                "overdue_days": overdue_days,
            }
        )

    return ok_list(result, len(result))


# ==================== 内部工具函数 ====================


def _auto_update_project_progress(db: Session, project_id: int):
    """自动根据里程碑完成情况更新项目进度"""
    milestones = db.query(ProjectMilestone).filter(ProjectMilestone.project_id == project_id).all()
    if milestones:
        progress = calculate_milestone_progress(milestones)
        db.query(Project).filter(Project.id == project_id).update({"progress": progress})
        safe_commit(db)
