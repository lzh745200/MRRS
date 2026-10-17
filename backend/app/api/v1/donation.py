"""捐赠物资台账 API

- 增删改查 + 统计 + 软删（``include_deleted`` 仅管理员可见软删记录）；
- 数据域：列表/统计走 ``donation_item_service`` 的查询基座（``filter_by_org_ids``），
  点查走 ``require_data_permission``（跨组织 403 / 不存在 404）；
- 附件：凭证文件走通用 ``/files/upload``（category=donations）拿到 url 后存入本表
  ``attachments`` 列，不在本模块重复实现上传落盘。
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.deps import build_viewable_because, enforce_admin_include_deleted
from app.core.data_permission import OrgScopeFilter, get_org_scope, require_data_permission
from app.core.database import get_db
from app.core.errors import AppError
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.core.transaction import safe_commit
from app.models.donation_item import DonationItem
from app.services.donation_item_service import (
    attach_destination_names,
    donation_base_query,
    donation_stats,
    ensure_donation_valid,
    normalize_destination_fields,
    resolve_destination,
)
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/donations", tags=["捐赠物资台账"])


# ==================== 请求模型 ====================


class AttachmentItem(BaseModel):
    """凭证附件（由通用上传接口返回的元数据）"""

    url: str = Field(..., min_length=1, max_length=500)
    file_name: Optional[str] = Field(default=None, max_length=300)


class DonationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(default="material", max_length=16)
    quantity: float = Field(default=0, ge=0)
    unit: Optional[str] = Field(default=None, max_length=32)
    valuation: float = Field(default=0, ge=0)
    source_unit: Optional[str] = Field(default=None, max_length=200)
    destination_type: str = Field(..., max_length=16)
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    project_id: Optional[int] = None
    delivery_date: Optional[date] = None
    receiver: Optional[str] = Field(default=None, max_length=64)
    attachments: Optional[list[AttachmentItem]] = None
    remark: Optional[str] = Field(default=None, max_length=500)


class DonationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=16)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=32)
    valuation: Optional[float] = Field(default=None, ge=0)
    source_unit: Optional[str] = Field(default=None, max_length=200)
    destination_type: Optional[str] = Field(default=None, max_length=16)
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    project_id: Optional[int] = None
    delivery_date: Optional[date] = None
    receiver: Optional[str] = Field(default=None, max_length=64)
    attachments: Optional[list[AttachmentItem]] = None
    remark: Optional[str] = Field(default=None, max_length=500)


# ==================== 内部工具 ====================


def _normalize_attachments(items) -> list[dict]:
    """统一附件存储形态（create 走全量 dump、update 走 exclude_unset，需归一）。"""
    return [{"url": a["url"], "file_name": a.get("file_name")} for a in items]


def _get_item_or_404(db: Session, item_id: int, current_user, error_message: str) -> DonationItem:
    item = db.query(DonationItem).filter(DonationItem.id == item_id).first()
    if not item:
        raise AppError.not_found("捐赠物资记录")
    require_data_permission(
        current_user,
        item.organization_id,
        item.created_by,
        db,
        error_message=error_message,
    )
    return item


def _write_log(
    db: Session, action: str, entity_id: int, title: str, current_user, detail: str = ""
) -> None:
    write_work_log(
        db,
        "donation",
        action,
        entity_id,
        title,
        user_id=current_user.id,
        username=getattr(current_user, "username", "系统"),
        detail=detail,
    )


# ==================== 台账 ====================


@router.get("")
async def list_donations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    destination_type: Optional[str] = None,
    destination_id: Optional[int] = None,
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """捐赠物资台账列表（envelope；非管理员 include_deleted 静默降级）。"""
    query = donation_base_query(db, data_scope, include_deleted=include_deleted)

    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                DonationItem.name.like(like),
                DonationItem.source_unit.like(like),
                DonationItem.receiver.like(like),
            )
        )
    if category:
        query = query.filter(DonationItem.category == category)
    if destination_type:
        query = query.filter(DonationItem.destination_type == destination_type)
    if destination_id:
        if destination_type == "village":
            query = query.filter(DonationItem.village_id == destination_id)
        elif destination_type == "school":
            query = query.filter(DonationItem.school_id == destination_id)
        elif destination_type == "project":
            query = query.filter(DonationItem.project_id == destination_id)
        else:
            query = query.filter(
                or_(
                    DonationItem.village_id == destination_id,
                    DonationItem.school_id == destination_id,
                    DonationItem.project_id == destination_id,
                )
            )

    total = query.count()
    items = (
        query.order_by(DonationItem.created_at.desc(), DonationItem.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    rows = attach_destination_names(db, [i.to_dict() for i in items])
    return ok_list(items=rows, total=total, page=page, page_size=page_size)


@router.get("/stats")
async def get_donation_stats(
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """台账统计（数据域内口径：条数 / 数量合计 / 折价合计）。"""
    return success_response(
        data=donation_stats(db, data_scope, include_deleted=include_deleted), message="成功"
    )


@router.get("/{item_id}")
async def get_donation(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """物资详情（含软删记录，管理员附带 viewableBecause 元数据）。"""
    item = _get_item_or_404(db, item_id, current_user, "无权访问该捐赠物资记录")
    data = attach_destination_names(db, [item.to_dict()])[0]
    data["viewableBecause"] = build_viewable_because(current_user, item)
    return success_response(data=data, message="成功")


@router.post("")
async def create_donation(
    data: DonationCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登记捐赠物资。"""
    ensure_donation_valid(
        category=data.category,
        destination_type=data.destination_type,
        village_id=data.village_id,
        school_id=data.school_id,
        project_id=data.project_id,
        quantity=data.quantity,
        valuation=data.valuation,
    )
    resolve_destination(
        db,
        destination_type=data.destination_type,
        village_id=data.village_id,
        school_id=data.school_id,
        project_id=data.project_id,
        current_user=current_user,
    )
    payload = normalize_destination_fields(data.model_dump())
    if payload.get("attachments") is not None:
        payload["attachments"] = _normalize_attachments(payload["attachments"])
    payload["organization_id"] = getattr(current_user, "organization_id", None)
    payload["created_by"] = current_user.id

    item = DonationItem(**payload)
    db.add(item)
    safe_commit(db)
    db.refresh(item)

    _write_log(db, "create", item.id, item.name, current_user)
    data_out = attach_destination_names(db, [item.to_dict()])[0]
    return success_response(data=data_out, message="登记成功")


