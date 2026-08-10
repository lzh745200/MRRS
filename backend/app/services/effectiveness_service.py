"""
效果评估服务

提供帮扶效果评估功能
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import timezone, datetime


@dataclass
class EffectivenessMetrics:
    """效果评估指标"""

    income_growth_rate: float = 0.0
    project_completion_rate: float = 0.0
    fund_usage_rate: float = 0.0
    satisfaction_score: float = 0.0
    overall_score: float = 0.0


@dataclass
class EffectivenessReport:
    """效果评估报告"""

    entity_id: int
    entity_type: str  # village, project, fund
    period_start: datetime
    period_end: datetime
    metrics: EffectivenessMetrics
    recommendations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EffectivenessService:
    """
    效果评估服务

    评估帮扶工作的效果
    """

    def __init__(self):
        self.evaluation_cache = {}

    # ==================== API 静态方法（/effectiveness 端点依赖） ====================

    @staticmethod
    def _eval_to_dict(ev) -> Dict[str, Any]:
        """评估记录 → API 响应字典"""
        return {
            "village_id": ev.village_id,
            "year": ev.year,
            "economic_score": ev.economic_score,
            "social_score": ev.social_score,
            "ecological_score": ev.ecological_score,
            "total_score": ev.total_score,
            "rank": ev.rank,
            "grade": ev.grade,
            "indicators": ev.indicators,
            "evaluated_at": ev.evaluated_at.isoformat() if ev.evaluated_at else None,
        }

    @staticmethod
    def _find_evaluation(db, village_id: int, year: int):
        from app.models.effectiveness import EffectivenessEvaluation

        return (
            db.query(EffectivenessEvaluation)
            .filter(
                EffectivenessEvaluation.village_id == village_id,
                EffectivenessEvaluation.year == year,
            )
            .order_by(EffectivenessEvaluation.evaluated_at.desc())
            .first()
        )

    @staticmethod
    def _compute_indicators(db, village: Any, year: int) -> Dict[str, Any]:
        """基于村庄年度数据计算三唯评估指标（无数据时给出中性基线）。"""
        from app.models.annual_income import AnnualIncome
        from app.models.annual_infrastructure import AnnualInfrastructure
        from app.models.annual_industry import AnnualIndustry
        from sqlalchemy import func

        # 年度收入（人均收入与增长率）
        incomes = (
            db.query(AnnualIncome)
            .filter(AnnualIncome.village_id == village.id, AnnualIncome.year == year)
            .all()
        )
        per_capita = 0.0
        income_growth = 0.0
        if incomes and getattr(incomes[0], "per_capita_income", None) is not None:
            per_capita = float(incomes[0].per_capita_income or 0)
        prev = (
            db.query(AnnualIncome)
            .filter(AnnualIncome.village_id == village.id, AnnualIncome.year == year - 1)
            .first()
        )
        if prev and getattr(prev, "per_capita_income", None) and per_capita > 0:
            prev_val = float(prev.per_capita_income or 0)
            if prev_val > 0:
                income_growth = round((per_capita - prev_val) / prev_val * 100, 1)

        # 基础设施覆盖
        infra_count = (
            db.query(func.count(AnnualInfrastructure.id))
            .filter(AnnualInfrastructure.village_id == village.id, AnnualInfrastructure.year == year)
            .scalar()
            or 0
        )
        industry_count = (
            db.query(func.count(AnnualIndustry.id))
            .filter(AnnualIndustry.village_id == village.id, AnnualIndustry.year == year)
            .scalar()
            or 0
        )

        # 经济分：人均收入 + 增长率
        economic = round(min(60, per_capita / 2000 * 60) + min(40, max(0, income_growth) * 4), 1)
        # 社会分：基础设施 + 产业覆盖
        social = round(min(70, infra_count * 15) + min(30, industry_count * 6), 1)
        # 生态分：中性基线 + 数据完整度加成（无年度数据时给 60 基线）
        ecological = round(60.0 + min(40, infra_count * 5), 1)

        indicators = {
            "per_capita_income": round(per_capita, 2),
            "income_growth_rate": income_growth,
            "infrastructure_count": infra_count,
            "industry_count": industry_count,
            "data_complete": bool(incomes),
        }
        return {
            "economic": min(100, economic),
            "social": min(100, social),
            "ecological": min(100, ecological),
            "indicators": indicators,
        }

    @staticmethod
    def evaluate_village(db, village_id: int, year: int, user_id: int) -> Dict[str, Any]:
        """评估村庄年度成效（/evaluate 端点）。

        基于村庄年度收入/基础设施/产业数据计算三唯分数并写入评估表；
        重复评估时更新已有记录（幂等）。
        """
        from app.models.village import Village

        village = db.query(Village).filter(Village.id == village_id).first()
        if not village:
            return {"error": f"村庄 {village_id} 不存在"}

        from app.models.effectiveness import EffectivenessEvaluation

        ev = EffectivenessService._find_evaluation(db, village_id, year)
        computed = EffectivenessService._compute_indicators(db, village, year)
        total = round(
            computed["economic"] * 0.4 + computed["social"] * 0.35 + computed["ecological"] * 0.25,
            1,
        )
        grade = "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "D"

        if ev:
            # 更新已有评估
            ev.economic_score = computed["economic"]
            ev.social_score = computed["social"]
            ev.ecological_score = computed["ecological"]
            ev.total_score = total
            ev.grade = grade
            ev.indicators = computed["indicators"]
            ev.evaluated_by = user_id
        else:
            ev = EffectivenessEvaluation(
                village_id=village_id,
                year=year,
                economic_score=computed["economic"],
                social_score=computed["social"],
                ecological_score=computed["ecological"],
                total_score=total,
                grade=grade,
                indicators=computed["indicators"],
                evaluated_by=user_id,
            )
            db.add(ev)
        db.commit()
        db.refresh(ev)

        # 更新同年度全部评估的排名
        all_evs = (
            db.query(EffectivenessEvaluation)
            .filter(EffectivenessEvaluation.year == year)
            .order_by(EffectivenessEvaluation.total_score.desc())
            .all()
        )
        for idx, row in enumerate(all_evs, 1):
            if row.rank != idx:
                row.rank = idx
        db.commit()

        result = EffectivenessService._eval_to_dict(ev)
        result["village_name"] = getattr(village, "name", "")
        return result

    @staticmethod
    def get_evaluation_report(db, village_id: int, year: int) -> Optional[Dict[str, Any]]:
        """获取评估报告（/report/{village_id} 端点）。无记录返回 None。"""
        ev = EffectivenessService._find_evaluation(db, village_id, year)
        if not ev:
            return None
        return EffectivenessService._eval_to_dict(ev)

    @staticmethod
    def compare_evaluations(db, village_id: int, year1: int, year2: int) -> Dict[str, Any]:
        """对比两年评估结果（/compare/{village_id} 端点）。"""
        ev1 = EffectivenessService._find_evaluation(db, village_id, year1)
        ev2 = EffectivenessService._find_evaluation(db, village_id, year2)
        if not ev1 or not ev2:
            missing = year1 if not ev1 else year2
            return {"error": f"缺少 {missing} 年的评估数据，无法对比"}

        def _r(v):
            return round(v, 2) if v is not None else None

        return {
            "village_id": village_id,
            "year1": year1,
            "year2": year2,
            "year1_data": EffectivenessService._eval_to_dict(ev1),
            "year2_data": EffectivenessService._eval_to_dict(ev2),
            "delta": {
                "total_score": _r((ev2.total_score or 0) - (ev1.total_score or 0)),
                "economic_score": _r((ev2.economic_score or 0) - (ev1.economic_score or 0)),
                "social_score": _r((ev2.social_score or 0) - (ev1.social_score or 0)),
                "ecological_score": _r((ev2.ecological_score or 0) - (ev1.ecological_score or 0)),
            },
        }

    def evaluate_village_effectiveness(self, village_id: int) -> EffectivenessMetrics:
        """
        评估村庄帮扶效果

        Args:
            village_id: 村庄ID

        Returns:
            EffectivenessMetrics: 效果评估指标
        """
        # 模拟评估逻辑
        return EffectivenessMetrics(
            income_growth_rate=0.15,
            project_completion_rate=0.85,
            fund_usage_rate=0.90,
            satisfaction_score=4.2,
            overall_score=0.82,
        )

    def evaluate_project_effectiveness(self, project_id: int) -> EffectivenessMetrics:
        """
        评估项目效果

        Args:
            project_id: 项目ID

        Returns:
            EffectivenessMetrics: 效果评估指标
        """
        return EffectivenessMetrics(
            income_growth_rate=0.12,
            project_completion_rate=0.95,
            fund_usage_rate=0.88,
            satisfaction_score=4.5,
            overall_score=0.85,
        )

    def evaluate_fund_effectiveness(self, fund_id: int) -> EffectivenessMetrics:
        """
        评估资金使用效果

        Args:
            fund_id: 资金ID

        Returns:
            EffectivenessMetrics: 效果评估指标
        """
        return EffectivenessMetrics(
            income_growth_rate=0.10,
            project_completion_rate=0.80,
            fund_usage_rate=0.92,
            satisfaction_score=4.0,
            overall_score=0.78,
        )

    def get_effectiveness_trends(self, entity_id: int, entity_type: str) -> Dict[str, List[float]]:
        """
        获取效果趋势

        Args:
            entity_id: 实体ID
            entity_type: 实体类型

        Returns:
            Dict[str, List[float]]: 各项指标的趋势数据
        """
        return {
            "income_growth": [0.10, 0.12, 0.15, 0.14, 0.16],
            "completion_rate": [0.70, 0.75, 0.80, 0.85, 0.90],
            "satisfaction": [3.8, 4.0, 4.1, 4.2, 4.3],
        }

    def export_effectiveness_report(self, entity_id: int, format: str = "pdf") -> bytes:
        """
        导出效果评估报告

        Args:
            entity_id: 实体ID
            format: 导出格式 (pdf, excel, word)

        Returns:
            bytes: 报告文件内容
        """
        # 模拟生成报告
        return b"Mock report content"

    def compare_effectiveness_periods(
        self, entity_id: int, period1: str, period2: str, period3: Optional[str] = None, period4: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        对比不同时期的效果

        Args:
            entity_id: 实体ID
            period1: 第一时期开始日期 (格式: YYYY-MM-DD) 或第一时期
            period2: 第一时期结束日期 (格式: YYYY-MM-DD) 或第二时期
            period3: 第二时期开始日期 (格式: YYYY-MM-DD)，可选
            period4: 第二时期结束日期 (格式: YYYY-MM-DD)，可选

        Returns:
            Dict[str, Any]: 对比结果
        """
        # 支持两种调用方式:
        # 1. compare_effectiveness_periods(entity_id, '2024-01', '2024-12')
        # 2. compare_effectiveness_periods(entity_id, '2024-01', '2024-06', '2024-07', '2024-12')
        if period3 is not None and period4 is not None:
            # 方式2: 4个日期参数
            return {
                "period1": f"{period1} to {period2}",
                "period2": f"{period3} to {period4}",
                "period1_metrics": EffectivenessMetrics(overall_score=0.75),
                "period2_metrics": EffectivenessMetrics(overall_score=0.82),
                "improvement": 0.07,
            }
        else:
            # 方式1: 2个时期参数
            return {
                "period1": period1,
                "period2": period2,
                "period1_metrics": EffectivenessMetrics(overall_score=0.75),
                "period2_metrics": EffectivenessMetrics(overall_score=0.82),
                "improvement": 0.07,
            }


def calculate_effectiveness_score(baseline: Dict[str, Any], current: Dict[str, Any]) -> float:
    """
    计算效果分数

    Args:
        baseline: 基线数据
        current: 当前数据

    Returns:
        float: 效果分数
    """
    return 0.80


def compare_effectiveness(
    baseline_metrics: List[Dict[str, Any]], current_metrics: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    对比效果

    Args:
        baseline_metrics: 基线指标列表
        current_metrics: 当前指标列表

    Returns:
        Dict[str, Any]: 对比结果
    """
    return {
        "improvement": 0.15,
        "regression": 0.05,
        "unchanged": 0.80,
    }


def generate_effectiveness_report(data: Dict[str, Any]) -> EffectivenessReport:
    """
    生成效果评估报告

    Args:
        data: 评估数据

    Returns:
        EffectivenessReport: 效果评估报告
    """
    return EffectivenessReport(
        entity_id=data.get("entity_id", 0),
        entity_type=data.get("entity_type", "village"),
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
        metrics=EffectivenessMetrics(overall_score=0.80),
        recommendations=["继续加强帮扶力度", "优化资金使用效率"],
    )
