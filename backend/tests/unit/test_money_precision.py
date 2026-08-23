"""金额统一保留4位小数（四舍五入）回归测试。

背景：原口径为2位小数（前端 step=0.01 + 后端 round(x,2)），
需求变更为全系统金额字段统一 4 位小数、ROUND_HALF_UP。
"""
from decimal import Decimal

import pytest

from app.models.fund import BudgetRecord, Fund
from app.models.project import Project
from app.utils.helpers import (
    BUDGET_MONEY_FIELDS,
    FUND_MONEY_FIELDS,
    quantize_money,
    quantize_money_fields,
)


class TestQuantizeMoney:
    def test_rounds_to_4_places_half_up(self):
        assert quantize_money("1.23456") == Decimal("1.2346")
        assert quantize_money(1.23455) == Decimal("1.2346")
        assert quantize_money(0.00005) == Decimal("0.0001")

    def test_keeps_4_places(self):
        assert quantize_money(1.2345) == Decimal("1.2345")
        assert quantize_money("12.34") == Decimal("12.3400")

    def test_none_returns_zero(self):
        assert quantize_money(None) == Decimal("0")

    def test_invalid_returns_zero(self):
        assert quantize_money("abc") == Decimal("0")

    def test_negative_allowed_for_computation(self):
        assert quantize_money(-1.23456) == Decimal("-1.2346")


class TestQuantizeMoneyFields:
    def test_quantizes_only_money_fields(self):
        payload = {"amount": 1.00005, "name": "x", "used_amount": None}
        out = quantize_money_fields(payload)
        assert out["amount"] == Decimal("1.0001")
        assert out["name"] == "x"
        assert out["used_amount"] is None

    def test_budget_fields_constant(self):
        assert BUDGET_MONEY_FIELDS == frozenset(
            {"budget_amount", "executed_amount", "used_amount"}
        )


class TestModelColumnScale:
    """锁定模型列精度契约：金额列 scale=4。"""

    @pytest.mark.parametrize(
        "field", ["budget", "actual_cost", "invested_amount", "total_budget_estimate"]
    )
    def test_project_money_columns_scale_4(self, field):
        col = getattr(Project, field).property.columns[0]
        assert col.type.scale == 4
        assert col.type.precision == 15

    @pytest.mark.parametrize(
        "field",
        [
            "amount", "planned_amount", "approved_amount",
            "allocated_amount", "used_amount", "remaining_amount",
        ],
    )
    def test_fund_money_columns_scale_4(self, field):
        col = getattr(Fund, field).property.columns[0]
        assert col.type.scale == 4

    @pytest.mark.parametrize("field", ["budget_amount", "used_amount"])
    def test_budget_record_columns_scale_4(self, field):
        col = getattr(BudgetRecord, field).property.columns[0]
        assert col.type.scale == 4

    def test_ratio_columns_stay_scale_2(self):
        col = Fund.deviation_rate.property.columns[0]
        assert col.type.scale == 2


class TestProjectWritePathQuantize:
    def test_convert_update_fields_quantizes_budget(self):
        from app.api.v1.projects import _convert_update_fields

        update_data = {"budget": 1.23456}
        _convert_update_fields(update_data)
        assert update_data["budget"] == Decimal("1.2346")
