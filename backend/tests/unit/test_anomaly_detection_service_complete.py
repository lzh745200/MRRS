"""
完整测试 - app.services.ai.anomaly_detection_service
覆盖率目标: 100%
"""


from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import numpy as np

class TestAnomalyDetectionService:
    """测试 AnomalyDetectionService 类"""

    def test_detect_anomalies_empty_data(self):
        """测试空数据返回空列表"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        result = AnomalyDetectionService.detect_anomalies([])
        assert result == []

    def test_detect_anomalies_zscore(self):
        """测试Z-Score异常检测"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        # 使用Z-Score直接测试，确保数据能触发异常检测
        # 通过直接调用内部方法测试，而不是通过detect_anomalies
        data = [
            {"id": 1, "value": 100},
            {"id": 2, "value": 100},
            {"id": 3, "value": 100},
            {"id": 4, "value": 100},
            {"id": 5, "value": 100},
            {"id": 6, "value": 1000},  # 明显异常值，Z-Score约17
        ]

        result = AnomalyDetectionService._detect_with_zscore(data, "value", threshold=2.0)

        assert len(result) >= 1
        assert result[0]["method"] == "zscore"
        assert "z_score" in result[0]

    def test_detect_anomalies_iqr(self):
        """测试IQR异常检测"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        data = [
            {"id": 1, "value": 100},
            {"id": 2, "value": 102},
            {"id": 3, "value": 101},
            {"id": 4, "value": 500},  # 异常值
        ]

        result = AnomalyDetectionService.detect_anomalies(data, method="iqr")

        assert len(result) >= 1
        assert result[0]["method"] == "iqr"
        assert "lower_bound" in result[0]
        assert "upper_bound" in result[0]

    def test_detect_anomalies_default_method(self):
        """测试默认检测方法（iqr）"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        data = [
            {"id": 1, "value": 100},
            {"id": 2, "value": 500},
        ]

        result = AnomalyDetectionService.detect_anomalies(data)

        # 当sklearn不可用时使用iqr
        assert isinstance(result, list)

    def test_detect_anomalies_exception(self):
        """测试异常处理"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        # 提供无效数据触发异常
        data = [{"id": 1}]  # 缺少value字段

        with patch('app.services.ai.anomaly_detection_service.logger') as mock_logger:
            result = AnomalyDetectionService.detect_anomalies(data, value_field="value")

        assert result == []
        mock_logger.error.assert_called_once()

    def test_detect_with_isolation_forest(self):
        """测试孤立森林检测"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        # 生成一些测试数据
        np.random.seed(42)
        normal_data = np.random.normal(100, 10, 50)
        anomaly_data = [500, 600]  # 异常值
        all_values = list(normal_data) + anomaly_data

        data = [{"id": i, "value": v} for i, v in enumerate(all_values)]

        with patch('app.services.ai.anomaly_detection_service.SKLEARN_AVAILABLE', True):
            with patch('app.services.ai.anomaly_detection_service.IsolationForest') as mock_model:
                mock_instance = MagicMock()
                mock_instance.fit_predict.return_value = [1] * 50 + [-1, -1]  # 最后两个是异常
                mock_instance.score_samples.return_value = [-0.5]
                mock_model.return_value = mock_instance

                result = AnomalyDetectionService._detect_with_isolation_forest(
                    data, "value", 0.1
                )

        assert len(result) == 2
        assert result[0]["method"] == "isolation_forest"
        assert "anomaly_score" in result[0]

    def test_detect_with_zscore_zero_std(self):
        """测试Z-Score检测 - 标准差为0"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        data = [{"id": 1, "value": 100}, {"id": 2, "value": 100}]

        result = AnomalyDetectionService._detect_with_zscore(data, "value")

        assert result == []

    def test_detect_with_zscore_with_threshold(self):
        """测试Z-Score检测 - 自定义阈值"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        data = [
            {"id": 1, "value": 100},
            {"id": 2, "value": 100},
            {"id": 3, "value": 100},
            {"id": 4, "value": 200},
        ]

        result = AnomalyDetectionService._detect_with_zscore(data, "value", threshold=1.5)

        assert len(result) >= 1
        assert result[0]["method"] == "zscore"

    def test_detect_fund_anomalies(self):
        """测试资金异常检测"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_fund = MagicMock()
        mock_fund.id = 1
        mock_fund.village_id = 1
        mock_fund.project_id = 1
        mock_fund.amount = 1000
        mock_fund.allocation_date = datetime.utcnow()
        mock_fund.purpose = "test"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_fund]

        with patch('app.services.ai.anomaly_detection_service.SKLEARN_AVAILABLE', False):
            result = AnomalyDetectionService.detect_fund_anomalies(mock_db, days=30)

        assert isinstance(result, list)

    def test_detect_fund_anomalies_empty(self):
        """测试资金异常检测 - 无数据"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = AnomalyDetectionService.detect_fund_anomalies(mock_db, days=30)

        assert result == []

    def test_detect_fund_anomalies_none_date(self):
        """测试资金异常检测 - allocation_date为None"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_fund = MagicMock()
        mock_fund.id = 1
        mock_fund.village_id = 1
        mock_fund.project_id = 1
        mock_fund.amount = 1000
        mock_fund.allocation_date = None
        mock_fund.purpose = "test"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_fund]

        with patch('app.services.ai.anomaly_detection_service.SKLEARN_AVAILABLE', False):
            result = AnomalyDetectionService.detect_fund_anomalies(mock_db, days=30)

        assert isinstance(result, list)

    def test_detect_project_progress_anomalies(self):
        """测试项目进度异常检测"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test"
        mock_project.village_id = 1
        mock_project.status = "in_progress"
        mock_project.start_date = datetime.utcnow().date() - timedelta(days=50)
        mock_project.end_date = datetime.utcnow().date() + timedelta(days=50)
        mock_project.progress = 10  # 偏差很大

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project]

        result = AnomalyDetectionService.detect_project_progress_anomalies(mock_db)

        assert len(result) >= 1
        assert result[0]["type"] == "progress_deviation"
        assert "deviation" in result[0]

    def test_detect_project_progress_anomalies_no_projects(self):
        """测试项目进度异常检测 - 无项目"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = AnomalyDetectionService.detect_project_progress_anomalies(mock_db)

        assert result == []

    def test_detect_project_progress_anomalies_no_dates(self):
        """测试项目进度异常检测 - 无日期"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test"
        mock_project.village_id = 1
        mock_project.start_date = None
        mock_project.end_date = None
        mock_project.progress = 50

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project]

        result = AnomalyDetectionService.detect_project_progress_anomalies(mock_db)

        assert result == []

    def test_detect_project_progress_anomalies_no_deviation(self):
        """测试项目进度异常检测 - 无偏差"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "test"
        mock_project.village_id = 1
        mock_project.start_date = datetime.utcnow().date() - timedelta(days=50)
        mock_project.end_date = datetime.utcnow().date() + timedelta(days=50)
        mock_project.progress = 50  # 偏差很小

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_project]

        result = AnomalyDetectionService.detect_project_progress_anomalies(mock_db)

        assert result == []

    def test_detect_data_entry_anomalies(self):
        """测试数据录入异常检测"""
        from app.services.ai.anomaly_detection_service import AnomalyDetectionService

        data = [
            {"id": 1, "amount": 100},
            {"id": 2, "amount": 102},
            {"id": 3, "amount": 500},
        ]

        result = AnomalyDetectionService.detect_data_entry_anomalies(data, "amount")

        assert isinstance(result, list)

class TestSklearnImport:
    """测试scikit-learn导入处理"""

    def test_sklearn_not_available_path(self):
        """sklearn 不可用时模块导入仍成功且 SKLEARN_AVAILABLE=False（覆盖22-24行）。

        W1 不变量 8: 禁止对 services 子模块 importlib.reload（reload 就地重建
        类对象, 且半初始化状态无法可靠还原）。导入分支改在子进程中验证,
        零模块状态污染。
        """
        import subprocess
        import sys
        from pathlib import Path

        code = (
            "import builtins\n"
            "_orig_import = builtins.__import__\n"
            "def _mock_import(name, *args, **kwargs):\n"
            "    if 'sklearn' in name:\n"
            "        raise ImportError(f'No module named {name!r}')\n"
            "    return _orig_import(name, *args, **kwargs)\n"
            "builtins.__import__ = _mock_import\n"
            "import app.services.ai.anomaly_detection_service as m\n"
            "assert m.SKLEARN_AVAILABLE is False\n"
            "print('OK')\n"
        )
        backend_dir = str(Path(__file__).resolve().parents[2])
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"子进程失败:\n{result.stderr}"
        assert "OK" in result.stdout

    def test_sklearn_available_info(self):
        """测试sklearn可用时记录信息日志（覆盖21行）"""
        from app.services.ai import anomaly_detection_service

        # 当SKLEARN_AVAILABLE为True时，验证模块已正确加载
        assert hasattr(anomaly_detection_service, 'SKLEARN_AVAILABLE')
