"""
效果评估服务

提供帮扶效果评估功能
"""

from typing import Any, Dict, Optional

from app.core.transaction import safe_commit


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
        # AnnualIncome 的人均收入按年份分散列存储（per_capita_income_2020..2025），
        # 外键为 supported_village_id（village_id 字段已废弃）。
        income_field = f"per_capita_income_{year}"
        prev_field = f"per_capita_income_{year - 1}"
        incomes = (
            db.query(AnnualIncome)
            .filter(AnnualIncome.supported_village_id == village.id, AnnualIncome.year == year)
            .all()
        )
        per_capita = 0.0
        income_growth = 0.0
        if incomes and getattr(incomes[0], income_field, None) is not None:
            per_capita = float(getattr(incomes[0], income_field) or 0)
        prev = (
            db.query(AnnualIncome)
            .filter(AnnualIncome.supported_village_id == village.id, AnnualIncome.year == year - 1)
            .first()
        )
        if prev and getattr(prev, prev_field, None) and per_capita > 0:
            prev_val = float(getattr(prev, prev_field) or 0)
            if prev_val > 0:
                income_growth = round((per_capita - prev_val) / prev_val * 100, 1)

        # 基础设施覆盖
        infra_count = (
            db.query(func.count(AnnualInfrastructure.id))
            .filter(AnnualInfrastructure.supported_village_id == village.id, AnnualInfrastructure.year == year)
            .scalar()
            or 0
        )
        industry_count = (
            db.query(func.count(AnnualIndustry.id))
            .filter(AnnualIndustry.supported_village_id == village.id, AnnualIndustry.year == year)
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
        from app.models.supported_village import SupportedVillage

        village = (
            db.query(SupportedVillage)
            .filter(
                SupportedVillage.id == village_id,
                SupportedVillage.is_active == True,  # noqa: E712
            )
            .first()
        )
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
        db.flush()  # 先 flush 获得 ev.id（不提交事务）
        db.refresh(ev)

        # 更新同年度全部评估的排名（与评估写入同一事务：排名更新后统一 commit，
        # 保证"评估+排名"原子提交——避免第一步成功、第二步失败留下脏态）
        all_evs = (
            db.query(EffectivenessEvaluation)
            .filter(EffectivenessEvaluation.year == year)
            .order_by(EffectivenessEvaluation.total_score.desc())
            .all()
        )
        for idx, row in enumerate(all_evs, 1):
            if row.rank != idx:
                row.rank = idx
        safe_commit(db)

        result = EffectivenessService._eval_to_dict(ev)
        result["village_name"] = village.village_name
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
