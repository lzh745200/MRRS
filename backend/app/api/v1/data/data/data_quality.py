"""
数据质量监控 API

提供帮扶村数据的质量报告：
- 空值率：按帮扶村×年份统计各表填报情况
- 异常值：VillageIncome 年度波动超过 50% 预警
- 填报进度：按县/年度展示完成率矩阵
"""

import logging
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.supported_village import (SupportedVillage, VillageIncome,
                                          VillagePopulation)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["数据质量"])

_DATA_START_YEAR = 2021


@router.get("/report")
async def get_data_quality_report(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """数据质量综合报告"""
    try:
        null_rate = _calc_null_rates(db)
        anomalies = _detect_income_anomalies(db)
        progress = _calc_filing_progress(db)

        return {
            "generated_at": datetime.now().isoformat(),
            "null_rate_report": null_rate,
            "income_anomalies": anomalies,
            "filing_progress": progress,
        }
    except Exception as e:
        logger.error("数据质量报告生成失败: %s", e, exc_info=True)
        return {
            "generated_at": datetime.now().isoformat(),
            "error": str(e),
            "null_rate_report": {},
            "income_anomalies": [],
            "filing_progress": {},
        }


# ------------------------------------------------------------------
# 1. 空值率统计
# ------------------------------------------------------------------


def _calc_null_rates(db: Session) -> dict:
    """统计 VillagePopulation 和 VillageIncome 的填报空缺情况"""
    current_year = datetime.now().year
    expected_years = list(range(_DATA_START_YEAR, current_year + 1))

    villages = db.query(
        SupportedVillage.id,
        SupportedVillage.village_name,
        SupportedVillage.county,
    ).all()

    # 已填年份集合
    pop_filled = defaultdict(set)
    for vid, yr in db.query(VillagePopulation.supported_village_id, VillagePopulation.year).all():
        pop_filled[vid].add(yr)

    income_filled = defaultdict(set)
    for vid, yr in db.query(VillageIncome.supported_village_id, VillageIncome.year).all():
        income_filled[vid].add(yr)

    village_reports = []
    total_expected = len(expected_years)
    for v_id, v_name, county in villages:
        pop_missing = [y for y in expected_years if y not in pop_filled[v_id]]
        income_missing = [y for y in expected_years if y not in income_filled[v_id]]
        village_reports.append(
            {
                "village_id": v_id,
                "village_name": v_name,
                "county": county or "未知",
                "population_filled": total_expected - len(pop_missing),
                "population_missing_years": pop_missing,
                "income_filled": total_expected - len(income_missing),
                "income_missing_years": income_missing,
            }
        )

    total_villages = len(villages)
    pop_fill_rate = 0
    income_fill_rate = 0
    if total_villages > 0 and total_expected > 0:
        total_slots = total_villages * total_expected
        pop_fill_rate = round(sum(v["population_filled"] for v in village_reports) / total_slots, 4)
        income_fill_rate = round(sum(v["income_filled"] for v in village_reports) / total_slots, 4)

    return {
        "expected_years": expected_years,
        "total_villages": total_villages,
        "population_fill_rate": pop_fill_rate,
        "income_fill_rate": income_fill_rate,
        "villages": village_reports,
    }


# ------------------------------------------------------------------
# 2. 异常值检测
# ------------------------------------------------------------------


def _detect_income_anomalies(db: Session) -> list:
    """检测 VillageIncome 年度人均收入波动超过 50% 的记录"""
    rows = (
        db.query(
            VillageIncome.supported_village_id,
            VillageIncome.year,
            VillageIncome.per_capita_income,
        )
        .order_by(VillageIncome.supported_village_id, VillageIncome.year)
        .all()
    )

    # 按村分组
    by_village = defaultdict(list)
    for vid, yr, pci in rows:
        by_village[vid].append((yr, float(pci or 0)))

    # 获取村名映射
    village_names = dict(db.query(SupportedVillage.id, SupportedVillage.village_name).all())

    anomalies = []
    for vid, yearly in by_village.items():
        yearly.sort(key=lambda x: x[0])
        for i in range(1, len(yearly)):
            prev_yr, prev_val = yearly[i - 1]
            curr_yr, curr_val = yearly[i]
            if prev_val > 0:
                change_rate = (curr_val - prev_val) / prev_val
                if abs(change_rate) > 0.5:
                    anomalies.append(
                        {
                            "village_id": vid,
                            "village_name": village_names.get(vid, ""),
                            "year": curr_yr,
                            "previous_year": prev_yr,
                            "previous_value": round(prev_val, 4),
                            "current_value": round(curr_val, 4),
                            "change_rate": round(change_rate, 4),
                            "severity": "high" if abs(change_rate) > 1.0 else "medium",
                        }
                    )

    return anomalies


# ------------------------------------------------------------------
# 3. 填报进度矩阵
# ------------------------------------------------------------------


@router.post("/full-check")
async def run_full_check(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全面数据质量检查（覆盖帮扶村、项目、经费、学校）"""
    from app.models.fund import Fund
    from app.models.project import Project
    from app.models.school import School

    issues: list[dict] = []

    # --- 1. 必填字段空值检查 ---
    _required_fields = [
        (SupportedVillage, "supported_villages", [("village_name", "帮扶村名称"), ("county", "所属县")]),
        (Project, "projects", [("name", "项目名称"), ("status", "项目状态")]),
        (
            Fund,
            "funds",
            [
                ("amount", "金额"),
            ],
        ),
        (
            School,
            "schools",
            [
                ("name", "学校名称"),
            ],
        ),
    ]
    for model, table, fields in _required_fields:
        for col_name, label in fields:
            col = getattr(model, col_name, None)
            if col is None:
                continue
            cnt = db.query(func.count(model.id)).filter((col == None) | (col == "")).scalar() or 0  # noqa: E711
            if cnt > 0:
                issues.append(
                    {
                        "check": "required_field",
                        "table": table,
                        "field": col_name,
                        "label": label,
                        "count": cnt,
                        "severity": "high",
                        "suggestion": f"有 {cnt} 条记录的「{label}」为空，请补充完善",
                    }
                )

    # --- 2. 数值范围检查 ---
    neg_funds = db.query(func.count(Fund.id)).filter(Fund.amount < 0).scalar() or 0
    if neg_funds > 0:
        issues.append(
            {
                "check": "value_range",
                "table": "funds",
                "field": "amount",
                "label": "金额",
                "count": neg_funds,
                "severity": "high",
                "suggestion": f"有 {neg_funds} 条经费记录金额为负数",
            }
        )

    neg_budget = db.query(func.count(Project.id)).filter(Project.budget < 0).scalar() or 0
    if neg_budget > 0:
        issues.append(
            {
                "check": "value_range",
                "table": "projects",
                "field": "budget",
                "label": "预算金额",
                "count": neg_budget,
                "severity": "medium",
                "suggestion": f"有 {neg_budget} 个项目预算金额为负数",
            }
        )

    # --- 3. 关联完整性检查 ---
    # 项目引用的 village_id 不存在
    orphan_project_village = (
        db.query(func.count(Project.id))
        .filter(
            Project.village_id.isnot(None),
            ~Project.village_id.in_(db.query(SupportedVillage.id)),
        )
        .scalar()
        or 0
    )
    if orphan_project_village > 0:
        issues.append(
            {
                "check": "referential_integrity",
                "table": "projects",
                "field": "village_id",
                "label": "关联帮扶村",
                "count": orphan_project_village,
                "severity": "high",
                "suggestion": f"有 {orphan_project_village} 个项目关联的帮扶村不存在",
            }
        )

    orphan_fund_project = (
        db.query(func.count(Fund.id))
        .filter(
            Fund.project_id.isnot(None),
            ~Fund.project_id.in_(db.query(Project.id)),
        )
        .scalar()
        or 0
    )
    if orphan_fund_project > 0:
        issues.append(
            {
                "check": "referential_integrity",
                "table": "funds",
                "field": "project_id",
                "label": "关联项目",
                "count": orphan_fund_project,
                "severity": "high",
                "suggestion": f"有 {orphan_fund_project} 条经费记录关联的项目不存在",
            }
        )

    # --- 4. 重复数据检查 ---
    dup_villages = (
        db.query(SupportedVillage.village_name, func.count(SupportedVillage.id))
        .group_by(SupportedVillage.village_name)
        .having(func.count(SupportedVillage.id) > 1)
        .all()
    )
    if dup_villages:
        issues.append(
            {
                "check": "duplicate",
                "table": "supported_villages",
                "field": "village_name",
                "label": "帮扶村名称",
                "count": len(dup_villages),
                "severity": "medium",
                "suggestion": f"发现 {len(dup_villages)} 组同名帮扶村: " + ", ".join(d[0] or "" for d in dup_villages[:5]),
            }
        )

    dup_projects = (
        db.query(Project.name, func.count(Project.id)).group_by(Project.name).having(func.count(Project.id) > 1).all()
    )
    if dup_projects:
        issues.append(
            {
                "check": "duplicate",
                "table": "projects",
                "field": "name",
                "label": "项目名称",
                "count": len(dup_projects),
                "severity": "medium",
                "suggestion": f"发现 {len(dup_projects)} 组同名项目: " + ", ".join(d[0] or "" for d in dup_projects[:5]),
            }
        )

    # 汇总
    high_count = sum(1 for i in issues if i["severity"] == "high")
    medium_count = sum(1 for i in issues if i["severity"] == "medium")
    score = max(0, 100 - high_count * 10 - medium_count * 5)

    return {
        "generated_at": datetime.now().isoformat(),
        "score": score,
        "total_issues": len(issues),
        "high_issues": high_count,
        "medium_issues": medium_count,
        "issues": issues,
    }


def _calc_filing_progress(db: Session) -> dict:
    """按县/年度展示 VillagePopulation 填报完成率矩阵"""
    current_year = datetime.now().year
    expected_years = list(range(_DATA_START_YEAR, current_year + 1))

    # 各县村庄数量
    county_counts = dict(
        db.query(SupportedVillage.county, func.count(SupportedVillage.id)).group_by(SupportedVillage.county).all()
    )

    # 各县×年份已填报数
    filled = (
        db.query(
            SupportedVillage.county,
            VillagePopulation.year,
            func.count(VillagePopulation.id),
        )
        .join(VillagePopulation, SupportedVillage.id == VillagePopulation.supported_village_id)
        .group_by(SupportedVillage.county, VillagePopulation.year)
        .all()
    )

    filled_map = defaultdict(dict)
    for county, yr, cnt in filled:
        filled_map[county or "未知"][yr] = cnt

    matrix = []
    for county, total in county_counts.items():
        county_key = county or "未知"
        year_data = {}
        for yr in expected_years:
            filled_cnt = filled_map.get(county_key, {}).get(yr, 0)
            year_data[str(yr)] = {
                "filled": filled_cnt,
                "total": total,
                "rate": round(filled_cnt / total, 4) if total > 0 else 0,
            }
        matrix.append(
            {
                "county": county_key,
                "total_villages": total,
                "years": year_data,
            }
        )

    return {
        "expected_years": expected_years,
        "matrix": matrix,
    }
