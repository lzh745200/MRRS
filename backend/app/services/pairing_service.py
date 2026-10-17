"""结对帮扶与走访台账服务层

职责：
- 字段组合校验（帮扶对象类型与目标 ID 的一致性、日期区间、状态枚举）；
- 帮扶对象可达性校验（不存在 404 / 跨组织越权 403，fail-closed）；
- 数据域查询基座（结对 / 走访统一走 ``data_scope.filter_by_org_ids``）；
- 台账统计（总量/在帮/已结束/对象类型分布/走访次数）与对象名称富化。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from app.core.data_permission import OrgScopeFilter, require_data_permission
from app.core.errors import AppError
from app.models.pairing import (
    PAIRING_STATUSES,
    PARTNER_TYPES,
    SUBJECT_TYPES,
    PairingRecord,
    VisitRecord,
)
from app.models.school import School
from app.models.supported_village import SupportedVillage


def ensure_pairing_valid(
    *,
    subject_type: str,
    partner_type: str,
    village_id: Optional[int] = None,
    school_id: Optional[int] = None,
    student_name: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> None:
    """校验结对记录字段组合；不合法抛 422（与 Pydantic 层校验语义一致）。"""
    if subject_type not in SUBJECT_TYPES:
        raise HTTPException(
            status_code=422, detail=f"帮扶主体类型不合法，可选：{'/'.join(SUBJECT_TYPES)}"
        )
    if partner_type not in PARTNER_TYPES:
        raise HTTPException(
            status_code=422, detail=f"帮扶对象类型不合法，可选：{'/'.join(PARTNER_TYPES)}"
        )
    if status is not None and status not in PAIRING_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"结对状态不合法，可选：{'/'.join(PAIRING_STATUSES)}"
        )
    if partner_type == "village" and not village_id:
        raise HTTPException(status_code=422, detail="帮扶对象为帮扶村时必须选择帮扶村")
    if partner_type == "school" and not school_id:
        raise HTTPException(status_code=422, detail="帮扶对象为帮扶学校时必须选择帮扶学校")
    if partner_type == "student" and not student_name:
        raise HTTPException(status_code=422, detail="帮扶对象为困难学生时必须填写学生姓名")
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="结束日期不能早于起始日期")


def resolve_partner(
    db: Session,
    *,
    partner_type: str,
    village_id: Optional[int] = None,
    school_id: Optional[int] = None,
    current_user,
) -> None:
    """校验帮扶对象存在且在当前用户数据范围内。

    - 对象不存在或已软删：404（``AppError.not_found``）；
    - 对象存在但属其他组织：403（``require_data_permission``）。
    """
    if partner_type == "village" and village_id:
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
    elif partner_type == "school" and school_id:
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


def pairing_base_query(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> Query:
    """结对记录查询基座：软删过滤 + 数据域过滤。"""
    query = db.query(PairingRecord)
    if not include_deleted:
        query = query.filter(PairingRecord.is_active == True)  # noqa: E712
    return data_scope.filter_by_org_ids(
        query, PairingRecord.organization_id, created_by_column=PairingRecord.created_by
    )


def visit_base_query(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> Query:
    """走访记录查询基座：与结对记录联表（保证父记录可见）+ 软删/数据域过滤。"""
    query = db.query(VisitRecord).join(
        PairingRecord, VisitRecord.pairing_id == PairingRecord.id
    )
    if not include_deleted:
        query = query.filter(
            VisitRecord.is_active == True,  # noqa: E712
            PairingRecord.is_active == True,  # noqa: E712
        )
    return data_scope.filter_by_org_ids(
        query, VisitRecord.organization_id, created_by_column=VisitRecord.created_by
    )


def pairing_stats(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> dict:
    """台账统计（口径跟随当前用户数据域；include_deleted 时含软删记录）。"""
    query = pairing_base_query(db, data_scope, include_deleted=include_deleted)
    return {
        "total": query.count(),
        "active": query.filter(PairingRecord.status == "active").count(),
        "ended": query.filter(PairingRecord.status == "ended").count(),
        "villages": query.filter(PairingRecord.partner_type == "village").count(),
        "schools": query.filter(PairingRecord.partner_type == "school").count(),
        "students": query.filter(PairingRecord.partner_type == "student").count(),
        "visits": visit_base_query(db, data_scope, include_deleted=include_deleted).count(),
    }


def normalize_partner_fields(payload: dict) -> dict:
    """归一化对象字段组合：与所选 partner_type 无关的字段一律清空。"""
    partner_type = payload.get("partner_type")
    if partner_type and partner_type != "village":
        payload["village_id"] = None
    if partner_type and partner_type != "school":
        payload["school_id"] = None
    if partner_type and partner_type != "student":
        payload["student_name"] = None
    return payload


def attach_partner_names(db: Session, items: list[dict]) -> list[dict]:
    """为结对记录字典补充帮扶对象显示名（跨村/校批量查询，避免 N+1）。"""
    village_ids = {i.get("village_id") for i in items if i.get("village_id")}
    school_ids = {i.get("school_id") for i in items if i.get("school_id")}

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

    for item in items:
        partner_type = item.get("partner_type")
        if partner_type == "village":
            item["partner_name"] = village_names.get(item.get("village_id"))
        elif partner_type == "school":
            item["partner_name"] = school_names.get(item.get("school_id"))
        else:
            item["partner_name"] = item.get("student_name")
    return items
