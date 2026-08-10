"""
统一提醒扫描接线器（单机提醒中心底座）

将 reminder_engine 的三个扫描函数（审批超时/项目截止/预算预警）接入调度，
结果写入 Message 表（幂等去重），前端提醒中心聚合展示。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.transaction import get_db_context
from app.models.message import Message

logger = logging.getLogger(__name__)

# reminder_engine 提醒类型 → Message.message_type
_TYPE_TO_MESSAGE = {
    "approval_overtime": "approval_overtime",
    "deadline_warning": "deadline_warning",
    "budget_warning": "budget_warning",
}


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
                reminder_engine.scan_deadline_warnings(db),
                reminder_engine.scan_budget_warnings(db),
            ]
            for reminders in scans:
                for r in reminders:
                    link = _dedupe_link(r)
                    exists = (
                        db.query(Message)
                        .filter(Message.message_type == _TYPE_TO_MESSAGE.get(r.get("type", ""), "reminder"))
                        .filter(Message.link == link)
                        .first()
                    )
                    if exists:
                        continue
                    msg = Message(
                        message_type=_TYPE_TO_MESSAGE.get(r.get("type", ""), "reminder"),
                        title=r.get("title", "系统提醒"),
                        content=_format_reminder(r),
                        link=link,
                    )
                    db.add(msg)
                    created.append(r)
            from app.core.transaction import safe_commit

            safe_commit(db)
    except Exception as e:
        logger.error("提醒扫描失败: %s", e, exc_info=True)
    return created


def _format_reminder(r: Dict[str, Any]) -> str:
    t = r.get("type", "")
    if t == "approval_overtime":
        return f"审批任务已超时 {r.get('elapsed_hours', 0)} 小时，请及时处理。"
    if t == "deadline_warning":
        return f"项目将于 {r.get('end_date', '')} 到期（剩 {r.get('days_left', 0)} 天）。"
    if t == "budget_warning":
        return f"经费预算已使用 {r.get('ratio', 0)}%，请关注。"
    return str(r)


def list_reminders(limit: int = 50) -> List[Dict[str, Any]]:
    """查询提醒中心的全部提醒（按时间倒序）"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        rows = (
            db.query(Message)
            .filter(Message.message_type.in_(
                ["approval_overtime", "deadline_warning", "budget_warning", "backup_reminder", "package_reminder"]
            ))
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": m.id,
                "type": m.message_type,
                "title": m.title,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "is_read": m.is_read if hasattr(m, "is_read") else False,
            }
            for m in rows
        ]
    finally:
        db.close()
