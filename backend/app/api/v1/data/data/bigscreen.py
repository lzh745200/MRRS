"""汇报大屏 API（对象维度筛选）。

提供两类能力：

- ``GET /bigscreen/filters``：返回当前数据域内可筛选的帮扶村 / 帮扶学校 / 帮扶单位
  （单位是自由文本 facet，来源为村、学校、项目、结对记录四路并集）；
- ``GET /bigscreen/overview``：按 全局 / 帮扶村 / 帮扶学校 / 帮扶单位 四个维度返回
  大屏所需的 KPI、经费趋势、项目状态、年度对比、排行、人物榜、对象档案与明细。

数据域沿用组织树可见性模型（``get_org_scope``），与 dashboard 的统计 helper 同口径；
金额统一 ``round(x, 2)``，字符串空值统一输出 "—"。本模块只读，不做任何写操作。
"""

import logging
from datetime import datetime
from typing import Any, Optional, cast as type_cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.fund import Fund
from app.models.pairing import PairingRecord, VisitRecord
from app.models.project import Project
from app.models.school import (
    School,
    SchoolProject,
    ScholarshipStudent,
)
from app.models.supported_village import (
    EducationSupport,
    IndustrySupport,
    InfrastructureImprovement,
    MedicalSupport,
    PartyBuildingSupport,
    SupportedVillage,
    VillageIncome,
    VillagePopulation,
)
from .dashboard import (
    _apply_project_scope,
    _build_yearly_trends,
    _query_fund_stats,
    _query_project_approval_stats,
    _query_village_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bigscreen", tags=["汇报大屏"])

# ── 常量 ────────────────────────────────────────────────────────────
_ALLOWED_SCOPE_TYPES = ("all", "village", "school", "unit")
_RANKING_LIMIT = 8
_LEADER_LIMIT = 5
_DETAIL_LIMIT = 5
_COVERAGE_NAME_LIMIT = 30

_PROJECT_STATUS_ORDER = ("completed", "approved", "in_progress", "pending")
_PROJECT_STATUS_LABELS = {
    "completed": "已完成",
    "approved": "已审批",
    "in_progress": "进行中",
    "pending": "待审批",
}
_SCHOOL_PHASE_ORDER = ("research", "approval", "implementation", "acceptance", "completed")
_SCHOOL_PHASE_LABELS = {
    "research": "调研",
    "approval": "立项审批",
    "implementation": "实施",
    "acceptance": "验收",
    "completed": "已完成",
}
# 库内 SQLEnum 以枚举名（大写）落库；cast 成字符串后需归一为小写枚举值
_SCHOOL_PHASE_VALUE_ALIASES = {
    "RESEARCH": "research",
    "APPROVAL": "approval",
    "IMPLEMENTATION": "implementation",
    "ACCEPTANCE": "acceptance",
    "COMPLETED": "completed",
}
_FUND_STATUS_LABELS = {
    "pending": "待审批",
    "planned": "已规划",
    "approved": "已审批",
    "rejected": "已驳回",
    "allocated": "已拨付",
    "in_use": "使用中",
    "completed": "已完成",
    "audited": "已审计",
}
_SUPPORT_STATUS_LABELS = {"active": "帮扶中", "inactive": "未帮扶", "completed": "已完成"}
_TRANSITION_STATUS_LABELS = {
    "none": "无",
    "entering": "进入过渡期",
    "in_transition": "过渡期中",
    "exiting": "退出过渡期",
    "completed": "过渡期结束",
}
# 村档案的区域标记标签：(字段名, 中文标签)
_VILLAGE_TAG_FIELDS = (
    ("is_three_regions", "三区三州"),
    ("is_border_area", "边疆地区"),
    ("is_ethnic_area", "民族地区"),
    ("is_revolutionary_area", "革命地区"),
    ("is_key_county", "重点帮扶县"),
    ("is_provincial_demo", "省级示范"),
    ("is_hundred_village_demo", "百村示范"),
    ("is_tiered_development", "梯次振兴"),
)
# 帮扶投入年度子表：(模型, 档案标签, 投入字段名)
_SUPPORT_INVESTMENT_FIELDS = (
    (IndustrySupport, "产业投入(万元)", "investment"),
    (InfrastructureImprovement, "基础设施投入(万元)", "investment"),
    (PartyBuildingSupport, "党建投入(万元)", "investment"),
    (MedicalSupport, "医疗投入(万元)", "investment"),
    (EducationSupport, "教育投入(万元)", "investment"),
)


# ════════════════════════════════════════════════════════════════════
#  格式化与标签工具
# ════════════════════════════════════════════════════════════════════

def _round_amount(value) -> float:
    """金额统一保留两位小数（None 视为 0）。"""
    return round(float(value or 0), 2)


def _text(value) -> str:
    """字符串空值兜底为 "—"。"""
    if value is None or value == "":
        return "—"
    return str(value)


def _format_completeness(value) -> str:
    """数据完整度 0~1 → 百分比字符串；None → "—"。"""
    if value is None:
        return "—"
    return f"{round(float(value) * 100, 1)}%"


def _format_location(*parts) -> str:
    """省/市/县/乡镇拼接（缺失项跳过）。"""
    return "".join(str(part) for part in parts if part)


def _format_yes_no(flag) -> str:
    """布尔标记 → 是/否。"""
    return "是" if flag else "否"


def _format_date(value) -> str:
    """日期 → YYYY-MM-DD；空值 → "—"。"""
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d")


def _format_period(start, end) -> str:
    """帮扶起止日期展示。"""
    if start is None and end is None:
        return "—"
    return f"{_format_date(start)} 至 {_format_date(end)}"


def _status_key(value) -> str:
    """状态值归一为字符串 key（None/空串 → unset）。"""
    if value is None or value == "":
        return "unset"
    return str(value)


def _enum_key(value) -> str:
    """枚举成员 / 普通字符串归一为字符串 key。"""
    return _status_key(getattr(value, "value", value))


def _project_status_label(key: str) -> str:
    """项目状态中文标签（未知状态回退原始 key）。"""
    if key == "unset":
        return "未设置"
    return _PROJECT_STATUS_LABELS.get(key, key)


def _school_phase_label(key: str) -> str:
    """学校项目阶段中文标签（未知阶段回退原始 key）。"""
    if key == "unset":
        return "未设置"
    return _SCHOOL_PHASE_LABELS.get(key, key)


def _phase_key(value) -> str:
    """学校项目阶段归一：兼容库内枚举名（大写）与未知脏值。"""
    key = _status_key(value)
    return _SCHOOL_PHASE_VALUE_ALIASES.get(key, key)


def _fund_status_label(key: str) -> str:
    """经费状态中文标签（未知状态回退原始 key）。"""
    if key == "unset":
        return "未设置"
    return _FUND_STATUS_LABELS.get(key, key)


def _support_status_label(value) -> str:
    """学校帮扶状态中文标签。"""
    key = _enum_key(value)
    if key == "unset":
        return "未设置"
    return _SUPPORT_STATUS_LABELS.get(key, key)


def _transition_status_label(value) -> str:
    """村过渡状态中文标签。"""
    key = _status_key(value)
    if key == "unset":
        return "未设置"
    return _TRANSITION_STATUS_LABELS.get(key, key)


def _row_value(row, attr: str) -> str:
    """年度数据行字段展示值（行缺失 / 字段为空 → "—"）。"""
    if row is None:
        return "—"
    value = getattr(row, attr, None)
    if value is None:
        return "—"
    if isinstance(value, float):
        return str(round(value, 2))
    return str(value)


def _row_int(row, attr: str) -> int:
    """年度数据行整数取值（行缺失 / 字段为空 → 0）。"""
    if row is None:
        return 0
    return int(getattr(row, attr, None) or 0)


def _project_status_items(counts: dict) -> list:
    """项目状态固定四键 + 未知状态回退原始 key。"""
    items = [
        {"key": key, "label": _PROJECT_STATUS_LABELS[key], "value": int(counts.get(key, 0))}
        for key in _PROJECT_STATUS_ORDER
    ]
    for key in sorted(counts):
        if key in _PROJECT_STATUS_LABELS:
            continue
        items.append({"key": key, "label": _project_status_label(key), "value": int(counts[key])})
    return items


def _school_phase_items(counts: dict) -> list:
    """学校项目阶段固定五键 + 未知/未设置阶段回退。"""
    items = [
        {"key": key, "label": _SCHOOL_PHASE_LABELS[key], "value": int(counts.get(key, 0))}
        for key in _SCHOOL_PHASE_ORDER
    ]
    for key in sorted(counts):
        if key in _SCHOOL_PHASE_LABELS:
            continue
        items.append({"key": key, "label": _school_phase_label(key), "value": int(counts[key])})
    return items


# ════════════════════════════════════════════════════════════════════
#  经费 / 项目 / 结对聚合查询（全部显式软删过滤 + 数据域过滤）
# ════════════════════════════════════════════════════════════════════

def _year_window(years: int) -> list:
    """最近 N 年的年份列表（含当前年）。"""
    current_year = datetime.now().year
    return list(range(current_year - years + 1, current_year + 1))


def _fund_trend_lists(year_list: list, fund_rows: list, project_rows: list):
    """按年聚合行 → (fund_trend, yearly) 两个前端固定结构。

    ``fund_rows`` 为 (year, sum(planned), sum(allocated), count) 行，
    ``project_rows`` 为 (year, count) 行；year 为 None 的行跳过。
    """
    fund_by_year = {}
    for year, planned, actual, count in fund_rows:
        if year is None:
            continue
        fund_by_year[int(year)] = (_round_amount(planned), _round_amount(actual), int(count or 0))
    project_by_year = {}
    for year, count in project_rows:
        if year is None:
            continue
        project_by_year[int(year)] = int(count or 0)
    fund_trend = []
    yearly = []
    for year in year_list:
        planned, actual, fund_count = fund_by_year.get(year, (0.0, 0.0, 0))
        fund_trend.append({"year": year, "planned": planned, "actual": actual})
        yearly.append(
            {"year": year, "project_count": project_by_year.get(year, 0), "fund_count": fund_count}
        )
    return fund_trend, yearly


def _scoped_fund_query(db: Session, data_scope: OrgScopeFilter, conditions: list):
    """数据域内的有效经费查询（conditions 之间为 OR 关系）。"""
    query = db.query(Fund).filter(Fund.is_active == True, or_(*conditions))  # noqa: E712
    return data_scope.filter_by_org_ids(
        query, Fund.organization_id, created_by_column=Fund.created_by
    )


def _sum_fund_amount(db: Session, data_scope: OrgScopeFilter, conditions: list) -> float:
    """经费 amount 合计（万元）。"""
    amount = (
        _scoped_fund_query(db, data_scope, conditions)
        .with_entities(func.coalesce(func.sum(Fund.amount), 0))
        .scalar()
    )
    return _round_amount(amount)


def _fund_year_rows(db: Session, data_scope: OrgScopeFilter, conditions: list) -> list:
    """经费按 Fund.year 聚合行（year, planned, actual, count）。"""
    year_col = Fund.year
    return (
        _scoped_fund_query(db, data_scope, conditions)
        .with_entities(
            year_col,
            func.coalesce(func.sum(Fund.planned_amount), 0),
            func.coalesce(func.sum(Fund.allocated_amount), 0),
            func.count(Fund.id),
        )
        .group_by(year_col)
        .all()
    )


def _fund_detail_rows(
    db: Session, data_scope: OrgScopeFilter, conditions: list, limit: int = _DETAIL_LIMIT
) -> list:
    """经费明细（按年度倒序取前 N 条）。"""
    funds = (
        _scoped_fund_query(db, data_scope, conditions)
        .order_by(Fund.year.desc(), Fund.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "name": _text(fund.name),
            "year": fund.year,
            "status": _status_key(fund.status),
            "label": _fund_status_label(_status_key(fund.status)),
            "amount": _round_amount(fund.amount),
        }
        for fund in funds
    ]


def _scoped_project_query(
    db: Session, data_scope: OrgScopeFilter, entities: tuple, conditions: list
):
    """数据域内的有效项目查询（排除已取消项目）。"""
    query = db.query(*entities).filter(
        Project.is_active == True,  # noqa: E712
        Project.status != "cancelled",
        *conditions,
    )
    return _apply_project_scope(query, data_scope)


def _count_projects(db: Session, data_scope: OrgScopeFilter, conditions: list) -> int:
    """有效项目计数。"""
    query = _scoped_project_query(db, data_scope, (func.count(Project.id),), conditions)
    return int(query.scalar() or 0)


def _project_status_counts(db: Session, data_scope: OrgScopeFilter, conditions: list) -> dict:
    """项目状态计数（key 归一字符串）。"""
    rows = (
        _scoped_project_query(
            db, data_scope, (Project.status, func.count(Project.id)), conditions
        )
        .group_by(Project.status)
        .all()
    )
    return {_status_key(status): int(count) for status, count in rows}


def _project_year_rows(db: Session, data_scope: OrgScopeFilter, conditions: list) -> list:
    """项目按 start_date 年份聚合行（start_date 为空的记录自然被 group_by 排除）。"""
    year_col = func.strftime("%Y", Project.start_date)
    return (
        _scoped_project_query(db, data_scope, (year_col, func.count(Project.id)), conditions)
        .group_by(year_col)
        .all()
    )


def _project_rankings(
    db: Session, data_scope: OrgScopeFilter, conditions: list, limit: int = _RANKING_LIMIT
) -> list:
    """项目排行（按实际投入倒序）。"""
    rows = (
        _scoped_project_query(db, data_scope, (Project.name, Project.actual_cost), conditions)
        .order_by(Project.actual_cost.desc(), Project.id.asc())
        .limit(limit)
        .all()
    )
    return [{"name": name, "score": _round_amount(cost)} for name, cost in rows]


def _project_leaders(
    db: Session, data_scope: OrgScopeFilter, conditions: list, limit: int = _LEADER_LIMIT
) -> list:
    """项目负责人榜（按实际投入倒序，person 兜底 responsible_person → leader）。"""
    rows = (
        _scoped_project_query(
            db,
            data_scope,
            (Project.name, Project.responsible_person, Project.leader, Project.responsible_unit),
            conditions,
        )
        .order_by(Project.actual_cost.desc(), Project.id.asc())
        .limit(limit)
        .all()
    )
    return [{"name": row[0], "person": row[1] or row[2] or "", "unit": row[3]} for row in rows]


def _project_detail_rows(
    db: Session, data_scope: OrgScopeFilter, conditions: list, limit: int = _DETAIL_LIMIT
) -> list:
    """项目明细（按实际投入倒序取前 N 条）。"""
    projects = (
        _scoped_project_query(db, data_scope, (Project,), conditions)
        .order_by(Project.actual_cost.desc(), Project.id.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "name": project.name,
            "status": _status_key(project.status),
            "label": _project_status_label(_status_key(project.status)),
            "amount": _round_amount(project.actual_cost),
            "person": project.responsible_person or project.leader or "",
        }
        for project in projects
    ]


def _pairing_id_query(db: Session, data_scope: OrgScopeFilter, conditions: list):
    """数据域内的有效结对记录 id 查询。"""
    query = db.query(PairingRecord.id).filter(
        PairingRecord.is_active == True,  # noqa: E712
        *conditions,
    )
    return data_scope.filter_by_org_ids(
        query, PairingRecord.organization_id, created_by_column=PairingRecord.created_by
    )


def _pairing_stats(db: Session, data_scope: OrgScopeFilter, conditions: list) -> tuple:
    """结对记录（总数 / 进行中）与走访次数。"""
    ids_query = _pairing_id_query(db, data_scope, conditions)
    total = int(ids_query.count() or 0)
    active = int(ids_query.filter(PairingRecord.status == "active").count() or 0)
    visits = (
        db.query(func.count(VisitRecord.id))
        .filter(
            VisitRecord.is_active == True,  # noqa: E712
            VisitRecord.pairing_id.in_(ids_query),
        )
        .scalar()
        or 0
    )
    return total, active, int(visits)


def _pairing_section(pairing_stats: tuple) -> dict:
    """档案中的「结对与走访」区块。"""
    total, active, visits = pairing_stats
    return {
        "title": "结对与走访",
        "items": [
            {"label": "结对记录数", "value": str(total)},
            {"label": "进行中", "value": str(active)},
            {"label": "走访次数", "value": str(visits)},
        ],
    }


# ════════════════════════════════════════════════════════════════════
#  filters：对象筛选项
# ════════════════════════════════════════════════════════════════════

def _collect_village_filters(db: Session, data_scope: OrgScopeFilter) -> list:
    """可筛选帮扶村（仅有效村，按名称升序）。"""
    query = db.query(
        SupportedVillage.id,
        SupportedVillage.village_name,
        SupportedVillage.county,
        SupportedVillage.support_unit,
    ).filter(SupportedVillage.is_active == True)  # noqa: E712
    query = data_scope.filter_by_org_ids(
        query, SupportedVillage.organization_id, created_by_column=SupportedVillage.created_by
    )
    rows = query.order_by(SupportedVillage.village_name.asc(), SupportedVillage.id.asc()).all()
    return [
        {"id": row[0], "name": row[1], "county": row[2], "support_unit": row[3]} for row in rows
    ]


def _collect_school_filters(db: Session, data_scope: OrgScopeFilter) -> list:
    """可筛选帮扶学校（仅有效学校，按名称升序）。"""
    query = db.query(
        School.id,
        School.name,
        School.district,
        School.support_unit,
    ).filter(School.is_active == True)  # noqa: E712
    query = data_scope.filter_by_org_ids(
        query, School.organization_id, created_by_column=School.created_by
    )
    rows = query.order_by(School.name.asc(), School.id.asc()).all()
    return [
        {"id": row[0], "name": row[1], "district": row[2], "support_unit": row[3]} for row in rows
    ]


def _bump_unit_count(units: dict, raw_name, field: str) -> None:
    """把一路来源的命中累加到单位 facet（空名一律排除）。"""
    name = (str(raw_name) if raw_name is not None else "").strip()
    if not name:
        return
    item = units.setdefault(
        name,
        {"village_count": 0, "school_count": 0, "project_count": 0, "pairing_count": 0},
    )
    item[field] += 1


def _collect_unit_filters(db: Session, data_scope: OrgScopeFilter) -> list:
    """可筛选帮扶单位 facet：村 / 学校 / 项目 / 结对四路并集，同名合并计数。"""
    units: dict[Any, Any] = {}

    village_query = db.query(SupportedVillage.support_unit).filter(
        SupportedVillage.is_active == True  # noqa: E712
    )
    village_query = data_scope.filter_by_org_ids(
        village_query, SupportedVillage.organization_id, created_by_column=SupportedVillage.created_by
    )
    for (name,) in village_query.all():
        _bump_unit_count(units, name, "village_count")

    school_query = db.query(School.support_unit).filter(School.is_active == True)  # noqa: E712
    school_query = data_scope.filter_by_org_ids(
        school_query, School.organization_id, created_by_column=School.created_by
    )
    for (name,) in school_query.all():
        _bump_unit_count(units, name, "school_count")

    project_query = db.query(Project.responsible_unit).filter(
        Project.is_active == True,  # noqa: E712
        Project.status != "cancelled",
    )
    project_query = _apply_project_scope(project_query, data_scope)
    for (name,) in project_query.all():
        _bump_unit_count(units, name, "project_count")

    pairing_query = db.query(PairingRecord.subject_name).filter(
        PairingRecord.subject_type == "unit",
        PairingRecord.is_active == True,  # noqa: E712
    )
    pairing_query = data_scope.filter_by_org_ids(
        pairing_query, PairingRecord.organization_id, created_by_column=PairingRecord.created_by
    )
    for (name,) in pairing_query.all():
        _bump_unit_count(units, name, "pairing_count")

    items = [{"name": name, **counts} for name, counts in units.items()]
    items.sort(
        key=lambda item: (
            -(item["village_count"] + item["school_count"] + item["project_count"]),
            -item["pairing_count"],
            item["name"],
        )
    )
    return items


@router.get("/filters", summary="汇报大屏对象筛选项")
async def get_bigscreen_filters(
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """返回当前数据域内可筛选的帮扶村 / 帮扶学校 / 帮扶单位列表。"""
    try:
        data = {
            "villages": _collect_village_filters(db, data_scope),
            "schools": _collect_school_filters(db, data_scope),
            "units": _collect_unit_filters(db, data_scope),
        }
    except Exception as exc:
        logger.exception("汇报大屏筛选项查询失败: %s", exc)
        raise AppError("筛选项查询失败，请稍后重试", 500) from exc
    return success_response(data=data, message="筛选项已获取")


# ════════════════════════════════════════════════════════════════════
#  overview：对象概览
# ════════════════════════════════════════════════════════════════════

def _village_fund_rankings(
    db: Session, data_scope: OrgScopeFilter, village_ids: Optional[list]
) -> list:
    """村经费排行（SUM(Fund.allocated_amount) 降序前 N）。"""
    query = (
        db.query(SupportedVillage.village_name, func.coalesce(func.sum(Fund.allocated_amount), 0))
        .join(Fund, Fund.village_id == SupportedVillage.id)
        .filter(
            SupportedVillage.is_active == True,  # noqa: E712
            Fund.is_active == True,  # noqa: E712
        )
    )
    if village_ids is not None:
        query = query.filter(SupportedVillage.id.in_(village_ids))
    query = data_scope.filter_by_org_ids(
        query, SupportedVillage.organization_id, created_by_column=SupportedVillage.created_by
    )
    query = data_scope.filter_by_org_ids(
        query, Fund.organization_id, created_by_column=Fund.created_by
    )
    rows = (
        query.group_by(SupportedVillage.id, SupportedVillage.village_name)
        .order_by(func.sum(Fund.allocated_amount).desc(), SupportedVillage.village_name.asc())
        .limit(_RANKING_LIMIT)
        .all()
    )
    return [{"name": name, "score": _round_amount(score)} for name, score in rows]


def _collect_all_scope(db: Session, data_scope: OrgScopeFilter, years: int) -> dict:
    """全局维度：直接复用 dashboard 的统计 helper 与年度趋势聚合。"""
    village_stats = _query_village_stats(db, data_scope)
    fund_stats = _query_fund_stats(db, data_scope)
    project_stats = _query_project_approval_stats(db, data_scope)
    trend_data = _build_yearly_trends(db, data_scope, years)
    fund_trend = [
        {"year": row["year"], "planned": row["total_planned"], "actual": row["total_actual"]}
        for row in trend_data["trends"]
    ]
    yearly = [
        {
            "year": row["year"],
            "project_count": row["project_count"],
            "fund_count": row["fund_count"],
        }
        for row in trend_data["trends"]
    ]
    kpis = [
        {
            "key": "villages",
            "label": "帮扶村",
            "value": int(village_stats["total_villages"]),
            "unit": "个",
        },
        {
            "key": "projects",
            "label": "帮扶项目",
            "value": int(project_stats["total_projects"]),
            "unit": "个",
        },
        {
            "key": "schools",
            "label": "帮扶学校",
            "value": int(village_stats["total_schools"]),
            "unit": "所",
        },
        {
            "key": "completeness",
            "label": "完成率",
            "value": _format_completeness(project_stats["data_completeness"]),
            "unit": "",
        },
        {
            "key": "funds",
            "label": "经费总额",
            "value": fund_stats["total_funds"],
            "unit": "万元",
        },
    ]
    return {
        "scope": {"type": "all", "id": None, "name": "全局", "subtitle": "全部帮扶对象"},
        "kpis": kpis,
        "fund_trend": fund_trend,
        "project_status": _project_status_items(project_stats["projects_by_status"]),
        "yearly": yearly,
        "rankings": _village_fund_rankings(db, data_scope, None),
        "leaders": _project_leaders(db, data_scope, []),
        "profile": None,
        "details": None,
    }


# ── 村维度 ──────────────────────────────────────────────────────────

def _load_scoped_village(db: Session, data_scope: OrgScopeFilter, village_id: int) -> SupportedVillage:
    """按数据域加载有效帮扶村；不存在或越权 → 404。"""
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


def _latest_village_population(db: Session, village_id: int) -> Optional[VillagePopulation]:
    """该村最新年度人口数据（无数据 → None）。"""
    return (
        db.query(VillagePopulation)
        .filter(VillagePopulation.supported_village_id == village_id)
        .order_by(VillagePopulation.year.desc())
        .first()
    )


def _latest_village_income(db: Session, village_id: int) -> Optional[VillageIncome]:
    """该村最新年度收入数据（无数据 → None）。"""
    return (
        db.query(VillageIncome)
        .filter(VillageIncome.supported_village_id == village_id)
        .order_by(VillageIncome.year.desc())
        .first()
    )


def _annual_year(population, income) -> int:
    """人口 / 收入数据的展示年份（两者取最新）。"""
    if population is not None and income is not None:
        return max(population.year, income.year)
    if population is not None:
        return population.year
    return income.year


def _latest_support_investments(db: Session, village_id: int) -> tuple:
    """帮扶投入类年度子表的最新年度行。

    Returns:
        (latest_year, {模型: 该年度行})；无任何年度数据时 (None, {})。
    """
    rows: list[tuple[Any, Any]] = []
    for model, _label, _attr in _SUPPORT_INVESTMENT_FIELDS:
        row = (
            db.query(model)
            .filter(model.supported_village_id == village_id)
            .order_by(model.year.desc())
            .first()
        )
        if row is not None:
            rows.append((model, row))
    if not rows:
        return None, {}
    latest_year = max(row.year for _model, row in rows)
    latest_rows = {model: row for model, row in rows if row.year == latest_year}
    return latest_year, latest_rows


def _village_basic_section(village: SupportedVillage) -> dict:
    """村档案「基础信息」区块。"""
    return {
        "title": "基础信息",
        "items": [
            {
                "label": "所属区域",
                "value": _text(
                    _format_location(
                        village.province, village.city, village.county, village.township
                    )
                ),
            },
            {"label": "帮扶单位", "value": _text(village.support_unit)},
            {"label": "部门单位", "value": _text(village.department)},
            {"label": "振兴梯队", "value": _format_yes_no(village.is_revitalization_tier)},
            {"label": "过渡状态", "value": _transition_status_label(village.transition_status)},
        ],
    }


def _village_population_section(population, income) -> dict:
    """村档案「人口与收入（最新年度）」区块。"""
    year = _annual_year(population, income)
    return {
        "title": f"人口与收入（{year}年）",
        "items": [
            {"label": "总户数", "value": _row_value(population, "total_households")},
            {"label": "总人口", "value": _row_value(population, "total_population")},
            {"label": "常住人口", "value": _row_value(population, "resident_population")},
            {"label": "脱贫人口", "value": _row_value(population, "poverty_population")},
            {"label": "村人均纯收入(万元)", "value": _row_value(income, "per_capita_income")},
            {"label": "村集体收入(万元)", "value": _row_value(income, "collective_income")},
        ],
    }


def _village_investment_section(village: SupportedVillage, support_year, support_rows: dict) -> dict:
    """村档案「帮扶投入（最新年度）」区块。"""
    if support_year is None:
        title = "帮扶投入"
    else:
        title = f"帮扶投入（{support_year}年）"
    items = [
        {"label": "专项投入(万元)", "value": _row_value(village, "transition_fund_military_total")},
        {"label": "协调地方投入(万元)", "value": _row_value(village, "transition_fund_local_total")},
    ]
    if support_year is not None:
        for model, label, attr in _SUPPORT_INVESTMENT_FIELDS:
            items.append({"label": label, "value": _row_value(support_rows.get(model), attr)})
    return {"title": title, "items": items}


def _village_tags(village: SupportedVillage) -> list:
    """村档案区域标记 tag（无标记时返回空列表）。"""
    items = [label for attr, label in _VILLAGE_TAG_FIELDS if getattr(village, attr, False)]
    if not items:
        return []
    return [{"label": "区域标记", "items": items}]


def _build_village_profile(
    db: Session,
    village: SupportedVillage,
    population,
    income,
    pairing_stats: tuple,
) -> dict:
    """村对象档案（sections / tags）。"""
    sections = [_village_basic_section(village)]
    if population is not None or income is not None:
        sections.append(_village_population_section(population, income))
    support_year, support_rows = _latest_support_investments(db, type_cast(int, village.id))
    sections.append(_village_investment_section(village, support_year, support_rows))
    sections.append(_pairing_section(pairing_stats))
    return {
        "title": f"{village.village_name} · 对象档案",
        "sections": sections,
        "tags": _village_tags(village),
    }


def _collect_village_scope(
    db: Session, data_scope: OrgScopeFilter, village_id: int, years: int
) -> dict:
    """帮扶村维度概览。"""
    village = _load_scoped_village(db, data_scope, village_id)
    population = _latest_village_population(db, type_cast(int, village.id))
    income = _latest_village_income(db, type_cast(int, village.id))
    pairing_stats = _pairing_stats(
        db,
        data_scope,
        [PairingRecord.partner_type == "village", PairingRecord.village_id == village.id],
    )
    fund_conditions = [Fund.village_id == village.id]
    project_conditions = [Project.village_id == village.id]
    fund_trend, yearly = _fund_trend_lists(
        _year_window(years),
        _fund_year_rows(db, data_scope, fund_conditions),
        _project_year_rows(db, data_scope, project_conditions),
    )
    kpis = [
        {
            "key": "population",
            "label": "总人口",
            "value": _row_int(population, "total_population"),
            "unit": "人",
        },
        {
            "key": "households",
            "label": "总户数",
            "value": _row_int(population, "total_households"),
            "unit": "户",
        },
        {
            "key": "projects",
            "label": "帮扶项目",
            "value": _count_projects(db, data_scope, project_conditions),
            "unit": "个",
        },
        {
            "key": "funds",
            "label": "经费总额",
            "value": _sum_fund_amount(db, data_scope, fund_conditions),
            "unit": "万元",
        },
        {"key": "visits", "label": "走访次数", "value": pairing_stats[2], "unit": "次"},
    ]
    details = {
        "projects": _project_detail_rows(db, data_scope, project_conditions),
        "funds": _fund_detail_rows(db, data_scope, fund_conditions),
        "pairing": {
            "total": pairing_stats[0],
            "active": pairing_stats[1],
            "visits": pairing_stats[2],
        },
    }
    return {
        "scope": {
            "type": "village",
            "id": village.id,
            "name": village.village_name,
            "subtitle": _format_location(
                village.province, village.city, village.county, village.township
            ),
        },
        "kpis": kpis,
        "fund_trend": fund_trend,
        "project_status": _project_status_items(
            _project_status_counts(db, data_scope, project_conditions)
        ),
        "yearly": yearly,
        "rankings": _project_rankings(db, data_scope, project_conditions),
        "leaders": _project_leaders(db, data_scope, project_conditions),
        "profile": _build_village_profile(db, village, population, income, pairing_stats),
        "details": details,
    }


# ── 学校维度 ────────────────────────────────────────────────────────

def _load_scoped_school(db: Session, data_scope: OrgScopeFilter, school_id: int) -> School:
    """按数据域加载有效学校；不存在或越权 → 404。"""
    query = db.query(School).filter(
        School.id == school_id,
        School.is_active == True,  # noqa: E712
    )
    query = data_scope.filter_by_org_ids(
        query, School.organization_id, created_by_column=School.created_by
    )
    school = query.first()
    if school is None:
        raise AppError.not_found("帮扶学校")
    return school


def _school_project_year_rows(db: Session, school_id: int) -> list:
    """学校项目按 start_date 年份聚合行。"""
    year_col = func.strftime("%Y", SchoolProject.start_date)
    return (
        db.query(year_col, func.count(SchoolProject.id))
        .filter(SchoolProject.school_id == school_id)
        .group_by(year_col)
        .all()
    )


def _load_school_projects(db: Session, school_id: int) -> list:
    """学校项目行（按实际投入倒序）。

    阶段列用 ``cast(... AS String)`` 读取：``SchoolProject.phase`` 是 SQLEnum，
    历史上手工修复/旧版本写入的未知阶段值直接经 ORM 读取会抛 LookupError，
    把整块大屏打成 500；先转字符串再在展示层做「未知回退原始 key」。
    """
    phase_col = cast(SchoolProject.phase, String)
    return (
        db.query(
            SchoolProject.name,
            phase_col.label("phase"),
            SchoolProject.category,
            SchoolProject.budget,
            SchoolProject.actual_cost,
        )
        .filter(SchoolProject.school_id == school_id)
        .order_by(SchoolProject.actual_cost.desc(), SchoolProject.id.asc())
        .all()
    )


def _scholarship_stats(db: Session, school_id: int) -> tuple:
    """学校资助学生数 / 资助金额合计（元）。"""
    count, amount = (
        db.query(
            func.count(ScholarshipStudent.id),
            func.coalesce(func.sum(ScholarshipStudent.amount), 0),
        )
        .filter(ScholarshipStudent.school_id == school_id)
        .one()
    )
    return int(count or 0), _round_amount(amount)


def _school_project_totals(projects: list) -> tuple:
    """学校项目预算合计 / 实际投入合计（万元）。"""
    budget_total = 0.0
    actual_total = 0.0
    for _name, _phase, _category, budget, actual_cost in projects:
        budget_total += float(budget or 0)
        actual_total += float(actual_cost or 0)
    return round(budget_total, 2), round(actual_total, 2)


def _school_phase_counts(projects: list) -> dict:
    """学校项目阶段计数。"""
    counts: dict[Any, Any] = {}
    for _name, phase, _category, _budget, _actual in projects:
        key = _phase_key(phase)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _school_project_rows(projects: list, limit: int) -> list:
    """学校项目明细 / 排行 / 人物榜共用的项目行结构。"""
    return [
        {
            "name": name,
            "status": _phase_key(phase),
            "label": _school_phase_label(_phase_key(phase)),
            "amount": _round_amount(actual_cost),
            "person": category or "",
        }
        for name, phase, category, _budget, actual_cost in projects[:limit]
    ]


def _build_school_profile(
    school: School,
    project_count: int,
    budget_total: float,
    actual_total: float,
    scholarship_count: int,
    scholarship_amount: float,
    pairing_stats: tuple,
) -> dict:
    """学校对象档案（sections；无需 tag）。"""
    sections = [
        {
            "title": "基础信息",
            "items": [
                {
                    "label": "所属区域",
                    "value": _text(
                        _format_location(school.province, school.city, school.district)
                    ),
                },
                {"label": "帮扶单位", "value": _text(school.support_unit)},
                {"label": "帮扶状态", "value": _support_status_label(school.support_status)},
                {
                    "label": "帮扶起止日期",
                    "value": _format_period(school.support_start_date, school.support_end_date),
                },
            ],
        },
        {
            "title": "办学规模",
            "items": [
                {"label": "学生人数", "value": _row_value(school, "student_count")},
                {"label": "教师人数", "value": _row_value(school, "teacher_count")},
                {"label": "班级数量", "value": _row_value(school, "class_count")},
                {"label": "建校年份", "value": _row_value(school, "established_year")},
            ],
        },
        {
            "title": "助学帮扶",
            "items": [
                {"label": "学校项目数", "value": str(project_count)},
                {"label": "预算合计(万元)", "value": str(_round_amount(budget_total))},
                {"label": "实际投入合计(万元)", "value": str(_round_amount(actual_total))},
                {"label": "资助学生数", "value": str(scholarship_count)},
                {"label": "资助金额合计(元)", "value": str(_round_amount(scholarship_amount))},
            ],
        },
        _pairing_section(pairing_stats),
    ]
    return {"title": f"{school.name} · 对象档案", "sections": sections, "tags": []}


def _collect_school_scope(
    db: Session, data_scope: OrgScopeFilter, school_id: int, years: int
) -> dict:
    """帮扶学校维度概览。"""
    school = _load_scoped_school(db, data_scope, school_id)
    projects = _load_school_projects(db, type_cast(int, school.id))
    fund_conditions = [Fund.school_id == school.id]
    fund_trend, yearly = _fund_trend_lists(
        _year_window(years),
        _fund_year_rows(db, data_scope, fund_conditions),
        _school_project_year_rows(db, type_cast(int, school.id)),
    )
    pairing_stats = _pairing_stats(
        db,
        data_scope,
        [PairingRecord.partner_type == "school", PairingRecord.school_id == school.id],
    )
    scholarship_count, scholarship_amount = _scholarship_stats(db, type_cast(int, school.id))
    budget_total, actual_total = _school_project_totals(projects)
    ranking_rows = _school_project_rows(projects, _RANKING_LIMIT)
    kpis = [
        {
            "key": "students",
            "label": "学生人数",
            "value": int(school.student_count or 0),
            "unit": "人",
        },
        {
            "key": "teachers",
            "label": "教师人数",
            "value": int(school.teacher_count or 0),
            "unit": "人",
        },
        {
            "key": "classes",
            "label": "班级数量",
            "value": int(school.class_count or 0),
            "unit": "个",
        },
        {"key": "projects", "label": "学校项目数", "value": len(projects), "unit": "个"},
        {
            "key": "funds",
            "label": "经费总额",
            "value": _sum_fund_amount(db, data_scope, fund_conditions),
            "unit": "万元",
        },
    ]
    return {
        "scope": {
            "type": "school",
            "id": school.id,
            "name": school.name,
            "subtitle": _format_location(school.province, school.city, school.district),
        },
        "kpis": kpis,
        "fund_trend": fund_trend,
        "project_status": _school_phase_items(_school_phase_counts(projects)),
        "yearly": yearly,
        "rankings": [
            {"name": row["name"], "score": row["amount"]} for row in ranking_rows
        ],
        "leaders": [
            {"name": row["name"], "person": row["person"], "unit": None}
            for row in _school_project_rows(projects, _LEADER_LIMIT)
        ],
        "profile": _build_school_profile(
            school,
            len(projects),
            budget_total,
            actual_total,
            scholarship_count,
            scholarship_amount,
            pairing_stats,
        ),
        "details": {
            "projects": _school_project_rows(projects, _DETAIL_LIMIT),
            "funds": _fund_detail_rows(db, data_scope, fund_conditions),
            "pairing": {
                "total": pairing_stats[0],
                "active": pairing_stats[1],
                "visits": pairing_stats[2],
            },
        },
    }


# ── 单位维度 ────────────────────────────────────────────────────────

def _unit_village_ids(db: Session, data_scope: OrgScopeFilter, name: str) -> list:
    """单位名下帮扶村 id：村表 support_unit 命中 ∪ 结对记录命中，再按数据域收敛。"""
    direct = db.query(SupportedVillage.id).filter(
        SupportedVillage.is_active == True,  # noqa: E712
        SupportedVillage.support_unit == name,
    )
    direct = data_scope.filter_by_org_ids(
        direct, SupportedVillage.organization_id, created_by_column=SupportedVillage.created_by
    )
    paired = db.query(PairingRecord.village_id).filter(
        PairingRecord.subject_type == "unit",
        PairingRecord.subject_name == name,
        PairingRecord.is_active == True,  # noqa: E712
        PairingRecord.partner_type == "village",
        PairingRecord.village_id.isnot(None),
    )
    paired = data_scope.filter_by_org_ids(
        paired, PairingRecord.organization_id, created_by_column=PairingRecord.created_by
    )
    candidate_ids = {row[0] for row in direct.all()} | {row[0] for row in paired.all()}
    if not candidate_ids:
        return []
    villages = db.query(SupportedVillage.id).filter(
        SupportedVillage.is_active == True,  # noqa: E712
        SupportedVillage.id.in_(candidate_ids),
    )
    villages = data_scope.filter_by_org_ids(
        villages, SupportedVillage.organization_id, created_by_column=SupportedVillage.created_by
    )
    return sorted(row[0] for row in villages.all())


def _unit_school_ids(db: Session, data_scope: OrgScopeFilter, name: str) -> list:
    """单位名下帮扶学校 id：学校表 support_unit 命中 ∪ 结对记录命中，再按数据域收敛。"""
    direct = db.query(School.id).filter(
        School.is_active == True,  # noqa: E712
        School.support_unit == name,
    )
    direct = data_scope.filter_by_org_ids(
        direct, School.organization_id, created_by_column=School.created_by
    )
    paired = db.query(PairingRecord.school_id).filter(
        PairingRecord.subject_type == "unit",
        PairingRecord.subject_name == name,
        PairingRecord.is_active == True,  # noqa: E712
        PairingRecord.partner_type == "school",
        PairingRecord.school_id.isnot(None),
    )
    paired = data_scope.filter_by_org_ids(
        paired, PairingRecord.organization_id, created_by_column=PairingRecord.created_by
    )
    candidate_ids = {row[0] for row in direct.all()} | {row[0] for row in paired.all()}
    if not candidate_ids:
        return []
    schools = db.query(School.id).filter(
        School.is_active == True,  # noqa: E712
        School.id.in_(candidate_ids),
    )
    schools = data_scope.filter_by_org_ids(
        schools, School.organization_id, created_by_column=School.created_by
    )
    return sorted(row[0] for row in schools.all())


def _unit_project_ids(
    db: Session, data_scope: OrgScopeFilter, name: str, village_ids: list
) -> list:
    """单位名下项目 id：responsible_unit 命中 ∪ 覆盖村名下项目。"""
    conditions = [Project.responsible_unit == name]
    if village_ids:
        conditions.append(Project.village_id.in_(village_ids))
    query = db.query(Project.id).filter(
        Project.is_active == True,  # noqa: E712
        Project.status != "cancelled",
        or_(*conditions),
    )
    query = _apply_project_scope(query, data_scope)
    return sorted(row[0] for row in query.all())


def _unit_fund_conditions(village_ids: list, school_ids: list, project_ids: list) -> list:
    """单位经费命中条件（村 / 学校 / 项目三路 OR；全空返回空列表）。"""
    conditions = []
    if village_ids:
        conditions.append(Fund.village_id.in_(village_ids))
    if school_ids:
        conditions.append(Fund.school_id.in_(school_ids))
    if project_ids:
        conditions.append(Fund.project_id.in_(project_ids))
    return conditions


def _village_names(db: Session, village_ids: list) -> list:
    """覆盖村名称列表（最多 30 个，按名称升序）。"""
    if not village_ids:
        return []
    query = db.query(SupportedVillage.village_name).filter(
        SupportedVillage.is_active == True,  # noqa: E712
        SupportedVillage.id.in_(village_ids),
    )
    rows = query.order_by(SupportedVillage.village_name.asc()).limit(_COVERAGE_NAME_LIMIT).all()
    return [row[0] for row in rows]


def _school_names(db: Session, school_ids: list) -> list:
    """覆盖学校名称列表（最多 30 个，按名称升序）。"""
    if not school_ids:
        return []
    query = db.query(School.name).filter(
        School.is_active == True,  # noqa: E712
        School.id.in_(school_ids),
    )
    rows = query.order_by(School.name.asc()).limit(_COVERAGE_NAME_LIMIT).all()
    return [row[0] for row in rows]


def _build_unit_profile(
    db: Session,
    name: str,
    village_ids: list,
    school_ids: list,
    project_count: int,
    fund_total: float,
    pairing_stats: tuple,
) -> dict:
    """单位对象档案：单位概况 + 覆盖名单 tags。"""
    total, _active, visits = pairing_stats
    sections = [
        {
            "title": "单位概况",
            "items": [
                {"label": "覆盖帮扶村", "value": str(len(village_ids))},
                {"label": "覆盖帮扶学校", "value": str(len(school_ids))},
                {"label": "帮扶项目", "value": str(project_count)},
                {"label": "经费投入(万元)", "value": str(_round_amount(fund_total))},
                {"label": "结对记录", "value": str(total)},
                {"label": "走访次数", "value": str(visits)},
            ],
        }
    ]
    tags = []
    village_names = _village_names(db, village_ids)
    if village_names:
        tags.append({"label": "覆盖帮扶村", "items": village_names})
    school_names = _school_names(db, school_ids)
    if school_names:
        tags.append({"label": "覆盖帮扶学校", "items": school_names})
    return {"title": f"{name} · 帮扶档案", "sections": sections, "tags": tags}


def _collect_unit_scope(db: Session, data_scope: OrgScopeFilter, name: str, years: int) -> dict:
    """帮扶单位维度概览。"""
    village_ids = _unit_village_ids(db, data_scope, name)
    school_ids = _unit_school_ids(db, data_scope, name)
    project_ids = _unit_project_ids(db, data_scope, name, village_ids)
    fund_conditions = _unit_fund_conditions(village_ids, school_ids, project_ids)
    pairing_stats = _pairing_stats(
        db,
        data_scope,
        [PairingRecord.subject_type == "unit", PairingRecord.subject_name == name],
    )
    project_conditions = [Project.id.in_(project_ids)]
    if fund_conditions:
        fund_total = _sum_fund_amount(db, data_scope, fund_conditions)
        fund_year_rows = _fund_year_rows(db, data_scope, fund_conditions)
        fund_details = _fund_detail_rows(db, data_scope, fund_conditions)
    else:
        fund_total = 0.0
        fund_year_rows = []
        fund_details = []
    fund_trend, yearly = _fund_trend_lists(
        _year_window(years),
        fund_year_rows,
        _project_year_rows(db, data_scope, project_conditions),
    )
    if village_ids:
        rankings = _village_fund_rankings(db, data_scope, village_ids)
    else:
        rankings = _project_rankings(db, data_scope, project_conditions)
    kpis = [
        {"key": "villages", "label": "覆盖帮扶村", "value": len(village_ids), "unit": "个"},
        {"key": "schools", "label": "覆盖帮扶学校", "value": len(school_ids), "unit": "所"},
        {"key": "projects", "label": "帮扶项目", "value": len(project_ids), "unit": "个"},
        {"key": "funds", "label": "经费投入", "value": fund_total, "unit": "万元"},
        {"key": "visits", "label": "结对走访次数", "value": pairing_stats[2], "unit": "次"},
    ]
    return {
        "scope": {
            "type": "unit",
            "id": None,
            "name": name,
            "subtitle": f"覆盖 {len(village_ids)} 个帮扶村 / {len(school_ids)} 所帮扶学校",
        },
        "kpis": kpis,
        "fund_trend": fund_trend,
        "project_status": _project_status_items(
            _project_status_counts(db, data_scope, project_conditions)
        ),
        "yearly": yearly,
        "rankings": rankings,
        "leaders": _project_leaders(db, data_scope, project_conditions),
        "profile": _build_unit_profile(
            db, name, village_ids, school_ids, len(project_ids), fund_total, pairing_stats
        ),
        "details": {
            "projects": _project_detail_rows(db, data_scope, project_conditions),
            "funds": fund_details,
            "pairing": {
                "total": pairing_stats[0],
                "active": pairing_stats[1],
                "visits": pairing_stats[2],
            },
        },
    }


# ════════════════════════════════════════════════════════════════════
#  端点
# ════════════════════════════════════════════════════════════════════

def _validate_scope(
    scope_type: str, scope_id: Optional[int], scope_name: Optional[str]
) -> Optional[str]:
    """校验维度参数；返回去除首尾空白的单位名（unit 维度）。"""
    if scope_type not in _ALLOWED_SCOPE_TYPES:
        raise AppError.bad_request(f"不支持的筛选维度: {scope_type}")
    if scope_type == "unit":
        unit_name = (scope_name or "").strip()
        if not unit_name:
            raise AppError.bad_request("单位名称不能为空")
        return unit_name
    if scope_type in ("village", "school") and scope_id is None:
        raise AppError.bad_request("缺少对象 ID")
    return None


@router.get("/overview", summary="汇报大屏对象概览")
async def get_bigscreen_overview(
    scope_type: str = Query("all", description="筛选维度：all/village/school/unit"),
    scope_id: Optional[int] = Query(None, description="帮扶村 / 帮扶学校 ID"),
    scope_name: Optional[str] = Query(None, max_length=200, description="帮扶单位名称"),
    years: int = Query(5, ge=1, le=10, description="年度趋势年数"),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """按维度返回大屏概览数据；村/学校不存在或越权 → 404，参数非法 → 400。"""
    unit_name = _validate_scope(scope_type, scope_id, scope_name)
    if scope_type == "all":
        data = _collect_all_scope(db, data_scope, years)
    elif scope_type == "village":
        data = _collect_village_scope(db, data_scope, type_cast(int, scope_id), years)
    elif scope_type == "school":
        data = _collect_school_scope(db, data_scope, type_cast(int, scope_id), years)
    else:
        data = _collect_unit_scope(db, data_scope, type_cast(str, unit_name), years)
    return success_response(data=data, message="大屏概览已获取")
