"""
统一提醒扫描接线器（单机提醒中心底座）

将 reminder_engine 的三个扫描函数（审批超时/项目截止/预算预警）接入调度，
结果写入 Message 表（幂等去重），前端提醒中心聚合展示。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.transaction import get_db_context
from app.models.message import Message
from app.services.reminder_types import REMINDER_MESSAGE_TYPES
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

# reminder_engine 提醒类型 → Message.message_type
_TYPE_TO_MESSAGE = {
    "approval_overtime": "approval_overtime",
    "approval_approaching": "approval_approaching",
    "deadline_warning": "deadline_warning",
    "budget_warning": "budget_warning",
}

# 排序权重：未处理优先，其次已处理，忽略置底（稳定排序，组内保持时间倒序）
_STATE_RANK = {"open": 0, "handled": 1, "ignored": 2}


def _dedupe_link(reminder: Dict[str, Any]) -> str:
    """提醒去重键：type:entity_id"""
    return f"{reminder.get('type')}:{reminder.get('entity_id')}"


def run_reminder_scans() -> List[Dict[str, Any]]:
    """执行全部提醒扫描并写入 Message（幂等），返回本次新增的提醒列表。"""
    from app.services import reminder_engine

    created: List[Dict[str, Any]] = []
    try:
        with get_db_context() as db:
            scans = [
                reminder_engine.scan_overtime_approvals(db),
                reminder_engine.scan_approaching_approvals(db),
                reminder_engine.scan_deadline_warnings(db),
                reminder_engine.scan_budget_warnings(db),
            ]
            for reminders in scans:
                for r in reminders:
                    link = _dedupe_link(r)
                    msg_type = _TYPE_TO_MESSAGE.get(r.get("type", ""), "reminder")
                    exists = (
                        db.query(Message)
                        .filter(Message.message_type == msg_type)
                        .filter(Message.link == link)
                        .first()
                    )
                    if exists:
                        continue
                    # messages.user_id 为 NOT NULL：无法确定接收人的提醒跳过，
                    # 避免单条坏数据导致整批提醒提交失败（修复 2026-08-15）
                    user_id = r.get("user_id")
                    if not user_id:
                        logger.warning(
                            "提醒无法确定接收人，跳过 type=%s entity_id=%s",
                            r.get("type"),
                            r.get("entity_id"),
                        )
                        continue
                    msg = Message(
                        message_type=msg_type,
                        title=r.get("title", "系统提醒"),
                        content=_format_reminder(r),
                        link=link,
                        user_id=user_id,
                    )
                    db.add(msg)
                    created.append(r)
            from app.core.transaction import safe_commit

            safe_commit(db)
    except Exception as e:
        logger.error("提醒扫描失败: %s", e, exc_info=True)
        # 提交失败 → 本批提醒全部未落库，返回空列表（防止上层误报"新增 N 条"）
        return []
    return created


def _format_reminder(r: Dict[str, Any]) -> str:
    t = r.get("type", "")
    if t == "approval_overtime":
        return f"审批任务已超时 {r.get('elapsed_hours', 0)} 小时，请及时处理。"
    if t == "approval_approaching":
        return f"审批任务已等待 {r.get('elapsed_hours', 0)} 小时，即将超时，请及时审批。"
    if t == "deadline_warning":
        return f"项目将于 {r.get('end_date', '')} 到期（剩 {r.get('days_left', 0)} 天）。"
    if t == "budget_warning":
        return f"经费预算已使用 {r.get('ratio', 0)}%，请关注。"
    return str(r)


def _parse_entity_id(link: Optional[str]) -> Optional[int]:
    """解析去重键 ``type:entity_id`` 中的实体 ID；无法解析时返回 None。"""
    if not link:
        return None
    tail = link.partition(":")[2]
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


def list_reminders(
    limit: int = 50, user_id: Optional[int] = None, include_ignored: bool = False
) -> List[Dict[str, Any]]:
    """查询当前用户的提醒（未处理优先，其次时间倒序）

    fail-closed：提醒归属具体接收人（messages.user_id NOT NULL），缺少 user_id 时
    返回空列表，绝不返回全实例提醒。历史缺陷：任意登录用户都能看到他人提醒的
    标题/内容。调用方（api/v1/reminders.py）必须传 current_user.id。

    处置富化（w17-001）：附带 ``state/note/snooze_until/entity_id/link``；
    ``include_ignored=False``（默认）时过滤掉已忽略的提醒。
    """
    if not user_id:
        logger.warning("list_reminders 缺少 user_id，按 fail-closed 返回空列表")
        return []

    from app.core.database import SessionLocal
    from app.services.reminder_disposition_service import load_dispositions, serialize_disposition

    db = SessionLocal()
    try:
        rows = (
            db.query(Message)
            .filter(
                Message.message_type.in_(REMINDER_MESSAGE_TYPES),
                Message.user_id == user_id,
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        dispositions = load_dispositions(db, [m.id for m in rows], user_id)
        items: List[Dict[str, Any]] = []
        for m in rows:
            disposition = serialize_disposition(dispositions.get(m.id))
            if disposition["state"] == "ignored" and not include_ignored:
                continue
            items.append(
                {
                    "id": m.id,
                    "type": m.message_type,
                    "title": m.title,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "is_read": m.is_read if hasattr(m, "is_read") else False,
                    "state": disposition["state"],
                    "note": disposition["note"],
                    "snooze_until": disposition["snooze_until"],
                    "acted_at": disposition["acted_at"],
                    "link": getattr(m, "link", None),
                    "entity_id": _parse_entity_id(getattr(m, "link", None)),
                }
            )
        # 稳定排序：未处理优先；同组保持 created_at 倒序
        items.sort(key=lambda r: _STATE_RANK.get(r["state"], 0))
        return items
    finally:
        db.close()


def summarize_reminders(reminders: List[Dict[str, Any]]) -> Dict[str, int]:
    """按处置状态汇总（提醒中心统计卡片）。"""
    now = utcnow()
    stats = {"pending": 0, "handled": 0, "ignored": 0, "snoozed": 0, "total": len(reminders)}
    for r in reminders:
        state = r.get("state") or "open"
        if state == "handled":
            stats["handled"] += 1
        elif state == "ignored":
            stats["ignored"] += 1
        else:
            stats["pending"] += 1
        snooze_until = r.get("snooze_until")
        if state == "open" and snooze_until:
            try:
                if datetime.fromisoformat(snooze_until) > now:
                    stats["snoozed"] += 1
            except (TypeError, ValueError):
                logger.debug("忽略无法解析的延期时间: %r", snooze_until)
    return stats
