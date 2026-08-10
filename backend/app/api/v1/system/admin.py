"""
系统管理员专用API
提供系统配置、备份恢复、系统监控等功能
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.models.user import User
from app.utils.paths import get_backup_directory, get_database_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["系统管理"])


# ==================== Pydantic 模型 ====================


class SystemInfo(BaseModel):
    """系统信息"""

    version: str
    database_size: int
    user_count: int
    organization_count: int
    project_count: int
    village_count: int
    uptime: str


class BackupInfo(BaseModel):
    """备份信息"""

    filename: str
    size: int
    created_at: str


class SystemConfig(BaseModel):
    """系统配置"""

    system_name: Optional[str] = None
    max_login_attempts: Optional[int] = None
    session_timeout: Optional[int] = None
    password_expiry_days: Optional[int] = None


# ==================== API 端点 ====================


@router.get("/info", response_model=SystemInfo)
async def get_system_info(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取系统信息"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    db_path = get_database_path()
    db_size = db_path.stat().st_size if db_path.exists() else 0

    # 统计各类数据数量
    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.village import Village

    user_count = db.query(User).count()
    org_count = db.query(Organization).count()
    project_count = db.query(Project).count()
    village_count = db.query(Village).count()

    return {
        "version": settings.PROJECT_VERSION,
        "database_size": db_size,
        "user_count": user_count,
        "organization_count": org_count,
        "project_count": project_count,
        "village_count": village_count,
        "uptime": "运行中",
    }


@router.post("/backup")
async def create_backup(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """创建数据库备份"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    try:
        db_path = get_database_path()
        backup_dir = get_backup_directory()
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = backup_dir / backup_filename

        # 复制数据库文件（直接操作，让异常自然抛出）
        try:
            shutil.copy2(db_path, backup_path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="数据库文件不存在")

        return {
            "success": True,
            "message": "备份创建成功",
            "data": {
                "filename": backup_filename,
                "size": backup_path.stat().st_size,
                "created_at": datetime.now().isoformat(),
            },
        }
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@router.get("/backups")
async def list_backups(current_user=Depends(get_current_user)):
    """获取备份列表"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    backup_dir = get_backup_directory()

    if not backup_dir.exists():
        return ok_list([], 0)

    backups = []
    for backup_file in backup_dir.glob("backup_*.db"):
        stat = backup_file.stat()
        backups.append(
            {
                "filename": backup_file.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    # 按创建时间倒序排序
    backups.sort(key=lambda x: x["created_at"], reverse=True)

    return ok_list(backups, len(backups))


@router.post("/restore")
async def restore_backup(
    filename: str = Query(..., description="备份文件名"),
    current_user=Depends(get_current_user),
):
    """恢复数据库备份"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    # 安全检查：防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="无效的文件名")

    try:
        db_path = get_database_path()
        backup_dir = get_backup_directory()
        backup_path = backup_dir / filename

        # 确保文件在实际备份目录内（防御：realpath 检查）
        if not str(backup_path.resolve()).startswith(str(backup_dir.resolve())):
            raise HTTPException(status_code=400, detail="无效的文件名")

        # 直接操作，让异常自然抛出
        try:
            # 备份当前数据库
            if db_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safety_backup = db_path.parent / f"{db_path.stem}_before_restore_{timestamp}.db"
                shutil.copy2(db_path, safety_backup)

            # 恢复备份
            shutil.copy2(backup_path, db_path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="备份文件不存在")

        return {"success": True, "message": "数据库恢复成功"}
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


@router.delete("/backups/{filename}")
async def delete_backup(filename: str, current_user=Depends(get_current_user)):
    """删除备份文件"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    # 安全检查：防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="无效的文件名")

    backup_dir = get_backup_directory()
    backup_path = backup_dir / filename

    # 确保文件在实际备份目录内（防御：realpath 检查）
    if not str(backup_path.resolve()).startswith(str(backup_dir.resolve())):
        raise HTTPException(status_code=400, detail="无效的文件名")

    try:
        backup_path.unlink()
        return {"success": True, "message": "备份删除成功"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/config")
async def get_system_config(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """获取系统配置（从 system_configs 表读取，回退到默认值）"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    from app.services.system_config_service import SystemConfigService

    svc = SystemConfigService(db)
    return {
        "success": True,
        "data": {
            "system_name": svc.get("system_name", "帮扶管理信息系统"),
            # svc.get(key, default) 保留两参数调用契约（兼容 mock）；
            # 额外用 ``or`` 防御配置值显式为 None 时 int(None) 抛 TypeError。
            "max_login_attempts": int(svc.get("max_login_attempts", "5") or "5"),
            "session_timeout": int(svc.get("session_timeout", "480") or "480"),
            "password_expiry_days": int(svc.get("password_expiry_days", "90") or "90"),
        },
    }


