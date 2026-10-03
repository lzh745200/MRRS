"""dashboard kpi-trends / yearly-trends 端点测试"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _user():
    return SimpleNamespace(id=1, username="u", role="admin")


def _deps(app, mock_db):
    from app.core.database import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: _user()


def test_kpi_trends_success():
    from app.main import app

    mock_db = MagicMock()
    _deps(app, mock_db)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.api.v1.data.data.dashboard._query_village_stats",
            return_value={"total_villages": 12, "total_population": 3400},
        ), patch(
            "app.api.v1.data.data.dashboard._query_fund_stats",
            return_value={"funds_allocated": 5000.0, "total_funds": 8000.0},
        ), patch(
            "app.api.v1.data.data.dashboard._avg_per_capita_income",
            return_value=8800.5,
        ):
            resp = client.get("/api/v1/dashboard/kpi-trends")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["villages"] == 12
        assert data["population"] == 3400
        assert data["income"] == 8800.5
        assert data["investment"] == 9000.0  # 5000 + 8000/2
    finally:
        app.dependency_overrides.clear()


def test_kpi_trends_exception_fallback():
    from app.main import app

    mock_db = MagicMock()
    _deps(app, mock_db)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.api.v1.data.data.dashboard._query_village_stats",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/v1/dashboard/kpi-trends")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["villages"] == 0
    finally:
        app.dependency_overrides.clear()


def test_yearly_trends_structure():
    from app.main import app
    from app.core.data_permission import get_org_scope

    def _q_all(rows):
        """按年聚合查询链 mock：filter(...).group_by(...).all() → rows"""
        q = MagicMock()
        q.filter.return_value.group_by.return_value.all.return_value = rows
        q.group_by.return_value.all.return_value = rows
        return q

    # 端点已改为一次性按年聚合（4 条查询按调用序：村/人口/经费/项目）
    mock_db = MagicMock()
    mock_db.query = MagicMock(side_effect=[
        _q_all([("2026", 2)]),                # 帮扶村按 created_at 年分组
        _q_all([(2026, 100)]),                # 人口按年度表分组
        _q_all([(2026, 100.0, 80.0, 3)]),     # 经费按年度分组
        _q_all([("2026", 5)]),                # 项目按 start_date 年分组
    ])

    from types import SimpleNamespace as _NS

    _full_scope = _NS(
        has_full_access=lambda: True,
        org_ids=[1],
        org_names=[],
        filter_by_org_ids=lambda q, *a, **k: q,
    )

    def _scope_dep():
        return _full_scope

    app.dependency_overrides[get_org_scope] = _scope_dep
    _deps(app, mock_db)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.api.v1.data.data.dashboard._avg_per_capita_income",
            return_value=7600.0,
        ):
            resp = client.get("/api/v1/dashboard/yearly-trends?years=3")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["years"]) == 3
        assert len(data["villages"]) == 3
        assert len(data["population"]) == 3
        assert len(data["income"]) == 3
        assert len(data["trends"]) == 3
        t0 = data["trends"][0]
        assert "year" in t0
        assert "total_planned" in t0
        assert "total_actual" in t0
        assert "project_count" in t0
        assert "fund_count" in t0
        # 年份为最近 3 年
        now = datetime.now().year
        assert data["years"] == [now - 2, now - 1, now]
    finally:
        app.dependency_overrides.clear()


def test_avg_per_capita_income_no_columns():
    from app.api.v1.data.data.dashboard import _avg_per_capita_income

    mock_db = MagicMock()

    class _FakeCols:
        name = "id"

    class _FakeTable:
        columns = [_FakeCols()]

    class _FakeModel:
        __table__ = _FakeTable()

    with patch("app.models.annual_income.AnnualIncome", _FakeModel):
        assert _avg_per_capita_income(mock_db, MagicMock()) == 0.0


def test_avg_per_capita_income_specific_year_missing():
    from app.api.v1.data.data.dashboard import _avg_per_capita_income

    mock_db = MagicMock()

    class _FakeCols:
        name = "per_capita_income_2024"

    class _FakeTable:
        columns = [_FakeCols()]

    class _FakeModel:
        __table__ = _FakeTable()

    with patch("app.models.annual_income.AnnualIncome", _FakeModel):
        # 请求 2025 年但只有 2024 列 → 0
        assert _avg_per_capita_income(mock_db, MagicMock(), year=2025) == 0.0


def test_yearly_trends_exception_fallback():
    from app.main import app

    mock_db = MagicMock()
    _deps(app, mock_db)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.api.v1.data.data.dashboard._avg_per_capita_income",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/v1/dashboard/yearly-trends?years=2")
        assert resp.status_code == 200
        assert resp.json()["data"]["trends"] == []
    finally:
        app.dependency_overrides.clear()


def test_yearly_trends_limited_scope_applies_org_filters():
    """非全量访问：村/人口/经费三类查询必须套数据范围（审计口径 S2）。

    回归守护：修复前 yearly-trends 的三类查询完全没有 data_scope，
    非管理员能在图上看到全局数据，与 /dashboard/stats 的组织口径自相矛盾。
    本用例锁定「非全量访问时三类查询逐个套范围过滤」这一契约。
    """
    from sqlalchemy import select

    from app.main import app
    from app.core.data_permission import get_org_scope
    from app.models.supported_village import SupportedVillage

    def _q_all(rows):
        """按年聚合查询链 mock：filter(...) 链式返回自身，group_by(...).all() → rows"""
        q = MagicMock()
        q.filter.return_value = q
        q.group_by.return_value.all.return_value = rows
        return q

    scope_calls = []

    def _filter_by_org_ids(query, *id_columns, **kwargs):
        scope_calls.append(kwargs.get("created_by_column"))
        return query

    _limited_scope = SimpleNamespace(
        has_full_access=lambda: False,
        org_ids=[1],
        org_names=[],
        filter_by_org_ids=_filter_by_org_ids,
    )

    # 调用序：可访问村子查询 → 村聚合 → 人口聚合 → 经费聚合 → 项目聚合
    mock_db = MagicMock()
    mock_db.query = MagicMock(side_effect=[
        select(SupportedVillage.id),  # 真实 selectable：其 in_() 参数校验要求非 MagicMock
        _q_all([("2026", 2)]),
        _q_all([(2026, 100)]),
        _q_all([(2026, 100.0, 80.0, 3)]),
        _q_all([("2026", 5)]),
    ])

    app.dependency_overrides[get_org_scope] = lambda: _limited_scope
    _deps(app, mock_db)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.api.v1.data.data.dashboard._avg_per_capita_income",
            return_value=0.0,
        ):
            resp = client.get("/api/v1/dashboard/yearly-trends?years=3")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["villages"][-1] == 2
        assert data["population"][-1] == 100
        trend = data["trends"][-1]
        assert trend["project_count"] == 5
        assert trend["fund_count"] == 3
        assert trend["total_planned"] == 100.0
        assert trend["total_actual"] == 80.0
        # 可访问村、村聚合、项目聚合各套一次组织范围过滤
        assert len(scope_calls) == 3
    finally:
        app.dependency_overrides.clear()


def test_apply_project_scope_without_org_info_returns_query():
    """非全量且无任何组织信息时不加过滤条件（原样返回，避免误伤全量结果）。"""
    from app.api.v1.data.data.dashboard import _apply_project_scope

    query = MagicMock()
    scope = SimpleNamespace(has_full_access=lambda: False, org_ids=[], org_names=[])
    assert _apply_project_scope(query, scope) is query
    query.filter.assert_not_called()
