"""
系统备份 API
提供数据库备份的创建、列表、统计、恢复和计划管理功能
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import get_current_user
from app.core.permission_utils import require_admin
from app.services.backup_service import BackupService, get_backup_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["备份管理"])


# ==================== Pydantic 模型 ====================

class CreateBackupRequest(BaseModel):
    """创建备份请求"""
    description: str = Field("手动备份", description="备份描述")
    include_uploads: bool = Field(True, description="是否包含上传文件")
    password: Optional[str] = Field(None, description="加密密码（可选）")
    target_dir: Optional[str] = Field(None, description="备份目标目录（可选，缺省用配置 backup_target_dir，再缺省用应用数据目录）")


class RestoreBackupRequest(BaseModel):
    """恢复备份请求"""
    filename: str = Field(..., description="备份文件名")
    password: Optional[str] = Field(None, description="加密密码（加密备份必需）")


class DeleteBackupRequest(BaseModel):
    """删除备份请求"""
    filename: str = Field(..., description="备份文件名")


def _resolve_auto_backup_password(provided: Optional[str]) -> Optional[str]:
    """恢复加密备份时的密码兜底。

    自动备份的加密口令是运行时持久化的随机密钥（BACKUP_ENCRYPTION_KEY，
    见 backup_scheduler.auto_backup_job），管理员无法得知其值。
    恢复时若未提供密码，自动尝试该密钥，保证自动备份可恢复；
    密钥不可用时返回 None（明文备份与用户手动设置的密码不受影响）。
    """
    if provided:
        return provided
    try:
        from app.utils.runtime_secrets import get_or_create_secret

        return get_or_create_secret("BACKUP_ENCRYPTION_KEY")
    except Exception:  # pragma: no cover - 密钥存储异常时按未提供处理
        return None


class BackupScheduleUpdate(BaseModel):
    """备份计划更新"""
    enabled: bool = Field(..., description="是否启用自动备份")
    schedule: Optional[str] = Field(None, description="Cron 表达式或时间间隔")
    keep_count: Optional[int] = Field(10, description="保留备份数量")


async def _authenticate_backup_request(request: Request) -> str:
    """备份创建鉴权：本机内部密钥 或 管理员 JWT 二选一。

    Electron 主进程的定时/托盘自动备份无 JWT，携带启动时注入环境变量的
    X-Internal-Backup 密钥（与 shutdown 端点同模式）；普通用户走 JWT 管理员校验。

    Returns: 操作人标识（内部通道返回 "internal-backup"）
    """
    import os

    internal_key = os.getenv("INTERNAL_BACKUP_KEY", "")
    if internal_key and request.headers.get("X-Internal-Backup", "") == internal_key:
        return "internal-backup"

    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.security import get_current_user

    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="未提供认证凭证")
    user = await get_current_user(HTTPAuthorizationCredentials(scheme=scheme, credentials=token))
    require_admin(user, error_message="仅超级管理员可创建备份")
    return getattr(user, "username", "unknown")


# ==================== API 端点 ====================


@router.post("", summary="创建数据库备份")
async def create_backup(
    body: CreateBackupRequest,
    request: Request,
    db: Session = Depends(get_db),
    operator: str = Depends(_authenticate_backup_request),
):
    """创建系统数据库备份

    将当前数据库和上传文件打包为 ZIP 备份文件。
    支持可选的 AES-256 加密保护。
    需要管理员权限（或 Electron 内部备份密钥）。
    """

    try:
        # 目标目录解析: 请求参数 > 配置 backup_target_dir > 应用数据目录
        from app.services.system_config_service import get_config

        svc = get_backup_service(db)
        target_dir = body.target_dir or get_config("backup_target_dir", "")
        if target_dir:
            from app.utils.drive_detect import ensure_target_dir

            if not ensure_target_dir(target_dir):
                raise HTTPException(status_code=400, detail=f"备份目标目录不可写: {target_dir}")
            svc = BackupService(db, backup_dir=target_dir)
        record = svc.create_backup(
            description=body.description,
            include_uploads=body.include_uploads,
            password=body.password,
        )

        logger.info(
            "备份已创建: %s，操作人: %s",
            record.file_name, operator,
        )

        return {
            "success": True,
            "message": "备份已创建",
            "data": {
                "backup_id": record.backup_id,
                "file_name": record.file_name,
                "file_path": record.file_path,
                "file_size": record.file_size,
                "description": record.description,
                "created_at": record.created_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建备份失败: %s", e)
        raise HTTPException(status_code=500, detail=f"创建备份失败: {str(e)}")


@router.get("", summary="获取备份列表")
async def list_backups(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取所有数据库备份文件列表

    按创建时间倒序排列，包含文件名、大小、描述等元信息。
    """
    try:
        svc = get_backup_service(db)
        records = svc.list_backups()

        items = []
        for r in records:
            # 检测是否为加密备份（读文件头标记），供前端决定是否提示输入解密密码
            is_encrypted = False
            try:
                from app.services.backup_service import BackupService

                with open(r.file_path, "rb") as _f:
                    is_encrypted = (
                        _f.read(len(BackupService._ENCRYPTED_MARKER))
                        == BackupService._ENCRYPTED_MARKER
                    )
            except Exception:
                # 文件缺失/不可读/记录为 mock 路径时按未加密处理
                is_encrypted = False

            items.append({
                "backup_id": r.backup_id,
                "file_name": r.file_name,
                "file_path": r.file_path,
                "file_size": r.file_size,
                "description": r.description,
                "created_at": r.created_at.isoformat(),
                "backup_type": r.backup_type,
                "is_encrypted": is_encrypted,
            })

        return ok_list(items=items, total=len(items))
    except Exception as e:
        logger.error("获取备份列表失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取备份列表失败: {str(e)}")


