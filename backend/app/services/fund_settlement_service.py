"""经费决算金额一致性维护（短期项 2，2026-11-01 审计）。

缺陷：决算生成时按当时经费快照写入 ``total_budget/total_spent/total_remaining``；
之后新增经费、追加支出、或只改预算/支出单字段，决算里的结余不再重算 —— 审批后
错误金额被固化进档案。本模块提供唯一的重算入口，供经费写操作与决算更新调用。
"""

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.fund_lifecycle import FundSettlement, SettlementStatus

logger = logging.getLogger(__name__)


def _quantize(value: Any) -> Decimal:
    """金额统一落 4 位小数（与模型 Numeric(15, 4) 一致，避免浮点残差）。"""
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"))


def _fund_budget(fund: Fund) -> float:
    """按扩展口径取单条经费的预算：批准额 > 计划额 > 申报额。"""
    return float(fund.approved_amount or fund.planned_amount or fund.amount or 0)


def recalculate_settlement_totals(db: Session, settlement: FundSettlement) -> FundSettlement:
    """按项目当前经费重算单张未审批决算（原地修改，不提交）。"""
    if settlement.project_id is None:
        return settlement
    funds = db.query(Fund).filter(Fund.project_id == settlement.project_id).all()
    total_budget = sum(_fund_budget(f) for f in funds)
    total_spent = sum(float(f.used_amount or 0) for f in funds)
    settlement.total_budget = _quantize(total_budget)
    settlement.total_spent = _quantize(total_spent)
    settlement.total_remaining = _quantize(total_budget - total_spent)
    return settlement


def refresh_project_settlements(db: Session, project_id: Any) -> int:
    """重算项目下所有未审批决算，返回被更新的条数（不提交事务）。

    - 无 project_id（或非整数）→ 0；
    - 已审批（APPROVED）决算视为固化档案，**不得**改写；
    - 调用方负责 ``safe_commit``，与业务写入同事务提交。
    """
    if not project_id:
        return 0
    try:
        project_key = int(project_id)
    except (TypeError, ValueError):
        return 0

    settlements = (
        db.query(FundSettlement)
        .filter(FundSettlement.project_id == project_key)
        .all()
    )
    touched = 0
    for settlement in settlements:
        if settlement.status == SettlementStatus.APPROVED.value:
            continue
        recalculate_settlement_totals(db, settlement)
        touched += 1
    if touched:
        logger.info("重算项目 %s 的未审批决算 %s 条", project_key, touched)
    return touched
