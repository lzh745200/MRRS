"""R28 · H2 回归：仪表盘趋势（`_compute_trends`）的数据域收敛。

背景（R27 报告 H2）：
    `/dashboard/stats` 的 30 天环比趋势此前**四个查询全部全局聚合**，非管理员
    在大屏上仍能看到全库环比，与同接口其它指标的组织口径自相矛盾。

修复口径（T3）：村/项目/学校/资金四类趋势各自套数据范围；人口与人均收入为
年度数据，经「可访问帮扶村 id 子查询」收敛。

本文件补齐此前未覆盖的两条分支并用**受限 scope** 双向锁定：
    * `_scope_village_query` 的非全量访问分支；
    * `_compute_trends` 中学校 / 资金两组查询的受限分支；
    * `max_pop_year` 存在时的人口/收入同比计算；
    * `max_pop_year` 为空时跳过人口同比（不产出误导性 0）。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from app.api.v1.data.data import dashboard as dash
from app.models.fund import Fund
from app.models.school import School
from app.models.supported_village import SupportedVillage


def _agg(value):
    """聚合查询链 mock：filter(...) 链式返回自身，scalar() → value。"""
    q = MagicMock()
    q.filter.return_value = q
    q.scalar.return_value = value
    return q


def _limited_scope(org_ids=(1,)):
    """受限数据域替身（非全量访问），记录被套用的列。"""
    calls = []

    def _filter_by_org_ids(query, *id_columns, **kwargs):
        calls.append(id_columns)
        return query

    scope = SimpleNamespace(
        has_full_access=lambda: False,
        org_ids=list(org_ids),
        org_names=[],
        filter_by_org_ids=_filter_by_org_ids,
    )
    return scope, calls


class TestComputeTrendsLimitedScope:
    def _db(self):
        """按 `_compute_trends` 的查询顺序预置返回链。

        顺序：村当前/村环比前/项目当前/项目环比前/学校当前/学校环比前/
        资金当前/资金环比前/最新人口年 → (村 id 子查询) → 当前人口 →
        (村 id 子查询) → 上年人口 → (村 id 子查询)。
        村 id 子查询必须返回**真实 selectable**：`in_()` 会校验参数类型。
        """
        db = MagicMock()
        db.query = MagicMock(side_effect=[
            _agg(5), _agg(2),          # 村：当前 5 / 30 天前 2
            _agg(8), _agg(3),          # 项目：当前 8 / 30 天前 3
            _agg(6), _agg(2),          # 学校：当前 6 / 30 天前 2
            _agg(1000), _agg(800),     # 资金：当前 1000 / 30 天前 800
            _agg(2024),                # 最新人口年
            select(SupportedVillage.id),
            _agg(100),                 # 当年人口
            select(SupportedVillage.id),
            _agg(80),                  # 上年人口
            select(SupportedVillage.id),
        ])
        return db

    def test_all_trends_scoped_for_limited_user(self):
        scope, calls = _limited_scope()
        with patch.object(dash, "_avg_per_capita_income", side_effect=[5000.0, 4000.0]):
            trends = dash._compute_trends(self._db(), scope)

        assert trends == {
            "villages": 150.0,
            "projects": 166.7,
            "schools": 200.0,
            "funds": 25.0,
            "population_yoy": 25.0,
            "income_yoy": 25.0,
        }
        # 四类趋势各自套了数据域（含此前未覆盖的学校 / 资金分支）
        scoped_columns = {col for cols in calls for col in cols}
        assert SupportedVillage.organization_id in scoped_columns
        assert School.organization_id in scoped_columns
        assert Fund.organization_id in scoped_columns

    def test_skips_population_yoy_without_population_year(self):
        """无人口数据（max 为 None）→ 不产出人口/收入同比，避免误导性 0。"""
        db = MagicMock()
        db.query = MagicMock(side_effect=[
            _agg(5), _agg(2),
            _agg(8), _agg(3),
            _agg(6), _agg(2),
            _agg(1000), _agg(800),
            _agg(None),                                # 最新人口年为空
            select(SupportedVillage.id),               # 村 id 子查询（真 selectable）
        ])
        scope, _ = _limited_scope()
        trends = dash._compute_trends(db, scope)
        assert "population_yoy" not in trends
        assert "income_yoy" not in trends

    def test_scope_failure_returns_empty_trends(self):
        scope, _ = _limited_scope()
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        assert dash._compute_trends(db, scope) == {}


class TestScopeVillageQuery:
    def test_limited_scope_applies_org_filter(self):
        scope, calls = _limited_scope()
        query = MagicMock()
        assert dash._scope_village_query(query, scope) is query
        assert calls == [(SupportedVillage.organization_id,)]

    def test_full_access_returns_query_untouched(self):
        scope = SimpleNamespace(
            has_full_access=lambda: True,
            filter_by_org_ids=MagicMock(),
        )
        query = MagicMock()
        assert dash._scope_village_query(query, scope) is query
        scope.filter_by_org_ids.assert_not_called()
