"""考核评估 API — 量化评分、排名看板、异常检测、趋势预测"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.cache import get_cache_service
from app.core.data_permission import filter_by_data_scope
from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import get_current_user
from app.models.fund import Fund
from app.models.project import Project
from app.models.supported_village import SupportedVillage, VillageIncome

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assessment", tags=["考核评估"])


# ==================== 评分权重配置 ====================

SCORE_WEIGHTS = {
    "economic": 0.30,  # 经济效益
    "social": 0.25,  # 社会效益
    "project_completion": 0.25,  # 项目完成率
    "fund_execution": 0.20,  # 经费执行率
}


# ==================== 帮扶成效评分 ====================


@router.get("/village-scores")
async def get_village_scores(
    year: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取帮扶村综合成效评分（量化评分模型）

    优化：使用批量查询避免 N+1 问题
    """
    target_year = year or date.today().year

    # 缓存检查（TTL=5分钟）
    cache = await get_cache_service()
    cache_key = f"village_scores:{target_year}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    # 预加载关联数据，避免N+1查询
    villages = filter_by_data_scope(db.query(SupportedVillage), SupportedVillage, current_user).limit(5000).all()

    if not villages:
        return ok_list([], 0, year=target_year, weights=SCORE_WEIGHTS)

    village_ids = [v.id for v in villages]

    # 批量查询所有村庄的收入数据（最近两年）
    incomes_query = (
        db.query(VillageIncome)
        .filter(VillageIncome.supported_village_id.in_(village_ids))
        .order_by(VillageIncome.supported_village_id, VillageIncome.year.desc())
        .all()
    )

    # 按村庄ID分组收入数据
    from collections import defaultdict

    incomes_by_village = defaultdict(list)
    for inc in incomes_query:
        incomes_by_village[inc.supported_village_id].append(inc)

    # 批量查询项目统计
    project_stats = (
        db.query(
            Project.village_id,
            func.count(Project.id).label("total"),
            func.sum(case((Project.status == "completed", 1), else_=0)).label("completed"),
        )
        .filter(Project.village_id.in_(village_ids))
        .group_by(Project.village_id)
        .all()
    )
    project_stats_dict = {stat.village_id: stat for stat in project_stats}

    # 批量查询经费统计
    fund_stats = (
        db.query(
            Fund.village_id,
            func.coalesce(func.sum(Fund.amount), 0).label("total_amount"),
            func.coalesce(func.sum(Fund.used_amount), 0).label("total_used"),
        )
        .filter(Fund.village_id.in_(village_ids))
        .group_by(Fund.village_id)
        .all()
    )
    fund_stats_dict = {stat.village_id: stat for stat in fund_stats}

    results = []
    for v in villages:
        scores = _calculate_village_score_batch(v, target_year, incomes_by_village, project_stats_dict, fund_stats_dict)
        results.append(
            {
                "village_id": v.id,
                "village_name": v.village_name,
                "support_unit": v.support_unit or "",
                "scores": scores["detail"],
                "total_score": scores["total"],
                "level": _score_level(scores["total"]),
            }
        )

    # 按总分排名
    results.sort(key=lambda x: x["total_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    # 写入缓存并返回
    result = ok_list(results, len(results), year=target_year, weights=SCORE_WEIGHTS)
    await cache.set(cache_key, result, ttl=300)
    return result


@router.get("/anomalies")
async def detect_anomalies(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """检测数据异常（首页预警卡片用）"""
    try:
        anomalies = []

        current_year = date.today().year

        # 获取当前用户有权访问的村庄ID列表
        allowed_villages = filter_by_data_scope(db.query(SupportedVillage), SupportedVillage, current_user).all()
        allowed_village_ids = {v.id for v in allowed_villages}

        # 1. 收入突降检测: 与上一年度相比降幅 > 30%
        incomes_current = (
            db.query(VillageIncome)
            .filter(
                VillageIncome.year == current_year,
                VillageIncome.supported_village_id.in_(allowed_village_ids),
            )
            .all()
        )

        # 批量查询上一年度数据和村庄信息，避免N+1查询
        prev_incomes = {
            inc.supported_village_id: inc
            for inc in (
                db.query(VillageIncome)
                .filter(
                    VillageIncome.year == current_year - 1,
                    VillageIncome.supported_village_id.in_(allowed_village_ids),
                )
                .all()
            )
        }

        village_ids = [inc.supported_village_id for inc in incomes_current]
        villages_dict = {v.id: v for v in allowed_villages if v.id in village_ids}

        for inc in incomes_current:
            prev = prev_incomes.get(inc.supported_village_id)
            if prev and prev.per_capita_income and float(prev.per_capita_income or 0) > 0:
                cur_val = float(inc.per_capita_income or 0)
                prev_val = float(prev.per_capita_income or 0)
                change_rate = (cur_val - prev_val) / prev_val
                if change_rate < -0.3:
                    village = villages_dict.get(inc.supported_village_id)
                    anomalies.append(
                        {
                            "type": "income_drop",
                            "level": "danger",
                            "village_id": inc.supported_village_id,
                            "village_name": (village.village_name if village else f"ID={inc.supported_village_id}"),
                            "message": f"人均收入同比下降 {abs(round(change_rate * 100, 1))}%",
                            "detail": f"上年: {prev_val}元 → 本年: {cur_val}元",
                        }
                    )

        # 2. 逾期项目检测
        overdue_projects = (
            filter_by_data_scope(db.query(Project), Project, current_user)
            .filter(
                Project.end_date < date.today(),
                Project.status.notin_(["completed", "cancelled"]),
            )
            .all()
        )
        for p in overdue_projects:
            overdue_days = (date.today() - p.end_date).days if p.end_date else 0
            if overdue_days > 30:
                anomalies.append(
                    {
                        "type": "project_overdue",
                        "level": "warning",
                        "project_id": p.id,
                        "project_name": p.name,
                        "message": f"项目已逾期 {overdue_days} 天",
                        "detail": f"计划结束日期: {p.end_date.isoformat() if p.end_date else '未设置'}",
                    }
                )

        # 3. 预算超支检测
        over_budget = (
            filter_by_data_scope(db.query(Project), Project, current_user)
            .filter(Project.budget > 0, Project.actual_cost > Project.budget)
            .all()
        )
        for p in over_budget:
            ratio = round((float(p.actual_cost or 0) - float(p.budget or 0)) / float(p.budget or 0) * 100, 1)
            anomalies.append(
                {
                    "type": "budget_overrun",
                    "level": "warning",
                    "project_id": p.id,
                    "project_name": p.name,
                    "message": f"实际花费超预算 {ratio}%",
                    "detail": f"预算: {float(p.budget or 0)}万 → 实际: {float(p.actual_cost or 0)}万",
                }
            )

        return ok_list(anomalies, len(anomalies))
    except Exception:
        logger.exception("Failed to detect anomalies")
        raise HTTPException(status_code=500, detail="异常检测失败")


# ==================== 趋势预测（简单线性回归） ====================


@router.get("/trend-prediction")
async def get_trend_prediction(
    metric: str = Query("per_capita_income", description="指标: per_capita_income/collective_income"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于历史数据的简单线性回归趋势预测"""
    col = VillageIncome.per_capita_income if metric == "per_capita_income" else VillageIncome.collective_income

    try:
        # 仅统计用户有权访问的村庄
        allowed_villages = filter_by_data_scope(db.query(SupportedVillage), SupportedVillage, current_user).all()
        allowed_village_ids = {v.id for v in allowed_villages}
        rows = (
            db.query(VillageIncome.year, func.avg(col))
            .filter(VillageIncome.supported_village_id.in_(allowed_village_ids))
            .group_by(VillageIncome.year)
            .order_by(VillageIncome.year)
            .all()
        )

        if len(rows) < 2:
            return {
                "message": "数据不足，至少需要两年数据",
                "historical": [],
                "predicted": [],
            }

        # 线性回归 y = a + b*x
        xs = [r[0] for r in rows]
        ys = [float(r[1] or 0) for r in rows]
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        ss_xx = sum((x - mean_x) ** 2 for x in xs)

        b = ss_xy / ss_xx if ss_xx != 0 else 0
        a = mean_y - b * mean_x

        # 预测未来2年
        last_year = xs[-1]
        predictions = []
        for offset in range(1, 3):
            pred_year = last_year + offset
            pred_value = max(0, round(a + b * pred_year, 2))
            predictions.append({"year": pred_year, "value": pred_value})

        return {
            "metric": metric,
            "historical": [{"year": x, "value": round(y, 2)} for x, y in zip(xs, ys)],
            "predicted": predictions,
            "slope": round(b, 4),
            "intercept": round(a, 4),
        }
    except Exception:
        logger.exception("Failed to get trend prediction")
        raise HTTPException(status_code=500, detail="趋势预测失败")


# ==================== 多维度对比 ====================


@router.get("/village-comparison")
async def compare_villages(
    village_ids: str = Query(..., description="逗号分隔的村ID，最多5个"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """多村横向对比（雷达图数据）"""
    ids = [int(x.strip()) for x in village_ids.split(",") if x.strip().isdigit()][:5]
    if not ids:
        return ok_list([], 0)

    # 批量查询村庄信息，避免 N+1，且仅查询用户有权访问的村庄
    villages = (
        filter_by_data_scope(db.query(SupportedVillage), SupportedVillage, current_user)
        .filter(SupportedVillage.id.in_(ids))
        .all()
    )
    if not villages:
        return ok_list([], 0)
    villages_dict = {v.id: v for v in villages}
    allowed_ids = [v.id for v in villages]

    # 批量查询最新收入数据
    latest_incomes_subq = (
        db.query(
            VillageIncome.supported_village_id,
            func.max(VillageIncome.year).label("max_year"),
        )
        .filter(VillageIncome.supported_village_id.in_(allowed_ids))
        .group_by(VillageIncome.supported_village_id)
        .subquery()
    )
    latest_incomes = (
        db.query(VillageIncome)
        .join(
            latest_incomes_subq,
            (VillageIncome.supported_village_id == latest_incomes_subq.c.supported_village_id)
            & (VillageIncome.year == latest_incomes_subq.c.max_year),
        )
        .all()
    )
    incomes_dict = {inc.supported_village_id: inc for inc in latest_incomes}

    # 批量查询项目统计
    project_stats = (
        db.query(
            Project.village_id,
            func.count(Project.id).label("total"),
            func.sum(case((Project.status == "completed", 1), else_=0)).label("completed"),
        )
        .filter(Project.village_id.in_(allowed_ids))
        .group_by(Project.village_id)
        .all()
    )
    project_stats_dict = {stat.village_id: stat for stat in project_stats}

    # 批量查询经费统计
    fund_stats = (
        db.query(
            Fund.village_id,
            func.coalesce(func.sum(Fund.amount), 0).label("total_funds"),
        )
        .filter(Fund.village_id.in_(allowed_ids))
        .group_by(Fund.village_id)
        .all()
    )
    fund_stats_dict = {stat.village_id: float(stat.total_funds) for stat in fund_stats}

    # 组装结果
    results = []
    for vid in allowed_ids:
        village = villages_dict.get(vid)
        if not village:
            continue

        latest_income = incomes_dict.get(vid)
        project_stat = project_stats_dict.get(vid)
        total_projects = int(project_stat.total) if project_stat else 0
        completed_projects = int(project_stat.completed) if project_stat else 0
        total_funds = fund_stats_dict.get(vid, 0)

        results.append(
            {
                "village_id": vid,
                "village_name": village.village_name,
                "per_capita_income": (float(latest_income.per_capita_income or 0) if latest_income else 0),
                "collective_income": (float(latest_income.collective_income or 0) if latest_income else 0),
                "total_projects": total_projects,
                "completed_projects": completed_projects,
                "project_completion_rate": (
                    round(completed_projects / total_projects * 100, 1) if total_projects > 0 else 0
                ),
                "total_funds": round(total_funds, 2),
            }
        )

    return ok_list(results, len(results))


# ==================== 内部工具函数 ====================


def _calculate_village_score_batch(
    village,
    year: int,
    incomes_by_village: dict,
    project_stats_dict: dict,
    fund_stats_dict: dict,
) -> dict:
    """计算单个帮扶村的综合评分（批量优化版本）

    使用预先批量查询的数据，避免 N+1 查询问题

    Args:
        village: 村庄对象
        year: 目标年份
        incomes_by_village: 按村庄ID分组的收入数据
        project_stats_dict: 项目统计数据字典
        fund_stats_dict: 经费统计数据字典
    """
    vid = village.id

    # 1. 经济效益 (0-100): 基于人均收入增长率
    economic_score = 50  # 默认
    incomes = incomes_by_village.get(vid, [])[:2]  # 取最近两年
    if len(incomes) >= 2:
        cur = float(incomes[0].per_capita_income or 0)
        prev = float(incomes[1].per_capita_income or 0)
        if prev > 0:
            growth = (cur - prev) / prev
            economic_score = min(100, max(0, 50 + growth * 200))

    # 2. 社会效益 (0-100): 基于帮扶村关联数据丰富度
    social_score = 60  # 基础分
    if incomes:
        social_score += 20

    # 3. 项目完成率 (0-100)
    project_stat = project_stats_dict.get(vid)
    if project_stat:
        total_p = int(project_stat.total) if project_stat.total else 0
        completed_p = int(project_stat.completed) if project_stat.completed else 0
        project_score = round(completed_p / total_p * 100) if total_p > 0 else 50
    else:
        project_score = 50

    # 4. 经费执行率 (0-100)
    fund_stat = fund_stats_dict.get(vid)
    if fund_stat:
        total_f = float(fund_stat.total_amount or 0)
        used_f = float(fund_stat.total_used or 0)
        fund_score = round(used_f / total_f * 100) if total_f > 0 else 50
    else:
        fund_score = 50

    detail = {
        "economic": round(economic_score, 1),
        "social": round(social_score, 1),
        "project_completion": round(project_score, 1),
        "fund_execution": round(fund_score, 1),
    }

    total = sum(detail[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)

    return {"detail": detail, "total": round(total, 1)}


def _score_level(score: float) -> str:
    if score >= 90:
        return "优秀"
    elif score >= 75:
        return "良好"
    elif score >= 60:
        return "合格"
    else:
        return "待改进"
