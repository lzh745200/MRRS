"""fund_budgets.py 分支覆盖缺口专项（分支清零第五批）。

覆盖 coverage report --show-missing 实测的 7 个部分分支：
- TransactionCreate.validate_purpose：purpose=None 的假分支（91->95）；
- create_budget：used_amount=None → pop 后不写 executed_amount（200->204，
  原「键不存在」分支经等价重构后可达）；
- get_budget_summary：同科目预算复用汇总桶（308->310）；
- create_transaction：未关联预算/Fund 的跳过分支（390->398）；
- delete_transaction：tx 无 budget_id / fund_id 的跳过分支（423->427、429->433）；
- _apply_budget_execution：budget_total≤0 → 跳过 100% 上限 WHERE（507->511）。

全部为直调函数级用例（asyncio_mode=auto），不依赖 TestClient。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1.fund_budgets import (
    BudgetCreate,
    TransactionCreate,
    _apply_budget_execution,
    create_budget,
    create_transaction,
    delete_transaction,
    get_budget_summary,
)
from app.models.fund_budget import FundBudget, FundTransaction
from app.models.fund import Fund


def _admin():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.is_active = True
    u.permissions_list = ["*"]
    u.organization_id = 1
    return u


async def test_validate_purpose_none_returns_none():
    """purpose=None（可选形态校验直调）→ if v 为假，原样返回（91->95）。"""
    assert TransactionCreate.validate_purpose(None) is None


async def test_create_budget_with_none_used_amount():
    """used_amount=None → pop 后为 None → executed_amount 不写入（200->204 假分支）。"""
    data = BudgetCreate(year=2026, category="education", budget_amount=1000.0, used_amount=None)
    db = MagicMock()
    await create_budget(data=data, current_user=_admin(), db=db)
    budget = db.add.call_args[0][0]
    assert isinstance(budget, FundBudget)
    assert budget.year == 2026
    assert budget.budget_amount == 1000.0
    # 前端字段 used_amount 不落入模型，executed_amount 保持默认
    assert not hasattr(budget, "used_amount")


async def test_budget_summary_reuses_category_bucket():
    """同科目两条预算 → 复用同一汇总桶（308->310 假分支）。"""
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q  # 链式调用必须自链，否则 all() 落到未配置的新 mock
    q.all.return_value = [
        SimpleNamespace(category="education", budget_amount=100, executed_amount=30, year=2026),
        SimpleNamespace(category="education", budget_amount=200, executed_amount=70, year=2026),
    ]
    db.query.return_value = q
    with patch("app.api.v1.fund_budgets.apply_data_scope", side_effect=lambda query, *a, **k: query):
        resp = await get_budget_summary(year=2026, current_user=_admin(), db=db)
    data = resp["data"] if isinstance(resp, dict) and "data" in resp else resp
    # 断言按科目汇总存在且金额正确累加（100+200 / 30+70）
    text = str(data)
    assert "300" in text
    assert "100" in text


async def test_create_transaction_without_fund_and_budget():
    """未关联预算与 Fund → 两处关联更新块整体跳过（382-398 的假分支）。"""
    data = TransactionCreate(
        amount=100.0,
        purpose="差旅支出",
        transaction_date=__import__("datetime").date(2026, 10, 7),
        budget_id=None,
        fund_id=None,
    )
    db = MagicMock()
    resp = await create_transaction(data=data, current_user=_admin(), db=db)
    # create_transaction 还会写一条 WorkLog 审计记录，按类型过滤出交易本体
    tx_calls = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], FundTransaction)]
    assert len(tx_calls) == 1
    tx = tx_calls[0]
    assert tx.amount == 100.0
    assert tx.created_by == 1


async def test_delete_transaction_without_relations():
    """tx 无 budget_id / fund_id → 两处减回块整体跳过（423->427、429->433）。"""
    tx = SimpleNamespace(id=9, budget_id=None, fund_id=None, amount=100.0)
    db = MagicMock()
    with patch("app.api.v1.fund_budgets._get_transaction_or_404", return_value=tx):
        await delete_transaction(transaction_id=9, current_user=_admin(), db=db)
    db.delete.assert_called_once_with(tx)


def test_apply_budget_execution_zero_total_skips_cap_guard():
    """budget_total≤0 → 跳过 100% 上限 WHERE 子句（507->511 假分支）。"""
    db = MagicMock()
    db.execute.return_value.rowcount = 1
    budget = SimpleNamespace(id=1, budget_amount=0)
    _apply_budget_execution(db, budget, 50.0)
    db.execute.assert_called_once()


def test_apply_budget_execution_under_cap_hits_guard():
    """budget_total>0 → 上限 WHERE 生效（守门不回归）。"""
    db = MagicMock()
    db.execute.return_value.rowcount = 1
    budget = SimpleNamespace(id=1, budget_amount=1000)
    _apply_budget_execution(db, budget, 50.0)
    db.execute.assert_called_once()


async def test_create_transaction_with_missing_fund():
    """fund_id 有值但 Fund 已不存在 → 内层 if fund 为假，跳过联动更新（390->398）。"""
    data = TransactionCreate(
        amount=50.0,
        purpose="对方账户已删除的支出",
        transaction_date=__import__("datetime").date(2026, 10, 7),
        budget_id=None,
        fund_id=999,
    )
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q
    await create_transaction(data=data, current_user=_admin(), db=db)
    tx_calls = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], FundTransaction)]
    assert len(tx_calls) == 1


async def test_delete_transaction_with_missing_relations():
    """budget_id/fund_id 有值但记录均已不存在 → 两处内层 if 为假（423->427、429->433）。"""
    tx = SimpleNamespace(id=9, budget_id=5, fund_id=7, amount=100.0)
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q
    with patch("app.api.v1.fund_budgets._get_transaction_or_404", return_value=tx):
        await delete_transaction(transaction_id=9, current_user=_admin(), db=db)
    db.delete.assert_called_once_with(tx)
