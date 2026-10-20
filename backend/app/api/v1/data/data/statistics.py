import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.data_permission import get_accessible_org_ids
from app.core.database import get_db
from app.core.permission_utils import is_admin
from app.core.security import get_current_user
from app.models.fund import Fund
from app.models.project import Project
from app.models.school import School, SchoolSupport
from app.models.user import User
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


def _calc_village_completeness(db: Session, SV, VP, VI, total_villages: int, scope_filter=None) -> int:
    """计算帮扶村数据完整率（百分比整数）

    检查维度：
    1. 基本信息字段：village_name, county, department, support_unit
    2. 地理坐标：latitude + longitude
    3. 人口数据：至少有1年 VillagePopulation 记录
    4. 收入数据：至少有1年 VillageIncome 记录

    每个帮扶村满分 6 个检查项，汇总所有村的通过项占比。

    2026-09-17 修复（软删分子 + 数据范围）：
    * 全部子计数只统计 is_active=True 的帮扶村。此前 4 个基本字段、坐标、
      人口、收入子计数一律不过滤软删（分母 sv_count 却是活跃村数），
      软删村仍计入分子 → 完整率可输出 >100%（实测 117）；
    * scope_filter：可选的数据域过滤回调（调用方传 _scoped 这类既有
      app.core.data_permission 入口）。传入后分子与分母取同一村集合，
      窄范围用户不会再看到全库聚合出的完整率；
    * 结果钳制到 [0, 100]，任何口径漂移都不再输出 >100% 的完整率。
    """
    if total_villages <= 0:
        return 0

    checks_per_village = 6
    total_checks = total_villages * checks_per_village
    passed = 0

    def _apply_scope(query):
        """把调用方的数据域过滤挂到子计数上（未传回调时保持原样）"""
        return scope_filter(query) if scope_filter is not None else query

    # 1. 基本信息字段（各字段非空计数；排除软删村）
    for col in [SV.village_name, SV.county, SV.department, SV.support_unit]:
        cnt = (
            _apply_scope(
                db.query(func.count(SV.id)).filter(
                    SV.is_active.is_(True), col.isnot(None), col != ""
                )
            ).scalar() or 0
        )
        passed += min(cnt, total_villages)

    # 2. 地理坐标（lat 和 lng 都非空才算通过；排除软删村）
    coords_filled = (
        _apply_scope(
            db.query(func.count(SV.id)).filter(
                SV.is_active.is_(True),
                SV.latitude.isnot(None),
                SV.longitude.isnot(None),
            )
        ).scalar() or 0
    )
    passed += min(coords_filled, total_villages)

    # 3. 人口数据（至少有1年记录的村数）——join 村表排除软删村与数据范围外的村
    pop_villages = (
        _apply_scope(
            db.query(func.count(func.distinct(VP.supported_village_id)))
            .join(SV, VP.supported_village_id == SV.id)
            .filter(SV.is_active.is_(True))
        ).scalar() or 0
    )
    passed += min(pop_villages, total_villages)

    # 4. 收入数据（至少有1年记录的村数）——同上
    # NOTE: VillageIncome 表名可能为 village_income 或 village_incomes
    income_villages = (
        _apply_scope(
            db.query(func.count(func.distinct(VI.supported_village_id)))
            .join(SV, VI.supported_village_id == SV.id)
            .filter(SV.is_active.is_(True))
        ).scalar() or 0
    )
    passed += min(income_villages, total_villages)

    return max(0, min(100, round(passed / total_checks * 100)))


