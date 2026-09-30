"""自动化提醒引擎 — 审批超时/项目到期/经费告警."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.approval import ApprovalTask, ApprovalStatus
from app.models.project import Project
from app.models.fund import Fund
from app.models.base import _utcnow

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    """把从库中读回的时间统一为 UTC aware。

    created_at 由 models.base._utcnow 写 UTC，但 SQLite 读回的是 naive 值；
    历史实现用 `datetime.now()`（本机时区）与之比较，非 UTC 主机（UTC+8）上
    阈值与 elapsed_hours 整体偏移 8 小时（超时提醒晚 8 小时才触发）。
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _elapsed_hours(created_at: Optional[datetime]) -> float:
    """已等待小时数（UTC 口径）；创建时间为空时按 0 处理，避免 NoneType 崩溃"""
    if created_at is None:
        return 0.0
    return round((_utcnow() - _as_utc(created_at)).total_seconds() / 3600, 1)


def _approval_recipient(task: Any) -> Optional[int]:
    """解析审批提醒接收人：当前审批人 → 提交人。

    两者都为空时返回 None，由 orchestrator 跳过（messages.user_id NOT NULL）。
    历史实现在这里不解析接收人，导致审批类提醒在 orchestrator 恒被丢弃。
    """
    for attr in ("current_approver_id", "submitter_id"):
        value = getattr(task, attr, None)
        if value:
            return value
    return None


def scan_overtime_approvals(db: Session, hours_threshold: int = 48) -> List[Dict[str, Any]]:
    """扫描超时未处理的审批任务."""
    cutoff = _utcnow() - timedelta(hours=hours_threshold)
    tasks = (
        db.query(ApprovalTask)
        .filter(
            ApprovalTask.status == ApprovalStatus.PENDING.value,
            ApprovalTask.created_at <= cutoff,
        )
        .all()
    )
    return [
        {
            "type": "approval_overtime",
            "entity_id": t.id,
            "title": getattr(t, "title", "") or f"审批任务 #{t.id}",
            "elapsed_hours": _elapsed_hours(t.created_at),
            "user_id": _approval_recipient(t),
        }
        for t in tasks
    ]


def scan_approaching_approvals(
    db: Session, warning_hours: int = 36, deadline_hours: int = 48
) -> List[Dict[str, Any]]:
    """扫描即将超时的审批任务（36~48 小时预警档，与旧 reminder_service 功能对齐）。"""
    now = _utcnow()
    warning_time = now - timedelta(hours=warning_hours)
    deadline = now - timedelta(hours=deadline_hours)
    tasks = (
        db.query(ApprovalTask)
        .filter(
            ApprovalTask.status == ApprovalStatus.PENDING.value,
            ApprovalTask.created_at <= warning_time,
            ApprovalTask.created_at > deadline,
        )
        .all()
    )
    return [
        {
            "type": "approval_approaching",
            "entity_id": t.id,
            "title": getattr(t, "title", "") or f"审批任务 #{t.id}",
            "elapsed_hours": _elapsed_hours(t.created_at),
            "user_id": _approval_recipient(t),
        }
        for t in tasks
    ]


def scan_deadline_warnings(db: Session, days_threshold: int = 7) -> List[Dict[str, Any]]:
    """扫描即将到期的项目."""
    now = datetime.now().date()
    deadline = now + timedelta(days=days_threshold)
    projects = (
        db.query(Project)
        .filter(
            Project.is_active == True,  # noqa: E712 软删项目不提醒
            Project.end_date.isnot(None),
            Project.end_date <= deadline,
        )
        .all()
    )
    results = []
    for p in projects:
        days_left = (p.end_date - now).days if p.end_date else 0
        results.append({
            "type": "deadline_warning",
            "entity_id": p.id,
            "title": getattr(p, "name", "") or f"项目 #{p.id}",
            "end_date": str(p.end_date) if p.end_date else "",
            "days_left": days_left,
            "severity": "danger" if days_left < 0 else ("warning" if days_left <= 3 else "info"),
            # 项目归属人（无归属时由 orchestrator 跳过，避免 messages.user_id NOT NULL 崩溃）
            "user_id": getattr(p, "created_by", None),
        })
    return results


def scan_budget_warnings(
    db: Session,
    warning_threshold: float = 0.80,
    danger_threshold: float = 0.95,
) -> List[Dict[str, Any]]:
    """扫描经费预算告警."""
    funds = db.query(Fund).filter(Fund.amount > 0).all()
    results = []
    for f in funds:
        used = getattr(f, "used_amount", 0) or 0
        approved = f.amount or 0
        if approved <= 0:
            continue
        ratio = used / approved
        if ratio >= warning_threshold:
            results.append({
                "type": "budget_warning",
                "entity_id": f.id,
                "title": getattr(f, "name", "") or f"经费 #{f.id}",
                "ratio": round(ratio * 100, 1),
                "severity": "danger" if ratio >= danger_threshold else "warning",
                # 经费归属人（无归属时由 orchestrator 跳过，避免 messages.user_id NOT NULL 崩溃）
                "user_id": getattr(f, "created_by", None),
            })
    return results


def should_skip_duplicate(reminder_type, entity_id, existing):
    """去重：同一类型+实体ID已存在则跳过."""
    for e in existing:
        if e.get("type") == reminder_type and e.get("entity_id") == entity_id:
            return True
    return False
