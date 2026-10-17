"""统一提醒中心 API（单机：审批超时/项目截止/预算预警/备份/打包提醒聚合 + 处置闭环）

处置闭环（.scratch/w17-feature-completion/001）：
`POST /reminders/{id}/handle|ignore|snooze|reopen`——仅提醒接收人本人可操作，
越权/不存在一律 404（fail-closed），处置写工作日志留痕。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db, require_manager_role
from app.core.response import success_response
from app.core.security import get_current_user
from app.services.reminder_disposition_service import (
    InvalidSnoozeDaysError,
    ReminderNotFoundError,
    handle as _handle,
    ignore as _ignore,
    reopen as _reopen,
    snooze as _snooze,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reminders", tags=["reminders"])

_EMPTY_STATS = {"pending": 0, "handled": 0, "ignored": 0, "snoozed": 0, "total": 0}


class ReminderNoteBody(BaseModel):
    """处理/忽略/重新打开的说明（选填）。"""

    note: str = Field(default="", max_length=500)


class ReminderSnoozeBody(BaseModel):
    """延期天数（默认 7 天）。"""

    days: int = Field(default=7, ge=1, le=90)


@router.get("", summary="获取提醒列表（聚合视图 + 处置状态）")
async def list_reminders(
    include_ignored: bool = Query(False, description="是否包含已忽略的提醒"),
    current_user=Depends(get_current_user),
):
    """提醒中心：审批超时/项目截止/预算预警等（未处理优先，其次时间倒序）"""
    try:
        from app.services.reminder_orchestrator import list_reminders as _list
        from app.services.reminder_orchestrator import summarize_reminders

        reminders = _list(
            limit=100,
            user_id=getattr(current_user, "id", None),
            include_ignored=include_ignored,
        )
        unread = sum(1 for r in reminders if not r.get("is_read"))
        return success_response(
            data={
                "items": reminders,
                "total": len(reminders),
                "unread": unread,
                "stats": summarize_reminders(reminders),
            }
        )
    except Exception as e:
        logger.error("获取提醒失败: %s", e, exc_info=True)
        return success_response(
            data={"items": [], "total": 0, "unread": 0, "stats": dict(_EMPTY_STATS)},
            message="获取提醒失败",
        )


@router.post("/scan", summary="手动触发一次提醒扫描")
async def trigger_scan(
    current_user=Depends(get_current_user),
):
    """立即执行一次提醒扫描（审批超时/项目截止/预算预警）——仅管理员"""
    require_manager_role(current_user)
    try:
        from app.services.reminder_orchestrator import run_reminder_scans

        created = run_reminder_scans()
        return success_response(data={"created": len(created)}, message=f"扫描完成，新增 {len(created)} 条提醒")
    except Exception as e:
        logger.error("手动提醒扫描失败: %s", e, exc_info=True)
        return success_response(data={"created": 0}, message="扫描失败")


def _run_disposition(
    db: Session,
    current_user,
    message_id: int,
    action_fn,
    success_message: str,
    **kwargs,
):
    """统一兜底：404（不存在/越权）/ 400（参数非法）/ 500（未知异常，泛化文案）。"""
    try:
        data = action_fn(
            db,
            message_id,
            getattr(current_user, "id", None),
            username=getattr(current_user, "username", "") or "",
            **kwargs,
        )
        return success_response(data=data, message=success_message)
    except ReminderNotFoundError:
        raise HTTPException(status_code=404, detail="提醒不存在或无权操作")
    except InvalidSnoozeDaysError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("提醒处置失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")


@router.post("/{message_id}/handle", summary="标记提醒已处理")
async def handle_reminder(
    message_id: int,
    body: Optional[ReminderNoteBody] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _run_disposition(
        db, current_user, message_id, _handle, "已标记处理",
        note=body.note if body else "",
    )


@router.post("/{message_id}/ignore", summary="忽略提醒（可填原因）")
async def ignore_reminder(
    message_id: int,
    body: Optional[ReminderNoteBody] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _run_disposition(
        db, current_user, message_id, _ignore, "已忽略该提醒",
        reason=body.note if body else "",
    )


@router.post("/{message_id}/snooze", summary="延期提醒（天）")
async def snooze_reminder(
    message_id: int,
    body: Optional[ReminderSnoozeBody] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    days = body.days if body else 7
    return _run_disposition(
        db, current_user, message_id, _snooze, f"已延期 {days} 天",
        days=days,
    )


@router.post("/{message_id}/reopen", summary="重新打开提醒")
async def reopen_reminder(
    message_id: int,
    body: Optional[ReminderNoteBody] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _run_disposition(
        db, current_user, message_id, _reopen, "已重新打开",
        note=body.note if body else "",
    )
