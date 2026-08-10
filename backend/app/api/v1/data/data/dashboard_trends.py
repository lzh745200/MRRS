"""
仪表盘 KPI 趋势 & 年度对比 API
提供 Dashboard.vue 所需的真实历史统计数据，替代前端示意数据
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.unified_data_scope import OrgScopeFilter, get_org_scope
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.fund import Fund
from app.models.supported_village import SupportedVillage, VillageIncome, VillagePopulation
from app.models.user import User
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard/trends", tags=["仪表盘趋势同比"])


def _yoy(cur_val: float, prev_val: float) -> float:
    """计算同比变化百分比"""
    if prev_val == 0:
        return 0.0 if cur_val == 0 else 100.0
    return round((cur_val - prev_val) / prev_val * 100, 1)


@router.get("/kpi-trends", summary="KPI 年度同比趋势")
def get_kpi_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
):
    """返回关键指标的年度同比变化百分比，供 Dashboard KPI 卡片使用"""
    try:
        now = datetime.now()
        cur_year = now.year
        prev_year = cur_year - 1

        # --- 帮扶村数量同比 ---
        def _village_count(year: int) -> int:
            q = db.query(func.count(SupportedVillage.id)).filter(
                SupportedVillage.is_active == True,  # noqa: E712
                func.extract("year", SupportedVillage.created_at) == year,
            )
            q = data_scope.filter_by_org_ids(
                q, SupportedVillage.organization_id,
                created_by_column=SupportedVillage.created_by,
            )
            return q.scalar() or 0

        villages_cur = _village_count(cur_year)
        villages_prev = _village_count(prev_year)

        # --- 人口同比 ---
        def _pop_sum(year: int) -> int:
            return int(
                db.query(func.coalesce(func.sum(VillagePopulation.total_population), 0))
                .filter(VillagePopulation.year == year)
                .scalar() or 0
            )

        pop_cur = _pop_sum(cur_year)
        pop_prev = _pop_sum(prev_year)

        # --- 投资/经费同比 ---
        def _fund_sum(year: int) -> float:
            return float(
                db.query(func.coalesce(func.sum(Fund.planned_amount), 0))
                .filter(func.extract("year", Fund.created_at) == year)
                .scalar() or 0
            )

        invest_cur = _fund_sum(cur_year)
        invest_prev = _fund_sum(prev_year)

        # --- 人均收入同比 ---
        # 收入字段在 VillageIncome 模型上（此前误判为 VillagePopulation，
        # 导致 hasattr 恒为 False、收入同比恒为 0 的死代码缺陷）
        income_cur = 0.0
        income_prev = 0.0
        if hasattr(VillageIncome, "per_capita_income"):
            income_cur = float(
                db.query(func.coalesce(func.avg(VillageIncome.per_capita_income), 0))
                .filter(VillageIncome.year == cur_year).scalar() or 0
            )
            income_prev = float(
                db.query(func.coalesce(func.avg(VillageIncome.per_capita_income), 0))
                .filter(VillageIncome.year == prev_year).scalar() or 0
            )

        return success_response(data={
            "villages": _yoy(villages_cur, villages_prev),
            "population": _yoy(pop_cur, pop_prev),
            "income": _yoy(income_cur, income_prev),
            "investment": _yoy(invest_cur, invest_prev),
            "current_year": cur_year,
            "previous_year": prev_year,
        })
    except Exception as e:
        logger.error("KPI趋势查询失败: %s", e, exc_info=True)
        return success_response(data={
            "villages": 0, "population": 0, "income": 0, "investment": 0,
            "current_year": datetime.now().year,
            "previous_year": datetime.now().year - 1,
        })


@router.get("/yearly-trends", summary="年度趋势对比数据")
def get_yearly_trends(
    years: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
):
    """返回近 N 年的年度汇总数据，供 Dashboard 趋势图使用"""
    try:
        now = datetime.now()
        cur_year = now.year
        year_list = list(range(cur_year - years + 1, cur_year + 1))

        villages_data = []
        population_data = []
        income_data = []
        investment_data = []

        for y in year_list:
            # 帮扶村累计数量
            vq = db.query(func.count(SupportedVillage.id)).filter(
                SupportedVillage.is_active == True,  # noqa: E712
                func.extract("year", SupportedVillage.created_at) <= y,
            )
            vq = data_scope.filter_by_org_ids(
                vq, SupportedVillage.organization_id,
                created_by_column=SupportedVillage.created_by,
            )
            villages_data.append(vq.scalar() or 0)

            # 人口
            pop = int(
                db.query(func.coalesce(func.sum(VillagePopulation.total_population), 0))
                .filter(VillagePopulation.year == y).scalar() or 0
            )
            population_data.append(pop)

            # 人均收入
            inc = 0.0
            if hasattr(VillageIncome, "per_capita_income"):
                inc = float(
                    db.query(func.coalesce(func.avg(VillageIncome.per_capita_income), 0))
                    .filter(VillageIncome.year == y).scalar() or 0
                )
            income_data.append(round(inc, 1))

            # 投资/经费
            inv = float(
                db.query(func.coalesce(func.sum(Fund.planned_amount), 0))
                .filter(func.extract("year", Fund.created_at) == y).scalar() or 0
            )
            investment_data.append(round(inv, 1))

        return success_response(data={
            "years": year_list,
            "villages": villages_data,
            "population": population_data,
            "income": income_data,
            "investment": investment_data,
        })
    except Exception as e:
        logger.error("年度趋势查询失败: %s", e, exc_info=True)
        cur_year = datetime.now().year
        year_list = list(range(cur_year - years + 1, cur_year + 1))
        return success_response(data={
            "years": year_list,
            "villages": [0] * len(year_list),
            "population": [0] * len(year_list),
            "income": [0] * len(year_list),
            "investment": [0] * len(year_list),
        })