@router.put("/{item_id}")
async def update_donation(
    item_id: int,
    data: DonationUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新物资记录（部分更新；字段组合按合并后的完整值校验）。"""
    item = _get_item_or_404(db, item_id, current_user, "无权编辑该捐赠物资记录")

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("attachments") is not None:
        update_data["attachments"] = _normalize_attachments(update_data["attachments"])
    if "destination_type" in update_data:
        update_data = normalize_destination_fields(update_data)

    merged = {
        "category": update_data.get("category", item.category),
        "destination_type": update_data.get("destination_type", item.destination_type),
        "village_id": update_data.get("village_id", item.village_id),
        "school_id": update_data.get("school_id", item.school_id),
        "project_id": update_data.get("project_id", item.project_id),
        "quantity": update_data.get("quantity", float(item.quantity or 0)),
        "valuation": update_data.get("valuation", float(item.valuation or 0)),
    }

    ensure_donation_valid(**merged)
    if any(k in update_data for k in ("destination_type", "village_id", "school_id", "project_id")):
        resolve_destination(
            db,
            destination_type=merged["destination_type"],
            village_id=merged["village_id"],
            school_id=merged["school_id"],
            project_id=merged["project_id"],
            current_user=current_user,
        )

    for key, value in update_data.items():
        setattr(item, key, value)
    safe_commit(db)
    db.refresh(item)

    _write_log(db, "update", item.id, item.name, current_user)
    data_out = attach_destination_names(db, [item.to_dict()])[0]
    return success_response(data=data_out, message="更新成功")


@router.delete("/{item_id}")
async def delete_donation(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除物资记录（软删除）。"""
    item = _get_item_or_404(db, item_id, current_user, "无权删除该捐赠物资记录")

    item.is_active = False
    item.deleted_at = datetime.now(timezone.utc)
    safe_commit(db)

    _write_log(db, "delete", item.id, item.name, current_user)
    return success_response(data={"id": item.id}, message="删除成功")
