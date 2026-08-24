"""Tests for app.api.v1.fund_budgets — 补齐校验器、筛选项与金额联动分支。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1 import fund_budgets as fb


def _user():
    u = MagicMock()
    u.id = 1
    u.role = "manager"
    u.is_superuser = True
    u.full_name = "Admin"
    u.username = "admin"
    return u


class TestPurposeValidator:
    def test_whitespace_only_purpose_rejected(self):
        with pytest.raises(ValidationError):
            fb.TransactionCreate(amount=1.0, purpose="   ", transaction_date=date(2025, 1, 1))


class TestGetTransactionsFilters:
    async def test_project_and_budget_filters(self):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        db = MagicMock()
        db.query.return_value = q

        result = await fb.get_transactions(
            fund_id=1, project_id=2, village_id=3, budget_id=4,
            page=1, page_size=20, current_user=_user(), db=db,
        )
        assert result == []


class TestCreateTransactionLinks:
    async def test_updates_budget_and_fund(self):
        """核销联动：预算 executed 与 Fund used/remaining 同步更新（额度内）。"""
        data = fb.TransactionCreate(
            amount=5000.0, purpose="修路", transaction_date=date(2025, 6, 15),
            budget_id=1, fund_id=2,
        )
        q_budget = MagicMock()
        budget = MagicMock()
        budget.executed_amount = 100.0
        budget.budget_amount = 10000.0  # 核销后 51%，未触发 ADR-0009 禁止线
        q_budget.filter.return_value = q_budget
        q_budget.first.return_value = budget

        q_fund = MagicMock()
        fund = MagicMock()
        fund.used_amount = 200.0
        fund.allocated_amount = 1000.0
        q_fund.filter.return_value = q_fund
        q_fund.first.return_value = fund

        db = MagicMock()
        db.query.side_effect = [q_budget, q_fund]

        with patch.object(fb, "write_work_log"):
            tx = await fb.create_transaction(data=data, current_user=_user(), db=db)

        assert float(budget.executed_amount) == 5100.0
        assert float(fund.used_amount) == 5200.0
        assert float(fund.remaining_amount) == 1000.0 - 5200.0
        db.add.assert_called()
        assert tx is not None

    async def test_overspend_blocked_at_danger_line(self):
        """ADR-0009：核销导致执行率超 100% → 400 拒绝。"""
        data = fb.TransactionCreate(
            amount=5000.0, purpose="超支核销", transaction_date=date(2025, 6, 15),
            budget_id=1,
        )
        q_budget = MagicMock()
        budget = MagicMock()
        budget.executed_amount = 100.0
        budget.budget_amount = 5000.0  # 核销后 102% → 阻断
        q_budget.filter.return_value = q_budget
        q_budget.first.return_value = budget

        db = MagicMock()
        db.query.side_effect = [q_budget]

        with pytest.raises(HTTPException) as exc_info:
            await fb.create_transaction(data=data, current_user=_user(), db=db)
        assert exc_info.value.status_code == 400
        assert "禁止核销" in str(exc_info.value.detail)


class TestDeleteTransactionFundLink:
    async def test_rolls_back_fund_amounts(self):
        tx = MagicMock()
        tx.budget_id = None
        tx.fund_id = 2
        tx.amount = 100.0

        q_tx = MagicMock()
        q_tx.filter.return_value = q_tx
        q_tx.first.return_value = tx

        q_fund = MagicMock()
        fund = MagicMock()
        fund.used_amount = 500.0
        fund.allocated_amount = 1000.0
        q_fund.filter.return_value = q_fund
        q_fund.first.return_value = fund

        db = MagicMock()
        db.query.side_effect = [q_tx, q_fund]

        result = await fb.delete_transaction(transaction_id=1, current_user=_user(), db=db)

        assert result["code"] == 200
        assert result["success"] is True
        assert result["message"] == "删除成功"
        assert fund.used_amount == 400.0
        assert fund.remaining_amount == 600.0
        db.delete.assert_called_once_with(tx)
