"""
智能推荐服务
提供项目推荐、资金分配建议、政策匹配等功能
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import and_
from sqlalchemy.orm import Session
from sqlalchemy.sql import func as sa_func

logger = logging.getLogger(__name__)


class RecommendationService:
    """智能推荐服务"""

    @staticmethod
    def recommend_projects(
        db: Session, village_id: int, limit: int = 5, user: Any = None
    ) -> List[Dict[str, Any]]:
        """
        为村庄推荐项目

        Args:
            db: 数据库会话
            village_id: 村庄ID（supported_villages.id）
            limit: 推荐数量
            user: 当前用户，用于数据权限过滤

        Returns:
            推荐项目列表
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.project import Project
        from app.models.supported_village import SupportedVillage

        # 获取村庄信息（受数据权限约束）
        village_query = filter_by_data_scope(
            db.query(SupportedVillage).filter(SupportedVillage.id == village_id),
            SupportedVillage, user, db=db,
        )
        village = village_query.first()
        if not village:
            return []

        # 查询相似村庄的成功项目（受数据权限约束）
        similar_villages_query = filter_by_data_scope(
            db.query(SupportedVillage).filter(
                and_(
                    SupportedVillage.id != village_id,
                    SupportedVillage.province == village.province,
                    SupportedVillage.city == village.city,
                )
            ),
            SupportedVillage,
            user,
            db=db,
        )
        similar_villages = similar_villages_query.limit(10).all()

        if not similar_villages:
            return []

        similar_village_ids = [v.id for v in similar_villages]

        # 查询这些村庄的成功项目（受数据权限约束）
        successful_projects_query = filter_by_data_scope(
            db.query(Project).filter(
                and_(
                    Project.village_id.in_(similar_village_ids),
                    Project.status == "completed",
                    Project.progress >= 90,
                )
            ),
            Project,
            user,
            db=db,
        )
        successful_projects = successful_projects_query.all()

        # 统计项目类型和成功率
        project_stats = {}
        for project in successful_projects:
            project_type = project.project_type or "other"
            if project_type not in project_stats:
                project_stats[project_type] = {
                    "count": 0,
                    "total_budget": 0,
                    "avg_progress": 0,
                    "examples": [],
                }

            project_stats[project_type]["count"] += 1
            project_stats[project_type]["total_budget"] += project.budget or 0
            project_stats[project_type]["avg_progress"] += project.progress or 0

            if len(project_stats[project_type]["examples"]) < 3:
                project_stats[project_type]["examples"].append(
                    {
                        "name": project.name,
                        "village_id": project.village_id,
                        "budget": project.budget,
                    }
                )

        # 计算推荐分数
        recommendations = []
        for project_type, stats in project_stats.items():
            avg_progress = stats["avg_progress"] / stats["count"] if stats["count"] > 0 else 0
            avg_budget = stats["total_budget"] / stats["count"] if stats["count"] > 0 else 0

            score = stats["count"] * 0.5 + (avg_progress / 100) * 0.5

            recommendations.append(
                {
                    "project_type": project_type,
                    "score": round(score, 2),
                    "success_count": stats["count"],
                    "avg_budget": round(avg_budget, 2),
                    "avg_progress": round(avg_progress, 2),
                    "examples": stats["examples"],
                    "reason": f'在相似村庄中有{stats["count"]}个成功案例',
                }
            )

        # 按分数排序
        recommendations.sort(key=lambda x: x["score"], reverse=True)

        return recommendations[:limit]

    @staticmethod
    def recommend_fund_allocation(
        db: Session, total_budget: float, village_ids: List[int], user: Any = None
    ) -> Dict[str, Any]:
        """
        推荐资金分配方案

        Args:
            db: 数据库会话
            total_budget: 总预算
            village_ids: 村庄ID列表（supported_villages.id）
            user: 当前用户，用于数据权限过滤

        Returns:
            资金分配建议
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.annual_income import AnnualIncome
        from app.models.annual_population import AnnualPopulation
        from app.models.supported_village import SupportedVillage

        if not village_ids:
            return {"allocations": [], "error": "村庄列表为空"}

        # 获取村庄信息（受数据权限约束）
        villages = filter_by_data_scope(
            db.query(SupportedVillage).filter(SupportedVillage.id.in_(village_ids)),
            SupportedVillage, user, db=db,
        ).all()

        if not villages:
            return {"allocations": [], "error": "未找到村庄"}

        # 批量查询所有村庄的最新人口数据（避免 N+1）
        pop_subq = (
            db.query(
                AnnualPopulation.supported_village_id,
                sa_func.max(AnnualPopulation.year).label("max_year"),
            )
            .filter(AnnualPopulation.supported_village_id.in_(village_ids))
            .group_by(AnnualPopulation.supported_village_id)
            .subquery()
        )
        pop_rows = (
            db.query(AnnualPopulation)
            .join(
                pop_subq,
                and_(
                    AnnualPopulation.supported_village_id == pop_subq.c.supported_village_id,
                    AnnualPopulation.year == pop_subq.c.max_year,
                ),
            )
            .all()
        )
        pop_by_village = {p.supported_village_id: p for p in pop_rows}

        # 批量查询所有村庄的最新收入数据（避免 N+1）
        inc_subq = (
            db.query(
                AnnualIncome.supported_village_id,
                sa_func.max(AnnualIncome.year).label("max_year"),
            )
            .filter(AnnualIncome.supported_village_id.in_(village_ids))
            .group_by(AnnualIncome.supported_village_id)
            .subquery()
        )
        inc_rows = (
            db.query(AnnualIncome)
            .join(
                inc_subq,
                and_(
                    AnnualIncome.supported_village_id == inc_subq.c.supported_village_id,
                    AnnualIncome.year == inc_subq.c.max_year,
                ),
            )
            .all()
        )
        inc_by_village = {i.supported_village_id: i for i in inc_rows}

        def _income_value(income: Any) -> float:
            """取年度收入记录中对应年份的人均纯收入（按年份列动态取值，兼容任意年份）"""
            if income is None:
                return 0.0
            value = getattr(income, f"per_capita_income_{income.year}", None)
            try:
                return float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                return 0.0

        # 计算每个村庄的需求指数
        allocations = []
        total_score = 0

        for village in villages:
            population = pop_by_village.get(village.id)
            income = inc_by_village.get(village.id)

            # 计算需求分数(人口多、收入低的村庄分数高)
            population_score = (population.population or 0) / 1000 if population else 0
            income_value = _income_value(income)
            income_score = 10000 / (income_value or 10000) if income else 1

            score = population_score * 0.4 + income_score * 0.6
            total_score += score

            allocations.append(
                {
                    "village_id": village.id,
                    "village_name": village.village_name,
                    "score": score,
                    "population": population.population if population else 0,
                    "per_capita_income": income_value,
                }
            )

        # 按比例分配资金
        if total_score > 0:
            for allocation in allocations:
                allocation["recommended_amount"] = round((allocation["score"] / total_score) * total_budget, 2)
                allocation["percentage"] = round((allocation["score"] / total_score) * 100, 2)

        # 按推荐金额排序
        allocations.sort(key=lambda x: x["recommended_amount"], reverse=True)

        return {
            "total_budget": total_budget,
            "allocations": allocations,
            "method": "weighted_by_need",
        }

    @staticmethod
    def match_policies(
        db: Session, village_id: int, limit: int = 5, user: Any = None
    ) -> List[Dict[str, Any]]:
        """
        为村庄匹配相关政策

        Args:
            db: 数据库会话
            village_id: 村庄ID（supported_villages.id）
            limit: 匹配数量
            user: 当前用户，用于数据权限过滤

        Returns:
            匹配的政策列表
        """
        from app.core.data_permission import filter_by_data_scope
        from app.models.policy import Policy
        from app.models.supported_village import SupportedVillage

        # 获取村庄信息（受数据权限约束）
        village = filter_by_data_scope(
            db.query(SupportedVillage).filter(SupportedVillage.id == village_id),
            SupportedVillage, user, db=db,
        ).first()
        if not village:
            return []

        # 查询所有有效政策
        policies = db.query(Policy).filter(Policy.status == "active").all()

        if not policies:
            return []

        # 计算匹配分数
        matches = []
        for policy in policies:
            score = 0
            reasons = []

            # 地域匹配
            if policy.scope == "national":
                score += 1
                reasons.append("全国性政策")
            elif policy.province and policy.province == village.province:
                score += 2
                reasons.append(f"适用于{village.province}")

                if policy.city and policy.city == village.city:
                    score += 1
                    reasons.append(f"适用于{village.city}")

            # 关键词匹配(简化实现)
            village_keywords = [village.village_name, village.province, village.city]
            policy_text = f"{policy.title} {policy.content or ''}"

            for keyword in village_keywords:
                if keyword and keyword in policy_text:
                    score += 0.5

            if score > 0:
                matches.append(
                    {
                        "policy_id": policy.id,
                        "title": policy.title,
                        "category": policy.category,
                        "score": round(score, 2),
                        "reasons": reasons,
                        "effective_date": (policy.effective_date.isoformat() if policy.effective_date else None),
                    }
                )

        # 按分数排序
        matches.sort(key=lambda x: x["score"], reverse=True)

        return matches[:limit]
