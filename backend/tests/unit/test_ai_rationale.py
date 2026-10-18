# -*- coding: utf-8 -*-
"""AI 结论可解释性（W17-008）回归测试 —— app/api/v1/ai.py + app/api/v1/ai_enhanced.py。

锁定三件事：

1. 每个 AI 端点响应都带**结构化** rationale（方法/依据字段/窗口/算式/规则）与
   data_scope（参与计算的数据量/范围），且 rationale 只允许固定键集合
   —— 杜绝自由文本结论（模型幻觉式"我觉得..."）；
2. 数据不足时如实置 None/0（不臆造计数）；
3. ai-enhanced 端点由裸 list/dict 改为结构化信封后的字段契约。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.api.v1.ai as ai_mod
import app.api.v1.ai_enhanced as enh_mod

# rationale 只允许的结构化键（出现自然语言结论键即为违约）
_RATIONALE_KEYS = {
    "version",
    "method",
    "basis_fields",
    "window",
    "formula",
    "rules",
    "assumptions",
}
_DATA_SCOPE_KEYS = {
    "dataset",
    "scope",
    "row_count",
    "granularity",
    "window",
    "filters",
    "counts",
}


def _mgr():
    m = MagicMock()
    m.initialize = AsyncMock()
    m.get_service_status = AsyncMock(return_value={"local_analysis": {"status": "available"}})
    m.analyze_data = AsyncMock(return_value={"summary": "s"})
    m.get_recommendations = AsyncMock(return_value=[{"id": 1}])
    m._initialized = True
    return m


def _assert_structured(payload):
    """断言 rationale / data_scope 均为固定键集合（结构化，无自由文本结论）。"""
    assert set(payload["rationale"]) == _RATIONALE_KEYS
    assert set(payload["data_scope"]) == _DATA_SCOPE_KEYS
    assert isinstance(payload["rationale"]["method"], str)
    assert payload["rationale"]["method"]
    assert isinstance(payload["rationale"]["rules"], list)
    assert isinstance(payload["data_scope"]["counts"], dict)


# ==================== 基础设施 ====================


class TestExplainabilityBuilders:
    def test_build_rationale_defaults(self):
        built = ai_mod.build_rationale("m", ["A.b"])
        assert built == {
            "version": 1,
            "method": "m",
            "basis_fields": ["A.b"],
            "window": None,
            "formula": None,
            "rules": [],
            "assumptions": [],
        }
        # basis_fields 可省略（空列表）
        assert ai_mod.build_rationale("m")["basis_fields"] == []

    def test_build_rationale_full(self):
        built = ai_mod.build_rationale(
            "m",
            ["A"],
            window={"start_year": 2021},
            formula={"kind": "k"},
            rules=[{"id": "r"}],
            assumptions=["x"],
        )
        assert built["window"] == {"start_year": 2021}
        assert built["formula"] == {"kind": "k"}
        assert built["rules"] == [{"id": "r"}]
        assert built["assumptions"] == ["x"]

    def test_build_data_scope_defaults(self):
        built = ai_mod.build_data_scope("ds")
        assert built == {
            "dataset": "ds",
            "scope": "user_data_scope",
            "row_count": None,
            "granularity": "record",
            "window": None,
            "filters": [],
            "counts": {},
        }

    def test_build_data_scope_full(self):
        built = ai_mod.build_data_scope(
            "ds",
            scope="request",
            row_count=3,
            granularity="year",
            window={"a": 1},
            filters=[{"field": "f"}],
            counts={"n": 2},
        )
        assert built["scope"] == "request"
        assert built["row_count"] == 3
        assert built["granularity"] == "year"
        assert built["window"] == {"a": 1}
        assert built["filters"] == [{"field": "f"}]
        assert built["counts"] == {"n": 2}

    def test_year_window_empty_or_values(self):
        assert ai_mod.year_window([]) is None
        assert ai_mod.year_window([2021, 2024, 2026]) == {
            "start_year": 2021,
            "end_year": 2026,
            "year_count": 3,
        }


# ==================== /ai/* 端点的依据说明 ====================


class TestAnalysisExplainers:
    def test_fallback_request_payload(self):
        for analysis_type in ("summary", "unknown_type"):
            rationale, scope = ai_mod._analysis_explainers(analysis_type, {"a": 1, "b": 2}, {})
            assert rationale["method"] == "request_payload_descriptive_statistics"
            assert rationale["formula"]["kind"] == "count"
            assert scope["dataset"] == "request_payload"
            assert scope["scope"] == "request"
            assert scope["row_count"] == 2

    def test_trend_with_years(self):
        result = {
            "yearly_data": [
                {"year": 2021, "village_count": 3},
                {"year": 2023, "village_count": 2},
            ],
            "cagr_per_capita_income": 0.05,
        }
        rationale, scope = ai_mod._analysis_explainers("trend", {}, result)
        assert rationale["method"] == "yearly_segmented_aggregation"
        assert rationale["window"] == {
            "start_year": 2021,
            "end_year": 2023,
            "year_count": 2,
        }
        assert rationale["formula"]["derived"]["cagr"]
        assert scope["dataset"] == "village_income"
        assert scope["row_count"] == 5
        assert scope["counts"] == {"years": 2}

    def test_trend_without_yearly_data(self):
        rationale, scope = ai_mod._analysis_explainers("trend", {}, {})
        assert rationale["window"] is None
        assert scope["row_count"] == 0
        assert scope["counts"] == {"years": 0}

    def test_project_progress(self):
        result = {"overdue_count": 2, "over_budget_count": 1}
        rationale, scope = ai_mod._analysis_explainers("project_progress", {}, result)
        assert rationale["method"] == "rule_based_predicate_count"
        assert rationale["window"]["kind"] == "as_of"
        predicate_ids = [p["id"] for p in rationale["formula"]["predicates"]]
        assert predicate_ids == ["overdue", "over_budget"]
        assert scope["dataset"] == "projects"
        assert scope["counts"] == {"overdue_projects": 2, "over_budget_projects": 1}

    def test_fund_efficiency(self):
        result = {"by_village": [{"village_id": 1}, {"village_id": 2}]}
        rationale, scope = ai_mod._analysis_explainers("fund_efficiency", {}, result)
        assert rationale["method"] == "grouped_ratio_aggregation"
        assert rationale["formula"]["group_by"] == "Fund.village_id"
        assert scope["dataset"] == "funds"
        assert scope["counts"] == {"village_groups": 2}

    def test_village_comparison(self):
        result = {
            "income_year": 2025,
            "population_year": 2025,
            "county_income": [{}, {}],
            "county_population": [{}],
        }
        rationale, scope = ai_mod._analysis_explainers("compare", {}, result)
        assert rationale["method"] == "latest_year_grouped_comparison"
        assert rationale["window"] == {"income_year": 2025, "population_year": 2025}
        assert scope["counts"] == {"income_counties": 2, "population_counties": 1}

    def test_recommendation_rules(self):
        rationale, scope = ai_mod._recommendation_explainers({"k": "v"}, [{"id": 1}, {"id": 2}])
        assert rationale["method"] == "rule_based_suggestion_engine"
        rule_ids = [rule["id"] for rule in rationale["rules"]]
        assert rule_ids == [
            "overdue_projects",
            "over_budget_projects",
            "fallback_backup_reminder",
        ]
        assert scope["counts"] == {"suggestions": 2, "context_keys": 1}

    def test_income_forecast(self):
        result = {
            "historical": [{"year": 2021}, {"year": 2022}],
            "forecast": [{"year": 2023}],
            "model_confidence": {"per_capita_income_r2": 0.9},
        }
        rationale, scope = ai_mod._income_forecast_explainers(result)
        assert rationale["method"] == "ordinary_least_squares_regression"
        assert rationale["window"] == {
            "start_year": 2021,
            "end_year": 2022,
            "year_count": 2,
        }
        assert rationale["formula"]["r2"] == {"per_capita_income_r2": 0.9}
        assert scope["dataset"] == "village_income"
        assert scope["row_count"] == 2
        assert scope["counts"] == {"forecast_years": 1}

    def test_income_forecast_insufficient_data(self):
        rationale, scope = ai_mod._income_forecast_explainers({"historical": [], "forecast": []})
        # 数据不足时窗口与计数如实为空/0，不臆造
        assert rationale["window"] is None
        assert scope["window"] is None
        assert scope["row_count"] == 0
        assert scope["counts"] == {"forecast_years": 0}

    def test_fund_forecast(self):
        result = {"current_year": 2026, "year_progress": 0.5}
        rationale, scope = ai_mod._fund_forecast_explainers(result)
        assert rationale["method"] == "time_progress_ratio_projection"
        assert rationale["window"]["year"] == 2026
        assert rationale["formula"]["cap"] == 1.0
        assert [rule["id"] for rule in rationale["rules"]] == [
            "low_risk",
            "medium_risk",
            "high_risk",
        ]
        assert scope["dataset"] == "funds"
        assert scope["filters"] == [
            {"field": "Fund.date", "operator": "in_year", "value": 2026}
        ]
        assert scope["counts"] == {"year_progress": 0.5}

    def test_status_explainers_tolerates_non_dict(self):
        rationale, scope = ai_mod._status_explainers({"local_analysis": {"status": "available"}})
        assert rationale["method"] == "runtime_service_registry"
        assert scope["counts"] == {"services": 1}
        _, empty_scope = ai_mod._status_explainers(None)
        assert empty_scope["counts"] == {"services": 0}


class TestAIEndpointsIncludeExplainability:
    @pytest.mark.asyncio
    async def test_status(self):
        with patch.object(ai_mod, "ai_service_manager", _mgr()):
            resp = await ai_mod.get_ai_status(current_user=MagicMock())
        _assert_structured(resp["data"])
        assert resp["data"]["services"] == {"local_analysis": {"status": "available"}}

    @pytest.mark.asyncio
    async def test_analyze_every_type(self):
        for analysis_type in (
            "summary",
            "trend",
            "project_progress",
            "fund_efficiency",
            "compare",
            "unsupported",
        ):
            mgr = _mgr()
            mgr.analyze_data = AsyncMock(return_value={})
            request = ai_mod.AnalyzeRequest(analysis_type=analysis_type, data={"x": 1})
            with patch.object(ai_mod, "ai_service_manager", mgr):
                resp = await ai_mod.analyze_data(
                    request=request, current_user=MagicMock(), db=MagicMock()
                )
            _assert_structured(resp["data"])
            assert resp["data"]["analysis_type"] == analysis_type

    @pytest.mark.asyncio
    async def test_recommendations(self):
        with patch.object(ai_mod, "ai_service_manager", _mgr()):
            request = ai_mod.RecommendationRequest(context={"k": "v"})
            resp = await ai_mod.get_recommendations(
                request=request, current_user=MagicMock(), db=MagicMock()
            )
        _assert_structured(resp["data"])
        assert resp["data"]["total"] == 1
        assert resp["data"]["data_scope"]["counts"]["suggestions"] == 1

    @pytest.mark.asyncio
    async def test_forecast_income(self):
        result = {
            "historical": [{"year": 2021}, {"year": 2022}],
            "forecast": [{"year": 2023}],
            "model_confidence": {},
        }
        with patch.object(ai_mod, "ai_service_manager", _mgr()), patch.object(
            ai_mod, "run_in_threadpool", AsyncMock(return_value=result)
        ):
            resp = await ai_mod.forecast_income(
                forecast_years=2, current_user=MagicMock(), db=MagicMock()
            )
        _assert_structured(resp["data"])
        assert resp["data"]["forecast"] == [{"year": 2023}]
        assert resp["data"]["data_scope"]["row_count"] == 2

    @pytest.mark.asyncio
    async def test_forecast_funds(self):
        result = {"current_year": 2026, "year_progress": 0.5, "risk_level": "medium"}
        with patch.object(ai_mod, "ai_service_manager", _mgr()), patch.object(
            ai_mod, "run_in_threadpool", AsyncMock(return_value=result)
        ):
            resp = await ai_mod.forecast_funds(current_user=MagicMock(), db=MagicMock())
        _assert_structured(resp["data"])
        assert resp["data"]["risk_level"] == "medium"
        assert resp["data"]["data_scope"]["counts"] == {"year_progress": 0.5}


# ==================== /ai-enhanced/* 端点 ====================


class TestEnhancedEndpoints:
    def test_date_window_helper(self):
        assert enh_mod._date_window([]) is None
        assert enh_mod._date_window(["2024-01", "2024-03"]) == {
            "start": "2024-01",
            "end": "2024-03",
            "point_count": 2,
        }

    @pytest.mark.asyncio
    async def test_predict(self):
        service = MagicMock()
        service.predict_time_series.return_value = {
            "predictions": [{"date": "2024-02-01", "value": 2.0}],
            "confidence_intervals": [],
            "method": "moving_average",
            "model_params": {"window": 3},
        }
        request = enh_mod.PredictRequest(
            historical_data=[
                {"date": "2024-01-01", "value": 1},
                {"date": "2024-02-01", "value": 2},
            ],
            periods=1,
            method="moving_average",
        )
        with patch.object(enh_mod, "_get_trend_service", return_value=service):
            resp = await enh_mod.predict_trend(
                request=request, db=MagicMock(), current_user=MagicMock()
            )
        _assert_structured(resp)
        assert resp["rationale"]["method"] == "moving_average"
        assert resp["rationale"]["window"] == {
            "start": "2024-01-01",
            "end": "2024-02-01",
            "point_count": 2,
        }
        assert resp["data_scope"]["counts"]["predictions"] == 1

    @pytest.mark.asyncio
    async def test_predict_empty_history_window_none(self):
        service = MagicMock()
        service.predict_time_series.return_value = {
            "predictions": [],
            "confidence_intervals": [],
            "method": "linear_regression",
            "error": "历史数据为空",
        }
        request = enh_mod.PredictRequest(historical_data=[], periods=2, method="linear")
        with patch.object(enh_mod, "_get_trend_service", return_value=service):
            resp = await enh_mod.predict_trend(
                request=request, db=MagicMock(), current_user=MagicMock()
            )
        assert resp["rationale"]["window"] is None
        assert resp["data_scope"]["row_count"] == 0

    @pytest.mark.asyncio
    async def test_anomaly_detection_list_result(self):
        service = MagicMock()
        service.detect_anomalies.return_value = [{"value": 1, "z_score": 9.0}]
        request = enh_mod.AnomalyDetectionRequest(
            data=[{"value": 1}, {"value": 2}], method="zscore"
        )
        with patch.object(enh_mod, "_get_anomaly_service", return_value=service):
            resp = await enh_mod.detect_anomalies(
                request=request, db=MagicMock(), current_user=MagicMock()
            )
        _assert_structured(resp)
        assert resp["anomaly_count"] == 1
        assert resp["rationale"]["method"] == "z_score_threshold"
        assert resp["rationale"]["formula"]["decision_rule"] == "abs(z_score) > 3.0"
        assert resp["data_scope"]["row_count"] == 2

    @pytest.mark.asyncio
    async def test_anomaly_detection_mapping_result(self):
        service = MagicMock()
        service.detect_anomalies.return_value = {"anomalies": [{"value": 1}]}
        request = enh_mod.AnomalyDetectionRequest(data=[{"value": 1}], method="iqr")
        with patch.object(enh_mod, "_get_anomaly_service", return_value=service):
            resp = await enh_mod.detect_anomalies(
                request=request, db=MagicMock(), current_user=MagicMock()
            )
        assert resp["anomalies"] == [{"value": 1}]
        assert resp["rationale"]["method"] == "interquartile_range_bounds"

    @pytest.mark.asyncio
    async def test_recommend_projects_list_result(self):
        service = MagicMock()
        service.recommend_projects.return_value = [{"project_type": "infrastructure"}]
        with patch.object(enh_mod, "_get_recommendation_service", return_value=service):
            resp = await enh_mod.recommend_projects(
                village_id=7, limit=5, db=MagicMock(), current_user=MagicMock()
            )
        _assert_structured(resp)
        assert resp["items"] == [{"project_type": "infrastructure"}]
        assert resp["total"] == 1

    @pytest.mark.asyncio
    async def test_recommend_projects_mapping_result(self):
        service = MagicMock()
        service.recommend_projects.return_value = {"items": []}
        with patch.object(enh_mod, "_get_recommendation_service", return_value=service):
            resp = await enh_mod.recommend_projects(
                village_id=7, limit=3, db=MagicMock(), current_user=MagicMock()
            )
        assert resp["items"] == []
        assert resp["data_scope"]["filters"] == [
            {"field": "village_id", "operator": "equals", "value": 7}
        ]

    @pytest.mark.asyncio
    async def test_recommend_fund_allocation(self):
        service = MagicMock()
        service.recommend_fund_allocation.return_value = {
            "allocations": [{"village_id": 1, "recommended_amount": 60.0}],
            "method": "weighted_by_need",
        }
        request = enh_mod.FundAllocationRequest(total_budget=100.0, village_ids=[1, 2])
        with patch.object(enh_mod, "_get_recommendation_service", return_value=service):
            resp = await enh_mod.recommend_fund_allocation(
                request=request, db=MagicMock(), current_user=MagicMock()
            )
        _assert_structured(resp)
        assert resp["allocations"][0]["village_id"] == 1
        assert resp["data_scope"]["row_count"] == 1
        assert resp["data_scope"]["filters"] == [
            {"field": "village_id", "operator": "in", "value": [1, 2]}
        ]

    def test_nlp_query_success_rows(self):
        service = MagicMock()
        service.execute_query.return_value = {
            "success": True,
            "data": [{"count": 3}],
            "explanation": "系统中共有 3 个村庄",
            "sql": "SELECT 1",
            "query": "有多少个村",
        }
        user = MagicMock()
        with patch.object(enh_mod, "_get_nlp_service", return_value=service):
            resp = enh_mod.nlp_query(query="有多少个村", db=MagicMock(), current_user=user)
        _assert_structured(resp)
        assert resp["data_scope"]["row_count"] == 1
        assert resp["data_scope"]["counts"] == {"success": True}
        # 结构化依据不含 SQL 原文
        assert "sql" not in resp["rationale"]["formula"]

    def test_nlp_query_failure(self):
        service = MagicMock()
        service.execute_query.return_value = {
            "success": False,
            "error": "未找到匹配的查询模板",
            "query": "???",
        }
        with patch.object(enh_mod, "_get_nlp_service", return_value=service):
            resp = enh_mod.nlp_query(query="???", db=MagicMock(), current_user=MagicMock())
        assert resp["data_scope"]["row_count"] == 0
        assert resp["data_scope"]["counts"] == {"success": False}
