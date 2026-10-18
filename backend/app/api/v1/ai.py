"""
AI智能分析 API
提供数据分析、趋势分析、智能推荐等功能
"""

# security-audit: exempt work_log — 只读AI分析端点，POST 仅承载复杂查询体，全程不落库

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.response import success_response
from app.core.security import get_current_user
from app.services.ai_service import ai_service_manager

router = APIRouter(prefix="/ai", tags=["AI智能分析"])


# ==================== 可解释性基础设施 ====================
# W17-008：AI 结论必须能"说清楚依据"。响应中的 rationale / data_scope 是
# **结构化**描述——只给字段名、时间窗口、算式、规则与计数等机器可核对的事实，
# 不生成自然语言结论（禁止模型幻觉式自由文本）。前端据此展示「为什么」。
#
# 本模块的 build_rationale / build_data_scope / year_window 也被
# app/api/v1/ai_enhanced.py 复用（响应信封同一口径，避免两份漂移）。

RATIONALE_VERSION = 1


def build_rationale(
    method: str,
    basis_fields: Optional[list] = None,
    *,
    window: Optional[Dict[str, Any]] = None,
    formula: Optional[Dict[str, Any]] = None,
    rules: Optional[list] = None,
    assumptions: Optional[list] = None,
) -> Dict[str, Any]:
    """构造结构化依据说明（rationale）。

    Args:
        method: 计算/规则方法标识（机器可读，如 ordinary_least_squares_regression）。
        basis_fields: 参与计算的字段（模型.列名）。
        window: 时间/数据窗口，如 {"start_year": 2021, "end_year": 2026}。
        formula: 算式或聚合方式的结构化描述（kind / expression / inputs 等）。
        rules: 规则说明列表，如 {"id","when"}，禁止自然语言结论。
        assumptions: 计算假设标识列表。
    """
    return {
        "version": RATIONALE_VERSION,
        "method": method,
        "basis_fields": list(basis_fields or []),
        "window": window,
        "formula": formula,
        "rules": list(rules or []),
        "assumptions": list(assumptions or []),
    }


