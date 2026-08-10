import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.fund import Fund
from app.models.project import Project
from app.models.school import School, SchoolSupport
from app.models.user import User
from app.models.village import Village
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/statistics", tags=["统计分析"])

# 统计数据缓存TTL（秒）- 5分钟
STATS_CACHE_TTL = 300
# 统计缓存键前缀
STATS_CACHE_PREFIX = "stats:"


async def _get_cached_stats(cache_key: str):
    """从缓存获取统计数据"""
    if not settings.CACHE_ENABLED:
        return None

    try:
        from app.core.cache import get_cache_service

        cache = await get_cache_service()
        cached_data = await cache.get(f"{STATS_CACHE_PREFIX}{cache_key}")
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning("统计缓存读取失败 (key=%s): %s", cache_key, e)
    return None


async def _cache_stats(cache_key: str, data: dict):
    """缓存统计数据"""
    if not settings.CACHE_ENABLED:
        return

    try:
        from app.core.cache import get_cache_service

        cache = await get_cache_service()
        await cache.set(f"{STATS_CACHE_PREFIX}{cache_key}", json.dumps(data, default=str), ttl=STATS_CACHE_TTL)
    except Exception as e:
        logger.warning("统计缓存写入失败 (key=%s): %s", cache_key, e)


def _calc_village_completeness(db: Session, SV, VP, VI, total_villages: int) -> int:
    """计算帮扶村数据完整率（百分比整数）

    检查维度：
    1. 基本信息字段：village_name, county, department, support_unit
    2. 地理坐标：latitude + longitude
    3. 人口数据：至少有1年 VillagePopulation 记录
    4. 收入数据：至少有1年 VillageIncome 记录

    每个帮扶村满分 6 个检查项，汇总所有村的通过项占比。
    """
    if total_villages == 0:
        return 0

    checks_per_village = 6
    total_checks = total_villages * checks_per_village
    passed = 0

    # 1. 基本信息字段（各字段非空计数）
    for col in [SV.village_name, SV.county, SV.department, SV.support_unit]:
        cnt = (
            db.query(func.count(SV.id))
            .filter(col.isnot(None), col != "")
            .scalar() or 0
        )
        passed += cnt

    # 2. 地理坐标（lat 和 lng 都非空才算通过）
    coords_filled = (
        db.query(func.count(SV.id))
        .filter(SV.latitude.isnot(None), SV.longitude.isnot(None))
        .scalar() or 0
    )
    passed += coords_filled

    # 3. 人口数据（至少有1年记录的村数）
    pop_villages = db.query(func.count(func.distinct(VP.supported_village_id))).scalar() or 0
    passed += min(pop_villages, total_villages)

    # 4. 收入数据（至少有1年记录的村数）
    # NOTE: VillageIncome 表名可能为 village_income 或 village_incomes
    income_villages = db.query(func.count(func.distinct(VI.supported_village_id))).scalar() or 0
    passed += min(income_villages, total_villages)

    return round(passed / total_checks * 100)


