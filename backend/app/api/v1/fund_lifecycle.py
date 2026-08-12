"""经费全生命周期管理 API

挂载到 /api/v1/fund-lifecycle 前缀，覆盖七阶段全部端点：
1. 论证立项  2. 汇总审核  3. 计划下达与资金拨付
4. 对接与资金划转  5. 组织实施与过程监管
6. 核查督查与效益评估  7. 常态监管与项目决算
"""

from datetime import date, datetime
import json as _json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.response import ok_list, success_response
from ...core.security import get_current_user
from ...core.transaction import safe_commit
from ...models.fund import Fund
from ...models.fund_budget import FundTransaction
from ...models.fund_lifecycle import (
    PHASE_LABELS,
    BudgetBaseline,
    ContractStatus,
    FundAnomaly,
    FundContract,
    FundContractPayment,
    FundSettlement,
    FundTransferVoucher,
    PhaseStatus,
    ProjectFundPhase,
    SettlementStatus,
    VoucherStatus,
)
from ...models.project import Project
from ...core.permission_utils import is_superuser
from ...core.data_permission import apply_data_scope, check_record_access
from ...services.work_log_service import write_work_log
from .deps import ADMIN_ROLES, require_funds_operator_role as _require_manager  # noqa: F401

router = APIRouter(prefix="/fund-lifecycle", tags=["经费生命周期"])


def _get_username(current_user) -> str:
    return getattr(current_user, "full_name", None) or getattr(current_user, "username", "")


def _get_project_or_403(project_id: int, current_user, db: Session) -> Project:
    """加载项目并做 404/403 数据权限校验（区分"不存在"与"跨组织"）。

    所有带 project_id 的详情端点必须先过此校验，防止跨组织读取经费数据。
    """
    if not project_id or project_id <= 0:
        # 前端从菜单/快捷入口进入生命周期页时可能缺 projectId（回退为 0），
        # 返回 400 而非 404，避免误导用户以为项目不存在。
        raise HTTPException(status_code=400, detail="缺少有效的项目ID，请从经费列表中选择具体项目进入")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not check_record_access(project, current_user):
        raise HTTPException(status_code=403, detail="无权访问该组织数据")
    return project


# =====================================================================
#  3.1 阶段管理
# =====================================================================


@router.get("/phases/{project_id}")
async def get_phases(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取项目各阶段状态"""
    _get_project_or_403(project_id, current_user, db)

    phases = (
        db.query(ProjectFundPhase)
        .filter(ProjectFundPhase.project_id == project_id)
        .order_by(ProjectFundPhase.phase)
        .all()
    )

    # 如果尚未初始化阶段记录，自动创建 7 条
    if not phases:
        phases = _init_phases(db, project_id)

    result = []
    for p in phases:
        result.append(
            {
                "id": p.id,
                "phase": p.phase,
                "phase_label": PHASE_LABELS.get(p.phase, f"阶段{p.phase}"),
                "status": p.status,
                "entered_at": p.entered_at.isoformat() if p.entered_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                "operator": p.operator,
                "remarks": p.remarks,
            }
        )

    # 当前阶段
    current_phase = 1
    for p in phases:
        if p.status == PhaseStatus.IN_PROGRESS.value:
            current_phase = p.phase
            break
        elif p.status == PhaseStatus.COMPLETED.value:
            current_phase = p.phase + 1

    return success_response(
        data={
            "project_id": project_id,
            "current_phase": min(current_phase, 7),
            "phases": result,
        }
    )


class PhaseAdvanceRequest(BaseModel):
    remarks: Optional[str] = None


def _find_current_phase(phases: list) -> Optional[ProjectFundPhase]:
    for p in phases:
        if p.status == PhaseStatus.IN_PROGRESS.value:
            return p
    for p in phases:
        if p.status == PhaseStatus.NOT_STARTED.value:
            return p
    return None


def _check_phase_danger_anomalies(db: Session, project_id: int) -> None:
    danger_count = (
        db.query(sa_func.count(FundAnomaly.id))
        .filter(
            FundAnomaly.project_id == project_id,
            FundAnomaly.resolved == False,  # noqa: E712
            FundAnomaly.severity == "danger",
        )
        .scalar()
        or 0
    )
    if danger_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"存在 {danger_count} 个未解决的严重异常，请先处理后再推进阶段",
        )


def _start_current_phase(
    phase: ProjectFundPhase, now: datetime, username: str, remarks: Optional[str]
) -> None:
    phase.status = PhaseStatus.IN_PROGRESS.value
    phase.entered_at = now
    phase.operator = username
    if remarks:
        phase.remarks = remarks


def _complete_and_advance_phase(
    phases: list, current: ProjectFundPhase, now: datetime, username: str, remarks: Optional[str]
) -> None:
    current.status = PhaseStatus.COMPLETED.value
    current.completed_at = now

    next_phase = None
    for p in phases:
        if p.phase == current.phase + 1:
            next_phase = p
            break

    if next_phase:
        next_phase.status = PhaseStatus.IN_PROGRESS.value
        next_phase.entered_at = now
        next_phase.operator = username
        if remarks:
            next_phase.remarks = remarks


@router.post("/phases/{project_id}/advance")
async def advance_phase(
    project_id: int,
    data: PhaseAdvanceRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """推进到下一阶段（含准入校验）"""
    _require_manager(current_user)

    phases = (
        db.query(ProjectFundPhase)
        .filter(ProjectFundPhase.project_id == project_id)
        .order_by(ProjectFundPhase.phase)
        .all()
    )
    if not phases:
        phases = _init_phases(db, project_id)

    current = _find_current_phase(phases)
    if current is None:
        raise HTTPException(status_code=400, detail="所有阶段已完成，无法继续推进")

    _check_phase_danger_anomalies(db, project_id)

    now = datetime.now()
    username = _get_username(current_user)
    remarks = data.remarks if data else None

    if current.status == PhaseStatus.NOT_STARTED.value:
        _start_current_phase(current, now, username, remarks)
    else:
        _complete_and_advance_phase(phases, current, now, username, remarks)

    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    new_phase = current.phase if current.status == PhaseStatus.IN_PROGRESS.value else current.phase + 1
    for f in funds:
        f.lifecycle_phase = min(new_phase, 7)

    safe_commit(db)
    return success_response(message=f"已推进到阶段 {min(new_phase, 7)}")


@router.post("/phases/{project_id}/rollback")
async def rollback_phase(
    project_id: int,
    data: PhaseAdvanceRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """退回上一阶段"""
    _require_manager(current_user)

    phases = (
        db.query(ProjectFundPhase)
        .filter(ProjectFundPhase.project_id == project_id)
        .order_by(ProjectFundPhase.phase)
        .all()
    )
    if not phases:
        raise HTTPException(status_code=400, detail="阶段记录不存在")

    current = None
    for p in phases:
        if p.status == PhaseStatus.IN_PROGRESS.value:
            current = p
            break

    if not current or current.phase <= 1:
        raise HTTPException(status_code=400, detail="已在第一阶段，无法退回")

    username = _get_username(current_user)

    # 当前阶段重置
    current.status = PhaseStatus.NOT_STARTED.value
    current.entered_at = None

    # 上一阶段重新设为进行中
    prev = None
    for p in phases:
        if p.phase == current.phase - 1:
            prev = p
            break

    if prev:
        prev.status = PhaseStatus.IN_PROGRESS.value
        prev.completed_at = None
        prev.operator = username
        prev.remarks = (data.remarks if data else None) or f"从阶段{current.phase}退回"

    # 同步 Fund
    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    for f in funds:
        f.lifecycle_phase = current.phase - 1

    safe_commit(db)
    return success_response(message=f"已退回到阶段 {current.phase - 1}")


# =====================================================================
#  3.2 阶段1 - 论证立项
# =====================================================================


@router.post("/initiate/{project_id}")
async def initiate_project_fund(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """初始化预算并生成项目报告模板"""
    _require_manager(current_user)

    project = _get_project_or_403(project_id, current_user, db)

    # 确保阶段记录存在
    phases = db.query(ProjectFundPhase).filter(ProjectFundPhase.project_id == project_id).all()
    if not phases:
        phases = _init_phases(db, project_id)

    # 阶段1 设为进行中
    phase1 = next((p for p in phases if p.phase == 1), None)
    if phase1 and phase1.status == PhaseStatus.NOT_STARTED.value:
        phase1.status = PhaseStatus.IN_PROGRESS.value
        phase1.entered_at = datetime.now()
        phase1.operator = _get_username(current_user)

    safe_commit(db)
    return success_response(
        message="论证立项已启动",
        data={
            "project_id": project_id,
            "project_name": project.name,
            "budget": float(project.budget or 0),
            "phase": 1,
        },
    )


@router.get("/report-template/{project_id}")
async def get_report_template(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取论证报告数据（经济指标 + 预算概算）"""
    project = _get_project_or_403(project_id, current_user, db)

    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    total_planned = sum(float(f.planned_amount or 0) for f in funds)
    total_approved = sum(float(f.approved_amount or 0) for f in funds)

    return success_response(
        data={
            "project": {
                "id": project.id,
                "name": project.name,
                "type": project.type,
                "description": project.description,
                "objectives": project.objectives,
                "budget": float(project.budget or 0),
                "start_date": (project.start_date.isoformat() if project.start_date else None),
                "end_date": project.end_date.isoformat() if project.end_date else None,
                "leader": project.leader,
                "responsible_unit": project.responsible_unit,
            },
            "fund_summary": {
                "total_planned": total_planned,
                "total_approved": total_approved,
                "fund_count": len(funds),
                "funds": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "planned_amount": float(f.planned_amount or 0),
                        "type": f.type,
                        "fund_source": f.fund_source,
                    }
                    for f in funds
                ],
            },
        }
    )


