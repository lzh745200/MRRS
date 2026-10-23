"""``dashboard._avg_per_capita_income`` 回归（W27：已统一到 ``village_income`` 行式表）。

## 变更背景（W26-P0-2）
原实现读 ``annual_income`` 表的**年份列**（`per_capita_income_2020..2025`），
而该表**只被读、从不被写**（全仓 0 处写入，dev 库 0 行），且年份列写死到 2025 ——
工作台人均收入因此恒为 0/陈旧，与其余 5 处读 ``village_income`` 的实现给出两个数字。

现 `_avg_per_capita_income` 委托 ``services.metrics_service.avg_per_capita_income``
（单一实现，数据源 ``village_income``）。本文件锁定：
1. 有数据时返回平均值；
2. 无数据 / 未指定数据域 / 查询异常 → **fail-closed 返回 0.0**（绝不退化成不过滤全库）；
3. 数据域必须真正接线（filter_by_org_ids 被调用）。
"""

from unittest.mock import MagicMock

import pytest


class _Scope:
    """最小 OrgScopeFilter 替身：记录 filter_by_org_ids 是否被调用。"""

    def __init__(self):
        self.calls = 0

    def filter_by_org_ids(self, q, *args, **kwargs):
        self.calls += 1
        return q

    def has_full_access(self):
        return False


def _db_with_scalar(value):
    q = MagicMock()
    q.filter.return_value = q
    q.join.return_value = q
    q.with_entities.return_value = q
    q.scalar.return_value = value
    db = MagicMock()
    db.query.return_value = q
    return db, q


class TestAvgPerCapitaIncomeUnified:
    def test_returns_average_from_village_income(self):
        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        db, _q = _db_with_scalar(1234.5)
        scope = _Scope()
        assert _avg_per_capita_income(db=db, data_scope=scope) == 1234.5
        assert scope.calls == 1, "数据域必须真正接线（不得收下形参不用）"

    def test_specific_year_filter(self):
        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        db, _q = _db_with_scalar(500.0)
        assert _avg_per_capita_income(db=db, data_scope=_Scope(), year=2024) == 500.0

    def test_scalar_none_returns_zero(self):
        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        db, _q = _db_with_scalar(None)
        assert _avg_per_capita_income(db=db, data_scope=_Scope()) == 0.0

    def test_no_data_scope_fail_closed(self):
        """无数据域 → 0.0（fail-closed），绝不查询全库。"""
        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        db, _q = _db_with_scalar(999.0)
        assert _avg_per_capita_income(db=db, data_scope=None) == 0.0

    def test_exception_returns_zero(self):
        """查询异常 → fail-closed 0.0（不让仪表盘整体 500）。"""
        from app.api.v1.data.data.dashboard import _avg_per_capita_income

        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        assert _avg_per_capita_income(db=db, data_scope=_Scope()) == 0.0

    def test_uses_village_income_not_annual_income(self):
        """核心回归：不得再触碰 annual_income（该表从无写入、dev 库 0 行）。"""
        import inspect

        from app.api.v1.data.data import dashboard as dash

        src = inspect.getsource(dash._avg_per_capita_income)
        assert "annual_income" not in src.replace("``annual_income``", ""), (
            "实现不应再引用 annual_income"
        )
        assert "village_income" in src or "metrics_service" in src