@router.get("/stats", summary="获取备份统计")
async def get_backup_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取备份统计信息

    返回备份总数、总大小、最早/最新备份时间等统计数据。
    """
    try:
        svc = get_backup_service(db)
        stats = svc.get_backup_statistics()

        # 获取调度器状态
        schedule_enabled = os.getenv("AUTO_BACKUP_ENABLED", "false").lower() == "true"

        return {
            "success": True,
            "data": {
                "totalBackups": stats.get("total_backups", 0),
                "totalSize": stats.get("total_size", 0),
                "totalSizeMb": stats.get("total_size_mb", 0),
                "fullBackups": stats.get("full_backups", 0),
                "incrementalBackups": stats.get("incremental_backups", 0),
                "lastBackup": stats.get("newest_backup"),
                "oldestBackup": stats.get("oldest_backup"),
                "scheduleEnabled": schedule_enabled,
            },
        }
    except Exception as e:
        logger.error("获取备份统计失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取备份统计失败: {str(e)}")


@router.get("/dirs", summary="检测可用备份目标目录（U盘/移动硬盘）")
async def list_backup_dirs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """枚举可用的备份目标目录（可移动磁盘/固定盘/网络盘），供前端备份目标选择。

    单机场景：把备份写到 U 盘/移动硬盘可防止本机硬盘故障导致数据丢失。
    """
    try:
        from app.services.system_config_service import get_config
        from app.utils.drive_detect import list_backup_dirs as _list_dirs

        dirs = _list_dirs()
        # 当前配置的目标目录若不在列表中则追加（可能尚未插入磁盘）
        current = get_config("backup_target_dir", "")
        paths = {d["path"] for d in dirs}
        if current and current not in paths:
            dirs.append({"path": current, "type": "configured", "available": False})

        return {
            "success": True,
            "data": {
                "dirs": dirs,
                "current": current,
                "default_dir": os.environ.get("BACKUP_DEFAULT_DIR", ""),
            },
        }
    except Exception as e:
        logger.error("检测备份目录失败: %s", e)
        raise HTTPException(status_code=500, detail=f"检测备份目录失败: {str(e)}")


@router.put("/target", summary="设置备份目标目录")
async def set_backup_target(
    body: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """持久化备份目标目录（写入 SystemConfig）"""
    try:
        from app.services.system_config_service import set_config
        from app.utils.drive_detect import ensure_target_dir

        target = (body.get("target_dir") or "").strip()
        if target and not ensure_target_dir(target):
            raise HTTPException(status_code=400, detail=f"目标目录不可用或不可写: {target}")
        set_config("backup_target_dir", target, "备份目标目录（单机防丢失）")
        return {"success": True, "message": "备份目标已更新", "data": {"target_dir": target}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("设置备份目标失败: %s", e)
        raise HTTPException(status_code=500, detail=f"设置备份目标失败: {str(e)}")


@router.get("/schedule", summary="获取备份计划配置")
async def get_backup_schedule(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取自动备份计划配置

    自动备份已永久禁用（防止生成大文件占用磁盘空间）。
    备份请通过管理界面手动执行。
    """
    return {
        "success": True,
        "data": {
            "enabled": False,
            "schedule": None,
            "keepCount": 3,
            "nextRun": None,
            "message": "自动备份已禁用。请通过备份管理页面手动创建备份。",
        },
    }


