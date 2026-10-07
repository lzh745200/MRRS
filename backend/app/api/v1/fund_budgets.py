"""经费预算与使用明细 API"""

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func as sa_func
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

import json as _json
import os

from app.core.config import settings
from app.core.database import get_db
from app.core.data_permission import apply_data_scope
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.models.fund import Fund
from app.models.fund_budget import FundBudget, FundTransaction, check_budget_alerts
from app.core.money import MoneyField
from app.api.v1.deps import require_funds_operator_role as _require_manager
from app.core.transaction import safe_commit
from app.services.data_scope_query import scoped_filter  # B1 下沉：服务层统一数据域入口
from app.services.work_log_service import write_work_log
from app.utils.helpers import BUDGET_MONEY_FIELDS, quantize_money, quantize_money_fields

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fund-budgets", tags=["经费预算"])

# ==================== Pydantic 模型 ====================


class BudgetCreate(BaseModel):
    year: int = Field(..., ge=2000, le=2099)
    category: str = Field(..., min_length=1, max_length=100)
    budget_amount: float = Field(..., ge=0)
    used_amount: Optional[float] = Field(None, ge=0, description="已使用金额（前端字段，映射到 executed_amount）")
    village_id: Optional[int] = None
    organization_id: Optional[int] = None
    description: Optional[str] = None
    remarks: Optional[str] = None


class BudgetUpdate(BaseModel):
    budget_amount: Optional[float] = Field(None, ge=0)
    executed_amount: Optional[float] = Field(None, ge=0)
    used_amount: Optional[float] = Field(None, ge=0, description="前端兼容字段，等价 executed_amount")
    description: Optional[str] = None
    remarks: Optional[str] = None


class BudgetResponse(BaseModel):
    id: int
    year: int
    category: str
    budget_amount: float
    executed_amount: float
    remaining_amount: float = 0
    execution_rate: float = 0
    village_id: Optional[int] = None
    organization_id: Optional[int] = None
    description: Optional[str] = None
    remarks: Optional[str] = None
    # 附件单独出参（remarks 列内保留键存储，见 _decode_remarks）
    attachments: Optional[List[dict]] = None
    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    fund_id: Optional[int] = None
    project_id: Optional[int] = None
    village_id: Optional[int] = None
    budget_id: Optional[int] = None
    amount: MoneyField = Field(..., gt=0)
    category: Optional[str] = None
    purpose: str = Field(..., min_length=1, description="用途说明")
    transaction_date: date
    receipt_number: Optional[str] = None
    receipt_attachment: Optional[str] = None
    handler: Optional[str] = None
    reimbursement_person: Optional[str] = None
    remarks: Optional[str] = None

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        """验证并清理用途说明"""
        if v:
            v = v.strip()
            if not v:
                raise ValueError("用途说明不能为空或仅包含空格")
        return v


class TransactionResponse(BaseModel):
    id: int
    fund_id: Optional[int] = None
    project_id: Optional[int] = None
    village_id: Optional[int] = None
    budget_id: Optional[int] = None
    amount: MoneyField
    category: Optional[str] = None
    purpose: str
    transaction_date: date
    receipt_number: Optional[str] = None
    handler: Optional[str] = None
    reimbursement_person: Optional[str] = None
    status: str
    remarks: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ==================== 数据域守卫 ====================


def _get_budget_or_404(db: Session, budget_id: int, current_user) -> FundBudget:
    """按数据域取预算；不可见即 404（不泄露记录是否存在）。

    深审 LIVE：update/delete/附件端点此前只做 _require_manager（角色）校验，
    再按裸 id 取记录 → 任意管理角色可改删他组织预算并解析其附件清单。
    """
    budget = scoped_filter(
        db.query(FundBudget).filter(FundBudget.id == budget_id), FundBudget, current_user
    ).first()
    if not budget:
        raise HTTPException(status_code=404, detail="预算不存在")
    return budget


def _get_transaction_or_404(db: Session, transaction_id: int, current_user) -> FundTransaction:
    """按数据域取使用明细；不可见即 404（同预算守卫，深审 LIVE）。"""
    tx = scoped_filter(
        db.query(FundTransaction).filter(FundTransaction.id == transaction_id),
        FundTransaction,
        current_user,
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="明细不存在")
    return tx


def _budget_to_response(budget) -> dict:
    """预算响应体：备注只出用户文本，附件单独出列表。"""
    data = budget.to_dict()
    data["remaining_amount"] = budget.remaining_amount
    data["execution_rate"] = budget.execution_rate
    decoded = _decode_remarks(getattr(budget, "remarks", None))
    data["remarks"] = decoded["text"]
    data["attachments"] = decoded["attachments"]
    return data


