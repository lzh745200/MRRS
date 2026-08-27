"""
完整测试 - app.services.effectiveness_service
覆盖率目标: 100%
"""
from datetime import datetime

class TestEffectivenessMetrics:
    """测试 EffectivenessMetrics 数据类"""

    def test_metrics_default(self):
        """测试默认指标值"""
        from app.services.effectiveness_service import EffectivenessMetrics
        metrics = EffectivenessMetrics()
        assert metrics.income_growth_rate == 0.0
        assert metrics.project_completion_rate == 0.0
        assert metrics.fund_usage_rate == 0.0
        assert metrics.satisfaction_score == 0.0
        assert metrics.overall_score == 0.0

    def test_metrics_custom(self):
        """测试自定义指标值"""
        from app.services.effectiveness_service import EffectivenessMetrics
        metrics = EffectivenessMetrics(
            income_growth_rate=0.15,
            project_completion_rate=0.85,
            fund_usage_rate=0.90,
            satisfaction_score=4.2,
            overall_score=0.82
        )
        assert metrics.income_growth_rate == 0.15
        assert metrics.project_completion_rate == 0.85
        assert metrics.fund_usage_rate == 0.90
        assert metrics.satisfaction_score == 4.2
        assert metrics.overall_score == 0.82

class TestEffectivenessReport:
    """测试 EffectivenessReport 数据类"""

    def test_report_creation(self):
        """测试报告创建"""
        from app.services.effectiveness_service import EffectivenessReport, EffectivenessMetrics
        metrics = EffectivenessMetrics(overall_score=0.80)
        report = EffectivenessReport(
            entity_id=1,
            entity_type="village",
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
            metrics=metrics,
            recommendations=["建议1", "建议2"]
        )
        assert report.entity_id == 1
        assert report.entity_type == "village"
        assert report.recommendations == ["建议1", "建议2"]

class TestEffectivenessService:
    """测试 EffectivenessService 类"""

    def test_service_import(self):
        """测试类可以导入"""
        from app.services.effectiveness_service import EffectivenessService
        assert EffectivenessService is not None

    def test_service_creation(self):
        """测试服务创建"""
        from app.services.effectiveness_service import EffectivenessService
        service = EffectivenessService()
        assert service is not None
        assert service.evaluation_cache == {}

    def test_evaluate_village_effectiveness(self):
        """测试评估村庄效果"""
        from app.services.effectiveness_service import EffectivenessService, EffectivenessMetrics
        service = EffectivenessService()
        result = service.evaluate_village_effectiveness(1)
        assert isinstance(result, EffectivenessMetrics)
        assert result.overall_score == 0.82

    def test_evaluate_project_effectiveness(self):
        """测试评估项目效果"""
        from app.services.effectiveness_service import EffectivenessService, EffectivenessMetrics
        service = EffectivenessService()
        result = service.evaluate_project_effectiveness(1)
        assert isinstance(result, EffectivenessMetrics)
        assert result.overall_score == 0.85

    def test_evaluate_fund_effectiveness(self):
        """测试评估资金效果"""
        from app.services.effectiveness_service import EffectivenessService, EffectivenessMetrics
        service = EffectivenessService()
        result = service.evaluate_fund_effectiveness(1)
        assert isinstance(result, EffectivenessMetrics)
        assert result.overall_score == 0.78

    def test_get_effectiveness_trends(self):
        """测试获取效果趋势"""
        from app.services.effectiveness_service import EffectivenessService
        service = EffectivenessService()
        result = service.get_effectiveness_trends(1, "village")
        assert isinstance(result, dict)
        assert "income_growth" in result
        assert "completion_rate" in result
        assert "satisfaction" in result

    def test_export_effectiveness_report_pdf(self):
        """测试导出PDF报告"""
        from app.services.effectiveness_service import EffectivenessService
        service = EffectivenessService()
        result = service.export_effectiveness_report(1, format="pdf")
        assert isinstance(result, bytes)

    def test_export_effectiveness_report_excel(self):
        """测试导出Excel报告"""
        from app.services.effectiveness_service import EffectivenessService
        service = EffectivenessService()
        result = service.export_effectiveness_report(1, format="excel")
        assert isinstance(result, bytes)

    def test_compare_effectiveness_periods(self):
        """测试对比时期效果"""
        from app.services.effectiveness_service import EffectivenessService
        service = EffectivenessService()
        result = service.compare_effectiveness_periods(
            1, "2024-01-01", "2024-06-30", "2024-07-01", "2024-12-31"
        )
        assert isinstance(result, dict)
        assert "period1_metrics" in result
        assert "period2_metrics" in result
        assert "improvement" in result
