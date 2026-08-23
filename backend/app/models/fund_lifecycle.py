"""经费全生命周期管理模型"""

import enum

from sqlalchemy import (
    Boolean,
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

# ==================== 枚举 ====================


class LifecyclePhase(int, enum.Enum):
    """经费生命周期七阶段"""

    INITIATION = 1  # 论证立项
    REVIEW = 2  # 汇总审核
    ALLOCATION = 3  # 计划下达与资金拨付
    TRANSFER = 4  # 对接与资金划转
    IMPLEMENTATION = 5  # 组织实施与过程监管
    INSPECTION = 6  # 核查督查与效益评估
    SETTLEMENT = 7  # 常态监管与项目决算


PHASE_LABELS = {
    1: "论证立项",
    2: "汇总审核",
    3: "计划下达与资金拨付",
    4: "对接与资金划转",
    5: "组织实施与过程监管",
    6: "核查督查与效益评估",
    7: "常态监管与项目决算",
}


class PhaseStatus(str, enum.Enum):
    """阶段状态"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class VoucherDirection(str, enum.Enum):
    """划转方向"""

    MILITARY_TO_LOCAL = "military_to_local"
    LOCAL_TO_MILITARY = "local_to_military"


class VoucherStatus(str, enum.Enum):
    """凭证状态"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ContractStatus(str, enum.Enum):
    """合同状态"""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class AnomalyType(str, enum.Enum):
    """异常类型"""

    OVERSPEND = "overspend"
    DEVIATION = "deviation"
    IDLE = "idle"
    DUPLICATE = "duplicate"
    MISSING_VOUCHER = "missing_voucher"


class AnomalySeverity(str, enum.Enum):
    """异常严重程度"""

    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


class SettlementStatus(str, enum.Enum):
    """决算状态"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"


class PerformanceLevel(str, enum.Enum):
    """绩效等级"""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


# ==================== 模型 ====================


class ProjectFundPhase(Base):
    """项目-经费阶段跟踪"""

    __tablename__ = "project_fund_phases"

    __table_args__ = (
        Index("ix_pfp_project_id", "project_id"),
        Index("ix_pfp_phase", "phase"),
        Index("ix_pfp_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    phase = Column(Integer, nullable=False, comment="阶段编号(1-7)")
    status = Column(String(20), default=PhaseStatus.NOT_STARTED.value, comment="阶段状态")
    entered_at = Column(DateTime(timezone=True), nullable=True, comment="进入时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    operator = Column(String(50), nullable=True, comment="操作人")
    remarks = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ProjectFundPhase(project={self.project_id}, phase={self.phase}, status={self.status})>"


class BudgetBaseline(Base):
    """预算基线快照（阶段2锁定）"""

    __tablename__ = "budget_baselines"

    __table_args__ = (
        Index("ix_bb_project_id", "project_id"),
        Index("ix_bb_fund_id", "fund_id"),
        Index("ix_bb_year", "snapshot_year"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    snapshot_year = Column(Integer, nullable=False, comment="快照年度")
    category = Column(String(100), nullable=True, comment="预算科目")
    baseline_amount = Column(Numeric(15, 4), default=0, comment="基线金额(万元)")
    locked_at = Column(DateTime(timezone=True), nullable=True, comment="锁定时间")
    locked_by = Column(String(50), nullable=True, comment="锁定人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<BudgetBaseline(project={self.project_id}, year={self.snapshot_year}, amount={self.baseline_amount})>"


class FundTransferVoucher(Base):
    """资金划转凭证"""

    __tablename__ = "fund_transfer_vouchers"

    __table_args__ = (
        Index("ix_ftv_fund_id", "fund_id"),
        Index("ix_ftv_project_id", "project_id"),
        Index("ix_ftv_status", "status"),
        Index("ix_ftv_voucher_no", "voucher_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联项目ID",
    )
    voucher_no = Column(String(100), unique=True, nullable=False, comment="凭证编号")
    direction = Column(String(30), nullable=False, comment="划转方向")
    amount = Column(Numeric(15, 4), nullable=False, comment="划转金额(万元)")
    payer_account = Column(String(200), nullable=True, comment="付款账户")
    payee_account = Column(String(200), nullable=True, comment="收款账户")
    transfer_date = Column(Date, nullable=True, comment="划转日期")
    status = Column(String(20), default=VoucherStatus.DRAFT.value, comment="凭证状态")
    confirmed_by = Column(String(50), nullable=True, comment="确认人")
    confirmed_at = Column(DateTime(timezone=True), nullable=True, comment="确认时间")
    attachment_id = Column(Integer, nullable=True, comment="附件ID")
    remarks = Column(Text, nullable=True, comment="备注")
    created_by = Column(String(50), nullable=True, comment="创建人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 协同扩展字段
    military_project_code = Column(String(100), nullable=True, comment="专项项目编号")
    local_project_code = Column(String(100), nullable=True, comment="地方项目编号")
    sync_status = Column(String(20), default="pending", comment="同步状态: pending/synced/failed")

    def __repr__(self):
        return f"<FundTransferVoucher(id={self.id}, voucher_no={self.voucher_no}, amount={self.amount})>"


class FundContract(Base):
    """合同-支付联动"""

    __tablename__ = "fund_contracts"

    __table_args__ = (
        Index("ix_fc_fund_id", "fund_id"),
        Index("ix_fc_project_id", "project_id"),
        Index("ix_fc_status", "status"),
        Index("ix_fc_contract_no", "contract_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联项目ID",
    )
    contract_no = Column(String(100), unique=True, nullable=False, comment="合同编号")
    contract_name = Column(String(300), nullable=False, comment="合同名称")
    party_a = Column(String(200), nullable=True, comment="甲方")
    party_b = Column(String(200), nullable=True, comment="乙方")
    contract_amount = Column(Numeric(15, 4), default=0, comment="合同金额(万元)")
    paid_amount = Column(Numeric(15, 4), default=0, comment="已付金额(万元)")
    payment_progress = Column(Numeric(5, 2), default=0, comment="付款进度(%)")
    sign_date = Column(Date, nullable=True, comment="签订日期")
    deadline = Column(Date, nullable=True, comment="截止日期")
    status = Column(String(20), default=ContractStatus.DRAFT.value, comment="合同状态")
    remarks = Column(Text, nullable=True, comment="备注")
    created_by = Column(String(50), nullable=True, comment="创建人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FundContract(id={self.id}, contract_no={self.contract_no}, status={self.status})>"


class FundContractPayment(Base):
    """合同付款明细"""

    __tablename__ = "fund_contract_payments"

    __table_args__ = (
        Index("ix_fcp_contract_id", "contract_id"),
        Index("ix_fcp_payment_date", "payment_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(
        Integer,
        ForeignKey("fund_contracts.id", ondelete="SET NULL"),
        nullable=False,
        comment="合同ID",
    )
    payment_no = Column(String(100), nullable=True, comment="付款编号")
    amount = Column(Numeric(15, 4), nullable=False, comment="付款金额(万元)")
    payment_date = Column(Date, nullable=False, comment="付款日期")
    purpose = Column(Text, nullable=True, comment="用途说明")
    voucher_no = Column(String(100), nullable=True, comment="凭证编号")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected")
    operator = Column(String(50), nullable=True, comment="经办人")
    remarks = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # WBS 关联字段
    wbs_code = Column(String(100), nullable=True, comment="WBS工作分解结构编码")
    task_id = Column(
        Integer,
        ForeignKey("project_tasks.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联项目任务ID",
    )

    def __repr__(self):
        return f"<FundContractPayment(id={self.id}, amount={self.amount})>"


class FundAnomaly(Base):
    """经费异常检测记录"""

    __tablename__ = "fund_anomalies"

    __table_args__ = (
        Index("ix_fa_fund_id", "fund_id"),
        Index("ix_fa_project_id", "project_id"),
        Index("ix_fa_anomaly_type", "anomaly_type"),
        Index("ix_fa_severity", "severity"),
        Index("ix_fa_resolved", "resolved"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联项目ID",
    )
    anomaly_type = Column(String(30), nullable=False, comment="异常类型")
    severity = Column(String(20), default=AnomalySeverity.WARNING.value, comment="严重程度")
    description = Column(Text, nullable=False, comment="异常描述")
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="检测时间")
    resolved = Column(Boolean, default=False, comment="是否已解决")
    resolved_by = Column(String(50), nullable=True, comment="解决人")
    resolved_at = Column(DateTime(timezone=True), nullable=True, comment="解决时间")
    resolution = Column(Text, nullable=True, comment="解决说明")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<FundAnomaly(id={self.id}, type={self.anomaly_type}, severity={self.severity})>"


class FundSettlement(Base):
    """项目决算"""

    __tablename__ = "fund_settlements"

    __table_args__ = (
        Index("ix_fs_project_id", "project_id"),
        Index("ix_fs_fund_id", "fund_id"),
        Index("ix_fs_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    settlement_no = Column(String(100), unique=True, nullable=True, comment="决算编号")
    total_budget = Column(Numeric(15, 4), default=0, comment="总预算(万元)")
    total_spent = Column(Numeric(15, 4), default=0, comment="总支出(万元)")
    total_remaining = Column(Numeric(15, 4), default=0, comment="总结余(万元)")
    settlement_date = Column(Date, nullable=True, comment="决算日期")
    status = Column(String(20), default=SettlementStatus.DRAFT.value, comment="决算状态")
    auditor = Column(String(50), nullable=True, comment="审核人")
    audit_opinion = Column(Text, nullable=True, comment="审核意见")
    performance_score = Column(Integer, nullable=True, comment="绩效评分(0-100)")
    performance_level = Column(String(5), nullable=True, comment="绩效等级(A/B/C/D)")
    remarks = Column(Text, nullable=True, comment="备注")
    created_by = Column(String(50), nullable=True, comment="创建人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 资产联动校验字段
    asset_verified = Column(Boolean, default=False, comment="资产是否已校验")
    asset_value = Column(Numeric(15, 4), nullable=True, comment="转固资产价值(万元)")

    def __repr__(self):
        return f"<FundSettlement(id={self.id}, project={self.project_id}, status={self.status})>"


class BudgetVersion(Base):
    """预算版本快照（痕迹追踪）"""

    __tablename__ = "budget_versions"

    __table_args__ = (
        Index("ix_bv_fund_id", "fund_id"),
        Index("ix_bv_project_id", "project_id"),
        Index("ix_bv_version", "version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联经费ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID",
    )
    version = Column(Integer, nullable=False, comment="版本号")
    planned_amount = Column(Numeric(15, 4), default=0, comment="计划金额(万元)")
    approved_amount = Column(Numeric(15, 4), nullable=True, comment="批准金额(万元)")
    change_reason = Column(Text, nullable=True, comment="变更原因")
    change_type = Column(String(30), default="initial", comment="变更类型: initial/adjust/approve")
    status = Column(String(20), default="draft", comment="状态: draft/submitted/approved/rejected")
    operator = Column(String(50), nullable=True, comment="操作人")
    approved_by = Column(String(50), nullable=True, comment="审批人")
    approved_at = Column(DateTime(timezone=True), nullable=True, comment="审批时间")
    snapshot_data = Column(Text, nullable=True, comment="完整预算快照(JSON)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<BudgetVersion(fund={self.fund_id}, version={self.version}, status={self.status})>"
