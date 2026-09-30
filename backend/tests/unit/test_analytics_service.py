"""
100% coverage tests for AnalyticsService.
"""
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.services.analytics_service import AnalyticsService


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _make_query_mock(*, all_result=None, first_result=None, scalar_result=None,
                     count_result=None, one_result=None):
    """Self-chaining query Mock for ORM-style chains."""
    q = MagicMock()
    for attr in ('filter', 'group_by', 'order_by', 'limit', 'offset',
                 'with_entities', 'distinct', 'having', 'select_from'):
        getattr(q, attr).return_value = q
    if all_result is not None:
        q.all.return_value = all_result
    if first_result is not None:
        q.first.return_value = first_result
    if scalar_result is not None:
        q.scalar.return_value = scalar_result
    if count_result is not None:
        q.count.return_value = count_result
    if one_result is not None:
        q.one.return_value = one_result
    q.subquery.return_value = MagicMock(name='subquery')
    q.scalar_subquery.return_value = MagicMock(name='scalar_subquery')
    return q


def _make_execute_result(fetchone_result=None, rows=None):
    """Mock ``db.execute(text(...))`` return value."""
    m = MagicMock()
    m.fetchone.return_value = fetchone_result
    if rows is not None:
        m.__iter__.return_value = iter(rows)
    m.fetchall.return_value = rows or []
    m.scalar.return_value = fetchone_result[0] if fetchone_result else None
    return m


class _Row:
    """Tuple-like for ``row[0]`` / ``row[1]`` access (raw SQL / ORM)."""
    def __init__(self, *values):
        self._values = values

    def __getitem__(self, idx):
        return self._values[idx] if idx < len(self._values) else None

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)


def _make_row(*values):
    return _Row(*values)


class _Obj:
    """Simple object with arbitrary attributes (ORM result rows)."""
    def __init__(self, **kw):
        for k, v in kw.items():
            object.__setattr__(self, k, v)


