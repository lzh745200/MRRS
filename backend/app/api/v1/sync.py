"""
同步状态API - 提供同步状态查询和可视化仪表盘数据
"""

import logging
from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success_response
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["同步状态"])


@router.get("/status")
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取同步状态

    返回当前用户的同步状态信息，从 data_sync_logs 表查询真实数据。
    """
    from app.models.data_sync import DataSyncLog

    # 查询最近一次同步记录
    last_log = (
        db.query(DataSyncLog)
        .order_by(DataSyncLog.started_at.desc())
        .first()
    )
    last_sync = last_log.started_at.isoformat() if last_log and last_log.started_at else None

    # 统计待处理（pending/processing）的同步任务数
    pending_changes = (
        db.query(DataSyncLog)
        .filter(DataSyncLog.status.in_(["pending", "processing"]))
        .count()
    )

    # 判断当前同步状态
    if pending_changes > 0:
        sync_status = "syncing"
    else:
        sync_status = "idle"

    return {
        "success": True,
        "data": {
            "sync_enabled": True,
            "last_sync": last_sync,
            "pending_changes": pending_changes,
            "sync_status": sync_status,
            "message": "同步功能正常",
        },
    }


@router.get("/dashboard")
async def get_sync_dashboard(
    days: int = Query(30, ge=1, le=365, description="统计天数范围"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取同步状态可视化仪表盘数据

    返回综合同步统计信息，包括：
    - 导入/导出历史记录统计
    - 数据包状态分布
    - 同步趋势（按日/周）
    - 磁盘空间使用情况
    - 最近同步活动
    """
    from app.core.database import check_disk_space
    from app.models.audit import AuditLog

    # ── 1. 审计日志中的同步操作统计 ──
    start_date = datetime.now() - timedelta(days=days)
    sync_logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.created_at >= start_date,
            AuditLog.action.in_(["export", "import", "sync", "data_sync"]),
        )
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    # ── 2. 按操作类型统计 ──
    action_counts: Dict[str, int] = {}
    for log in sync_logs:
        action = log.action or "unknown"
        action_counts[action] = action_counts.get(action, 0) + 1

    # ── 3. 按日期统计趋势 ──
    daily_trend: Dict[str, int] = {}
    for log in sync_logs:
        day = log.created_at.strftime("%Y-%m-%d") if log.created_at else "unknown"
        daily_trend[day] = daily_trend.get(day, 0) + 1

    # 转为有序列表
    trend_list = [
        {"date": k, "count": v}
        for k, v in sorted(daily_trend.items())
    ]

    # ── 4. 最近同步活动（最多20条） ──
    recent_activities = []
    for log in sync_logs[:20]:
        recent_activities.append({
            "id": log.id,
            "time": log.created_at.isoformat() if log.created_at else "",
            "user": log.username or "",
            "action": log.action or "",
            "resource_type": log.resource_type or "",
            "status": log.status or "success",
            "ip": log.user_ip or "",
        })

    # ── 5. 数据包文件统计 ──
    from app.utils.paths import get_runtime_uploads_path
    uploads_dir = get_runtime_uploads_path()
    package_stats = {
        "total_packages": 0,
        "total_size_mb": 0,
        "packages_dir": str(uploads_dir),
    }
    try:
        if uploads_dir.exists():
            package_files = list(uploads_dir.glob("*.rrs")) + list(uploads_dir.glob("*.zip"))
            package_stats["total_packages"] = len(package_files)
            total_size = sum(f.stat().st_size for f in package_files if f.is_file())
            package_stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
    except Exception as e:
        logger.warning("统计数据包文件失败: %s", e)

    # ── 6. 磁盘空间 ──
    disk_info = check_disk_space(min_mb=100)

    # ── 7. 成功率统计 ──
    success_count = sum(1 for log in sync_logs if log.status == "success")
    failure_count = sum(1 for log in sync_logs if log.status == "failure")
    total_count = len(sync_logs)
    success_rate = round(success_count / total_count * 100, 1) if total_count > 0 else 100.0

    return success_response(
        data={
            "summary": {
                "total_syncs": total_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
                "period_days": days,
            },
            "action_counts": action_counts,
            "daily_trend": trend_list,
            "recent_activities": recent_activities,
            "package_stats": package_stats,
            "disk_info": disk_info,
            "last_updated": datetime.now().isoformat(),
        },
        message="成功获取同步仪表盘数据"
    )
