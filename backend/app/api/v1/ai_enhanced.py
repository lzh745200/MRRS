"""
AI增强API
提供趋势预测、异常检测、智能推荐、自然语言查询等功能
"""

# security-audit: exempt work_log — 只读AI预测/异常检测/推荐/NLP查询端点，全程不落库

from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.ai import build_data_scope, build_rationale
from app.api.v1.deps import get_current_active_user, get_db
from app.models.user import User

router = APIRouter(prefix="/ai-enhanced", tags=["AI增强"])

PredictionMethod = Literal["prophet", "moving_average", "linear"]
AnomalyMethod = Literal["isolation_forest", "zscore", "iqr"]

DEFAULT_PREDICTION_PERIODS = 12
DEFAULT_CONTAMINATION = 0.1
DEFAULT_RECOMMENDATION_LIMIT = 5
MAX_RECOMMENDATION_LIMIT = 20
MIN_RECOMMENDATION_LIMIT = 1

# 异常检测方法 → 结构化依据标识（方法/判定规则；不输出自然语言结论）
_ANOMALY_METHODS = {
    "isolation_forest": "isolation_forest_score",
    "zscore": "z_score_threshold",
    "iqr": "interquartile_range_bounds",
}
_ANOMALY_RULES = {
    "isolation_forest": "score_samples < 0",
    "zscore": "abs(z_score) > 3.0",
    "iqr": "value < Q1 - 1.5 * IQR OR value > Q3 + 1.5 * IQR",
}


@lru_cache(maxsize=1)
def _get_trend_service():
    from app.services.ai.trend_prediction_service import TrendPredictionService
    return TrendPredictionService()


@lru_cache(maxsize=1)
def _get_anomaly_service():
    from app.services.ai.anomaly_detection_service import AnomalyDetectionService
    return AnomalyDetectionService()


@lru_cache(maxsize=1)
def _get_recommendation_service():
    from app.services.ai.recommendation_service import RecommendationService
    return RecommendationService()


@lru_cache(maxsize=1)
def _get_nlp_service():
    from app.services.ai.nlp_query_service import NLPQueryService
    return NLPQueryService()


def _date_window(values: List[str]) -> Optional[Dict[str, Any]]:
    """输入数据的时间窗口；无日期（空数据）时返回 None。"""
    if not values:
        return None
    return {"start": min(values), "end": max(values), "point_count": len(values)}


class PredictRequest(BaseModel):
    """预测请求"""

    historical_data: List[Dict[str, Any]] = Field(..., max_length=5000)
    periods: int = Field(default=DEFAULT_PREDICTION_PERIODS, ge=1, le=60)
    date_field: str = "date"
    value_field: str = "value"
    method: PredictionMethod = "prophet"


class AnomalyDetectionRequest(BaseModel):
    """异常检测请求"""

    data: List[Dict[str, Any]] = Field(..., max_length=10000)
    value_field: str = "value"
    method: AnomalyMethod = "isolation_forest"
    contamination: float = Field(default=DEFAULT_CONTAMINATION, ge=0.01, le=0.5)


class FundAllocationRequest(BaseModel):
    """资金分配请求"""

    total_budget: float = Field(..., gt=0)
    village_ids: List[int] = Field(..., min_length=1)


