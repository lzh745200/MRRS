"""
系统指标API
提供系统运行指标数据的查询和统计功能
用于帮扶管理信息系统的性能监控和数据分析
"""

import logging
import platform
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import engine

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["系统指标"])


# ==================== Pydantic 模型 ====================

class SystemMetricsResponse(BaseModel):
    """系统指标综合响应"""
    timestamp: str
    uptime: dict
    resources: dict
    database: dict
    application: dict


class PerformanceMetric(BaseModel):
    """性能指标"""
    name: str
    value: float
    unit: str
    threshold: Optional[float] = None
    status: str = "normal"


# ==================== API 端点 ====================

@router.get("", summary="获取系统综合指标")
async def get_system_metrics(current_user=Depends(get_current_user)):
    """获取系统运行的综合指标数据

    包含系统资源使用、数据库状态、应用运行状况等多维度指标。
    """
    metrics = {}

    # 系统资源指标
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        metrics["resources"] = {
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "memory_percent": memory.percent,
            "memory_used_mb": round(memory.used / (1024 * 1024), 2),
            "memory_total_mb": round(memory.total / (1024 * 1024), 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        }
    except ImportError:  # pragma: no cover
        metrics["resources"] = {
            "status": "unavailable",
            "message": "psutil 未安装，资源指标不可用",
        }
    except Exception as e:
        metrics["resources"] = {
            "status": "error",
            "message": f"获取资源指标失败: {str(e)}",
        }

    # 系统运行时间
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
        uptime = datetime.now(timezone.utc) - boot_time
        metrics["uptime"] = {
            "boot_time": boot_time.isoformat(),
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_display": str(uptime).split(".")[0],
        }
    except Exception:
        metrics["uptime"] = {}

    # Python进程信息
    try:
        process = psutil.Process()
        with process.oneshot():
            process_info = {
                "pid": process.pid,
                "cpu_percent": process.cpu_percent(),
                "memory_mb": round(process.memory_info().rss / (1024 * 1024), 2),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
                "create_time": datetime.fromtimestamp(process.create_time(), tz=timezone.utc).isoformat(),
            }
        metrics["process"] = process_info
    except Exception:
        metrics["process"] = {}

    # 应用信息
    metrics["application"] = {
        "version": getattr(settings, "PROJECT_VERSION", "1.0.0"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": platform.node(),
    }

    # 数据库指标
    try:
        pool = engine.pool
        metrics["database"] = {
            "status": "connected",
            "size": getattr(pool, 'size', lambda: 0)(),
            "checkedin": getattr(pool, 'checkedin', lambda: 0)(),
            "overflow": getattr(pool, 'overflow', lambda: 0)(),
            "connections_in_use": (
                getattr(pool, 'size', lambda: 0)() - getattr(pool, 'checkedin', lambda: 0)()
                if hasattr(pool, 'size') and hasattr(pool, 'checkedin') else 0
            ),
        }
    except Exception:
        metrics["database"] = {"status": "unavailable", "message": "数据库监控不可用"}

    return {
        "success": True,
        "data": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metrics,
        },
    }


@router.get("/performance", summary="获取性能指标列表")
async def get_performance_metrics(current_user=Depends(get_current_user)):
    """获取各关键性能指标的详细数据

    返回预定义的性能指标列表及其当前值和状态。
    """
    indicators = []

    try:
        import psutil

        # CPU指标
        cpu_percent = psutil.cpu_percent(interval=0.3)
        indicators.append({
            "name": "CPU使用率",
            "key": "cpu_usage",
            "value": cpu_percent,
            "unit": "%",
            "threshold": 80,
            "status": "warning" if cpu_percent > 80 else "critical" if cpu_percent > 95 else "normal",
        })

        # 内存指标
        memory = psutil.virtual_memory()
        indicators.append({
            "name": "内存使用率",
            "key": "memory_usage",
            "value": memory.percent,
            "unit": "%",
            "threshold": 85,
            "status": "warning" if memory.percent > 85 else "critical" if memory.percent > 95 else "normal",
        })

        # 磁盘指标
        disk = psutil.disk_usage("/")
        indicators.append({
            "name": "磁盘使用率",
            "key": "disk_usage",
            "value": disk.percent,
            "unit": "%",
            "threshold": 80,
            "status": "warning" if disk.percent > 80 else "critical" if disk.percent > 95 else "normal",
        })
    except ImportError:  # pragma: no cover
        pass

    return {
        "success": True,
        "data": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "indicators": indicators,
            "summary": {
                "total": len(indicators),
                "normal": len([i for i in indicators if i["status"] == "normal"]),
                "warning": len([i for i in indicators if i["status"] == "warning"]),
                "critical": len([i for i in indicators if i["status"] == "critical"]),
            },
        },
    }


