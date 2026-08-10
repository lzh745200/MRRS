"""app.api.v1.data.data.dashboard_trends 覆盖率测试。

dashboard_trends.py 与 dashboard.py 都注册了 /dashboard/kpi-trends 与
/dashboard/yearly-trends（前缀相同），FastAPI 按注册顺序匹配，实际生效的是
dashboard.py 的实现。因此本文件直接调用 dashboard_trends 的函数体进行覆盖，
并通过 HTTP 测试 dashboard.py 的缓存命中分支。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.data.data.dashboard_trends as dt
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.unified_data_scope import get_org_scope

BASE = "/api/v1/dashboard"


class _Scope:
    @staticmethod
    def filter_by_org_ids(q, *args, **kwargs):
        return q


def _make_db(scalars):
    q = MagicMock()
    q.filter.return_value = q
    q.scalar.side_effect = list(scalars)
    db = MagicMock()
    db.query.return_value = q
    return db


@pytest.fixture
def dt_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="root")
    app.dependency_overrides[get_org_scope] = lambda: _Scope()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _use_db(client, db):
    client.app.dependency_overrides[get_db] = lambda: db


# ==================== _yoy 纯函数 ====================


class TestYoy:
    def test_prev_zero_cur_zero(self):
        assert dt._yoy(0, 0) == 0.0

    def test_prev_zero_cur_nonzero(self):
        assert dt._yoy(50, 0) == 100.0

    def test_normal_calc(self):
        assert dt._yoy(120, 100) == 20.0

    def test_normal_calc_negative(self):
        assert dt._yoy(80, 100) == -20.0


# ==================== get_kpi_trends（直接调用） ====================


class TestKpiTrendsDirect:
    def test_full_path(self):
        # villages_cur, villages_prev, pop_cur, pop_prev, invest_cur, invest_prev,
        # income_cur, income_prev
        db = _make_db([10, 8, 500, 450, 1000.0, 800.0, 6000.0, 5500.0])
        result = dt.get_kpi_trends(db=db, current_user=SimpleNamespace(id=1),
                                   data_scope=_Scope())
        assert result["villages"] == 25.0
        assert result["population"] == pytest.approx(11.1, abs=0.1)
        assert result["income"] == pytest.approx(9.1, abs=0.1)
        assert result["investment"] == 25.0

    def test_zero_prev_gives_100(self):
        db = _make_db([0, 0, 0, 0, 0, 0, 0, 0])
        result = dt.get_kpi_trends(db=db, current_user=SimpleNamespace(id=1),
                                   data_scope=_Scope())
        assert result["villages"] == 0.0
        assert result["income"] == 0.0

    def test_no_per_capita_income_attr(self):
        db = _make_db([5, 3, 100, 90, 50.0, 40.0])
        with patch("app.api.v1.data.data.dashboard_trends.VillageIncome",
                   SimpleNamespace(year=None)):
            result = dt.get_kpi_trends(db=db, current_user=SimpleNamespace(id=1),
                                       data_scope=_Scope())
            assert result["income"] == 0.0

    def test_scalar_none_falls_back_zero(self):
        db = _make_db([None] * 8)
        result = dt.get_kpi_trends(db=db, current_user=SimpleNamespace(id=1),
                                   data_scope=_Scope())
        assert result["villages"] == 0.0
        assert result["investment"] == 0.0

    def test_exception_returns_fallback(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        result = dt.get_kpi_trends(db=db, current_user=SimpleNamespace(id=1),
                                   data_scope=_Scope())
        assert result["villages"] == 0
        assert result["income"] == 0


# ==================== get_yearly_trends（直接调用） ====================


class TestYearlyTrendsDirect:
    def test_full_path(self):
        scalars = []
        for _ in range(3):
            scalars += [1, 100, 2000.0, 50.0]
        db = _make_db(scalars)
        result = dt.get_yearly_trends(db=db, current_user=SimpleNamespace(id=1),
                                      data_scope=_Scope(), years=3)
        assert len(result["years"]) == 3
        assert result["villages"] == [1, 1, 1]
        assert result["income"] == [2000.0, 2000.0, 2000.0]
        assert result["investment"] == [50.0, 50.0, 50.0]

    def test_no_per_capita_income_attr(self):
        scalars = []
        for _ in range(3):
            scalars += [1, 100, 50.0]
        db = _make_db(scalars)
        with patch("app.api.v1.data.data.dashboard_trends.VillageIncome",
                   SimpleNamespace(year=None)):
            result = dt.get_yearly_trends(db=db, current_user=SimpleNamespace(id=1),
                                          data_scope=_Scope(), years=3)
            assert result["income"] == [0.0, 0.0, 0.0]

    def test_scalar_none_falls_back_zero(self):
        db = _make_db([None] * 12)
        result = dt.get_yearly_trends(db=db, current_user=SimpleNamespace(id=1),
                                      data_scope=_Scope(), years=3)
        assert result["villages"] == [0, 0, 0]
        assert result["population"] == [0, 0, 0]

    def test_exception_returns_fallback(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        result = dt.get_yearly_trends(db=db, current_user=SimpleNamespace(id=1),
                                      data_scope=_Scope(), years=3)
        assert len(result["years"]) == 3
        assert result["villages"] == [0, 0, 0]


# ==================== dashboard.py 缓存命中分支 ====================


class TestDashboardCacheHit:
    def test_summary_cache_hit(self, dt_client):
        """dashboard.py get_dashboard_summary 的缓存命中分支（517-518）。"""
        from app.api.v1.data.data.dashboard import _get_cached
        import app.api.v1.data.data.dashboard as dash_mod

        cached_payload = {"success": True, "data": {"cached": True}}
        with patch.object(dash_mod, "_get_cached", return_value=cached_payload):
            resp = dt_client.get(f"{BASE}/summary")
            assert resp.status_code == 200
            assert resp.json()["data"]["cached"] is True

    def test_kpi_trends_http_success(self, dt_client):
        """dashboard.py 的 /kpi-trends HTTP 成功路径（被注册的路由）。"""
        db = MagicMock()

        def fake_query(model):
            q = MagicMock()
            q.filter.return_value = q
            q.first.return_value = None
            q.all.return_value = []
            q.scalar.return_value = 0
            q.order_by.return_value = q
            q.group_by.return_value = q
            q.count.return_value = 0
            return q

        db.query.side_effect = fake_query
        _use_db(dt_client, db)
        resp = dt_client.get(f"{BASE}/kpi-trends")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "villages" in body["data"]