@router.get("/summary")
async def get_summary(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    获取系统概览统计

    Task 4.2: 在查询服务中集成缓存
    - 缓存频繁访问的查询结果
    - 配置查询结果TTL（5分钟）
    """
    try:
        # 尝试从缓存获取（缓存键含用户，避免跨用户串数据）
        user_id = getattr(current_user, "id", 0)
        cache_key = f"summary:{user_id}"
        cached = await _get_cached_stats(cache_key)
        if cached:
            return cached

        # 缓存未命中，从数据库查询（H2：全部按调用者数据域收敛）
        from app.core.data_permission import apply_scope_filter
        from app.models.supported_village import SupportedVillage as SVModel

        def _scoped(query, model):
            return apply_scope_filter(query, current_user, model, db=db)

        users_count = _scoped(db.query(User).filter(User.is_active == True), User).count()  # noqa: E712
        villages_count = _scoped(
            db.query(SVModel).filter(SVModel.is_active.is_(True)), SVModel
        ).count()
        schools_count = _scoped(db.query(School).filter(School.is_active == True), School).count()  # noqa: E712
        projects_count = _scoped(db.query(Project).filter(Project.is_active == True), Project).count()  # noqa: E712
        funds_count = _scoped(db.query(Fund).filter(Fund.is_active == True), Fund).count()  # noqa: E712

        funds_sum = (
            _scoped(
                db.query(func.sum(Fund.amount)).filter(
                    Fund.status == "approved", Fund.is_active == True  # noqa: E712
                ),
                Fund,
            ).scalar()
            or 0
        )

        projects_by_status = _scoped(
            db.query(Project.status, func.count(Project.id)).filter(Project.is_active == True),  # noqa: E712
            Project,
        ).group_by(Project.status).all()
        projects_status_dist = {status: count for status, count in projects_by_status}

        active_projects = _scoped(
            db.query(Project).filter(
                Project.is_active == True, Project.status == "active"  # noqa: E712
            ),
            Project,
        ).count()
        completed_projects = _scoped(
            db.query(Project).filter(
                Project.is_active == True, Project.status == "completed"  # noqa: E712
            ),
            Project,
        ).count()

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
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


@router.get("/overview")
async def get_overview(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    数据总览接口 - 返回各模块概况、最后更新时间、健康评分、趋势数据（按调用者数据域收敛）
    """
    try:
        return await _get_overview_impl(db, current_user)
    except Exception as e:
        logger.error("数据总览查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


def _calc_health_score(
    villages_count: int, projects_count: int, schools_count: int, funds_count: int, completeness
):
    """数据健康评分 (0-100)：综合各模块数据量与帮扶村完整率。

    从 _get_overview_impl 拆出，使主聚合流程的控制复杂度维持在门禁内。
    """
    module_scores = []
    if villages_count > 0:
        module_scores.append(min(100, completeness))
    else:
        module_scores.append(0)
    module_scores.append(100 if projects_count > 0 else 0)
    module_scores.append(100 if schools_count > 0 else 0)
    module_scores.append(100 if funds_count > 0 else 0)
    return round(sum(module_scores) / max(len(module_scores), 1))


def _build_7day_trend(day_counts) -> list:
    """把 (日期 -> 操作数) 映射补齐成连续 7 天趋势（含无数据日补 0）。"""
    trend = []
    now = datetime.now()
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%m-%d")
        day_key = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append({"date": day, "operations": day_counts.get(day_key, 0)})
    return trend


def _build_recent_logs(logs) -> list:
    """把审计日志 ORM 行转成看板所需的精简字典。"""
    return [
        {
            "id": log.id,
            "action": f"{log.action or ''} {log.resource_type or ''}".strip(),
            "user": log.username or f"用户{log.user_id or ''}",
            "time": str(log.created_at) if log.created_at else "",
        }
        for log in logs
    ]


async def _get_overview_impl(db: Session, current_user=None):
    """数据总览聚合（H2：按调用者数据域收敛）。

    模型覆盖：帮扶村/项目/学校/经费均带 organization_id（apply_scope_filter 直接过滤）；
    用户总数按可访问组织收敛；审计日志（今日操作/7 天趋势/最近操作）在受限范围内
    收敛为"本人操作"，避免向任意登录用户回显全局操作流水（M9 同类问题）。
    """
    from app.core.data_permission import OrgScopeFilter, apply_scope_filter
    from app.models.audit import AuditLog
    from app.models.supported_village import SupportedVillage
    from app.utils.time_utils import utcnow_naive

    def _scoped(query, model, org_field="organization_id"):
        """统一数据域过滤入口（严格口径：部门级 admin 仅本组织及子树）。

        current_user 为 None 表示"无用户上下文"（内部/定时调用），保持系统级口径；
        端点路径始终透传真实用户。
        """
        if current_user is None:
            return query
        return apply_scope_filter(query, current_user, model, org_field, db=db)

    def _users_query():
        """用户统计口径：受限用户只统计可访问组织内的活跃用户。

        User 模型无 created_by 列（"仅本人"范围无法表达），故不经
        apply_scope_filter 的 OWN 分支，直接按可访问组织收敛。
        """
        query = db.query(User).filter(User.is_active == True)  # noqa: E712
        if current_user is not None and not is_admin(current_user):
            org_ids = get_accessible_org_ids(current_user, db=db)
            query = query.filter(User.organization_id.in_(org_ids or []))
        return query

    villages_count = _scoped(
        db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True)), SupportedVillage
    ).count()
    projects_count = _scoped(db.query(Project).filter(Project.is_active == True), Project).count()  # noqa: E712
    schools_count = _scoped(db.query(School).filter(School.is_active == True), School).count()  # noqa: E712
    funds_count = _scoped(db.query(Fund).filter(Fund.is_active == True), Fund).count()  # noqa: E712

    users_count = _users_query().count()

    funds_total = (
        _scoped(
            db.query(func.sum(Fund.amount)).filter(
                Fund.status == "approved", Fund.is_active == True  # noqa: E712
            ),
            Fund,
        ).scalar()
        or 0
    )

    # 审计日志范围：全量访问者看全局；受限用户只看本人操作（不泄漏他人操作流水）
    audit_scope = OrgScopeFilter(is_admin=True)
    if current_user is not None and not is_admin(current_user):
        audit_scope = OrgScopeFilter(
            is_admin=False,
            self_only=True,
            user_id=getattr(current_user, "id", None),
        )

    def _audit_scoped(query):
        return audit_scope.filter_by_org_ids(query, AuditLog.user_id, created_by_column=AuditLog.user_id)

    # 各模块最后更新时间
    def _last_update(model):
        col = getattr(model, "updated_at", None) or getattr(model, "created_at", None)
        if col is None:  # pragma: no cover —— 调用方仅传入 Village/Project/Fund/School/User，均带时间戳，防御分支不可达
            return None
        if model is User:
            val = _users_query().with_entities(func.max(col)).scalar()
        else:
            val = _scoped(db.query(func.max(col)), model).scalar()
        return str(val) if val else None

    modules = [
        {
            "module": "帮扶村数据",
            "records": villages_count,
            "lastUpdate": _last_update(SupportedVillage),
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

    sv_count = villages_count
    # _calc_village_completeness 的 scope_filter 是**单参**回调，而 _scoped 需 (query, model)；
    # 这里绑定默认 model 让分子/分母同源（详见 2026-09-17 修复注释）。直接传 _scoped 会
    # TypeError: missing 1 required positional argument: 'model'。
    completeness = (
        _calc_village_completeness(
            db, SV, VP, VI, sv_count, lambda q, _m=SV: _scoped(q, _m)
        )
        if sv_count > 0
        else 0
    )

    # 数据健康评分 (0-100) — 综合考虑各模块数据量和完整率
    health_score = _calc_health_score(
        villages_count, projects_count, schools_count, funds_count, completeness
    )

    # 「今日/近 7 天」按**本地日历**解释，而 AuditLog.created_at 是 UTC 墙钟列：
    # 必须先把本地日界平移到 UTC 再比较、并给分桶键加同样的偏移，否则 UTC+8 下
    # 「今日」从本地 08:00 才起算（漏掉 00:00–08:00 的操作），日桶也会错位。
    # 偏移取「本地墙钟 − UTC 墙钟」（后者走 time_utils 单一事实源），
    # 避免 astimezone().utcoffset() 的 None 分支。
    # 必须取整到秒：两次取时相差若干微秒，直接 int() 截断会得到 28799 秒（UTC+8），
    # 使日界整体偏移 1 秒。
    local_offset = timedelta(seconds=round((datetime.now() - utcnow_naive()).total_seconds()))
    local_shift = f"{int(local_offset.total_seconds())} seconds"

    # 今日操作数
    today_start = (
        datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - local_offset
    )
    today_ops = 0
    try:
        today_ops = _audit_scoped(
            db.query(AuditLog).filter(AuditLog.created_at >= today_start)
        ).count()
    except Exception:
        logger.warning("查询今日操作数失败（看板将显示 0）", exc_info=True)

    # 近7天数据趋势（单次 GROUP BY 查询替代 7 次循环查询）
    trend = []
    try:
        week_start = (datetime.now() - timedelta(days=6)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - local_offset
        local_day = func.date(AuditLog.created_at, local_shift)
        daily_results = _audit_scoped(
            db.query(local_day.label("day"), func.count(AuditLog.id).label("cnt")).filter(
                AuditLog.created_at >= week_start
            )
        ).group_by(local_day).all()
        day_counts = {r.day: r.cnt for r in daily_results}
    except Exception:
        logger.warning("查询近7天趋势失败（看板趋势将为空）", exc_info=True)
        day_counts = {}

    trend = _build_7day_trend(day_counts)

    # 最近操作记录
    recent_logs = []
    try:
        logs = _audit_scoped(db.query(AuditLog)).order_by(AuditLog.created_at.desc()).limit(8).all()
        recent_logs = _build_recent_logs(logs)
    except Exception:
        logger.warning("查询最近操作记录失败（最近操作列表将为空）", exc_info=True)

    return {
        "villages": villages_count,
        "projects": projects_count,
        "schools": schools_count,
        "users": users_count,
        "funds_amount": float(funds_total),
        "completeness": completeness,
        "health_score": health_score,
        "today_operations": today_ops,
        "modules": modules,
        "filing_rates": [
            {"module": "帮扶村", "rate": completeness},
            {"module": "帮扶项目", "rate": 100 if projects_count > 0 else 0},
            {"module": "帮扶学校", "rate": 100 if schools_count > 0 else 0},
            {"module": "经费管理", "rate": 100 if funds_count > 0 else 0},
        ],
        "trend": trend,
        "recent_logs": recent_logs,
    }


@router.get("/villages/distribution")
async def get_villages_distribution(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from app.core.data_permission import apply_scope_filter
        from app.models.supported_village import SupportedVillage, VillagePopulation

        def _scoped(query):
            return apply_scope_filter(query, current_user, SupportedVillage, db=db)

        by_status = _scoped(
            db.query(SupportedVillage.transition_status, func.count(SupportedVillage.id)).filter(
                SupportedVillage.is_active.is_(True)
            )
        ).group_by(SupportedVillage.transition_status).all()
        status_data = [{"name": status or "未分类", "value": count} for status, count in by_status]

        # 人口最多的村庄：取每个村最新年人口（避免 N+1）；软删村排除
        pop_subq = (
            db.query(
                VillagePopulation.supported_village_id,
                func.max(VillagePopulation.year).label("max_year"),
            )
            .group_by(VillagePopulation.supported_village_id)
            .subquery()
        )
        top_villages = (
            _scoped(
                db.query(SupportedVillage.village_name, VillagePopulation.total_population)
                .join(pop_subq, pop_subq.c.supported_village_id == SupportedVillage.id)
                .join(
                    VillagePopulation,
                    and_(
                        VillagePopulation.supported_village_id == SupportedVillage.id,
                        VillagePopulation.year == pop_subq.c.max_year,
                    ),
                )
                .filter(SupportedVillage.is_active.is_(True))
            )
            .order_by(VillagePopulation.total_population.desc())
            .limit(10)
            .all()
        )
        top_data = [{"name": name, "value": population or 0} for name, population in top_villages]

        by_province = _scoped(
            db.query(SupportedVillage.province, func.count(SupportedVillage.id)).filter(
                SupportedVillage.is_active.is_(True)
            )
        ).group_by(SupportedVillage.province).all()
        province_data = [{"name": province or "未知", "value": count} for province, count in by_province if province]

        return success_response(
            data={"by_status": status_data, "top_population": top_data, "by_province": province_data}
        )
    except Exception as e:
        logger.error("帮扶村分布统计查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


@router.get("/projects/statistics")
async def get_projects_statistics(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from app.core.data_permission import apply_scope_filter

        def _scoped(query):
            return apply_scope_filter(query, current_user, Project, db=db)

        by_status = _scoped(
            db.query(Project.status, func.count(Project.id)).filter(Project.is_active == True)  # noqa: E712
        ).group_by(Project.status).all()
        status_data = [{"name": status, "value": count} for status, count in by_status]

        by_type = _scoped(
            db.query(Project.type, func.count(Project.id)).filter(Project.is_active == True)  # noqa: E712
        ).group_by(Project.type).all()
        type_data = [{"name": ptype or "未分类", "value": count} for ptype, count in by_type if ptype]

        budget_sum = (
            _scoped(db.query(func.sum(Project.budget)).filter(Project.is_active == True)).scalar() or 0  # noqa: E712
        )
        invested_sum = (
            _scoped(
                db.query(func.sum(Project.invested_amount)).filter(Project.is_active == True)  # noqa: E712
            ).scalar()
            or 0
        )

        avg_progress = (
            _scoped(db.query(func.avg(Project.progress)).filter(Project.is_active == True)).scalar() or 0  # noqa: E712
        )

        recent_projects = (
            _scoped(db.query(Project).filter(Project.is_active == True))  # noqa: E712
            .order_by(Project.created_at.desc())
            .limit(5)
            .all()
        )
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
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


@router.get("/funds/statistics")
async def get_funds_statistics(year: int = None, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from app.core.data_permission import apply_scope_filter

        def _scoped(query):
            return apply_scope_filter(query, current_user, Fund, db=db)

        query = _scoped(db.query(Fund).filter(Fund.is_active == True))  # noqa: E712

        if year:
            query = query.filter(func.strftime("%Y", Fund.date) == str(year))

        by_type = query.with_entities(Fund.type, func.count(Fund.id), func.sum(Fund.amount)).all()
        type_data = [
            {"type": ftype or "未分类", "count": count, "total_amount": total or 0} for ftype, count, total in by_type
        ]

        total_amount = query.with_entities(func.sum(Fund.amount)).scalar() or 0
        approved_amount = (
            _scoped(
                db.query(func.sum(Fund.amount)).filter(
                    Fund.status == "approved", Fund.is_active == True  # noqa: E712
                )
            ).scalar()
            or 0
        )

        monthly_stats = (
            _scoped(
                db.query(
                    func.strftime("%Y-%m", Fund.date).label("month"),
                    func.count(Fund.id).label("count"),
                    func.sum(Fund.amount).label("amount"),
                ).filter(Fund.date.isnot(None), Fund.is_active == True)  # noqa: E712
            )
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
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


@router.get("/schools/statistics")
async def get_schools_statistics(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from app.core.data_permission import apply_scope_filter

        def _scoped(query):
            """学校子表经 schools.organization_id 收敛（SchoolSupport 自身无组织列）。"""
            return apply_scope_filter(query, current_user, School, db=db)

        by_type = _scoped(
            db.query(School.type, func.count(School.id)).filter(School.is_active == True)  # noqa: E712
        ).group_by(School.type).all()
        type_data = [{"name": stype or "未分类", "value": count} for stype, count in by_type if stype]

        total_students = (
            _scoped(
                db.query(func.sum(School.student_count)).filter(School.is_active == True)  # noqa: E712
            ).scalar()
            or 0
        )
        total_teachers = (
            _scoped(
                db.query(func.sum(School.teacher_count)).filter(School.is_active == True)  # noqa: E712
            ).scalar()
            or 0
        )

        supports_by_type = (
            _scoped(
                db.query(SchoolSupport.support_type, func.count(SchoolSupport.id))
                .join(School, SchoolSupport.school_id == School.id)
                .filter(School.is_active == True)  # noqa: E712
            )
            .group_by(SchoolSupport.support_type)
            .all()
        )
        support_data = [{"name": sptype or "未分类", "value": count} for sptype, count in supports_by_type]

        total_support_amount = (
            _scoped(
                db.query(func.sum(SchoolSupport.amount))
                .join(School, SchoolSupport.school_id == School.id)
                .filter(
                    SchoolSupport.amount.isnot(None),
                    School.is_active == True,  # noqa: E712
                )
            ).scalar()
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
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


@router.get("/analysis")
async def get_analysis_data(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    数据统计分析页面聚合接口
    返回投入趋势、帮扶分类统计、地区分布等
    """
    try:
        return await _get_analysis_data_impl(db, current_user)
    except Exception as e:
        logger.error("分析数据查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


def _aggregate_transition_fund_items(items_rows):
    """按年度聚合 ``SupportedVillage.transition_fund_items`` 明细 JSON。

    H3 权威经费源：与列表 KPI、年度对比同源，消除历史上读空的 SupportFunding
    子表导致趋势图恒空白的缺陷。逐行容错——单个村的脏 JSON 静默跳过，不拖垮
    整份分析聚合。

    Returns:
        (year_mil, year_loc) 两个 ``{年份: 金额}`` 字典。
    """
    year_mil = {}
    year_loc = {}
    for row in items_rows:
        items_json = row[0] if isinstance(row, (tuple, list)) else row
        if not items_json:
            continue
        try:
            parsed = json.loads(items_json)
        except (ValueError, TypeError):
            continue
        if not isinstance(parsed, list):
            continue
        for it in parsed:
            if not isinstance(it, dict):
                continue
            try:
                yr = int(it.get("year"))
            except (TypeError, ValueError):
                continue
            year_mil[yr] = year_mil.get(yr, 0.0) + float(it.get("militaryInvestment") or 0)
            year_loc[yr] = year_loc.get(yr, 0.0) + float(it.get("localInvestment") or 0)
    return year_mil, year_loc


def _build_investment_trend(year_mil, year_loc, total_villages, total_investment):
    """构造 2021-2025 投入趋势列表。

    仅在「有帮扶村且有经费数据」时输出——没有帮扶村时趋势图没有实际意义。
    has_funding_data 基于权威经费源（汇总列或明细 JSON）。
    """
    has_funding_data = total_investment > 0 or bool(year_mil) or bool(year_loc)
    if not (total_villages > 0 and has_funding_data):
        return []

    trend = []
    prev_total = 0
    for yr in (2021, 2022, 2023, 2024, 2025):
        mil_f = year_mil.get(yr, 0.0)
        loc_f = year_loc.get(yr, 0.0)
        yr_total = mil_f + loc_f
        growth = round((yr_total - prev_total) / max(prev_total, 1) * 100, 1) if prev_total > 0 else 0
        trend.append(
            {"year": str(yr), "military": mil_f, "local": loc_f, "total": yr_total, "growth": growth}
        )
        prev_total = yr_total if yr_total > 0 else prev_total
    return trend


async def _get_analysis_data_impl(db: Session, current_user):
    from app.models.supported_village import (ConsumptionSupport,
                                              EducationSupport,
                                              EmploymentSupport,
                                              IndustrySupport,
                                              InfrastructureImprovement,
                                              MedicalSupport,
                                              PartyBuildingSupport,
                                              SupportedVillage,
                                              VillageIncome, VillagePopulation)
    from app.core.data_permission import apply_scope_filter

    def _scoped(q, model=SupportedVillage):
        """H3：统计查询统一附加数据隔离。

        current_user 为必填位置参数（fail-closed，对齐 W5-006）：漏传即在调用点
        抛 TypeError，而非静默跳过隔离返回跨组织数据。

        W25：新增 ``model`` 参数 —— 原先硬绑 ``SupportedVillage``，导致
        ``active_projects``（Project 模型）无法复用本入口而直查全库
        （跨组织规模泄漏，且与 get_summary 的同名指标两套口径）。
        """
        return apply_scope_filter(q, current_user, model, db=db)

    # --- 概览统计（软删村/项目不参与统计） ---
    total_villages = _scoped(
        db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
    ).count()
    active_projects = _scoped(
        db.query(Project).filter(
            Project.is_active == True,  # noqa: E712
            Project.status.in_(["in_progress", "approved", "active"]),
        ),
        Project,
    ).count()

    # 总投入资金（H3：附加数据隔离，与列表 KPI(H1) 同源同口径）
    mil_total = (
        _scoped(
            db.query(func.coalesce(func.sum(SupportedVillage.transition_fund_military_total), 0))
            .filter(SupportedVillage.is_active.is_(True))
        )
        .scalar()
        or 0
    )
    loc_total = (
        _scoped(
            db.query(func.coalesce(func.sum(SupportedVillage.transition_fund_local_total), 0))
            .filter(SupportedVillage.is_active.is_(True))
        )
        .scalar()
        or 0
    )
    total_investment = float(mil_total) + float(loc_total)

    # 数据完整率 — 基于关键字段实际填写率
    # 2026-09-17 修复：分子同样套 _scoped —— 否则窄范围用户的完整率分子取全库计数、
    # 分母只取本范围村数（既虚高又泄漏范围外数据规模）。传 _scoped 使分子分母同源。
    # 注意：本作用域内的 _scoped 是单参回调（见其定义），正好匹配
    # _calc_village_completeness 的 scope_filter 契约，直接传入即可。
    completeness = _calc_village_completeness(
        db, SupportedVillage, VillagePopulation, VillageIncome, total_villages, _scoped
    )

    # --- 投入趋势 (2021-2025) ---
    # H3：经费口径统一到权威源 SupportedVillage.transition_fund_items(按年度明细 JSON)
    # 及 transition_fund_* 汇总列，消除与列表 KPI(H1) 的同源分裂——此前 has_funding_data
    # 与趋势图读取从未被生产路径写入的 SupportFunding 子表，导致趋势图恒空白。
    items_rows = (
        _scoped(
            db.query(SupportedVillage.transition_fund_items)
            .filter(SupportedVillage.is_active.is_(True))
        )
        .all()
    )
    year_mil, year_loc = _aggregate_transition_fund_items(items_rows)
    investment_trend = _build_investment_trend(
        year_mil, year_loc, total_villages, total_investment
    )

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
        # 合并 count + sum 为单次查询（减少 50% 查询数）；join 村表排除软删村数据
        # 2026-09-17 修复：分类聚合此前未套数据范围，窄范围用户可见全库分类汇总。
        result = (
            _scoped(
                db.query(
                    func.count(1).label("cnt"),
                    func.coalesce(func.sum(getattr(model, inv_field)), 0).label("inv"),
                )
                .join(SupportedVillage, model.supported_village_id == SupportedVillage.id)
                .filter(SupportedVillage.is_active.is_(True))
            )
            .first()
        )
        cnt = (result.cnt if result else 0) or 0
        inv = float(result.inv if result else 0) or 0.0
        total_cat_inv += inv
        cat_stats.append(
            {"category": cat_name, "count": cnt, "investment": round(inv, 2), "beneficiaries": 0, "ratio": 0}
        )

    # 消费帮扶（合并 count + sum；排除软删村；2026-09-17 补数据范围）
    cons_result = (
        _scoped(
            db.query(
                func.count(1).label("cnt"),
                func.coalesce(func.sum(ConsumptionSupport.village_products_purchase), 0).label("inv"),
            )
            .join(SupportedVillage, ConsumptionSupport.supported_village_id == SupportedVillage.id)
            .filter(SupportedVillage.is_active.is_(True))
        )
        .first()
    )
    cons_cnt = (cons_result.cnt if cons_result else 0) or 0
    cons_inv = float(cons_result.inv if cons_result else 0) or 0.0
    total_cat_inv += cons_inv
    cat_stats.append(
        {"category": "消费帮扶", "count": cons_cnt, "investment": round(cons_inv, 2), "beneficiaries": 0, "ratio": 0}
    )

    # 就业帮扶（合并 count + sum；排除软删村；2026-09-17 补数据范围）
    emp_result = (
        _scoped(
            db.query(
                func.count(1).label("cnt"),
                func.coalesce(func.sum(EmploymentSupport.trained_population), 0).label("ben"),
            )
            .join(SupportedVillage, EmploymentSupport.supported_village_id == SupportedVillage.id)
            .filter(SupportedVillage.is_active.is_(True))
        )
        .first()
    )
    emp_cnt = (emp_result.cnt if emp_result else 0) or 0
    emp_ben = (emp_result.ben if emp_result else 0) or 0
    cat_stats.append({"category": "就业帮扶", "count": emp_cnt, "investment": 0, "beneficiaries": int(emp_ben), "ratio": 0})

    # 计算占比
    if total_cat_inv > 0:
        for cs in cat_stats:
            cs["ratio"] = round(cs["investment"] / total_cat_inv * 100) if cs["investment"] > 0 else 0

    # --- 地区分布 ---
    # 2026-09-17 修复：县区聚合此前只有 is_active，窄范围用户可见全州县区投入。
    region_stats = []
    county_data = (
        _scoped(
            db.query(
                SupportedVillage.county,
                func.count(SupportedVillage.id),
                func.coalesce(func.sum(SupportedVillage.transition_fund_military_total), 0),
                func.coalesce(func.sum(SupportedVillage.transition_fund_local_total), 0),
            )
            .filter(
                SupportedVillage.county.isnot(None),
                SupportedVillage.county != "",
                SupportedVillage.is_active.is_(True),
            )
            .group_by(SupportedVillage.county)
        )
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

    # --- 年度关键指标对比（按年份聚合，供前端年度对比图/描述展示） ---
    yearly_comparison = {"years": [], "villages": {}, "investment": {}, "income": {}}
    # 各年有数据的帮扶村数（以人口数据为准；软删村排除；2026-09-17 补数据范围）
    pop_rows = (
        _scoped(
            db.query(VillagePopulation.year, func.count(func.distinct(VillagePopulation.supported_village_id)))
            .join(SupportedVillage, VillagePopulation.supported_village_id == SupportedVillage.id)
            .filter(SupportedVillage.is_active.is_(True))
            .group_by(VillagePopulation.year)
        )
        .all()
    )
    for yr, cnt in pop_rows:
        yearly_comparison["years"].append(str(yr))
        yearly_comparison["villages"][str(yr)] = cnt
    # 各年投入（万元）——H3：复用 transition_fund_items 明细聚合的 year_mil/year_loc，
    # 与投入趋势、列表 KPI 保持同一权威口径（不再读空的 SupportFunding 子表）。
    for yr in sorted(set(year_mil) | set(year_loc)):
        yearly_comparison["investment"][str(yr)] = round(year_mil.get(yr, 0.0) + year_loc.get(yr, 0.0), 2)
    # 各年人均收入均值（万元）——2026-09-17 补 join 村表 + 数据范围（此前全库无隔离）
    inc_rows = (
        _scoped(
            db.query(VillageIncome.year, func.avg(VillageIncome.per_capita_income))
            .join(SupportedVillage, VillageIncome.supported_village_id == SupportedVillage.id)
            .filter(SupportedVillage.is_active.is_(True))
            .group_by(VillageIncome.year)
        )
        .all()
    )
    for yr, avg_inc in inc_rows:
        yearly_comparison["income"][str(yr)] = round(float(avg_inc or 0), 4)
    yearly_comparison["years"] = sorted(set(yearly_comparison["years"]))

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
        "yearly_comparison": yearly_comparison,
    }


@router.get("/dashboard")
async def get_dashboard_data(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    获取仪表盘数据

    Task 4.2: 在查询服务中集成缓存
    """
    try:
        # 尝试从缓存获取（缓存键含用户，避免跨用户串数据）
        user_id = getattr(current_user, "id", 0)
        cache_key = f"dashboard:{user_id}"
        cached = await _get_cached_stats(cache_key)
        if cached:
            return cached

        from app.core.data_permission import apply_scope_filter
        from app.models.supported_village import SupportedVillage

        def _scoped(query, model):
            return apply_scope_filter(query, current_user, model, db=db)

        summary = {
            "total_users": _scoped(db.query(User), User).count(),
            "total_villages": _scoped(
                db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True)), SupportedVillage
            ).count(),
            "total_schools": _scoped(db.query(School).filter(School.is_active == True), School).count(),  # noqa: E712
            "total_projects": _scoped(
                db.query(Project).filter(Project.is_active == True), Project  # noqa: E712
            ).count(),
            "active_projects": _scoped(
                db.query(Project).filter(
                    Project.is_active == True, Project.status == "active"  # noqa: E712
                ),
                Project,
            ).count(),
            "total_funds": _scoped(db.query(Fund).filter(Fund.is_active == True), Fund).count(),  # noqa: E712
        }

        funds_total = (
            _scoped(
                db.query(func.sum(Fund.amount)).filter(
                    Fund.status == "approved", Fund.is_active == True  # noqa: E712
                ),
                Fund,
            ).scalar()
            or 0
        )
        summary["approved_funds"] = funds_total

        recent_activities = (
            _scoped(db.query(Project).filter(Project.is_active == True), Project)  # noqa: E712
            .order_by(Project.updated_at.desc())
            .limit(5)
            .all()
        )
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

        projects_by_status = _scoped(
            db.query(Project.status, func.count(Project.id)).filter(Project.is_active == True),  # noqa: E712
            Project,
        ).group_by(Project.status).all()
        summary["projects_chart"] = [{"name": status, "value": count} for status, count in projects_by_status]

        # 写入缓存
        await _cache_stats(cache_key, summary)

        return summary
    except Exception as e:
        logger.error("仪表盘数据查询失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")
