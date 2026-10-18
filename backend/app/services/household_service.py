"""一户一档服务层（W22 契约 §1 / §2）。

职责：
- 户 / 成员 / 风险记录的 CRUD（软删 ``is_active``，PII 只走 ORM 加密列）；
- 列表筛选（村 / 风险等级 / 户类型 / 关键词 + 数据域 ``filter_by_org_ids``）；
- 预警规则（不落库，供列表与 /households/alerts 展示）：
    1) 连续未走访：``last_visit_date`` 为空或距今天 > 90 天，且户类型非一般户 → medium；
    2) 大病 / 住房不安全 / 突发困难（``sudden``、``multiple``）→ high；
- 风险记录登记 / 关闭闭环；
- ``rollup_to_village_population``：按村把一户一档明细汇总回填 ``VillagePopulation``
  当年度行（总户数 / 总人口 / 脱贫户数 / 监测户数），幂等 upsert、不覆盖其它年度；
- 台账导出数据组装（xlsx / csv 字节由 API 层以 StreamingResponse 下发）。

数据域：所有查询统一 ``data_scope.filter_by_org_ids``（无数据域参数即无法构造查询），
点查一律收敛后再判 404，避免跨组织存在性探测。
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.core.data_permission import OrgScopeFilter
from app.core.exceptions import AppError
from app.core.transaction import safe_commit
from app.models.household import (
    HIGH_RISK_TYPES,
    Household,
    HouseholdMember,
    HouseholdRiskRecord,
)
from app.models.pairing import VisitRecord
from app.models.supported_village import SupportedVillage, VillagePopulation
from app.schemas.household import (
    HouseholdMemberResponse,
    HouseholdResponse,
    HouseholdRiskRecordResponse,
)

logger = logging.getLogger(__name__)

# 连续未走访预警阈值（天）
NO_VISIT_ALERT_DAYS = 90
# 预警等级排序（高 → 低）
_LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}
# 导出列：(表头, 字段名)。字段取自 ``enrich_households`` 的 item。
EXPORT_COLUMNS = (
    ("户编号", "household_code"),
    ("户主姓名", "household_name"),
    ("帮扶村", "village_name"),
    ("户类型", "household_type"),
    ("风险类型", "risk_type"),
    ("风险等级", "risk_level"),
    ("帮扶责任人", "helper_name"),
    ("联系电话", "helper_phone"),
    ("年收入(元)", "annual_income"),
    ("务工人数", "migrant_workers"),
    ("大病", "has_serious_illness"),
    ("住房安全", "housing_safe"),
    ("成员数", "member_count"),
    ("最近走访", "last_visit_date"),
    ("预警", "risk_alerts"),
)


def _utcnow() -> datetime:
    """当前 UTC 时间（与全库 UtcDateTime 约定一致）。"""
    return datetime.now(timezone.utc)


def _today(today: Optional[date] = None) -> date:
    """参照日期（测试可注入固定日期，默认取 UTC 当天）。"""
    if today is not None:
        return today
    return datetime.now(timezone.utc).date()


# ════════════════════════════════════════════════════════════════════
#  查询基座与点查
# ════════════════════════════════════════════════════════════════════

def household_base_query(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> Query:
    """一户一档查询基座：软删过滤 + 数据域过滤。"""
    query = db.query(Household)
    if not include_deleted:
        query = query.filter(Household.is_active == True)  # noqa: E712
    return data_scope.filter_by_org_ids(
        query, Household.organization_id, created_by_column=Household.created_by
    )


def member_base_query(
    db: Session, data_scope: OrgScopeFilter, household_id: int, *, include_deleted: bool = False
) -> Query:
    """家庭成员查询基座（限定到某户 + 软删/数据域过滤）。"""
    query = db.query(HouseholdMember).filter(HouseholdMember.household_id == household_id)
    if not include_deleted:
        query = query.filter(HouseholdMember.is_active == True)  # noqa: E712
    return data_scope.filter_by_org_ids(
        query, HouseholdMember.organization_id, created_by_column=HouseholdMember.created_by
    )


def risk_record_base_query(
    db: Session,
    data_scope: OrgScopeFilter,
    *,
    household_id: Optional[int] = None,
    include_deleted: bool = False,
) -> Query:
    """风险记录查询基座（可按户过滤 + 软删/数据域过滤）。"""
    query = db.query(HouseholdRiskRecord)
    if household_id is not None:
        query = query.filter(HouseholdRiskRecord.household_id == household_id)
    if not include_deleted:
        query = query.filter(HouseholdRiskRecord.is_active == True)  # noqa: E712
    return data_scope.filter_by_org_ids(
        query,
        HouseholdRiskRecord.organization_id,
        created_by_column=HouseholdRiskRecord.created_by,
    )


def load_village(db: Session, data_scope: OrgScopeFilter, village_id: int) -> SupportedVillage:
    """加载数据域内的有效帮扶村；不存在 / 软删 / 越权一律 404。"""
    query = db.query(SupportedVillage).filter(
        SupportedVillage.id == village_id,
        SupportedVillage.is_active == True,  # noqa: E712
    )
    query = data_scope.filter_by_org_ids(
        query, SupportedVillage.organization_id, created_by_column=SupportedVillage.created_by
    )
    village = query.first()
    if village is None:
        raise AppError.not_found("帮扶村")
    return village


def get_household_or_404(
    db: Session,
    data_scope: OrgScopeFilter,
    household_id: int,
    *,
    include_deleted: bool = False,
) -> Household:
    """按数据域加载户档案；不存在 / 越权 → 404。"""
    household = (
        household_base_query(db, data_scope, include_deleted=include_deleted)
        .filter(Household.id == household_id)
        .first()
    )
    if household is None:
        raise AppError.not_found("一户一档")
    return household


def get_member_or_404(
    db: Session, data_scope: OrgScopeFilter, household: Household, member_id: int
) -> HouseholdMember:
    """按户 + 数据域加载成员；不存在 → 404。"""
    member = (
        member_base_query(db, data_scope, household.id)
        .filter(HouseholdMember.id == member_id)
        .first()
    )
    if member is None:
        raise AppError.not_found("家庭成员")
    return member


def get_risk_record_or_404(
    db: Session, data_scope: OrgScopeFilter, record_id: int
) -> HouseholdRiskRecord:
    """按数据域加载风险记录；不存在 → 404。"""
    record = (
        risk_record_base_query(db, data_scope)
        .filter(HouseholdRiskRecord.id == record_id)
        .first()
    )
    if record is None:
        raise AppError.not_found("风险记录")
    return record


# ════════════════════════════════════════════════════════════════════
#  序列化
# ════════════════════════════════════════════════════════════════════

def serialize_household(household: Household) -> dict:
    """户档案出站序列化（响应模型二次校验，金额 float / 时间 ISO）。"""
    return HouseholdResponse.model_validate(household.to_dict()).model_dump(mode="json")


def serialize_member(member: HouseholdMember) -> dict:
    """家庭成员出站序列化。"""
    return HouseholdMemberResponse.model_validate(member.to_dict()).model_dump(mode="json")


def serialize_risk_record(record: HouseholdRiskRecord) -> dict:
    """风险记录出站序列化。"""
    return HouseholdRiskRecordResponse.model_validate(record.to_dict()).model_dump(mode="json")


# ════════════════════════════════════════════════════════════════════
#  预警规则（纯函数，便于边界测试）
# ════════════════════════════════════════════════════════════════════

def evaluate_household_alerts(household: Household, today: Optional[date] = None) -> list:
    """计算单个户命中的预警规则（不落库）。

    规则（契约 §1.3）：
    1) 连续未走访：``last_visit_date`` 为空或距参照日 > 90 天，且非一般户 → medium；
    2) 大病 / 住房不安全 / 突发困难（sudden、multiple）→ high（逐项独立命中）。
    """
    reference = _today(today)
    alerts = []
    no_visit_days = None
    if household.last_visit_date is not None:
        no_visit_days = (reference - household.last_visit_date).days
    if household.household_type != "general" and (
        no_visit_days is None or no_visit_days > NO_VISIT_ALERT_DAYS
    ):
        alerts.append(
            {
                "code": "no_visit",
                "level": "medium",
                "message": f"连续未走访超过 {NO_VISIT_ALERT_DAYS} 天（或从未走访）",
            }
        )
    if household.has_serious_illness:
        alerts.append({"code": "serious_illness", "level": "high", "message": "家庭成员患大病"})
    if household.housing_safe is False:
        alerts.append({"code": "housing_unsafe", "level": "high", "message": "住房安全未达标"})
    if household.risk_type in HIGH_RISK_TYPES:
        alerts.append(
            {"code": "risk_type", "level": "high", "message": "存在突发困难/多重风险"}
        )
    return alerts


def list_alerts(
    db: Session,
    data_scope: OrgScopeFilter,
    *,
    level: Optional[str] = None,
    today: Optional[date] = None,
) -> list:
    """预警清单：规则命中 + 处理中的风险记录（可按等级过滤，按风险降序）。"""
    households = household_base_query(db, data_scope).all()
    household_map = {household.id: household for household in households}
    items = []
    for household in households:
        for alert in evaluate_household_alerts(household, today=today):
            items.append(
                {
                    "household_id": household.id,
                    "household_name": household.household_name,
                    "village_id": household.supported_village_id,
                    "source": "rule",
                    "code": alert["code"],
                    "level": alert["level"],
                    "message": alert["message"],
                    "detected_at": None,
                }
            )
    records = (
        risk_record_base_query(db, data_scope)
        .filter(HouseholdRiskRecord.status == "open")
        .all()
    )
    for record in records:
        household = household_map.get(record.household_id)
        if household is None:
            # 户已软删或不在数据域：孤儿风险记录不展示（避免泄漏已删除对象）
            continue
        items.append(
            {
                "household_id": record.household_id,
                "household_name": household.household_name,
                "village_id": household.supported_village_id,
                "source": "risk_record",
                "risk_record_id": record.id,
                "code": record.risk_type,
                "level": record.risk_level,
                "message": record.reason or "",
                "detected_at": record.detected_at.isoformat() if record.detected_at else None,
            }
        )
    if level:
        items = [item for item in items if item["level"] == level]
    items.sort(key=lambda item: (_LEVEL_ORDER.get(item["level"], len(_LEVEL_ORDER)), item["household_id"]))
    return items


# ════════════════════════════════════════════════════════════════════
#  列表 / 详情富化
# ════════════════════════════════════════════════════════════════════

def apply_household_filters(
    query: Query,
    *,
    village_id: Optional[int] = None,
    risk_level: Optional[str] = None,
    household_type: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Query:
    """列表/导出共用筛选条件。"""
    if village_id is not None:
        query = query.filter(Household.supported_village_id == village_id)
    if risk_level:
        query = query.filter(Household.risk_level == risk_level)
    if household_type:
        query = query.filter(Household.household_type == household_type)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                Household.household_name.like(like),
                Household.household_code.like(like),
                Household.helper_name.like(like),
                Household.address.like(like),
            )
        )
    return query


def _village_name_map(db: Session, village_ids: set) -> dict:
    """批量取帮扶村名称（避免逐行查询）。"""
    if not village_ids:
        return {}
    rows = (
        db.query(SupportedVillage.id, SupportedVillage.village_name)
        .filter(
            SupportedVillage.id.in_(village_ids),
            SupportedVillage.is_active == True,  # noqa: E712
        )
        .all()
    )
    return {row[0]: row[1] for row in rows}


def _member_count_map(db: Session, household_ids: list) -> dict:
    """批量统计各户有效成员数（避免 N+1）。"""
    if not household_ids:
        return {}
    rows = (
        db.query(HouseholdMember.household_id, func.count(HouseholdMember.id))
        .filter(
            HouseholdMember.household_id.in_(household_ids),
            HouseholdMember.is_active == True,  # noqa: E712
        )
        .group_by(HouseholdMember.household_id)
        .all()
    )
    return {row[0]: int(row[1] or 0) for row in rows}


def enrich_households(
    db: Session, households: list, today: Optional[date] = None
) -> list:
    """批量富化户列表：village_name / member_count / risk_alerts。"""
    if not households:
        return []
    household_ids = [household.id for household in households]
    village_ids = {household.supported_village_id for household in households}
    village_names = _village_name_map(db, village_ids)
    member_counts = _member_count_map(db, household_ids)
    items = []
    for household in households:
        data = serialize_household(household)
        data["village_name"] = village_names.get(household.supported_village_id)
        data["member_count"] = member_counts.get(household.id, 0)
        data["risk_alerts"] = evaluate_household_alerts(household, today=today)
        items.append(data)
    return items


def list_households(
    db: Session,
    data_scope: OrgScopeFilter,
    *,
    page: int = 1,
    page_size: int = 20,
    village_id: Optional[int] = None,
    risk_level: Optional[str] = None,
    household_type: Optional[str] = None,
    keyword: Optional[str] = None,
    include_deleted: bool = False,
) -> tuple:
    """分页查询户档案，返回 (富化 items, total)。"""
    query = household_base_query(db, data_scope, include_deleted=include_deleted)
    query = apply_household_filters(
        query,
        village_id=village_id,
        risk_level=risk_level,
        household_type=household_type,
        keyword=keyword,
    )
    total = query.count()
    households = (
        query.order_by(Household.created_at.desc(), Household.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return enrich_households(db, households), total


def list_visits(db: Session, data_scope: OrgScopeFilter, household: Household) -> list:
    """该户走访记录（W22 走访挂户；按 visit_date 倒序，只取有效记录）。

    字段与前端一户一档详情时间线契约一致：
    ``{id, pairing_id, visit_date, visitors, purpose, content, materials}``。
    走访记录随结对记录入库，户 id 由配对 API 挂户回写；这里只做查询富化，
    数据域按 ``VisitRecord.organization_id`` 收敛（早于挂户的旧记录无户归属，不展示）。
    """
    query = db.query(VisitRecord).filter(
        VisitRecord.household_id == household.id,
        VisitRecord.is_active == True,  # noqa: E712
    )
    query = data_scope.filter_by_org_ids(
        query, VisitRecord.organization_id, created_by_column=VisitRecord.created_by
    )
    visits = query.order_by(VisitRecord.visit_date.desc(), VisitRecord.id.desc()).all()
    return [
        {
            "id": visit.id,
            "pairing_id": visit.pairing_id,
            "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
            "visitors": visit.visitors,
            "purpose": visit.purpose,
            "content": visit.content,
            "materials": visit.materials,
        }
        for visit in visits
    ]


def get_household_detail(
    db: Session,
    data_scope: OrgScopeFilter,
    household_id: int,
    *,
    include_deleted: bool = False,
) -> dict:
    """户档案详情：基础档案 + 成员 + 风险记录 + 走访记录 + 预警（富化后合并）。"""
    household = get_household_or_404(
        db, data_scope, household_id, include_deleted=include_deleted
    )
    data = enrich_households(db, [household])[0]
    data["members"] = [
        serialize_member(member)
        for member in member_base_query(db, data_scope, household.id)
        .order_by(HouseholdMember.id.asc())
        .all()
    ]
    data["risk_records"] = [
        serialize_risk_record(record)
        for record in risk_record_base_query(db, data_scope, household_id=household.id)
        .order_by(HouseholdRiskRecord.detected_at.desc(), HouseholdRiskRecord.id.desc())
        .all()
    ]
    data["visits"] = list_visits(db, data_scope, household)
    return data


# ════════════════════════════════════════════════════════════════════
#  户 CRUD
# ════════════════════════════════════════════════════════════════════

def _ensure_household_code_unique(
    db: Session,
    village_id: int,
    household_code: Optional[str],
    *,
    exclude_id: Optional[int] = None,
) -> None:
    """校验户编号村内唯一（空编号不校验）；冲突 → 409。"""
    if not household_code:
        return
    query = db.query(Household).filter(
        Household.supported_village_id == village_id,
        Household.household_code == household_code,
        Household.is_active == True,  # noqa: E712
    )
    if exclude_id is not None:
        query = query.filter(Household.id != exclude_id)
    if query.first() is not None:
        raise AppError.conflict("户编号在该村已存在")


def create_household(db: Session, payload, current_user, data_scope: OrgScopeFilter) -> Household:
    """新建户档案（校验帮扶村可达性与户编号唯一性）。"""
    load_village(db, data_scope, payload.supported_village_id)
    _ensure_household_code_unique(db, payload.supported_village_id, payload.household_code)
    household = Household(**payload.model_dump())
    household.organization_id = getattr(current_user, "organization_id", None)
    household.created_by = getattr(current_user, "id", None)
    db.add(household)
    safe_commit(db)
    db.refresh(household)
    return household


def update_household(
    db: Session, household: Household, payload, data_scope: OrgScopeFilter
) -> Household:
    """部分更新户档案（村变更 / 编号变更时重新校验）。"""
    data = payload.model_dump(exclude_unset=True)
    target_village_id = data.get("supported_village_id", household.supported_village_id)
    if "supported_village_id" in data and target_village_id != household.supported_village_id:
        load_village(db, data_scope, target_village_id)
    if "household_code" in data or "supported_village_id" in data:
        _ensure_household_code_unique(
            db,
            target_village_id,
            data.get("household_code", household.household_code),
            exclude_id=household.id,
        )
    for key, value in data.items():
        setattr(household, key, value)
    safe_commit(db)
    db.refresh(household)
    return household


def soft_delete_household(db: Session, household: Household) -> None:
    """软删户档案（is_active=False；成员与风险记录保留以便审计）。"""
    household.is_active = False
    household.deleted_at = _utcnow()
    safe_commit(db)


# ════════════════════════════════════════════════════════════════════
#  成员 CRUD
# ════════════════════════════════════════════════════════════════════

def list_members(db: Session, data_scope: OrgScopeFilter, household: Household) -> list:
    """某户有效成员列表（按创建顺序）。"""
    members = (
        member_base_query(db, data_scope, household.id)
        .order_by(HouseholdMember.id.asc())
        .all()
    )
    return [serialize_member(member) for member in members]


def create_member(
    db: Session, household: Household, payload, current_user
) -> HouseholdMember:
    """新增家庭成员（组织/创建人随户继承）。"""
    member = HouseholdMember(**payload.model_dump())
    member.household_id = household.id
    member.organization_id = household.organization_id
    member.created_by = getattr(current_user, "id", None)
    db.add(member)
    safe_commit(db)
    db.refresh(member)
    return member


def update_member(db: Session, member: HouseholdMember, payload) -> HouseholdMember:
    """部分更新家庭成员。"""
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, key, value)
    safe_commit(db)
    db.refresh(member)
    return member


def soft_delete_member(db: Session, member: HouseholdMember) -> None:
    """软删家庭成员。"""
    member.is_active = False
    member.deleted_at = _utcnow()
    safe_commit(db)


# ════════════════════════════════════════════════════════════════════
#  风险记录
# ════════════════════════════════════════════════════════════════════

def list_risk_records(
    db: Session, data_scope: OrgScopeFilter, household: Household
) -> list:
    """某户风险记录（按发现时间倒序）。"""
    records = (
        risk_record_base_query(db, data_scope, household_id=household.id)
        .order_by(HouseholdRiskRecord.detected_at.desc(), HouseholdRiskRecord.id.desc())
        .all()
    )
    return [serialize_risk_record(record) for record in records]


def create_risk_record(db: Session, household: Household, payload, current_user) -> HouseholdRiskRecord:
    """登记风险记录（等级缺省继承户风险等级，状态 open）。"""
    record = HouseholdRiskRecord(
        household_id=household.id,
        risk_type=payload.risk_type,
        risk_level=payload.risk_level or household.risk_level,
        reason=payload.reason,
        detected_at=payload.detected_at or _utcnow(),
        status="open",
        organization_id=household.organization_id,
        created_by=getattr(current_user, "id", None),
    )
    db.add(record)
    safe_commit(db)
    db.refresh(record)
    return record


def close_risk_record(db: Session, record: HouseholdRiskRecord, payload) -> HouseholdRiskRecord:
    """关闭风险记录（重复关闭 → 400）。"""
    if record.status == "closed":
        raise AppError.bad_request("该风险记录已关闭")
    record.status = "closed"
    record.closed_at = _utcnow()
    record.closed_note = payload.closed_note
    safe_commit(db)
    db.refresh(record)
    return record


# ════════════════════════════════════════════════════════════════════
#  汇总回填（一户一档明细 → VillagePopulation 年度汇总）
# ════════════════════════════════════════════════════════════════════

def rollup_to_village_population(
    db: Session,
    village_id: int,
    year: Optional[int],
    current_user,
    data_scope: OrgScopeFilter,
) -> dict:
    """按户汇总回填帮扶村当年度人口数据（幂等 upsert）。

    写回字段：
    - ``total_households`` = 该村有效户数
    - ``total_population`` = 这些户的有效成员数
    - ``poverty_households`` = 脱贫户数
    - ``unstable_poverty_households`` = 监测户数（``VillagePopulation`` 无同名列，
      按"监测户≈脱贫不稳定户"语义映射；返回摘要里同时给出 ``monitoring_households``）
    """
    village = load_village(db, data_scope, village_id)
    target_year = year if year is not None else datetime.now(timezone.utc).year
    base = household_base_query(db, data_scope).filter(
        Household.supported_village_id == village.id
    )
    household_ids = [row[0] for row in base.with_entities(Household.id).all()]
    total_households = len(household_ids)
    total_population = 0
    if household_ids:
        total_population = int(
            db.query(func.count(HouseholdMember.id))
            .filter(
                HouseholdMember.household_id.in_(household_ids),
                HouseholdMember.is_active == True,  # noqa: E712
            )
            .scalar()
            or 0
        )
    poverty_households = base.filter(Household.household_type == "poverty").count()
    monitoring_households = base.filter(Household.household_type == "monitor").count()

    row = (
        db.query(VillagePopulation)
        .filter(
            VillagePopulation.supported_village_id == village.id,
            VillagePopulation.year == target_year,
        )
        .first()
    )
    created = row is None
    if created:
        row = VillagePopulation(supported_village_id=village.id, year=target_year)
        db.add(row)
    row.total_households = total_households
    row.total_population = total_population
    row.poverty_households = poverty_households
    row.unstable_poverty_households = monitoring_households
    safe_commit(db)
    db.refresh(row)
    logger.info(
        "一户一档汇总回填完成 village_id=%s year=%s operator_id=%s",
        village.id,
        target_year,
        getattr(current_user, "id", None),
    )
    return {
        "village_id": village.id,
        "village_name": village.village_name,
        "year": target_year,
        "total_households": total_households,
        "total_population": total_population,
        "poverty_households": poverty_households,
        "monitoring_households": monitoring_households,
        "created": created,
        "written_fields": [
            "total_households",
            "total_population",
            "poverty_households",
            "unstable_poverty_households",
        ],
    }


# ════════════════════════════════════════════════════════════════════
#  台账导出（数据组装 + xlsx/csv 字节）
# ════════════════════════════════════════════════════════════════════

def _export_value(value):
    """导出单元格归一：空 → ""；布尔 → 是/否；预警列表 → 文案拼接。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return "；".join(str(item.get("message", "")) for item in value)
    return value


def household_export_data(
    db: Session,
    data_scope: OrgScopeFilter,
    *,
    village_id: Optional[int] = None,
    risk_level: Optional[str] = None,
    include_deleted: bool = False,
    today: Optional[date] = None,
) -> tuple:
    """组装台账导出 (headers, rows)。"""
    query = household_base_query(db, data_scope, include_deleted=include_deleted)
    query = apply_household_filters(query, village_id=village_id, risk_level=risk_level)
    households = query.order_by(Household.id.asc()).all()
    items = enrich_households(db, households, today=today)
    headers = [header for header, _field in EXPORT_COLUMNS]
    rows = [
        [_export_value(item.get(field)) for _header, field in EXPORT_COLUMNS]
        for item in items
    ]
    return headers, rows


def build_csv_bytes(headers: list, rows: list) -> bytes:
    """生成 CSV（utf-8-sig，便于 Excel 直接打开中文）。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def build_xlsx_bytes(headers: list, rows: list) -> bytes:
    """生成 XLSX（openpyxl，单 sheet）。"""
    # P2-4 启动优化：openpyxl（连带 numpy）不得在 import 期加载 → 函数内惰性导入
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "一户一档"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