@router.put("/schedule", summary="更新备份计划配置")
async def update_backup_schedule(
    body: BackupScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新自动备份计划配置（已弃用——自动备份已永久禁用）

    自动备份已禁用，此端点保留仅用于前端兼容。
    """
    return {
        "success": True,
        "message": "自动备份已永久禁用以节省磁盘空间。请通过备份管理页面手动创建备份。",
        "data": {"enabled": False, "schedule": None, "keepCount": 3},
    }


@router.delete("/{filename}", summary="删除指定备份")
async def delete_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定的备份文件

    同时删除磁盘上的备份文件和数据库中的记录。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可删除备份")

    try:
        svc = get_backup_service(db)
        # 查找匹配文件名的备份
        records = svc.list_backups()
        target = None
        for r in records:
            if r.file_name == filename:
                target = r
                break

        if not target:
            raise HTTPException(status_code=404, detail=f"备份文件 '{filename}' 不存在")

        success = svc.delete_backup(target.backup_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除备份失败")

        logger.info(
            "备份已删除: %s，操作人: %s",
            filename, getattr(current_user, "username", "unknown"),
        )

        return {"success": True, "message": f"备份文件 '{filename}' 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除备份失败: %s", e)
        raise HTTPException(status_code=500, detail=f"删除备份失败: {str(e)}")


@router.get("/download/{filename}", summary="下载备份文件")
async def download_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """下载指定的备份文件

    返回备份 ZIP 文件供本地保存或迁移使用。
    需要管理员权限（备份含全库数据）。
    """
    require_admin(current_user, error_message="仅管理员可下载备份文件")

    from fastapi.responses import FileResponse
    from app.utils.paths import get_backup_path

    backup_dir = str(get_backup_path())
    file_path = os.path.join(backup_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"备份文件 '{filename}' 不存在")

    # 安全检查：确保路径在备份目录内
    real_path = os.path.realpath(file_path)
    real_backup_dir = os.path.realpath(backup_dir)
    if not (real_path == real_backup_dir or real_path.startswith(real_backup_dir + os.sep)):
        raise HTTPException(status_code=403, detail="禁止访问备份目录外的文件")

    logger.info(
        "备份文件下载: %s，操作人: %s",
        filename, getattr(current_user, "username", "unknown"),
    )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip",
    )


@router.get("/preview/{filename}", summary="预览备份包内容")
async def preview_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """读取备份 ZIP 的文件清单与元信息（backup_info.json），供前端预览弹窗使用。

    返回 {filename, size, files: [{name, size}], meta}；加密/损坏的 ZIP 返回 400。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可预览备份")

    import json
    import zipfile

    from app.utils.paths import get_backup_path

    backup_dir = str(get_backup_path())
    file_path = os.path.join(backup_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"备份文件 '{filename}' 不存在")

    # 安全检查：确保路径在备份目录内
    real_path = os.path.realpath(file_path)
    real_backup_dir = os.path.realpath(backup_dir)
    if not (real_path == real_backup_dir or real_path.startswith(real_backup_dir + os.sep)):
        raise HTTPException(status_code=403, detail="禁止访问备份目录外的文件")

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            files = [
                {"name": info.filename, "size": info.file_size}
                for info in zf.infolist()
            ]
            try:
                meta = json.loads(zf.read("backup_info.json"))
            except Exception:
                # 无元信息文件或内容加密时降级为空 dict
                meta = {}
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="备份文件损坏或已加密，无法预览")

    return {
        "success": True,
        "data": {
            "filename": filename,
            "size": os.path.getsize(file_path),
            "files": files,
            "meta": meta,
        },
    }


