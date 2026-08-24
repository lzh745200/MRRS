"""补齐 app.models.fund_budget 覆盖率缺口（a23）。

缺口：FundBudget.remaining_amount (65)、FundBudget.execution_rate (69-72)、
check_budget_alerts (159-189)。纯 Python 属性/函数，直接调用即可。
"""

from app.models.fund_budget import FundBudget, check_budget_alerts


class TestRemainingAmount:
    def test_normal(self):
        b = FundBudget(year=2024, category="education", budget_amount=100, executed_amount=30)
        assert b.remaining_amount == 70.0

    def test_none_amounts(self):
        b = FundBudget(year=2024, category="education", budget_amount=None, executed_amount=None)
        assert b.remaining_amount == 0.0


class TestExecutionRate:
    def test_zero_budget_returns_zero(self):
        b = FundBudget(year=2024, category="education", budget_amount=0, executed_amount=10)
        assert b.execution_rate == 0.0

    def test_none_budget_returns_zero(self):
        b = FundBudget(year=2024, category="education", budget_amount=None, executed_amount=None)
        assert b.execution_rate == 0.0

    def test_normal_rate(self):
        b = FundBudget(year=2024, category="education", budget_amount=200, executed_amount=50)
        assert b.execution_rate == 25.0


class TestCheckBudgetAlerts:
    def test_empty_list(self):
        assert check_budget_alerts([]) == []

    def test_zero_budget_skipped(self):
        b = FundBudget(id=1, year=2024, category="education", budget_amount=0, executed_amount=0)
        assert check_budget_alerts([b]) == []

    def test_danger_level_at_100_percent(self):
        """ADR-0009：≥100% 为 danger（禁止核销）。"""
        b = FundBudget(id=2, year=2024, category="medical", budget_amount=100, executed_amount=100)
        alerts = check_budget_alerts([b])
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["budget_id"] == 2
        assert alert["level"] == "danger"
        assert alert["execution_rate"] == 100.0
        assert alert["year"] == 2024
        assert alert["category"] == "medical"
        assert "禁止继续核销" in alert["message"]

    def test_critical_level_at_95_percent(self):
        """ADR-0009：90%~100% 为 critical（接近禁止线）。"""
        b = FundBudget(id=5, year=2024, category="culture", budget_amount=100, executed_amount=95)
        alerts = check_budget_alerts([b])
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["level"] == "critical"
        assert alert["execution_rate"] == 95.0
        assert "接近禁止线" in alert["message"]

    def test_info_level_at_80_to_90(self):
        """ADR-0009：80%~90% 为 info（提醒）。"""
        b = FundBudget(id=3, year=2024, category="industry", budget_amount=100, executed_amount=85)
        alerts = check_budget_alerts([b])
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["level"] == "info"
        assert alert["execution_rate"] == 85.0

    def test_below_threshold_no_alert(self):
        b = FundBudget(id=4, year=2024, category="other", budget_amount=100, executed_amount=50)
        assert check_budget_alerts([b]) == []

    def test_mixed_budgets(self):
        budgets = [
            FundBudget(id=1, year=2024, category="a", budget_amount=0, executed_amount=0),
            FundBudget(id=2, year=2024, category="b", budget_amount=100, executed_amount=102),
            FundBudget(id=3, year=2024, category="c", budget_amount=100, executed_amount=92),
            FundBudget(id=4, year=2024, category="d", budget_amount=100, executed_amount=85),
            FundBudget(id=5, year=2024, category="e", budget_amount=100, executed_amount=10),
        ]
        alerts = check_budget_alerts(budgets)
        assert [a["level"] for a in alerts] == ["danger", "critical", "info"]
        assert [a["budget_id"] for a in alerts] == [2, 3, 4]
