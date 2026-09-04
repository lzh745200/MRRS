"""
系统监控API
提供系统实时监控数据查询和告警管理功能
用于帮扶管理信息系统的运行状态监控
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitor", tags=["系统监控"])


# ==================== Pydantic 模型 ====================

class MonitorSnapshot(BaseModel):
    """监控快照"""
    timestamp: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: Optional[float] = None
    network_out: Optional[float] = None
    active_users: Optional[int] = None
    request_count: Optional[int] = None
    error_count: Optional[int] = None
    db_connections: Optional[int] = None
    host: Optional[str] = None


class AlertRule(BaseModel):
    """告警规则"""
    name: str
    metric_type: str
    threshold: float
    duration_seconds: int
    enabled: bool


# ==================== API 端点 ====================


@router.get("/snapshot", summary="获取当前系统快照")
async def get_monitor_snapshot(current_user=Depends(get_current_user)):
    """获取当前时刻系统运行状态的实时快照

    包含CPU、内存、磁盘、网络等核心资源的即时使用情况。
    """
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": None,
    }

    try:
        import psutil
        import platform

        snapshot["host"] = platform.node()

        # CPU（interval>0 为阻塞采样，async 端点卸载到线程池，避免冻结事件循环 0.3s）
        snapshot["cpu_usage"] = await run_in_threadpool(psutil.cpu_percent, interval=0.3)
        snapshot["cpu_count"] = psutil.cpu_count()

        # 内存
        memory = psutil.virtual_memory()
        snapshot["memory_usage"] = memory.percent
        snapshot["memory_used_mb"] = round(memory.used / (1024 * 1024), 2)
        snapshot["memory_total_mb"] = round(memory.total / (1024 * 1024), 2)

        # 磁盘（跨平台：Windows 取 SystemDrive，其它平台取文件系统根 "/"）
        # 历史缺陷：曾硬编码回退 "C:\\"，在 Linux/麒麟上 SystemDrive 未设置 →
        # psutil.disk_usage("C:\\") 抛 FileNotFoundError，被外层 except 吞成整快照
        # status=error（丢失 CPU/内存/网络并刷 ERROR 日志）。
        disk_path = os.environ.get("SystemDrive") or os.path.abspath(os.sep)
        try:
            disk = psutil.disk_usage(disk_path)
            snapshot["disk_usage"] = disk.percent
            snapshot["disk_used_gb"] = round(disk.used / (1024 ** 3), 2)
            snapshot["disk_total_gb"] = round(disk.total / (1024 ** 3), 2)
        except Exception:
            # 单块磁盘读取失败不应拖垮整份快照：降级为 warning，其余指标照常上报
            logger.warning("磁盘使用率读取失败（path=%s）", disk_path, exc_info=True)

        # 网络
        net_io = psutil.net_io_counters()
        snapshot["network_sent_mb"] = round(net_io.bytes_sent / (1024 * 1024), 2)
        snapshot["network_recv_mb"] = round(net_io.bytes_recv / (1024 * 1024), 2)

        # Python进程
        process = psutil.Process()
        snapshot["process_cpu_percent"] = process.cpu_percent()
        snapshot["process_memory_mb"] = round(process.memory_info().rss / (1024 * 1024), 2)
        snapshot["process_threads"] = process.num_threads()

        snapshot["status"] = "healthy"
    except ImportError:  # pragma: no cover
        snapshot["status"] = "limited"
        snapshot["message"] = "psutil未安装，仅提供基础监控数据"
    except Exception:
        logger.error("获取监控数据失败", exc_info=True)
        snapshot["status"] = "error"
        snapshot["message"] = "获取监控数据失败，请查看日志"

    return success_response(data=snapshot)


@router.get("/resources", summary="获取资源使用详情")
async def get_resource_usage(current_user=Depends(get_current_user)):
    """获取系统资源使用详细报告

    包含更详细的资源使用情况和健康评估。
    """
    resources = {}

    try:
        import psutil

        # CPU详细信息（interval>0 为阻塞采样，async 端点卸载到线程池，避免冻结事件循环 0.2s）
        cpu_percent = await run_in_threadpool(psutil.cpu_percent, interval=0.2)
        resources["cpu"] = {
            "percent": cpu_percent,
            "count_logical": psutil.cpu_count(),
            "count_physical": psutil.cpu_count(logical=False),
            "freq_current_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
        }

        # 内存详细信息
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        resources["memory"] = {
            "percent": memory.percent,
            "used_gb": round(memory.used / (1024 ** 3), 2),
            "available_gb": round(memory.available / (1024 ** 3), 2),
            "total_gb": round(memory.total / (1024 ** 3), 2),
            "swap_percent": swap.percent if swap.total > 0 else 0,
        }

        # 磁盘详细信息
        partitions = psutil.disk_partitions()
        disks = []
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "filesystem": part.fstab,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent": usage.percent,
                })
            except (OSError, Exception) as e:
                logger.warning("Failed to read disk partition %s: %s", part.mountpoint, e)
                disks.append({"mountpoint": part.mountpoint, "device": part.device,
                              "error": "读取失败", "available": False})
        resources["disk"] = disks

        # 健康评估
        issues = []
        if resources["cpu"]["percent"] > 90:
            issues.append({"component": "CPU", "severity": "warning",
                          "message": f"CPU使用率过高: {resources['cpu']['percent']}%"})
        if resources["memory"]["percent"] > 85:
            issues.append({"component": "内存", "severity": "warning",
                          "message": f"内存使用率过高: {resources['memory']['percent']}%"})
        if disks and disks[0]["percent"] > 85:
            issues.append({"component": "磁盘", "severity": "warning", "message": f"磁盘使用率过高: {disks[0]['percent']}%"})

        resources["health_status"] = "unhealthy" if len(issues) > 2 else "degraded" if issues else "healthy"
        resources["health_issues"] = issues
    except ImportError:  # pragma: no cover
        resources["status"] = "limited"
        resources["message"] = "psutil未安装，资源监控功能受限"
    except Exception:
        logger.error("获取资源使用详情失败", exc_info=True)
        resources["status"] = "error"
        resources["message"] = "获取资源使用详情失败，请查看日志"

    return success_response(data=resources)


@router.get("/alerts", summary="获取告警规则列表")
async def get_alert_rules(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取当前配置的监控告警规则"""
    rules = []

    try:
        from app.models.monitoring import AlertRule

        db_rules = db.query(AlertRule).all()
        for rule in db_rules:
            rules.append({
                "id": rule.id,
                "name": rule.name,
                "metric_type": rule.metric_type,
                "threshold": rule.threshold,
                "duration_seconds": rule.duration_seconds,
                "enabled": rule.enabled,
                "created_at": rule.created_at.isoformat() if hasattr(rule, "created_at") and rule.created_at else None,
            })
    except Exception as e:
        logger.debug("获取告警规则失败: %s", e)

    # 如果没有数据库中的告警规则，返回默认规则
    if not rules:
        rules = [{"id": "default-1",
                  "name": "CPU使用率告警",
                  "metric_type": "cpu_usage",
                  "threshold": 90.0,
                  "duration_seconds": 60,
                  "enabled": True},
                 {"id": "default-2",
                  "name": "内存使用率告警",
                  "metric_type": "memory_usage",
                  "threshold": 85.0,
                  "duration_seconds": 60,
                  "enabled": True},
                 {"id": "default-3",
                  "name": "磁盘使用率告警",
                  "metric_type": "disk_usage",
                  "threshold": 85.0,
                  "duration_seconds": 120,
                  "enabled": True},
                 {"id": "default-4",
                  "name": "错误率告警",
                  "metric_type": "error_rate",
                  "threshold": 5.0,
                  "duration_seconds": 300,
                  "enabled": False},
                 ]

    return success_response(data={"rules": rules, "total": len(rules)})


