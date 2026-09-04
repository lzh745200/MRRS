"""app.api.v1.data.data.statistics 覆盖率攻坚测试（补充既有测试未覆盖分支）

覆盖点：
- _get_cached_stats / _cache_stats：缓存禁用/命中/未命中/读写异常
- _calc_village_completeness：0村回退 + 全维度计分
- _get_overview_impl：全查询序列 + AuditLog 三处异常降级
- _get_analysis_data_impl：有数据全路径（趋势/分类/占比/地区）+ 无数据空路径
- 各端点 500 异常分支与缓存命中直达
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.data.data.statistics as st
from app.core.database import get_db
from app.core.security import get_current_user

BASE = "/api/v1/statistics"


# ==================== 公共设施 ====================


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit", "group_by", "with_entities", "join"):
        getattr(q, attr).return_value = q
    q.count.return_value = kw.get("count", 0)
    q.scalar.return_value = kw.get("scalar")
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


def _db_with(queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


# _get_analysis_data_impl 的 current_user 为必填位置参数（fail-closed，W5-006）
_SCOPE_USER = SimpleNamespace(
    id=1, username="root", role="super_admin", is_superuser=True, organization_id=1
)


def _patch_scope():
    """把 apply_scope_filter 打成「原样返回 query」的替身。

    既避免它干扰 _db_with 排序好的 side_effect 查询链，又保留 call_count
    以便断言数据隔离确实被挂载到每一条经费查询上。
    """
    return patch(
        "app.core.data_scope_adapter.apply_scope_filter",
        side_effect=lambda q, *a, **k: q,
    )


@pytest.fixture
def st_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="root")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _use_db(client, db):
    client.app.dependency_overrides[get_db] = lambda: db


# ==================== 缓存辅助函数 ====================


class TestCacheHelpers:
    async def test_get_cached_disabled(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", False)
        assert await st._get_cached_stats("k") is None

    async def test_get_cached_hit(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", True)
        cache = MagicMock()
        cache.get = AsyncMock(return_value='{"a": 1}')
        with patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)):
            assert await st._get_cached_stats("summary") == {"a": 1}

    async def test_get_cached_miss_returns_none(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", True)
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        with patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)):
            assert await st._get_cached_stats("k") is None

    async def test_get_cached_exception_degrades(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", True)
        with patch("app.core.cache.get_cache_service", AsyncMock(side_effect=Exception("cache down"))):
            assert await st._get_cached_stats("k") is None

    async def test_cache_stats_disabled_noop(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", False)
        await st._cache_stats("k", {"a": 1})  # 直接返回，不抛异常

    async def test_cache_stats_write(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", True)
        cache = MagicMock()
        cache.set = AsyncMock()
        with patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)):
            await st._cache_stats("k", {"a": 1})
        cache.set.assert_awaited_once()

    async def test_cache_stats_write_exception_degrades(self, monkeypatch):
        monkeypatch.setattr(st.settings, "CACHE_ENABLED", True)
        with patch("app.core.cache.get_cache_service", AsyncMock(side_effect=Exception("x"))):
            await st._cache_stats("k", {"a": 1})  # 异常被吞


# ==================== _calc_village_completeness ====================


class TestCalcVillageCompleteness:
    def test_zero_villages(self):
        from app.models.supported_village import SupportedVillage, VillageIncome, VillagePopulation

        assert st._calc_village_completeness(MagicMock(), SupportedVillage, VillagePopulation, VillageIncome, 0) == 0

    def test_full_scoring(self):
        from app.models.supported_village import SupportedVillage as SV
        from app.models.supported_village import VillageIncome as VI
        from app.models.supported_village import VillagePopulation as VP

        db = _db_with([
            _q(scalar=1), _q(scalar=1), _q(scalar=1), _q(scalar=1),  # 4 个基本字段
            _q(scalar=1),   # 坐标
            _q(scalar=5),   # 人口（min(5,2)=2）
            _q(scalar=0),   # 收入
        ])
        # passed=1+1+1+1+1+2+0=7, total=2*6=12 → round(58.33)=58
        assert st._calc_village_completeness(db, SV, VP, VI, 2) == 58


# ==================== _get_overview_impl ====================


class TestOverviewImpl:
    async def test_full_path(self):
        logs = [SimpleNamespace(
            id=1, action="创建", resource_type="项目", username="root",
            user_id=1, created_at="2026-07-25 01:00:00",
        )]
        db = _db_with([
            _q(count=2),                 # villages
            _q(count=3),                 # projects
            _q(count=4),                 # schools
            _q(count=5),                 # funds
            _q(count=6),                 # users
            _q(scalar=100.0),            # funds_total
            _q(scalar="2026-07-24"),     # last_update Village
            _q(scalar=None),             # last_update Project → None
            _q(scalar="2026-07-23"),     # Fund
            _q(scalar="2026-07-22"),     # School
            _q(scalar="2026-07-21"),     # User
            _q(count=0),                 # sv_count=0 → completeness=0 跳过计算
            _q(count=7),                 # today_ops
            _q(all=[SimpleNamespace(day=datetime.now().strftime("%Y-%m-%d"), cnt=3)]),  # trend（须落在近7天窗口内，动态取今天）
            _q(all=logs),                # recent_logs
        ])
        result = await st._get_overview_impl(db)
        assert result["villages"] == 2
        assert result["funds_amount"] == 100.0
        assert result["completeness"] == 0
        assert result["today_operations"] == 7
        assert len(result["trend"]) == 7
        assert any(t["operations"] == 3 for t in result["trend"] if t["date"] == datetime.now().strftime("%m-%d"))
        assert result["recent_logs"][0]["user"] == "root"
        assert result["recent_logs"][0]["action"] == "创建 项目"
        assert result["modules"][0]["healthy"] is True
        assert result["modules"][1]["lastUpdate"] is None

    async def test_audit_failures_degrade(self):
        """AuditLog 三处查询均异常 → 降级默认值（覆盖 233-234/247-249/270-271）"""
        call = {"n": 0}

        def _query(*args):
            call["n"] += 1
            if call["n"] >= 13:  # today_ops / trend / recent_logs
                raise Exception("audit table gone")
            return _q(count=0, scalar=None, all=[])

        db = MagicMock()
        db.query = MagicMock(side_effect=_query)
        result = await st._get_overview_impl(db)
        assert result["today_operations"] == 0
        assert all(t["operations"] == 0 for t in result["trend"])
        assert result["recent_logs"] == []


# ==================== _get_analysis_data_impl ====================


class TestAnalysisDataImpl:
    async def test_full_path_with_data(self):
        db = _db_with([
            _q(count=2),                 # total_villages
            _q(count=3),                 # active_projects
            _q(scalar=100.0),            # mil_total
            _q(scalar=50.0),             # loc_total
            # _calc_village_completeness（7 个查询：4字段+坐标+人口+收入）
            _q(scalar=2), _q(scalar=2), _q(scalar=2), _q(scalar=2),
            _q(scalar=2), _q(scalar=2), _q(scalar=2),
            # H3：items_rows —— 经费口径改为解析 transition_fund_items(JSON)
            _q(all=[(
                '[{"year":2021,"militaryInvestment":10,"localInvestment":5},'
                '{"year":2022,"militaryInvestment":20,"localInvestment":10}]',
            )]),
            # 5 个帮扶分类 count+sum
            _q(first=SimpleNamespace(cnt=1, inv=100.0)),
            _q(first=SimpleNamespace(cnt=2, inv=200.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=None),              # result 为 None 的回退
            _q(first=SimpleNamespace(cnt=1, inv=300.0)),
            _q(first=SimpleNamespace(cnt=1, inv=400.0)),   # 消费帮扶
            _q(first=SimpleNamespace(cnt=1, ben=80.0)),    # 就业帮扶
            _q(all=[("甲县", 2, 100.0, 50.0)]),            # county_data
            # 年度对比：各村人口年份 / 收入年份（投入改由 items JSON 聚合，H3）
            _q(all=[(2024, 2), (2025, 3)]),                # pop_rows
            _q(all=[(2024, 1.2), (2025, 1.5)]),            # inc_rows
        ])
        with _patch_scope() as scope:
            result = await st._get_analysis_data_impl(db, _SCOPE_USER)
        # fail-closed 回归：4 条经费查询（村数/军投入/地方投入/年度明细）均须挂隔离
        assert scope.call_count == 4
        ov = result["overview"]
        assert ov["total_villages"] == 2
        assert ov["total_investment"] == 150.0
        # passed=2*4(字段)+2(坐标)+min(2,2)(人口)+min(2,2)(收入)=14，total=2*6=12 → round(116.67)=117
        assert ov["completeness"] == 117
        # 投入趋势
        trend = result["investment_trend"]
        assert len(trend) == 5
        assert trend[0]["total"] == 15.0
        assert trend[0]["growth"] == 0       # prev_total=0 → 无基期
        assert trend[1]["total"] == 30.0
        assert trend[1]["growth"] == 100.0   # (30-15)/15*100
        assert trend[2]["growth"] == -100.0  # 2023 无数据但 prev_total 保持 30
        # 分类统计
        cats = {c["category"]: c for c in result["category_stats"]}
        assert cats["产业帮扶"]["investment"] == 100.0
        assert cats["医疗帮扶"]["count"] == 0  # first=None 回退
        assert cats["就业帮扶"]["beneficiaries"] == 80
        assert cats["产业帮扶"]["ratio"] == 10  # 100/1000*100
        # 地区分布
        assert result["region_stats"] == [
            {"region": "甲县", "villages": 2, "investment": 150.0, "avgIncome": 0}
        ]
        # 年度对比（v1.8.0）——投入口径改为 transition_fund_items 聚合（H3）
        yc = result["yearly_comparison"]
        assert yc["years"] == ["2024", "2025"]
        assert yc["villages"] == {"2024": 2, "2025": 3}
        assert yc["investment"] == {"2021": 15.0, "2022": 30.0}
        assert yc["income"] == {"2024": 1.2, "2025": 1.5}

    async def test_empty_villages_path(self):
        """无帮扶村 → 趋势为空、完整率为 0（覆盖 460-463 的 False 分支）"""
        db = _db_with([
            _q(count=0),                 # total_villages=0
            _q(count=0),                 # active_projects
            _q(scalar=0),                # mil_total
            _q(scalar=0),                # loc_total
            _q(all=[]),                  # items_rows（H3：经费明细 JSON）
            # 5 个帮扶分类
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),   # 消费
            _q(first=SimpleNamespace(cnt=0, ben=0.0)),   # 就业
            _q(all=[]),                  # county_data
            _q(all=[]),                  # pop_rows（年度对比，v1.8.0）
            _q(all=[]),                  # inc_rows
        ])
        with _patch_scope():
            result = await st._get_analysis_data_impl(db, _SCOPE_USER)
        assert result["overview"]["completeness"] == 0
        assert result["investment_trend"] == []
        assert all(c["ratio"] == 0 for c in result["category_stats"])  # total_cat_inv=0 跳过占比
        assert result["region_stats"] == []
        # 年度对比空数据兜底
        assert result["yearly_comparison"] == {"years": [], "villages": {}, "investment": {}, "income": {}}

    async def test_items_json_defensive_branches(self):
        """覆盖 610/613-614/616/619/622-623 —— transition_fund_items JSON 解析全防御分支。

        依次构造：空值(None/空串)、非法JSON(str/int)、合法JSON但非list、
        list内非dict项、year不可转int(str/None)，均须静默跳过不抛异常；
        夹杂一条合法行验证正常聚合不被坏行干扰。
        """
        db = _db_with([
            _q(count=2),                 # total_villages
            _q(count=0),                 # active_projects
            _q(scalar=0),                # mil_total
            _q(scalar=0),                # loc_total
            # _calc_village_completeness 7 个查询
            _q(scalar=2), _q(scalar=2), _q(scalar=2), _q(scalar=2),
            _q(scalar=2), _q(scalar=2), _q(scalar=2),
            # items_rows：坏行 + 好行
            _q(all=[
                (None,),                # 610：空值跳过
                ("",),                  # 610：空串跳过
                ("not-json{",),          # 613-614：ValueError
                (12345,),                # 613-614：TypeError
                ('{"year": 2021}',),     # 616：合法JSON但非list
                ('["abc", 3]',),         # 619：list内非dict项
                ('[{"year": "xyz"}]',),  # 622-623：int("xyz") ValueError
                ('[{"year": null}]',),   # 622-623：int(None) TypeError
                ('[{"year": 2021, "militaryInvestment": 10, "localInvestment": 5}]',),  # 合法行
            ]),
            # 7 个帮扶分类查询
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),
            _q(first=SimpleNamespace(cnt=0, inv=0.0)),   # 消费
            _q(first=SimpleNamespace(cnt=0, ben=0.0)),   # 就业
            _q(all=[]),                  # county_data
            _q(all=[]),                  # pop_rows
            _q(all=[]),                  # inc_rows
        ])
        with _patch_scope():
            result = await st._get_analysis_data_impl(db, _SCOPE_USER)
        # 坏行全部被跳过，仅合法 2021 行参与聚合：total=10+5=15
        trend = result["investment_trend"]
        assert len(trend) == 5
        assert trend[0] == {"year": "2021", "military": 10.0, "local": 5.0, "total": 15.0, "growth": 0}
        assert trend[1]["total"] == 0.0

    async def test_current_user_is_mandatory_fail_closed(self):
        """fail-closed 回归（W5-006）：漏传 current_user 必须直接 TypeError。

        历史缺陷：current_user 曾带 None 默认值，_scoped 内 `if current_user is
        not None` 使漏传时静默跳过隔离、返回跨组织聚合数据。改为必填位置参数后，
        漏传在调用点即失败，不会静默放行。
        """
        db = _db_with([])
        with pytest.raises(TypeError):
            await st._get_analysis_data_impl(db)


# ==================== 端点 500 与缓存命中 ====================


class TestEndpointBranches:
    def test_summary_cache_hit(self, st_client):
        with patch.object(st, "_get_cached_stats", AsyncMock(return_value={"cached": True})):
            resp = st_client.get(f"{BASE}/summary")
        assert resp.status_code == 200
        assert resp.json() == {"cached": True}

    def test_summary_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("db boom"))
        _use_db(st_client, db)
        with patch.object(st, "_get_cached_stats", AsyncMock(return_value=None)):
            resp = st_client.get(f"{BASE}/summary")
        assert resp.status_code == 500

    def test_dashboard_cache_hit(self, st_client):
        with patch.object(st, "_get_cached_stats", AsyncMock(return_value={"dash": 1})):
            resp = st_client.get(f"{BASE}/dashboard")
        assert resp.json() == {"dash": 1}

    def test_dashboard_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        with patch.object(st, "_get_cached_stats", AsyncMock(return_value=None)):
            resp = st_client.get(f"{BASE}/dashboard")
        assert resp.status_code == 500

    def test_overview_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        resp = st_client.get(f"{BASE}/overview")
        assert resp.status_code == 500

    def test_analysis_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        resp = st_client.get(f"{BASE}/analysis")
        assert resp.status_code == 500

    def test_villages_distribution_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        resp = st_client.get(f"{BASE}/villages/distribution")
        assert resp.status_code == 500

    def test_projects_statistics_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        resp = st_client.get(f"{BASE}/projects/statistics")
        assert resp.status_code == 500

    def test_funds_statistics_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        resp = st_client.get(f"{BASE}/funds/statistics")
        assert resp.status_code == 500

    def test_schools_statistics_500(self, st_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("x"))
        _use_db(st_client, db)
        resp = st_client.get(f"{BASE}/schools/statistics")
        assert resp.status_code == 500
