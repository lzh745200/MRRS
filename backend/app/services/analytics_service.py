"""
数据分析服务
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, cast, func, text
from sqlalchemy.orm import Session

from app.core.error_handler import app_logger
from app.models.supported_village import (
    SupportedVillage,
    VillagePopulation,
    EducationSupport,
    IndustrySupport,
    InfrastructureImprovement,
    VillageIncome,
)


class AnalyticsService:
    """数据分析服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_overview(self, db: Session) -> Dict[str, Any]:
        """获取仪表盘总览数据"""
        try:
            # 按省份统计帮扶村 - 使用 ORM 查询替代原始 SQL
            from sqlalchemy import func

            province_result = (
                db.query(
                    SupportedVillage.province,
                    func.count(SupportedVillage.id).label("count"),
                )
                .filter(SupportedVillage.is_active.is_(True))
                .group_by(SupportedVillage.province)
                .order_by(func.count(SupportedVillage.id).desc())
                .all()
            )
            province_distribution = [{"province": row.province, "count": row.count} for row in province_result]

            # 按振兴梯队统计 - 使用 ORM 查询
            tier_result = (
                db.query(
                    SupportedVillage.is_revitalization_tier,
                    func.count(SupportedVillage.id).label("count"),
                )
                .filter(SupportedVillage.is_active.is_(True))
                .group_by(SupportedVillage.is_revitalization_tier)
                .all()
            )

            tier_map = {True: "振兴梯队", False: "非振兴梯队"}
            tier_distribution = [
                {
                    "tier": tier_map.get(row.is_revitalization_tier, "未知"),
                    "count": row.count,
                }
                for row in tier_result
            ]

            total_villages = (
                db.query(func.count(SupportedVillage.id))
                .filter(SupportedVillage.is_active.is_(True))
                .scalar()
                or 0
            )

            return {
                "total_villages": total_villages,
                "province_distribution": province_distribution,
                "tier_distribution": tier_distribution,
            }
        except Exception as e:
            app_logger.error(f"获取仪表盘数据失败: {e}")
            return {
                "total_villages": 0,
                "province_distribution": [],
                "tier_distribution": [],
            }

    def get_village_analysis(self, db: Session) -> Dict[str, Any]:
        """获取帮扶村分析数据"""
        try:
            # 投资统计（软删村排除）
            investment_result = db.execute(text("""
                SELECT
                    SUM(transition_fund_military_total + transition_fund_local_total) as total_investment,
                    AVG(transition_fund_military_total + transition_fund_local_total) as avg_investment,
                    MAX(transition_fund_military_total + transition_fund_local_total) as max_investment
                FROM supported_villages
                WHERE is_active = 1
            """))
            investment_row = investment_result.fetchone()

            # 人口统计
            population_result = db.execute(text("""
                SELECT
                    SUM(vp.total_population) as total_population,
                    SUM(vp.resident_population) as total_resident,
                    AVG(vp.resident_population * 100.0 / vp.total_population) as avg_resident_rate
                FROM village_populations vp
                JOIN supported_villages sv ON sv.id = vp.supported_village_id AND sv.is_active = 1
                WHERE vp.year = (
                    SELECT MAX(year) FROM village_populations
                )
            """))
            population_row = population_result.fetchone()

            # 收入统计
            income_result = db.execute(text("""
                SELECT
                    AVG(vi.per_capita_income) as avg_per_capita_income,
                    AVG(vi.county_per_capita_income) as avg_county_income
                FROM village_incomes vi
                JOIN supported_villages sv ON sv.id = vi.supported_village_id AND sv.is_active = 1
                WHERE vi.year = (
                    SELECT MAX(year) FROM village_incomes
                )
            """))
            income_row = income_result.fetchone()

            # 基础设施投资分类
            infra_result = db.execute(text("""
                SELECT
                    investment_category,
                    SUM(investment) as total_amount
                FROM (
                    SELECT '道路' as investment_category, SUM(ii.road_km * 1000000) as investment
                    FROM infrastructure_improvements ii
                    JOIN supported_villages sv ON sv.id = ii.supported_village_id AND sv.is_active = 1
                    WHERE ii.year = (SELECT MAX(year) FROM infrastructure_improvements)
                    UNION ALL
                    SELECT '住房改造' as investment_category, SUM(housing_renovation) as investment
                    FROM infrastructure_improvements ii2
                    JOIN supported_villages sv2 ON sv2.id = ii2.supported_village_id AND sv2.is_active = 1
                    WHERE ii2.year = (SELECT MAX(year) FROM infrastructure_improvements)
                    UNION ALL
                    SELECT '文化设施' as investment_category, SUM(cultural_plaza + library_cafe) as investment
                    FROM infrastructure_improvements ii3
                    JOIN supported_villages sv3 ON sv3.id = ii3.supported_village_id AND sv3.is_active = 1
                    WHERE ii3.year = (SELECT MAX(year) FROM infrastructure_improvements)
                ) infra
                GROUP BY investment_category
            """))
            infra_data = [{"category": row[0], "amount": float(row[1]) if row[1] else 0} for row in infra_result]

            return {
                "investment": {
                    "total": (float(investment_row[0]) if investment_row and investment_row[0] else 0),
                    "average": (float(investment_row[1]) if investment_row and investment_row[1] else 0),
                    "max": (float(investment_row[2]) if investment_row and investment_row[2] else 0),
                },
                "population": {
                    "total": (int(population_row[0]) if population_row and population_row[0] else 0),
                    "resident": (int(population_row[1]) if population_row and population_row[1] else 0),
                    "avg_resident_rate": (float(population_row[2]) if population_row and population_row[2] else 0),
                },
                "income": {
                    "avg_per_capita": (float(income_row[0]) if income_row and income_row[0] else 0),
                    "avg_county": (float(income_row[1]) if income_row and income_row[1] else 0),
                },
                "infrastructure": infra_data,
            }
        except Exception as e:
            app_logger.error(f"获取帮扶村分析数据失败: {e}")
            return {}

    def get_funding_trends(self, db: Session, years: int = 5) -> Dict[str, Any]:
        """获取资金趋势分析"""
        try:
            current_year = datetime.now().year
            start_year = current_year - years
            end_year = current_year

            result = db.execute(
                text("""
                SELECT
                    vp.year,
                    SUM(vp.transition_fund_military_total + vp.transition_fund_local_total) as total_funding,
                    SUM(vp.transition_fund_military_total) as military_funding,
                    SUM(vp.transition_fund_local_total) as local_funding,
                    COUNT(vp.id) as village_count
                FROM supported_villages vp
                WHERE vp.is_active = 1
                  AND vp.id IN (
                    SELECT DISTINCT sv.id
                    FROM supported_villages sv
                    JOIN village_populations vp_pop ON sv.id = vp_pop.supported_village_id
                    WHERE vp_pop.year BETWEEN :start_year AND :end_year
                      AND sv.is_active = 1
                )
                GROUP BY vp.year
                ORDER BY vp.year
            """),
                {"start_year": start_year, "end_year": end_year},
            )

            trends = []
            for row in result:
                trends.append(
                    {
                        "year": row[0],
                        "total_funding": float(row[1]) if row[1] else 0,
                        "military_funding": float(row[2]) if row[2] else 0,
                        "local_funding": float(row[3]) if row[3] else 0,
                        "village_count": row[4],
                    }
                )

            return {"trends": trends, "start_year": start_year, "end_year": end_year}
        except Exception as e:
            app_logger.error(f"获取资金趋势失败: {e}")
            return {"trends": [], "start_year": 0, "end_year": 0}

    def get_performance_metrics(self, db: Session) -> Dict[str, Any]:
        """获取绩效指标"""
        try:
            # 政策统计
            policy_result = db.execute(text("""
                SELECT
                    COUNT(*) as total_policies,
                    SUM(CASE WHEN status = '已发布' THEN 1 ELSE 0 END) as published_policies
                FROM policies
            """))
            policy_row = policy_result.fetchone()

            # 示范村统计
            village_result = db.execute(text("""
                SELECT
                    COUNT(*) as total_villages,
                    SUM(CASE
                        WHEN is_hundred_village_demo = true OR is_provincial_demo = true
                        THEN 1 ELSE 0 END
                    ) as demo_villages
                FROM supported_villages
                WHERE is_active = 1
            """))
            village_row = village_result.fetchone()

            # 各类帮扶投资
            category_result = db.execute(text("""
                SELECT
                    '产业帮扶' as category,
                    SUM(investment) as amount
                FROM industry_support
                WHERE year = (SELECT MAX(year) FROM industry_support)
                  AND supported_village_id IN (SELECT id FROM supported_villages WHERE is_active = 1)
                UNION ALL
                SELECT
                    '基础设施' as category,
                    SUM(investment) as amount
                FROM infrastructure_improvements
                WHERE year = (SELECT MAX(year) FROM infrastructure_improvements)
                  AND supported_village_id IN (SELECT id FROM supported_villages WHERE is_active = 1)
                UNION ALL
                SELECT
                    '医疗帮扶' as category,
                    SUM(investment) as amount
                FROM medical_support
                WHERE year = (SELECT MAX(year) FROM medical_support)
                  AND supported_village_id IN (SELECT id FROM supported_villages WHERE is_active = 1)
                UNION ALL
                SELECT
                    '教育帮扶' as category,
                    SUM(investment) as amount
                FROM education_support
                WHERE year = (SELECT MAX(year) FROM education_support)
                  AND supported_village_id IN (SELECT id FROM supported_villages WHERE is_active = 1)
            """))
            categories = [{"category": row[0], "amount": float(row[1]) if row[1] else 0} for row in category_result]

            return {
                "policies": {
                    "total": policy_row[0] if policy_row else 0,
                    "published": policy_row[1] if policy_row else 0,
                },
                "villages": {
                    "total": village_row[0] if village_row else 0,
                    "demo": village_row[1] if village_row else 0,
                },
                "investment_categories": categories,
            }
        except Exception as e:
            app_logger.error(f"获取绩效指标失败: {e}")
            return {}

    def get_comparison_analysis(self, db: Session, compare_type: str, target_value: Optional[str]) -> Dict[str, Any]:
        """获取对比分析数据"""
        try:
            if compare_type == "province":
                result = db.execute(text("""
                    SELECT
                        province,
                        COUNT(*) as village_count,
                        SUM(vp.transition_fund_military_total + vp.transition_fund_local_total) as total_investment,
                        AVG(vi.per_capita_income) as avg_income
                    FROM supported_villages vp
                    JOIN village_incomes vi ON vp.id = vi.supported_village_id
                    JOIN village_populations vp_pop ON vp.id = vp_pop.supported_village_id
                    WHERE vp.is_active = 1
                      AND vi.year = (SELECT MAX(year) FROM village_incomes)
                      AND vp_pop.year = (SELECT MAX(year) FROM village_populations)
                    GROUP BY province
                    ORDER BY total_investment DESC
                """))
            elif compare_type == "tier":
                result = db.execute(text("""
                    SELECT
                        CASE WHEN vp.is_revitalization_tier THEN '是' ELSE '否' END as tier,
                        COUNT(*) as village_count,
                        SUM(vp.transition_fund_military_total + vp.transition_fund_local_total) as total_investment,
                        AVG(vi.per_capita_income) as avg_income
                    FROM supported_villages vp
                    JOIN village_incomes vi ON vp.id = vi.supported_village_id
                    WHERE vp.is_active = 1
                      AND vi.year = (SELECT MAX(year) FROM village_incomes)
                    GROUP BY vp.is_revitalization_tier
                    ORDER BY avg_income DESC
                """))
            else:
                return {"comparison": [], "compare_type": compare_type}

            comparison = [
                {
                    "label": row[0],
                    "village_count": row[1],
                    "total_investment": float(row[2]) if row[2] else 0,
                    "avg_income": float(row[3]) if row[3] else 0,
                }
                for row in result
            ]

            return {"comparison": comparison, "compare_type": compare_type}
        except Exception as e:
            app_logger.error(f"获取对比分析失败: {e}")
            return {"comparison": [], "compare_type": compare_type}

    def generate_report_data(
        self,
        db: Session,
        report_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成报表数据"""
        try:
            if report_type == "comprehensive":
                dashboard = self.get_dashboard_overview(db)
                village_analysis = self.get_village_analysis(db)
                performance = self.get_performance_metrics(db)
                return {
                    "report_type": "comprehensive",
                    "dashboard": dashboard,
                    "village_analysis": village_analysis,
                    "performance": performance,
                    "generated_at": datetime.now().isoformat(),
                }
            elif report_type == "village_funding":
                funding = self.get_funding_trends(db)
                return {
                    "report_type": "village_funding",
                    "funding_trends": funding,
                    "generated_at": datetime.now().isoformat(),
                }
            elif report_type == "policy_execution":
                performance = self.get_performance_metrics(db)
                return {
                    "report_type": "policy_execution",
                    "performance": performance,
                    "generated_at": datetime.now().isoformat(),
                }
            else:
                return {
                    "report_type": report_type,
                    "data": {},
                    "generated_at": datetime.now().isoformat(),
                }
        except Exception as e:
            app_logger.error(f"生成报表数据失败: {e}")
            return {}

    @staticmethod
    def _apply_year_filter(query, model, year, village_subq, db):
        """对查询应用年份过滤，未指定时取最新年份"""
        if year:
            return query.filter(model.year == year)
        latest = (
            db.query(func.max(model.year))
            .filter(model.supported_village_id.in_(db.query(village_subq.c.id)))
            .scalar_subquery()
        )
        return query.filter(model.year == latest)

    def _build_village_query(self, filters, db):
        """构建帮扶村查询并返回子查询和总数（软删村统一排除）"""
        village_query = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
        if filters:
            if filters.get("department"):
                village_query = village_query.filter(SupportedVillage.department == filters["department"])
            if filters.get("is_three_regions"):
                village_query = village_query.filter(SupportedVillage.is_three_regions == True)  # noqa: E712
            if filters.get("is_key_county"):
                village_query = village_query.filter(SupportedVillage.is_key_county == True)  # noqa: E712
        village_subq = village_query.with_entities(SupportedVillage.id).subquery()
        total_villages = db.query(func.count()).select_from(village_subq).scalar() or 0
        return village_subq, total_villages

    def _calc_village_features(self, db, village_subq, result):
        """统计帮扶村特征（三区三州、重点县等）"""
        feature_row = (
            db.query(
                func.coalesce(func.sum(cast(SupportedVillage.is_three_regions, Integer)), 0),
                func.coalesce(func.sum(cast(SupportedVillage.is_key_county, Integer)), 0),
                func.coalesce(func.sum(cast(SupportedVillage.is_provincial_demo, Integer)), 0),
                func.coalesce(func.sum(cast(SupportedVillage.is_cross_province, Integer)), 0),
            )
            .filter(SupportedVillage.id.in_(db.query(village_subq.c.id)))
            .first()
        )
        if feature_row:
            result["villages"]["threeRegionsCount"] = int(feature_row[0] or 0)
            result["villages"]["keyCountyCount"] = int(feature_row[1] or 0)
            result["villages"]["provincialDemoCount"] = int(feature_row[2] or 0)
            result["villages"]["crossProvinceCount"] = int(feature_row[3] or 0)

    def _calc_population(self, db, village_subq, year, result):
        """统计人口数据"""
        pop_query = db.query(
            func.sum(VillagePopulation.total_population).label("total_pop"),
            func.sum(VillagePopulation.total_households).label("total_households"),
            func.sum(
                VillagePopulation.unstable_poverty_households
                + VillagePopulation.marginal_poverty_households
                + VillagePopulation.sudden_difficulty_households
            ).label("poverty_households"),
        ).filter(VillagePopulation.supported_village_id.in_(db.query(village_subq.c.id)))
        pop_query = self._apply_year_filter(pop_query, VillagePopulation, year, village_subq, db)
        pop_result = pop_query.first()
        if pop_result:
            result["population"]["totalPopulation"] = int(pop_result.total_pop or 0)
            result["population"]["totalHouseholds"] = int(pop_result.total_households or 0)
            result["population"]["povertyHouseholds"] = int(pop_result.poverty_households or 0)

    def _calc_income(self, db, village_subq, year, result):
        """统计收入数据"""
        income_query = db.query(
            func.avg(VillageIncome.per_capita_income).label("avg_income"),
            func.sum(VillageIncome.collective_income).label("total_collective"),
        ).filter(VillageIncome.supported_village_id.in_(db.query(village_subq.c.id)))
        income_query = self._apply_year_filter(income_query, VillageIncome, year, village_subq, db)
        income_result = income_query.first()
        if income_result:
            result["income"]["avgPerCapitaIncome"] = float(income_result.avg_income or 0)
            result["income"]["totalCollectiveIncome"] = float(income_result.total_collective or 0)

    def _calc_industry(self, db, village_subq, year, result):
        """统计产业投资"""
        industry_query = db.query(func.sum(IndustrySupport.investment).label("total_investment")).filter(
            IndustrySupport.supported_village_id.in_(db.query(village_subq.c.id))
        )
        industry_query = self._apply_year_filter(industry_query, IndustrySupport, year, village_subq, db)
        result["investment"]["industry"] = float(industry_query.scalar() or 0)

    def _calc_infrastructure(self, db, village_subq, year, result):
        """统计基础设施投资"""
        infra_query = db.query(
            func.sum(InfrastructureImprovement.investment).label("total_investment"),
            func.sum(InfrastructureImprovement.road_km).label("total_road_km"),
        ).filter(InfrastructureImprovement.supported_village_id.in_(db.query(village_subq.c.id)))
        infra_query = self._apply_year_filter(infra_query, InfrastructureImprovement, year, village_subq, db)
        infra_result = infra_query.first()
        if infra_result:
            result["investment"]["infrastructure"] = float(infra_result.total_investment or 0)
            result["investment"]["infrastructureRoadKm"] = float(infra_result.total_road_km or 0)

    def _calc_education(self, db, village_subq, year, result):
        """统计教育投资"""
        edu_query = db.query(
            func.sum(EducationSupport.investment).label("total_investment"),
            func.sum(EducationSupport.aided_students).label("total_aided_students"),
        ).filter(EducationSupport.supported_village_id.in_(db.query(village_subq.c.id)))
        edu_query = self._apply_year_filter(edu_query, EducationSupport, year, village_subq, db)
        edu_result = edu_query.first()
        if edu_result:
            result["investment"]["education"] = float(edu_result.total_investment or 0)
            result["investment"]["educationAidedStudents"] = int(edu_result.total_aided_students or 0)

    @staticmethod
    def _empty_summary(year):
        """返回空汇总数据结构"""
        return {
            "year": year or datetime.now().year,
            "villages": {
                "totalVillages": 0, "threeRegionsCount": 0, "keyCountyCount": 0,
                "provincialDemoCount": 0, "crossProvinceCount": 0,
            },
            "population": {"totalPopulation": 0, "totalHouseholds": 0, "povertyHouseholds": 0},
            "income": {"avgPerCapitaIncome": 0, "totalCollectiveIncome": 0},
            "investment": {
                "industry": 0, "infrastructure": 0,
                "infrastructureRoadKm": 0, "education": 0,
                "educationAidedStudents": 0,
            },
        }

    def get_summary_statistics(self, filters: Optional[Dict] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """汇总统计（同步，供 reports/analytics/summary 使用）"""
        try:
            db = self.db
            current_year = year or datetime.now().year
            village_subq, total_villages = self._build_village_query(filters, db)

            result = self._empty_summary(current_year)
            result["villages"]["totalVillages"] = total_villages
            if total_villages == 0:
                return result

            self._calc_village_features(db, village_subq, result)
            self._calc_population(db, village_subq, year, result)
            self._calc_income(db, village_subq, year, result)
            self._calc_industry(db, village_subq, year, result)
            self._calc_infrastructure(db, village_subq, year, result)
            self._calc_education(db, village_subq, year, result)
            return result
        except Exception as e:
            app_logger.error(f"获取汇总统计失败: {e}", exc_info=True)
            return self._empty_summary(year)

    def drill_down(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """数据钻取（同步，供 reports 路由使用）"""
        try:
            db = self.db
            dimension = query_params.get("dimension", "province")
            value = query_params.get("value")

            if dimension == "province":
                villages = (
                    db.query(SupportedVillage)
                    .filter(
                        SupportedVillage.province == value,
                        SupportedVillage.is_active.is_(True),
                    )
                    .all()
                )
            else:
                villages = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True)).all()

            items = [{"id": v.id, "name": v.village_name, "province": v.province} for v in villages]
            return {
                "dimension": dimension,
                "value": value,
                "items": items,
                "total": len(items),
            }
        except Exception as e:
            app_logger.error(f"数据钻取失败: {e}")
            return {"items": [], "total": 0}

    def compare_villages(
        self,
        village_ids: List[int],
        year: Optional[int] = None,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """帮扶村对比（同步，供 reports 路由使用）"""
        try:
            db = self.db
            villages = (
                db.query(SupportedVillage)
                .filter(
                    SupportedVillage.id.in_(village_ids),
                    SupportedVillage.is_active.is_(True),
                )
                .all()
            )
            items = [{"id": v.id, "name": v.village_name, "province": v.province} for v in villages]
            return {"villages": items, "year": year, "metrics": metrics or []}
        except Exception as e:
            app_logger.error(f"帮扶村对比失败: {e}")
            return {"villages": [], "year": year}

    def compare_years(self, village_id: int, years: List[int], metrics: Optional[List[str]] = None) -> Dict[str, Any]:
        """年度对比（同步，供 reports 路由使用）"""
        try:
            return {
                "village_id": village_id,
                "years": years,
                "metrics": metrics or [],
                "data": [],
            }
        except Exception as e:
            app_logger.error(f"年度对比失败: {e}")
            return {}

    def get_filter_options(self) -> Dict[str, Any]:
        """获取筛选选项（同步，供 reports 路由使用）"""
        try:
            db = self.db
            provinces = (
                db.query(SupportedVillage.province)
                .filter(SupportedVillage.is_active.is_(True))
                .distinct()
                .all()
            )
            province_list = [p[0] for p in provinces if p[0]]

            is_tier_list = (
                db.query(SupportedVillage.is_revitalization_tier)
                .filter(SupportedVillage.is_active.is_(True))
                .distinct()
                .all()
            )
            tier_list = ["是" if t[0] else "否" for t in is_tier_list]

            departments = (
                db.query(SupportedVillage.department)
                .filter(SupportedVillage.is_active.is_(True))
                .distinct()
                .all()
            )
            dept_list = [d[0] for d in departments if d[0]]

            return {
                "provinces": province_list,
                "tiers": tier_list,
                "departments": dept_list,
            }
        except Exception as e:
            app_logger.error(f"获取筛选选项失败: {e}")
            return {"provinces": [], "tiers": [], "departments": []}

    def filter_villages(
        self,
        filters: Dict[str, Any],
        page: int = 1,
        page_size: int = 20,
        user: Any = None,
    ) -> tuple:
        """多维度筛选帮扶村（同步，供 reports 路由使用）。

        Args:
            filters: 筛选条件字典。
            page: 页码（从 1 开始）。
            page_size: 每页记录数。
            user: 当前用户，用于数据权限过滤。

        Returns:
            元组 ``(items, total)``：items 为 SupportedVillage ORM 对象列表
            （由路由层负责字段序列化），total 为符合条件的总记录数。
        """
        try:
            from app.core.data_permission import filter_by_data_scope

            db = self.db
            query = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
            # 数据权限过滤（参照 villages.py:50 范式）
            query = filter_by_data_scope(query, SupportedVillage, user, db=db)

            if filters.get("province"):
                query = query.filter(SupportedVillage.province == filters["province"])
            if "tier" in filters and filters["tier"] is not None:
                query = query.filter(SupportedVillage.is_revitalization_tier == (filters["tier"] == "是"))
            if filters.get("region"):
                query = query.filter(SupportedVillage.region_scope == filters["region"])
            if filters.get("department"):
                query = query.filter(SupportedVillage.department == filters["department"])
            if "is_three_regions" in filters and filters["is_three_regions"] is not None:
                query = query.filter(SupportedVillage.is_three_regions == filters["is_three_regions"])
            if "is_key_county" in filters and filters["is_key_county"] is not None:
                query = query.filter(SupportedVillage.is_key_county == filters["is_key_county"])

            total = query.count()
            items = query.offset((page - 1) * page_size).limit(page_size).all()

            return items, total
        except Exception as e:
            app_logger.error(f"筛选帮扶村失败: {e}")
            return [], 0

    def export_data(self, db: Session, export_type: str, data: Dict[str, Any]) -> bytes:
        """导出数据，返回文件字节流"""
        if export_type == "excel":
            from app.services.export_service import ExcelExportService

            export_service = ExcelExportService()

            summary_data = []
            basic_stats = {
                "帮扶村总数": data.get("dashboard", {}).get("total_villages", 0),
                "组织机构数": data.get("dashboard", {}).get("total_organizations", 0),
                "政策文件数": data.get("performance", {}).get("policies", {}).get("total", 0),
            }
            for key, value in basic_stats.items():
                summary_data.append({"指标": key, "数值": str(value)})

            return export_service.export_list(summary_data, ["指标", "数值"], "数据分析报告", "分析数据")
        return b""