@router.post("/verify/{filename}", summary="验证备份文件完整性")
async def verify_backup(
    filename: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """验证指定备份文件的完整性

    检查 ZIP 文件是否损坏、数据库文件是否可以正常打开、
    以及备份内文件的哈希校验。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可验证备份")

    try:
        from app.utils.paths import get_backup_path

        backup_dir = str(get_backup_path())
        file_path = os.path.join(backup_dir, filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"备份文件 '{filename}' 不存在")

        # 安全检查：确保路径在备份目录内
        real_path = os.path.realpath(file_path)
        real_backup_dir = os.path.realpath(backup_dir)
        if not (real_path == real_backup_dir or real_path.startswith(real_backup_dir + os.sep)):
            raise HTTPException(status_code=403, detail="禁止访问备份目录外的文件")

        svc = get_backup_service(db)
        result = svc.verify_backup(file_path)

        logger.info(
            "备份验证: %s，结果: %s，操作人: %s",
            filename, result.get("status"), getattr(current_user, "username", "unknown"),
        )

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("验证备份失败: %s", e)
        raise HTTPException(status_code=500, detail=f"验证备份失败: {str(e)}")


@router.post("/restore", summary="从备份恢复系统")
async def restore_backup(
    body: RestoreBackupRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """从指定的备份文件恢复系统数据

    此操作将覆盖当前数据库和上传文件。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可恢复备份")

    try:
        from app.utils.paths import get_backup_path

        backup_dir = str(get_backup_path())
        file_path = os.path.join(backup_dir, body.filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"备份文件 '{body.filename}' 不存在")

        svc = get_backup_service(db)
        result = svc.restore_backup(file_path, password=_resolve_auto_backup_password(body.password))

        logger.warning(
            "系统已从备份恢复: %s，操作人: %s",
            body.filename, getattr(current_user, "username", "unknown"),
        )

        # 恢复后建议重启服务以回收 SQLite 连接池
        logger.warning(
            "系统已从备份恢复，建议立即重启应用以回收数据库连接池。"
            "恢复文件: %s，操作人: %s",
            body.filename, getattr(current_user, "username", "unknown"),
        )

        return {
            "success": True,
            "message": "系统恢复成功（建议重启应用以确保数据库连接正确）",
            "data": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("恢复备份失败: %s", e)
        raise HTTPException(status_code=500, detail=f"恢复备份失败: {str(e)}")


@router.post("/upload-restore", summary="上传备份文件并恢复系统")
async def upload_and_restore(  # noqa: C901 - 恢复流程多分支校验,拆分风险高
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """上传备份 ZIP 文件并立即用于恢复系统数据

    适用于跨机器迁移场景：用户在其他机器导出备份后，通过此接口上传并恢复。
    支持加密备份（需提供创建备份时设置的密码）。
    上传的文件会临时保存到备份目录，恢复完成后自动删除。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可上传恢复备份")

    # 安全校验：文件名不得包含路径分隔符，防止路径遍历
    original_name = file.filename or "uploaded_backup.zip"
    if "/" in original_name or "\\" in original_name or ".." in original_name:
        raise HTTPException(status_code=400, detail="非法的文件名")

    # 仅允许 ZIP 文件
    if not original_name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持 ZIP 格式的备份文件")

    file_path = None  # 预初始化，便于异常时清理
    try:
        import time
        import zipfile

        from app.utils.paths import get_backup_path

        backup_dir = str(get_backup_path())
        os.makedirs(backup_dir, exist_ok=True)

        # 使用时间戳前缀避免覆盖已有备份
        safe_name = f"upload_{int(time.time())}_{original_name}"
        file_path = os.path.join(backup_dir, safe_name)

        # 确保最终路径仍在备份目录内
        real_path = os.path.realpath(file_path)
        real_backup_dir = os.path.realpath(backup_dir)
        if not (real_path == real_backup_dir or real_path.startswith(real_backup_dir + os.sep)):
            raise HTTPException(status_code=403, detail="禁止写入备份目录外的路径")

        # 分块流式落盘（避免大备份包整体读入内存导致 OOM），并施加防御性大小上限
        _MAX_RESTORE_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024  # 10GB
        _CHUNK_SIZE = 8 * 1024 * 1024
        total = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_RESTORE_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="备份包超过大小限制（10GB）")
                f.write(chunk)

        logger.info(
            "备份文件已上传: %s (%d bytes)，操作人: %s",
            safe_name, total, getattr(current_user, "username", "unknown"),
        )

        # ── 落盘后校验：拒绝明显无效的备份包（fail fast，避免进入恢复流程） ──
        # 1. 加密备份：必须提供密码
        from app.services.backup_service import BackupService

        with open(file_path, "rb") as _f:
            _head = _f.read(len(BackupService._ENCRYPTED_MARKER))
        if _head == BackupService._ENCRYPTED_MARKER:
            if not password:
                password = _resolve_auto_backup_password(None)
                if not password:
                    raise HTTPException(status_code=400, detail="备份文件已加密，请提供解密密码")
        else:
            # 2. 明文 ZIP：必须是有效 ZIP 且包含数据库文件
            try:
                with zipfile.ZipFile(file_path, "r") as _zf:
                    _names = {n.replace("\\", "/") for n in _zf.namelist()}
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="上传的文件不是有效的备份包（ZIP 已损坏）")
            if "data/rural_revitalization.db" not in _names:
                raise HTTPException(
                    status_code=400,
                    detail="上传的文件不是有效的备份包（缺少数据库文件 data/rural_revitalization.db）",
                )

        # 调用恢复逻辑
        svc = get_backup_service(db)
        result = svc.restore_backup(file_path, password=password)

        logger.warning(
            "系统已从上传的备份恢复: %s，操作人: %s",
            safe_name, getattr(current_user, "username", "unknown"),
        )

        # 恢复完成后删除上传的临时文件（释放磁盘空间）
        try:
            os.remove(file_path)
        except OSError:
            logger.warning("临时备份文件删除失败: %s", file_path)

        return {
            "success": True,
            "message": "上传恢复成功（建议重启应用以确保数据库连接正确）",
            "data": result,
        }
    except ValueError as e:
        # 与通用异常一致：清理已保存的临时文件，避免磁盘泄漏
        if file_path:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # 校验/大小限制/路径逃逸等拒绝分支同样清理已落盘的临时文件
        if file_path:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        raise
    except Exception as e:
        logger.error("上传恢复备份失败: %s", e)
        # 清理已保存的临时文件（若存在）
        if file_path:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        # 用户上传的备份包内容损坏（解密后非 ZIP/缺文件）→ 400 而非 500
        from app.services.backup_service import BackupRestoreError
        if isinstance(e, BackupRestoreError):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=f"上传恢复备份失败: {str(e)}")
