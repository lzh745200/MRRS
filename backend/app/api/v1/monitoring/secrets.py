"""
密钥管理 API
提供密钥轮换、版本管理和安全存储
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.core.security import get_current_active_user
from app.core.permission_utils import is_admin
from app.models.user import User
from app.services.secrets_manager import secrets_manager

router = APIRouter(prefix="/secrets", tags=["密钥管理"])


def _require_admin(user: User) -> None:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")


@router.get("/versions")
async def list_key_versions(
    current_user: User = Depends(get_current_active_user),
):
    """
    列出所有密钥版本（管理员）
    """
    _require_admin(current_user)
    versions = secrets_manager.list_key_versions()
    return {"versions": versions, "count": len(versions)}


@router.post("/rotate")
async def rotate_key(
    version_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    轮换密钥（管理员）
    """
    _require_admin(current_user)
    try:
        new_version = secrets_manager.rotate_key(version_id)
        return {"message": "密钥轮换成功", "new_version": new_version}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/create")
async def create_key(
    key_type: str = "fernet",
    expires_days: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    创建新密钥（管理员）
    """
    _require_admin(current_user)
    version_id = secrets_manager.create_key(key_type=key_type, expires_days=expires_days)
    return {"message": "密钥创建成功", "version_id": version_id}


@router.post("/revoke/{version_id}")
async def revoke_key(
    version_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    撤销密钥（管理员）
    """
    _require_admin(current_user)
    success = secrets_manager.revoke_key(version_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"密钥版本不存在: {version_id}")
    return {"message": "密钥已撤销", "version_id": version_id}


@router.post("/cleanup")
async def cleanup_expired_keys(
    keep_days: int = 90,
    current_user: User = Depends(get_current_active_user),
):
    """
    清理过期密钥（管理员）
    """
    _require_admin(current_user)
    count = secrets_manager.cleanup_expired_keys(keep_days)
    return {"message": f"清理了 {count} 个过期密钥", "deleted_count": count}


@router.get("/status")
async def get_secrets_status(
    current_user: User = Depends(get_current_active_user),
):
    """
    获取密钥状态
    """
    versions = secrets_manager.list_key_versions()
    active_versions = [v for v in versions if v.get("is_active")]

    return {
        "total_versions": len(versions),
        "active_versions": len(active_versions),
        "latest_version": versions[0] if versions else None,
        "requires_rotation": len(active_versions) == 0,
    }