@router.get("/summary")
async def get_summary(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    获取系统概览统计

    Task 4.2: 在查询服务中集成缓存
    - 缓存频繁访问的查询结果
    - 配置查询结果TTL（5分钟）
    """
    try:
        # 尝试从缓存获取
        cache_key = "summary"
        cached = await _get_cached_stats(cache_key)
        if cached:
            return cached

        # 缓存未命中，从数据库查询
        users_count = db.query(User).filter(User.is_active == True).count()  # noqa: E712
        villages_count = db.query(Village).count()
        schools_count = db.query(School).filter(School.is_active == True).count()  # noqa: E712
        projects_count = db.query(Project).count()
        funds_count = db.query(Fund).count()

        funds_total = db.query(Fund.amount).filter(Fund.status == "approved").all()
        funds_sum = sum(f[0] for f in funds_total) if funds_total else 0

        projects_by_status = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
        projects_status_dist = {status: count for status, count in projects_by_status}

        active_projects = db.query(Project).filter(Project.status == "active").count()
        completed_projects = db.query(Project).filter(Project.status == "completed").count()

        result = {
            "total_users": users_count,
            "total_villages": villages_count,
            "total_schools": schools_count,
            "total_projects": projects_count,
            "total_funds": funds_count,
            "approved_funds_amount": funds_sum,
            "projects_by_status": projects_status_dist,
            "active_projects": active_projects,
            "completed_projects": completed_projects,
        }

        # 写入缓存
        await _cache_stats(cache_key, result)

        return result
    except Exception as e:
        logger.error("系统概览统计查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.get("/overview")
async def get_overview(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    数据总览接口 - 返回各模块概况、最后更新时间、健康评分、趋势数据
    """
    try:
        return await _get_overview_impl(db)
    except Exception as e:
        logger.error("数据总览查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


async def _get_overview_impl(db: Session):
    from datetime import datetime, timedelta

    from app.models.audit import AuditLog

    villages_count = db.query(Village).count()
    projects_count = db.query(Project).count()
    schools_count = db.query(School).filter(School.is_active == True).count()  # noqa: E712
    funds_count = db.query(Fund).count()
    users_count = db.query(User).filter(User.is_active == True).count()  # noqa: E712

    funds_total = db.query(func.sum(Fund.amount)).filter(Fund.status == "approved").scalar() or 0

    # 各模块最后更新时间
    def _last_update(model):
        col = getattr(model, "updated_at", None) or getattr(model, "created_at", None)
        if col is None:  # pragma: no cover —— 调用方仅传入 Village/Project/Fund/School/User，均带时间戳，防御分支不可达
            return None
        val = db.query(func.max(col)).scalar()
        return str(val) if val else None

    modules = [
        {
            "module": "帮扶村数据",
            "records": villages_count,
            "lastUpdate": _last_update(Village),
            "healthy": villages_count > 0,
        },
        {
            "module": "项目管理",
            "records": projects_count,
            "lastUpdate": _last_update(Project),
            "healthy": projects_count > 0,
        },
        {"module": "经费管理", "records": funds_count, "lastUpdate": _last_update(Fund), "healthy": funds_count > 0},
        {"module": "帮扶学校", "records": schools_count, "lastUpdate": _last_update(School), "healthy": schools_count > 0},
        {"module": "用户管理", "records": users_count, "lastUpdate": _last_update(User), "healthy": users_count > 0},
    ]

    # 数据完整率 — 基于帮扶村关键字段实际填写率
    from app.models.supported_village import SupportedVillage as SV
    from app.models.supported_village import VillageIncome as VI
    from app.models.supported_village import VillagePopulation as VP

    sv_count = db.query(SV).count()
    completeness = _calc_village_completeness(db, SV, VP, VI, sv_count) if sv_count > 0 else 0

    # 数据健康评分 (0-100) — 综合考虑各模块数据量和完整率
    module_scores = []
    if villages_count > 0:
        module_scores.append(min(100, completeness))
    else:
        module_scores.append(0)
    module_scores.append(100 if projects_count > 0 else 0)
    module_scores.append(100 if schools_count > 0 else 0)
    module_scores.append(100 if funds_count > 0 else 0)
    health_score = round(sum(module_scores) / max(len(module_scores), 1))

    # 今日操作数
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_ops = 0
    try:
        today_ops = db.query(AuditLog).filter(AuditLog.created_at >= today_start).count()
    except Exception:
        logger.warning("查询今日操作数失败（看板将显示 0）", exc_info=True)

    # 近7天数据趋势（单次 GROUP BY 查询替代 7 次循环查询）
    trend = []
    try:
        week_start = (datetime.now() - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_results = (
            db.query(func.date(AuditLog.created_at).label("day"), func.count(AuditLog.id).label("cnt"))
            .filter(AuditLog.created_at >= week_start)
            .group_by(func.date(AuditLog.created_at))
            .all()
        )
        day_counts = {r.day: r.cnt for r in daily_results}
    except Exception:
        logger.warning("查询近7天趋势失败（看板趋势将为空）", exc_info=True)
        day_counts = {}

    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%m-%d")
        day_key = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        cnt = day_counts.get(day_key, 0)
        trend.append({"date": day, "operations": cnt})

    # 最近操作记录
    recent_logs = []
    try:
        logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(8).all()
        for log in logs:
            recent_logs.append(
                {
                    "id": log.id,
                    "action": f"{log.action or ''} {log.resource_type or ''}".strip(),
                    "user": log.username or f"用户{log.user_id or ''}",
                    "time": str(log.created_at) if log.created_at else "",
                }
            )
    except Exception:
        logger.warning("查询最近操作记录失败（最近操作列表将为空）", exc_info=True)

    return {
        "villages": villages_count,
        "projects": projects_count,
        "schools": schools_count,
        "funds_amount": float(funds_total),
        "completeness": completeness,
        "health_score": health_score,
        "today_operations": today_ops,
        "modules": modules,
        "trend": trend,
        "recent_logs": recent_logs,
    }


@router.get("/villages/distribution")
async def get_villages_distribution(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        by_status = db.query(Village.status, func.count(Village.id)).group_by(Village.status).all()
        status_data = [{"name": status, "value": count} for status, count in by_status]

        top_villages = db.query(Village).order_by(Village.total_population.desc()).limit(10).all()
        top_data = [{"name": v.name, "value": v.total_population or 0} for v in top_villages]

        by_province = db.query(Village.province, func.count(Village.id)).group_by(Village.province).all()
        province_data = [{"name": province or "未知", "value": count} for province, count in by_province if province]

        return success_response(
            data={"by_status": status_data, "top_population": top_data, "by_province": province_data}
        )
    except Exception as e:
        logger.error("帮扶村分布统计查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.get("/projects/statistics")
async def get_projects_statistics(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        by_status = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
        status_data = [{"name": status, "value": count} for status, count in by_status]

        by_type = db.query(Project.type, func.count(Project.id)).group_by(Project.type).all()
        type_data = [{"name": ptype or "未分类", "value": count} for ptype, count in by_type if ptype]

        budget_sum = db.query(func.sum(Project.budget)).scalar() or 0
        invested_sum = db.query(func.sum(Project.invested_amount)).scalar() or 0

        avg_progress = db.query(func.avg(Project.progress)).scalar() or 0

        recent_projects = db.query(Project).order_by(Project.created_at.desc()).limit(5).all()
        recent_data = [
            {"id": p.id, "name": p.name, "status": p.status, "progress": p.progress, "budget": p.budget}
            for p in recent_projects
        ]

        return success_response(data={
            "by_status": status_data,
            "by_type": type_data,
            "total_budget": budget_sum,
            "total_invested": invested_sum,
            "average_progress": round(avg_progress, 1),
            "recent_projects": recent_data,
        })
    except Exception as e:
        logger.error("项目统计查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.get("/funds/statistics")
async def get_funds_statistics(year: int = None, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        query = db.query(Fund)

        if year:
            query = query.filter(func.strftime("%Y", Fund.date) == str(year))

        by_type = query.with_entities(Fund.type, func.count(Fund.id), func.sum(Fund.amount)).all()
        type_data = [
            {"type": ftype or "未分类", "count": count, "total_amount": total or 0} for ftype, count, total in by_type
        ]

        total_amount = query.with_entities(func.sum(Fund.amount)).scalar() or 0
        approved_amount = db.query(func.sum(Fund.amount)).filter(Fund.status == "approved").scalar() or 0

        monthly_stats = (
            db.query(
                func.strftime("%Y-%m", Fund.date).label("month"),
                func.count(Fund.id).label("count"),
                func.sum(Fund.amount).label("amount"),
            )
            .filter(Fund.date.isnot(None))
            .group_by("month")
            .order_by("month")
            .limit(12)
            .all()
        )

        monthly_data = [
            {"month": month, "count": count, "amount": amount or 0} for month, count, amount in monthly_stats
        ]

        return success_response(data={
            "by_type": type_data,
            "total_amount": total_amount,
            "approved_amount": approved_amount,
            "monthly_trend": monthly_data,
        })
    except Exception as e:
        logger.error("经费统计查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.get("/schools/statistics")
async def get_schools_statistics(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        by_type = db.query(School.type, func.count(School.id)).group_by(School.type).all()
        type_data = [{"name": stype or "未分类", "value": count} for stype, count in by_type if stype]

        total_students = db.query(func.sum(School.student_count)).scalar() or 0
        total_teachers = db.query(func.sum(School.teacher_count)).scalar() or 0

        supports_by_type = (
            db.query(SchoolSupport.support_type, func.count(SchoolSupport.id))
            .group_by(SchoolSupport.support_type)
            .all()
        )
        support_data = [{"name": sptype or "未分类", "value": count} for sptype, count in supports_by_type]

        total_support_amount = (
            db.query(func.sum(SchoolSupport.amount))
            .filter(SchoolSupport.amount.isnot(None))
            .scalar()
            or 0
        )

        return success_response(data={
            "by_type": type_data,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "by_support_type": support_data,
            "total_support_amount": total_support_amount,
        })
    except Exception as e:
        logger.error("学校统计查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.get("/analysis")
async def get_analysis_data(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    数据统计分析页面聚合接口
    返回投入趋势、帮扶分类统计、地区分布等
    """
    try:
        return await _get_analysis_data_impl(db)
    except Exception as e:
        logger.error("分析数据查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


async def _get_analysis_data_impl(db: Session):
    from app.models.supported_village import (ConsumptionSupport,
                                              EducationSupport,
                                              EmploymentSupport,
                                              IndustrySupport,
                                              InfrastructureImprovement,
                                              MedicalSupport,
                                              PartyBuildingSupport,
                                              SupportedVillage, SupportFunding,
                                              VillageIncome, VillagePopulation)

    # --- 概览统计 ---
    total_villages = db.query(SupportedVillage).count()
    active_projects = db.query(Project).filter(Project.status.in_(["in_progress", "approved", "active"])).count()

    # 总投入资金
    mil_total = db.query(func.coalesce(func.sum(SupportedVillage.transition_fund_military_total), 0)).scalar() or 0
    loc_total = db.query(func.coalesce(func.sum(SupportedVillage.transition_fund_local_total), 0)).scalar() or 0
    total_investment = float(mil_total) + float(loc_total)

    # 数据完整率 — 基于关键字段实际填写率
    completeness = _calc_village_completeness(db, SupportedVillage, VillagePopulation, VillageIncome, total_villages)

    # --- 投入趋势 (2021-2025) ---
    investment_trend = []
    years = [2021, 2022, 2023, 2024, 2025]
    prev_total = 0

    # 只有在有帮扶村数据时才显示投入趋势
    # 因为没有帮扶村的话，投入趋势数据没有实际意义
    has_villages = total_villages > 0
    has_funding_data = db.query(SupportFunding).count() > 0

    if has_villages and has_funding_data:
        # 单次 GROUP BY 查询替代 5 次循环 × 2 次聚合 = 10 次查询
        yearly_data = (
            db.query(
                SupportFunding.year.label("yr"),
                func.coalesce(func.sum(SupportFunding.military_investment), 0).label("mil"),
                func.coalesce(func.sum(SupportFunding.local_investment), 0).label("loc"),
            )
            .filter(SupportFunding.year.in_(years))
            .group_by(SupportFunding.year)
            .all()
        )
        year_map = {r.yr: (float(r.mil or 0), float(r.loc or 0)) for r in yearly_data}
        for yr in years:
            mil_f, loc_f = year_map.get(yr, (0.0, 0.0))
            yr_total = mil_f + loc_f
            growth = round((yr_total - prev_total) / max(prev_total, 1) * 100, 1) if prev_total > 0 else 0
            investment_trend.append(
                {"year": str(yr), "military": mil_f, "local": loc_f, "total": yr_total, "growth": growth}
            )
            prev_total = yr_total if yr_total > 0 else prev_total

    # --- 帮扶分类统计 ---
    # 从各帮扶子表统计
    cat_stats = []
    cat_models = [
        ("产业帮扶", IndustrySupport, "investment"),
        ("基础设施", InfrastructureImprovement, "investment"),
        ("教育帮扶", EducationSupport, "investment"),
        ("医疗帮扶", MedicalSupport, "investment"),
        ("党建帮扶", PartyBuildingSupport, "investment"),
    ]
    total_cat_inv = 0
    for cat_name, model, inv_field in cat_models:
        # 合并 count + sum 为单次查询（减少 50% 查询数）
        result = db.query(
            func.count(1).label("cnt"),
            func.coalesce(func.sum(getattr(model, inv_field)), 0).label("inv"),
        ).first()
        cnt = (result.cnt if result else 0) or 0
        inv = float(result.inv if result else 0) or 0.0
        total_cat_inv += inv
        cat_stats.append(
            {"category": cat_name, "count": cnt, "investment": round(inv, 2), "beneficiaries": 0, "ratio": 0}
        )

    # 消费帮扶（合并 count + sum）
    cons_result = db.query(
        func.count(1).label("cnt"),
        func.coalesce(func.sum(ConsumptionSupport.village_products_purchase), 0).label("inv"),
    ).first()
    cons_cnt = (cons_result.cnt if cons_result else 0) or 0
    cons_inv = float(cons_result.inv if cons_result else 0) or 0.0
    total_cat_inv += cons_inv
    cat_stats.append(
        {"category": "消费帮扶", "count": cons_cnt, "investment": round(cons_inv, 2), "beneficiaries": 0, "ratio": 0}
    )

    # 就业帮扶（合并 count + sum）
    emp_result = db.query(
        func.count(1).label("cnt"),
        func.coalesce(func.sum(EmploymentSupport.trained_population), 0).label("ben"),
    ).first()
    emp_cnt = (emp_result.cnt if emp_result else 0) or 0
    emp_ben = (emp_result.ben if emp_result else 0) or 0
    cat_stats.append({"category": "就业帮扶", "count": emp_cnt, "investment": 0, "beneficiaries": int(emp_ben), "ratio": 0})

    # 计算占比
    if total_cat_inv > 0:
        for cs in cat_stats:
            cs["ratio"] = round(cs["investment"] / total_cat_inv * 100) if cs["investment"] > 0 else 0

    # --- 地区分布 ---
    region_stats = []
    county_data = (
        db.query(
            SupportedVillage.county,
            func.count(SupportedVillage.id),
            func.coalesce(func.sum(SupportedVillage.transition_fund_military_total), 0),
            func.coalesce(func.sum(SupportedVillage.transition_fund_local_total), 0),
        )
        .filter(SupportedVillage.county.isnot(None), SupportedVillage.county != "")
        .group_by(SupportedVillage.county)
        .all()
    )

    for county, cnt, mil, loc in county_data:
        region_stats.append(
            {
                "region": county,
                "villages": cnt,
                "investment": round(float(mil) + float(loc), 2),
                "avgIncome": 0,
            }
        )

    return {
        "overview": {
            "total_villages": total_villages,
            "total_investment": round(total_investment, 2),
            "completeness": completeness,
            "active_projects": active_projects,
        },
        "investment_trend": investment_trend,
        "category_stats": cat_stats,
        "region_stats": region_stats,
    }


@router.get("/dashboard")
async def get_dashboard_data(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    获取仪表盘数据

    Task 4.2: 在查询服务中集成缓存
    """
    try:
        # 尝试从缓存获取
        cache_key = "dashboard"
        cached = await _get_cached_stats(cache_key)
        if cached:
            return cached

        summary = {
            "total_users": db.query(User).count(),
            "total_villages": db.query(Village).count(),
            "total_schools": db.query(School).count(),
            "total_projects": db.query(Project).count(),
            "active_projects": db.query(Project).filter(Project.status == "active").count(),
            "total_funds": db.query(Fund).count(),
        }

        funds_total = db.query(func.sum(Fund.amount)).filter(Fund.status == "approved").scalar() or 0
        summary["approved_funds"] = funds_total

        recent_activities = db.query(Project).order_by(Project.updated_at.desc()).limit(5).all()
        summary["recent_projects"] = [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "progress": p.progress,
                "updated_at": str(p.updated_at) if p.updated_at else None,
            }
            for p in recent_activities
        ]

        projects_by_status = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
        summary["projects_chart"] = [{"name": status, "value": count} for status, count in projects_by_status]

        # 写入缓存
        await _cache_stats(cache_key, summary)

        return summary
    except Exception as e:
        logger.error("仪表盘数据查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")
