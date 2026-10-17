"""提醒处置服务（提醒中心处置闭环）。

处理 / 忽略（含理由）/ 延期 / 重新打开；全部动作：
- 仅提醒**接收人本人**可操作（越权与不存在一律 404，不泄露存在性）；
- 处置落 `reminder_dispositions`（每人每条提醒一行，重复操作幂等更新）；
- 处置即视为已读（`messages.is_read/read_at`）；
- 写工作日志留痕（失败只记日志，不阻断处置主流程）。
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.transaction import safe_commit
from app.models.message import Message
from app.models.reminder_disposition import ReminderDisposition
from app.services.reminder_types import is_reminder_type
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

STATE_OPEN = "open"
STATE_HANDLED = "handled"
STATE_IGNORED = "ignored"

SNOOZE_MIN_DAYS = 1
SNOOZE_MAX_DAYS = 90


class ReminderNotFoundError(Exception):
    """提醒不存在、不属于当前用户或不是提醒类消息（对外统一 404）。"""


class InvalidSnoozeDaysError(ValueError):
    """延期天数超出允许范围（对外统一 400）。"""


def load_owned_reminder(db: Session, message_id: int, user_id: Optional[int]) -> Message:
    """加载本人提醒；任何缺失/越权/类型不符均抛 ReminderNotFoundError。

    fail-closed：`user_id` 为空直接拒绝；消息接收人为 NULL（用户已删除的
    历史消息）同样拒绝 —— 绝不允许"无主消息"被任意登录用户处置。
    """
    if not user_id:
        raise ReminderNotFoundError()
    msg = db.query(Message).filter(Message.id == message_id).first()
    if msg is None or msg.user_id != user_id:
        raise ReminderNotFoundError()
    if not is_reminder_type(msg.message_type):
        raise ReminderNotFoundError()
    return msg


def serialize_disposition(row: Optional[ReminderDisposition]) -> Dict[str, Any]:
    """序列化处置状态；无行时返回 open 默认值。"""
    if row is None:
        return {"state": STATE_OPEN, "note": None, "snooze_until": None, "acted_at": None}
    return {
        "state": row.state or STATE_OPEN,
        "note": row.note,
        "snooze_until": row.snooze_until.isoformat() if row.snooze_until else None,
        "acted_at": row.acted_at.isoformat() if row.acted_at else None,
    }


def load_dispositions(
    db: Session, message_ids: Iterable[int], user_id: Optional[int]
) -> Dict[int, ReminderDisposition]:
    """批量加载本人处置行（列表富化用）；无 id 或缺 user_id 时返回空映射。"""
    ids = [i for i in message_ids if i is not None]
    if not ids or not user_id:
        return {}
    rows = (
        db.query(ReminderDisposition)
        .filter(
            ReminderDisposition.message_id.in_(ids),
            ReminderDisposition.user_id == user_id,
        )
        .all()
    )
    return {row.message_id: row for row in rows}


def _upsert(db: Session, msg: Message, user_id: int) -> ReminderDisposition:
    row = db.query(ReminderDisposition).filter(ReminderDisposition.message_id == msg.id).first()
    if row is None:
        row = ReminderDisposition(message_id=msg.id, user_id=user_id, state=STATE_OPEN)
        db.add(row)
    return row


def _mark_read(msg: Message) -> None:
    if not msg.is_read:
        msg.is_read = True
        msg.read_at = utcnow()


def _audit(db: Session, action: str, msg: Message, user_id: int, username: str, detail: str) -> None:
    """写工作日志；失败只告警，不阻断处置（与 machine_code 等模块同约定）。"""
    try:
        from app.services.work_log_service import write_work_log

        write_work_log(
            db,
            "reminder",
            action,
            msg.id,
            msg.title or f"提醒 #{msg.id}",
            user_id=user_id,
            username=username or "",
            detail=detail,
        )
    except Exception:
        logger.warning(
            "提醒处置审计留痕失败 action=%s message_id=%s", action, msg.id, exc_info=True
        )


def _apply(
    db: Session,
    message_id: int,
    user_id: int,
    *,
    state: str,
    action: str,
    note: str = "",
    snooze_days: Optional[int] = None,
    username: str = "",
    detail: str = "",
) -> Dict[str, Any]:
    msg = load_owned_reminder(db, message_id, user_id)
    row = _upsert(db, msg, user_id)
    row.state = state
    row.note = note or None
    row.snooze_until = utcnow() + timedelta(days=snooze_days) if snooze_days is not None else None
    row.acted_at = utcnow()
    _mark_read(msg)
    safe_commit(db)
    _audit(db, action, msg, user_id, username, detail or note or action)
    return {"message_id": message_id, **serialize_disposition(row)}


def handle(
    db: Session, message_id: int, user_id: int, *, note: str = "", username: str = ""
) -> Dict[str, Any]:
    """标记已处理（幂等）。"""
    return _apply(
        db, message_id, user_id, state=STATE_HANDLED, action="handle",
        note=note, username=username, detail=f"标记已处理：{note}" if note else "标记已处理",
    )


def ignore(
    db: Session, message_id: int, user_id: int, *, reason: str = "", username: str = ""
) -> Dict[str, Any]:
    """忽略提醒（原因可选但建议填写，幂等）。"""
    return _apply(
        db, message_id, user_id, state=STATE_IGNORED, action="ignore",
        note=reason, username=username, detail=f"忽略：{reason}" if reason else "忽略（未填原因）",
    )


def snooze(
    db: Session, message_id: int, user_id: int, *, days: int = 7, username: str = ""
) -> Dict[str, Any]:
    """延期 N 天（保持未处理状态；重复延期更新到期时间）。"""
    if not isinstance(days, int) or not (SNOOZE_MIN_DAYS <= days <= SNOOZE_MAX_DAYS):
        raise InvalidSnoozeDaysError(
            f"延期天数须在 {SNOOZE_MIN_DAYS}-{SNOOZE_MAX_DAYS} 之间"
        )
    return _apply(
        db, message_id, user_id, state=STATE_OPEN, action="snooze",
        snooze_days=days, username=username, detail=f"延期 {days} 天",
    )


def reopen(
    db: Session, message_id: int, user_id: int, *, note: str = "", username: str = ""
) -> Dict[str, Any]:
    """重新打开（清除处理/忽略状态与延期）。"""
    return _apply(
        db, message_id, user_id, state=STATE_OPEN, action="reopen",
        note=note, username=username, detail=f"重新打开：{note}" if note else "重新打开",
    )
