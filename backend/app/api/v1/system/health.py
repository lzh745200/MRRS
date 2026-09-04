"""System health monitoring routes — comprehensive health check with DB, backup, and performance metrics."""

import logging
import os
import platform
import time
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["系统健康"])

_START_TIME = time.time()


@router.get("")
@router.get("/overview")
async def health_overview():
    """System health overview with key metrics."""
    uptime = time.time() - _START_TIME
    return {
        "code": 200,
        "data": {
            "status": "healthy",
            "uptime_seconds": round(uptime, 1),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
    }


@router.get("/database")
async def health_database():
    """Check database connectivity and size."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
        db_size = os.path.getsize(db_path) if db_path and os.path.exists(db_path) else 0
        return {
            "code": 200,
            "data": {
                "connected": True,
                "size_bytes": db_size,
                "size_mb": round(db_size / 1024 / 1024, 2) if db_size else 0,
            },
        }
    except Exception as e:
        return {"code": 500, "message": str(e)}
    finally:
        db.close()


@router.get("/database-health")
async def health_database_detail():
    """数据库健康详情（自检结果 + 统计），供前端启动后提示"""
    try:
        from app.services.database_health_service import database_health_service

        info = database_health_service.get_database_info()
        stats = database_health_service.get_stats()
        return {
            "code": 200,
            "data": {
                "status": info.get("status", "unknown"),
                "info": info,
                "stats": stats,
                "issues": database_health_service.health_status.get("issues", []),
            },
        }
    except Exception as e:
        return {"code": 500, "message": str(e), "data": {"status": "error"}}


@router.get("/liveness")
async def health_liveness():
    """Kubernetes-style liveness probe."""
    return {"status": "alive"}


@router.get("/readiness")
async def health_readiness():
    """Kubernetes-style readiness probe (checks DB)."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.warning("就绪检查失败: %s", e)
        return {"status": "not_ready"}
    finally:
        db.close()


@router.get("/full")
async def health_full():
    """Comprehensive health report with DB stats, backup status, and performance metrics."""
    import sqlite3
    from app.core.build_info import get_build_info
    from app.core.config import settings
    from app.utils.paths import get_database_path, get_backup_path

    build = get_build_info()
    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_version": settings.PROJECT_VERSION,
        "build_git_hash": build.get("git_hash", "unknown"),
        "build_time": build.get("build_time"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "process_pid": os.getpid(),
    }

    # ── Database stats ──
    db_path = str(get_database_path().absolute())
    if os.path.exists(db_path):
        try:
            db_size = os.path.getsize(db_path)
            result["db_size_mb"] = round(db_size / 1024 / 1024, 1)
            wal_path = db_path + "-wal"
            result["wal_size_kb"] = round(os.path.getsize(wal_path) / 1024, 0) if os.path.exists(wal_path) else 0

            conn = sqlite3.connect(db_path)
            try:
                tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
                result["table_count"] = tables[0] if tables else 0
                integrity = conn.execute("PRAGMA integrity_check").fetchone()
                result["db_integrity_ok"] = integrity[0] == "ok" if integrity else False
            finally:
                conn.close()
        except Exception as e:
            # 无认证端点：db_error 只出异常类名，原文（可含数据库绝对路径）仅进日志
            logger.error("健康检查读取数据库统计失败", exc_info=True)
            result["db_error"] = type(e).__name__

    # ── Backup status ──
    backup_dir = str(get_backup_path())
    if os.path.exists(backup_dir):
        try:
            backups = [f for f in os.listdir(backup_dir) if f.endswith((".zip", ".db"))]
            result["total_backups"] = len(backups)
            total_size = sum(os.path.getsize(os.path.join(backup_dir, f)) for f in backups)
            result["backup_total_size_mb"] = round(total_size / 1024 / 1024, 1)
        except Exception:
            result["total_backups"] = 0

    # ── System resources ──
    try:
        import shutil
        # 跨平台磁盘路径：Windows 取 SystemDrive，其它平台取文件系统根 "/"
        # （曾硬编码回退 "C:\\"，在 Linux/麒麟上抛错使 disk_free_gb 恒为 None）
        disk = shutil.disk_usage(os.environ.get("SystemDrive") or os.path.abspath(os.sep))
        result["disk_free_gb"] = round(disk.free / 1024**3, 1)
    except Exception:
        result["disk_free_gb"] = None

    # ── Slow queries ──
    try:
        from app.core.query_optimizer import get_slow_queries
        slow = get_slow_queries(100)
        result["slow_queries_24h"] = len([q for q in slow if q.get("slow")])
    except Exception:
        result["slow_queries_24h"] = 0

    return {"code": 200, "data": result}
