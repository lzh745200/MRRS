"""
双因素认证API
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.security import check_rate_limit, verify_password
from app.models.user import User
from app.services.two_factor_service import TwoFactorService
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/two-factor", tags=["双因素认证"])

# 二次验证尝试限流：同一用户每分钟最多 10 次（W15 深审 #5）。
# 修复前 /two-factor/verify 与 /two-factor/disable 均无任何限流，
# 持有有效会话即可在线暴力枚举 6 位动态码 / 8 位备用码。
_TWO_FACTOR_RATE_LIMIT = 10
_TWO_FACTOR_RATE_WINDOW = 60


class EnableTwoFactorResponse(BaseModel):
    """启用双因素认证响应"""

    secret: str
    qr_code: str
    backup_codes: list


class VerifyTokenRequest(BaseModel):
    """验证令牌请求"""

    token: str


class DisableTwoFactorRequest(BaseModel):
    """禁用双因素认证请求（必须携带二次验证凭据）

    - code: 当前 TOTP 动态码或未使用的备用码；
    - password: 账户登录密码（设备丢失时的兜底通道）。
    二者至少提供一个，且必须验证通过，否则拒绝关闭二次验证。
    """

    code: Optional[str] = None
    password: Optional[str] = None


async def _enforce_two_factor_rate_limit(request: Request, current_user: User, action: str) -> None:
    """二次验证接口限流（按用户维度计数）。

    计数键包含业务动作，避免 verify / disable 互相挤占配额；
    超限返回 429，而不是静默放行。
    """
    is_allowed = await check_rate_limit(
        key=f"two_factor:{action}:{getattr(current_user, 'id', 'anonymous')}",
        request=request,
        limit=_TWO_FACTOR_RATE_LIMIT,
        window=_TWO_FACTOR_RATE_WINDOW,
    )
    if not is_allowed:
        logger.warning("双因素认证 %s 触发限流: user_id=%s", action, getattr(current_user, "id", None))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证尝试过于频繁，请稍后再试",
        )


def _verify_second_factor(db: Session, user: User, payload: DisableTwoFactorRequest) -> bool:
    """关闭二次验证前的二次因子校验。

    优先校验动态码/备用码（TwoFactorService.verify_login），
    再回退到账户密码；任一通过即视为通过。异常一律视为校验失败（fail-closed）。
    """
    code = (payload.code or "").strip()
    if code:
        try:
            if TwoFactorService.verify_login(db, user, code):
                return True
        except Exception:
            logger.warning("关闭双因素认证时动态码校验异常: user_id=%s", getattr(user, "id", None), exc_info=True)

    if payload.password:
        hashed = getattr(user, "hashed_password", None)
        if hashed:
            try:
                if verify_password(payload.password, hashed):
                    return True
            except Exception:
                logger.warning("关闭双因素认证时密码校验异常: user_id=%s", getattr(user, "id", None), exc_info=True)

    return False


@router.post("/enable", response_model=EnableTwoFactorResponse)
async def enable_two_factor(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    启用双因素认证
    返回密钥、二维码和备用码
    """
    try:
        result = TwoFactorService.enable_two_factor(db, current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="启用双因素认证失败，请稍后重试或联系管理员")


@router.post("/verify")
async def verify_and_enable(
    request: Request,
    payload: VerifyTokenRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    验证TOTP令牌并正式启用双因素认证
    """
    await _enforce_two_factor_rate_limit(request, current_user, "verify")

    try:
        success = TwoFactorService.verify_and_enable(db, current_user, payload.token)
        if success:
            return success_response(data={"message": "双因素认证已启用"}, message="双因素认证已启用")
        else:
            raise HTTPException(status_code=400, detail="验证码错误")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="验证失败，请稍后重试或联系管理员")


@router.post("/disable")
async def disable_two_factor(
    request: Request,
    payload: Optional[DisableTwoFactorRequest] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    禁用双因素认证（W15 深审 #6：必须先通过二次验证）

    修复前仅凭一个有效会话即可关闭二次验证——账号被盗后攻击者可先关闭
    2FA 再长期驻留。现要求动态码/备用码或账户密码二者之一验证通过。
    """
    await _enforce_two_factor_rate_limit(request, current_user, "disable")

    if payload is None or (not payload.code and not payload.password):
        raise HTTPException(
            status_code=400,
            detail="关闭双因素认证需要二次验证：请提供当前动态验证码/备用码，或账户密码",
        )

    if not _verify_second_factor(db, current_user, payload):
        logger.warning("关闭双因素认证二次验证失败: user_id=%s", getattr(current_user, "id", None))
        raise HTTPException(status_code=401, detail="二次验证失败，无法关闭双因素认证")

    try:
        TwoFactorService.disable_two_factor(db, current_user)
        return success_response(data={"message": "双因素认证已禁用"}, message="双因素认证已禁用")
    except Exception:
        raise HTTPException(status_code=500, detail="禁用失败，请稍后重试或联系管理员")


@router.get("/status")
async def get_two_factor_status(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    获取双因素认证状态
    """
    enabled = TwoFactorService.is_enabled(db, current_user)
    return success_response(data={"enabled": enabled})
