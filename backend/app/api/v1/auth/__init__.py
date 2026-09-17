"""
认证与用户管理路由子模块
聚合 auth / users / rbac / two_factor 路由

注：原 user_management 路由（/api/v1/user-management）已于 2026-09-14 下线——
它与 /api/v1/users 是同一业务的两套并行实现，且创建 admin 时会误置 is_superuser=True。
"""

from fastapi import APIRouter

from .auth import create_access_token
from .auth import router as auth_router
from .auth import verify_token
from .rbac import router as rbac_router
from .two_factor import router as two_factor_router
from .users import router as users_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(rbac_router)
router.include_router(two_factor_router)

__all__ = ["router", "create_access_token", "verify_token"]