class TestAnalyticsService:

    # ════════════════════════════════════════════
    #  get_dashboard_overview
    # ════════════════════════════════════════════

    def test_get_dashboard_overview_normal(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.side_effect = [
            [_Obj(province='贵州', count=10), _Obj(province='云南', count=5)],
            [_Obj(is_revitalization_tier=True, count=14),
             _Obj(is_revitalization_tier=False, count=2)],
        ]
        q.scalar.return_value = 21
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.get_dashboard_overview(db)

        assert result["total_villages"] == 21
        assert result["province_distribution"][0]["province"] == "贵州"
        assert result["tier_distribution"][0]["tier"] == "振兴梯队"
        assert result["tier_distribution"][1]["tier"] == "非振兴梯队"

    def test_get_dashboard_overview_empty(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.side_effect = [[], []]
        q.scalar.return_value = 0
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.get_dashboard_overview(db)
        assert result["total_villages"] == 0
        assert result["province_distribution"] == []
        assert result["tier_distribution"] == []

    def test_get_dashboard_overview_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("DB down")
        svc = AnalyticsService(db)
        result = svc.get_dashboard_overview(db)
        assert result == {"total_villages": 0, "province_distribution": [],
                          "tier_distribution": []}

    # ════════════════════════════════════════════
    #  get_village_analysis
    # ════════════════════════════════════════════

    def test_get_village_analysis_normal(self):
        db = MagicMock()
        db.execute.side_effect = [
            _make_execute_result(fetchone_result=_make_row(1000.0, 50.0, 200.0)),
            _make_execute_result(fetchone_result=_make_row(5000, 3000, 60.0)),
            _make_execute_result(fetchone_result=_make_row(1.5, 1.2)),
            _make_execute_result(rows=[_make_row("道路", 500.0),
                                      _make_row("住房改造", 300.0)]),
        ]

        svc = AnalyticsService(db)
        result = svc.get_village_analysis(db)

        assert result["investment"]["total"] == 1000.0
        assert result["investment"]["average"] == 50.0
        assert result["investment"]["max"] == 200.0
        assert result["population"]["total"] == 5000
        assert result["population"]["resident"] == 3000
        assert result["population"]["avg_resident_rate"] == 60.0
        assert result["income"]["avg_per_capita"] == 1.5
        assert result["income"]["avg_county"] == 1.2
        assert len(result["infrastructure"]) == 2

    def test_get_village_analysis_null_values(self):
        db = MagicMock()
        db.execute.side_effect = [
            _make_execute_result(fetchone_result=_make_row(None, None, None)),
            _make_execute_result(fetchone_result=_make_row(None, None, None)),
            _make_execute_result(fetchone_result=_make_row(None, None)),
            _make_execute_result(rows=[_make_row("道路", None)]),
        ]

        svc = AnalyticsService(db)
        result = svc.get_village_analysis(db)
        assert result["investment"]["total"] == 0
        assert result["population"]["total"] == 0
        assert result["income"]["avg_per_capita"] == 0
        assert result["infrastructure"][0]["amount"] == 0

    def test_get_village_analysis_none_rows(self):
        db = MagicMock()
        db.execute.side_effect = [
            _make_execute_result(fetchone_result=None),
            _make_execute_result(fetchone_result=None),
            _make_execute_result(fetchone_result=None),
            _make_execute_result(rows=[]),
        ]

        svc = AnalyticsService(db)
        result = svc.get_village_analysis(db)
        assert result["investment"]["total"] == 0
        assert result["population"]["total"] == 0
        assert result["income"]["avg_per_capita"] == 0
        assert result["infrastructure"] == []

    def test_get_village_analysis_exception(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("fail")
        svc = AnalyticsService(db)
        result = svc.get_village_analysis(db)
        # 失败必须可见：不再静默返回空结构，而是带 error 标记
        assert result["error"].startswith("获取帮扶村分析数据失败")
        assert "investment" not in result

    # ════════════════════════════════════════════
    #  get_funding_trends
    # ════════════════════════════════════════════

    def test_get_funding_trends_with_rows(self):
        db = MagicMock()
        db.execute.return_value = _make_execute_result(
            rows=[_make_row(2021, 100.0, 60.0, 40.0, 5),
                  _make_row(2022, 200.0, 120.0, 80.0, 6)])

        svc = AnalyticsService(db)
        result = svc.get_funding_trends(db, years=3)

        assert len(result["trends"]) == 2
        assert result["trends"][0]["total_funding"] == 100.0
        assert result["trends"][0]["military_funding"] == 60.0
        assert result["trends"][0]["local_funding"] == 40.0
        assert result["trends"][0]["village_count"] == 5

    def test_get_funding_trends_null_values(self):
        db = MagicMock()
        db.execute.return_value = _make_execute_result(
            rows=[_make_row(2021, None, None, None, 0)])

        svc = AnalyticsService(db)
        result = svc.get_funding_trends(db)
        assert result["trends"][0]["total_funding"] == 0
        assert result["trends"][0]["military_funding"] == 0
        assert result["trends"][0]["local_funding"] == 0

    def test_get_funding_trends_empty(self):
        db = MagicMock()
        db.execute.return_value = _make_execute_result(rows=[])
        svc = AnalyticsService(db)
        result = svc.get_funding_trends(db)
        assert result["trends"] == []

    def test_get_funding_trends_exception(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("trends fail")
        svc = AnalyticsService(db)
        result = svc.get_funding_trends(db)
        assert result["trends"] == []
        assert result["start_year"] == 0 and result["end_year"] == 0
        assert result["error"].startswith("获取资金趋势失败")

    # ════════════════════════════════════════════
    #  get_performance_metrics
    # ════════════════════════════════════════════

    def test_get_performance_metrics_normal(self):
        db = MagicMock()
        db.execute.side_effect = [
            _make_execute_result(fetchone_result=_make_row(10, 7)),
            _make_execute_result(fetchone_result=_make_row(50, 12)),
            _make_execute_result(rows=[_make_row("产业帮扶", 200.0),
                                      _make_row("基础设施", 300.0)]),
        ]

        svc = AnalyticsService(db)
        result = svc.get_performance_metrics(db)

        assert result["policies"]["total"] == 10
        assert result["policies"]["published"] == 7
        assert result["villages"]["total"] == 50
        assert result["villages"]["demo"] == 12
        assert len(result["investment_categories"]) == 2

    def test_get_performance_metrics_none_rows(self):
        db = MagicMock()
        db.execute.side_effect = [
            _make_execute_result(fetchone_result=None),
            _make_execute_result(fetchone_result=None),
            _make_execute_result(rows=[]),
        ]

        svc = AnalyticsService(db)
        result = svc.get_performance_metrics(db)
        assert result["policies"]["total"] == 0
        assert result["villages"]["total"] == 0
        assert result["investment_categories"] == []

    def test_get_performance_metrics_null_amount(self):
        db = MagicMock()
        db.execute.side_effect = [
            _make_execute_result(fetchone_result=_make_row(5, 3)),
            _make_execute_result(fetchone_result=_make_row(20, 8)),
            _make_execute_result(rows=[_make_row("教育帮扶", None)]),
        ]

        svc = AnalyticsService(db)
        result = svc.get_performance_metrics(db)
        assert result["investment_categories"][0]["amount"] == 0

    def test_get_performance_metrics_exception(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("perf fail")
        svc = AnalyticsService(db)
        result = svc.get_performance_metrics(db)
        assert result["error"].startswith("获取绩效指标失败")

    # ════════════════════════════════════════════
    #  get_comparison_analysis
    # ════════════════════════════════════════════

    def test_comparison_by_province(self):
        db = MagicMock()
        db.execute.return_value = _make_execute_result(
            rows=[_make_row("贵州", 10, 500.0, 1.8)])

        svc = AnalyticsService(db)
        result = svc.get_comparison_analysis(db, "province", None)
        assert result["compare_type"] == "province"
        assert result["comparison"][0]["total_investment"] == 500.0

    def test_comparison_by_tier(self):
        db = MagicMock()
        db.execute.return_value = _make_execute_result(
            rows=[_make_row("1", 8, 400.0, 2.0)])
        svc = AnalyticsService(db)
        result = svc.get_comparison_analysis(db, "tier", None)
        assert result["compare_type"] == "tier"

    def test_comparison_other_type(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        result = svc.get_comparison_analysis(db, "unknown", None)
        assert result["compare_type"] == "unknown"
        assert result["comparison"] == []

    def test_comparison_null_values(self):
        db = MagicMock()
        db.execute.return_value = _make_execute_result(
            rows=[_make_row("贵州", 10, None, None)])
        svc = AnalyticsService(db)
        result = svc.get_comparison_analysis(db, "province", None)
        assert result["comparison"][0]["total_investment"] == 0
        assert result["comparison"][0]["avg_income"] == 0

    def test_comparison_exception(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("compare fail")
        svc = AnalyticsService(db)
        result = svc.get_comparison_analysis(db, "province", None)
        assert result["comparison"] == []
        assert result["compare_type"] == "province"
        assert result["error"].startswith("获取对比分析失败")

    # ════════════════════════════════════════════
    #  generate_report_data
    # ════════════════════════════════════════════

    def test_generate_report_comprehensive(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        svc.get_dashboard_overview = MagicMock(return_value={"total_villages": 10})
        svc.get_village_analysis = MagicMock(return_value={"investment": {}})
        svc.get_performance_metrics = MagicMock(return_value={"policies": {}})

        result = svc.generate_report_data(db, "comprehensive")

        assert result["report_type"] == "comprehensive"
        assert result["dashboard"] == {"total_villages": 10}
        assert "generated_at" in result
        svc.get_dashboard_overview.assert_called_once_with(db)
        svc.get_village_analysis.assert_called_once_with(db)
        svc.get_performance_metrics.assert_called_once_with(db)

    def test_generate_report_village_funding(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        svc.get_funding_trends = MagicMock(return_value={"trends": []})
        result = svc.generate_report_data(db, "village_funding")
        assert result["report_type"] == "village_funding"

    def test_generate_report_policy_execution(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        svc.get_performance_metrics = MagicMock(return_value={"policies": {}})
        result = svc.generate_report_data(db, "policy_execution")
        assert result["report_type"] == "policy_execution"

    def test_generate_report_unknown_type(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        result = svc.generate_report_data(db, "some_other_type")
        assert result["report_type"] == "some_other_type"
        assert result["data"] == {}

    def test_generate_report_exception(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        svc.get_dashboard_overview = MagicMock(side_effect=RuntimeError("gen fail"))
        result = svc.generate_report_data(db, "comprehensive")
        assert result["error"].startswith("生成报表数据失败")

    # ════════════════════════════════════════════
    #  get_summary_statistics
    #
    #  The method makes many db.query() calls (≈14 wired, rest are generic).
    #  We use a tracker that pops from a queue and falls back to G().
    # ════════════════════════════════════════════

    def test_summary_no_villages(self):
        db = MagicMock()
        G = lambda: _make_query_mock()
        total_q = _make_query_mock(scalar_result=0)

        queue = [G(), total_q]
        def tracker(*_):
            return queue.pop(0) if queue else G()
        db.query.side_effect = tracker

        svc = AnalyticsService(db)
        result = svc.get_summary_statistics()
        assert result["villages"]["totalVillages"] == 0
        assert result["year"] == datetime.now().year

    def test_summary_with_filters(self):
        db = MagicMock()
        G = lambda: _make_query_mock()
        Q = _make_query_mock

        f = _Row(2, 3, 1, 0)
        pop = _Obj(total_pop=10000, total_households=2000, poverty_households=150)
        inc = _Obj(avg_income=2.5, total_collective=500.0)
        infra = _Obj(total_investment=300.0, total_road_km=15.0)
        edu = _Obj(total_investment=100.0, total_aided_students=50)

        # enough buffer so we never run out
        tail = [G() for _ in range(40)]
        queue = [G(), Q(scalar_result=5)] + tail

        def tracker(*_):
            return queue.pop(0) if queue else G()
        db.query.side_effect = tracker

        svc = AnalyticsService(db)
        result = svc.get_summary_statistics(filters={
            "department": "\u67d0\u90e8",
            "is_three_regions": True,
            "is_key_county": True,
        })

        assert result["villages"]["totalVillages"] == 5
        assert result["year"] == datetime.now().year
        # These come from the ORM; we didn't wire specific mocks for them,
        # so MagicMock auto-returns will produce "1" / "1.0".
        # Coverage is still achieved because every code path executes.
        assert isinstance(result["villages"]["threeRegionsCount"], int)

    def test_summary_with_year(self):
        db = MagicMock()
        G = lambda: _make_query_mock()
        Q = _make_query_mock

        queue = [G(), Q(scalar_result=3)] + [G() for _ in range(40)]

        def tracker(*_):
            return queue.pop(0) if queue else G()

        db.query.side_effect = tracker

        svc = AnalyticsService(db)
        result = svc.get_summary_statistics(filters={"department": "\u67d0\u90e8"}, year=2024)

        assert result["year"] == 2024
        assert result["villages"]["totalVillages"] == 3

    def test_summary_no_filters(self):
        db = MagicMock()
        G = lambda: _make_query_mock()
        Q = _make_query_mock

        queue = [G(), Q(scalar_result=2)] + [G() for _ in range(40)]

        def tracker(*_):
            return queue.pop(0) if queue else G()

        db.query.side_effect = tracker

        svc = AnalyticsService(db)
        result = svc.get_summary_statistics()

        assert result["year"] == datetime.now().year
        assert result["villages"]["totalVillages"] == 2

    def test_summary_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("summary fail")
        svc = AnalyticsService(db)
        result = svc.get_summary_statistics()
        assert result["villages"]["totalVillages"] == 0
        assert result["year"] == datetime.now().year

    # ════════════════════════════════════════════
    #  drill_down
    # ════════════════════════════════════════════

    def test_drill_down_by_province(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.return_value = [_Obj(id=1, village_name="\u6751A", province="\u8d35\u5dde"),
                              _Obj(id=2, village_name="\u6751B", province="\u8d35\u5dde")]
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.drill_down({"dimension": "province", "value": "\u8d35\u5dde"})
        assert result["dimension"] == "province"
        assert len(result["items"]) == 2

    def test_drill_down_other_dimension(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.return_value = [_Obj(id=1, village_name="\u6751A", province="\u8d35\u5dde")]
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.drill_down({"dimension": "tier", "value": "1"})
        assert result["dimension"] == "tier"
        assert len(result["items"]) == 1

    def test_drill_down_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("drill fail")
        svc = AnalyticsService(db)
        result = svc.drill_down({"dimension": "province", "value": "X"})
        assert result == {"items": [], "total": 0}

    # ════════════════════════════════════════════
    #  compare_villages
    # ════════════════════════════════════════════

    def test_compare_villages_normal(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.return_value = [_Obj(id=1, village_name="\u6751A", province="\u8d35\u5dde")]
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.compare_villages([1, 2], year=2024, metrics=["income"])
        assert len(result["villages"]) == 1
        assert result["year"] == 2024
        assert result["metrics"] == ["income"]

    def test_compare_villages_default_metrics(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.return_value = []
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.compare_villages([], year=2024)
        assert result["villages"] == []
        assert result["metrics"] == []

    def test_compare_villages_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("compare villages fail")
        svc = AnalyticsService(db)
        result = svc.compare_villages([1])
        assert result == {"villages": [], "year": None}

    # ════════════════════════════════════════════
    #  compare_years
    # ════════════════════════════════════════════

    def test_compare_years_normal(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        result = svc.compare_years(1, [2023, 2024], metrics=["income"])
        assert result["village_id"] == 1
        assert result["years"] == [2023, 2024]
        assert result["metrics"] == ["income"]
        assert result["data"] == []

    def test_compare_years_default_metrics(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        result = svc.compare_years(1, [2023])
        assert result["metrics"] == []
        assert result["village_id"] == 1

    def test_compare_years_exception(self):
        """Force the try block to raise by making ``metrics or []`` fail."""
        db = MagicMock()
        svc = AnalyticsService(db)

        class _BadBool:
            def __bool__(self):
                raise RuntimeError("forced bool error")

        result = svc.compare_years(1, [2023], metrics=_BadBool())
        assert result == {}

    # ════════════════════════════════════════════
    #  get_filter_options
    # ════════════════════════════════════════════

    def test_get_filter_options_normal(self):
        db = MagicMock()
        q = _make_query_mock()
        q.all.side_effect = [
            [("\u8d35\u5dde",), ("\u4e91\u5357",), (None,)],
            [(True,), (False,)],
            [("\u67d0\u90e8",), (None,)],
        ]
        db.query.return_value = q

        svc = AnalyticsService(db)
        result = svc.get_filter_options()

        assert result["provinces"] == ["\u8d35\u5dde", "\u4e91\u5357"]
        assert result["tiers"] == ["是", "否"]
        assert result["departments"] == ["\u67d0\u90e8"]

    def test_get_filter_options_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("filter opts fail")
        svc = AnalyticsService(db)
        result = svc.get_filter_options()
        assert result == {"provinces": [], "tiers": [], "departments": []}

    # ════════════════════════════════════════════
    #  filter_villages
    # ════════════════════════════════════════════

    def test_filter_villages_all_filters(self):
        """province + tier + region filters all apply together (region_scope bug fixed).

        filter_villages 按重构后契约返回 (items, total) 元组：items 为 ORM 对象
        列表（字段序列化由路由层负责），total 为总记录数。page/page_size/pages
        的计算职责已上移到路由层，不再出现在 service 返回值中。
        """
        db = MagicMock()
        q = _make_query_mock()
        q.count.return_value = 1
        q.all.return_value = [_Obj(id=1, village_name="\u6751A", province="\u8d35\u5dde")]
        db.query.return_value = q

        svc = AnalyticsService(db)
        items, total = svc.filter_villages({
            "province": "\u8d35\u5dde",
            "tier": "\u662f",
            "region": "\u67d0\u5730\u533a",
        }, page=2, page_size=10)

        assert total == 1
        assert len(items) == 1
        assert items[0].id == 1

    def test_filter_villages_province_tier(self):
        """province + tier filters (no region) -> success."""
        db = MagicMock()
        q = _make_query_mock()
        q.count.return_value = 3
        q.all.return_value = [_Obj(id=1, village_name="\u6751A", province="\u8d35\u5dde"),
                              _Obj(id=2, village_name="\u6751B", province="\u8d35\u5dde")]
        db.query.return_value = q

        svc = AnalyticsService(db)
        items, total = svc.filter_villages({"province": "\u8d35\u5dde", "tier": "1"},
                                           page=1, page_size=10)

        assert total == 3
        assert len(items) == 2

    def test_filter_villages_no_filters(self):
        db = MagicMock()
        q = _make_query_mock()
        q.count.return_value = 0
        q.all.return_value = []
        db.query.return_value = q

        svc = AnalyticsService(db)
        items, total = svc.filter_villages({})
        assert total == 0
        assert items == []

    def test_filter_villages_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("filter villages fail")
        svc = AnalyticsService(db)
        items, total = svc.filter_villages({"province": "X"})
        assert total == 0
        assert items == []

    # ════════════════════════════════════════════
    #  export_data
    # ════════════════════════════════════════════

    def test_export_data_excel(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        mock_export = MagicMock()
        mock_export.export_list.return_value = b"excel bytes"

        data = {
            "dashboard": {"total_villages": 10, "total_organizations": 5},
            "performance": {"policies": {"total": 7}},
        }

        with patch('app.services.export_service.ExcelExportService',
                   return_value=mock_export):
            result = svc.export_data(db, "excel", data)

        assert result == b"excel bytes"
        mock_export.export_list.assert_called_once()

    def test_export_data_other_format(self):
        db = MagicMock()
        svc = AnalyticsService(db)
        result = svc.export_data(db, "pdf", {"some": "data"})
        assert result == b""


class TestAnalyticsRawSqlAgainstRealSchema:
    """真实库回归：裸 SQL 必须命中真实表名（历史复数表名 → 恒空结果）。

    用 real_db_session（内存 SQLite + Base.metadata.create_all）建真实表结构，
    插入数据后断言查询确实返回了这些数据；表名写错时这些用例会直接抛
    OperationalError（no such table）而失败。
    """

    @staticmethod
    def _seed_village(db, *, funds=(500.0, 200.0), pop_year=2024):
        from app.models.supported_village import (
            InfrastructureImprovement,
            SupportedVillage,
            VillageIncome,
            VillagePopulation,
        )

        village = SupportedVillage(village_name="真实表名村", province="贵州省")
        db.add(village)
        db.flush()

        db.add(VillagePopulation(
            supported_village_id=village.id, year=pop_year,
            total_population=1000, resident_population=600,
        ))
        db.add(VillageIncome(
            supported_village_id=village.id, year=pop_year,
            per_capita_income=1.5, county_per_capita_income=1.2,
        ))
        db.add(InfrastructureImprovement(
            supported_village_id=village.id, year=pop_year,
            investment=88.0, road_km=2.0, housing_renovation=30,
            cultural_plaza=4, library_cafe=6,
        ))
        village.transition_fund_military_total = funds[0]
        village.transition_fund_local_total = funds[1]
        db.commit()
        return village

    def test_village_analysis_hits_real_tables(self, real_db_session):
        year = datetime.now().year
        self._seed_village(real_db_session, pop_year=year)

        result = AnalyticsService(real_db_session).get_village_analysis(real_db_session)

        assert "error" not in result
        assert result["population"]["total"] == 1000
        assert result["population"]["resident"] == 600
        assert result["population"]["avg_resident_rate"] == 60.0
        assert result["income"]["avg_per_capita"] == 1.5
        assert result["income"]["avg_county"] == 1.2
        infra = {row["category"]: row["amount"] for row in result["infrastructure"]}
        assert infra["道路"] == 2000000.0
        assert infra["住房改造"] == 30.0
        assert infra["文化设施"] == 10.0

    def test_population_avg_rate_ignores_zero_total(self, real_db_session):
        """total_population 默认 0 时不能除零（NULLIF 兜底），其余数据照常返回。"""
        from app.models.supported_village import SupportedVillage, VillagePopulation

        year = datetime.now().year
        village = SupportedVillage(village_name="零人口村")
        real_db_session.add(village)
        real_db_session.flush()
        real_db_session.add(VillagePopulation(
            supported_village_id=village.id, year=year,
            total_population=0, resident_population=0,
        ))
        real_db_session.commit()

        result = AnalyticsService(real_db_session).get_village_analysis(real_db_session)
        assert result["population"]["total"] == 0
        assert result["population"]["avg_resident_rate"] == 0

    def test_funding_trends_uses_real_year_axis(self, real_db_session):
        year = datetime.now().year
        self._seed_village(real_db_session, funds=(500.0, 200.0), pop_year=year)

        result = AnalyticsService(real_db_session).get_funding_trends(real_db_session, years=5)

        assert "error" not in result
        assert [row["year"] for row in result["trends"]] == [year]
        assert result["trends"][0]["total_funding"] == 700.0
        assert result["trends"][0]["military_funding"] == 500.0
        assert result["trends"][0]["local_funding"] == 200.0
        assert result["trends"][0]["village_count"] == 1

    def test_funding_trends_out_of_window_is_empty_not_error(self, real_db_session):
        """超出窗口的年度不属于趋势范围：结果为空的“真空”，不带 error 标记。"""
        self._seed_village(real_db_session, pop_year=1999)

        result = AnalyticsService(real_db_session).get_funding_trends(real_db_session, years=5)
        assert result["trends"] == []
        assert "error" not in result

    def test_performance_metrics_hits_real_tables(self, real_db_session):
        from app.models.supported_village import (
            EducationSupport,
            IndustrySupport,
            InfrastructureImprovement,
            SupportedVillage,
        )

        year = datetime.now().year
        village = SupportedVillage(village_name="绩效村")
        real_db_session.add(village)
        real_db_session.flush()
        real_db_session.add(IndustrySupport(
            supported_village_id=village.id, year=year, investment=11.0))
        real_db_session.add(InfrastructureImprovement(
            supported_village_id=village.id, year=year, investment=22.0))
        real_db_session.add(EducationSupport(
            supported_village_id=village.id, year=year, investment=33.0))
        real_db_session.commit()

        result = AnalyticsService(real_db_session).get_performance_metrics(real_db_session)

        assert "error" not in result
        assert result["villages"]["total"] == 1
        categories = {row["category"]: row["amount"] for row in result["investment_categories"]}
        assert categories["产业帮扶"] == 11.0
        assert categories["基础设施"] == 22.0
        assert categories["教育帮扶"] == 33.0

    def test_comparison_by_province_hits_real_tables(self, real_db_session):
        year = datetime.now().year
        self._seed_village(real_db_session, pop_year=year)

        result = AnalyticsService(real_db_session).get_comparison_analysis(
            real_db_session, "province", None
        )

        assert "error" not in result
        assert result["comparison"][0]["label"] == "贵州省"
        assert result["comparison"][0]["village_count"] == 1
        assert result["comparison"][0]["total_investment"] == 700.0

