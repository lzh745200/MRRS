"""
核心系统API
提供系统运行控制（重启、关闭）、系统信息查询等核心功能
用于帮扶管理信息系统的系统级运维操作
"""

import logging
import os
import platform
import sys
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["系统控制"])


# ==================== Pydantic 模型 ====================

class SystemInfoResponse(BaseModel):
    """系统信息"""
    name: str
    version: str
    python_version: str
    platform: str
    database_type: str
    uptime: str
    total_users: int
    total_organizations: int
    total_villages: int
    total_projects: int


class ShutdownRequest(BaseModel):
    """关机/重启请求"""
    delay_seconds: int = 3
    confirm: str = ""


# ==================== API 端点 ====================

_start_time = datetime.now(timezone.utc)


@router.get("/info", summary="获取系统基本信息")
async def get_system_info(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取帮扶管理信息系统的综合信息

    包含软件版本、运行环境、核心业务数据统计等。
    """
    # 计算运行时间
    uptime_delta = datetime.now(timezone.utc) - _start_time
    uptime_str = str(uptime_delta).split(".")[0]

    # 数据库类型
    db_type = "SQLite"
    try:
        db_url = getattr(settings, "DATABASE_URL", "")
        if "postgresql" in db_url:
            db_type = "PostgreSQL"
        elif "mysql" in db_url:
            db_type = "MySQL"
    except Exception:
        logger.warning("Failed to detect database type", exc_info=True)

    # 统计数据
    total_users = 0
    total_orgs = 0
    total_villages = 0
    total_projects = 0
    stat_errors = []

    try:
        from sqlalchemy import text
        total_users = db.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
    except Exception as e:
        stat_errors.append(f"users({e})")
        logger.warning("Failed to count users: %s", e)

    try:
        from sqlalchemy import text
        total_orgs = db.execute(text("SELECT COUNT(*) FROM organizations")).scalar() or 0
    except Exception as e:
        stat_errors.append(f"organizations({e})")
        logger.warning("Failed to count organizations: %s", e)

    try:
        from sqlalchemy import text
        total_villages = db.execute(text("SELECT COUNT(*) FROM supported_villages")).scalar() or 0
    except Exception as e:
        stat_errors.append(f"villages({e})")
        logger.warning("Failed to count villages: %s", e)

    try:
        from sqlalchemy import text
        total_projects = db.execute(text("SELECT COUNT(*) FROM projects")).scalar() or 0
    except Exception as e:
        stat_errors.append(f"projects({e})")
        logger.warning("Failed to count projects: %s", e)

    return {
        "success": True,
        "data": {
            "name": "帮扶管理信息系统",
            "version": getattr(settings, "PROJECT_VERSION", "1.1.0"),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "database_type": db_type,
            "uptime": uptime_str,
            "total_users": total_users,
            "total_organizations": total_orgs,
            "total_villages": total_villages,
            "total_projects": total_projects,
            "stat_errors": stat_errors if stat_errors else None,
        },
    }


@router.get("/status", summary="获取系统运行状态")
async def get_system_status(current_user=Depends(get_current_user)):
    """获取当前系统运行状态概览"""
    status_info = {
        "status": "running",
        "started_at": _start_time.isoformat(),
        "uptime_seconds": int((datetime.now(timezone.utc) - _start_time).total_seconds()),
        "services": [],
    }

    # 检查数据库
    try:
        from app.core.database import engine
        engine.connect().close()
        status_info["services"].append({"name": "database", "status": "connected"})
    except Exception as e:
        status_info["services"].append({"name": "database", "status": "disconnected", "error": str(e)})

    # 检查缓存
    try:
        from app.core.cache import cache_manager
        # cache_manager.get 是 async def，必须 await —— 否则协程体不执行，
        # 缓存健康检查永远是假阳性（且产生 "coroutine never awaited" 警告）。
        await cache_manager.get("system_status_check")
        status_info["services"].append({"name": "cache", "status": "connected"})
    except Exception:
        status_info["services"].append({"name": "cache", "status": "unavailable"})

    return {"success": True, "data": status_info}


@router.post("/shutdown", summary="系统关机")
async def shutdown_system(
    background_tasks: BackgroundTasks,
    delay_seconds: int = Query(5, ge=1, le=30, description="关机延迟秒数"),
    current_user=Depends(get_current_user),
):
    """触发系统安全关闭

    延迟指定秒数后执行系统关闭操作。此操作需要管理员权限。
    系统将在关闭前完成当前请求的处理。
    """
    from app.core.permission_utils import require_admin
    require_admin(current_user, error_message="仅超级管理员可执行关机操作")

    logger.warning(
        "系统关机已触发，操作人: %s，延迟: %d秒",
        getattr(current_user, "username", "unknown"),
        delay_seconds,
    )

    def _shutdown():
        time.sleep(delay_seconds)
        logger.warning("系统正在关闭...")
        # 执行必要的清理操作
        try:
            from app.core.cache import cache_manager
            cache_manager.close()
        except Exception as e:
            logger.warning("关闭缓存管理器失败: %s", e)
        os._exit(0)

    background_tasks.add_task(_shutdown)

    return {
        "success": True,
        "message": f"系统将在 {delay_seconds} 秒后关闭，请稍候...",
    }


@router.post("/restart", summary="系统重启")
async def restart_system(
    background_tasks: BackgroundTasks,
    delay_seconds: int = Query(5, ge=1, le=30, description="重启延迟秒数"),
    current_user=Depends(get_current_user),
):
    """触发系统安全重启

    延迟指定秒数后执行系统重启操作。此操作需要管理员权限。
    """
    from app.core.permission_utils import require_admin
    require_admin(current_user, error_message="仅超级管理员可执行重启操作")

    logger.warning(
        "系统重启已触发，操作人: %s，延迟: %d秒",
        getattr(current_user, "username", "unknown"),
        delay_seconds,
    )

    def _restart():
        time.sleep(delay_seconds)
        logger.warning("系统正在重启...")
        try:
            from app.core.cache import cache_manager
            cache_manager.close()
        except Exception as e:
            logger.warning("关闭缓存管理器失败: %s", e)
        # 安全重启：使用 subprocess/subprocess.Popen 避免命令注入
        if sys.platform == "win32":
            import subprocess
            subprocess.Popen(
                [sys.executable] + sys.argv[1:],
                creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0,
                close_fds=True,
            )
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        os._exit(0)

    background_tasks.add_task(_restart)

    return {
        "success": True,
        "message": f"系统将在 {delay_seconds} 秒后重启，请稍候...",
    }


@router.get("/environment", summary="获取运行环境信息")
async def get_environment_info(current_user=Depends(get_current_user)):
    """获取详细的系统运行环境信息"""
    import importlib.metadata

    # 获取已安装的关键依赖包版本
    key_packages = [
        "fastapi", "uvicorn", "sqlalchemy", "pydantic",
        "PyJWT", "passlib", "alembic", "openpyxl",
    ]
    packages = {}
    for pkg_name in key_packages:
        try:
            packages[pkg_name] = importlib.metadata.version(pkg_name)
        except Exception:
            packages[pkg_name] = "未安装"

    return {
        "success": True,
        "data": {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "cwd": os.getcwd(),
            "packages": packages,
            "env_mode": os.environ.get("ENV", "production"),
        },
    }


@router.get("/version", summary="获取系统版本信息")
async def get_version_info():
    """获取当前系统版本及发布信息"""
    return {
        "code": 200,
        "success": True,
        "message": "成功",
        "data": {
            "version": getattr(settings, "PROJECT_VERSION", "1.1.0"),
            "name": "帮扶管理信息系统",
            "codename": "帮扶振兴",
            "release_date": "2026-04-25",
            "description": "面向帮扶乡村工作的综合管理平台",
            "copyright": "2025-2026",
            "license": "内部使用",
        },
    }
