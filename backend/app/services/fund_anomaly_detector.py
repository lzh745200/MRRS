"""经费异常检测引擎

检测规则（规则引擎方式，可扩展）：
- 超支：已用 > 已批 × 阈值
- 偏差：|实际进度 - 计划进度| > 阈值
- 资金闲置：已拨付 > 30天未动用
- 重复支付：同一凭证号 / 相近金额+日期
- 缺失凭证：支出无对应 FundTransaction
"""

from datetime import datetime
from typing import List

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.fund_budget import FundTransaction
from app.models.fund_lifecycle import AnomalySeverity, AnomalyType, FundAnomaly
from app.utils.time_utils import as_utc, utcnow

# ---------- 阈值配置 ----------

OVERSPEND_WARNING = 0.90  # 已用 ≥ 已批 90% → warning
OVERSPEND_DANGER = 1.00  # 已用 ≥ 已批 100% → danger
DEVIATION_THRESHOLD = 15.0  # 进度偏差 > 15% 视为异常
IDLE_DAYS = 30  # 拨付后 30 天未使用视为闲置
DUPLICATE_AMOUNT_TOLERANCE = 0.01  # 金额容差（万元）
DUPLICATE_DATE_DAYS = 3  # 日期容差（天）
LARGE_CASH_THRESHOLD = 50.0  # 大额提现阈值（50万元）
CONTRACT_SPLIT_DAYS = 30  # 合同拆分检测时间窗口（30天）
CONTRACT_SPLIT_COUNT = 3  # 同一供应商合同数量阈值


def detect_anomalies(db: Session, project_id: int) -> List[dict]:
    """对指定项目运行全部检测规则，返回新发现的异常列表。"""
    results: List[dict] = []

    # 获取项目关联的经费记录
    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    if not funds:
        return results

    for fund in funds:
        results.extend(_check_overspend(fund))
        results.extend(_check_deviation(fund))
        results.extend(_check_idle(fund))

    # 跨记录检测
    results.extend(_check_duplicate_payments(db, project_id))
    results.extend(_check_missing_vouchers(db, project_id, funds))
    results.extend(_check_large_cash(db, project_id))
    results.extend(_check_contract_split(db, project_id))
    results.extend(_check_single_source(db, project_id))

    # 写入数据库（去重：同项目+同类型+同经费 且未解决的不重复写入）
    new_anomalies = []
    for r in results:
        exists = (
            db.query(FundAnomaly)
            .filter(
                FundAnomaly.project_id == project_id,
                FundAnomaly.fund_id == r.get("fund_id"),
                FundAnomaly.anomaly_type == r["anomaly_type"],
                FundAnomaly.resolved == False,  # noqa: E712
            )
            .first()
        )
        if not exists:
            anomaly = FundAnomaly(
                fund_id=r.get("fund_id"),
                project_id=project_id,
                anomaly_type=r["anomaly_type"],
                severity=r["severity"],
                description=r["description"],
            )
            db.add(anomaly)
            new_anomalies.append(r)

    # 更新 Fund.has_anomaly 标志
    for fund in funds:
        unresolved = (
            db.query(sa_func.count(FundAnomaly.id))
            .filter(
                FundAnomaly.fund_id == fund.id,
                FundAnomaly.resolved == False,  # noqa: E712
            )
            .scalar()
            or 0
        )
        fund.has_anomaly = unresolved > 0

    db.flush()
    return new_anomalies


# ==================== 检测规则 ====================


