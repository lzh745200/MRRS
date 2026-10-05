"""数据同步API路由"""

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from app.core.exceptions import AppError, NotFoundException, BusinessError
from app.core.permission_utils import require_admin
from app.core.response import ok_list
from app.core.security import get_current_user
from app.core.upload_security import sanitize_filename
from app.models.user import User
from app.services.data_sync_service import data_sync_service, ExportConfig


class ExportEncryptedRequest(BaseModel):
    """加密导出请求体"""

    password: str
    modules: Optional[List[str]] = None
    export_type: str = "full"
    since: Optional[str] = None


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-sync", tags=["数据同步"])

# 允许上传的文件扩展名白名单
ALLOWED_UPLOAD_EXTENSIONS = {".zip", ".rrs"}

# 分块读取缓冲区大小 (1MB)
CHUNK_SIZE = 1024 * 1024


def _safe_filename(filename: str) -> str:
    """净化文件名，防止路径遍历攻击"""
    # sanitize_filename 已剥离目录成分；再用 Path(...).name 兜底一次，
    # 保证任何平台语义下都不会有路径分隔符残留到 upload_dir / name 拼接中
    safe_name = Path(sanitize_filename(filename)).name
    # 验证扩展名白名单
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")
    return safe_name


async def _save_upload_file(file: UploadFile, upload_dir: Path, default_name: str) -> Path:
    """
    分块保存上传的文件，避免大文件占用过多内存

    Args:
        file: 上传的文件对象
        upload_dir: 上传目录
        default_name: 默认文件名（当 file.filename 为空时使用）

    Returns:
        保存后的文件路径

    深审 LIVE：写盘中途失败（磁盘写满/客户端断流）时本函数直接抛出，调用方
    的 file_path 仍是 None（赋值发生在返回之后），finally 清理分支永不执行
    —— 半成品文件永久残留在 uploads 目录。这里在失败点就地清理自身产物。
    """
    safe_name = _safe_filename(file.filename or default_name)
    # R18：文件名必须唯一。此前直接用客户端原文件名（缺省时固定为 upload.zip），
    # 两个并发导入会写同一物理路径——后写者截断前写者正在读取的文件，
    # 先到者把后到者的数据当自己的包导入（静默数据错乱），且 finally 清理会
    # 删掉对方刚写入的文件。加 uuid 前缀保证唯一，保留原名便于排查。
    file_path = upload_dir / f"{uuid.uuid4().hex}_{safe_name}"

    try:
        with open(file_path, "wb") as f:
            # 分块读取，避免一次性读入内存
            while chunk := await file.read(CHUNK_SIZE):
                f.write(chunk)
    except Exception:
        _cleanup_file(file_path)
        raise

    return file_path


def _cleanup_file(file_path: Path) -> None:
    """清理临时文件（忽略错误）"""
    try:
        file_path.unlink()
    except Exception:
        logger.debug("清理临时文件失败")


@router.post("/export")
async def export_data(
    since: Optional[str] = None,
    modules: Optional[List[str]] = None,
    include_files: bool = False,
    current_user: User = Depends(get_current_user),
):
    """
    导出增量数据包（ZIP格式，无加密）
    """
    require_admin(current_user, error_message="仅管理员可执行数据同步操作")
    try:
        since_time = None
        if since:
            try:
                since_time = datetime.fromisoformat(since)
            except ValueError:
                raise HTTPException(status_code=400, detail="时间格式错误")

        result = await data_sync_service.export_incremental(
            config=ExportConfig(
                since=since_time,
                modules=modules,
                include_files=include_files,
                user_id=getattr(current_user, "id", None),
                user_name=getattr(current_user, "username", "system"),
            )
        )
        return result
    except Exception as e:
        raise BusinessError(f"导出数据失败: {str(e)}")


