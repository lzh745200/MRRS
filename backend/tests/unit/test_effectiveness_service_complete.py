"""
完整测试 - app.services.effectiveness_service
覆盖率目标: 100%
"""



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


# 说明（R27-H7）：本文件原有 4 个用例锁定 effectiveness_service 的假数据占位方法
# （get_effectiveness_trends / export_effectiveness_report / compare_effectiveness_periods）。
# 这些方法无任何调用方且返回写死数据，已随 R28 收尾删除 —— 旧断言锁定的正是
# R27 报告 H7 要求消除的「误导性假数据」，故未保留替代断言。