@router.get("/alerts/history", summary="获取告警历史记录")
async def get_alert_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="按状态筛选: triggered/resolved"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取系统告警历史记录"""
    items = []

    try:
        from app.models.monitoring import AlertHistory

        query = db.query(AlertHistory)
        if status:
            query = query.filter(AlertHistory.status == status)
        total = query.count()
        records = query.order_by(AlertHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        for record in records:
            items.append({
                "id": record.id,
                "rule_id": record.rule_id,
                "message": record.message,
                "metric_value": record.metric_value,
                "status": record.status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            })
    except Exception as e:
        logger.debug("获取告警历史失败: %s", e)
        total = 0

    return ok_list(items=items, total=total, page=page, page_size=page_size)


@router.get("/api-stats", summary="获取API调用统计")
async def get_api_statistics(
    hours: int = Query(24, ge=1, le=720, description="统计时间范围（小时）"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取API接口调用统计数据

    优先读取内存指标存储（MetricsMiddleware 实时采集），
    数据库 api_metrics 表无写入方时回退为空统计，保证面板有真实数据。
    """
    try:
        from app.middleware.metrics_middleware import metrics_store

        summary = metrics_store.get_summary()
        return success_response(
            data={
                "period_hours": hours,
                "request_count": summary.get("request_count", 0),
                "error_count": summary.get("error_count", 0),
                "error_rate": summary.get("error_rate", 0),
                "avg_duration": summary.get("avg_duration", 0),
                "requests_per_second": summary.get("requests_per_second", 0),
                "uptime_seconds": summary.get("uptime_seconds", 0),
                "top_endpoints": summary.get("top_endpoints", []),
                "by_method_status": summary.get("by_method_status", {}),
                "slow_requests": summary.get("slow_requests", []),
                "slow_request_count": summary.get("slow_request_count", 0),
            },
        )
    except Exception as e:
        logger.warning("获取 API 统计失败: %s", e)
        return success_response(
            data={
                "period_hours": hours,
                "request_count": 0,
                "error_count": 0,
                "error_rate": 0,
                "avg_duration": 0,
                "requests_per_second": 0,
                "uptime_seconds": 0,
                "top_endpoints": [],
                "by_method_status": {},
                "slow_requests": [],
                "slow_request_count": 0,
            },
        )


@router.get("/database-size", summary="获取数据库文件大小")
async def get_database_size(current_user=Depends(get_current_user)):
    """获取数据库文件大小（用于系统监控面板）"""
    from app.utils.paths import get_database_path
    try:
        # 路径解析唯一来源（AGENTS.md 路径双源规则）：禁止在此自行拼 DATABASE_URL
        db_path = str(get_database_path())
        if not os.path.exists(db_path):
            logger.error("数据库文件不存在: %s", db_path)
            return success_response(
                data={"size_bytes": 0, "size_mb": 0, "error": "数据库文件不存在，请查看日志"},
                success=False,
            )
        size = os.path.getsize(db_path)
        return success_response(
            data={
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 2),
            },
        )
    except PermissionError:
        return success_response(data={"size_bytes": 0, "size_mb": 0, "error": "无权限读取数据库文件"}, success=False)
    except Exception:
        logger.error("获取数据库大小失败", exc_info=True)
        return success_response(data={"size_bytes": 0, "size_mb": 0, "error": "获取数据库大小失败，请查看日志"}, success=False)
