# -*- coding: utf-8 -*-
"""ai.py 五端点覆盖率测试（直接异步调用 + mock ai_service_manager）"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.ai as ai_mod


def _mgr():
    m = MagicMock()
    m.initialize = AsyncMock()
    m.get_service_status = AsyncMock(return_value={"nlp": "ok"})
    m.analyze_data = AsyncMock(return_value={"summary": "s"})
    m.get_recommendations = AsyncMock(return_value=[{"id": 1}])
    m._initialized = True
    return m


@pytest.mark.asyncio
async def test_get_ai_status():
    with patch.object(ai_mod, "ai_service_manager", _mgr()):
        resp = await ai_mod.get_ai_status(current_user=MagicMock())
    assert resp["code"] == 200
    assert resp["data"]["initialized"] is True
    assert resp["data"]["services"] == {"nlp": "ok"}


@pytest.mark.asyncio
async def test_analyze_data_success():
    with patch.object(ai_mod, "ai_service_manager", _mgr()):
        req = ai_mod.AnalyzeRequest(analysis_type="trend", data={"x": 1})
        resp = await ai_mod.analyze_data(request=req, current_user=MagicMock(), db=MagicMock())
    assert resp["code"] == 200
    assert resp["data"]["analysis_type"] == "trend"
    assert resp["data"]["result"] == {"summary": "s"}


@pytest.mark.asyncio
async def test_analyze_data_error_raises_500():
    mgr = _mgr()
    mgr.analyze_data = AsyncMock(return_value={"error": "模型失败"})
    with patch.object(ai_mod, "ai_service_manager", mgr):
        req = ai_mod.AnalyzeRequest()
        with pytest.raises(HTTPException) as exc:
            await ai_mod.analyze_data(request=req, current_user=MagicMock(), db=MagicMock())
    assert exc.value.status_code == 500
    assert exc.value.detail == "模型失败"


@pytest.mark.asyncio
async def test_get_recommendations():
    with patch.object(ai_mod, "ai_service_manager", _mgr()):
        req = ai_mod.RecommendationRequest(context={"k": "v"}, category="c")
        resp = await ai_mod.get_recommendations(request=req, current_user=MagicMock(), db=MagicMock())
    assert resp["code"] == 200
    assert resp["data"]["total"] == 1
    assert resp["data"]["recommendations"] == [{"id": 1}]


@pytest.mark.asyncio
async def test_forecast_income():
    with patch.object(ai_mod, "ai_service_manager", _mgr()), patch.object(
        ai_mod, "run_in_threadpool", AsyncMock(return_value={"forecast": [1, 2]})
    ) as rip:
        resp = await ai_mod.forecast_income(forecast_years=2, current_user=MagicMock(), db=MagicMock())
    assert resp["code"] == 200
    # W17-008：data 为 result 平铺 + 结构化 rationale / data_scope
    assert resp["data"]["forecast"] == [1, 2]
    assert resp["data"]["rationale"]["method"] == "ordinary_least_squares_regression"
    assert resp["data"]["data_scope"]["dataset"] == "village_income"
    assert rip.await_count == 1


@pytest.mark.asyncio
async def test_forecast_funds():
    with patch.object(ai_mod, "ai_service_manager", _mgr()), patch.object(
        ai_mod, "run_in_threadpool", AsyncMock(return_value={"risk": "低"})
    ) as rip:
        resp = await ai_mod.forecast_funds(current_user=MagicMock(), db=MagicMock())
    assert resp["code"] == 200
    assert resp["data"]["risk"] == "低"
    assert resp["data"]["rationale"]["method"] == "time_progress_ratio_projection"
    assert resp["data"]["data_scope"]["dataset"] == "funds"
    assert rip.await_count == 1
