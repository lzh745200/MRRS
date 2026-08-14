"""
数据与报表路由子模块
聚合 analytics / statistics / reports / data_reports / data_packages / dashboard 路由
"""
from fastapi import APIRouter

from .analytics import router as analytics_router
from .dashboard import router as dashboard_router
from .data_packages import router as data_packages_router
from .data_quality import router as data_quality_router
from .data_reports import router as data_reports_router
from .reports import router as reports_router
from .statistics import router as statistics_router

router = APIRouter()

router.include_router(analytics_router)
router.include_router(statistics_router)
router.include_router(reports_router)
router.include_router(data_reports_router)
router.include_router(data_packages_router)
router.include_router(dashboard_router)
router.include_router(data_quality_router, prefix="/data-quality")

__all__ = ["router"]
