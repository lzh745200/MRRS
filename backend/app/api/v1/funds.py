"""
经费管理 API 路由 (最终优化版)

离线桌面管理系统 - 经费全流程管理
重构亮点：
1. 全面拥抱 SQLAlchemy 2.0 (select 语法)
2. 修复状态流转中的字段映射 Bug (allocated_at -> allocation_date 等)
3. 引入严格的状态机校验，防止非法状态流转
4. 统计接口性能极致优化 (单次聚合、消灭 strftime 全表扫描)
5. 集成 DataScope 数据权限隔离
6. 修复 list_funds 中 status 参数名覆盖 fastapi.status 模块的致命隐患
"""

# 数据权限过滤已迁移到 app.core.data_scope_adapter.apply_scope_filter()
# 支持组织树展开（org_children 含下级组织），与 school.py 行为一致

import logging
import mimetypes
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.v1.deps import require_manager_role, enforce_admin_include_deleted, build_viewable_because
from app.core.database import get_db
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.core.transaction import safe_commit
from app.utils.pagination import keyset_paginate
from app.core.data_scope_adapter import apply_scope_filter
from app.services.work_log_service import write_work_log
from app.utils.upload_helper import save_upload_file, get_attachment_response, delete_attachment_file

from app.models.fund import Fund, FundAttachment
from app.models.fund_history import FundStatusHistory, FundOperationLog
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/funds", tags=["经费管理"])


# ============================================================================
# Pydantic Schemas (建议后续移至 app/schemas/fund.py)
# ============================================================================


class FundCreate(BaseModel):
    """创建经费记录"""
    name: Optional[str] = None
    amount: float = 0
    planned_amount: float = 0
    approved_amount: Optional[float] = None
    allocated_amount: Optional[float] = None
    used_amount: Optional[float] = None
    remaining_amount: Optional[float] = None
    code: Optional[str] = None
    type: Optional[str] = None
    fund_type: Optional[str] = None
    fund_source: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    purpose: Optional[str] = None
    source: Optional[str] = None
    operator: Optional[str] = None
    receiver: Optional[str] = None
    usage_description: Optional[str] = None
    status: str = "pending"
    applicant: Optional[str] = None
    remarks: Optional[str] = None
    date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    model_config = {"extra": "ignore"}


class FundUpdate(BaseModel):
    """更新经费记录"""
    name: Optional[str] = None
    amount: Optional[float] = None
    planned_amount: Optional[float] = None
    approved_amount: Optional[float] = None
    allocated_amount: Optional[float] = None
    used_amount: Optional[float] = None
    remaining_amount: Optional[float] = None
    code: Optional[str] = None
    type: Optional[str] = None
    fund_type: Optional[str] = None
    fund_source: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    purpose: Optional[str] = None
    source: Optional[str] = None
    operator: Optional[str] = None
    status: Optional[str] = None
    applicant: Optional[str] = None
    remarks: Optional[str] = None
    date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    approved_by: Optional[str] = None
    approval_date: Optional[str] = None

    model_config = {"extra": "forbid"}


# ============================================================================
# 辅助工具与序列化
# ============================================================================

def _safe_val(val: Any) -> Any:
    """安全转换数据库值为 JSON 可序列化类型"""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if hasattr(val, "isoformat"):  # 兼容 date 类型
        return val.isoformat()
    return val


# 需要解析为 date/datetime 的字段集合
_DATE_FIELDS = {"date", "start_date", "end_date", "approval_date", "application_date", "allocation_date", "audit_date"}


def _parse_date_value(key: str, value: Any) -> Any:
    """将日期字符串解析为 Python date/datetime 对象。

    SQLite Date/DateTime 列只接受 Python date/datetime 对象，
    前端发来的 JSON 日期是字符串（如 '2026-07-21'），必须转换。
    """
    if value is None or key not in _DATE_FIELDS:
        return value
    if isinstance(value, (date, datetime)):
        return value
    if isinstance(value, str):
        value_str = value.strip()
        if not value_str:
            return None
        # 尝试解析 datetime（含时间部分）
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                return datetime.strptime(value_str, fmt)
            except ValueError:
                continue
        # 尝试解析纯日期
        try:
            return date.fromisoformat(value_str)
        except ValueError:
            pass
        # 无法解析则原样返回（让 SQLAlchemy 报错而非静默丢失）
        logger.warning("无法解析日期字段 %s='%s'，原样传递", key, value_str)
    return value


