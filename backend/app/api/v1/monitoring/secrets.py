"""
密钥管理 API
提供密钥轮换、版本管理和安全存储
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from app.core.security import get_current_active_user
from app.core.permission_utils import is_admin
from app.models.user import User
from app.services.secrets_manager import secrets_manager
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/secrets", tags=["密钥管理"])

# 清理保留天数下界（W15 深审 #62）：keep_days<=0 会让 secrets_manager 的 cutoff
# （now - keep_days*86400）落到当前时刻/未来，使"已撤销且创建时间早于 cutoff"
# 对全部非活跃版本成立 → 一次调用清空所有密钥。这里拒绝非法值。
_MIN_KEEP_DAYS = 1


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
    return success_response(data={"versions": versions, "count": len(versions)})


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
        # 轮换后自检：密钥类操作「返回成功」不等于「数据还能解开」。
        # PII 解密失败是逐字段静默降级（原样回密文），如果不在这一步证明往返能力，
        # 现场看到的是「身份证/手机号全变乱码」，而审计里写的是「轮换成功」。
        try:
            from app.core.pii_crypto import self_check as _pii_self_check

            _pii_self_check()
        except RuntimeError as exc:  # 自检失败是显式 RuntimeError；其余异常照常冒泡
            # W1-T8 不变量：异常细节不得直出响应（自检失败信息可能含密钥/密文线索），
            # 只记服务端日志，响应给可读结论。回归 tests/unit/api/test_no_error_detail_leak.py。
            logger.error("密钥轮换后 PII 加解密自检失败: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="密钥轮换后 PII 加解密自检失败，请勿继续写入（详情见服务端日志）",
            ) from exc
        # 批次 3（危险操作强制审计）：密钥轮换会使全部既有密文/令牌受影响
        from app.utils.audit_logger import AuditLogger

        AuditLogger.log(
            action="secrets_rotate",
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", ""),
            resource_type="secrets",
            resource_id=version_id,
            details={"new_version": new_version},
        )
        return success_response(data={"message": "密钥轮换成功", "new_version": new_version}, message="密钥轮换成功")
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
    return success_response(data={"message": "密钥创建成功", "version_id": version_id}, message="密钥创建成功")


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
    return success_response(data={"message": "密钥已撤销", "version_id": version_id}, message="密钥已撤销")


@router.post("/cleanup")
async def cleanup_expired_keys(
    keep_days: int = Query(90, ge=_MIN_KEEP_DAYS, description="保留最近 N 天的密钥（下界 1 天）"),
    current_user: User = Depends(get_current_active_user),
):
    """
    清理过期密钥（管理员）
    """
    _require_admin(current_user)
    # 双保险：Query(ge=1) 由 FastAPI 拦非法查询串；这里兜住直接调用端点函数
    # （内部调用/单测）绕过 Pydantic 校验的路径。
    if keep_days < _MIN_KEEP_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"keep_days 必须不小于 {_MIN_KEEP_DAYS} 天（过小会清空全部密钥）",
        )
    count = secrets_manager.cleanup_expired_keys(keep_days)
    return success_response(
        data={"message": f"清理了 {count} 个过期密钥", "deleted_count": count},
        message=f"清理了 {count} 个过期密钥",
    )


@router.get("/status")
async def get_secrets_status(
    current_user: User = Depends(get_current_active_user),
):
    """
    获取密钥状态
    """
    _require_admin(current_user)
    versions = secrets_manager.list_key_versions()
    active_versions = [v for v in versions if v.get("is_active")]

    return success_response(data={
        "total_versions": len(versions),
        "active_versions": len(active_versions),
        "latest_version": versions[0] if versions else None,
        "requires_rotation": len(active_versions) == 0,
    })
