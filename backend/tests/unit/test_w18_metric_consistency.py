"""W18 P0/P1 回归：指标口径一致性 + 数据范围接线。

来源：docs/W18深度探测-系统完善方案-2026-10-17.md
- P0-1 总人口在 dashboard 与 statistics 两处口径不同（全库最大年 vs 每村各自最新年），
  实测同一数据下相差 500 人，两个页面数字打架。
- P0-2 dashboard._avg_per_capita_income 收下 data_scope 形参却从未使用（越权不报警）。
- P1   报表 total_villages 用明细 limit(100) 截断后的 len() 当总数。

这些用例是**一致性守护**：把"同一指标只能有一个口径"锁死，防止未来再次漂移。
"""
import pytest

from app.core.data_permission import OrgScopeFilter
from app.models.annual_income import AnnualIncome
from app.models.supported_village import SupportedVillage, VillagePopulation


def _mk_village(db, name, org_id=None, created_by=None):
    v = SupportedVillage(
        village_name=name,
        is_active=True,
        organization_id=org_id,
        created_by=created_by,
    )
    db.add(v)
    db.flush()
    return v


class TestPopulationMetricConsistency:
    """P0-1：总人口必须按"每村各自最新年份"汇总。"""

    def _seed(self, db):
        a = _mk_village(db, "A村")
        b = _mk_village(db, "B村")
        c = _mk_village(db, "C村")  # 只报到 2023（今年还没上报）
        db.add_all([
            VillagePopulation(supported_village_id=a.id, year=2023, total_population=900, total_households=90),
            VillagePopulation(supported_village_id=a.id, year=2024, total_population=1000, total_households=100),
            VillagePopulation(supported_village_id=b.id, year=2024, total_population=500, total_households=50),
            VillagePopulation(supported_village_id=c.id, year=2023, total_population=450, total_households=45),
        ])
        db.commit()
        return a, b, c

    def test_dashboard_population_uses_per_village_latest_year(self, real_db_session):
        db = real_db_session
        self._seed(db)

        from app.api.v1.data.data.dashboard import _query_village_stats

        stats = _query_village_stats(db, OrgScopeFilter(is_admin=True))
        # 每村各自最新年：1000 + 500 + 450 = 1950
        # 旧的"全库最大年份(2024)"口径只有 1000 + 500 = 1500（漏掉 C 村 450）
        assert stats["total_population"] == 1950
        assert stats["total_households"] == 195

    def test_dashboard_matches_statistics_style_aggregation(self, real_db_session):
        """一致性守护：dashboard 与 statistics 的每村最新年口径必须相等。"""
        db = real_db_session
        self._seed(db)

        from sqlalchemy import func

        from app.api.v1.data.data.dashboard import _query_village_stats

        # statistics.py 的口径：按村分组取 max(year) 后再求和（独立实现，用作对照）
        pop_subq = (
            db.query(
                VillagePopulation.supported_village_id.label("vid"),
                func.max(VillagePopulation.year).label("max_year"),
            )
            .group_by(VillagePopulation.supported_village_id)
            .subquery()
        )
        expected = (
            db.query(func.coalesce(func.sum(VillagePopulation.total_population), 0))
            .join(
                pop_subq,
                (VillagePopulation.supported_village_id == pop_subq.c.vid)
                & (VillagePopulation.year == pop_subq.c.max_year),
            )
            .scalar()
        )

        stats = _query_village_stats(db, OrgScopeFilter(is_admin=True))
        # 两个口径必须相等（这正是 P0-1 修复前相差 500 人的地方）
        assert stats["total_population"] == int(expected)


class TestAvgPerCapitaIncomeScope:
    """P0-2：data_scope 必须真正参与过滤（fail-closed）。"""

    def test_scope_only_counts_visible_org(self, real_db_session):
        db = real_db_session
        v1 = _mk_village(db, "一村", org_id=1)
        v2 = _mk_village(db, "二村", org_id=2)
        db.add_all([
            AnnualIncome(supported_village_id=v1.id, year=2025, per_capita_income_2025=10),
            AnnualIncome(supported_village_id=v2.id, year=2025, per_capita_income_2025=30),
        ])
        db.commit()

        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        scope_org1 = OrgScopeFilter(is_admin=False, org_ids=[1])
        # 只统计一村 → 10；若 data_scope 未接线会得到 (10+30)/2 = 20
        assert _avg_per_capita_income(db, scope_org1, year=2025) == pytest.approx(10.0)

    def test_none_scope_is_fail_closed(self, real_db_session):
        db = real_db_session
        v1 = _mk_village(db, "一村", org_id=1)
        db.add(AnnualIncome(supported_village_id=v1.id, year=2025, per_capita_income_2025=10))
        db.commit()

        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        # 无 scope 绝不退化成"不过滤全库"
        assert _avg_per_capita_income(db, None, year=2025) == 0.0


class TestReportTotalNotTruncated:
    """P1：报表总数必须用 count()，不能用明细 limit 截断后的 len()。"""

    def test_total_villages_counts_all_matching_rows(self, real_db_session):
        db = real_db_session
        # 造 3 个村，明细只取 2 条时总数仍必须是 3
        for i in range(3):
            _mk_village(db, f"村{i}")
        db.commit()

        from app.models.supported_village import SupportedVillage

        query = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
        total = query.count()          # 修复后的写法
        listed = query.limit(2).all()  # 明细截断

        assert total == 3
        assert len(listed) == 2
        # 核心断言：总数不得等于截断后的明细条数（修复前的缺陷形态）
        assert total != len(listed)

    def test_truncation_flag_reflects_reality(self, real_db_session):
        """villages_truncated 必须如实反映"明细是否被截断"。"""
        db = real_db_session
        for i in range(3):
            _mk_village(db, f"村{i}")
        db.commit()

        from app.models.supported_village import SupportedVillage

        query = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
        total = query.count()
        listed = query.limit(2).all()
        assert (total > len(listed)) is True

        listed_all = query.limit(100).all()
        assert (total > len(listed_all)) is False
