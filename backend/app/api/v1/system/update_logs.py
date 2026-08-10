"""
系统更新日志API
提供系统版本更新历史的查询、记录和管理功能
用于帮扶管理信息系统的版本追溯和升级管理
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import get_current_user
from app.core.config import settings
from app.services.update_log_service import UpdateLogService
from app.models.system_config import SystemUpdateLog
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/update-logs", tags=["更新日志"])


# ==================== Pydantic 模型 ====================

class UpdateLogCreate(BaseModel):
    """创建更新日志"""
    version: str = Field(..., description="版本号", min_length=1, max_length=50)
    description: str = Field(..., description="更新内容描述")
    updated_by: Optional[str] = Field(None, description="更新人")


class UpdateLogResponse(BaseModel):
    """更新日志响应"""
    id: str
    version: str
    description: str
    updated_by: Optional[str] = None
    created_at: str


class VersionHistoryInit(BaseModel):
    """版本历史初始化请求"""
    updated_by: Optional[str] = Field("system", description="初始化执行人")
    force: bool = Field(False, description="是否强制重新初始化")


# ==================== API 端点 ====================

@router.get("", summary="获取更新日志列表")
async def get_update_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    version: Optional[str] = Query(None, description="按版本号筛选"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取系统版本更新日志列表

    按时间倒序排列，支持按版本号筛选。
    记录系统从初始版本到当前的完整更新历程。
    """
    svc = UpdateLogService(db)

    if version:
        record = svc.get_update_by_version(version)
        items = [record.to_dict()] if record else []
        total = len(items)
    else:
        skip = (page - 1) * page_size
        records = svc.get_update_logs(skip=skip, limit=page_size, order_by_desc=True)
        items = [r.to_dict() for r in records]
        total = svc.get_update_count()

    return ok_list(items=items, total=total, page=page, page_size=page_size)


@router.get("/latest", summary="获取最新更新日志")
async def get_latest_update_log(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取最新的系统更新记录

    用于前端显示当前版本信息或检查是否有新版本。
    """
    svc = UpdateLogService(db)
    latest = svc.get_latest_update()

    if not latest:
        return {
            "success": True,
            "data": {
                "version": getattr(settings, "PROJECT_VERSION", "1.1.0"),
                "message": "暂无更新记录",
                "has_records": False,
            },
        }

    return {
        "success": True,
        "data": latest.to_dict(),
    }


@router.get("/{update_id}", summary="获取更新日志详情")
async def get_update_log_detail(
    update_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取指定更新日志的详细信息"""
    UpdateLogService(db)
    record = db.query(SystemUpdateLog).filter(SystemUpdateLog.id == update_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="更新日志不存在")

    return {"success": True, "data": record.to_dict()}


@router.post("", summary="创建更新日志")
async def create_update_log(
    body: UpdateLogCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """手动创建一条系统更新日志

    用于记录系统升级或功能变更。需要管理员权限。
    """
    from app.core.permission_utils import is_admin
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员可创建更新日志")

    svc = UpdateLogService(db)
    updated_by = body.updated_by or getattr(current_user, "username", "system")

    try:
        record = svc.record_update(
            version=body.version,
            description=body.description,
            updated_by=updated_by,
        )
        return {
            "success": True,
            "message": f"更新日志 {body.version} 已创建",
            "data": record.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建更新日志失败: {str(e)}")


@router.post("/initialize", summary="初始化版本历史")
async def initialize_version_history(
    body: VersionHistoryInit,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """初始化版本历史记录

    从预定义的版本历史数据批量导入所有历史版本的更新记录。
    适用于新系统部署后的首次数据填充。需要管理员权限。
    """
    from app.core.permission_utils import is_admin
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行初始化操作")

    svc = UpdateLogService(db)
    updated_by = body.updated_by or getattr(current_user, "username", "system")

    try:
        result = svc.initialize_version_history(updated_by=updated_by, force=body.force)

        return {
            "success": True,
            "message": result["message"],
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"初始化版本历史失败: {str(e)}")


@router.post("/sync", summary="同步版本历史")
async def sync_version_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """同步版本历史数据

    检查预定义版本历史，补充数据库中缺失的版本记录。
    保留已有记录不变，仅追加新版本。需要管理员权限。
    """
    from app.core.permission_utils import is_admin
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行同步操作")

    svc = UpdateLogService(db)
    updated_by = getattr(current_user, "username", "system")

    try:
        result = svc.sync_version_history(updated_by=updated_by)

        return {
            "success": True,
            "message": result["message"],
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步版本历史失败: {str(e)}")


@router.delete("/{update_id}", summary="删除更新日志")
async def delete_update_log(
    update_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定的更新日志记录

    需要管理员权限。
    """
    from app.core.permission_utils import is_admin
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员可删除更新日志")

    record = db.query(SystemUpdateLog).filter(SystemUpdateLog.id == update_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="更新日志不存在")

    db.delete(record)
    safe_commit(db)

    logger.info(
        "更新日志 %s (版本 %s) 已被删除，操作人: %s",
        update_id,
        record.version,
        getattr(current_user, "username", "unknown"),
    )

    return {"success": True, "message": f"更新日志 {update_id} 已删除"}


@router.get("/check/version", summary="检查版本变更")
async def check_version_change(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """检查当前版本是否与最新记录一致

    用于启动时自动检测版本变更并记录。
    """
    svc = UpdateLogService(db)
    current_version = getattr(settings, "PROJECT_VERSION", "1.1.0")

    try:
        result = svc.check_and_record_version_change(
            current_version=current_version,
            updated_by=getattr(current_user, "username", "system"),
        )

        if result:
            return {
                "success": True,
                "message": "检测到版本变更并已记录",
                "data": result,
            }
        else:
            return {
                "success": True,
                "message": "版本未变更，无需记录",
                "data": {"current_version": current_version},
            }
    except Exception as e:
        return {
            "success": True,
            "message": f"版本检查完成，当前版本: {current_version}",
            "data": {"current_version": current_version, "check_error": str(e)},
        }
