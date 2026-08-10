# -*- coding: utf-8 -*-
"""effectiveness_service 覆盖率补测：静态方法组 + 实例方法组 + 模块级函数"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.effectiveness_service import (
    EffectivenessService,
    calculate_effectiveness_score,
    compare_effectiveness,
    generate_effectiveness_report,
)


def _ev(total=80.0, **kw):
    ev = MagicMock()
    ev.village_id = kw.get("village_id", 1)
    ev.year = kw.get("year", 2024)
    ev.economic_score = kw.get("economic_score", 80.0)
    ev.social_score = kw.get("social_score", 75.0)
    ev.ecological_score = kw.get("ecological_score", 70.0)
    ev.total_score = total
    ev.rank = 1
    ev.grade = "A"
    ev.indicators = {}
    ev.evaluated_at = kw.get("evaluated_at", datetime(2024, 6, 1, tzinfo=timezone.utc))
    return ev


def _chain(first=None):
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = first
    return q


# ---------- 静态方法组 ----------

def test_eval_to_dict_with_and_without_timestamp():
    d1 = EffectivenessService._eval_to_dict(_ev())
    assert d1["evaluated_at"] == "2024-06-01T00:00:00+00:00"
    d2 = EffectivenessService._eval_to_dict(_ev(evaluated_at=None))
    assert d2["evaluated_at"] is None


def test_find_evaluation_queries_latest():
    ev = _ev()
    db = MagicMock()
    db.query.return_value = _chain(ev)
    assert EffectivenessService._find_evaluation(db, 1, 2024) is ev


def test_evaluate_village_not_found():
    db = MagicMock()
    db.query.return_value = _chain(None)
    r = EffectivenessService.evaluate_village(db, 99, 2024, 1)
    assert r == {"error": "村庄 99 不存在"}


def test_evaluate_village_creates_evaluation():
    """无评估记录 → 基于年度数据自动计算并写入（修复死循环）"""
    village = MagicMock()
    db = MagicMock()
    db.query.side_effect = [_chain(village), _chain(None)]
    computed = {
        "economic": 80.0,
        "social": 70.0,
        "ecological": 60.0,
        "indicators": {"per_capita_income": 5000},
    }
    with patch.object(
        EffectivenessService, "_compute_indicators", return_value=computed
    ), patch.object(EffectivenessService, "_find_evaluation", return_value=None):
        r = EffectivenessService.evaluate_village(db, 1, 2024, 1)
    assert "error" not in r
    assert r["total_score"] == round(80 * 0.4 + 70 * 0.35 + 60 * 0.25, 1)
    assert r["grade"] in ("A", "B", "C", "D")
    # 新评估被写入
    added = db.add.call_args[0][0]
    assert added.village_id == 1
    assert added.year == 2024
    assert added.economic_score == 80.0
    assert db.commit.call_count >= 1


def test_evaluate_village_updates_existing():
    """已有评估记录 → 更新分数与等级（幂等）"""
    village = MagicMock()
    ev = _ev()
    db = MagicMock()
    # 查询序列：Village → 已有评估 → 排名更新（同年度评估列表）
    db.query.side_effect = [_chain(village), _chain(ev), _chain([ev])]
    computed = {
        "economic": 90.0,
        "social": 85.0,
        "ecological": 80.0,
        "indicators": {"per_capita_income": 6000},
    }
    with patch.object(
        EffectivenessService, "_compute_indicators", return_value=computed
    ):
        r = EffectivenessService.evaluate_village(db, 1, 2024, 1)
    assert r["total_score"] == round(90 * 0.4 + 85 * 0.35 + 80 * 0.25, 1)
    assert ev.economic_score == 90.0
    assert "village_name" in r
    assert db.commit.call_count >= 1


def test_get_evaluation_report_none_and_found():
    db = MagicMock()
    db.query.return_value = _chain(None)
    assert EffectivenessService.get_evaluation_report(db, 1, 2024) is None
    db2 = MagicMock()
    db2.query.return_value = _chain(_ev())
    assert EffectivenessService.get_evaluation_report(db2, 1, 2024)["year"] == 2024


def test_compare_evaluations_missing_year1():
    with patch.object(EffectivenessService, "_find_evaluation", side_effect=[None, _ev()]):
        r = EffectivenessService.compare_evaluations(MagicMock(), 1, 2023, 2024)
    assert "缺少 2023 年" in r["error"]


def test_compare_evaluations_missing_year2():
    with patch.object(EffectivenessService, "_find_evaluation", side_effect=[_ev(), None]):
        r = EffectivenessService.compare_evaluations(MagicMock(), 1, 2023, 2024)
    assert "缺少 2024 年" in r["error"]


def test_compare_evaluations_delta():
    ev1 = _ev(total=70.0, economic_score=None)
    ev2 = _ev(total=85.5)
    with patch.object(EffectivenessService, "_find_evaluation", side_effect=[ev1, ev2]):
        r = EffectivenessService.compare_evaluations(MagicMock(), 1, 2023, 2024)
    assert r["delta"]["total_score"] == 15.5
    assert r["delta"]["economic_score"] == 80.0
    assert r["year1_data"]["total_score"] == 70.0


# ---------- 实例方法组 ----------

def test_instance_evaluators():
    svc = EffectivenessService()
    m1 = svc.evaluate_village_effectiveness(1)
    assert m1.overall_score == 0.82
    m2 = svc.evaluate_project_effectiveness(2)
    assert m2.project_completion_rate == 0.95
    m3 = svc.evaluate_fund_effectiveness(3)
    assert m3.fund_usage_rate == 0.92


def test_trends_and_export():
    svc = EffectivenessService()
    t = svc.get_effectiveness_trends(1, "village")
    assert len(t["income_growth"]) == 5
    assert svc.export_effectiveness_report(1, format="excel") == b"Mock report content"


def test_compare_periods_four_and_two_args():
    svc = EffectivenessService()
    r4 = svc.compare_effectiveness_periods(1, "2024-01", "2024-06", "2024-07", "2024-12")
    assert r4["period1"] == "2024-01 to 2024-06"
    assert r4["improvement"] == 0.07
    r2 = svc.compare_effectiveness_periods(1, "2024-01", "2024-12")
    assert r2["period1"] == "2024-01"


# ---------- 模块级函数 ----------

def test_module_level_functions():
    assert calculate_effectiveness_score({}, {}) == 0.80
    r = compare_effectiveness([], [])
    assert r["improvement"] == 0.15
    rep = generate_effectiveness_report({"entity_id": 5, "entity_type": "project"})
    assert rep.entity_id == 5
    assert rep.entity_type == "project"
    assert len(rep.recommendations) == 2
    rep2 = generate_effectiveness_report({})
    assert rep2.entity_id == 0
    assert rep2.entity_type == "village"
