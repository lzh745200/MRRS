"""
数据分级存储 API
提供数据分级查询、归档管理和存储统计
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timezone, datetime

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.permission_utils import is_admin
from app.models.user import User
from app.services.data_tier_service import data_tier_service, DataTier
from app.core.response import success_response

router = APIRouter(prefix="/data-tier", tags=["数据分级存储"])


def _require_admin(user: User) -> None:
    """校验管理员权限，非管理员抛出 403"""
    if not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


@router.get("/stats")
async def get_storage_stats(
    current_user: User = Depends(get_current_active_user),
):
    """
    获取存储统计信息
    """
    stats = data_tier_service.get_archive_stats(db=None)
    return stats


@router.get("/summary")
async def get_storage_summary(
    current_user: User = Depends(get_current_active_user),
):
    """
    获取存储摘要报告（管理员）
    """
    _require_admin(current_user)
    summary = data_tier_service.get_storage_summary()
    return summary


@router.get("/tier/{tier}")
async def get_tier_info(
    tier: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    获取指定分级的信息
    """
    try:
        data_tier = DataTier(tier.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的数据分级: {tier}")

    return success_response(data={
        "tier": data_tier.value,
        "hot_threshold_days": data_tier_service.config.HOT_THRESHOLD_DAYS if data_tier == DataTier.HOT else None,
        "warm_threshold_days": data_tier_service.config.WARM_THRESHOLD_DAYS if data_tier == DataTier.WARM else None,
        "storage_path": {
            DataTier.HOT: data_tier_service.config.HOT_DATA_PATH,
            DataTier.WARM: data_tier_service.config.WARM_DATA_PATH,
            DataTier.COLD: data_tier_service.config.COLD_ARCHIVE_PATH,
        }.get(data_tier),
    })


@router.post("/archive/{model_name}")
async def archive_model(
    model_name: str,
    # 深审 #58：原实现无任何边界 —— before_days 传负数会让 before_date 落到
    # 未来（把全部"未到期"数据当旧数据归档），batch_size<=0 则静默不处理。
    before_days: int = Query(365, ge=1, le=36500, description="归档多少天之前的数据"),
    batch_size: int = Query(1000, ge=1, le=100000, description="批次大小"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    归档指定模型的旧数据（管理员）

    Args:
        model_name: 模型名称（如：auditlog, message, worklog）
        before_days: 归档多少天之前的数据
        batch_size: 批次大小
    """
    _require_admin(current_user)
    # 模型名称映射
    model_map = {
        "auditlog": "AuditLog",
        "message": "Message",
        "worklog": "WorkLog",
        "fundlifecycle": "FundLifecycleLog",
        "projectmilestone": "ProjectMilestone",
        "approvalhistory": "ApprovalHistory",
    }

    if model_name.lower() not in model_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的模型: {model_name}")

    # 动态导入模型
    try:
        from app import models

        model_class = getattr(models, model_map[model_name.lower()])
    except (ImportError, AttributeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"模型未找到: {model_name}")

    before_date = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=before_days)

    count, message = data_tier_service.archive_records(
        db=db, model_class=model_class, before_date=before_date, batch_size=batch_size
    )

    return success_response(
        data={"archived_count": count, "message": message, "model": model_name,
              "before_date": before_date.isoformat()},
        message=message,
    )


@router.get("/archives")
async def list_archives(
    tier: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    列出归档文件（管理员）
    """
    _require_admin(current_user)
    from pathlib import Path

    config = data_tier_service.config
    result = {"cold_archives": [], "warm_archives": []}

    # 冷数据归档
    cold_path = Path(config.COLD_ARCHIVE_PATH)
    if cold_path.exists():
        for f in cold_path.glob("*.gz"):
            stat = f.stat()
            result["cold_archives"].append(
                {
                    "name": f.name,
                    "size": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    # 温数据归档（如果存在）
    warm_path = Path(config.WARM_DATA_PATH)
    if warm_path.exists():
        stat = warm_path.stat()
        result["warm_archives"].append(
            {
                "name": warm_path.name,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    if tier:
        tier_key = f"{tier.lower()}_archives"
        if tier_key in result:
            return success_response(data={tier_key: result[tier_key]})

    return success_response(data=result)


@router.post("/restore")
async def restore_from_archive(
    archive_file: str,
    model_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    从归档恢复数据（管理员）
    """
    _require_admin(current_user)
    # 模型名称映射
    model_map = {
        "auditlog": "AuditLog",
        "message": "Message",
        "worklog": "WorkLog",
        "fundlifecycle": "FundLifecycleLog",
        "projectmilestone": "ProjectMilestone",
        "approvalhistory": "ApprovalHistory",
    }

    if model_name.lower() not in model_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的模型: {model_name}")

    try:
        from app import models

        model_class = getattr(models, model_map[model_name.lower()])
    except (ImportError, AttributeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"模型未找到: {model_name}")

    count, message = data_tier_service.restore_from_archive(db=db, model_class=model_class, archive_file=archive_file)

    return success_response(
        data={"restored_count": count, "message": message, "archive_file": archive_file},
        message=message,
    )


@router.delete("/cleanup")
async def cleanup_old_archives(
    # 深审 #59：max_age_days 为负数时 cutoff 移到未来，cleanup_old_archives
    # 会删除**全部**归档文件。这里强制为正数（fail-closed）。
    max_age_days: int = Query(365, ge=1, le=36500, description="归档文件最大保留天数"),
    current_user: User = Depends(get_current_active_user),
):
    """
    清理过期归档文件（管理员）
    """
    _require_admin(current_user)
    deleted, message = data_tier_service.cleanup_old_archives(max_age_days)

    return success_response(
        data={"deleted_count": deleted, "message": message, "max_age_days": max_age_days},
        message=message,
    )


@router.get("/tier-for-record/{date}")
async def get_tier_for_record(
    date: datetime,
    current_user: User = Depends(get_current_active_user),
):
    """
    根据日期确定数据分级
    """
    tier = data_tier_service.determine_tier(date)

    aware_date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    return success_response(data={
        "record_date": date.isoformat(),
        "tier": tier.value,
        "age_days": (datetime.now(timezone.utc) - aware_date).days,
    })
