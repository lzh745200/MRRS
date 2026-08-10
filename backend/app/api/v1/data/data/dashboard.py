"""
仪表盘API路由
提供前端 HomeSafe.vue 首页所需的统计数据

优化说明：
- 使用 SupportedVillage + VillagePopulation 替代旧的 Village 表（业务数据统一）
- 将 10+ 次独立 SQL 查询合并为 3 条聚合查询
- 实现 data_completeness、pending_approvals 真实计算
- 添加 diskcache 缓存（TTL=5分钟）
- recent-activities 覆盖项目、经费、审批多类事件
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.core.unified_data_scope import OrgScopeFilter, get_org_scope
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.response import success_response
from app.core.permission_utils import is_admin
from app.core.security import get_current_user
from app.models.approval import ApprovalTask
from app.models.fund import Fund
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage, VillagePopulation
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])

# 年份范围（帮扶数据应填报的年份起始年）
_DATA_START_YEAR = 2021

# ==================== diskcache 缓存 ====================
try:
    import diskcache

    _cache_dir = settings.CACHE_DIR
    os.makedirs(_cache_dir, exist_ok=True)
    _cache = diskcache.Cache(
        os.path.join(_cache_dir, "dashboard"),
        size_limit=50 * 1024 * 1024,  # 50MB
    )
    _CACHE_TTL = 120  # 2 分钟
except ImportError:  # pragma: no cover —— diskcache 为项目已安装依赖，导入失败分支在当前环境不可执行
    _cache = None
    _CACHE_TTL = 0
    logger.warning("diskcache 未安装，仪表盘缓存已禁用")


def _get_cached(key: str):
    """安全地从缓存读取"""
    if _cache is None:
        return None
    try:
        return _cache.get(key)
    except Exception:
        logger.warning("仪表盘缓存读取失败", exc_info=True)
        return None


def _set_cached(key: str, value, ttl: int = _CACHE_TTL):
    """安全地写入缓存"""
    if _cache is None:
        return
    try:
        _cache.set(key, value, expire=ttl)
    except Exception:
        logger.debug("写入仪表盘缓存失败")


def invalidate_dashboard_cache():
    """清除仪表盘缓存，供其他模块在数据变更后调用"""
    if _cache is None:
        return
    try:
        _cache.clear()
    except Exception:
        logger.debug("清除仪表盘缓存失败")


# ==================== 聚合查询 ====================


def _query_village_stats(db: Session, data_scope: OrgScopeFilter) -> dict:
    """查询1：帮扶村 + 人口 + 学校统计（基于 SupportedVillage）"""
    # 帮扶村查询（带数据范围过滤）— 用 subquery 避免大 IN 列表物化到 Python
    village_query = db.query(SupportedVillage.id).filter(
        SupportedVillage.is_active == True  # noqa: E712
    )
    village_query = data_scope.filter_by_org_ids(
        village_query, SupportedVillage.organization_id,
        created_by_column=SupportedVillage.created_by,
    )
    village_subq = village_query.subquery()
    total_villages = db.query(func.count()).select_from(village_subq).scalar() or 0

    # 人口/户数：取最新年份的汇总数据
    latest_year_sub = db.query(func.max(VillagePopulation.year)).scalar()
    total_population = 0
    total_households = 0
    if latest_year_sub and total_villages > 0:
        pop_row = (
            db.query(
                func.coalesce(func.sum(VillagePopulation.total_population), 0),
                func.coalesce(func.sum(VillagePopulation.total_households), 0),
            )
            .filter(
                VillagePopulation.year == latest_year_sub,
                VillagePopulation.supported_village_id.in_(
                    db.query(village_subq.c.id)
                ),
            )
            .first()
        )
        if pop_row:
            total_population = int(pop_row[0])
            total_households = int(pop_row[1])

    # 学校统计（带数据范围过滤，仅统计活跃学校）
    school_query = db.query(
        func.count(School.id),
        func.coalesce(func.sum(case((School.support_status == "active", 1), else_=0)), 0),
        func.coalesce(func.sum(School.student_count), 0),
        func.coalesce(func.sum(School.teacher_count), 0),
    ).filter(School.is_active == True)  # 修复: 使用 is_ 方法  # noqa: E712
    school_query = data_scope.filter_by_org_ids(
        school_query, School.organization_id, created_by_column=School.created_by
    )

    school_row = school_query.first()
    total_schools = int(school_row[0]) if school_row else 0
    schools_active = int(school_row[1]) if school_row else 0
    total_students = int(school_row[2]) if school_row else 0
    total_teachers = int(school_row[3]) if school_row else 0

    return {
        "total_villages": total_villages,
        "total_population": total_population,
        "total_households": total_households,
        "total_schools": total_schools,
        "schools_active": schools_active,
        "total_students": total_students,
        "total_teachers": total_teachers,
    }


def _query_fund_stats(db: Session, data_scope: OrgScopeFilter) -> dict:
    """查询2：经费聚合（按 status 分组一次性获取，带数据范围过滤）"""
    query = db.query(
        Fund.status,
        func.coalesce(func.sum(Fund.amount), 0),
    ).filter(Fund.is_active == True)  # noqa: E712

    # 非管理员仅统计关联到可访问帮扶村/学校的经费
    if not data_scope.has_full_access():
        from sqlalchemy import or_

        # 获取当前用户可访问的帮扶村 ID
        village_query = db.query(SupportedVillage.id).filter(
            SupportedVillage.is_active == True  # noqa: E712
        )
        village_query = data_scope.filter_by_org_ids(
            village_query, SupportedVillage.organization_id,
            created_by_column=SupportedVillage.created_by,
        )
        accessible_village_ids = [r[0] for r in village_query.all()]

        if accessible_village_ids:
            query = query.filter(
                or_(
                    Fund.village_id.in_(accessible_village_ids),
                    Fund.village_id.is_(None),  # 未关联帮扶村的经费也纳入统计
                )
            )
        else:
            # 无可访问的帮扶村时只统计未关联村的经费
            query = query.filter(Fund.village_id.is_(None))

    rows = query.group_by(Fund.status).all()

    funds_total = 0.0
    funds_allocated = 0.0
    funds_pending = 0.0
    funds_planned = 0.0
    allocated_statuses = {"approved", "allocated", "completed", "audited"}

    for status_val, amount in rows:
        amount_f = float(amount)
        funds_total += amount_f
        if status_val in allocated_statuses:
            funds_allocated += amount_f
        elif status_val == "pending":
            funds_pending += amount_f
        elif status_val == "planned":
            funds_planned += amount_f

    return {
        "total_funds": round(funds_total, 2),
        "funds_allocated": round(funds_allocated, 2),
        "funds_pending": round(funds_pending, 2),
        "funds_planned": round(funds_planned, 2),
    }


def _query_project_approval_stats(db: Session, data_scope: OrgScopeFilter) -> dict:
    """查询3：项目聚合 + 审批待办 + 用户数 + 数据完整性"""
    # 项目统计（按数据范围过滤）
    proj_query = db.query(
        func.count(Project.id),
        func.coalesce(func.sum(case((Project.status.in_(["active", "in_progress"]), 1), else_=0)), 0),
    ).filter(
        Project.status != "cancelled",
        Project.is_active == True,  # noqa: E712
    )
    # 非管理员按组织数据范围过滤项目
    if not data_scope.has_full_access():
        if hasattr(Project, "organization_id") and data_scope.org_ids:
            proj_query = data_scope.filter_by_org_ids(proj_query, Project.organization_id)
        elif data_scope.org_names:
            # 回退到文本匹配（按项目负责单位/部门过滤）
            from sqlalchemy import or_

            conditions = []
            for name in data_scope.org_names:
                if len(name) >= 2:
                    if hasattr(Project, "responsible_unit"):
                        conditions.append(Project.responsible_unit.contains(name))
                    if hasattr(Project, "department"):
                        conditions.append(Project.department.contains(name))
            if conditions:
                proj_query = proj_query.filter(or_(*conditions))
            else:
                proj_query = proj_query.filter(False)
    proj_row = proj_query.first()
    total_projects = int(proj_row[0]) if proj_row else 0
    active_projects = int(proj_row[1]) if proj_row else 0

    # 审批待办
    pending_approvals = 0
    try:
        pending_approvals = db.query(func.count(ApprovalTask.id)).filter(ApprovalTask.status == "pending").scalar() or 0
    except Exception as e:
        logger.warning("查询审批待办失败: %s", e)

    # 用户总数（仅活跃用户）
    total_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0  # noqa: E712

    # 数据完整性：帮扶村已填报年份数 / 应填报年份数
    current_year = datetime.now().year
    expected_years = max(current_year - _DATA_START_YEAR + 1, 1)
    data_completeness = 0.0

    total_villages_count = db.query(func.count(SupportedVillage.id)).filter(
        SupportedVillage.is_active == True  # noqa: E712
    ).scalar() or 0
    if total_villages_count > 0:
        # 简化计算：总填报条数 / (村数 × 应填年份数)
        total_expected = total_villages_count * expected_years
        total_filled = db.query(func.count(VillagePopulation.id)).scalar() or 0
        data_completeness = round(min(total_filled / total_expected, 1.0), 4) if total_expected > 0 else 0.0

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "pending_approvals": int(pending_approvals),
        "total_users": int(total_users),
        "data_completeness": data_completeness,
    }


def _compute_trends(db: Session, data_scope: OrgScopeFilter) -> dict:
    """计算各KPI的30天环比趋势百分比"""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    trends = {}

    try:
        # 帮扶村趋势
        current_villages = db.query(func.count(SupportedVillage.id)).filter(
            SupportedVillage.is_active == True  # noqa: E712
        ).scalar() or 0
        prev_villages = db.query(func.count(SupportedVillage.id)).filter(
            SupportedVillage.is_active == True,  # noqa: E712
            SupportedVillage.created_at <= thirty_days_ago,
        ).scalar() or 0
        trends["villages"] = _pct_change(current_villages, prev_villages)

        # 项目趋势
        current_projects = db.query(func.count(Project.id)).filter(
            Project.is_active == True,  # noqa: E712
            Project.status != "cancelled",
        ).scalar() or 0
        prev_projects = db.query(func.count(Project.id)).filter(
            Project.is_active == True,  # noqa: E712
            Project.status != "cancelled",
            Project.created_at <= thirty_days_ago,
        ).scalar() or 0
        trends["projects"] = _pct_change(current_projects, prev_projects)

        # 学校趋势
        current_schools = db.query(func.count(School.id)).filter(
            School.is_active == True  # noqa: E712
        ).scalar() or 0
        prev_schools = db.query(func.count(School.id)).filter(
            School.is_active == True,  # noqa: E712
            School.created_at <= thirty_days_ago,
        ).scalar() or 0
        trends["schools"] = _pct_change(current_schools, prev_schools)

        # 资金趋势
        current_funds = db.query(func.coalesce(func.sum(Fund.amount), 0)).filter(
            Fund.is_active == True  # noqa: E712
        ).scalar() or 0
        prev_funds = db.query(func.coalesce(func.sum(Fund.amount), 0)).filter(
            Fund.is_active == True,  # noqa: E712
            Fund.created_at <= thirty_days_ago,
        ).scalar() or 0
        trends["funds"] = _pct_change(float(current_funds), float(prev_funds))

    except Exception:
        # 趋势接口静默返回空会误导看板决策，升级为 warning 可观测
        logger.warning("趋势计算失败，返回空趋势", exc_info=True)

    return trends


def _pct_change(current, previous) -> float:
    """计算环比百分比变化"""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


@router.get("/stats")
async def get_dashboard_stats(
    refresh: bool = False,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """获取仪表盘统计数据（带缓存，按用户组织范围过滤，refresh=true 跳过缓存）"""
    user_id = getattr(current_user, "id", 0)
    cache_key = f"dashboard_stats:{user_id}"
    if not refresh:
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

    try:
        village_stats = _query_village_stats(db, data_scope)
        fund_stats = _query_fund_stats(db, data_scope)
        project_stats = _query_project_approval_stats(db, data_scope)

        result = {**village_stats, **fund_stats, **project_stats}

        # 计算30天环比趋势
        trends = _compute_trends(db, data_scope)
        result["trends"] = trends

        # 检查是否有任何非零数据
        has_data = any(
            isinstance(v, (int, float)) and v > 0
            for v in result.values()
            if not isinstance(v, dict)
        )

        # 如果完全没有数据，返回 None 而不是全0
        if not has_data:
            return None

        _set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error("仪表盘统计查询失败: %s", e, exc_info=True)
        # 降级返回 None，让前端显示空状态
        return None


@router.get("/kpi-trends", summary="KPI 趋势汇总（当前年度核心指标）")
async def get_kpi_trends(
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """返回当年 KPI：村数/人口/人均收入/经费投入（分析页与成效大屏用）"""
    try:
        village_stats = _query_village_stats(db, data_scope)
        fund_stats = _query_fund_stats(db, data_scope)

        # 人均收入: 取 annual_income 最近可用年份列的平均值
        income = _avg_per_capita_income(db, data_scope)

        return success_response(
            data={
                "villages": village_stats.get("total_villages", 0),
                "population": village_stats.get("total_population", 0),
                "income": round(income, 2),
                "investment": round(fund_stats.get("funds_allocated", 0) + fund_stats.get("total_funds", 0) / 2, 2),
            },
            message="KPI 趋势已获取",
        )
    except Exception as e:
        logger.error("KPI 趋势查询失败: %s", e, exc_info=True)
        return success_response(data={"villages": 0, "population": 0, "income": 0, "investment": 0}, message="获取失败")


@router.get("/yearly-trends", summary="年度趋势（村/人口/收入/经费投入，兼容分析页与大屏）")
async def get_yearly_trends(
    years: int = Query(5, ge=1, le=10),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """按最近 N 年返回:
    - years/villages/population/income: 分析页折线图
    - trends: [{year, total_planned, total_actual, project_count}] 大屏经费趋势
    """
    try:
        now_year = datetime.now().year
        year_list = list(range(now_year - years + 1, now_year + 1))

        villages_list = []
        population_list = []
        income_list = []
        trends_list = []

        for y in year_list:
            # 帮扶村(按创建年份统计, 无创建年份数据时按活跃村数占位)
            village_count = (
                db.query(func.count(SupportedVillage.id))
                .filter(SupportedVillage.is_active == True,  # noqa: E712
                        func.strftime("%Y", SupportedVillage.created_at) == str(y))
                .scalar()
            )
            villages_list.append(village_count or 0)

            # 人口(按年度表)
            pop = (
                db.query(func.coalesce(func.sum(VillagePopulation.total_population), 0))
                .filter(VillagePopulation.year == y)
                .scalar()
            )
            population_list.append(int(pop or 0))

            # 人均收入(该年可用列, 无则 0)
            income_list.append(round(_avg_per_capita_income(db, data_scope, year=y), 2))

            # 经费: 计划投入/实际投入 + 项目数
            fund_row = (
                db.query(
                    func.coalesce(func.sum(Fund.planned_amount), 0),
                    func.coalesce(func.sum(Fund.allocated_amount), 0),
                    func.count(Fund.id),
                )
                .filter(Fund.year == y)
                .first()
            )
            trends_list.append({
                "year": y,
                "total_planned": round(float(fund_row[0]) if fund_row else 0, 2),
                "total_actual": round(float(fund_row[1]) if fund_row else 0, 2),
                "project_count": int(fund_row[2]) if fund_row else 0,
            })

        return success_response(
            data={
                "years": year_list,
                "villages": villages_list,
                "population": population_list,
                "income": income_list,
                "trends": trends_list,
            },
            message="年度趋势已获取",
        )
    except Exception as e:
        logger.error("年度趋势查询失败: %s", e, exc_info=True)
        return success_response(data={"years": [], "trends": []}, message="获取失败")


def _avg_per_capita_income(db: Session, data_scope: OrgScopeFilter, year: Optional[int] = None) -> float:
    """人均收入: annual_income 表按年列存储(per_capita_income_{year})。
    未指定年份时取最大可用年份列的平均值。
    """
    try:
        from app.models.annual_income import AnnualIncome

        # 找出含 per_capita_income_ 前缀的最大年份列
        col_names = [c.name for c in AnnualIncome.__table__.columns if c.name.startswith("per_capita_income_")]
        if not col_names:
            return 0.0
        target_year = year
        if target_year is None:
            # 取最大可用年份列
            avail_years = [int(n.rsplit("_", 1)[1]) for n in col_names]
            target_year = max(avail_years)
        col_name = f"per_capita_income_{target_year}"
        if col_name not in col_names:
            return 0.0
        col = getattr(AnnualIncome, col_name)
        query = db.query(func.coalesce(func.avg(col), 0))
        if hasattr(AnnualIncome, "supported_village_id"):
            query = query.filter(
                AnnualIncome.supported_village_id.in_(
                    db.query(SupportedVillage.id).filter(SupportedVillage.is_active == True)  # noqa: E712
                )
            )
        val = query.scalar()
        return float(val or 0)
    except Exception:
        return 0.0


# ==================== 近期动态数据表 ====================
from app.core.transaction import safe_commit  # noqa: E402
from app.models.dashboard import (  # noqa: E402, F401
    DashboardActivity,
    HiddenDashboardActivity,
)


@router.get("/summary")
async def get_dashboard_summary(
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """仪表盘汇总接口：一次请求返回统计 + 近期动态，减少 HTTP 往返"""
    user_id = getattr(current_user, "id", 0)
    cache_key = f"dashboard_summary:{user_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        village_stats = _query_village_stats(db, data_scope)
        fund_stats = _query_fund_stats(db, data_scope)
        project_stats = _query_project_approval_stats(db, data_scope)
        stats = {**village_stats, **fund_stats, **project_stats}
    except Exception as e:
        logger.error("仪表盘汇总统计失败: %s", e, exc_info=True)
        stats = {}

    # 复用 recent-activities 逻辑
    activities = await get_recent_activities(current_user=current_user, db=db)

    result = {"stats": stats, "recent_activities": activities.get("items", [])}
    _set_cached(cache_key, result, ttl=120)  # 2 分钟缓存
    return result


def _fetch_hidden_activities() -> set:
    sess = SessionLocal()
    try:
        return {r[0] for r in sess.query(HiddenDashboardActivity.activity_id).all()}
    except Exception as e:
        logger.warning("获取隐藏动态列表失败: %s", e)
        return set()
    finally:
        sess.close()


def _fetch_custom_activities() -> list:
    sess = SessionLocal()
    items = []
    try:
        for act in sess.query(DashboardActivity).order_by(DashboardActivity.created_at.desc()).limit(10).all():
            items.append({
                "id": f"custom_{act.id}", "type": act.type or "project",
                "action": act.action or "", "target": act.target or "",
                "user": act.user or "系统",
                "time": act.created_at.strftime("%m-%d %H:%M") if act.created_at else "",
                "_custom": True,
            })
    except Exception as e:
        logger.warning("获取自定义动态失败: %s", e)
    finally:
        sess.close()
    return items


def _fetch_project_activities() -> list:
    sess = SessionLocal()
    items = []
    try:
        for p in sess.query(Project).order_by(Project.updated_at.desc()).limit(5).all():
            action = "更新了" if p.updated_at != p.created_at else "创建了"
            items.append({
                "id": f"project_{p.id}", "type": "project", "action": action,
                "target": p.name or "",
                "user": p.responsible_person or getattr(p, "leader", None) or "系统",
                "time": p.updated_at.strftime("%m-%d %H:%M") if p.updated_at else "",
            })
    except Exception as e:
        logger.warning("获取项目动态失败: %s", e)
    finally:
        sess.close()
    return items


def _fetch_fund_activities() -> list:
    sess = SessionLocal()
    items = []
    try:
        status_label_map = {"approved": "审批通过", "allocated": "已拨付", "pending": "待审批", "planned": "已规划"}
        for f in sess.query(Fund).order_by(Fund.updated_at.desc()).limit(5).all():
            items.append({
                "id": f"fund_{f.id}", "type": "fund",
                "action": status_label_map.get(f.status, "更新了"),
                "target": f.name or "",
                "user": getattr(f, "applicant", None) or "系统",
                "time": f.updated_at.strftime("%m-%d %H:%M") if f.updated_at else "",
            })
    except Exception as e:
        logger.warning("获取经费动态失败: %s", e)
    finally:
        sess.close()
    return items


def _fetch_approval_activities() -> list:
    sess = SessionLocal()
    items = []
    try:
        status_label_map = {"pending": "待审批", "approved": "已通过", "rejected": "已驳回", "withdrawn": "已撤回"}
        for a in (
            sess.query(ApprovalTask)
            .options(joinedload(ApprovalTask.submitter))
            .order_by(ApprovalTask.updated_at.desc())
            .limit(5).all()
        ):
            items.append({
                "id": f"approval_{a.id}", "type": "approval",
                "action": status_label_map.get(a.status, a.status),
                "target": a.title or f"{a.entity_type}#{a.entity_id}",
                "user": (a.submitter.username if a.submitter else None) or "系统",
                "time": (a.updated_at or a.created_at).strftime("%m-%d %H:%M")
                if (a.updated_at or a.created_at)
                else "",
            }
            )
    except Exception as e:
        logger.warning("获取审批动态失败: %s", e)
    finally:
        sess.close()
    return items


@router.get("/recent-activities")
async def get_recent_activities(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取近期动态（覆盖项目、经费、审批多类事件 + 自定义动态）

    优化：5个独立查询并行执行，响应时间从 sum(5) 降至 max(单次)。
    """
    cache_key = "dashboard_recent_activities"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    hidden_ids, custom_items, project_items, fund_items, approval_items = await asyncio.gather(
        asyncio.to_thread(_fetch_hidden_activities),
        asyncio.to_thread(_fetch_custom_activities),
        asyncio.to_thread(_fetch_project_activities),
        asyncio.to_thread(_fetch_fund_activities),
        asyncio.to_thread(_fetch_approval_activities),
    )

    items = custom_items + project_items + fund_items + approval_items

    if hidden_ids:
        items = [item for item in items if item["id"] not in hidden_ids]

    items.sort(key=lambda x: x.get("time", ""), reverse=True)
    result = {"items": items[:10]}
    _set_cached(cache_key, result, ttl=60)
    return result


