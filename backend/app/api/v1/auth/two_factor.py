"""
双因素认证API
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.models.user import User
from app.services.two_factor_service import TwoFactorService

router = APIRouter(prefix="/two-factor", tags=["双因素认证"])


class EnableTwoFactorResponse(BaseModel):
    """启用双因素认证响应"""

    secret: str
    qr_code: str
    backup_codes: list


class VerifyTokenRequest(BaseModel):
    """验证令牌请求"""

    token: str


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启用双因素认证失败: {str(e)}")


@router.post("/verify")
async def verify_and_enable(
    request: VerifyTokenRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    验证TOTP令牌并正式启用双因素认证
    """
    try:
        success = TwoFactorService.verify_and_enable(db, current_user, request.token)
        if success:
            return {"message": "双因素认证已启用"}
        else:
            raise HTTPException(status_code=400, detail="验证码错误")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")


@router.post("/disable")
async def disable_two_factor(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    禁用双因素认证
    """
    try:
        TwoFactorService.disable_two_factor(db, current_user)
        return {"message": "双因素认证已禁用"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"禁用失败: {str(e)}")


@router.get("/status")
async def get_two_factor_status(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    获取双因素认证状态
    """
    enabled = TwoFactorService.is_enabled(db, current_user)
    return {"enabled": enabled}
