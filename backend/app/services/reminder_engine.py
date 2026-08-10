"""自动化提醒引擎 — 审批超时/项目到期/经费告警."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.approval import ApprovalTask, ApprovalStatus
from app.models.project import Project
from app.models.fund import Fund

logger = logging.getLogger(__name__)


def scan_overtime_approvals(db: Session, hours_threshold: int = 48) -> List[Dict[str, Any]]:
    """扫描超时未处理的审批任务."""
    cutoff = datetime.now() - timedelta(hours=hours_threshold)
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
            "elapsed_hours": round(
                (datetime.now() - t.created_at).total_seconds() / 3600, 1
            ),
        }
        for t in tasks
    ]


def scan_deadline_warnings(db: Session, days_threshold: int = 7) -> List[Dict[str, Any]]:
    """扫描即将到期的项目."""
    now = datetime.now().date()
    deadline = now + timedelta(days=days_threshold)
    projects = (
        db.query(Project)
        .filter(Project.end_date.isnot(None), Project.end_date <= deadline)
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
            })
    return results


def should_skip_duplicate(reminder_type, entity_id, existing):
    """去重：同一类型+实体ID已存在则跳过."""
    for e in existing:
        if e.get("type") == reminder_type and e.get("entity_id") == entity_id:
            return True
    return False
