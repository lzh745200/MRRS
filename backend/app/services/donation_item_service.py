"""捐赠物资台账服务层

职责：
- 字段校验（类别 / 去向类型枚举、去向 ID 与类型一致性、数量与折价非负）；
- 去向可达性校验（不存在或已软删 404 / 跨组织越权 403，fail-closed）；
- 数据域查询基座（列表 / 统计统一走 ``data_scope.filter_by_org_ids``）；
- 台账统计（按去向与类别的条数、数量与折价合计）与去向名称富化。
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.core.data_permission import OrgScopeFilter, require_data_permission
from app.core.errors import AppError
from app.models.donation_item import (
    DONATION_CATEGORIES,
    DESTINATION_TYPES,
    DonationItem,
)
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage


def ensure_donation_valid(
    *,
    category: str,
    destination_type: str,
    village_id: Optional[int] = None,
    school_id: Optional[int] = None,
    project_id: Optional[int] = None,
    quantity: Optional[float] = None,
    valuation: Optional[float] = None,
) -> None:
    """校验捐赠物资字段组合；不合法抛 422（与 Pydantic 层校验语义一致）。"""
    if category not in DONATION_CATEGORIES:
        raise HTTPException(
            status_code=422, detail=f"物资类别不合法，可选：{'/'.join(DONATION_CATEGORIES)}"
        )
    if destination_type not in DESTINATION_TYPES:
        raise HTTPException(
            status_code=422, detail=f"去向类型不合法，可选：{'/'.join(DESTINATION_TYPES)}"
        )
    if destination_type == "village" and not village_id:
        raise HTTPException(status_code=422, detail="去向为帮扶村时必须选择帮扶村")
    if destination_type == "school" and not school_id:
        raise HTTPException(status_code=422, detail="去向为帮扶学校时必须选择帮扶学校")
    if destination_type == "project" and not project_id:
        raise HTTPException(status_code=422, detail="去向为帮扶项目时必须选择帮扶项目")
    if quantity is not None and quantity < 0:
        raise HTTPException(status_code=422, detail="数量不能为负数")
    if valuation is not None and valuation < 0:
        raise HTTPException(status_code=422, detail="折价不能为负数")


def resolve_destination(
    db: Session,
    *,
    destination_type: str,
    village_id: Optional[int] = None,
    school_id: Optional[int] = None,
    project_id: Optional[int] = None,
    current_user,
) -> None:
    """校验去向对象存在且在当前用户数据范围内。

    - 对象不存在或已软删：404（``AppError.not_found``）；
    - 对象存在但属其他组织：403（``require_data_permission``）。
    """
    if destination_type == "village" and village_id:
        village = (
            db.query(SupportedVillage).filter(SupportedVillage.id == village_id).first()
        )
        if village is None or village.is_active is False:
            raise AppError.not_found("帮扶村")
        require_data_permission(
            current_user,
            village.organization_id,
            village.created_by,
            db,
            error_message="无权关联该帮扶村",
        )
    elif destination_type == "school" and school_id:
        school = db.query(School).filter(School.id == school_id).first()
        if school is None or school.is_active is False:
            raise AppError.not_found("帮扶学校")
        require_data_permission(
            current_user,
            school.organization_id,
            school.created_by,
            db,
            error_message="无权关联该帮扶学校",
        )
    elif destination_type == "project" and project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None or project.is_active is False:
            raise AppError.not_found("帮扶项目")
        require_data_permission(
            current_user,
            project.organization_id,
            project.created_by,
            db,
            error_message="无权关联该帮扶项目",
        )


def donation_base_query(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> Query:
    """捐赠物资查询基座：软删过滤 + 数据域过滤。"""
    query = db.query(DonationItem)
    if not include_deleted:
        query = query.filter(DonationItem.is_active == True)  # noqa: E712
    return data_scope.filter_by_org_ids(
        query,
        DonationItem.organization_id,
        created_by_column=DonationItem.created_by,
    )


def donation_stats(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> dict:
    """台账统计（口径跟随当前用户数据域；include_deleted 时含软删记录）。"""
    query = donation_base_query(db, data_scope, include_deleted=include_deleted)
    totals = query.with_entities(
        func.coalesce(func.sum(DonationItem.quantity), 0),
        func.coalesce(func.sum(DonationItem.valuation), 0),
    ).one()
    return {
        "total": query.count(),
        "villages": query.filter(DonationItem.destination_type == "village").count(),
        "schools": query.filter(DonationItem.destination_type == "school").count(),
        "projects": query.filter(DonationItem.destination_type == "project").count(),
        "books": query.filter(DonationItem.category == "book").count(),
        "equipment": query.filter(DonationItem.category == "equipment").count(),
        "materials": query.filter(DonationItem.category == "material").count(),
        "quantity": float(totals[0] or 0),
        "valuation": float(totals[1] or 0),
    }


def normalize_destination_fields(payload: dict) -> dict:
    """归一化去向字段组合：与所选 destination_type 无关的字段一律清空。"""
    destination_type = payload.get("destination_type")
    if destination_type and destination_type != "village":
        payload["village_id"] = None
    if destination_type and destination_type != "school":
        payload["school_id"] = None
    if destination_type and destination_type != "project":
        payload["project_id"] = None
    return payload


def attach_destination_names(db: Session, items: list[dict]) -> list[dict]:
    """为物资字典补充去向显示名（跨村/校/项目批量查询，避免 N+1）。

    软删（``is_active=False``）的去向不再解析名称，与软删过滤口径一致。
    """
    village_ids = {i.get("village_id") for i in items if i.get("village_id")}
    school_ids = {i.get("school_id") for i in items if i.get("school_id")}
    project_ids = {i.get("project_id") for i in items if i.get("project_id")}

    village_names: dict = {}
    if village_ids:
        rows = (
            db.query(SupportedVillage.id, SupportedVillage.village_name)
            .filter(
                SupportedVillage.id.in_(village_ids),
                SupportedVillage.is_active == True,  # noqa: E712  软删对象不再展示
            )
            .all()
        )
        village_names = {row[0]: row[1] for row in rows}

    school_names: dict = {}
    if school_ids:
        rows = (
            db.query(School.id, School.name)
            .filter(
                School.id.in_(school_ids),
                School.is_active == True,  # noqa: E712  软删对象不再展示
            )
            .all()
        )
        school_names = {row[0]: row[1] for row in rows}

    project_names: dict = {}
    if project_ids:
        rows = (
            db.query(Project.id, Project.name)
            .filter(
                Project.id.in_(project_ids),
                Project.is_active == True,  # noqa: E712  软删对象不再展示
            )
            .all()
        )
        project_names = {row[0]: row[1] for row in rows}

    for item in items:
        destination_type = item.get("destination_type")
        if destination_type == "village":
            item["destination_name"] = village_names.get(item.get("village_id"))
        elif destination_type == "school":
            item["destination_name"] = school_names.get(item.get("school_id"))
        elif destination_type == "project":
            item["destination_name"] = project_names.get(item.get("project_id"))
        else:
            item["destination_name"] = None
    return items
