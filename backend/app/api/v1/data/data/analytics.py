"""
数据分析API路由
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import case, func as sa_func
from sqlalchemy.orm import Session

from app.core.cache import get_cache_service
from app.core.database import get_db
from app.core.security import get_current_user
from app.services.analytics_service import AnalyticsService
from app.utils.api_error import safe_api_call

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["数据分析"])

# 分析数据缓存 TTL（秒）—— 5 分钟
_ANALYTICS_CACHE_TTL = 300
# 从 core.constants 导入，保持向后兼容（原在此模块定义）
from app.core.constants import ANALYTICS_CACHE_PREFIX  # noqa: E402, F401


async def _get_cached(key: str):
    try:
        cache = await get_cache_service()
        return await cache.get(f"{ANALYTICS_CACHE_PREFIX}{key}")
    except Exception:  # pragma: no cover
        logger.warning("分析缓存读取失败", exc_info=True)
        return None


async def _set_cached(key: str, data):
    try:
        cache = await get_cache_service()
        await cache.set(f"{ANALYTICS_CACHE_PREFIX}{key}", data, _ANALYTICS_CACHE_TTL)
    except Exception:  # pragma: no cover
        logger.debug("写入分析数据缓存失败")


# ==================== 请求/响应模型 ====================


class DashboardRequest(BaseModel):
    """仪表盘数据请求"""

    date_range: Optional[str] = None
    filters: Optional[dict] = None


class ComparisonRequest(BaseModel):
    """对比分析请求"""

    province: Optional[str] = None
    compare_type: str = "province"
    target_value: Optional[str] = None


class ReportRequest(BaseModel):
    """报表生成请求"""

    report_type: str = "comprehensive"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """分析响应"""

    success: bool = True
    data: Optional[dict] = None
    message: str = ""


# ==================== API端点 ====================


@router.get("/dashboard")
@safe_api_call("获取仪表盘数据")
async def get_dashboard(
    date_range: Optional[str] = None,
    filters: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取仪表盘数据"""
    user_id = getattr(current_user, "id", 0)
    cached = await _get_cached(f"dashboard:{user_id}")
    if cached is not None:
        return AnalyticsResponse(success=True, data=cached, message="仪表盘数据获取成功")
    service = AnalyticsService(db)
    data = service.get_dashboard_overview(db)
    await _set_cached(f"dashboard:{user_id}", data)
    return AnalyticsResponse(success=True, data=data, message="仪表盘数据获取成功")


