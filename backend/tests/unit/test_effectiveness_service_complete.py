"""
完整测试 - app.services.effectiveness_service
覆盖率目标: 100%
"""
from datetime import datetime



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
