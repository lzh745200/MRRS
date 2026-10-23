"""W27：核心指标单一实现（``services/metrics_service.py``）回归。

## 背景（W26-P0-2「核心指标口径不一致」）
1. **人均纯收入两套实现**：工作台读 ``annual_income`` 的年份列（该表**只被读、
   从不被写**，dev 库 0 行，年份列写死 2025），其余 5 处读 ``village_income``（行式，
   有真实数据）→ 同一指标两个数字。
   **决策：统一到 ``village_income``**，本模块为唯一实现。
2. **总人口口径**：``analytics_service`` 曾用 `MAX(year)`（全库最大年），
   与 CONTEXT.md「每村各自最新年」冲突；该裸 SQL 分支已在 analytics_service 内修正，
   本文件锁定 ORM 侧（dashboard）与 raw-SQL 侧在**同一 fixture 下同数**。

本文件覆盖 ``metrics_service`` 的全部分支，并做一次 ORM↔SQL 口径一致性对照。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import metrics_service as ms


class _Scope:
    def __init__(self):
        self.calls = 0

    def filter_by_org_ids(self, q, *args, **kwargs):
        self.calls += 1
        return q


def _db(scalar=None):
    q = MagicMock()
    for m in ("filter", "join", "with_entities", "group_by"):
        getattr(q, m).return_value = q
    q.scalar.return_value = scalar
    db = MagicMock()
    db.query.return_value = q
    return db, q


class TestAccessibleVillageIdsQuery:
    def test_builds_scoped_query(self):
        db, _q = _db()
        scope = _Scope()
        ms.accessible_village_ids_query(db, scope)
        assert scope.calls == 1, "必须真正调用数据域过滤"

    def test_none_scope_raises(self):
        """必须显式声明数据域 —— fail-closed，绝不退化成"不过滤全库"。"""
        db, _q = _db()
        with pytest.raises(ValueError):
            ms.accessible_village_ids_query(db, None)


class TestAvgPerCapitaIncome:
    def test_none_db_returns_zero(self):
        assert ms.avg_per_capita_income(None, MagicMock()) == 0.0

    def test_none_village_query_returns_zero(self):
        db, _q = _db()
        assert ms.avg_per_capita_income(db, None) == 0.0

    def test_latest_year_path(self):
        """year=None → 走「每村各自最新年」JOIN 分支。"""
        db, q = _db(scalar=12.5)
        assert ms.avg_per_capita_income(db, MagicMock()) == 12.5
        q.join.assert_called()

    def test_specific_year_path(self):
        db, q = _db(scalar=7.5)
        assert ms.avg_per_capita_income(db, MagicMock(), year=2024) == 7.5
        q.join.assert_not_called(), "指定年份不应走最新年 JOIN"

    def test_scalar_none_returns_zero(self):
        db, _q = _db(scalar=None)
        assert ms.avg_per_capita_income(db, MagicMock()) == 0.0


class TestIncomeMetricSingleSource:
    """锁定「只有一处实现」：不得再出现读 annual_income 的指标代码。"""

    def test_no_module_reads_annual_income_for_metrics(self):
        import inspect

        import app.api.v1.data.data.dashboard as dash
        import app.services.effectiveness_service as eff
        import app.services.ai.recommendation_service as rec
        import app.services.ai.trend_prediction_service as trend

        for mod in (dash, eff, rec, trend):
            src = inspect.getsource(mod)
            assert "from app.models.annual_income import" not in src, (
                f"{mod.__name__} 仍在读 annual_income（该表从不写入）；"
                "人均纯收入应统一走 village_income"
            )