@router.get("/village-analysis")
@safe_api_call("获取帮扶村分析数据")
async def get_village_analysis(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取帮扶村分析数据"""
    user_id = getattr(current_user, "id", 0)
    cached = await _get_cached(f"village_analysis:{user_id}")
    if cached is not None:
        return AnalyticsResponse(success=True, data=cached, message="帮扶村分析数据获取成功")
    service = AnalyticsService(db)
    data = service.get_village_analysis(db)
    await _set_cached(f"village_analysis:{user_id}", data)
    return AnalyticsResponse(success=True, data=data, message="帮扶村分析数据获取成功")


@router.get("/funding-trends")
@safe_api_call("获取资金趋势分析")
async def get_funding_trends(
    years: int = 5,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取资金趋势分析"""
    cached = await _get_cached(f"funding_trends_{years}")
    if cached is not None:
        return AnalyticsResponse(success=True, data=cached, message="资金趋势分析数据获取成功")
    service = AnalyticsService(db)
    data = service.get_funding_trends(db, years)
    await _set_cached(f"funding_trends_{years}", data)
    return AnalyticsResponse(success=True, data=data, message="资金趋势分析数据获取成功")


@router.get("/performance-metrics")
@safe_api_call("获取绩效指标数据")
async def get_performance_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取绩效指标数据"""
    user_id = getattr(current_user, "id", 0)
    cached = await _get_cached(f"performance_metrics:{user_id}")
    if cached is not None:
        return AnalyticsResponse(success=True, data=cached, message="绩效指标数据获取成功")
    service = AnalyticsService(db)
    data = service.get_performance_metrics(db)
    await _set_cached(f"performance_metrics:{user_id}", data)
    return AnalyticsResponse(success=True, data=data, message="绩效指标数据获取成功")


@router.post("/comparison")
@safe_api_call("获取对比分析数据")
async def get_comparison_analysis(
    request: ComparisonRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取对比分析数据"""
    service = AnalyticsService(db)
    data = service.get_comparison_analysis(db, request.compare_type, request.target_value)
    return AnalyticsResponse(success=True, data=data, message="对比分析数据获取成功")


@router.post("/generate-report")
@safe_api_call("生成数据分析报表")
async def generate_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """生成数据分析报表"""
    service = AnalyticsService(db)
    data = service.generate_report_data(db, request.report_type, request.start_date, request.end_date)
    return AnalyticsResponse(success=True, data=data, message="报表生成成功")


@router.post("/export")
@safe_api_call("导出分析数据")
async def export_data(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """导出分析数据"""
    service = AnalyticsService(db)
    if request.report_type == "json":
        data = service.generate_report_data(db, "comprehensive", request.start_date, request.end_date)
        return AnalyticsResponse(success=True, data=data, message="数据导出成功")
    elif request.report_type == "excel":
        data = service.generate_report_data(db, "comprehensive", request.start_date, request.end_date)
        file_bytes = service.export_data(db, "excel", data)
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=analytics_export.xlsx"},
        )
    else:
        data = service.generate_report_data(db, request.report_type, request.start_date, request.end_date)
        return AnalyticsResponse(success=True, data=data, message="数据导出成功")


@router.get("/realtime-stats")
@safe_api_call("获取实时统计数据")
async def get_realtime_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取实时统计数据"""
    service = AnalyticsService(db)
    dashboard = service.get_dashboard_overview(db)
    recent_activities = [
        {"type": "project_updated", "source": "system", "message": "更新了项目: " + str(item)}
        for item in (dashboard.get("recent_updates", []) if dashboard else [])[:5]
    ]
    data = {
        "overview": dashboard,
        "recent_activities": recent_activities,
        "timestamp": datetime.now().isoformat(),
    }
    return AnalyticsResponse(success=True, data=data, message="实时统计数据获取成功")


def compute_kpi_summary_data(db: Session) -> dict:
    """KPI 汇总计算唯一实现：端点缓存未命中与每日预计算任务共用，杜绝口径漂移。"""
    from app.models.project import Project
    from app.models.supported_village import SupportedVillage

    total_villages = (
        db.query(sa_func.count(SupportedVillage.id))
        .filter(SupportedVillage.is_active.is_(True))
        .scalar()
        or 0
    )
    rows = (
        db.query(Project.status, sa_func.count(Project.id))
        .filter(Project.is_active == True)  # noqa: E712
        .group_by(Project.status)
        .all()
    )
    counts = {status: cnt for status, cnt in rows}
    total_projects = sum(counts.values())
    completed_projects = counts.get("completed", 0)
    approved_projects = counts.get("approved", 0)

    return {
        "total_villages": total_villages,
        "total_projects": total_projects,
        "completed_projects": completed_projects,
        "approved_projects": approved_projects,
        "completion_rate": round(completed_projects / total_projects * 100, 1)
        if total_projects
        else 0,
    }


@router.get("/kpi-summary")
@safe_api_call("获取KPI汇总数据")
async def get_kpi_summary(
    period: str = "month",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取KPI汇总数据"""
    cached = await _get_cached(f"kpi_summary_{period}")
    if cached is not None:
        return AnalyticsResponse(success=True, data=cached, message="KPI数据获取成功")

    data = compute_kpi_summary_data(db)
    data["period"] = period
    await _set_cached(f"kpi_summary_{period}", data)
    return AnalyticsResponse(success=True, data=data, message="KPI数据获取成功")


@router.get("/health")
async def get_analytics_health():
    """获取分析服务健康状态"""
    return AnalyticsResponse(success=True, data={"status": "healthy"}, message="分析服务状态正常")


@router.get("/cross-org-comparison")
@safe_api_call("跨组织对比分析")
async def get_cross_org_comparison(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """跨组织对比分析（仅 super_admin/admin 可用）

    按组织分组聚合：帮扶村数、项目数、资金总额、完成率。
    """
    role = getattr(current_user, "role", "")
    is_super = getattr(current_user, "is_superuser", False)
    if role not in ("admin", "super_admin") and not is_super:
        return AnalyticsResponse(success=False, data=None, message="仅管理员可查看跨组织对比")

    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.fund import Fund
    from app.models.supported_village import SupportedVillage

    # 1. 查询所有活跃组织（1 次查询）
    orgs = db.query(Organization.id, Organization.name).filter(
        Organization.is_active == True  # noqa: E712
    ).all()
    org_map = {
        org_id: {"organization_id": org_id, "organization_name": org_name,
                 "villages": 0, "projects_total": 0,
                 "projects_completed": 0, "completion_rate": 0.0,
                 "funds_total": 0.0}
        for org_id, org_name in orgs
    }

    # 2. 一次 GROUP BY 查询帮扶村计数（1 次查询，替代 N 次 COUNT）
    village_rows = db.query(
        SupportedVillage.organization_id,
        sa_func.count(SupportedVillage.id),
    ).filter(
        SupportedVillage.is_active == True,  # noqa: E712
    ).group_by(SupportedVillage.organization_id).all()
    for org_id, cnt in village_rows:
        if org_id in org_map:
            org_map[org_id]["villages"] = cnt

    # 3. 一次 GROUP BY 查询项目总数+完成数（条件聚合，1 次查询替代 2N 次 COUNT）
    project_rows = db.query(
        Project.organization_id,
        sa_func.count(Project.id),
        sa_func.sum(case((Project.status == "completed", 1), else_=0)),
    ).filter(
        Project.is_active == True,  # noqa: E712
    ).group_by(Project.organization_id).all()
    for org_id, total, completed in project_rows:
        if org_id in org_map:
            org_map[org_id]["projects_total"] = total
            org_map[org_id]["projects_completed"] = completed or 0

    # 4. 一次 GROUP BY 查询资金总额（1 次查询，替代 N 次 SUM）
    fund_rows = db.query(
        Fund.organization_id,
        sa_func.coalesce(sa_func.sum(Fund.amount), 0),
    ).filter(
        Fund.is_active == True,  # noqa: E712
    ).group_by(Fund.organization_id).all()
    for org_id, total in fund_rows:
        if org_id in org_map:
            org_map[org_id]["funds_total"] = round(float(total), 2)

    # 计算完成率并构建结果列表
    comparison = []
    for org_data in org_map.values():
        total = org_data["projects_total"]
        completed = org_data["projects_completed"]
        org_data["completion_rate"] = round(completed / total * 100, 1) if total > 0 else 0.0
        comparison.append(org_data)

    comparison.sort(key=lambda x: x["funds_total"], reverse=True)
    return AnalyticsResponse(
        success=True,
        data={"items": comparison, "total": len(comparison)},
        message="跨组织对比数据获取成功",
    )
