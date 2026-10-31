"""结对帮扶与走访台账 API

- 结对台账：增删改查 + 统计 + 软删（``include_deleted`` 仅管理员可见软删记录）；
- 走访记录：挂在结对下，独立软删；
- 数据域：列表/统计走 ``pairing_service`` 的查询基座（``filter_by_org_ids``），
  点查走 ``require_data_permission``（跨组织 403 / 不存在 404）。
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.v1.deps import build_viewable_because, enforce_admin_include_deleted
from app.core.data_permission import OrgScopeFilter, get_org_scope, require_data_permission
from app.core.database import get_db
from app.core.errors import AppError
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.core.transaction import safe_commit
from app.models.pairing import PairingRecord, VisitRecord
from app.services.pairing_service import (
    attach_partner_names,
    ensure_pairing_valid,
    normalize_partner_fields,
    pairing_base_query,
    pairing_stats,
    resolve_partner,
    visit_base_query,
)
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pairings", tags=["结对帮扶与走访台账"])


# ==================== 请求模型 ====================


class PairingCreate(BaseModel):
    subject_type: str = Field(..., description="帮扶主体类型: unit/branch/person")
    subject_name: str = Field(..., min_length=1, max_length=128)
    subject_user_id: Optional[int] = None
    partner_type: str = Field(..., description="帮扶对象类型: village/school/student")
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    student_name: Optional[str] = Field(default=None, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = Field(default="active", max_length=16)
    note: Optional[str] = Field(default=None, max_length=500)


class PairingUpdate(BaseModel):
    subject_type: Optional[str] = None
    subject_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    subject_user_id: Optional[int] = None
    partner_type: Optional[str] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    student_name: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    content: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(default=None, max_length=16)
    note: Optional[str] = Field(default=None, max_length=500)


class VisitAttachment(BaseModel):
    """走访照片/凭证附件（由通用 ``/files/upload`` 返回的元数据）。

    与捐赠物资台账（donation.AttachmentItem）同一形态：只存 url + 文件名，
    文件本体由 /files/upload 落盘，本表不重复实现上传。
    """

    url: str = Field(..., min_length=1, max_length=500)
    file_name: Optional[str] = Field(default=None, max_length=300)


class VisitCreate(BaseModel):
    visit_date: date
    visitors: str = Field(..., min_length=1, max_length=200)
    purpose: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    materials: Optional[str] = Field(default=None, max_length=200)
    attachments: Optional[list[VisitAttachment]] = None
    # W22（v1.14.0）：走访挂户（可选；关联后回写 households.last_visit_date）
    household_id: Optional[int] = None


class VisitUpdate(BaseModel):
    visit_date: Optional[date] = None
    visitors: Optional[str] = Field(default=None, min_length=1, max_length=200)
    purpose: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    materials: Optional[str] = Field(default=None, max_length=200)
    attachments: Optional[list[VisitAttachment]] = None
    household_id: Optional[int] = None


def _normalize_attachments(items) -> list[dict]:
    """统一附件存储形态（create 走全量 dump、update 走 exclude_unset，需归一）。"""
    return [
        {
            "url": a["url"] if isinstance(a, dict) else a.url,
            "file_name": a.get("file_name") if isinstance(a, dict) else a.file_name,
        }
        for a in items
    ]


# ==================== 内部工具 ====================


def _get_pairing_or_404(
    db: Session, pairing_id: int, current_user, error_message: str
) -> PairingRecord:
    pairing = db.query(PairingRecord).filter(PairingRecord.id == pairing_id).first()
    if not pairing:
        raise AppError.not_found("结对记录")
    require_data_permission(
        current_user,
        pairing.organization_id,
        pairing.created_by,
        db,
        error_message=error_message,
    )
    return pairing


def _get_visit_or_404(
    db: Session, pairing: PairingRecord, visit_id: int, current_user, error_message: str
) -> VisitRecord:
    visit = (
        db.query(VisitRecord)
        .filter(VisitRecord.id == visit_id, VisitRecord.pairing_id == pairing.id)
        .first()
    )
    if not visit:
        raise AppError.not_found("走访记录")
    require_data_permission(
        current_user,
        visit.organization_id,
        visit.created_by,
        db,
        error_message=error_message,
    )
    return visit


def _write_log(
    db: Session, action: str, entity_id: Optional[int], title: Optional[str], current_user, detail: Optional[str] = ""
) -> None:
    write_work_log(
        db,
        "pairing",
        action,
        entity_id,
        title,
        user_id=current_user.id,
        username=getattr(current_user, "username", "系统"),
        detail=detail,
    )


def _resolve_household(db: Session, household_id: Optional[int], pairing: PairingRecord, current_user):
    """校验并返回走访关联的一户一档（可空）；数据域必须与结对记录同组织。"""
    if household_id is None:
        return None
    from app.core.permission_utils import is_admin
    from app.models.household import Household

    household = (
        db.query(Household)
        .filter(Household.id == household_id, Household.is_active == True)  # noqa: E712
        .first()
    )
    if not household:
        raise AppError.not_found("关联的一户一档")
    if not is_admin(current_user) and household.organization_id not in (
        None,
        pairing.organization_id,
    ):
        raise AppError.forbidden("无权关联该户")
    return household


def _sync_household_last_visit(db: Session, household_id: Optional[int]) -> None:
    """按该户有效走访记录重算 last_visit_date（无记录则清空）。"""
    if household_id is None:
        return
    from app.models.household import Household

    latest = (
        db.query(func.max(VisitRecord.visit_date))
        .filter(
            VisitRecord.household_id == household_id,
            VisitRecord.is_active == True,  # noqa: E712
        )
        .scalar()
    )
    household = db.query(Household).filter(Household.id == household_id).first()
    if household:
        household.last_visit_date = latest
        safe_commit(db)


# ==================== 结对台账 ====================
@router.get("")
async def list_pairings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    subject_type: Optional[str] = None,
    partner_type: Optional[str] = None,
    partner_id: Optional[int] = None,
    status: Optional[str] = None,
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """结对台账列表（envelope；非管理员 include_deleted 静默降级）。"""
    query = pairing_base_query(db, data_scope, include_deleted=include_deleted)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                PairingRecord.subject_name.like(like),
                PairingRecord.title.like(like),
                PairingRecord.student_name.like(like),
            )
        )
    if subject_type:
        query = query.filter(PairingRecord.subject_type == subject_type)
    if partner_type:
        query = query.filter(PairingRecord.partner_type == partner_type)
    if partner_id:
        if partner_type == "village":
            query = query.filter(PairingRecord.village_id == partner_id)
        elif partner_type == "school":
            query = query.filter(PairingRecord.school_id == partner_id)
        else:
            query = query.filter(
                or_(
                    PairingRecord.village_id == partner_id,
                    PairingRecord.school_id == partner_id,
                )
            )
    if status:
        query = query.filter(PairingRecord.status == status)

    total = query.count()
    items = (
        query.order_by(PairingRecord.created_at.desc(), PairingRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    rows = attach_partner_names(db, [p.to_dict() for p in items])
    return ok_list(items=rows, total=total, page=page, page_size=page_size)


@router.get("/stats")
async def get_pairing_stats(
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """台账统计（数据域内口径）。"""
    return success_response(
        data=pairing_stats(db, data_scope, include_deleted=include_deleted), message="成功"
    )


@router.get("/{pairing_id}")
async def get_pairing(
    pairing_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """结对详情（含软删记录，管理员附带 viewableBecause 元数据）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权访问该结对记录")
    data = attach_partner_names(db, [pairing.to_dict()])[0]
    data["viewableBecause"] = build_viewable_because(current_user, pairing)
    return success_response(data=data, message="成功")


