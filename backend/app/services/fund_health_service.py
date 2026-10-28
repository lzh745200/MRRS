"""资金健康评分服务。

从 projects.py 提取的健康评分逻辑。
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.fund import Fund
from app.models.fund_lifecycle import FundAnomaly

logger = logging.getLogger(__name__)


class FundHealthService:
    """资金健康状态计算和监控（异步版本，保留兼容）。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_health_score(self, fund_id: int) -> dict:
        """计算单个资金记录的健康评分（0-100）。"""
        fund = await self.db.get(Fund, fund_id)
        if not fund:
            return {"fund_id": fund_id, "score": 0, "status": "not_found"}

        score = 100

        # 检查未解决的异常
        anomalies_result = await self.db.execute(
            select(func.count(FundAnomaly.id))
            .where(FundAnomaly.fund_id == fund_id, FundAnomaly.resolved == False)  # noqa: E712
        )
        unresolved = anomalies_result.scalar() or 0
        score -= min(unresolved * 10, 40)

        # 检查预算使用率（使用批准金额或计划金额作为预算基准）
        budget = fund.approved_amount or fund.planned_amount or fund.amount
        if budget and float(budget) > 0:
            usage_rate = float(fund.used_amount or 0) / float(budget)
            if usage_rate > 1.0:
                score -= 20  # 超预算
            elif usage_rate > 0.9:
                score -= 5   # 接近超预算

        score = max(0, min(100, score))
        status = "healthy" if score >= 80 else ("warning" if score >= 60 else "critical")
        return {
            "fund_id": fund_id,
            "score": score,
            "status": status,
            "unresolved_anomalies": unresolved,
        }


# ── 同步版（供 FastAPI 同步 Session 端点调用） ──────────────────────────


def _score_budget_usage(fund) -> float:
    """预算执行维度：超预算/接近超预算/正常"""
    budget = fund.approved_amount or fund.planned_amount or fund.amount or 0
    used = fund.used_amount or 0
    try:
        budget, used = float(budget), float(used)
    except (TypeError, ValueError):
        return 100.0
    if budget <= 0:
        return 100.0
    rate = used / budget
    if rate > 1.0:
        return 40.0
    if rate > 0.9:
        return 70.0
    return 100.0


def _score_anomaly(unresolved: int) -> float:
    """异常维度：每个未解决异常扣 10 分，最多扣 40"""
    return max(0.0, 100.0 - min(unresolved * 10, 40))


def _score_phase_completion(db, project_id: int) -> float:
    """决算/阶段完成维度：已完成阶段数 / 总阶段数 * 100"""
    from app.models.fund_lifecycle import ProjectFundPhase

    total = (
        db.query(ProjectFundPhase)
        .filter(ProjectFundPhase.project_id == project_id)
        .count()
    )
    if total <= 0:
        return 100.0
    done = (
        db.query(ProjectFundPhase)
        .filter(
            ProjectFundPhase.project_id == project_id,
            ProjectFundPhase.status == "completed",
        )
        .count()
    )
    return round(done / total * 100, 1)


def _score_payment_timeliness(funds) -> float:
    """支付及时性：已审批未拨付的占比越低越好（无审批记录视为中性 80）"""
    if not funds:
        return 80.0
    approved = [f for f in funds if f.approval_date is not None]
    if not approved:
        return 80.0
    allocated = [f for f in approved if f.allocation_date is not None]
    return round(len(allocated) / len(approved) * 100, 1)


def _score_voucher_completeness(funds) -> float:
    """凭证完整维度：有用途说明/使用金额的记录占比（可用数据中性 80）"""
    if not funds:
        return 80.0
    has_voucher = [
        f for f in funds
        if (f.usage_description or "").strip() or (f.remaining_amount is not None)
    ]
    return round(len(has_voucher) / len(funds) * 100, 1)