# =====================================================================
#  3.3 阶段2 - 汇总审核
# =====================================================================


@router.post("/budget-lock/{project_id}")
async def lock_budget(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """锁定预算基线"""
    _require_manager(current_user)

    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    if not funds:
        raise HTTPException(status_code=404, detail="该项目无关联经费")

    now = datetime.now()
    username = _get_username(current_user)
    year = now.year
    created_count = 0

    for fund in funds:
        if fund.budget_locked:
            continue

        # 创建基线快照
        baseline = BudgetBaseline(
            fund_id=fund.id,
            project_id=project_id,
            snapshot_year=year,
            category=fund.type or fund.fund_type,
            baseline_amount=fund.approved_amount or fund.planned_amount or fund.amount,
            locked_at=now,
            locked_by=username,
        )
        db.add(baseline)
        fund.budget_locked = True
        created_count += 1

    safe_commit(db)
    return success_response(
        message=f"已锁定 {created_count} 笔经费预算基线",
        data={"locked_count": created_count},
    )


@router.get("/compliance-check/{project_id}")
async def compliance_check(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """合规性校验（10%预警线 / 15%否决线 + 费用标准匹配）"""
    _get_project_or_403(project_id, current_user, db)
    from ...services.compliance_engine import run_compliance_check

    result = run_compliance_check(db, project_id)
    return success_response(data=result)


@router.get("/budget-aggregation")
async def budget_aggregation(
    group_by: str = Query("year", description="year/type/village/unit/organization"),
    year: Optional[int] = None,
    organization_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """多维度预算汇总（按年度/类型/村/单位/组织），含可视化预计算数据"""
    query = db.query(Fund)
    query = apply_data_scope(query, Fund, current_user)
    if year:
        query = query.filter(Fund.year == year)

    # 按组织筛选（通过 project 关联）
    if organization_id:
        from ...models.project import Project as _Project

        project_ids = [
            pid for (pid,) in db.query(_Project.id).filter(_Project.organization_id == organization_id).all()
        ]
        if project_ids:
            query = query.filter(Fund.project_id.in_(project_ids))
        else:
            return success_response(
                data=[],
                group_by=group_by,
                pie_chart_data=[],
                bar_chart_data=[],
            )

    if group_by == "type":
        group_col = sa_func.coalesce(Fund.type, "other")
    elif group_by == "village":
        group_col = sa_func.coalesce(Fund.village_id, 0)
    elif group_by == "unit":
        group_col = sa_func.coalesce(Fund.fund_source, "other")
    elif group_by == "organization":
        # 按项目所属组织聚合
        from ...models.project import Project as _Project

        group_col = sa_func.coalesce(_Project.organization_id, 0)
        query = query.join(_Project, Fund.project_id == _Project.id)
    else:
        group_col = Fund.year

    rows = (
        query.with_entities(
            group_col.label("group_key"),
            sa_func.count(Fund.id).label("count"),
            sa_func.coalesce(sa_func.sum(Fund.planned_amount), 0).label("total_planned"),
            sa_func.coalesce(sa_func.sum(Fund.approved_amount), 0).label("total_approved"),
            sa_func.coalesce(sa_func.sum(Fund.allocated_amount), 0).label("total_allocated"),
            sa_func.coalesce(sa_func.sum(Fund.used_amount), 0).label("total_used"),
        )
        .group_by(group_col)
        .all()
    )

    items = []
    grand_total_planned = 0
    grand_total_used = 0
    for row in rows:
        tp = float(row.total_planned or 0)
        tu = float(row.total_used or 0)
        grand_total_planned += tp
        grand_total_used += tu
        execution_rate = round(tu / tp * 100, 2) if tp > 0 else 0
        items.append(
            {
                "group_key": (str(row.group_key) if row.group_key is not None else "未知"),
                "count": row.count,
                "total_planned": tp,
                "total_approved": float(row.total_approved or 0),
                "total_allocated": float(row.total_allocated or 0),
                "total_used": tu,
                "execution_rate": execution_rate,
            }
        )

    # 饼图数据：各分组占计划总额比例
    pie_chart_data = [
        {
            "name": it["group_key"],
            "value": it["total_planned"],
            "percentage": (round(it["total_planned"] / grand_total_planned * 100, 1) if grand_total_planned > 0 else 0),
        }
        for it in items
    ]

    # 柱状图数据：各分组计划 vs 已用对比
    bar_chart_data = [
        {
            "name": it["group_key"],
            "planned": it["total_planned"],
            "used": it["total_used"],
            "execution_rate": it["execution_rate"],
        }
        for it in items
    ]

    return success_response(
        data=items,
        group_by=group_by,
        pie_chart_data=pie_chart_data,
        bar_chart_data=bar_chart_data,
    )


# =====================================================================
#  3.4 阶段3 - 计划下达与资金拨付
# =====================================================================


@router.post("/quota-lock/{fund_id}")
async def quota_lock(fund_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """额度锁定"""
    _require_manager(current_user)

    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="经费记录不存在")

    if not fund.budget_locked:
        raise HTTPException(status_code=400, detail="请先锁定预算基线（阶段2）")

    # 检查基线约束
    baseline = (
        db.query(BudgetBaseline).filter(BudgetBaseline.fund_id == fund_id).order_by(BudgetBaseline.id.desc()).first()
    )
    allocated = float(fund.allocated_amount or fund.approved_amount or fund.amount or 0)
    if baseline:
        baseline_val = float(baseline.baseline_amount or 0)
        if allocated > baseline_val:
            raise HTTPException(
                status_code=400,
                detail=f"拨付额度 {allocated:.2f} 超过基线 {baseline_val:.2f}，不允许",
            )

    safe_commit(db)
    return success_response(
        message="额度已锁定",
        data={"fund_id": fund_id, "allocated": allocated},
    )


@router.get("/allocation-plan/{project_id}")
async def allocation_plan(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拨付计划分解"""
    _get_project_or_403(project_id, current_user, db)
    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    # 预加载所有 baseline，避免 N+1 查询
    fund_ids = [f.id for f in funds]
    baselines = {}
    if fund_ids:
        # 子查询：每个 fund_id 的最新 baseline
        baseline_rows = (
            db.query(BudgetBaseline)
            .filter(BudgetBaseline.fund_id.in_(fund_ids))
            .order_by(BudgetBaseline.id.desc())
            .all()
        )
        # 每个 fund 只保留第一条（最新的）
        for b in baseline_rows:
            if b.fund_id not in baselines:
                baselines[b.fund_id] = b
    items = []
    for f in funds:
        baseline = baselines.get(f.id)
        items.append(
            {
                "fund_id": f.id,
                "fund_name": f.name,
                "planned_amount": float(f.planned_amount or 0),
                "approved_amount": float(f.approved_amount or 0),
                "allocated_amount": float(f.allocated_amount or 0),
                "baseline_amount": (float(baseline.baseline_amount or 0) if baseline else None),
                "budget_locked": f.budget_locked,
                "status": f.status,
            }
        )

    return success_response(data={"project_id": project_id, "items": items})


# =====================================================================
#  3.5 阶段4 - 对接与资金划转
# =====================================================================


class TransferVoucherCreate(BaseModel):
    fund_id: Optional[int] = None
    project_id: Optional[int] = None
    voucher_no: str
    direction: str = Field(..., description="military_to_local / local_to_military")
    amount: float = Field(..., gt=0)
    payer_account: Optional[str] = None
    payee_account: Optional[str] = None
    transfer_date: Optional[date] = None
    remarks: Optional[str] = None

    @field_validator("transfer_date", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v):
        """前端表单未选择日期时提交空字符串 → 视为 None，避免 Pydantic date 解析 422"""
        if isinstance(v, str) and not v.strip():
            return None
        return v


class TransferVoucherUpdate(BaseModel):
    direction: Optional[str] = None
    amount: Optional[float] = None
    payer_account: Optional[str] = None
    payee_account: Optional[str] = None
    transfer_date: Optional[date] = None
    status: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("transfer_date", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v):
        """前端表单未选择日期时提交空字符串 → 视为 None，避免 Pydantic date 解析 422"""
        if isinstance(v, str) and not v.strip():
            return None
        return v


@router.get("/transfer-vouchers")
async def list_transfer_vouchers(
    project_id: Optional[int] = None,
    fund_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """划转凭证列表"""
    query = db.query(FundTransferVoucher)
    query = apply_data_scope(query, FundTransferVoucher, current_user)
    if project_id:
        query = query.filter(FundTransferVoucher.project_id == project_id)
    if fund_id:
        query = query.filter(FundTransferVoucher.fund_id == fund_id)
    if status:
        query = query.filter(FundTransferVoucher.status == status)

    total = query.count()
    items = query.order_by(FundTransferVoucher.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return ok_list(items=[_voucher_to_dict(v) for v in items], total=total, page=page, page_size=page_size)


@router.post("/transfer-vouchers")
async def create_transfer_voucher(
    data: TransferVoucherCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建划转凭证（含预算余额校验）"""
    _require_manager(current_user)

    exists = db.query(FundTransferVoucher).filter(FundTransferVoucher.voucher_no == data.voucher_no).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"凭证编号 {data.voucher_no} 已存在")

    # 预算余额校验：划转金额 ≤ 预算余额
    if data.fund_id:
        fund = db.query(Fund).filter(Fund.id == data.fund_id).first()
        if fund:
            approved = float(fund.approved_amount or fund.planned_amount or fund.amount or 0)
            used = float(fund.used_amount or 0)
            # 已有确认状态凭证的划转金额
            existing_transfers = (
                db.query(sa_func.coalesce(sa_func.sum(FundTransferVoucher.amount), 0))
                .filter(
                    FundTransferVoucher.fund_id == data.fund_id,
                    FundTransferVoucher.status.in_(["submitted", "confirmed"]),
                )
                .scalar()
            ) or 0
            available = approved - used - float(existing_transfers)
            if data.amount > available:
                raise HTTPException(
                    status_code=400,
                    detail=f"划转金额 {data.amount:.2f} 超过可用预算余额 {available:.2f} 万元",
                )

    voucher = FundTransferVoucher(
        **data.model_dump(),
        created_by=_get_username(current_user),
    )
    db.add(voucher)
    safe_commit(db)
    db.refresh(voucher)
    write_work_log(
        db, "fund", "create_transfer_voucher", voucher.id,
        f"凭证 {voucher.voucher_no}",
        user_id=current_user.id, username=_get_username(current_user),
        detail=f"金额: {data.amount} 万元",
    )
    return success_response(message="创建成功", data=_voucher_to_dict(voucher))


@router.get("/transfer-vouchers/{voucher_id}")
async def get_transfer_voucher(
    voucher_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单条凭证详情"""
    v = db.query(FundTransferVoucher).filter(FundTransferVoucher.id == voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    _get_project_or_403(v.project_id, current_user, db)
    return success_response(data=_voucher_to_dict(v))


@router.put("/transfer-vouchers/{voucher_id}")
async def update_transfer_voucher(
    voucher_id: int,
    data: TransferVoucherUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新划转凭证"""
    _require_manager(current_user)

    v = db.query(FundTransferVoucher).filter(FundTransferVoucher.id == voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status == VoucherStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail="已确认凭证不可修改")

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(v, key, val)
    safe_commit(db)
    db.refresh(v)
    return success_response(message="更新成功", data=_voucher_to_dict(v))


@router.delete("/transfer-vouchers/{voucher_id}")
async def delete_transfer_voucher(
    voucher_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除凭证（仅 draft 状态）"""
    _require_manager(current_user)

    v = db.query(FundTransferVoucher).filter(FundTransferVoucher.id == voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != VoucherStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="仅草稿状态凭证可删除")

    db.delete(v)
    safe_commit(db)
    return success_response(message="删除成功")


@router.post("/transfer-vouchers/{voucher_id}/confirm")
async def confirm_transfer_voucher(
    voucher_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """凭证确认"""
    _require_manager(current_user)

    v = db.query(FundTransferVoucher).filter(FundTransferVoucher.id == voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status not in (VoucherStatus.DRAFT.value, VoucherStatus.SUBMITTED.value):
        raise HTTPException(status_code=400, detail=f"当前状态 {v.status} 不允许确认")

    v.status = VoucherStatus.CONFIRMED.value
    v.confirmed_by = _get_username(current_user)
    v.confirmed_at = datetime.now()
    safe_commit(db)
    write_work_log(
        db, "fund", "confirm_transfer_voucher", v.id,
        f"凭证 {v.voucher_no}",
        user_id=current_user.id, username=_get_username(current_user),
        detail="凭证已确认",
    )
    return success_response(message="凭证已确认")


@router.post("/transfer-vouchers/{voucher_id}/attachments")
async def upload_voucher_attachment(
    voucher_id: int,
    file: UploadFile = File(...),
    category: str = "bank_receipt",
    description: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """凭证附件上传（银行回单等电子化归档）

    使用统一的 save_upload_file 工具，支持真实文件上传。
    """
    _require_manager(current_user)

    v = db.query(FundTransferVoucher).filter(FundTransferVoucher.id == voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")

    from ...models.fund import FundAttachment
    from ...utils.upload_helper import save_upload_file

    # 使用统一上传工具
    file_info = await save_upload_file(
        file=file,
        sub_dir=f"vouchers/{voucher_id}",
    )

    attachment = FundAttachment(
        fund_id=v.fund_id or 0,
        file_name=file_info["file_name"],
        file_path=file_info["file_path"],
        file_size=file_info["file_size"],
        file_type=file_info["file_type"],
        category=category,
        description=description or f"划转凭证 {v.voucher_no} 附件",
        uploaded_by=_get_username(current_user),
    )
    db.add(attachment)
    db.flush()

    # 关联附件到凭证
    v.attachment_id = attachment.id
    safe_commit(db)
    db.refresh(attachment)

    return success_response(
        message="附件上传成功",
        data=attachment.to_dict(),
    )


@router.get("/transfer-ledger/{project_id}")
async def transfer_ledger(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """协调台账"""
    _get_project_or_403(project_id, current_user, db)
    vouchers = (
        db.query(FundTransferVoucher)
        .filter(FundTransferVoucher.project_id == project_id)
        .order_by(FundTransferVoucher.transfer_date.desc())
        .all()
    )

    mil_to_local = sum(
        float(v.amount or 0) for v in vouchers if v.direction == "military_to_local" and v.status == "confirmed"
    )
    local_to_mil = sum(
        float(v.amount or 0) for v in vouchers if v.direction == "local_to_military" and v.status == "confirmed"
    )

    return success_response(
        data={
            "project_id": project_id,
            "total_military_to_local": mil_to_local,
            "total_local_to_military": local_to_mil,
            "net_transfer": mil_to_local - local_to_mil,
            "voucher_count": len(vouchers),
            "confirmed_count": sum(1 for v in vouchers if v.status == "confirmed"),
            "vouchers": [_voucher_to_dict(v) for v in vouchers],
        }
    )


# =====================================================================
#  3.6 阶段5 - 实施监管
# =====================================================================


class ContractCreate(BaseModel):
    fund_id: Optional[int] = None
    project_id: Optional[int] = None
    contract_no: str
    contract_name: str
    party_a: Optional[str] = None
    party_b: Optional[str] = None
    contract_amount: float = Field(0, ge=0)
    sign_date: Optional[date] = None
    deadline: Optional[date] = None
    remarks: Optional[str] = None

    @field_validator("sign_date", "deadline", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v):
        """前端表单未选择日期时提交空字符串 → 视为 None，避免 Pydantic date 解析 422"""
        if isinstance(v, str) and not v.strip():
            return None
        return v


class ContractUpdate(BaseModel):
    contract_name: Optional[str] = None
    party_a: Optional[str] = None
    party_b: Optional[str] = None
    contract_amount: Optional[float] = None
    sign_date: Optional[date] = None
    deadline: Optional[date] = None
    status: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("sign_date", "deadline", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v):
        """前端表单未选择日期时提交空字符串 → 视为 None，避免 Pydantic date 解析 422"""
        if isinstance(v, str) and not v.strip():
            return None
        return v


@router.get("/contracts")
async def list_contracts(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """合同列表"""
    query = db.query(FundContract)
    query = apply_data_scope(query, FundContract, current_user)
    if project_id:
        query = query.filter(FundContract.project_id == project_id)
    if status:
        query = query.filter(FundContract.status == status)

    total = query.count()
    items = query.order_by(FundContract.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return ok_list(items=[_contract_to_dict(c) for c in items], total=total, page=page, page_size=page_size)


@router.post("/contracts")
async def create_contract(
    data: ContractCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建合同"""
    _require_manager(current_user)

    exists = db.query(FundContract).filter(FundContract.contract_no == data.contract_no).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"合同编号 {data.contract_no} 已存在")

    contract = FundContract(
        **data.model_dump(),
        created_by=_get_username(current_user),
    )
    db.add(contract)
    safe_commit(db)
    db.refresh(contract)
    write_work_log(
        db, "fund", "create_contract", contract.id,
        contract.contract_name,
        user_id=current_user.id, username=_get_username(current_user),
    )
    return success_response(message="创建成功", data=_contract_to_dict(contract))


@router.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取合同详情（含付款明细）"""
    c = db.query(FundContract).filter(FundContract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    _get_project_or_403(c.project_id, current_user, db)

    payments = (
        db.query(FundContractPayment)
        .filter(FundContractPayment.contract_id == contract_id)
        .order_by(FundContractPayment.payment_date.desc())
        .all()
    )

    result = _contract_to_dict(c)
    result["payments"] = [_payment_to_dict(p) for p in payments]
    return success_response(data=result)


@router.put("/contracts/{contract_id}")
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新合同"""
    _require_manager(current_user)

    c = db.query(FundContract).filter(FundContract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(c, key, val)
    safe_commit(db)
    db.refresh(c)
    return success_response(message="更新成功", data=_contract_to_dict(c))


@router.delete("/contracts/{contract_id}")
async def delete_contract(
    contract_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除合同（仅 draft）"""
    _require_manager(current_user)

    c = db.query(FundContract).filter(FundContract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")
    if c.status != ContractStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="仅草稿状态合同可删除")

    # 删除关联付款
    db.query(FundContractPayment).filter(FundContractPayment.contract_id == contract_id).delete()
    db.delete(c)
    safe_commit(db)
    return success_response(message="删除成功")


# 付款审批阈值（超过此金额自动触发上级审批）
PAYMENT_APPROVAL_THRESHOLD = 50.0  # 万元


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    payment_date: date
    purpose: Optional[str] = None
    voucher_no: Optional[str] = None
    operator: Optional[str] = None
    wbs_code: Optional[str] = None
    task_id: Optional[int] = None
    remarks: Optional[str] = None


@router.post("/contracts/{contract_id}/payments")
async def create_contract_payment(
    contract_id: int,
    data: PaymentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登记合同付款（含多级审批集成）"""
    _require_manager(current_user)

    c = db.query(FundContract).filter(FundContract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 生成付款编号
    count = (
        db.query(sa_func.count(FundContractPayment.id)).filter(FundContractPayment.contract_id == contract_id).scalar()
        or 0
    )
    payment_no = f"{c.contract_no}-P{count + 1:03d}"

    # 判断是否需要审批
    needs_approval = data.amount >= PAYMENT_APPROVAL_THRESHOLD
    initial_status = "pending" if needs_approval else "approved"

    payment = FundContractPayment(
        contract_id=contract_id,
        payment_no=payment_no,
        amount=data.amount,
        payment_date=data.payment_date,
        purpose=data.purpose,
        voucher_no=data.voucher_no,
        operator=data.operator or _get_username(current_user),
        wbs_code=data.wbs_code,
        task_id=data.task_id,
        status=initial_status,
        remarks=data.remarks,
    )
    db.add(payment)
    db.flush()

    # 超阈值自动创建审批任务
    approval_info = None
    if needs_approval:
        approval_info = _create_payment_approval(db, payment, c, current_user, data.amount)

    # 仅已批准的付款才更新合同金额
    if initial_status == "approved":
        c.paid_amount = float(c.paid_amount or 0) + data.amount
        contract_amt = float(c.contract_amount or 0)
        c.payment_progress = round(float(c.paid_amount or 0) / contract_amt * 100, 2) if contract_amt > 0 else 0

    safe_commit(db)
    db.refresh(payment)
    result = _payment_to_dict(payment)
    if approval_info:
        result["approval"] = approval_info
    msg = "付款登记成功" if not needs_approval else f"付款金额 {data.amount:.2f} 万元超过阈值，已自动提交审批"
    return success_response(message=msg, data=result)


def _create_payment_approval(db: Session, payment, contract, current_user, amount: float) -> dict:
    """为超阈值付款创建审批任务"""
    try:
        import json

        from ...models.approval import ApprovalTask, ApprovalWorkflow

        # 查找经费付款审批流程
        workflow = (
            db.query(ApprovalWorkflow)
            .filter(
                ApprovalWorkflow.entity_type == "fund_payment",
                ApprovalWorkflow.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not workflow:
            # 无配置审批流程时直接记录日志
            return {
                "status": "no_workflow",
                "message": "未配置付款审批流程，需人工审核",
            }

        user_id = getattr(current_user, "id", None)
        task = ApprovalTask(
            workflow_id=workflow.id,
            entity_type="fund_payment",
            entity_id=payment.id,
            submitter_id=user_id or 0,
            title=f"合同付款审批 - {contract.contract_name} - {amount:.2f}万元",
            description=f"付款编号: {payment.payment_no}，金额: {amount:.2f}万元",
            change_data=json.dumps(
                {
                    "payment_id": payment.id,
                    "contract_id": contract.id,
                    "amount": amount,
                    "payment_no": payment.payment_no,
                }
            ),
        )
        db.add(task)
        db.flush()
        return {"status": "submitted", "task_id": task.id, "workflow_id": workflow.id}
    except Exception as e:
        return {"status": "error", "message": f"创建审批任务失败: {str(e)}"}


@router.get("/monitoring/deviation/{project_id}")
async def monitoring_deviation(
    project_id: int,
    generate_report: bool = Query(False, description="是否同时生成偏差分析报告"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """进度-支付偏差分析（可选生成报告）"""
    project = _get_project_or_403(project_id, current_user, db)

    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    project_progress = project.progress or 0

    deviations = []
    for f in funds:
        approved = float(f.approved_amount or f.amount or 0)
        used = float(f.used_amount or 0)
        fund_progress = round(used / approved * 100, 1) if approved > 0 else 0
        deviation = round(fund_progress - project_progress, 1)

        # 更新偏差率
        f.deviation_rate = abs(deviation)

        # 红黄绿灯预警：±5%绿灯，±5%-10%黄灯，±10%以上红灯
        abs_dev = abs(deviation)
        if abs_dev <= 5:
            alert_level = "green"
        elif abs_dev <= 10:
            alert_level = "yellow"
        else:
            alert_level = "red"

        deviations.append(
            {
                "fund_id": f.id,
                "fund_name": f.name,
                "project_progress": project_progress,
                "fund_progress": fund_progress,
                "deviation": deviation,
                "alert_level": alert_level,
                "status": (
                    "normal" if alert_level == "green" else ("warning" if alert_level == "yellow" else "danger")
                ),
            }
        )

    db.flush()

    result = success_response(
        data={
            "project_id": project_id,
            "project_progress": project_progress,
            "deviations": deviations,
            "threshold": {"green": "±5%", "yellow": "±5%-10%", "red": "±10%以上"},
        }
    )

    # 可选：生成偏差分析报告
    if generate_report:
        from ...services.fund_report_generator import generate_deviation_report

        result["data"]["report"] = generate_deviation_report(db, project_id)

    return result


@router.get("/monitoring/fund-flow/{project_id}")
async def fund_flow(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """穿透式资金流查询（批量预加载，避免 N+1）"""
    _get_project_or_403(project_id, current_user, db)
    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    fund_ids = [f.id for f in funds]

    # 批量预加载所有交易记录和凭证（避免 N+1 查询）
    all_transactions = (
        db.query(FundTransaction)
        .filter(FundTransaction.fund_id.in_(fund_ids))
        .order_by(FundTransaction.transaction_date.desc())
        .all()
    ) if fund_ids else []
    all_vouchers = (
        db.query(FundTransferVoucher)
        .filter(FundTransferVoucher.fund_id.in_(fund_ids))
        .order_by(FundTransferVoucher.transfer_date.desc())
        .all()
    ) if fund_ids else []

    # 构建索引映射
    tx_by_fund = {}
    for t in all_transactions:
        tx_by_fund.setdefault(t.fund_id, []).append(t)
    vc_by_fund = {}
    for v in all_vouchers:
        vc_by_fund.setdefault(v.fund_id, []).append(v)

    flow_items = []
    for f in funds:
        transactions = tx_by_fund.get(f.id, [])
        vouchers = vc_by_fund.get(f.id, [])

        flow_items.append(
            {
                "fund_id": f.id,
                "fund_name": f.name,
                "planned": float(f.planned_amount or 0),
                "approved": float(f.approved_amount or 0),
                "allocated": float(f.allocated_amount or 0),
                "used": float(f.used_amount or 0),
                "remaining": float(f.remaining_amount or 0),
                "transactions": [
                    {
                        "id": t.id,
                        "amount": float(t.amount or 0),
                        "purpose": t.purpose,
                        "date": (t.transaction_date.isoformat() if t.transaction_date else None),
                        "receipt_number": t.receipt_number,
                        "handler": t.handler,
                    }
                    for t in transactions
                ],
                "transfer_vouchers": [_voucher_to_dict(v) for v in vouchers],
            }
        )

    return success_response(data={"project_id": project_id, "fund_flows": flow_items})


# =====================================================================
#  3.7 阶段6 - 核查督查
# =====================================================================


@router.get("/anomalies")
async def list_anomalies(
    project_id: Optional[int] = None,
    fund_id: Optional[int] = None,
    anomaly_type: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """异常记录列表"""
    query = db.query(FundAnomaly)
    query = apply_data_scope(query, FundAnomaly, current_user)
    if project_id:
        query = query.filter(FundAnomaly.project_id == project_id)
    if fund_id:
        query = query.filter(FundAnomaly.fund_id == fund_id)
    if anomaly_type:
        query = query.filter(FundAnomaly.anomaly_type == anomaly_type)
    if severity:
        query = query.filter(FundAnomaly.severity == severity)
    if resolved is not None:
        query = query.filter(FundAnomaly.resolved == resolved)

    total = query.count()
    items = query.order_by(FundAnomaly.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return ok_list(items=[_anomaly_to_dict(a) for a in items], total=total, page=page, page_size=page_size)


@router.post("/anomalies/detect/{project_id}")
async def detect_anomalies(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """触发智能异常检测"""
    _require_manager(current_user)

    from ...services.fund_anomaly_detector import detect_anomalies as run_detection

    new_anomalies = run_detection(db, project_id)
    safe_commit(db)

    return success_response(
        message=f"检测完成，发现 {len(new_anomalies)} 个新异常",
        data={"new_count": len(new_anomalies), "anomalies": new_anomalies},
    )


class AnomalyResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1, description="处理说明")


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: int,
    data: AnomalyResolveRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """标记异常已处理"""
    _require_manager(current_user)

    a = db.query(FundAnomaly).filter(FundAnomaly.id == anomaly_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="异常记录不存在")
    if a.resolved:
        raise HTTPException(status_code=400, detail="该异常已处理")

    a.resolved = True
    a.resolved_by = _get_username(current_user)
    a.resolved_at = datetime.now()
    a.resolution = data.resolution

    # 检查该经费是否还有未解决异常
    if a.fund_id:
        remaining = (
            db.query(sa_func.count(FundAnomaly.id))
            .filter(
                FundAnomaly.fund_id == a.fund_id,
                FundAnomaly.resolved == False,  # noqa: E712
                FundAnomaly.id != anomaly_id,
            )
            .scalar()
            or 0
        )
        fund = db.query(Fund).filter(Fund.id == a.fund_id).first()
        if fund:
            fund.has_anomaly = remaining > 0

    safe_commit(db)
    return success_response(message="异常已标记为已处理")


# =====================================================================
#  3.8 阶段7 - 决算与绩效
# =====================================================================


class SettlementCreate(BaseModel):
    fund_id: Optional[int] = None
    remarks: Optional[str] = None


@router.post("/settlement/{project_id}")
async def create_settlement(
    project_id: int,
    data: SettlementCreate = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成决算报告"""
    _require_manager(current_user)

    _get_project_or_403(project_id, current_user, db)

    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    total_budget = sum(float(f.approved_amount or f.planned_amount or f.amount or 0) for f in funds)
    total_spent = sum(float(f.used_amount or 0) for f in funds)
    total_remaining = total_budget - total_spent

    # 生成决算编号
    count = db.query(sa_func.count(FundSettlement.id)).scalar() or 0
    settlement_no = f"JS-{datetime.now().strftime('%Y%m%d')}-{count + 1:04d}"

    settlement = FundSettlement(
        project_id=project_id,
        fund_id=(data.fund_id if data else None),
        settlement_no=settlement_no,
        total_budget=total_budget,
        total_spent=total_spent,
        total_remaining=total_remaining,
        settlement_date=date.today(),
        created_by=_get_username(current_user),
        remarks=(data.remarks if data else None),
    )
    db.add(settlement)

    # 更新 Fund 决算状态
    for f in funds:
        f.settlement_status = "draft"

    safe_commit(db)
    db.refresh(settlement)
    write_work_log(
        db, "fund", "create_settlement", settlement.id,
        f"决算 {settlement.settlement_no}",
        user_id=current_user.id, username=_get_username(current_user),
        detail=f"项目ID: {project_id}, 预算: {total_budget}, 支出: {total_spent}",
    )
    return success_response(
        message="决算报告已生成",
        data=_settlement_to_dict(settlement),
    )


class SettlementUpdateRequest(BaseModel):
    total_budget: Optional[float] = None
    total_spent: Optional[float] = None
    audit_opinion: Optional[str] = None
    performance_score: Optional[int] = Field(None, ge=0, le=100)
    performance_level: Optional[str] = None
    remarks: Optional[str] = None


@router.put("/settlement/{settlement_id}")
async def update_settlement(
    settlement_id: int,
    data: SettlementUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新决算"""
    _require_manager(current_user)

    s = db.query(FundSettlement).filter(FundSettlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="决算记录不存在")
    if s.status == SettlementStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="已审批决算不可修改")

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(s, key, val)
    if data.total_budget is not None and data.total_spent is not None:
        s.total_remaining = data.total_budget - data.total_spent

    safe_commit(db)
    db.refresh(s)
    return success_response(message="更新成功", data=_settlement_to_dict(s))


class SettlementApproveRequest(BaseModel):
    audit_opinion: Optional[str] = None
    performance_score: Optional[int] = Field(None, ge=0, le=100)
    performance_level: Optional[str] = None


@router.post("/settlement/{settlement_id}/approve")
async def approve_settlement(
    settlement_id: int,
    data: SettlementApproveRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审批决算"""
    _require_manager(current_user)

    s = db.query(FundSettlement).filter(FundSettlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="决算记录不存在")
    # 幂等守卫：仅 SUBMITTED（或 DRAFT 直接提交）可审批，重复审批拒绝，
    # 避免覆盖 auditor/audit_opinion/performance_* 审计字段并重复写工作日志
    if s.status not in (
        SettlementStatus.SUBMITTED.value,
        SettlementStatus.DRAFT.value,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可审批，请检查决算状态")
    if s.status == SettlementStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="该决算已审批通过")

    s.status = SettlementStatus.APPROVED.value
    s.auditor = _get_username(current_user)
    if data:
        if data.audit_opinion:
            s.audit_opinion = data.audit_opinion
        if data.performance_score is not None:
            s.performance_score = data.performance_score
        if data.performance_level:
            s.performance_level = data.performance_level

    # 自动计算绩效等级
    if s.performance_score is not None and not s.performance_level:
        score = s.performance_score
        if score >= 90:
            s.performance_level = "A"
        elif score >= 75:
            s.performance_level = "B"
        elif score >= 60:
            s.performance_level = "C"
        else:
            s.performance_level = "D"

    # 更新 Fund 决算状态
    funds = db.query(Fund).filter(Fund.project_id == s.project_id).all()
    for f in funds:
        f.settlement_status = "approved"

    safe_commit(db)
    write_work_log(
        db, "fund", "approve_settlement", s.id,
        f"决算 {s.settlement_no}",
        user_id=current_user.id, username=_get_username(current_user),
        detail="决算审批通过",
    )
    return success_response(message="决算已审批通过")


@router.get("/performance/{project_id}")
async def get_performance(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """绩效评估数据"""
    _get_project_or_403(project_id, current_user, db)
    settlement = (
        db.query(FundSettlement)
        .filter(FundSettlement.project_id == project_id)
        .order_by(FundSettlement.id.desc())
        .first()
    )

    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    total_budget = sum(float(f.approved_amount or f.amount or 0) for f in funds)
    total_used = sum(float(f.used_amount or 0) for f in funds)
    execution_rate = round(total_used / total_budget * 100, 1) if total_budget > 0 else 0

    # 异常统计
    anomaly_total = db.query(sa_func.count(FundAnomaly.id)).filter(FundAnomaly.project_id == project_id).scalar() or 0
    anomaly_resolved = (
        db.query(sa_func.count(FundAnomaly.id))
        .filter(FundAnomaly.project_id == project_id, FundAnomaly.resolved == True)  # noqa: E712
        .scalar()
        or 0
    )

    return success_response(
        data={
            "project_id": project_id,
            "settlement": _settlement_to_dict(settlement) if settlement else None,
            "budget_summary": {
                "total_budget": total_budget,
                "total_used": total_used,
                "execution_rate": execution_rate,
            },
            "anomaly_summary": {
                "total": anomaly_total,
                "resolved": anomaly_resolved,
                "unresolved": anomaly_total - anomaly_resolved,
                "resolution_rate": (round(anomaly_resolved / anomaly_total * 100, 1) if anomaly_total > 0 else 100),
            },
        }
    )


# =====================================================================
#  3.9 健康度 & 联动
# =====================================================================


@router.get("/health/{project_id}")
async def get_health(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """资金健康度评分（按项目聚合其下全部资金记录计算）"""
    _get_project_or_403(project_id, current_user, db)
    from ...services.fund_health_service import calculate_project_health_sync

    result = calculate_project_health_sync(db, project_id)
    return success_response(data=result)


class BatchHealthRequest(BaseModel):
    project_ids: List[int]


@router.post("/health/batch")
async def batch_health(
    data: BatchHealthRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量获取多项目健康度（项目列表用）"""
    if not data.project_ids:
        return success_response(data=[])
    from ...services.fund_health_service import calculate_projects_health_sync

    result = calculate_projects_health_sync(db, data.project_ids)
    return success_response(data=result)


# =====================================================================
#  3.10 拨款指令管理
# =====================================================================


class AllocationOrderCreate(BaseModel):
    fund_id: Optional[int] = None
    project_id: Optional[int] = None
    order_no: str
    source_document: Optional[str] = None
    total_amount: float = Field(..., gt=0)
    target_organization_id: Optional[int] = None
    target_organization_name: Optional[str] = None
    target_account: Optional[str] = None
    issue_date: Optional[date] = None
    remarks: Optional[str] = None


@router.get("/allocation-orders")
async def list_allocation_orders(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拨款指令列表"""
    from ...models.fund_allocation_order import FundAllocationOrder

    query = db.query(FundAllocationOrder)
    query = apply_data_scope(query, FundAllocationOrder, current_user)
    if project_id:
        query = query.filter(FundAllocationOrder.project_id == project_id)
    if status:
        query = query.filter(FundAllocationOrder.status == status)

    total = query.count()
    items = query.order_by(FundAllocationOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok_list(items=[i.to_dict() for i in items], total=total, page=page, page_size=page_size)


@router.post("/allocation-orders")
async def create_allocation_order(
    data: AllocationOrderCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建拨款指令"""
    _require_manager(current_user)
    from ...models.fund_allocation_order import FundAllocationOrder

    exists = db.query(FundAllocationOrder).filter(FundAllocationOrder.order_no == data.order_no).first()
    if exists:
        raise HTTPException(status_code=400, detail=f"拨款指令编号 {data.order_no} 已存在")

    order = FundAllocationOrder(
        **data.model_dump(),
        created_by=_get_username(current_user),
    )
    db.add(order)
    safe_commit(db)
    db.refresh(order)
    return success_response(message="拨款指令创建成功", data=order.to_dict())


@router.post("/allocation-orders/{order_id}/issue")
async def issue_allocation_order(
    order_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下达拨款指令"""
    _require_manager(current_user)
    from ...models.fund_allocation_order import FundAllocationOrder

    order = db.query(FundAllocationOrder).filter(FundAllocationOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="拨款指令不存在")
    if order.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可下达")

    order.status = "issued"
    order.issue_date = date.today()
    safe_commit(db)
    write_work_log(
        db, "fund", "issue_allocation_order", order.id,
        f"拨款指令 {order.order_no}",
        user_id=current_user.id, username=_get_username(current_user),
        detail="拨款指令已下达",
    )
    return success_response(message="拨款指令已下达")


# =====================================================================
#  3.11 额度调整审批
# =====================================================================


class QuotaAdjustRequest(BaseModel):
    new_amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1, description="调整原因")
    is_emergency: bool = False

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """验证并清理调整原因"""
        if v:
            v = v.strip()
            if not v:
                raise ValueError("调整原因不能为空或仅包含空格")
        return v


@router.put("/quota-adjust/{fund_id}")
async def quota_adjust(
    fund_id: int,
    data: QuotaAdjustRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """额度调整申请（紧急调整需 super_admin）"""
    _require_manager(current_user)

    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="经费记录不存在")

    if data.is_emergency:
        role = getattr(current_user, "role", "")
        if role != "super_admin" and not is_superuser(current_user):
            raise HTTPException(status_code=403, detail="紧急额度调整需要 super_admin 权限")

    import json

    from ...models.fund_lifecycle import BudgetVersion

    # 记录版本快照
    old_amount = float(fund.approved_amount or fund.planned_amount or fund.amount or 0)
    new_version = (fund.budget_version or 1) + 1

    bv = BudgetVersion(
        fund_id=fund.id,
        project_id=fund.project_id or 0,
        version=new_version,
        planned_amount=old_amount,
        approved_amount=data.new_amount,
        change_reason=data.reason,
        change_type="adjust",
        status="approved" if data.is_emergency else "submitted",
        operator=_get_username(current_user),
        snapshot_data=json.dumps({"old": old_amount, "new": data.new_amount}),
    )
    db.add(bv)

    if data.is_emergency:
        fund.approved_amount = data.new_amount
        fund.budget_version = new_version
        bv.approved_by = _get_username(current_user)
        bv.approved_at = datetime.now()

    safe_commit(db)
    msg = "紧急额度调整已生效" if data.is_emergency else "额度调整申请已提交，待审批"
    return success_response(message=msg)


# =====================================================================
#  3.12 督查线索清单
# =====================================================================


@router.get("/inspection-clues/{project_id}")
async def inspection_clues(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成标准化督查线索清单（批量预加载 Fund，避免 N+1）"""
    _get_project_or_403(project_id, current_user, db)
    anomalies = (
        db.query(FundAnomaly)
        .filter(FundAnomaly.project_id == project_id)
        .order_by(FundAnomaly.severity.desc(), FundAnomaly.detected_at.desc())
        .all()
    )

    # 批量预加载关联的 Fund 记录
    fund_ids = {a.fund_id for a in anomalies if a.fund_id}
    fund_map = {}
    if fund_ids:
        funds = db.query(Fund).filter(Fund.id.in_(list(fund_ids))).all()
        fund_map = {f.id: f for f in funds}

    type_labels = {
        "overspend": "超支",
        "deviation": "偏差",
        "idle": "资金闲置",
        "duplicate": "重复支付",
        "missing_voucher": "缺失凭证",
        "large_cash": "大额提现",
        "contract_split": "合同拆分",
        "single_source": "单一来源采购",
    }
    suggestion_map = {
        "overspend": "建议立即停止支出，启动超支审查程序",
        "deviation": "建议核查项目进度与资金支付的匹配性",
        "idle": "建议查明资金闲置原因，加快使用或调回",
        "duplicate": "建议核实是否存在重复支付，如确认应追回",
        "missing_voucher": "建议补充完善支出凭证",
        "large_cash": "建议核查大额提现用途的合理性",
        "contract_split": "建议核查是否存在人为拆分合同规避审批",
        "single_source": "建议核查单一来源采购的合规性",
    }

    clues = []
    for a in anomalies:
        fund = fund_map.get(a.fund_id) if a.fund_id else None
        clues.append(
            {
                "anomaly_id": a.id,
                "type": a.anomaly_type,
                "type_label": type_labels.get(a.anomaly_type, a.anomaly_type),
                "severity": a.severity,
                "description": a.description,
                "involved_amount": float(fund.amount or 0) if fund else None,
                "involved_person": fund.operator if fund else None,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "resolved": a.resolved,
                "suggestion": suggestion_map.get(a.anomaly_type, "建议进一步核查"),
            }
        )

    return success_response(
        data={
            "project_id": project_id,
            "total_clues": len(clues),
            "unresolved_count": sum(1 for c in clues if not c["resolved"]),
            "clues": clues,
        }
    )


# =====================================================================
#  3.13 资产联动校验
# =====================================================================


class AssetVerifyRequest(BaseModel):
    asset_value: float = Field(..., ge=0, description="转固资产价值(万元)")
    opinion: Optional[str] = None


@router.post("/settlement/{settlement_id}/verify-asset")
async def verify_asset(
    settlement_id: int,
    data: AssetVerifyRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """资产联动校验（项目销号前置条件）"""
    _require_manager(current_user)

    s = db.query(FundSettlement).filter(FundSettlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="决算记录不存在")

    from ...models.fund_asset_verification import FundAssetVerification

    total_paid = float(s.total_spent or 0)
    asset_val = data.asset_value
    diff = abs(total_paid - asset_val)
    diff_rate = round(diff / total_paid * 100, 2) if total_paid > 0 else 0
    passed = diff_rate <= 5  # 差异率≤5% 视为通过

    verification = FundAssetVerification(
        project_id=s.project_id,
        settlement_id=settlement_id,
        total_paid=total_paid,
        asset_value=asset_val,
        difference=diff,
        difference_rate=diff_rate,
        status="passed" if passed else "failed",
        verified_by=_get_username(current_user),
        verified_at=datetime.now(),
        opinion=data.opinion,
    )
    db.add(verification)

    # 更新决算记录
    s.asset_verified = passed
    s.asset_value = asset_val

    safe_commit(db)
    db.refresh(verification)
    return success_response(
        message=("资产校验通过" if passed else f"资产校验未通过（差异率 {diff_rate}%）"),
        data=verification.to_dict(),
    )


# =====================================================================
#  3.14 绩效自评报告
# =====================================================================


@router.get("/performance-report/{project_id}")
async def performance_report(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """绩效自评报告（基于经济指标量化对比）"""
    _get_project_or_403(project_id, current_user, db)
    from ...services.performance_evaluator import generate_performance_report

    result = generate_performance_report(db, project_id)
    return success_response(data=result)


@router.get("/feasibility-report/{project_id}")
async def feasibility_report(
    project_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """可行性研究报告投资估算章节"""
    _get_project_or_403(project_id, current_user, db)
    from ...services.fund_report_generator import generate_feasibility_report

    result = generate_feasibility_report(db, project_id)
    return success_response(data=result)


# =====================================================================
#  3.15 穿透式查询增强
# =====================================================================


@router.get("/monitoring/fund-flow-tree/{project_id}")
async def fund_flow_tree(
    project_id: int,
    fund_code: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """资金流向树形结构（中央拨款→单位→末端采购）

    优化：使用 joinedload 预加载关联数据，避免 N+1 查询。
    """
    _get_project_or_403(project_id, current_user, db)
    from ...models.fund_allocation_order import AllocationOrderItem, FundAllocationOrder

    query = db.query(Fund).filter(Fund.project_id == project_id)
    if fund_code:
        query = query.filter(Fund.code == fund_code)
    funds = query.all()

    if not funds:
        return []

    # 批量预加载所有拨款指令和明细项（避免 N+1）
    fund_ids = [f.id for f in funds]
    all_orders = (
        db.query(FundAllocationOrder)
        .filter(FundAllocationOrder.fund_id.in_(fund_ids))
        .all()
    )
    order_ids = [o.id for o in all_orders]
    all_items = (
        db.query(AllocationOrderItem)
        .filter(AllocationOrderItem.order_id.in_(order_ids))
        .all()
    ) if order_ids else []

    # 批量预加载所有交易记录
    all_transactions = (
        db.query(FundTransaction)
        .filter(FundTransaction.fund_id.in_(fund_ids))
        .order_by(FundTransaction.transaction_date.desc())
        .all()
    )

    # 构建索引映射
    orders_by_fund = {}
    for o in all_orders:
        orders_by_fund.setdefault(o.fund_id, []).append(o)

    items_by_order = {}
    for it in all_items:
        items_by_order.setdefault(it.order_id, []).append(it)

    transactions_by_fund = {}
    for t in all_transactions:
        transactions_by_fund.setdefault(t.fund_id, []).append(t)

    tree = []
    for f in funds:
        # 第一层：拨款指令（使用预加载数据）
        order_nodes = []
        for o in orders_by_fund.get(f.id, []):
            items = items_by_order.get(o.id, [])
            order_nodes.append(
                {
                    "order_no": o.order_no,
                    "amount": float(o.total_amount or 0),
                    "status": o.status,
                    "children": [
                        {
                            "organization": it.organization_name,
                            "amount": float(it.amount or 0),
                            "status": it.status,
                        }
                        for it in items
                    ],
                }
            )

        # 第二层：支出明细（使用预加载数据）
        transactions = transactions_by_fund.get(f.id, [])

        tree.append(
            {
                "fund_id": f.id,
                "fund_name": f.name,
                "fund_code": f.code,
                "total_amount": float(f.amount or 0),
                "approved": float(f.approved_amount or 0),
                "used": float(f.used_amount or 0),
                "allocation_orders": order_nodes,
                "transactions": [
                    {
                        "id": t.id,
                        "amount": float(t.amount or 0),
                        "purpose": t.purpose,
                        "date": (t.transaction_date.isoformat() if t.transaction_date else None),
                        "handler": t.handler,
                    }
                    for t in transactions
                ],
            }
        )

    return success_response(data={"project_id": project_id, "fund_tree": tree})


# =====================================================================
#  辅助函数
# =====================================================================


def _init_phases(db: Session, project_id: int) -> list:
    """为项目初始化 7 个阶段记录。"""
    phases = []
    for i in range(1, 8):
        p = ProjectFundPhase(
            project_id=project_id,
            phase=i,
            status=PhaseStatus.NOT_STARTED.value,
        )
        db.add(p)
        phases.append(p)
    db.flush()
    return phases


def _voucher_to_dict(v: FundTransferVoucher) -> dict:
    direction_labels = {
        "military_to_local": "专项→地方",
        "local_to_military": "地方→专项",
    }
    status_labels = {
        "draft": "草稿",
        "submitted": "已提交",
        "confirmed": "已确认",
        "rejected": "已拒绝",
    }
    return {
        "id": v.id,
        "fund_id": v.fund_id,
        "project_id": v.project_id,
        "voucher_no": v.voucher_no,
        "direction": v.direction,
        "direction_label": direction_labels.get(v.direction, v.direction),
        "amount": float(v.amount or 0),
        "payer_account": v.payer_account,
        "payee_account": v.payee_account,
        "transfer_date": v.transfer_date.isoformat() if v.transfer_date else None,
        "status": v.status,
        "status_label": status_labels.get(v.status, v.status),
        "confirmed_by": v.confirmed_by,
        "confirmed_at": v.confirmed_at.isoformat() if v.confirmed_at else None,
        "remarks": v.remarks,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _contract_to_dict(c: FundContract) -> dict:
    status_labels = {
        "draft": "草稿",
        "active": "执行中",
        "completed": "已完成",
        "terminated": "已终止",
    }
    return {
        "id": c.id,
        "fund_id": c.fund_id,
        "project_id": c.project_id,
        "contract_no": c.contract_no,
        "contract_name": c.contract_name,
        "party_a": c.party_a,
        "party_b": c.party_b,
        "contract_amount": float(c.contract_amount or 0),
        "paid_amount": float(c.paid_amount or 0),
        "payment_progress": float(c.payment_progress or 0),
        "sign_date": c.sign_date.isoformat() if c.sign_date else None,
        "deadline": c.deadline.isoformat() if c.deadline else None,
        "status": c.status,
        "status_label": status_labels.get(c.status, c.status),
        "remarks": c.remarks,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _payment_to_dict(p: FundContractPayment) -> dict:
    return {
        "id": p.id,
        "contract_id": p.contract_id,
        "payment_no": p.payment_no,
        "amount": float(p.amount or 0),
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "purpose": p.purpose,
        "voucher_no": p.voucher_no,
        "status": p.status,
        "operator": p.operator,
        "remarks": p.remarks,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _anomaly_to_dict(a: FundAnomaly) -> dict:
    type_labels = {
        "overspend": "超支",
        "deviation": "偏差",
        "idle": "资金闲置",
        "duplicate": "重复支付",
        "missing_voucher": "缺失凭证",
    }
    severity_labels = {"info": "提示", "warning": "警告", "danger": "严重"}
    return {
        "id": a.id,
        "fund_id": a.fund_id,
        "project_id": a.project_id,
        "anomaly_type": a.anomaly_type,
        "anomaly_type_label": type_labels.get(a.anomaly_type, a.anomaly_type),
        "severity": a.severity,
        "severity_label": severity_labels.get(a.severity, a.severity),
        "description": a.description,
        "detected_at": a.detected_at.isoformat() if a.detected_at else None,
        "resolved": a.resolved,
        "resolved_by": a.resolved_by,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "resolution": a.resolution,
    }


def _settlement_to_dict(s: FundSettlement) -> dict:
    status_labels = {"draft": "草稿", "submitted": "已提交", "approved": "已审批"}
    level_labels = {"A": "优秀", "B": "良好", "C": "合格", "D": "不合格"}
    return {
        "id": s.id,
        "project_id": s.project_id,
        "fund_id": s.fund_id,
        "settlement_no": s.settlement_no,
        "total_budget": float(s.total_budget or 0),
        "total_spent": float(s.total_spent or 0),
        "total_remaining": float(s.total_remaining or 0),
        "settlement_date": s.settlement_date.isoformat() if s.settlement_date else None,
        "status": s.status,
        "status_label": status_labels.get(s.status, s.status),
        "auditor": s.auditor,
        "audit_opinion": s.audit_opinion,
        "performance_score": s.performance_score,
        "performance_level": s.performance_level,
        "performance_level_label": level_labels.get(s.performance_level, ""),
        "remarks": s.remarks,
        "created_by": s.created_by,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }

# ==================== ��ͬ�����ϱ� ====================


# ==================== 合同附件上报 ====================


class ContractAttachmentCreate(BaseModel):
    """合同附件记录（文件已通过通用上传端点保存，此处登记 URL）"""

    url: str = Field(..., min_length=1)
    file_name: Optional[str] = None
    file_size: Optional[float] = None


@router.post("/contracts/{contract_id}/attachments", summary="登记合同附件（合同文件/付款资料）")
async def upload_contract_attachment(
    contract_id: int,
    data: ContractAttachmentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登记合同相关附件资料（合同扫描件/付款凭证/验收资料等）

    文件先经通用上传端点 /files/upload 保存，此处将 URL 记录到合同备注。
    """
    _require_manager(current_user)
    from app.models.fund_lifecycle import FundContract

    contract = db.query(FundContract).filter(FundContract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    existing = _contract_attachments(contract)
    existing.append(
        {
            "url": data.url,
            "file_name": data.file_name or data.url.split("/")[-1],
            "file_size": data.file_size or "",
            "uploaded_by": _get_username(current_user),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    setattr(contract, "remarks", _json.dumps(existing, ensure_ascii=False) if existing else None)
    safe_commit(db)

    return success_response(
        message="附件上传成功",
        data={"url": data.url, "file_name": data.file_name},
    )


@router.get("/contracts/{contract_id}/attachments", summary="获取合同附件列表")
async def list_contract_attachments(
    contract_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取合同上传的附件记录列表"""
    _require_manager(current_user)
    from app.models.fund_lifecycle import FundContract

    contract = db.query(FundContract).filter(FundContract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")
    items = _contract_attachments(contract)
    return ok_list(items=items, total=len(items))


def _contract_attachments(contract) -> list:
    """解析合同备注中的附件记录（JSON 数组）"""
    remarks = getattr(contract, "remarks", None)
    if not remarks:
        return []
    try:
        parsed = _json.loads(remarks)
        if isinstance(parsed, list):
            return [a for a in parsed if isinstance(a, dict) and "url" in a]
    except (ValueError, TypeError):
        pass
    return []
