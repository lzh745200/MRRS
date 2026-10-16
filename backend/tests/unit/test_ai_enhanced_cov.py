# -*- coding: utf-8 -*-
"""ai_enhanced.py 覆盖率测试：4 个 lru_cache 工厂 + 5 个端点"""

from unittest.mock import MagicMock, patch

import pytest

import app.api.v1.ai_enhanced as mod


# ---------- lru_cache 工厂（真实实例化一次） ----------

def _fake_module(mod_name: str, attr: str):
    import sys
    import types

    m = types.ModuleType(mod_name)
    setattr(m, attr, MagicMock())
    return patch.dict(sys.modules, {mod_name: m})


def test_get_trend_service_factory():
    name = "app.services.ai.trend_prediction_service"
    with _fake_module(name, "TrendPredictionService") as fake:
        mod._get_trend_service.cache_clear()
        svc = mod._get_trend_service()
        assert svc is fake[name].TrendPredictionService.return_value


def test_get_anomaly_service_factory():
    name = "app.services.ai.anomaly_detection_service"
    with _fake_module(name, "AnomalyDetectionService") as fake:
        mod._get_anomaly_service.cache_clear()
        svc = mod._get_anomaly_service()
        assert svc is fake[name].AnomalyDetectionService.return_value


def test_get_recommendation_service_factory():
    assert mod._get_recommendation_service() is mod._get_recommendation_service()


def test_get_nlp_service_factory():
    assert mod._get_nlp_service() is mod._get_nlp_service()


# ---------- 端点 ----------

@pytest.mark.asyncio
async def test_predict_trend():
    svc = MagicMock()
    svc.predict_time_series.return_value = {"forecast": [1.0]}
    with patch.object(mod, "_get_trend_service", return_value=svc):
        req = mod.PredictRequest(historical_data=[{"date": "2024-01", "value": 1}])
        resp = await mod.predict_trend(request=req, db=MagicMock(), current_user=MagicMock())
    assert resp == {"forecast": [1.0]}
    svc.predict_time_series.assert_called_once()


@pytest.mark.asyncio
async def test_detect_anomalies():
    svc = MagicMock()
    svc.detect_anomalies.return_value = {"anomalies": []}
    with patch.object(mod, "_get_anomaly_service", return_value=svc):
        req = mod.AnomalyDetectionRequest(data=[{"value": 1}])
        resp = await mod.detect_anomalies(request=req, db=MagicMock(), current_user=MagicMock())
    assert resp == {"anomalies": []}
    svc.detect_anomalies.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_projects():
    svc = MagicMock()
    svc.recommend_projects.return_value = {"items": []}
    with patch.object(mod, "_get_recommendation_service", return_value=svc):
        resp = await mod.recommend_projects(village_id=3, limit=5, db=MagicMock(), current_user=MagicMock())
    assert resp == {"items": []}
    svc.recommend_projects.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_fund_allocation():
    svc = MagicMock()
    svc.recommend_fund_allocation.return_value = {"alloc": {}}
    with patch.object(mod, "_get_recommendation_service", return_value=svc):
        req = mod.FundAllocationRequest(total_budget=100.0, village_ids=[1, 2])
        resp = await mod.recommend_fund_allocation(request=req, db=MagicMock(), current_user=MagicMock())
    assert resp == {"alloc": {}}
    svc.recommend_fund_allocation.assert_called_once()


def test_nlp_query():
    """R28-H13：端点为同步 def（同步 DB 查询不得在 async def 内阻塞事件循环），
    且必须把 current_user 透传给 execute_query 以便服务层收敛数据域。"""
    svc = MagicMock()
    svc.execute_query.return_value = {"rows": 2}
    user = MagicMock()
    with patch.object(mod, "_get_nlp_service", return_value=svc):
        resp = mod.nlp_query(query="有多少个村", db=MagicMock(), current_user=user)
    assert resp == {"rows": 2}
    svc.execute_query.assert_called_once()
    assert svc.execute_query.call_args.kwargs.get("user") is user
