"""工作日志 API"""

import logging
from datetime import date, datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.models.work_log import WorkLog
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/work-logs", tags=["工作日志"])

# R28-M10：system_auto 是**保留分类**——服务端自动留痕用它，客户端不得写入
# （否则可伪造全局可见且不可删除的记录，见 deliverables/ocr-triage-2026-09-30 part-B #4）。
AUTO_CATEGORY = "system_auto"
# 客户端可写入的分类白名单（create/update 校验用）
_CLIENT_CATEGORIES = {
    "visit", "meeting", "inspection", "training", "daily", "checkin",
    "project", "village", "school", "other",
}


def _apply_work_log_scope(query, current_user):
    """工作日志可见性收敛（R28-M10）。

    原实现：非管理员可见「自己的日志 + **所有人的** system_auto 自动留痕」——
    自动留痕由 write_work_log 写入并携带 user_id，因此等价于向所有用户
    暴露他人操作流水（内容形如 "create: xxx | by <他人用户名>"）。
    收敛口径：管理员看全量；非管理员只看**本人**日志（含本人触发的自动留痕）。
    """
    from app.core.permission_utils import is_admin

    if is_admin(current_user):
        return query
    return query.filter(WorkLog.user_id == getattr(current_user, "id", None))


class WorkLogCreate(BaseModel):
    # 兼容前端字段：title/work_date/log_type
    title: Optional[str] = Field(None, max_length=200)
    work_date: Optional[date] = None
    log_type: Optional[str] = Field(None, max_length=50)

    # 标准字段
    log_date: Optional[date] = None
    content: Optional[str] = None  # 移除 min_length=1，在业务逻辑中验证
    project_id: Optional[int] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    category: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=200)
    participants: Optional[str] = None


class WorkLogUpdate(BaseModel):
    # 兼容前端字段
    title: Optional[str] = Field(None, max_length=200)
    work_date: Optional[date] = None
    log_type: Optional[str] = Field(None, max_length=50)

    # 标准字段
    log_date: Optional[date] = None
    content: Optional[str] = None
    project_id: Optional[int] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    category: Optional[str] = None
    location: Optional[str] = None
    participants: Optional[str] = None


class WorkLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    log_date: date
    content: str
    # 兼容前端字段
    title: Optional[str] = None
    work_date: Optional[str] = None
    log_type: Optional[str] = None
    # 标准字段
    project_id: Optional[int] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    category: Optional[str] = None
    location: Optional[str] = None
    participants: Optional[str] = None
    created_at: Optional[datetime] = None
    is_auto: bool = False  # 是否为自动记录
    model_config = ConfigDict(from_attributes=True)


