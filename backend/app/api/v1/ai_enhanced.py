"""
AI增强API
提供趋势预测、异常检测、智能推荐、自然语言查询等功能
"""

from functools import lru_cache
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
    """趋势预测 - 使用Prophet或线性回归预测时间序列数据"""
    service = _get_trend_service()
    return service.predict_time_series(
        historical_data=request.historical_data,
        periods=request.periods,
        date_field=request.date_field,
        value_field=request.value_field,
        method=request.method,
    )


@router.post("/anomaly-detection")
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """异常检测 - 使用Isolation Forest或统计方法检测数据中的异常值"""
    service = _get_anomaly_service()
    return service.detect_anomalies(
        data=request.data,
        value_field=request.value_field,
        method=request.method,
        contamination=request.contamination,
    )


@router.get("/recommendations/projects")
async def recommend_projects(
    village_id: int,
    limit: int = Query(DEFAULT_RECOMMENDATION_LIMIT, ge=MIN_RECOMMENDATION_LIMIT, le=MAX_RECOMMENDATION_LIMIT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    """项目推荐 - 根据村庄特征推荐适合的项目"""
    service = _get_recommendation_service()
    return service.recommend_projects(db=db, village_id=village_id, limit=limit, user=current_user)


@router.post("/recommendations/fund-allocation")
async def recommend_fund_allocation(
    request: FundAllocationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """资金分配建议 - 智能分配资金到多个村庄"""
    service = _get_recommendation_service()
    return service.recommend_fund_allocation(
        db=db, total_budget=request.total_budget, village_ids=request.village_ids, user=current_user
    )


@router.post("/nlp-query")
async def nlp_query(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """自然语言查询 - 将自然语言问题转换为SQL查询并返回结果"""
    service = _get_nlp_service()
    return service.execute_query(db=db, query=query)