def _fund_to_dict(f: Fund) -> Dict[str, Any]:
    """将 Fund ORM 对象转为字典（snake_case 键名，与前端字段名一致）"""
    result = {}
    for col in Fund.__table__.columns:
        result[col.name] = _safe_val(getattr(f, col.name, None))

    # 补充关联数据（如果使用了 joinedload 预加载）
    if hasattr(f, "project") and f.project:
        result["project_name"] = f.project.name
    if hasattr(f, "village") and f.village:
        result["village_name"] = f.village.village_name
    if hasattr(f, "school") and f.school:
        result["school_name"] = f.school.name

    return result


def _get_fund_or_404(db: Session, fund_id: int, current_user: User) -> Fund:
    """通用：获取经费并校验权限，不存在则抛出 404"""
    stmt = select(Fund).where(Fund.id == fund_id)
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    fund = db.execute(stmt).scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="经费记录不存在或无权访问")
    return fund


# ============================================================================
# 1. 基础 CRUD 操作
# ============================================================================


@router.get("")
def list_funds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    # 🚨 修复：使用 status_filter 避免覆盖 fastapi.status 模块，通过 alias 保持 API 契约
    status_filter: Optional[str] = Query(None, alias="status"),
    fund_type: Optional[str] = None,
    fund_source: Optional[str] = None,
    project_id: Optional[int] = None,
    village_id: Optional[int] = None,
    school_id: Optional[int] = None,
    cursor: Optional[str] = Query(None, description="Keyset分页游标"),
    pagination: str = Query("offset", description="分页方式: 'offset' | 'keyset'"),
    include_deleted: bool = Depends(enforce_admin_include_deleted),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询经费列表（支持OFFSET和Keyset两种分页）"""
    # 1. 构建基础查询 (SQLAlchemy 2.0)
    stmt = select(Fund).options(
        selectinload(Fund.project),
        selectinload(Fund.village),
        selectinload(Fund.school),
    )

    # 2. 数据权限隔离（统一使用 data_scope_adapter，支持 org_children 含下级组织）
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)

    # include_deleted 已由 enforce_admin_include_deleted 依赖收敛：非管理员自动降级为 False

    # 2.5 软删过滤：默认隐藏 is_active=False 的记录
    if not include_deleted:
        stmt = stmt.where(Fund.is_active == True)  # noqa: E712

    # 3. 动态过滤
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            (Fund.name.ilike(kw)) | (Fund.code.ilike(kw)) | (Fund.purpose.ilike(kw))
        )
    if status_filter:
        stmt = stmt.where(Fund.status == status_filter)
    if fund_type:
        stmt = stmt.where(Fund.fund_type == fund_type)
    if fund_source:
        stmt = stmt.where(Fund.fund_source == fund_source)
    if project_id:
        stmt = stmt.where(Fund.project_id == project_id)
    if village_id:
        stmt = stmt.where(Fund.village_id == village_id)
    if school_id:
        stmt = stmt.where(Fund.school_id == school_id)

    # 4. 分页执行
    if pagination == "keyset":
        result = keyset_paginate(
            stmt, order_column=Fund.id, page_size=page_size, cursor=cursor, desc=True, db=db
        )
        # 统一 envelope：{code:200, data:{items,total,page_size,page,next_cursor,has_more}, message}
        return ok_list(
            items=[_fund_to_dict(f) for f in result["items"]],
            total=result["total"],
            page=page,
            page_size=result["page_size"],
            next_cursor=result["next_cursor"],
            has_more=result["has_more"],
            pagination="keyset",
        )

    # 传统 OFFSET 分页 (手动构建以完美兼容 apply_scope_filter 和 joinedload)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    items_stmt = stmt.order_by(Fund.id.desc()).offset((page - 1) * page_size).limit(page_size)
    items = db.execute(items_stmt).scalars().unique().all()

    return ok_list(
        items=[_fund_to_dict(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
        pagination="offset",
    )


@router.get("/export")
def export_funds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(5000, ge=1, le=50000, description="最大导出条数"),
):
    """导出经费数据（带分页上限，防止内存溢出；排除软删记录）"""
    stmt = select(Fund).where(Fund.is_active == True).order_by(Fund.id.desc()).limit(limit)  # noqa: E712
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    funds = db.execute(stmt).scalars().all()
    return success_response(
        data={"items": [_fund_to_dict(f) for f in funds], "total_exported": len(funds), "limit": limit},
    )


@router.get("/{fund_id}")
def get_fund(
    fund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询经费详情。

    跨组织访问时返回明确 403，避免用户误以为记录不存在。
    管理员查看已软删记录时附带 viewableBecause="admin" 元数据。
    """
    # 先不带数据权限查一次，区分"不存在"和"无权访问"
    exists = db.execute(select(Fund.id).where(Fund.id == fund_id)).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail="经费记录不存在")

    stmt = (
        select(Fund)
        .where(Fund.id == fund_id)
        .options(
            joinedload(Fund.project), joinedload(Fund.village),
            joinedload(Fund.school), selectinload(Fund.organization),
        )
    )
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    fund = db.execute(stmt).scalar_one_or_none()

    if not fund:
        # 记录存在但数据权限过滤后为空 → 跨组织访问
        raise HTTPException(status_code=403, detail="无权访问该组织数据")
    data = _fund_to_dict(fund)
    data["viewableBecause"] = build_viewable_because(current_user, fund)
    return success_response(data=data)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_fund(
    data: FundCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建经费记录（需管理员权限）"""
    require_manager_role(current_user)
    from app.services.fund_service import FundService
    fund = FundService(db).create_fund_for_user(
        data, current_user.id, current_user.organization_id,
    )
    return success_response(data={"id": fund.id}, message="创建成功")


@router.post("/apply", status_code=status.HTTP_201_CREATED)
def apply_fund(
    data: FundCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户经费申请 — 无需管理员权限，所有登录用户均可提交"""
    from app.services.fund_service import FundService
    fund = FundService(db).create_fund_for_user(
        data, current_user.id, current_user.organization_id,
        status="pending",
        applicant=current_user.full_name or current_user.username,
    )
    return success_response(data={"id": fund.id}, message="申请已提交，等待审批")


@router.put("/{fund_id}")
def update_fund(
    fund_id: int,
    data: FundUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新经费记录"""
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)

    # 业务校验：已审批或已拨付的经费不允许随意修改核心字段
    if fund.status not in ["pending", "planned", "rejected"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不允许修改")

    # exclude_unset: 仅排除客户端未发送的字段，显式传 null 的字段会设为 None（清空）
    for key, value in data.model_dump(exclude_unset=True).items():
        if hasattr(fund, key):
            setattr(fund, key, _parse_date_value(key, value))
        else:  # pragma: no cover —— FundUpdate schema 字段在 Fund 模型上全部存在，防御分支不可达
            logger.warning("update_fund: skipping unknown field '%s' on Fund(id=%d)", key, fund_id)

    safe_commit(db)
    return success_response(message="更新成功")


@router.delete("/{fund_id}")
def delete_fund(
    fund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """软删经费记录（置 is_active=False，保留数据以便恢复/审计）"""
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)

    if fund.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅允许删除待审批(pending)状态的经费")

    fund.is_active = False
    safe_commit(db)
    return success_response(message="删除成功")


# ============================================================================
# 2. 资金统计 (极致性能优化)
# ============================================================================


@router.get("/statistics/overview")
def fund_statistics_overview(
    year: Optional[int] = Query(None, description="年度（按 Fund.year 过滤，默认全部）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """经费统计概览 (单次聚合查询，排除软删记录)

    支持按年度统计：预算总额/已执行（fund_budgets）、申请/批准/拨付/使用情况（funds）
    """
    from app.models.fund_budget import FundBudget

    stmt = select(
        func.count(Fund.id).label("total_count"),
        func.coalesce(func.sum(Fund.amount), 0).label("total_amount"),
        func.sum(case((Fund.status == "pending", 1), else_=0)).label("pending_count"),
        func.sum(case((Fund.status == "approved", 1), else_=0)).label("approved_count"),
        func.sum(case((Fund.status == "allocated", 1), else_=0)).label("allocated_count"),
        func.sum(case((Fund.status == "in_use", 1), else_=0)).label("in_use_count"),
        func.sum(case((Fund.status == "completed", 1), else_=0)).label("completed_count"),
        func.coalesce(func.sum(Fund.used_amount), 0).label("used_amount"),
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("allocated_amount"),
    ).where(Fund.is_active == True)  # noqa: E712
    if year:
        stmt = stmt.where(Fund.year == year)
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)

    row = db.execute(stmt).one()

    # 年度预算统计（fund_budgets）
    budget_stmt = db.query(
        func.coalesce(func.sum(FundBudget.budget_amount), 0),
        func.coalesce(func.sum(FundBudget.executed_amount), 0),
    )
    if year:
        budget_stmt = budget_stmt.filter(FundBudget.year == year)
    budget_row = budget_stmt.first()
    budget_total = float(budget_row[0] or 0) if budget_row else 0
    budget_executed = float(budget_row[1] or 0) if budget_row else 0

    budget_total = float(budget_total or 0)
    budget_executed = float(budget_executed or 0)
    total_amount = float(row.total_amount)

    return success_response(data={
        "year": year,
        "total_count": row.total_count,
        "total_amount": total_amount,
        "pending_count": row.pending_count,
        "approved_count": row.approved_count,
        "allocated_count": row.allocated_count,
        "in_use_count": row.in_use_count,
        "completed_count": row.completed_count,
        "used_amount": float(row.used_amount or 0),
        "allocated_amount": float(row.allocated_amount or 0),
        "budget_total": budget_total,
        "budget_executed": budget_executed,
        "budget_remaining": round(budget_total - budget_executed, 2),
        "usage_rate": round((budget_executed / budget_total * 100), 1) if budget_total > 0 else 0,
    })


@router.get("/statistics/multi-dimension")
def fund_statistics_multi_dimension(
    group_by: str = Query("type", description="分组维度: period, type, source, status"),
    start_date: str = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    period_type: str = Query("monthly", description="时间粒度: monthly, quarterly, yearly"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """经费多维度统计分析 (利用冗余字段消灭全表扫描，排除软删记录)"""
    stmt = select(Fund).where(Fund.is_active == True)  # noqa: E712
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)

    try:
        if start_date:
            stmt = stmt.where(Fund.date >= datetime.strptime(start_date, "%Y-%m-%d").date())
        if end_date:
            stmt = stmt.where(Fund.date <= datetime.strptime(end_date, "%Y-%m-%d").date())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式错误，请使用 YYYY-MM-DD 格式")

    agg_cols = [
        func.count(Fund.id).label("count"),
        func.coalesce(func.sum(Fund.amount), 0).label("total_amount"),
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("total_allocated"),
        func.coalesce(func.sum(Fund.used_amount), 0).label("total_used"),
    ]

    if group_by == "period":
        if period_type == "quarterly":
            group_col = Fund.year_quarter
        elif period_type == "yearly":
            group_col = Fund.year
        else:
            group_col = Fund.year_month

        stmt = stmt.with_only_columns(
            group_col.label("group_key"), *agg_cols
        ).group_by(group_col).order_by(group_col)

    elif group_by in ("type", "source", "status"):
        col_map = {"type": Fund.fund_type, "source": Fund.fund_source, "status": Fund.status}
        group_col = col_map[group_by]
        stmt = stmt.with_only_columns(group_col.label("group_key"), *agg_cols).group_by(group_col)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的分组维度: {group_by}")

    rows = db.execute(stmt).all()

    label_maps = {
        "source": {"military": "专项投资", "government": "政府拨款", "donation": "社会捐赠", "enterprise": "企业投资", "other": "其他"},
        "status": {
            "pending": "待审批", "planned": "规划中", "approved": "已批准",
            "allocated": "已拨付", "in_use": "使用中", "completed": "已完成", "audited": "已审计",
        },
        "type": {
            "project": "项目经费", "operation": "运营经费", "education": "教育帮扶",
            "infrastructure": "基础设施", "emergency": "应急经费", "other": "其他",
        }
    }
    current_map = label_maps.get(group_by, {})

    result = []
    for r in rows:
        key = r.group_key or "未知"
        if not key:  # pragma: no cover —— 上行 or "未知" 保证 key 永非空，防御分支不可达
            continue

        label = str(key) if group_by == "period" else current_map.get(key, key)
        total_amt = float(r.total_amount or 0)
        used_amt = float(r.total_used or 0)

        result.append({
            "label": label,
            "count": r.count,
            "total_amount": round(total_amt, 2),
            "total_allocated": round(float(r.total_allocated or 0), 2),
            "total_used": round(used_amt, 2),
            "utilization_rate": round((used_amt / total_amt * 100), 1) if total_amt > 0 else 0,
        })

    return success_response(data=result)


# ============================================================================
# 3. 资金审批流程 (严格状态机校验)
# ============================================================================


def _transition_status(
    db: Session,
    fund: Fund,
    target_status: str,
    allowed_statuses: List[str],
    *,
    required_attachments: Optional[List[str]] = None,
    **kwargs,
):
    """内部辅助：状态流转核心逻辑。

    Args:
        required_attachments: 必需的附件类别列表（如 ["contract", "allocation_order"]）。
            传 None 表示不检查附件；传空列表 [] 表示至少需要一个附件（任意类别）。
    """
    if fund.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"状态流转非法：当前状态为 '{fund.status}'，不允许变更为 '{target_status}'"
        )

    # ── 文档强制上传检查 ──
    if required_attachments is not None:
        existing = db.query(FundAttachment).filter(
            FundAttachment.fund_id == fund.id
        ).all()
        existing_categories = {a.category for a in existing if a.category}

        if len(required_attachments) == 0:
            # 空列表 → 至少需要 1 个附件
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该操作需要至少上传一个附件文档",
                )
        else:
            missing = [c for c in required_attachments if c not in existing_categories]
            if missing:
                labels = {"contract": "合同", "allocation_order": "分配令",
                          "invoice": "发票", "receipt": "收据", "report": "报告"}
                missing_labels = [labels.get(m, m) for m in missing]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"缺少必需文档: {', '.join(missing_labels)}",
                )

    fund.status = target_status
    for k, v in kwargs.items():
        if hasattr(fund, k):
            setattr(fund, k, v)
        else:  # noqa: E501 —— 全部调用方仅传 Fund 已有字段（approved_by/allocation_date/start_date/end_date/audit_date），防御分支不可达
            logger.warning("_transition_status: skipping unknown field '%s' on Fund(id=%d)", k, fund.id)
    safe_commit(db)


@router.post("/{fund_id}/approve")
def approve_fund(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)
    _transition_status(db, fund, "approved", ["pending", "planned"],
                       required_attachments=[],  # 至少需要 1 个附件
                       approved_by=current_user.full_name or current_user.username,
                       approval_date=datetime.now(timezone.utc))
    return success_response(message="审批通过")


@router.post("/{fund_id}/reject")
def reject_fund(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)
    _transition_status(db, fund, "rejected", ["pending", "planned"],
                       approved_by=current_user.full_name or current_user.username)
    return success_response(message="审批驳回")


@router.post("/{fund_id}/allocate")
def allocate_fund(
    fund_id: int,
    milestone_id: Optional[int] = Query(None, description="关联里程碑ID（可选，传入则校验完成状态）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)

    # ── 里程碑-经费绑定检查 ──
    if milestone_id is not None:
        if not fund.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该经费未关联项目，无法绑定里程碑",
            )
        from app.models.project_milestone import ProjectMilestone
        milestone = db.query(ProjectMilestone).filter(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.project_id == fund.project_id,
        ).first()
        if not milestone:
            raise HTTPException(status_code=404, detail="里程碑不存在或不属于该项目")
        if milestone.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"里程碑未完成（当前状态: {milestone.status}），无法拨付经费",
            )

    _transition_status(db, fund, "allocated", ["approved"],
                       required_attachments=["contract", "allocation_order"],
                       allocation_date=datetime.now(timezone.utc))
    return success_response(message="经费已拨付")


@router.post("/{fund_id}/start-use")
def start_use_fund(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)
    _transition_status(db, fund, "in_use", ["allocated"],
                       start_date=datetime.now(timezone.utc))
    return success_response(message="经费已开始使用")


@router.post("/{fund_id}/complete")
def complete_fund(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)
    _transition_status(db, fund, "completed", ["in_use"],
                       end_date=datetime.now(timezone.utc))
    return success_response(message="经费使用完成")


@router.post("/{fund_id}/audit")
def audit_fund(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_manager_role(current_user)
    fund = _get_fund_or_404(db, fund_id, current_user)
    _transition_status(db, fund, "audited", ["completed"],
                       audit_date=datetime.now(timezone.utc))
    return success_response(message="经费审计完成")


# ============================================================================
# 4. 帮扶村资金统计 & 历史
# ============================================================================


@router.get("/supported-village/statistics/by-type")
def fund_stats_by_type(
    year_start: int = Query(None),
    year_end: int = Query(None),
    department: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(
        Fund.fund_type,
        func.count(Fund.id).label("count"),
        func.coalesce(func.sum(Fund.amount), 0).label("amount")
    ).group_by(Fund.fund_type)
    if year_start:
        stmt = stmt.where(Fund.year >= year_start)
    if year_end:
        stmt = stmt.where(Fund.year <= year_end)
    stmt = stmt.where(Fund.is_active == True)  # noqa: E712
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    rows = db.execute(stmt).all()
    type_labels = {"project": "项目经费", "operation": "运营经费", "education": "教育帮扶",
                   "infrastructure": "基础设施", "emergency": "应急经费", "other": "其他"}
    result = {}
    for r in rows:
        key = r.fund_type or "other"
        result[key] = {
            "fund_type": key,
            "fund_type_label": type_labels.get(key, key),
            "total_investment": float(r.amount),
            "count": r.count,
        }
    return success_response(data=result)


@router.get("/supported-village/statistics/yearly-comparison")
def fund_stats_yearly_comparison(
    year_start: int = Query(None),
    year_end: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(
        Fund.year,
        func.count(Fund.id).label("count"),
        func.coalesce(func.sum(Fund.amount), 0).label("amount"),
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("allocated"),
    ).group_by(Fund.year).order_by(Fund.year)
    if year_start:
        stmt = stmt.where(Fund.year >= year_start)
    if year_end:
        stmt = stmt.where(Fund.year <= year_end)
    stmt = stmt.where(Fund.is_active == True)  # noqa: E712
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    rows = db.execute(stmt).all()
    return success_response(data=[
        {"year": r.year or 0, "total_actual": float(r.amount),
         "total_planned": float(r.allocated), "count": r.count} for r in rows
    ])


@router.get("/supported-village/statistics/utilization-rate")
def fund_stats_utilization(
    year_start: int = Query(None),
    year_end: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("planned"),
        func.coalesce(func.sum(Fund.used_amount), 0).label("actual"),
    ).where(Fund.is_active == True)  # noqa: E712
    if year_start:
        stmt = stmt.where(Fund.year >= year_start)
    if year_end:
        stmt = stmt.where(Fund.year <= year_end)
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    row = db.execute(stmt).one()
    planned = float(row.planned)
    actual = float(row.actual)
    rate = round((actual / planned * 100), 1) if planned > 0 else 0
    return success_response(
        data={
            "overall_utilization_rate": rate,
            "total_actual_investment": actual,
            "total_planned_investment": planned,
        }
    )


@router.get("/supported-village/statistics/summary")
def fund_stats_summary(
    year_start: int = Query(None),
    year_end: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(
        func.count(Fund.id).label("total_count"),
        func.coalesce(func.sum(Fund.amount), 0).label("total_amount"),
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("total_allocated"),
        func.coalesce(func.sum(Fund.used_amount), 0).label("total_used"),
    ).where(Fund.is_active == True)  # noqa: E712
    if year_start:
        stmt = stmt.where(Fund.year >= year_start)
    if year_end:
        stmt = stmt.where(Fund.year <= year_end)
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    row = db.execute(stmt).one()
    return success_response(data={
        "total_count": row.total_count, "total_amount": float(row.total_amount),
        "total_allocated": float(row.total_allocated), "total_used": float(row.total_used),
    })


@router.get("/village/{village_id}/summary")
def village_fund_summary(
    village_id: int,
    year: int = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """帮扶村经费汇总：按年度统计该村所有经费的申请/批准/拨付/使用金额"""
    stmt = select(
        func.count(Fund.id).label("count"),
        func.coalesce(func.sum(Fund.planned_amount), 0).label("planned"),
        func.coalesce(func.sum(Fund.approved_amount), 0).label("approved"),
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("allocated"),
        func.coalesce(func.sum(Fund.used_amount), 0).label("used"),
    ).where(Fund.village_id == village_id, Fund.is_active == True)  # noqa: E712
    if year:
        stmt = stmt.where(Fund.year == year)
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    row = db.execute(stmt).one()
    return success_response(data={
        "village_id": village_id,
        "year": year,
        "fund_count": row.count,
        "planned_amount": float(row.planned),
        "approved_amount": float(row.approved),
        "allocated_amount": float(row.allocated),
        "used_amount": float(row.used),
        "remaining_amount": float(row.approved) - float(row.used),
    })


@router.get("/school/{school_id}/summary")
def school_fund_summary(
    school_id: int,
    year: int = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """帮扶学校经费汇总：按年度统计该校所有经费的申请/批准/拨付/使用金额"""
    stmt = select(
        func.count(Fund.id).label("count"),
        func.coalesce(func.sum(Fund.planned_amount), 0).label("planned"),
        func.coalesce(func.sum(Fund.approved_amount), 0).label("approved"),
        func.coalesce(func.sum(Fund.allocated_amount), 0).label("allocated"),
        func.coalesce(func.sum(Fund.used_amount), 0).label("used"),
    ).where(Fund.school_id == school_id, Fund.is_active == True)  # noqa: E712
    if year:
        stmt = stmt.where(Fund.year == year)
    stmt = apply_scope_filter(stmt, current_user, Fund, db=db)
    row = db.execute(stmt).one()
    return success_response(data={
        "school_id": school_id,
        "year": year,
        "fund_count": row.count,
        "planned_amount": float(row.planned),
        "approved_amount": float(row.approved),
        "allocated_amount": float(row.allocated),
        "used_amount": float(row.used),
        "remaining_amount": float(row.approved) - float(row.used),
    })


@router.get("/{fund_id}/history/status")
def fund_history_status(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取经费状态变更历史"""
    _get_fund_or_404(db, fund_id, current_user)
    rows = (
        db.query(FundStatusHistory)
        .filter(FundStatusHistory.fund_id == fund_id)
        .order_by(FundStatusHistory.operation_time.desc())
        .limit(100).all()
    )
    return success_response(data=[{
        "id": r.id, "from_status": r.from_status, "to_status": r.to_status,
        "operator_id": r.operator_id, "operator_name": r.operator_name,
        "operation_time": r.operation_time.isoformat() if r.operation_time else None,
        "remark": r.remark,
    } for r in rows])


@router.get("/{fund_id}/history/fields")
def fund_history_fields(fund_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取经费字段变更历史"""
    _get_fund_or_404(db, fund_id, current_user)
    from app.models.fund_history import FundFieldChange
    rows = (
        db.query(FundFieldChange)
        .filter(FundFieldChange.fund_id == fund_id)
        .order_by(FundFieldChange.changed_at.desc())
        .limit(100).all()
    )
    items = [{
        "id": r.id, "field_name": r.field_name, "old_value": r.old_value,
        "new_value": r.new_value, "changed_by": r.changed_by,
        "changed_at": r.changed_at.isoformat() if r.changed_at else None,
    } for r in rows]
    return ok_list(items, len(items))


@router.get("/{fund_id}/history/operations")
def fund_history_operations(
    fund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取经费操作日志"""
    _get_fund_or_404(db, fund_id, current_user)
    rows = (
        db.query(FundOperationLog)
        .filter(FundOperationLog.fund_id == fund_id)
        .order_by(FundOperationLog.created_at.desc())
        .limit(100).all()
    )
    items = [{
        "id": r.id, "operation": r.operation, "operator": r.operator,
        "detail": r.detail, "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
    return ok_list(items, len(items))


# ============================================================================
# 5. 附件管理 (静态路由放在动态 /{fund_id}/* 之前以提高匹配优先级)
# ============================================================================


@router.get("/attachments/{attachment_id}/download")
async def download_fund_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """下载经费附件"""
    att = db.query(FundAttachment).filter(FundAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    # 数据隔离：校验附件所属经费的访问权限（防止跨组织下载）
    _get_fund_or_404(db, att.fund_id, current_user)

    return get_attachment_response(
        file_path=att.file_path,
        filename=att.file_name,
        media_type=att.file_type or "application/octet-stream",
    )


@router.get("/attachments/{attachment_id}/preview")
async def preview_fund_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """预览经费附件（支持图片/PDF/文本等常见格式）"""
    att = db.query(FundAttachment).filter(FundAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    # 数据隔离：校验附件所属经费的访问权限（防止跨组织预览）
    _get_fund_or_404(db, att.fund_id, current_user)

    # 推断 MIME 类型以决定是否内联显示
    mime_type, _ = mimetypes.guess_type(att.file_path)
    if not mime_type:
        mime_type = att.file_type or "application/octet-stream"

    # 图片、PDF、文本等可内联预览的类型使用 inline 模式
    inline_types = (
        "image/", "application/pd", "text/",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    use_inline = any(mime_type.startswith(t) for t in inline_types)

    return get_attachment_response(
        file_path=att.file_path,
        filename=att.file_name,
        media_type=mime_type,
        inline=use_inline,
    )


@router.delete("/attachments/{attachment_id}")
async def delete_fund_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除经费附件

    自动记录 FundOperationLog + write_work_log
    """
    att = db.query(FundAttachment).filter(FundAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    # 数据隔离：校验附件所属经费的访问权限（防止跨组织删除）
    _get_fund_or_404(db, att.fund_id, current_user)

    fund_id = att.fund_id
    file_name = getattr(att, "file_name", "unknown")
    file_path = att.file_path

    # 删除数据库记录
    db.delete(att)

    # 记录操作日志
    op_log = FundOperationLog(
        fund_id=fund_id,
        operation_type="attachment_delete",
        operation_detail=f"删除附件: {file_name}",
        operator_id=current_user.id,
        operator_name=getattr(current_user, "full_name", None) or current_user.username,
    )
    db.add(op_log)
    safe_commit(db)

    # 删除磁盘文件（使用统一工具，放在 commit 之后）
    delete_attachment_file(file_path)

    write_work_log(
        db, "fund", "delete_attachment", fund_id, file_name,
        user_id=current_user.id, username=getattr(current_user, "username", "系统"),
    )
    return success_response(message="删除成功")


@router.get("/{fund_id}/attachments")
async def list_fund_attachments(
    fund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取经费附件列表"""
    _get_fund_or_404(db, fund_id, current_user)

    attachments = (
        db.query(FundAttachment)
        .filter(FundAttachment.fund_id == fund_id)
        .order_by(FundAttachment.created_at.desc())
        .all()
    )
    items = [a.to_dict() for a in attachments]
    return ok_list(items, len(items))


@router.post("/{fund_id}/attachments")
async def upload_fund_attachment(
    fund_id: int,
    file: UploadFile = File(...),
    category: Optional[str] = "other",
    description: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传经费附件"""
    _get_fund_or_404(db, fund_id, current_user)

    # 使用统一上传工具
    file_info = await save_upload_file(
        file=file,
        sub_dir=f"funds/{fund_id}",
    )

    # 保存数据库记录
    uploaded_by = getattr(current_user, "full_name", None) or current_user.username
    attachment = FundAttachment(
        fund_id=fund_id,
        file_name=file_info["file_name"],
        file_path=file_info["file_path"],
        file_size=file_info["file_size"],
        file_type=file_info["file_type"],
        category=category or "other",
        description=description or "",
        uploaded_by=uploaded_by,
    )
    db.add(attachment)

    # 记录操作日志
    op_log = FundOperationLog(
        fund_id=fund_id,
        operation_type="attachment_upload",
        operation_detail=f"上传附件: {file_info['file_name']} (分类: {category or 'other'})",
        operator_id=current_user.id,
        operator_name=uploaded_by,
    )
    db.add(op_log)

    safe_commit(db)
    db.refresh(attachment)

    write_work_log(
        db, "fund", "upload_attachment", fund_id,
        file_info["file_name"],
        user_id=current_user.id, username=getattr(current_user, "username", "系统"),
        detail=f"分类: {category or 'other'}",
    )
    return success_response(data=attachment.to_dict(), message="上传成功")