def _check_overspend(fund: Fund) -> List[dict]:
    """超支检测"""
    approved = float(fund.approved_amount or fund.amount or 0)
    used = float(fund.used_amount or 0)
    if approved <= 0:
        return []

    ratio = used / approved
    if ratio >= OVERSPEND_DANGER:
        return [
            {
                "fund_id": fund.id,
                "anomaly_type": AnomalyType.OVERSPEND.value,
                "severity": AnomalySeverity.DANGER.value,
                "description": f"经费「{fund.name or fund.id}」已使用 {used:.2f} 万元，"
                f"超过批准额 {approved:.2f} 万元（比例 {ratio*100:.1f}%）",
            }
        ]
    elif ratio >= OVERSPEND_WARNING:
        return [
            {
                "fund_id": fund.id,
                "anomaly_type": AnomalyType.OVERSPEND.value,
                "severity": AnomalySeverity.WARNING.value,
                "description": f"经费「{fund.name or fund.id}」使用率已达 {ratio*100:.1f}%，"
                f"接近批准额 {approved:.2f} 万元",
            }
        ]
    return []


def _check_deviation(fund: Fund) -> List[dict]:
    """进度-支付偏差检测"""
    deviation = float(fund.deviation_rate or 0)
    if abs(deviation) <= DEVIATION_THRESHOLD:
        return []

    severity = AnomalySeverity.DANGER.value if abs(deviation) > 30 else AnomalySeverity.WARNING.value
    return [
        {
            "fund_id": fund.id,
            "anomaly_type": AnomalyType.DEVIATION.value,
            "severity": severity,
            "description": f"经费「{fund.name or fund.id}」支出偏差率为 {deviation:.1f}%，"
            f"超过阈值 {DEVIATION_THRESHOLD}%",
        }
    ]


def _check_idle(fund: Fund) -> List[dict]:
    """资金闲置检测：已拨付但超过 IDLE_DAYS 天未使用"""
    allocated = float(fund.allocated_amount or 0)
    used = float(fund.used_amount or 0)
    if allocated <= 0 or used > 0:
        return []

    alloc_date = fund.allocation_date
    if not alloc_date:
        return []

    if isinstance(alloc_date, str):
        try:
            alloc_date = datetime.fromisoformat(alloc_date)
        except (ValueError, TypeError):
            return []

    # allocation_date 为 UtcDateTime 列：ORM 读回是 aware UTC，字符串兜底分支
    # 可能是 naive（按约定视为 UTC）。统一经 as_utc 归一后再与 utcnow() 相减——
    # 此前用本地 naive 的 datetime.now() 与其相减，aware/naive 混算必抛 TypeError，
    # 且异常被 backup_scheduler 的逐项目 try/except 吞掉，导致资金闲置检测静默失效。
    days_since = (utcnow() - as_utc(alloc_date)).days
    if days_since < IDLE_DAYS:
        return []

    severity = AnomalySeverity.DANGER.value if days_since > 60 else AnomalySeverity.WARNING.value
    return [
        {
            "fund_id": fund.id,
            "anomaly_type": AnomalyType.IDLE.value,
            "severity": severity,
            "description": f"经费「{fund.name or fund.id}」已拨付 {allocated:.2f} 万元，" f"但 {days_since} 天未使用",
        }
    ]


def _check_duplicate_payments(db: Session, project_id: int) -> List[dict]:
    """重复支付检测：同一凭证号 或 相近金额+日期"""
    results: List[dict] = []

    # 检查凭证号重复
    dup_vouchers = (
        db.query(FundTransaction.receipt_number, sa_func.count(FundTransaction.id))
        .filter(
            FundTransaction.project_id == project_id,
            FundTransaction.receipt_number.isnot(None),
            FundTransaction.receipt_number != "",
        )
        .group_by(FundTransaction.receipt_number)
        .having(sa_func.count(FundTransaction.id) > 1)
        .all()
    )
    for voucher_no, count in dup_vouchers:
        results.append(
            {
                "fund_id": None,
                "anomaly_type": AnomalyType.DUPLICATE.value,
                "severity": AnomalySeverity.WARNING.value,
                "description": f"凭证号「{voucher_no}」在项目中出现 {count} 次，疑似重复支付",
            }
        )

    return results