def _score_contract_fulfillment(db, project_id: int) -> float:
    """合同履约维度：按合同状态与逾期情况计分（R27-H7：改真实计算）。

    历史缺陷（R27 报告 H7 / R20 登记未修）：旧实现查询合同总数后
    **无条件返回 90.0** —— ``total`` 从未参与任何计算，项目详情/健康度展示的
    「合同履约」分项与真实合同数据完全无关（误导性假数据）。

    新口径（基线 100，逐份合同按最严重适用项扣分，下限 0）：
      - 终止 terminated：-20/份（合同失败，履约维度重扣）；
      - 逾期（deadline 已过且非 completed）：-10/份；
      - 草稿 draft（尚未生效）：-5/份；
      - 履约中 active（及未知历史状态）：-2/份；
      - 已完成 completed：不扣分。
    无有效合同时返回中性 90（与旧行为一致 —— 无合同不等于履约完美）；
    查询异常返回 90（保持既有容错契约，不让评分链路 500）。
    """
    from datetime import date

    from app.models.fund_lifecycle import ContractStatus, FundContract

    try:
        rows = (
            db.query(FundContract.status, FundContract.deadline)
            .filter(FundContract.project_id == project_id)
            .all()
        )
    except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
        logger.warning('_score_contract_fulfillment 兜底失败（已降级）: %s', exc, exc_info=True)
        return 90.0
    if not rows:
        return 90.0

    today = date.today()
    score = 100.0
    for status, deadline in rows:
        value = getattr(status, "value", status)
        # hasattr(deadline, "year") 拦截非日期对象（防御历史脏数据/测试替身），
        # 避免 str < date 抛 TypeError 把健康度整链打崩。
        if value == ContractStatus.TERMINATED.value:
            score -= 20
        elif value == ContractStatus.COMPLETED.value:
            continue
        elif deadline is not None and hasattr(deadline, "year") and deadline < today:
            score -= 10
        elif value == ContractStatus.DRAFT.value:
            score -= 5
        else:
            # active 与未知历史状态：轻微扣分（绝不静默满分）
            score -= 2
    return round(max(0.0, score), 1)


def calculate_project_health_sync(db, project_id: int) -> dict:
    """按项目聚合其下全部资金记录计算健康度（同步 Session，供 API 端点调用）。

    返回结构对齐前端 HealthScore：{health_score, details: {key: {score, weight}}}。
    """
    # M18（R27 排查）：软删经费（is_active=False）不得计入健康度 ——
    # 旧实现不滤软删，已删除的经费仍参与预算/凭证/及时性分项计算。
    funds = (
        db.query(Fund)
        .filter(Fund.project_id == project_id, Fund.is_active.is_(True))
        .all()
    )
    unresolved = (
        db.query(func.count(FundAnomaly.id))
        .filter(FundAnomaly.project_id == project_id, FundAnomaly.resolved.is_(False))
        .scalar()
        or 0
    )
    anomalies_total = (
        db.query(func.count(FundAnomaly.id))
        .filter(FundAnomaly.project_id == project_id)
        .scalar()
        or 0
    )

    details = {
        "budget_execution": {
            "score": round(sum(_score_budget_usage(f) for f in funds) / len(funds), 1)
            if funds else 100.0,
            "weight": 30,
        },
        "payment_timeliness": {"score": _score_payment_timeliness(funds), "weight": 20},
        "voucher_completeness": {"score": _score_voucher_completeness(funds), "weight": 15},
        "anomaly_count": {
            "score": _score_anomaly(unresolved),
            "weight": 20,
            "unresolved": unresolved,
            "total": anomalies_total,
        },
        "contract_fulfillment": {"score": _score_contract_fulfillment(db, project_id), "weight": 5},
        "settlement_completion": {"score": _score_phase_completion(db, project_id), "weight": 10},
    }

    total_weight = sum(d["weight"] for d in details.values())
    health_score = round(
        sum(d["score"] * d["weight"] for d in details.values()) / total_weight, 1
    )
    return {
        "project_id": project_id,
        "health_score": health_score,
        "status": "healthy" if health_score >= 80 else ("warning" if health_score >= 60 else "critical"),
        "fund_count": len(funds),
        "details": details,
    }


def calculate_projects_health_sync(db, project_ids) -> list:
    """批量计算多项目健康度（项目列表用）"""
    return [calculate_project_health_sync(db, pid) for pid in project_ids]