# ==================== 预算 API ====================


@router.get("")
async def get_budgets(
    year: Optional[int] = None,
    category: Optional[str] = None,
    village_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取预算列表"""
    query = db.query(FundBudget)
    query = apply_data_scope(query, FundBudget, current_user)
    if year:
        query = query.filter(FundBudget.year == year)
    if category:
        query = query.filter(FundBudget.category == category)
    if village_id:
        query = query.filter(FundBudget.village_id == village_id)

    budgets = query.order_by(FundBudget.year.desc(), FundBudget.category).all()

    result = []
    for b in budgets:
        data = _budget_to_response(b)
        data["used_amount"] = float(b.executed_amount or 0)
        data["budget"] = float(b.budget_amount or 0)
        data["used"] = float(b.executed_amount or 0)
        result.append(data)
    return ok_list(items=result, total=len(result))


@router.post("", response_model=BudgetResponse)
async def create_budget(
    data: BudgetCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建预算（仅管理角色）"""
    _require_manager(current_user)
    payload = data.model_dump()
    # used_amount（前端字段）映射到 executed_amount
    # pop 带默认值：等价兼容「键缺失」与「键存在但为 None」两种形态
    used = payload.pop("used_amount", None)
    if used is not None:
        payload["executed_amount"] = used
    quantize_money_fields(payload, BUDGET_MONEY_FIELDS)
    budget = FundBudget(
        **payload,
        created_by=getattr(current_user, "id", None),
    )
    db.add(budget)
    safe_commit(db)
    db.refresh(budget)

    return _budget_to_response(budget)


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: int,
    data: BudgetUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新预算（仅管理角色）"""
    _require_manager(current_user)
    budget = _get_budget_or_404(db, budget_id, current_user)

    update_data = data.model_dump(exclude_unset=True)
    # used_amount（前端字段）映射到 executed_amount
    if "used_amount" in update_data:
        used = update_data.pop("used_amount")
        if used is not None:
            update_data["executed_amount"] = used
    quantize_money_fields(update_data, BUDGET_MONEY_FIELDS)

    # 备注与附件分离：PUT 只改用户备注文本，绝不摧毁已有附件清单（深审 LIVE）
    if "remarks" in update_data:
        update_data["remarks"] = _encode_remarks(
            update_data["remarks"], _get_attachments(budget)
        )

    for key, value in update_data.items():
        setattr(budget, key, value)
    safe_commit(db)
    db.refresh(budget)

    return _budget_to_response(budget)


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除预算（仅管理角色）"""
    _require_manager(current_user)
    budget = _get_budget_or_404(db, budget_id, current_user)
    db.delete(budget)
    safe_commit(db)
    return success_response(message="删除成功")


# ==================== 预算预警 ====================


@router.get("/alerts")
async def get_budget_alerts(
    year: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取预算预警信息（首页仪表板用）"""
    query = db.query(FundBudget)
    query = apply_data_scope(query, FundBudget, current_user)
    if year:
        query = query.filter(FundBudget.year == year)
    else:
        # 默认当前年度
        query = query.filter(FundBudget.year == date.today().year)

    budgets = query.all()
    alerts = check_budget_alerts(budgets)
    return ok_list(items=alerts, total=len(alerts))


# ==================== 预算汇总 ====================


@router.get("/summary")
async def get_budget_summary(
    year: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取预算汇总统计"""
    target_year = year or date.today().year
    query = db.query(FundBudget).filter(FundBudget.year == target_year)
    query = apply_data_scope(query, FundBudget, current_user)
    budgets = query.all()

    total_budget = sum(float(b.budget_amount or 0) for b in budgets)
    total_executed = sum(float(b.executed_amount or 0) for b in budgets)

    # 按科目汇总
    by_category = {}
    for b in budgets:
        cat = b.category or "其他"
        if cat not in by_category:
            by_category[cat] = {"budget": 0, "executed": 0}
        by_category[cat]["budget"] += float(b.budget_amount or 0)
        by_category[cat]["executed"] += float(b.executed_amount or 0)

    return success_response(data={
        "year": target_year,
        "total_budget": round(total_budget, 4),
        "total_executed": round(total_executed, 4),
        "total_remaining": round(total_budget - total_executed, 4),
        "execution_rate": (round(total_executed / total_budget * 100, 2) if total_budget > 0 else 0),
        "by_category": [
            {
                "category": cat,
                "budget": round(v["budget"], 4),
                "executed": round(v["executed"], 4),
                "remaining": round(v["budget"] - v["executed"], 4),
                "rate": (round(v["executed"] / v["budget"] * 100, 2) if v["budget"] > 0 else 0),
            }
            for cat, v in by_category.items()
        ],
    })


# ==================== 使用明细 API ====================


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    fund_id: Optional[int] = None,
    project_id: Optional[int] = None,
    village_id: Optional[int] = None,
    budget_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取经费使用明细列表"""
    query = db.query(FundTransaction)
    query = apply_data_scope(query, FundTransaction, current_user)
    if fund_id:
        query = query.filter(FundTransaction.fund_id == fund_id)
    if project_id:
        query = query.filter(FundTransaction.project_id == project_id)
    if village_id:
        query = query.filter(FundTransaction.village_id == village_id)
    if budget_id:
        query = query.filter(FundTransaction.budget_id == budget_id)

    items = (
        query.order_by(FundTransaction.transaction_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return items


@router.post("/transactions", response_model=TransactionResponse)
async def create_transaction(
    data: TransactionCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建经费使用明细（仅管理角色）"""
    _require_manager(current_user)
    tx_amount = quantize_money(data.amount)
    payload = data.model_dump()
    payload["amount"] = tx_amount
    transaction = FundTransaction(
        **payload,
        created_by=getattr(current_user, "id", None),
    )
    db.add(transaction)

    # 如果关联了预算，自动更新已执行金额；执行率达 100% 后禁止再写入（ADR-0009 三级预警）
    if data.budget_id:
        budget = db.query(FundBudget).filter(FundBudget.id == data.budget_id).first()
        if budget:
            _apply_budget_execution(db, budget, float(tx_amount))

    # 如果关联了 Fund，自动更新 Fund.used_amount 和 remaining_amount
    if data.fund_id:
        fund = db.query(Fund).filter(Fund.id == data.fund_id).first()
        if fund:
            fund.used_amount = quantize_money(
                float(fund.used_amount or 0) + float(tx_amount)
            )
            fund.remaining_amount = quantize_money(
                float(fund.allocated_amount or 0) - float(fund.used_amount or 0)
            )

    safe_commit(db)
    db.refresh(transaction)
    write_work_log(
        db, "fund_budget", "create_transaction", transaction.id,
        f"支出明细: {data.purpose}",
        user_id=current_user.id,
        username=getattr(current_user, "full_name", None) or getattr(current_user, "username", ""),
        detail=f"金额: {data.amount} 万元",
    )
    return transaction


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除经费使用明细（仅管理角色）"""
    _require_manager(current_user)
    tx = _get_transaction_or_404(db, transaction_id, current_user)

    # 如果关联了预算，减回已执行金额
    if tx.budget_id:
        budget = db.query(FundBudget).filter(FundBudget.id == tx.budget_id).first()
        if budget:
            budget.executed_amount = max(0, float(budget.executed_amount or 0) - float(tx.amount or 0))

    # 如果关联了 Fund，减回 Fund.used_amount
    if tx.fund_id:
        fund = db.query(Fund).filter(Fund.id == tx.fund_id).first()
        if fund:
            fund.used_amount = max(0, float(fund.used_amount or 0) - float(tx.amount or 0))
            fund.remaining_amount = float(fund.allocated_amount or 0) - float(fund.used_amount or 0)

    db.delete(tx)
    safe_commit(db)
    return success_response(message="删除成功")


# ==================== 预算附件上报 ====================


@router.post("/{budget_id}/attachments", summary="上传预算附件（凭证/资料）")
async def upload_budget_attachment(
    budget_id: int,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传预算相关的附件资料（批复文件/凭证/执行资料等）"""
    _require_manager(current_user)
    budget = _get_budget_or_404(db, budget_id, current_user)

    from app.utils.upload_helper import save_upload_file

    file_info = await save_upload_file(
        file=file,
        sub_dir=f"fund-budgets/{budget_id}",
    )
    base_upload = os.path.abspath(settings.UPLOAD_DIR)
    rel_path = os.path.relpath(file_info["file_path"], base_upload).replace("\\", "/")
    url = f"/uploads/{rel_path}"

    # 记录到预算备注（保留上传轨迹）
    _record_attachment(budget, url, file_info["file_name"], current_user, db)

    return {
        "success": True,
        "data": {
            "url": url,
            "file_name": file_info["file_name"],
            "file_size": file_info["file_size"],
        },
        "message": "附件上传成功",
    }


@router.get("/{budget_id}/attachments", summary="获取预算附件列表")
async def list_budget_attachments(
    budget_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取预算上传的附件记录列表"""
    _require_manager(current_user)
    budget = _get_budget_or_404(db, budget_id, current_user)
    attachments = _get_attachments(budget)
    return ok_list(items=attachments, total=len(attachments))


def _apply_budget_execution(db: Session, budget, amount: float) -> None:
    """原子累加预算已执行金额；超过 100% 上限时 400。

    深审 LIVE：原实现是"先读 executed_amount → 内存里算 projected → 比较 → 赋值"，
    两个并发请求都能在各自读到旧值后通过检查并写回，100% 上限可被突破
    （条件竞争）。这里把"上限判断 + 累加"合并进同一条 UPDATE 的 WHERE 子句，
    由数据库对写事务串行化，读改写窗口消失。
    """
    budget_total = float(budget.budget_amount or 0)
    executed_col = sa_func.coalesce(FundBudget.executed_amount, 0)
    stmt = (
        sa_update(FundBudget)
        .where(FundBudget.id == budget.id)
        .values(executed_amount=executed_col + amount)
        # fetch：更新后按 WHERE 条件回查同步会话内实例，避免内存值过期
        # 造成后续读取到旧执行额
        .execution_options(synchronize_session="fetch")
    )
    if budget_total > 0:
        # 仅当累加后仍在 100% 上限内才命中行；命中 0 行即代表会突破上限
        stmt = stmt.where(executed_col + amount <= budget_total + 1e-9)

    result = db.execute(stmt)
    if result.rowcount == 0:
        projected = quantize_money(float(budget.executed_amount or 0) + amount)
        raise HTTPException(
            status_code=400,
            detail=f"预算执行将达 {projected}/{budget_total}（超 100%），禁止核销；请先调整预算",
        )


# 预算附件在 remarks 列内的保留键。历史缺陷（深审 LIVE）：附件列表整段 JSON 写进
# 用户可见的 remarks —— ① PUT 预算写普通文本备注即摧毁全部附件；
# ② 备注里的附件 JSON 会原样出现在前端"备注"框。
# FundBudget 无独立附件列（本期不改模型/迁移），故在同一列内做命名空间隔离，
# 并兼容读取历史"裸数组"形态，保证老数据不丢。
_BUDGET_ATTACHMENT_KEY = "__budget_attachments__"


def _filter_attachment_entries(value) -> list:
    """仅保留形如 {"url": ...} 的字典条目（脏数据/注入串一律丢弃）。"""
    if not isinstance(value, list):
        return []
    return [a for a in value if isinstance(a, dict) and "url" in a]


def _decode_remarks(raw) -> dict:
    """把 remarks 原文解码为 {"text": 用户备注文本|None, "attachments": [...]}。"""
    if not raw:
        return {"text": None, "attachments": []}
    try:
        parsed = _json.loads(raw)
    except (ValueError, TypeError):
        # 普通文本备注（最常见形态）
        return {"text": raw, "attachments": []}
    if isinstance(parsed, list):
        # 历史裸数组：整列都是附件记录，用户备注已被覆盖、不可恢复
        return {"text": None, "attachments": _filter_attachment_entries(parsed)}
    if isinstance(parsed, dict) and _BUDGET_ATTACHMENT_KEY in parsed:
        return {
            "text": parsed.get("text"),
            "attachments": _filter_attachment_entries(parsed.get(_BUDGET_ATTACHMENT_KEY)),
        }
    # 其它 JSON 形态（对象/字符串/数字）按普通文本处理
    return {"text": raw, "attachments": []}


def _encode_remarks(text, attachments: list) -> Optional[str]:
    """编码备注列：无附件时存纯文本，有附件时存保留键信封。"""
    if not attachments:
        return text
    return _json.dumps({_BUDGET_ATTACHMENT_KEY: attachments, "text": text}, ensure_ascii=False)


def _record_attachment(budget, url: str, file_name: str, current_user, db) -> None:
    """追加一条附件记录（不触碰用户备注文本）并落库"""
    decoded = _decode_remarks(getattr(budget, "remarks", None))
    attachments = decoded["attachments"]
    attachments.append(
        {
            "url": url,
            "file_name": file_name,
            "uploaded_by": getattr(current_user, "full_name", None) or getattr(current_user, "username", ""),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    budget.remarks = _encode_remarks(decoded["text"], attachments)
    safe_commit(db)


def _get_attachments(budget) -> list:
    """解析预算附件记录（兼容历史裸数组与新的保留键信封）"""
    return _decode_remarks(getattr(budget, "remarks", None))["attachments"]
