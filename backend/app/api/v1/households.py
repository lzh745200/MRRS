"""一户一档 API（W22 契约 §2）。

端点：
- ``GET    /households``                          分页列表（筛选 + 数据域；items 含 village_name/member_count/risk_alerts）
- ``POST   /households``                          新建
- ``GET    /households/alerts?level``             预警清单（规则命中 + open 风险记录）
- ``POST   /households/rollup?village_id&year``   汇总回填 VillagePopulation
- ``GET    /households/export?format=xlsx|csv``   台账导出（StreamingResponse 下载）
- ``PUT    /households/risk-records/{id}/close``  关闭风险记录
- ``GET/PUT/DELETE /households/{id}``             详情 / 更新 / 软删
- ``GET/POST /households/{id}/members``           成员列表 / 新增
- ``PUT/DELETE /households/{id}/members/{mid}``   成员更新 / 软删
- ``GET/POST /households/{id}/risk-records``      风险记录列表 / 登记

数据域沿用 ``get_org_scope``；软删模型查询均带 ``is_active``；
写操作使用 ``safe_commit``；PII（helper_phone / id_card）只经 ORM 加密列读写。
"""

import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import enforce_admin_include_deleted
from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.schemas.household import (
    HouseholdCreate,
    HouseholdMemberCreate,
    HouseholdMemberUpdate,
    HouseholdRiskRecordClose,
    HouseholdRiskRecordCreate,
    HouseholdUpdate,
)
from app.services import household_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/households", tags=["一户一档"])

_EXPORT_FORMATS = ("xlsx", "csv")
_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


# ==================== 一户一档 ====================


@router.get("")
async def list_households(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    village_id: Optional[int] = Query(None, description="按帮扶村筛选"),
    risk_level: Optional[str] = Query(None, description="风险等级 low/medium/high"),
    household_type: Optional[str] = Query(None, description="户类型 general/poverty/monitor"),
    keyword: Optional[str] = Query(None, description="关键词：户主/户编号/帮扶责任人/地址"),
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """一户一档列表（envelope；非管理员 include_deleted 静默降级）。"""
    items, total = household_service.list_households(
        db,
        data_scope,
        page=page,
        page_size=page_size,
        village_id=village_id,
        risk_level=risk_level,
        household_type=household_type,
        keyword=keyword,
        include_deleted=include_deleted,
    )
    return ok_list(items=items, total=total, page=page, page_size=page_size)


@router.post("")
async def create_household(
    payload: HouseholdCreate,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """新建一户一档。"""
    household = household_service.create_household(db, payload, current_user, data_scope)
    return success_response(
        data=household_service.serialize_household(household), message="创建成功"
    )


@router.get("/alerts")
async def get_household_alerts(
    level: Optional[str] = Query(None, description="按风险等级过滤 low/medium/high"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """预警清单：规则命中 + 处理中的风险记录（可按等级过滤）。"""
    items = household_service.list_alerts(db, data_scope, level=level)
    return ok_list(items=items, total=len(items), page=1, page_size=max(len(items), 1))


@router.post("/rollup")
async def rollup_households(
    village_id: int = Query(..., description="帮扶村ID"),
    year: Optional[int] = Query(None, description="统计年度，缺省当前年"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """按户汇总回填帮扶村当年度人口数据（幂等）。"""
    summary = household_service.rollup_to_village_population(
        db, village_id, year, current_user, data_scope
    )
    return success_response(data=summary, message="汇总回填成功")


@router.get("/export")
async def export_households(
    format: str = Query("xlsx", description="导出格式 xlsx/csv"),
    village_id: Optional[int] = Query(None),
    risk_level: Optional[str] = Query(None),
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """导出一户一档台账（当前筛选范围；xlsx 或 csv）。"""
    if format not in _EXPORT_FORMATS:
        raise AppError.bad_request(f"不支持的导出格式: {format}（仅支持 xlsx/csv）")
    headers, rows = household_service.household_export_data(
        db,
        data_scope,
        village_id=village_id,
        risk_level=risk_level,
        include_deleted=include_deleted,
    )
    if format == "xlsx":
        content = household_service.build_xlsx_bytes(headers, rows)
        media_type = _XLSX_MEDIA_TYPE
    else:
        content = household_service.build_csv_bytes(headers, rows)
        media_type = _CSV_MEDIA_TYPE
    filename = f"households_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{format}"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/risk-records/{record_id}/close")
async def close_risk_record(
    record_id: int,
    payload: HouseholdRiskRecordClose,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """关闭风险记录（重复关闭返回 400）。"""
    record = household_service.get_risk_record_or_404(db, data_scope, record_id)
    record = household_service.close_risk_record(db, record, payload)
    return success_response(
        data=household_service.serialize_risk_record(record), message="关闭成功"
    )


@router.get("/{household_id}")
async def get_household(
    household_id: int,
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """户档案详情（含成员、风险记录、走访记录与预警命中）。"""
    data = household_service.get_household_detail(
        db, data_scope, household_id, include_deleted=include_deleted
    )
    return success_response(data=data, message="成功")


@router.put("/{household_id}")
async def update_household(
    household_id: int,
    payload: HouseholdUpdate,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """更新户档案（部分更新）。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    household = household_service.update_household(db, household, payload, data_scope)
    return success_response(
        data=household_service.serialize_household(household), message="更新成功"
    )


@router.delete("/{household_id}")
async def delete_household(
    household_id: int,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """软删除户档案（is_active=false）。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    household_service.soft_delete_household(db, household)
    return success_response(data={"id": household.id}, message="删除成功")


# ==================== 家庭成员 ====================


@router.get("/{household_id}/members")
async def list_members(
    household_id: int,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """某户家庭成员列表。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    items = household_service.list_members(db, data_scope, household)
    return ok_list(items=items, total=len(items), page=1, page_size=max(len(items), 1))


@router.post("/{household_id}/members")
async def create_member(
    household_id: int,
    payload: HouseholdMemberCreate,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """新增家庭成员。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    member = household_service.create_member(db, household, payload, current_user)
    return success_response(
        data=household_service.serialize_member(member), message="新增成功"
    )


@router.put("/{household_id}/members/{member_id}")
async def update_member(
    household_id: int,
    member_id: int,
    payload: HouseholdMemberUpdate,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """更新家庭成员（部分更新）。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    member = household_service.get_member_or_404(db, data_scope, household, member_id)
    member = household_service.update_member(db, member, payload)
    return success_response(
        data=household_service.serialize_member(member), message="更新成功"
    )


@router.delete("/{household_id}/members/{member_id}")
async def delete_member(
    household_id: int,
    member_id: int,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """软删除家庭成员。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    member = household_service.get_member_or_404(db, data_scope, household, member_id)
    household_service.soft_delete_member(db, member)
    return success_response(data={"id": member.id}, message="删除成功")


# ==================== 风险记录 ====================


@router.get("/{household_id}/risk-records")
async def list_risk_records(
    household_id: int,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """某户风险记录列表（按发现时间倒序）。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    items = household_service.list_risk_records(db, data_scope, household)
    return ok_list(items=items, total=len(items), page=1, page_size=max(len(items), 1))


@router.post("/{household_id}/risk-records")
async def create_risk_record(
    household_id: int,
    payload: HouseholdRiskRecordCreate,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """登记风险 / 预警记录。"""
    household = household_service.get_household_or_404(db, data_scope, household_id)
    record = household_service.create_risk_record(db, household, payload, current_user)
    return success_response(
        data=household_service.serialize_risk_record(record), message="登记成功"
    )