@router.post("/predict")
async def predict_trend(
    request: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """趋势预测 - 使用Prophet或线性回归预测时间序列数据

    W17-008：响应附带结构化 rationale / data_scope（方法、字段、输入窗口、
    周期数与模型参数），前端据此展示「为什么」。
    """
    service = _get_trend_service()
    result = service.predict_time_series(
        historical_data=request.historical_data,
        periods=request.periods,
        date_field=request.date_field,
        value_field=request.value_field,
        method=request.method,
    )
    dates = [
        str(row.get(request.date_field))
        for row in request.historical_data
        if row.get(request.date_field) is not None
    ]
    window = _date_window(dates)
    resolved_method = str(result.get("method") or request.method)
    rationale = build_rationale(
        resolved_method,
        [request.date_field, request.value_field],
        window=window,
        formula={
            "kind": resolved_method,
            "periods": request.periods,
            "model_params": result.get("model_params") or {},
        },
        assumptions=["request_payload_is_primary_source", "no_implicit_imputation"],
    )
    data_scope = build_data_scope(
        "request_payload",
        scope="request",
        row_count=len(request.historical_data),
        granularity="time_point",
        window=window,
        counts={
            "forecast_periods": request.periods,
            "predictions": len(result.get("predictions") or []),
        },
    )
    return {**result, "rationale": rationale, "data_scope": data_scope}


@router.post("/anomaly-detection")
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """异常检测 - 使用Isolation Forest或统计方法检测数据中的异常值

    W17-008：返回改为结构化信封 {anomalies, anomaly_count, rationale, data_scope}，
    依据为检测方法 + 判定规则 + 参与检测的记录数。
    """
    service = _get_anomaly_service()
    result = service.detect_anomalies(
        data=request.data,
        value_field=request.value_field,
        method=request.method,
        contamination=request.contamination,
    )
    anomalies = result if isinstance(result, list) else list(result.get("anomalies") or [])
    method = _ANOMALY_METHODS.get(request.method, request.method)
    rationale = build_rationale(
        method,
        [request.value_field],
        formula={
            "kind": method,
            "value_field": request.value_field,
            "decision_rule": _ANOMALY_RULES.get(request.method, request.method),
            "contamination": request.contamination,
        },
        rules=[
            {
                "id": request.method,
                "field": request.value_field,
                "operator": "is_outlier",
            }
        ],
        assumptions=["request_payload_is_primary_source"],
    )
    data_scope = build_data_scope(
        "request_payload",
        scope="request",
        row_count=len(request.data),
        granularity="record",
        counts={"anomalies": len(anomalies)},
    )
    return {
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "rationale": rationale,
        "data_scope": data_scope,
    }


@router.get("/recommendations/projects")
async def recommend_projects(
    village_id: int,
    limit: int = Query(DEFAULT_RECOMMENDATION_LIMIT, ge=MIN_RECOMMENDATION_LIMIT, le=MAX_RECOMMENDATION_LIMIT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """项目推荐 - 根据村庄特征推荐适合的项目

    W17-008：返回信封 {items, total, rationale, data_scope}；依据为相似村庄
    成功项目的评分算式（success_count*0.5 + avg_progress/100*0.5）。
    """
    service = _get_recommendation_service()
    result = service.recommend_projects(db=db, village_id=village_id, limit=limit, user=current_user)
    items = result if isinstance(result, list) else list(result.get("items") or [])
    rationale = build_rationale(
        "similar_village_success_scoring",
        [
            "SupportedVillage.province",
            "SupportedVillage.city",
            "Project.status",
            "Project.progress",
            "Project.budget",
        ],
        formula={
            "kind": "weighted_score",
            "expression": "score = success_count * 0.5 + (avg_progress / 100) * 0.5",
            "limit": limit,
        },
        rules=[
            {
                "id": "completed_projects",
                "expression": "status == 'completed' AND progress >= 90",
            }
        ],
        assumptions=["similar_same_province_and_city", "user_data_scope_applied"],
    )
    data_scope = build_data_scope(
        "projects",
        scope="user_data_scope",
        granularity="project_type_aggregate",
        filters=[{"field": "village_id", "operator": "equals", "value": village_id}],
        counts={"recommendations": len(items), "limit": limit},
    )
    return {
        "items": items,
        "total": len(items),
        "rationale": rationale,
        "data_scope": data_scope,
    }


@router.post("/recommendations/fund-allocation")
async def recommend_fund_allocation(
    request: FundAllocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """资金分配建议 - 智能分配资金到多个村庄

    W17-008：响应附带结构化依据（需求指数算式 + 参与村庄数）。
    """
    service = _get_recommendation_service()
    result = service.recommend_fund_allocation(
        db=db, total_budget=request.total_budget, village_ids=request.village_ids, user=current_user
    )
    allocations = result.get("allocations") or []
    rationale = build_rationale(
        "weighted_need_allocation",
        # W27：原写法引用 `AnnualIncome.per_capita_income` —— 该属性**不存在**
        # （annual_income 表是年份列 per_capita_income_2020..2025，且全仓从不写入），
        # 一旦被渲染即 AttributeError。统一改为实际数据源 village_income（行式）。
        ["VillagePopulation.total_population", "VillageIncome.per_capita_income"],
        formula={
            "kind": "proportional_allocation",
            "expression": (
                "score = population_score * 0.4 + income_score * 0.6; "
                "amount = score / sum(score) * total_budget"
            ),
            "total_budget": request.total_budget,
        },
        rules=[{"id": "latest_annual_records", "expression": "max(year) per village"}],
        assumptions=["user_data_scope_applied", "zero_score_falls_back_to_zero"],
    )
    data_scope = build_data_scope(
        "villages_annual_data",
        scope="user_data_scope",
        row_count=len(allocations),
        granularity="village",
        filters=[{"field": "village_id", "operator": "in", "value": request.village_ids}],
        counts={"requested_villages": len(request.village_ids), "allocations": len(allocations)},
    )
    return {**result, "rationale": rationale, "data_scope": data_scope}


@router.post("/nlp-query")
def nlp_query(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """自然语言查询 - 将自然语言问题转换为SQL查询并返回结果

    H13：① 透传 current_user —— execute_query 据此把模板 SQL 收敛到调用者数据域，
    不再让任意登录用户读取跨组织聚合；② 端点为同步 def（原 async def 内直接跑同步
    DB 查询会阻塞事件循环，FastAPI 会把同步端点自动放入线程池执行）。

    W17-008：响应附带结构化依据（模板参数化 + 数据域子查询 + 返回行数），
    不回显 SQL 原文，避免把实现细节当"解释"输出。
    """
    service = _get_nlp_service()
    result = service.execute_query(db=db, query=query, user=current_user)
    rows = result.get("data") or []
    rationale = build_rationale(
        "parameterized_sql_template",
        ["NLPQueryService.QUERY_TEMPLATES"],
        formula={
            "kind": "parameterized_sql",
            "parameters_bound": True,
            "data_scope_subquery": True,
            "read_only": True,
        },
        rules=[
            {"id": "template_match", "when": "first regex pattern matches"},
            {"id": "row_limit", "when": "LIMIT applied by template"},
        ],
        assumptions=["fail_closed_without_user_scope", "no_sql_text_echoed"],
    )
    data_scope = build_data_scope(
        "database_rows",
        scope="user_data_scope",
        row_count=len(rows),
        granularity="row",
        counts={"success": bool(result.get("success"))},
    )
    return {**result, "rationale": rationale, "data_scope": data_scope}
