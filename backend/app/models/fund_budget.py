"""经费预算与使用明细模型"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.sql import func

from .base import Base


class FundBudget(Base):
    """年度经费预算"""

    __tablename__ = "fund_budgets"

    __table_args__ = (
        Index("ix_fb_year", "year"),
        Index("ix_fb_category", "category"),
        Index("ix_fb_year_category", "year", "category"),
        Index("ix_fb_village_id", "village_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, comment="年度")
    category = Column(
        String(100),
        nullable=False,
        comment="预算科目: infrastructure/education/industry/medical/party_building/consumption/employment/other",
    )
    budget_amount = Column(Numeric(15, 4), default=0, comment="预算金额(万元)")
    executed_amount = Column(Numeric(15, 4), default=0, comment="已执行金额(万元)")
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=True,
        comment="帮扶村ID(可为空=全局预算)",
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属单位ID",
    )
    description = Column(Text, nullable=True, comment="预算说明")
    remarks = Column(Text, nullable=True, comment="备注")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建人ID",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def remaining_amount(self):
        return float(self.budget_amount or 0) - float(self.executed_amount or 0)

    @property
    def execution_rate(self):
        budget = float(self.budget_amount or 0)
        if budget <= 0:
            return 0.0
        return round(float(self.executed_amount or 0) / budget * 100, 2)

    def __repr__(self):
        return f"<FundBudget(id={self.id}, year={self.year}, category={self.category})>"


class FundTransaction(Base):
    """经费使用明细台账"""

    __tablename__ = "fund_transactions"

    __table_args__ = (
        Index("ix_ft_fund_id", "fund_id"),
        Index("ix_ft_project_id", "project_id"),
        Index("ix_ft_village_id", "village_id"),
        Index("ix_ft_transaction_date", "transaction_date"),
        Index("ix_ft_category", "category"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费记录ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联项目ID",
    )
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联帮扶村ID",
    )
    budget_id = Column(
        Integer,
        ForeignKey("fund_budgets.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联预算ID",
    )

    amount = Column(Numeric(15, 4), nullable=False, comment="金额(万元)")
    category = Column(String(100), nullable=True, comment="支出科目")
    purpose = Column(Text, nullable=False, comment="用途说明")
    transaction_date = Column(Date, nullable=False, comment="支出日期")
    receipt_number = Column(String(100), nullable=True, comment="凭证编号")
    receipt_attachment = Column(String(500), nullable=True, comment="凭证附件路径")
    handler = Column(String(50), nullable=True, comment="经办人")
    reimbursement_person = Column(String(50), nullable=True, comment="报销人")
    approved_by = Column(String(50), nullable=True, comment="审批人")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected")
    remarks = Column(Text, nullable=True, comment="备注")

    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="录入人ID",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        purpose_preview = self.purpose[:20] if self.purpose else ""
        return f"<FundTransaction(id={self.id}, amount={self.amount}, " f"purpose={purpose_preview})>"


# ==================== 预算预警逻辑 ====================

BUDGET_WARNING_THRESHOLD = 0.80  # 80% 提醒（黄）
BUDGET_CRITICAL_THRESHOLD = 0.90  # 90% 警告（橙，ADR-0009）
BUDGET_DANGER_THRESHOLD = 1.00  # 100% 禁止线（红）


def check_budget_alerts(budgets: list) -> list:
    """
    检查预算预警。

    Args:
        budgets: FundBudget 对象列表

    Returns:
        预警列表 [{"budget_id": ..., "level": "warning"/"danger", "message": "...", ...}]
    """
    alerts = []
    for b in budgets:
        budget_val = float(b.budget_amount or 0)
        if budget_val <= 0:
            continue
        executed_val = float(b.executed_amount or 0)
        rate = executed_val / budget_val

        if rate >= BUDGET_DANGER_THRESHOLD:
            alerts.append(
                {
                    "budget_id": b.id,
                    "year": b.year,
                    "category": b.category,
                    "level": "danger",
                    "execution_rate": round(rate * 100, 1),
                    "message": f"{b.year}年「{b.category}」预算使用率已达 {round(rate * 100, 1)}%，已禁止继续核销（ADR-0009）",
                }
            )
        elif rate >= BUDGET_CRITICAL_THRESHOLD:
            alerts.append(
                {
                    "budget_id": b.id,
                    "year": b.year,
                    "category": b.category,
                    "level": "critical",
                    "execution_rate": round(rate * 100, 1),
                    "message": f"{b.year}年「{b.category}」预算使用率已达 {round(rate * 100, 1)}%，接近禁止线，请严控支出",
                }
            )
        elif rate >= BUDGET_WARNING_THRESHOLD:
            alerts.append(
                {
                    "budget_id": b.id,
                    "year": b.year,
                    "category": b.category,
                    "level": "info",
                    "execution_rate": round(rate * 100, 1),
                    "message": f"{b.year}年「{b.category}」预算使用率已达 {round(rate * 100, 1)}%",
                }
            )
    return alerts