@router.post("")
async def create_pairing(
    data: PairingCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建结对记录。"""
    ensure_pairing_valid(
        subject_type=data.subject_type,
        partner_type=data.partner_type,
        village_id=data.village_id,
        school_id=data.school_id,
        student_name=data.student_name,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    resolve_partner(
        db,
        partner_type=data.partner_type,
        village_id=data.village_id,
        school_id=data.school_id,
        current_user=current_user,
    )
    payload = normalize_partner_fields(data.model_dump())
    payload["organization_id"] = getattr(current_user, "organization_id", None)
    payload["created_by"] = current_user.id

    pairing = PairingRecord(**payload)
    db.add(pairing)
    safe_commit(db)
    db.refresh(pairing)

    _write_log(db, "create", pairing.id, pairing.title, current_user)
    created = attach_partner_names(db, [pairing.to_dict()])[0]
    return success_response(data=created, message="创建成功")


@router.put("/{pairing_id}")
async def update_pairing(
    pairing_id: int,
    data: PairingUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新结对记录（部分更新；字段组合按合并后的完整值校验）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权编辑该结对记录")

    update_data = data.model_dump(exclude_unset=True)
    if "partner_type" in update_data:
        update_data = normalize_partner_fields(update_data)

    merged: dict[str, Any] = {
        "subject_type": update_data.get("subject_type", pairing.subject_type),
        "partner_type": update_data.get("partner_type", pairing.partner_type),
        "village_id": update_data.get("village_id", pairing.village_id),
        "school_id": update_data.get("school_id", pairing.school_id),
        "student_name": update_data.get("student_name", pairing.student_name),
        "status": update_data.get("status", pairing.status),
        "start_date": update_data.get("start_date", pairing.start_date),
        "end_date": update_data.get("end_date", pairing.end_date),
    }

    ensure_pairing_valid(**merged)
    if any(k in update_data for k in ("partner_type", "village_id", "school_id")):
        resolve_partner(
            db,
            partner_type=merged["partner_type"],
            village_id=merged["village_id"],
            school_id=merged["school_id"],
            current_user=current_user,
        )

    for key, value in update_data.items():
        setattr(pairing, key, value)
    safe_commit(db)
    db.refresh(pairing)

    _write_log(db, "update", pairing.id, pairing.title, current_user)
    updated = attach_partner_names(db, [pairing.to_dict()])[0]
    return success_response(data=updated, message="更新成功")


@router.delete("/{pairing_id}")
async def delete_pairing(
    pairing_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除结对记录（软删除；走访记录保留以维持历史）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权删除该结对记录")

    pairing.is_active = False
    pairing.deleted_at = datetime.now(timezone.utc)
    safe_commit(db)

    _write_log(db, "delete", pairing.id, pairing.title, current_user)
    return success_response(data={"id": pairing.id}, message="删除成功")


# ==================== 走访记录 ====================


@router.get("/{pairing_id}/visits")
async def list_visits(
    pairing_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """某结对下的走访记录列表（按走访日期倒序）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权访问该结对记录")

    query = visit_base_query(db, data_scope, include_deleted=include_deleted).filter(
        VisitRecord.pairing_id == pairing.id
    )
    total = query.count()
    items = (
        query.order_by(VisitRecord.visit_date.desc(), VisitRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok_list(
        items=[v.to_dict() for v in items], total=total, page=page, page_size=page_size
    )


@router.post("/{pairing_id}/visits")
async def create_visit(
    pairing_id: int,
    data: VisitCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登记走访记录（组织域继承结对记录，保证与主表同域）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权登记该结对记录的走访")
    household = _resolve_household(db, data.household_id, pairing, current_user)

    visit = VisitRecord(
        pairing_id=pairing.id,
        visit_date=data.visit_date,
        visitors=data.visitors,
        purpose=data.purpose,
        content=data.content,
        materials=data.materials,
        attachments=(
            _normalize_attachments(data.attachments) if data.attachments is not None else None
        ),
        household_id=household.id if household else None,
        organization_id=pairing.organization_id,
        created_by=current_user.id,
    )
    db.add(visit)
    safe_commit(db)
    db.refresh(visit)
    _sync_household_last_visit(db, visit.household_id)

    _write_log(db, "create_visit", visit.id, data.visitors, current_user, detail=pairing.title)
    return success_response(data=visit.to_dict(), message="登记成功")


@router.put("/{pairing_id}/visits/{visit_id}")
async def update_visit(
    pairing_id: int,
    visit_id: int,
    data: VisitUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新走访记录（部分更新）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权编辑该结对记录的走访")
    visit = _get_visit_or_404(db, pairing, visit_id, current_user, "无权编辑该走访记录")

    update_data = data.model_dump(exclude_unset=True)
    old_household_id = visit.household_id
    if "household_id" in update_data:
        household = _resolve_household(db, update_data.pop("household_id"), pairing, current_user)
        visit.household_id = household.id if household else None
    if update_data.get("attachments") is not None:
        update_data["attachments"] = _normalize_attachments(update_data["attachments"])
    for key, value in update_data.items():
        setattr(visit, key, value)
    safe_commit(db)
    db.refresh(visit)
    _sync_household_last_visit(db, old_household_id)
    if visit.household_id != old_household_id:
        _sync_household_last_visit(db, visit.household_id)

    _write_log(db, "update_visit", visit.id, visit.visitors, current_user, detail=pairing.title)
    return success_response(data=visit.to_dict(), message="更新成功")


@router.delete("/{pairing_id}/visits/{visit_id}")
async def delete_visit(
    pairing_id: int,
    visit_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除走访记录（软删除）。"""
    pairing = _get_pairing_or_404(db, pairing_id, current_user, "无权删除该结对记录的走访")
    visit = _get_visit_or_404(db, pairing, visit_id, current_user, "无权删除该走访记录")

    visit.is_active = False
    visit.deleted_at = datetime.now(timezone.utc)
    safe_commit(db)
    _sync_household_last_visit(db, visit.household_id)

    _write_log(db, "delete_visit", visit.id, visit.visitors, current_user, detail=pairing.title)
    return success_response(data={"id": visit.id}, message="删除成功")


# ==================== 回收站（W27 P1）====================
# 结对记录与走访记录都是软删，此前无恢复通道；挂接通用回收站路由。
# 放在文件末尾：`/batch-restore`、`/batch-purge` 必须晚于全部 `/{id}/...` 注册。
#
# ⚠️ 两张表**不能注册在同一个 router 上**：通用回收站的路径同为 `/{rid}/restore`、
# `/batch-restore` 等，重复注册会产生**完全相同的路径**，后者被先注册者永久遮蔽
# （"看着注册了其实调不到"的假修复）。因此走访记录用**子路由 + `/visits` 前缀**，
# 最终路径为 `/pairings/visits/{rid}/restore`，与结对记录的 `/pairings/{rid}/restore`
# 天然不冲突；也与既有 `/{pairing_id}/visits/{visit_id}` 段数不同，不会互相捕获。
from app.api.v1.recycle_bin import register_recycle_bin_routes  # noqa: E402

register_recycle_bin_routes(router, model=PairingRecord, resource="结对帮扶记录")

visits_recycle_router = APIRouter(tags=["结对帮扶与走访台账"])
register_recycle_bin_routes(visits_recycle_router, model=VisitRecord, resource="走访记录")
router.include_router(visits_recycle_router, prefix="/visits")
