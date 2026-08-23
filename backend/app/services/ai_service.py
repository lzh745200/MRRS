"""
AI服务管理模块
提供本地统计分析引擎：趋势分析、项目进度分析、经费效率分析、村庄对比

本地单机版 — 不依赖外部 AI 服务，所有计算基于 SQLAlchemy 聚合查询。
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AIServiceManager:
    """本地统计分析引擎"""

    def __init__(self):
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("统计分析引擎初始化完成（本地模式）")

    async def get_service_status(self) -> Dict[str, Any]:
        return {
            "local_analysis": {
                "status": "available",
                "type": "local",
                "description": "本地统计分析服务",
            }
        }

    # ------------------------------------------------------------------
    # 通用入口
    # ------------------------------------------------------------------

    async def analyze_data(
        self,
        data: Dict[str, Any],
        analysis_type: str = "summary",
        db: Optional[Session] = None,
        user: Any = None,
    ) -> Dict[str, Any]:
        try:
            if analysis_type == "summary":
                return self._generate_summary(data)
            elif analysis_type == "trend" and db:
                return self.analyze_income_trend(db, user=user)
            elif analysis_type == "project_progress" and db:
                return self.analyze_project_progress(db, user=user)
            elif analysis_type == "fund_efficiency" and db:
                return self.analyze_fund_efficiency(db, user=user)
            elif analysis_type == "compare" and db:
                return self.compare_villages(db, user=user)
            else:
                return {
                    "result": "unsupported",
                    "message": f"不支持的分析类型: {analysis_type}",
                }
        except Exception as e:
            logger.error("统计分析失败: %s", e, exc_info=True)
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # 1. 收入趋势分析
    # ------------------------------------------------------------------

    def analyze_income_trend(self, db: Session, user: Any = None) -> Dict[str, Any]:
        """查询 VillageIncome 按年份聚合，计算年均增长率

        Args:
            db: 数据库会话。
            user: 当前用户，用于数据权限过滤。
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.supported_village import SupportedVillage, VillageIncome

        # VillageIncome 无 organization_id/created_by，需 join SupportedVillage 后按数据权限过滤
        rows = (
            filter_by_data_scope(
                db.query(
                    VillageIncome.year,
                    func.avg(VillageIncome.per_capita_income),
                    func.avg(VillageIncome.collective_income),
                    func.count(VillageIncome.id),
                ).join(
                    SupportedVillage,
                    VillageIncome.supported_village_id == SupportedVillage.id,
                ),
                SupportedVillage,
                user,
                db=db,
            )
            .group_by(VillageIncome.year)
            .order_by(VillageIncome.year)
            .all()
        )

        yearly = []
        for yr, avg_pci, avg_ci, cnt in rows:
            yearly.append(
                {
                    "year": yr,
                    "avg_per_capita_income": round(float(avg_pci or 0), 4),
                    "avg_collective_income": round(float(avg_ci or 0), 4),
                    "village_count": cnt,
                }
            )

        # 年均增长率（CAGR）
        cagr_pci = None
        if len(yearly) >= 2:
            first_val = yearly[0]["avg_per_capita_income"]
            last_val = yearly[-1]["avg_per_capita_income"]
            n_years = yearly[-1]["year"] - yearly[0]["year"]
            if first_val > 0 and n_years > 0:
                cagr_pci = round((last_val / first_val) ** (1 / n_years) - 1, 4)

        return {
            "type": "income_trend",
            "status": "completed",
            "yearly_data": yearly,
            "cagr_per_capita_income": cagr_pci,
            "total_years": len(yearly),
        }

    # ------------------------------------------------------------------
    # 2. 项目进度分析
    # ------------------------------------------------------------------

    def analyze_project_progress(self, db: Session, user: Any = None) -> Dict[str, Any]:
        """分析逾期项目、预算超支项目

        Args:
            db: 数据库会话。
            user: 当前用户，用于数据权限过滤。
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.project import Project

        today = date.today()

        # 逾期项目：end_date < today 且 status 不是 completed/cancelled（受数据权限约束，软删项目排除）
        overdue_query = filter_by_data_scope(
            db.query(Project).filter(
                Project.is_active == True,  # noqa: E712
                Project.end_date < today,
                Project.status.notin_(["completed", "cancelled"]),
            ),
            Project,
            user,
            db=db,
        )
        overdue = overdue_query.all()
        overdue_list = [
            {
                "id": p.id,
                "name": p.name,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "status": p.status,
                "overdue_days": (today - p.end_date).days if p.end_date else 0,
            }
            for p in overdue
        ]

        # 预算超支项目：actual_cost > budget 且 budget > 0（受数据权限约束，软删项目排除）
        over_budget_query = filter_by_data_scope(
            db.query(Project).filter(
                Project.is_active == True,  # noqa: E712
                Project.budget > 0,
                Project.actual_cost > Project.budget,
            ),
            Project,
            user,
            db=db,
        )
        over_budget = over_budget_query.all()
        over_budget_list = [
            {
                "id": p.id,
                "name": p.name,
                "budget": float(p.budget or 0),
                "actual_cost": float(p.actual_cost or 0),
                "overspend_ratio": round(float((p.actual_cost or 0) - (p.budget or 0)) / float(p.budget or 0), 4),
            }
            for p in over_budget
        ]

        return {
            "type": "project_progress",
            "status": "completed",
            "overdue_projects": overdue_list,
            "overdue_count": len(overdue_list),
            "over_budget_projects": over_budget_list,
            "over_budget_count": len(over_budget_list),
        }

    # ------------------------------------------------------------------
    # 3. 经费效率分析
    # ------------------------------------------------------------------

    def analyze_fund_efficiency(self, db: Session, user: Any = None) -> Dict[str, Any]:
        """按帮扶村/单位维度计算拨付率和使用率

        Args:
            db: 数据库会话。
            user: 当前用户，用于数据权限过滤。
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.fund import Fund

        # 按帮扶村聚合（受数据权限约束）
        village_rows = (
            filter_by_data_scope(
                db.query(
                    Fund.village_id,
                    func.coalesce(func.sum(Fund.amount), 0),
                    func.coalesce(func.sum(Fund.allocated_amount), 0),
                    func.coalesce(func.sum(Fund.used_amount), 0),
                ).filter(Fund.village_id.isnot(None)),
                Fund,
                user,
                db=db,
            )
            .group_by(Fund.village_id)
            .all()
        )

        village_efficiency = []
        for vid, total, allocated, used in village_rows:
            total_f = float(total or 0)
            alloc_f = float(allocated or 0)
            used_f = float(used or 0)
            village_efficiency.append(
                {
                    "village_id": vid,
                    "total_amount": round(total_f, 2),
                    "allocated_amount": round(alloc_f, 2),
                    "used_amount": round(used_f, 2),
                    "allocation_rate": (round(alloc_f / total_f, 4) if total_f > 0 else 0),
                    "usage_rate": round(used_f / alloc_f, 4) if alloc_f > 0 else 0,
                }
            )

        # 全局汇总（受数据权限约束）
        global_row = filter_by_data_scope(
            db.query(
                func.coalesce(func.sum(Fund.amount), 0),
                func.coalesce(func.sum(Fund.allocated_amount), 0),
                func.coalesce(func.sum(Fund.used_amount), 0),
            ),
            Fund,
            user,
            db=db,
        ).first()
        g_total = float(global_row[0] or 0)
        g_alloc = float(global_row[1] or 0)
        g_used = float(global_row[2] or 0)

        return {
            "type": "fund_efficiency",
            "status": "completed",
            "global": {
                "total_amount": round(g_total, 2),
                "allocated_amount": round(g_alloc, 2),
                "used_amount": round(g_used, 2),
                "allocation_rate": round(g_alloc / g_total, 4) if g_total > 0 else 0,
                "usage_rate": round(g_used / g_alloc, 4) if g_alloc > 0 else 0,
            },
            "by_village": village_efficiency,
        }

    # ------------------------------------------------------------------
    # 4. 村庄横向对比
    # ------------------------------------------------------------------

    def compare_villages(self, db: Session, user: Any = None) -> Dict[str, Any]:
        """按县维度横向对比收入、人口变化

        Args:
            db: 数据库会话。
            user: 当前用户，用于数据权限过滤。
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.supported_village import (
            SupportedVillage,
            VillageIncome,
            VillagePopulation,
        )

        # 按县聚合最新年份收入（受数据权限约束）
        latest_income_year = filter_by_data_scope(
            db.query(func.max(VillageIncome.year)).join(
                SupportedVillage,
                VillageIncome.supported_village_id == SupportedVillage.id,
            ),
            SupportedVillage,
            user,
            db=db,
        ).scalar()
        county_income = []
        if latest_income_year:
            rows = (
                filter_by_data_scope(
                    db.query(
                        SupportedVillage.county,
                        func.count(SupportedVillage.id),
                        func.avg(VillageIncome.per_capita_income),
                        func.avg(VillageIncome.collective_income),
                    ),
                    SupportedVillage,
                    user,
                    db=db,
                )
                .join(
                    VillageIncome,
                    SupportedVillage.id == VillageIncome.supported_village_id,
                )
                .filter(VillageIncome.year == latest_income_year)
                .group_by(SupportedVillage.county)
                .all()
            )
            for county, cnt, avg_pci, avg_ci in rows:
                county_income.append(
                    {
                        "county": county or "未知",
                        "village_count": cnt,
                        "avg_per_capita_income": round(float(avg_pci or 0), 4),
                        "avg_collective_income": round(float(avg_ci or 0), 4),
                    }
                )

        # 按县聚合最新年份人口（受数据权限约束）
        latest_pop_year = filter_by_data_scope(
            db.query(func.max(VillagePopulation.year)).join(
                SupportedVillage,
                VillagePopulation.supported_village_id == SupportedVillage.id,
            ),
            SupportedVillage,
            user,
            db=db,
        ).scalar()
        county_population = []
        if latest_pop_year:
            rows = (
                filter_by_data_scope(
                    db.query(
                        SupportedVillage.county,
                        func.sum(VillagePopulation.total_population),
                        func.sum(VillagePopulation.total_households),
                    ),
                    SupportedVillage,
                    user,
                    db=db,
                )
                .join(
                    VillagePopulation,
                    SupportedVillage.id == VillagePopulation.supported_village_id,
                )
                .filter(VillagePopulation.year == latest_pop_year)
                .group_by(SupportedVillage.county)
                .all()
            )
            for county, total_pop, total_hh in rows:
                county_population.append(
                    {
                        "county": county or "未知",
                        "total_population": int(total_pop or 0),
                        "total_households": int(total_hh or 0),
                    }
                )

        return {
            "type": "village_comparison",
            "status": "completed",
            "income_year": latest_income_year,
            "population_year": latest_pop_year,
            "county_income": county_income,
            "county_population": county_population,
        }

    # ------------------------------------------------------------------
    # 5. 收入趋势预测（线性回归）
    # ------------------------------------------------------------------

    def forecast_income_trend(
        self, db: Session, forecast_years: int = 2, user: Any = None
    ) -> Dict[str, Any]:
        """基于历史收入数据用线性回归预测未来年份人均收入

        Args:
            db: 数据库会话。
            forecast_years: 预测未来年数。
            user: 当前用户，用于数据权限过滤。
        """
        import numpy as np
        from sklearn.linear_model import LinearRegression

        from app.core.data_permission import filter_by_data_scope
        from app.models.supported_village import SupportedVillage, VillageIncome

        # VillageIncome 无 organization_id/created_by，需 join SupportedVillage 后按数据权限过滤
        rows = (
            filter_by_data_scope(
                db.query(
                    VillageIncome.year,
                    func.avg(VillageIncome.per_capita_income),
                    func.avg(VillageIncome.collective_income),
                ).join(
                    SupportedVillage,
                    VillageIncome.supported_village_id == SupportedVillage.id,
                ),
                SupportedVillage,
                user,
                db=db,
            )
            .group_by(VillageIncome.year)
            .order_by(VillageIncome.year)
            .all()
        )

        if len(rows) < 2:
            return {
                "type": "income_forecast",
                "status": "insufficient_data",
                "message": "历史数据不足（至少需要2年），无法进行趋势预测",
                "historical": [],
                "forecast": [],
            }

        years = np.array([r[0] for r in rows], dtype=float).reshape(-1, 1)
        pci_values = np.array([float(r[1] or 0) for r in rows])
        ci_values = np.array([float(r[2] or 0) for r in rows])

        # 拟合人均收入
        pci_model = LinearRegression().fit(years, pci_values)
        pci_r2 = float(pci_model.score(years, pci_values))

        # 拟合集体收入
        ci_model = LinearRegression().fit(years, ci_values)
        ci_r2 = float(ci_model.score(years, ci_values))

        historical = [
            {
                "year": int(r[0]),
                "avg_per_capita_income": round(float(r[1] or 0), 2),
                "avg_collective_income": round(float(r[2] or 0), 2),
                "type": "historical",
            }
            for r in rows
        ]

        last_year = int(rows[-1][0])
        future_years = np.array(range(last_year + 1, last_year + 1 + forecast_years), dtype=float).reshape(-1, 1)
        pci_forecast = pci_model.predict(future_years)
        ci_forecast = ci_model.predict(future_years)

        forecast = [
            {
                "year": last_year + i + 1,
                "avg_per_capita_income": round(max(0.0, float(pci_forecast[i])), 2),
                "avg_collective_income": round(max(0.0, float(ci_forecast[i])), 2),
                "type": "forecast",
            }
            for i in range(forecast_years)
        ]

        return {
            "type": "income_forecast",
            "status": "completed",
            "historical": historical,
            "forecast": forecast,
            "model_confidence": {
                "per_capita_income_r2": round(pci_r2, 4),
                "collective_income_r2": round(ci_r2, 4),
            },
        }

    # ------------------------------------------------------------------
    # 6. 经费完成率预测
    # ------------------------------------------------------------------

    def forecast_fund_completion(self, db: Session, user: Any = None) -> Dict[str, Any]:
        """根据当年进度预测年末经费使用率，评估资金风险

        Args:
            db: 数据库会话。
            user: 当前用户，用于数据权限过滤。
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.fund import Fund

        today = date.today()
        current_year = today.year
        year_start = date(current_year, 1, 1)
        year_end = date(current_year, 12, 31)
        days_total = (year_end - year_start).days + 1
        days_elapsed = (today - year_start).days + 1
        year_progress = days_elapsed / days_total  # 0~1

        # 当年资金汇总（使用业务日期 Fund.date 而非 created_at，允许索引命中）
        # 使用半开区间 [Jan 1, Jan 1 next year) 查询全年数据（受数据权限约束）
        query_year_start = date(current_year, 1, 1)
        query_year_end = date(current_year + 1, 1, 1)
        row = (
            filter_by_data_scope(
                db.query(
                    func.coalesce(func.sum(Fund.amount), 0),
                    func.coalesce(func.sum(Fund.allocated_amount), 0),
                    func.coalesce(func.sum(Fund.used_amount), 0),
                ).filter(Fund.date >= query_year_start, Fund.date < query_year_end),
                Fund,
                user,
                db=db,
            )
            .first()
        )
        total = float(row[0] or 0)
        allocated = float(row[1] or 0)
        used = float(row[2] or 0)

        current_usage_rate = used / allocated if allocated > 0 else 0.0
        # 线性外推：假设使用进度与时间进度正比
        projected_rate = current_usage_rate / year_progress if year_progress > 0 else 0.0
        projected_rate = min(projected_rate, 1.0)  # 上限100%

        # 风险评级
        if projected_rate >= 0.9:
            risk_level = "low"
            risk_label = "低风险"
        elif projected_rate >= 0.7:
            risk_level = "medium"
            risk_label = "中风险"
        else:
            risk_level = "high"
            risk_label = "高风险（预计年末使用率不足70%）"

        return {
            "type": "fund_completion_forecast",
            "status": "completed",
            "current_year": current_year,
            "year_progress": round(year_progress, 4),
            "current": {
                "total_amount": round(total, 2),
                "allocated_amount": round(allocated, 2),
                "used_amount": round(used, 2),
                "usage_rate": round(current_usage_rate, 4),
            },
            "projected_year_end_usage_rate": round(projected_rate, 4),
            "risk_level": risk_level,
            "risk_label": risk_label,
        }

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "summary",
            "total_records": len(data) if isinstance(data, (list, dict)) else 0,
            "status": "completed",
        }

    async def get_recommendations(
        self,
        context: Dict[str, Any],
        db: Optional[Session] = None,
        user: Any = None,
    ) -> List[Dict[str, Any]]:
        """基于数据生成智能建议"""
        suggestions: List[Dict[str, Any]] = []

        if db:
            try:
                progress = self.analyze_project_progress(db, user=user)
                if progress.get("overdue_count", 0) > 0:
                    suggestions.append(
                        {
                            "type": "warning",
                            "content": f"当前有 {progress['overdue_count']} 个逾期项目，请及时跟进",
                            "priority": "high",
                        }
                    )
                if progress.get("over_budget_count", 0) > 0:
                    suggestions.append(
                        {
                            "type": "warning",
                            "content": f"当前有 {progress['over_budget_count']} 个预算超支项目",
                            "priority": "high",
                        }
                    )
            except Exception as e:
                logger.warning("生成智能建议时出错: %s", e)

        if not suggestions:
            suggestions.append(
                {
                    "type": "suggestion",
                    "content": "建议定期进行数据备份",
                    "priority": "medium",
                }
            )

        return suggestions


# 全局实例
ai_service_manager = AIServiceManager()