@router.get("/database", summary="获取数据库指标")
async def get_database_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取数据库相关的指标数据

    包含数据库大小、表数量、连接状态等关键指标。
    """

    metrics = {}

    # 数据库文件大小
    try:
        from app.utils.paths import get_database_path
        db_path = get_database_path()
        if db_path.exists():
            size_bytes = db_path.stat().st_size
            metrics["database_file_size_mb"] = round(size_bytes / (1024 * 1024), 2)
            metrics["database_file_path"] = str(db_path)
    except Exception as e:
        metrics["database_file_error"] = str(e)

    # 表数量统计
    try:
        from sqlalchemy import inspect, text

        inspector = inspect(db.get_bind())
        tables = inspector.get_table_names()
        metrics["table_count"] = len(tables)
        metrics["table_names"] = tables[:20]  # 限制返回数量
        if len(tables) > 20:
            metrics["table_names_truncated"] = True
    except Exception as e:
        metrics["table_count_error"] = str(e)

    # 关键表行数统计（白名单防御：仅允许预定义的安全表名）
    try:
        # 白名单：仅允许查询这些预定义的安全表名，防止 SQL 注入
        _SAFE_TABLE_NAMES = frozenset(
            {"users", "organizations", "villages", "projects", "funds", "schools"}
        )
        key_tables = ["users", "organizations", "villages", "projects", "funds", "schools"]
        row_counts = {}
        for table in key_tables:
            if table not in _SAFE_TABLE_NAMES:  # pragma: no cover - 防御性分支，key_tables 恒在白名单内
                row_counts[table] = "N/A"
                continue
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))  # nosec B608 — _SAFE_TABLE_NAMES 白名单
                row_counts[table] = result.scalar()
            except Exception as e:
                logger.debug("统计表 %s 行数失败: %s", table, e)
                row_counts[table] = "N/A"
        metrics["key_table_row_counts"] = row_counts
    except Exception as e:
        metrics["row_count_error"] = str(e)

    return {
        "success": True,
        "data": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
        },
    }


@router.get("/history", summary="获取历史指标数据")
async def get_metrics_history(
    hours: int = Query(24, ge=1, le=720, description="查询时间范围（小时）"),
    metric_type: str = Query("all", description="指标类型: cpu/memory/disk/all"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取指定时间范围内的历史监控指标数据"""
    try:
        from app.models.system_monitor import SystemMonitor

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        records = (
            db.query(SystemMonitor)
            .filter(SystemMonitor.created_at >= since)
            .order_by(SystemMonitor.created_at.asc())
            .limit(500)
            .all()
        )

        history = []
        for record in records:
            entry = {
                "timestamp": record.created_at.isoformat() if record.created_at else None,
                "host": record.host,
            }
            if metric_type in ("cpu", "all"):
                entry["cpu_usage"] = record.cpu_usage
            if metric_type in ("memory", "all"):
                entry["memory_usage"] = record.memory_usage
            if metric_type in ("disk", "all"):
                entry["disk_usage"] = record.disk_usage
            history.append(entry)

        return {
            "success": True,
            "data": {
                "metric_type": metric_type,
                "hours": hours,
                "record_count": len(history),
                "history": history,
            },
        }
    except Exception as e:
        return {
            "success": True,
            "data": {
                "metric_type": metric_type,
                "hours": hours,
                "record_count": 0,
                "history": [],
                "message": f"历史指标数据暂不可用: {str(e)}",
            },
        }