def build_data_scope(
    dataset: str,
    *,
    scope: str = "user_data_scope",
    row_count: Optional[int] = None,
    granularity: str = "record",
    window: Optional[Dict[str, Any]] = None,
    filters: Optional[list] = None,
    counts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造数据范围说明（data_scope）：参与计算的数据量、粒度与过滤条件。

    row_count 为**参与计算的记录数**；服务未返回可核对计数时给 None，
    不臆造数字（"说真话"要求宁可缺数，不可编数）。
    """
    return {
        "dataset": dataset,
        "scope": scope,
        "row_count": row_count,
        "granularity": granularity,
        "window": window,
        "filters": list(filters or []),
        "counts": dict(counts or {}),
    }


def year_window(years: list) -> Optional[Dict[str, Any]]:
    """年度窗口；无年度数据（空库/数据不足）时返回 None。"""
    if not years:
        return None
    return {
        "start_year": min(years),
        "end_year": max(years),
        "year_count": len(years),
    }


# ==================== Schemas ====================


class AnalyzeRequest(BaseModel):
    """数据分析请求"""

    analysis_type: str = Field(default="summary", description="分析类型: summary / trend")
    data: Dict[str, Any] = Field(default_factory=dict, description="待分析数据")
    description: Optional[str] = Field(None, description="分析说明")


class RecommendationRequest(BaseModel):
    """智能推荐请求"""

    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    category: Optional[str] = Field(None, description="推荐类别")


# ==================== 各端点的依据说明 ====================


def _analysis_explainers(
    analysis_type: str, request_data: Dict[str, Any], result: Dict[str, Any]
) -> tuple:
    """按分析类型返回 (rationale, data_scope)，全部为结构化依据。

    分支与 services/ai_service.py 的 analyze_data 分发一一对应；无法识别的
    类型走请求数据的描述统计口径（不臆造业务含义）。
    """
    if analysis_type == "trend":
        yearly = result.get("yearly_data") or []
        years = [row.get("year") for row in yearly if row.get("year") is not None]
        window = year_window(years)
        return (
            build_rationale(
                "yearly_segmented_aggregation",
                [
                    "VillageIncome.year",
                    "VillageIncome.per_capita_income",
                    "VillageIncome.collective_income",
                ],
                window=window,
                formula={
                    "kind": "group_by_aggregation",
                    "group_by": "VillageIncome.year",
                    "aggregates": {
                        "per_capita_income": "avg",
                        "collective_income": "avg",
                    },
                    "derived": {"cagr": "(last_value / first_value) ** (1 / year_gap) - 1"},
                },
                assumptions=[
                    "village_income_joined_to_supported_village",
                    "user_data_scope_applied",
                ],
            ),
            build_data_scope(
                "village_income",
                scope="user_data_scope",
                row_count=sum(int(row.get("village_count") or 0) for row in yearly),
                granularity="village_year",
                window=window,
                counts={"years": len(yearly)},
            ),
        )
    if analysis_type == "project_progress":
        return (
            build_rationale(
                "rule_based_predicate_count",
                ["Project.end_date", "Project.status", "Project.budget", "Project.actual_cost"],
                window={"kind": "as_of", "as_of": date.today().isoformat()},
                formula={
                    "kind": "predicate_count",
                    "predicates": [
                        {
                            "id": "overdue",
                            "expression": "end_date < today AND status NOT IN ('completed', 'cancelled')",
                        },
                        {
                            "id": "over_budget",
                            "expression": "budget > 0 AND actual_cost > budget",
                        },
                    ],
                },
                assumptions=["is_active_projects_only", "user_data_scope_applied"],
            ),
            build_data_scope(
                "projects",
                scope="user_data_scope",
                granularity="project",
                counts={
                    "overdue_projects": result.get("overdue_count", 0),
                    "over_budget_projects": result.get("over_budget_count", 0),
                },
            ),
        )
    if analysis_type == "fund_efficiency":
        rows = result.get("by_village") or []
        return (
            build_rationale(
                "grouped_ratio_aggregation",
                ["Fund.village_id", "Fund.amount", "Fund.allocated_amount", "Fund.used_amount"],
                formula={
                    "kind": "ratio",
                    "group_by": "Fund.village_id",
                    "ratios": {
                        "allocation_rate": "sum(allocated_amount) / sum(amount)",
                        "usage_rate": "sum(used_amount) / sum(allocated_amount)",
                    },
                    "zero_denominator": 0,
                },
                assumptions=["is_active_funds_only", "user_data_scope_applied"],
            ),
            build_data_scope(
                "funds",
                scope="user_data_scope",
                granularity="village_aggregate",
                counts={"village_groups": len(rows)},
            ),
        )
    if analysis_type == "compare":
        latest_window = {
            "income_year": result.get("income_year"),
            "population_year": result.get("population_year"),
        }
        return (
            build_rationale(
                "latest_year_grouped_comparison",
                [
                    "SupportedVillage.county",
                    "VillageIncome.per_capita_income",
                    "VillageIncome.collective_income",
                    "VillagePopulation.total_population",
                    "VillagePopulation.total_households",
                ],
                window=latest_window,
                formula={
                    "kind": "group_by_aggregation",
                    "group_by": "SupportedVillage.county",
                    "aggregates": {
                        "per_capita_income": "avg",
                        "collective_income": "avg",
                        "total_population": "sum",
                        "total_households": "sum",
                    },
                },
                assumptions=[
                    "latest_available_year_per_dataset",
                    "user_data_scope_applied",
                ],
            ),
            build_data_scope(
                "village_income_population",
                scope="user_data_scope",
                granularity="county_aggregate",
                window=latest_window,
                counts={
                    "income_counties": len(result.get("county_income") or []),
                    "population_counties": len(result.get("county_population") or []),
                },
            ),
        )
    return (
        build_rationale(
            "request_payload_descriptive_statistics",
            ["request.data"],
            formula={
                "kind": "count",
                "input": "request.data",
                "output": "total_records",
            },
        ),
        build_data_scope(
            "request_payload",
            scope="request",
            row_count=len(request_data),
            granularity="record",
        ),
    )


def _recommendation_explainers(context: Dict[str, Any], recommendations: list) -> tuple:
    """智能推荐：规则引擎（逾期待办/超预算项目/兜底提醒），非模型生成文本。"""
    return (
        build_rationale(
            "rule_based_suggestion_engine",
            ["Project.end_date", "Project.status", "Project.budget", "Project.actual_cost"],
            rules=[
                {
                    "id": "overdue_projects",
                    "when": "project_progress.overdue_count > 0",
                    "priority": "high",
                },
                {
                    "id": "over_budget_projects",
                    "when": "project_progress.over_budget_count > 0",
                    "priority": "high",
                },
                {
                    "id": "fallback_backup_reminder",
                    "when": "no_rule_matched",
                    "priority": "medium",
                },
            ],
            assumptions=["rules_evaluated_in_order", "user_data_scope_applied"],
        ),
        build_data_scope(
            "projects",
            scope="user_data_scope",
            granularity="suggestion",
            counts={"suggestions": len(recommendations), "context_keys": len(context)},
        ),
    )


def _income_forecast_explainers(result: Dict[str, Any]) -> tuple:
    """收入趋势预测：按年聚合值做最小二乘线性回归。"""
    historical = result.get("historical") or []
    years = [row.get("year") for row in historical if row.get("year") is not None]
    window = year_window(years)
    return (
        build_rationale(
            "ordinary_least_squares_regression",
            [
                "VillageIncome.year",
                "VillageIncome.per_capita_income",
                "VillageIncome.collective_income",
            ],
            window=window,
            formula={
                "kind": "linear_regression",
                "x": "year",
                "y": ["avg_per_capita_income", "avg_collective_income"],
                "expression": "y = slope * year + intercept",
                "range_floor": 0.0,
                "r2": result.get("model_confidence") or {},
            },
            assumptions=[
                "historical_yearly_aggregates",
                "non_negative_forecast_floor",
                "user_data_scope_applied",
            ],
        ),
        build_data_scope(
            "village_income",
            scope="user_data_scope",
            row_count=len(historical),
            granularity="year",
            window=window,
            counts={"forecast_years": len(result.get("forecast") or [])},
        ),
    )


def _fund_forecast_explainers(result: Dict[str, Any]) -> tuple:
    """经费完成率预测：使用率按时间进度线性外推，并按阈值给风险等级。"""
    year = result.get("current_year")
    return (
        build_rationale(
            "time_progress_ratio_projection",
            ["Fund.date", "Fund.amount", "Fund.allocated_amount", "Fund.used_amount"],
            window={"year": year, "as_of": date.today().isoformat()},
            formula={
                "kind": "ratio_projection",
                "expression": "projected_usage_rate = (used_amount / allocated_amount) / year_progress",
                "cap": 1.0,
            },
            rules=[
                {"id": "low_risk", "when": "projected_usage_rate >= 0.9"},
                {"id": "medium_risk", "when": "projected_usage_rate >= 0.7"},
                {"id": "high_risk", "when": "projected_usage_rate < 0.7"},
            ],
            assumptions=[
                "usage_tracks_time_progress",
                "same_year_records_only",
                "user_data_scope_applied",
            ],
        ),
        build_data_scope(
            "funds",
            scope="user_data_scope",
            granularity="fund_record",
            window={"year": year},
            filters=[{"field": "Fund.date", "operator": "in_year", "value": year}],
            counts={"year_progress": result.get("year_progress")},
        ),
    )


def _status_explainers(services: Any) -> tuple:
    """服务状态：本地统计引擎的注册表快照。"""
    service_map = services if isinstance(services, dict) else {}
    return (
        build_rationale(
            "runtime_service_registry",
            ["ai_service_manager.get_service_status"],
            rules=[
                {
                    "id": "local_statistics_engine",
                    "field": "services.local_analysis.status",
                    "operator": "reported_as_is",
                }
            ],
        ),
        build_data_scope(
            "ai_service_registry",
            scope="runtime",
            granularity="service",
            counts={"services": len(service_map)},
        ),
    )


# ==================== Endpoints ====================


@router.get("/status", summary="获取AI服务状态")
async def get_ai_status(
    current_user=Depends(get_current_user),
):
    """获取AI服务的运行状态"""
    await ai_service_manager.initialize()
    status = await ai_service_manager.get_service_status()
    rationale, data_scope = _status_explainers(status)
    return success_response(
        data={
            "initialized": ai_service_manager._initialized,
            "services": status,
            "rationale": rationale,
            "data_scope": data_scope,
        }
    )


@router.post("/analyze", summary="执行数据分析")
async def analyze_data(
    request: AnalyzeRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    执行AI数据分析

    支持类型:
    - summary: 数据摘要
    - trend: 趋势分析
    """
    await ai_service_manager.initialize()

    result = await ai_service_manager.analyze_data(
        data=request.data,
        analysis_type=request.analysis_type,
        db=db,
        user=current_user,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    rationale, data_scope = _analysis_explainers(request.analysis_type, request.data, result)
    return success_response(
        data={
            "analysis_type": request.analysis_type,
            "result": result,
            "rationale": rationale,
            "data_scope": data_scope,
        }
    )


@router.post("/recommendations", summary="获取智能推荐")
async def get_recommendations(
    request: RecommendationRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取基于上下文的智能推荐"""
    await ai_service_manager.initialize()

    recommendations = await ai_service_manager.get_recommendations(
        context=request.context,
        db=db,
        user=current_user,
    )

    rationale, data_scope = _recommendation_explainers(request.context, recommendations)
    return success_response(
        data={
            "recommendations": recommendations,
            "total": len(recommendations),
            "rationale": rationale,
            "data_scope": data_scope,
        }
    )


@router.get("/forecast/income", summary="收入趋势预测")
async def forecast_income(
    forecast_years: int = Query(default=2, ge=1, le=5),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    基于历史人均收入数据进行线性回归预测。

    - `forecast_years`: 预测未来年数（默认2年，最多5年）
    """
    result = await run_in_threadpool(
        ai_service_manager.forecast_income_trend, db, forecast_years=forecast_years, user=current_user
    )
    rationale, data_scope = _income_forecast_explainers(result)
    return success_response(
        data={
            **result,
            "rationale": rationale,
            "data_scope": data_scope,
        }
    )


@router.get("/forecast/funds", summary="年度经费完成率预测")
async def forecast_funds(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    根据当前时间进度和已使用经费，线性外推预测年末经费使用率，
    并给出资金执行风险评级（低/中/高）。
    """
    result = await run_in_threadpool(ai_service_manager.forecast_fund_completion, db, user=current_user)
    rationale, data_scope = _fund_forecast_explainers(result)
    return success_response(
        data={
            **result,
            "rationale": rationale,
            "data_scope": data_scope,
        }
    )
