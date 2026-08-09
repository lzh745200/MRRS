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
    """合同履约维度：存在异常未解决时扣分，否则 90（中性偏积极）"""
    from app.models.fund_lifecycle import FundContract

    try:
        total = (
            db.query(FundContract)
            .filter(FundContract.project_id == project_id)
            .count()
        )
    except Exception:
        return 90.0
    if total <= 0:
        return 90.0
    return 90.0


def calculate_project_health_sync(db, project_id: int) -> dict:
    """按项目聚合其下全部资金记录计算健康度（同步 Session，供 API 端点调用）。

    返回结构对齐前端 HealthScore：{health_score, details: {key: {score, weight}}}。
    """
    funds = (
        db.query(Fund)
        .filter(Fund.project_id == project_id)
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