@router.get("")
async def get_work_logs(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    project_id: Optional[int] = None,
    village_id: Optional[int] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    log_type: Optional[str] = None,
    source: Optional[str] = Query(None, description="日志来源: auto=自动记录, manual=手动记录, all=全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取工作日志列表"""
    query = db.query(WorkLog)

    # R28-M10：非管理员只看本人日志（原实现额外放行「所有人的自动留痕」→
    # 他人操作流水对所有登录用户可见）。
    query = _apply_work_log_scope(query, current_user)

    if start_date:
        query = query.filter(WorkLog.log_date >= start_date)
    if end_date:
        query = query.filter(WorkLog.log_date <= end_date)
    if project_id:
        query = query.filter(WorkLog.project_id == project_id)
    if village_id:
        query = query.filter(WorkLog.village_id == village_id)
    if category:
        query = query.filter(WorkLog.category == category)
    if log_type:  # 兼容前端 log_type 参数
        query = query.filter(WorkLog.category == log_type)
    if keyword:
        query = query.filter(WorkLog.content.contains(keyword))

    # 日志来源筛选
    if source == "auto":
        query = query.filter(WorkLog.category == "system_auto")
    elif source == "manual":
        query = query.filter(WorkLog.category != "system_auto")

    # 自动记录优先显示
    from sqlalchemy import case

    # count() 必须在 order_by 之前执行，否则 order_by 会影响结果
    total = query.count()
    items = (
        query.order_by(
            case((WorkLog.category == "system_auto", 0), else_=1),
            WorkLog.log_date.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 转换为兼容格式
    result_items = []
    work_log_columns = [c.key for c in inspect(WorkLog).columns]
    for log in items:
        # 只保留数据库列，过滤 SQLAlchemy 内部属性
        log_dict = {k: getattr(log, k) for k in work_log_columns}
        # 使用 model_construct 避免 pydantic 2.6+ 的严格验证
        item = WorkLogResponse.model_construct(
            **log_dict,
            work_date=log.log_date.isoformat(),
            title=log.content[:100] if log.content else "",
            log_type=log.category or "daily"
        )
        # 添加 is_auto 字段供前端区分
        result_items.append({**item.__dict__, "is_auto": log.category == "system_auto"})

    return ok_list(items=result_items, total=total, page=page, page_size=page_size)


@router.post("", response_model=WorkLogResponse)
async def create_work_log(
    data: WorkLogCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建工作日志"""
    # 字段兼容处理
    log_data = data.model_dump(exclude_unset=True)

    # work_date -> log_date
    if "work_date" in log_data and not log_data.get("log_date"):
        log_data["log_date"] = log_data.pop("work_date")
    elif "work_date" in log_data:
        log_data.pop("work_date")

    # title -> content（如果 content 为空）
    if "title" in log_data and not log_data.get("content"):
        log_data["content"] = log_data.pop("title")
    elif "title" in log_data:
        log_data.pop("title")

    # log_type -> category
    if "log_type" in log_data and not log_data.get("category"):
        log_data["category"] = log_data.pop("log_type")
    elif "log_type" in log_data:
        log_data.pop("log_type")

    # 验证必填字段
    if not log_data.get("log_date"):
        raise HTTPException(status_code=422, detail="工作日期不能为空")
    content = log_data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="工作内容不能为空")
    log_data["content"] = content  # 使用去除空格后的内容

    # 将字符串日期转换为 Python date 对象（SQLite Date 列要求）
    from datetime import date as dt_date
    raw_date = log_data.get("log_date")
    if isinstance(raw_date, str):
        log_data["log_date"] = dt_date.fromisoformat(raw_date)
    elif not isinstance(raw_date, dt_date):
        raise HTTPException(status_code=422, detail="工作日期格式无效")

    # 驻村打卡去重：同一用户同一天仅允许一条 checkin 记录
    if log_data.get("category") == "checkin":
        exists = (
            db.query(WorkLog)
            .filter(
                WorkLog.user_id == current_user.id,
                WorkLog.category == "checkin",
                WorkLog.log_date == log_data["log_date"],
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="今天已完成驻村打卡")

    # R28-M10 附带收口：system_auto 是服务端保留分类，客户端不得写入
    # （原实现允许任意用户创建 category="system_auto" 的记录：该分类在
    # 可见性逻辑里被特殊放行且删除接口固定拒绝删除 → 可造出全局可见、
    # 不可清理的伪造留痕）。
    if log_data.get("category") == AUTO_CATEGORY:
        raise HTTPException(status_code=400, detail="system_auto 为系统保留分类，不允许手工写入")

    log = WorkLog(user_id=current_user.id, **log_data)
    db.add(log)
    safe_commit(db)
    db.refresh(log)

    # 返回时添加兼容字段
    result = WorkLogResponse.model_construct(
        **log.__dict__,
        work_date=log.log_date.isoformat(),
        title=log.content[:100] if log.content else "",
        log_type=log.category or "daily"
    )
    return result


@router.put("/{log_id}", response_model=WorkLogResponse)
async def update_work_log(
    log_id: int,
    data: WorkLogUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新工作日志"""
    log = db.query(WorkLog).filter(WorkLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    if log.user_id != current_user.id and getattr(current_user, "role", "") not in (
        "admin",
        "super_admin",
    ):
        raise HTTPException(status_code=403, detail="只能编辑自己的日志")

    # 字段兼容处理
    update_data = data.model_dump(exclude_unset=True)

    # work_date -> log_date
    if "work_date" in update_data:
        if not update_data.get("log_date"):
            update_data["log_date"] = update_data["work_date"]
        update_data.pop("work_date")

    # title -> content
    if "title" in update_data:
        if not update_data.get("content"):
            update_data["content"] = update_data["title"]
        update_data.pop("title")

    # log_type -> category
    if "log_type" in update_data:
        if not update_data.get("category"):
            update_data["category"] = update_data["log_type"]
        update_data.pop("log_type")

    # R28-M10 附带收口：不得把已有日志改写为系统保留分类（同上）
    if update_data.get("category") == AUTO_CATEGORY:
        raise HTTPException(status_code=400, detail="system_auto 为系统保留分类，不允许手工写入")

    for key, value in update_data.items():
        setattr(log, key, value)
    safe_commit(db)
    db.refresh(log)

    # 返回时添加兼容字段
    result = WorkLogResponse.model_construct(
        **log.__dict__,
        work_date=log.log_date.isoformat(),
        title=log.content[:100] if log.content else "",
        log_type=log.category or "daily"
    )
    return result


@router.delete("/{log_id}")
async def delete_work_log(
    log_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除工作日志"""
    log = db.query(WorkLog).filter(WorkLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    # 自动日志不允许删除
    if log.category == "system_auto":
        raise HTTPException(status_code=403, detail="自动记录不支持删除")
    if log.user_id != current_user.id and getattr(current_user, "role", "") not in (
        "admin",
        "super_admin",
    ):
        raise HTTPException(status_code=403, detail="只能删除自己的日志")

    db.delete(log)
    safe_commit(db)
    return success_response(message="删除成功")


@router.get("/calendar")
async def get_calendar_events(
    year: int = Query(..., ge=2000, le=2099),
    month: int = Query(..., ge=1, le=12),
    source: Optional[str] = Query(None, description="日志来源: auto=自动记录, manual=手动记录"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取日历视图数据（按月）"""
    import calendar

    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    query = db.query(WorkLog).filter(WorkLog.log_date >= start, WorkLog.log_date <= end)

    # R28-M10：非管理员只看本人日志（同列表端点口径）
    query = _apply_work_log_scope(query, current_user)

    # 日志来源筛选
    if source == "auto":
        query = query.filter(WorkLog.category == "system_auto")
    elif source == "manual":
        query = query.filter(WorkLog.category != "system_auto")

    logs = query.order_by(WorkLog.log_date).all()

    # 转换为前端期望的格式
    items = []
    for log in logs:
        items.append(
            {
                "id": log.id,
                "title": log.content[:100] if log.content else "",
                "content": log.content,
                "work_date": log.log_date.isoformat(),
                "log_date": log.log_date.isoformat(),
                "log_type": log.category or "daily",
                "category": log.category,
                "is_auto": log.category == "system_auto",
                "location": log.location,
                "participants": log.participants,
                "project_id": log.project_id,
                "village_id": log.village_id,
                "school_id": log.school_id,
            }
        )

    return ok_list(items, len(items), year=year, month=month)


@router.get("/monthly-summary", summary="驻村工作月度总结")
async def work_log_monthly_summary(
    year: int = Query(..., ge=2000, le=2099),
    month: int = Query(..., ge=1, le=12),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """聚合当月工作日志生成月度总结：总条数/打卡天数/分类统计/内容列表"""
    import calendar

    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    query = db.query(WorkLog).filter(WorkLog.log_date >= start, WorkLog.log_date <= end)
    # R28-M10：非管理员只看本人日志（同列表端点口径）
    query = _apply_work_log_scope(query, current_user)

    logs = query.order_by(WorkLog.log_date).all()

    category_counts: Dict[str, int] = {}
    checkin_days: set = set()
    items = []
    for log in logs:
        cat = log.category or "daily"
        category_counts[cat] = category_counts.get(cat, 0) + 1
        if cat == "checkin":
            checkin_days.add(log.log_date.isoformat())
        items.append(
            {
                "work_date": log.log_date.isoformat(),
                "content": log.content,
                "category": cat,
                "location": log.location,
            }
        )

    summary_text = (
        f"{year}年{month}月驻村工作总结："
        f"共记录工作 {len(logs)} 项，驻村打卡 {len(checkin_days)} 天"
        + (f"，其中 {category_counts.get('checkin', 0)} 次打卡。" if category_counts.get('checkin') else "。")
    )

    return success_response(
        data={
            "year": year,
            "month": month,
            "total_logs": len(logs),
            "checkin_days": len(checkin_days),
            "category_counts": category_counts,
            "items": items,
            "summary_text": summary_text,
        },
        message="月度总结已生成",
    )