@router.post("/export-encrypted")
async def export_encrypted_data(
    body: ExportEncryptedRequest,
    current_user: User = Depends(get_current_user),
):
    """
    导出加密数据包（.rrs格式，JSON body）
    """
    require_admin(current_user, error_message="仅管理员可执行数据同步操作")
    try:
        export_type = body.export_type
        password = body.password
        modules = body.modules
        since = body.since

        if export_type not in ["full", "selective"]:
            raise HTTPException(status_code=400, detail="export_type 必须是 'full' 或 'selective'")

        since_time = None
        if since:
            try:
                since_time = datetime.fromisoformat(since)
            except ValueError:
                raise HTTPException(status_code=400, detail="时间格式错误")

        tables_list = modules  # frontend sends "modules" as table list

        result = await data_sync_service.export_encrypted(
            export_type=export_type,
            tables=tables_list,
            password=password,
            since=since_time,
            user_id=getattr(current_user, "id", None),
            user_name=getattr(current_user, "username", "system"),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise BusinessError(f"导出数据失败: {str(e)}")


@router.get("/export/download/{package_name}")
async def download_export_package(
    package_name: str,
    current_user: User = Depends(get_current_user),
):
    """下载导出的数据包"""
    import re

    # 路径遍历防护：仅允许字母数字和下划线横线点
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", package_name):
        raise HTTPException(status_code=400, detail="无效的数据包名称")
    try:
        # 与 DataSyncService.sync_dir 同源（get_app_data_dir()/data_sync）。
        # 历史缺陷：相对路径 Path("data_sync") 依赖进程工作目录——开发态碰巧
        # 重合可过测试，打包/Electron 注入环境下与导出写入目录分叉 → 下载恒
        # 400/404（路径双源，同备份模块 2026-08-30 的病根）。
        base_dir = data_sync_service.sync_dir.resolve()
        # 尝试 .zip 格式
        package_path = (base_dir / f"{package_name}.zip").resolve()
        if not package_path.exists():
            # 尝试 .rrs 格式
            package_path = (base_dir / f"{package_name}.rrs").resolve()
        # 路径边界检查
        if not str(package_path).startswith(str(base_dir)):
            raise HTTPException(status_code=400, detail="无效的数据包路径")
        if not package_path.exists():
            raise NotFoundException("数据包不存在")

        media_type = "application/zip" if package_path.suffix == ".zip" else "application/octet-stream"

        return FileResponse(path=str(package_path), filename=package_path.name, media_type=media_type)
    except (HTTPException, AppError):
        # 深审 LIVE：数据包不存在时抛 NotFoundException(404)（AppError 子类），
        # 被下面的通用 except 包装成 BusinessError（默认 400）—— 404 语义丢失，
        # 前端把"文件不存在"当成"请求有误"。HTTPException/AppError 原样透传。
        raise
    except Exception as e:
        raise BusinessError(f"下载数据包失败: {str(e)}")


@router.post("/import")
async def import_data(
    file: UploadFile = File(...),
    strategy: str = Form("skip"),
    current_user: User = Depends(get_current_user),
):
    """导入数据包（ZIP格式，无加密）"""
    require_admin(current_user, error_message="仅管理员可执行数据同步操作")
    file_path: Path | None = None
    try:
        # 保存上传的文件（分块读取，避免内存占用）
        from app.utils.paths import get_app_data_dir

        upload_dir = get_app_data_dir() / "data_sync" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = await _save_upload_file(file, upload_dir, "upload.zip")

        # 导入数据
        result = await data_sync_service.import_package(
            package_path=str(file_path),
            strategy=strategy,
            user_id=getattr(current_user, "id", None),
            user_name=getattr(current_user, "username", "system"),
        )

        return result
    except Exception as e:
        raise BusinessError(f"导入数据失败: {str(e)}")
    finally:
        # 确保临时文件被清理
        if file_path:
            _cleanup_file(file_path)


@router.post("/import-encrypted")
async def import_encrypted_data(
    file: UploadFile = File(...),
    password: str = Form(...),
    strategy: str = Form("merge"),
    current_user: User = Depends(get_current_user),
):
    """导入加密数据包（.rrs格式）"""
    require_admin(current_user, error_message="仅管理员可执行数据同步操作")
    file_path: Path | None = None
    try:
        # 保存上传的文件（分块读取，避免内存占用）
        from app.utils.paths import get_app_data_dir

        upload_dir = get_app_data_dir() / "data_sync" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = await _save_upload_file(file, upload_dir, "upload.rrs")

        # 导入数据
        result = await data_sync_service.import_encrypted(
            package_path=str(file_path),
            password=password,
            strategy=strategy,
            user_id=getattr(current_user, "id", None),
            user_name=getattr(current_user, "username", "system"),
        )

        return result
    except Exception as e:
        raise BusinessError(f"导入加密数据失败: {str(e)}")
    finally:
        # 确保临时文件被清理
        if file_path:
            _cleanup_file(file_path)


@router.get("/conflicts/{sync_log_id}")
async def get_conflicts(
    sync_log_id: int,
    current_user: User = Depends(get_current_user),
):
    """获取冲突列表"""
    try:
        conflicts = await data_sync_service.get_conflicts(sync_log_id)
        return {"success": True, "data": conflicts, "count": len(conflicts)}
    except Exception as e:
        raise BusinessError(f"获取冲突列表失败: {str(e)}")


class ResolveConflictRequest(BaseModel):
    """解决冲突请求体。

    深审 LIVE：原实现把 conflict_id/resolution/merged_data 全部声明为查询参数，
    而前端（frontend/src/api/dataSync.ts → resolveConflict）发的是 JSON body，
    实际调用恒 422；merged_data 是 dict，查询参数也无法承载。
    """

    conflict_id: int
    resolution: str
    merged_data: Optional[dict] = None


@router.post("/resolve-conflict")
async def resolve_conflict(
    body: ResolveConflictRequest,
    current_user: User = Depends(get_current_user),
):
    """
    解决冲突
    """
    require_admin(current_user, error_message="仅管理员可执行数据同步操作")
    try:
        result = await data_sync_service.resolve_conflict(
            conflict_id=body.conflict_id,
            resolution=body.resolution,
            merged_data=body.merged_data,
            user_id=getattr(current_user, "id", None),
        )
        return result
    except Exception as e:
        raise BusinessError(f"解决冲突失败: {str(e)}")


@router.get("/logs")
async def get_sync_logs(
    sync_type: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """获取同步日志"""
    try:
        from app.core.database import get_db
        from app.models.data_sync import DataSyncLog

        db_gen = get_db()
        db = next(db_gen)

        try:
            query = db.query(DataSyncLog)
            if sync_type:
                query = query.filter(DataSyncLog.sync_type == sync_type)

            logs = query.order_by(DataSyncLog.created_at.desc()).limit(limit).all()

            items_list = [
                {
                    "id": log.id,
                    "sync_type": log.sync_type,
                    "status": log.status,
                    "package_name": log.package_name,
                    "total_records": log.total_records,
                    "success_records": log.success_records,
                    "failed_records": log.failed_records,
                    "conflicts_count": log.conflicts_count,
                    "created_at": log.created_at.isoformat(),
                    "completed_at": (log.completed_at.isoformat() if log.completed_at else None),
                    "user_name": log.user_name,
                }
                for log in logs
            ]
            return ok_list(items=items_list, total=len(items_list), page=1, page_size=limit)
        finally:
            db.close()

    except Exception as e:
        raise BusinessError(f"获取同步日志失败: {str(e)}")