@router.put("/config")
async def update_system_config(
    config: SystemConfig,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新系统配置（持久化到 system_configs 表）"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    from app.services.system_config_service import SystemConfigService

    svc = SystemConfigService(db)

    if config.system_name is not None:
        svc.set("system_name", config.system_name, "系统名称")
    if config.max_login_attempts is not None:
        svc.set("max_login_attempts", config.max_login_attempts, "最大登录尝试次数")
    if config.session_timeout is not None:
        svc.set("session_timeout", config.session_timeout, "会话超时时间（分钟）")
    if config.password_expiry_days is not None:
        svc.set("password_expiry_days", config.password_expiry_days, "密码过期天数")

    import logging as _logging

    _logging.getLogger(__name__).info(
        f"系统配置已更新，操作人: {getattr(current_user, 'username', None) or '未知用户'}"
    )
    return {"success": True, "message": "系统配置更新成功"}


@router.post("/clear-cache")
async def clear_cache(current_user=Depends(get_current_user)):
    """清理系统缓存"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    try:
        from app.core.cache import cache_manager

        cache_manager.clear()

        # 清除各模块独立的 diskcache 实例
        try:
            from app.api.v1.data.data.dashboard import invalidate_dashboard_cache

            invalidate_dashboard_cache()
        except Exception as e:  # pragma: no cover
            logger.warning("清理 dashboard 缓存失败: %s", e)

        try:
            from app.api.v1.map import invalidate_map_cache

            invalidate_map_cache()
        except Exception as e:  # pragma: no cover
            logger.warning("清理 map 缓存失败: %s", e)

        return {"success": True, "message": "缓存清理成功"}
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.get("/logs")
async def get_system_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    """获取系统日志"""
    require_admin(current_user, error_message="仅超级管理员可执行此操作")

    log_file = Path(settings.LOG_FILE)
    if not log_file.exists():
        return ok_list([], 0)

    try:
        from collections import deque

        # 使用 deque 高效读取最后 N 行，避免加载整个文件到内存
        max_lines_needed = page * page_size
        with open(log_file, "r", encoding="utf-8") as f:
            # 只保留需要的行数，自动丢弃更早的行
            recent_lines = deque(f, maxlen=max_lines_needed)

        # 转换为列表并倒序（最新的在前）
        lines = list(recent_lines)
        lines.reverse()

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_lines = lines[start:end]

        # 获取总行数（需要完整扫描，但不加载到内存）
        with open(log_file, "r", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)

        return ok_list(
            [{"line": line.strip()} for line in page_lines],
            total_lines,
            page=page,
            page_size=page_size,
        )
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")


@router.post("/db-optimize", summary="一键数据库优化")
async def optimize_database(
    current_user=Depends(get_current_user),
):
    """执行 WAL checkpoint + PRAGMA optimize，返回优化前后空间对比"""
    require_admin(current_user, error_message="仅管理员可执行数据库优化")
    import os
    import sqlite3
    from urllib.parse import unquote
    from app.core.database import engine

    db_url = str(engine.url)
    if not db_url.startswith("sqlite"):
        raise HTTPException(status_code=400, detail="仅支持 SQLite 数据库")

    # 提取文件路径：sqlite:///path/to/db, sqlite://path, sqlite:path
    if ":///" in db_url:
        db_path = db_url.split(":///", 1)[1]
    elif "://" in db_url:
        db_path = db_url.split("://", 1)[1]
    elif ":" in db_url:
        db_path = db_url.split(":", 1)[1]
    else:
        db_path = db_url

    # :memory: 不支持文件级优化
    if db_path == ":memory:" or db_path.startswith(":memory"):
        raise HTTPException(status_code=400, detail="内存数据库不支持文件优化")

    # 解码 URL 编码字符（空格、中文路径等）
    db_path = unquote(db_path)

    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="数据库文件不存在")

    size_before = os.path.getsize(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    cursor.execute("PRAGMA optimize")
    conn.close()
    size_after = os.path.getsize(db_path)

    saved = size_before - size_after
    return {
        "success": True,
        "message": f"优化完成，{'释放' if saved >= 0 else '增加'} {abs(saved) / 1024:.1f} KB",
        "size_before_kb": round(size_before / 1024, 1),
        "size_after_kb": round(size_after / 1024, 1),
        "saved_kb": round(saved / 1024, 1),
    }


# ==================== 用户会话管理 ====================


@router.get("/users/{user_id}/sessions")
async def list_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """查看用户活跃会话（基于 token 黑名单反向推断）"""
    require_admin(current_user, error_message="仅管理员可查看用户会话")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 安全获取黑名单计数：优先用内存计数，失败时回退到 DB 查询
    try:
        from app.core.token_blacklist import count as blacklist_count_fn
        blacklisted = blacklist_count_fn()
    except Exception:
        try:
            from app.models.token_blacklist import TokenBlacklist
            blacklisted = db.query(TokenBlacklist).count()
        except Exception:
            blacklisted = 0

    return success_response(data={
        "user_id": user_id,
        "username": user.username,
        "blacklisted_tokens": blacklisted,
        "sessions": [],
        "message": "单机部署模式下会话信息有限，仅显示 token 黑名单统计",
    })


@router.post("/users/{user_id}/sessions/{session_id}/revoke")
async def revoke_user_session(
    user_id: int,
    session_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """强制登出用户（将 token 加入黑名单）"""
    require_admin(current_user, error_message="仅管理员可强制登出用户")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    from app.core.token_manager import revoke_token

    if not revoke_token(session_id, reason="admin_force_logout"):
        raise HTTPException(status_code=400, detail="无效的会话 Token，无法强制登出")
    logger.info("管理员 %s 强制登出用户 %s (session: %s)", current_user.username, user.username, session_id)
    return success_response(message=f"已强制登出用户 {user.username}")


@router.post("/users/{user_id}/two-factor/reset")
async def reset_user_two_factor(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """重置用户双因素认证"""
    require_admin(current_user, error_message="仅管理员可重置双因素认证")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    from app.models.two_factor_auth import TwoFactorAuth

    tfa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
    if tfa:
        tfa.enabled = False
        tfa.secret_key = ""
        tfa.backup_codes = None
        tfa.verified_at = None
        db.commit()
        logger.info("管理员 %s 重置用户 %s 的双因素认证", current_user.username, user.username)
        return success_response(message=f"已重置用户 {user.username} 的双因素认证")

    return success_response(message=f"用户 {user.username} 未启用双因素认证，无需重置")