class ActivityCreate(BaseModel):
    """创建动态请求体"""

    type: str = "project"
    action: str
    target: str


class ActivityUpdate(BaseModel):
    """更新动态请求体"""

    type: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None


@router.post("/recent-activities")
async def create_activity(
    data: ActivityCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建自定义动态"""
    try:
        activity = DashboardActivity(
            type=data.type,
            action=data.action,
            target=data.target,
            user=getattr(current_user, "name", None) or getattr(current_user, "username", None) or "系统",
        )
        db.add(activity)
        safe_commit(db)
        db.refresh(activity)
        # 清除缓存
        if _cache:
            try:
                _cache.delete("dashboard_recent_activities")
            except Exception:
                logger.debug("清除仪表盘活动缓存失败")
        return {
            "id": f"custom_{activity.id}",
            "type": activity.type,
            "action": activity.action,
            "target": activity.target,
            "user": activity.user,
            "time": activity.created_at.strftime("%m-%d %H:%M") if activity.created_at else "",
        }
    except Exception as e:
        logger.error("创建自定义动态失败: %s", e, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建动态失败：{str(e)}")


@router.put("/recent-activities/{activity_id}")
async def update_activity(
    activity_id: str,
    data: ActivityUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新自定义动态（仅本人或管理员）"""
    try:
        # 只能更新自定义动态
        if activity_id.startswith("custom_"):
            real_id = int(activity_id.replace("custom_", ""))
            activity = db.query(DashboardActivity).filter(DashboardActivity.id == real_id).first()
            if activity is None:
                raise HTTPException(status_code=404, detail="动态不存在")
            # 归属校验: 仅本人或管理员可修改
            actor = getattr(current_user, "username", "") or getattr(current_user, "name", "")
            owner = getattr(activity, "user", "")
            if owner != actor and not is_admin(current_user):
                raise HTTPException(status_code=403, detail="无权修改该动态")
            if data.type is not None:
                activity.type = data.type
            if data.action is not None:
                activity.action = data.action
            if data.target is not None:
                activity.target = data.target
            safe_commit(db)
            # 清除缓存
            if _cache:
                try:
                    _cache.delete("dashboard_recent_activities")
                except Exception:
                    logger.debug("清除仪表盘活动缓存失败")
            return success_response(message="更新成功")
        return success_response(message="无法更新系统自动生成的动态")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("更新自定义动态失败: %s", e, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新动态失败：{str(e)}")


@router.delete("/recent-activities/{activity_id}")
async def delete_activity(
    activity_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除动态（自定义动态物理删除，系统动态持久化隐藏）"""
    try:
        if activity_id.startswith("custom_"):
            # 自定义动态：物理删除（仅本人或管理员）
            real_id = int(activity_id.replace("custom_", ""))
            activity = db.query(DashboardActivity).filter(DashboardActivity.id == real_id).first()
            if activity:
                actor = getattr(current_user, "username", "") or getattr(current_user, "name", "")
                owner = getattr(activity, "user", "")
                if owner != actor and not is_admin(current_user):
                    raise HTTPException(status_code=403, detail="无权删除该动态")
                db.delete(activity)
                safe_commit(db)
        else:
            # 系统动态：写入隐藏表，确保刷新后不再出现
            existing = (
                db.query(HiddenDashboardActivity)
                .filter(HiddenDashboardActivity.activity_id == activity_id)
                .first()
            )
            if not existing:
                db.add(HiddenDashboardActivity(activity_id=activity_id))
                safe_commit(db)

        # 清除缓存
        if _cache:
            try:
                _cache.delete("dashboard_recent_activities")
            except Exception:
                logger.debug("清除仪表盘活动缓存失败")
        return success_response(message="删除成功")
    except Exception as e:
        logger.error("删除动态失败: %s", e, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除动态失败：{str(e)}")
