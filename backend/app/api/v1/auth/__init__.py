"""
认证与用户管理路由子模块
聚合 auth / users / user_management / rbac / two_factor 路由
"""

from fastapi import APIRouter

from .auth import create_access_token
from .auth import router as auth_router
from .auth import verify_token
from .rbac import router as rbac_router
from .two_factor import router as two_factor_router
from .user_management import router as user_management_router
from .users import router as users_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(user_management_router)
router.include_router(rbac_router)
router.include_router(two_factor_router)

__all__ = ["router", "create_access_token", "verify_token"]
