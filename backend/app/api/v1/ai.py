"""
AI智能分析 API
提供数据分析、趋势分析、智能推荐等功能
"""

# security-audit: exempt work_log — 只读AI分析端点，POST 仅承载复杂查询体，全程不落库

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


# ==================== Endpoints ====================


@router.get("/status", summary="获取AI服务状态")
async def get_ai_status(
    current_user=Depends(get_current_user),
):
    """获取AI服务的运行状态"""
    await ai_service_manager.initialize()
    status = await ai_service_manager.get_service_status()
    return success_response(
        data={
            "initialized": ai_service_manager._initialized,
            "services": status,
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

    return success_response(
        data={
            "analysis_type": request.analysis_type,
            "result": result,
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

    return success_response(
        data={
            "recommendations": recommendations,
            "total": len(recommendations),
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
    return success_response(data=result)


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
    return success_response(data=result)