def _check_missing_vouchers(db: Session, project_id: int, funds: list) -> List[dict]:
    """缺失凭证检测：已使用金额 > 0 但无对应支出明细"""
    results: List[dict] = []

    for fund in funds:
        used = float(fund.used_amount or 0)
        if used <= 0:
            continue

        tx_count = db.query(sa_func.count(FundTransaction.id)).filter(FundTransaction.fund_id == fund.id).scalar() or 0
        if tx_count == 0:
            results.append(
                {
                    "fund_id": fund.id,
                    "anomaly_type": AnomalyType.MISSING_VOUCHER.value,
                    "severity": AnomalySeverity.WARNING.value,
                    "description": f"经费「{fund.name or fund.id}」已使用 {used:.2f} 万元，" "但无任何支出明细记录",
                }
            )

    return results


def _check_large_cash(db: Session, project_id: int) -> List[dict]:
    """大额提现检测：单笔支出超过阈值"""
    results: List[dict] = []

    large_txs = (
        db.query(FundTransaction)
        .filter(
            FundTransaction.project_id == project_id,
            FundTransaction.amount >= LARGE_CASH_THRESHOLD,
        )
        .all()
    )
    for tx in large_txs:
        results.append(
            {
                "fund_id": tx.fund_id,
                "anomaly_type": "large_cash",
                "severity": AnomalySeverity.WARNING.value,
                "description": f"单笔支出 {float(tx.amount):.2f} 万元超过大额阈值 "
                f"{LARGE_CASH_THRESHOLD} 万元，用途：{tx.purpose or '未说明'}",
            }
        )

    return results


def _check_contract_split(db: Session, project_id: int) -> List[dict]:
    """合同拆分检测：同一乙方在短期内多笔小额合同"""
    from app.models.fund_lifecycle import FundContract

    results: List[dict] = []

    # 按乙方分组统计
    contracts = db.query(FundContract).filter(FundContract.project_id == project_id).all()

    party_b_map = {}
    for c in contracts:
        if c.party_b:
            party_b_map.setdefault(c.party_b, []).append(c)

    for party_b, contract_list in party_b_map.items():
        if len(contract_list) >= CONTRACT_SPLIT_COUNT:
            # 检查时间跨度
            dates = [c.sign_date for c in contract_list if c.sign_date]
            if dates and (max(dates) - min(dates)).days <= CONTRACT_SPLIT_DAYS:
                total = sum(float(c.contract_amount or 0) for c in contract_list)
                results.append(
                    {
                        "fund_id": None,
                        "anomaly_type": "contract_split",
                        "severity": AnomalySeverity.WARNING.value,
                        "description": f"供应商「{party_b}」在 {CONTRACT_SPLIT_DAYS} 天内"
                        f"签订 {len(contract_list)} 笔合同，"
                        f"总金额 {total:.2f} 万元，疑似拆分合同",
                    }
                )

    return results


def _check_single_source(db: Session, project_id: int) -> List[dict]:
    """单一来源采购检测：项目所有合同均指向同一供应商"""
    from app.models.fund_lifecycle import FundContract

    results: List[dict] = []

    contracts = db.query(FundContract).filter(FundContract.project_id == project_id).all()

    if len(contracts) >= 2:
        party_bs = set(c.party_b for c in contracts if c.party_b)
        if len(party_bs) == 1:
            the_party = party_bs.pop()
            total = sum(float(c.contract_amount or 0) for c in contracts)
            results.append(
                {
                    "fund_id": None,
                    "anomaly_type": "single_source",
                    "severity": AnomalySeverity.WARNING.value,
                    "description": f"项目所有 {len(contracts)} 笔合同均指向同一供应商"
                    f"「{the_party}」，总金额 {total:.2f} 万元，疑似单一来源采购",
                }
            )

    return results


# 向后兼容的类别名
class FundAnomalyDetector:
    """向后兼容包装器 - 代理到 detect_anomalies 函数"""

    def __init__(self, db: Session = None):
        self.db = db

    def detect_anomalies(self, project_id: int) -> List[dict]:
        if self.db:
            return detect_anomalies(self.db, project_id)
        return []

    @staticmethod
    def create(db: Session = None) -> "FundAnomalyDetector":
        return FundAnomalyDetector(db)
