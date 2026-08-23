"""
异常检测服务
使用统计方法和机器学习检测异常数据
"""

import logging
from datetime import timezone, datetime, timedelta
from typing import Any, Dict, List

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 尝试导入scikit-learn
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
    logger.info("scikit-learn 已加载，异常检测功能可用")
except ImportError as e:  # pragma: no cover
    SKLEARN_AVAILABLE = False
    logger.warning(f"scikit-learn未安装,异常检测功能将受限: {e}")


class AnomalyDetectionService:
    """异常检测服务"""

    @staticmethod
    def detect_anomalies(
        data: List[Dict[str, Any]],
        value_field: str = "value",
        method: str = "isolation_forest",
        contamination: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        检测异常值

        Args:
            data: 数据列表
            value_field: 值字段名
            method: 检测方法(isolation_forest/zscore/iqr)
            contamination: 异常比例(0-0.5)

        Returns:
            异常记录列表
        """
        if not data:
            return []

        try:
            if method == "isolation_forest" and SKLEARN_AVAILABLE:
                return AnomalyDetectionService._detect_with_isolation_forest(data, value_field, contamination)
            elif method == "zscore":
                return AnomalyDetectionService._detect_with_zscore(data, value_field)
            else:
                return AnomalyDetectionService._detect_with_iqr(data, value_field)
        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return []

    @staticmethod
    def _detect_with_isolation_forest(
        data: List[Dict[str, Any]], value_field: str, contamination: float
    ) -> List[Dict[str, Any]]:
        """使用孤立森林检测异常"""
        values = np.array([d[value_field] for d in data]).reshape(-1, 1)

        # 标准化
        scaler = StandardScaler()
        values_scaled = scaler.fit_transform(values)

        # 训练模型
        model = IsolationForest(contamination=contamination, random_state=42)
        predictions = model.fit_predict(values_scaled)

        # 提取异常
        anomalies = []
        for idx, pred in enumerate(predictions):
            if pred == -1:  # -1表示异常
                anomaly = data[idx].copy()
                anomaly["anomaly_score"] = float(model.score_samples(values_scaled[idx: idx + 1])[0])
                anomaly["method"] = "isolation_forest"
                anomalies.append(anomaly)

        return anomalies

    @staticmethod
    def _detect_with_zscore(
        data: List[Dict[str, Any]], value_field: str, threshold: float = 3.0
    ) -> List[Dict[str, Any]]:
        """使用Z-Score检测异常"""
        values = np.array([d[value_field] for d in data])

        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return []

        z_scores = np.abs((values - mean) / std)

        anomalies = []
        for idx, z_score in enumerate(z_scores):
            if z_score > threshold:
                anomaly = data[idx].copy()
                anomaly["z_score"] = float(z_score)
                anomaly["method"] = "zscore"
                anomalies.append(anomaly)

        return anomalies

    @staticmethod
    def _detect_with_iqr(data: List[Dict[str, Any]], value_field: str) -> List[Dict[str, Any]]:
        """使用IQR(四分位距)检测异常"""
        values = np.array([d[value_field] for d in data])

        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        anomalies = []
        for idx, value in enumerate(values):
            if value < lower_bound or value > upper_bound:
                anomaly = data[idx].copy()
                anomaly["lower_bound"] = float(lower_bound)
                anomaly["upper_bound"] = float(upper_bound)
                anomaly["method"] = "iqr"
                anomalies.append(anomaly)

        return anomalies

    @staticmethod
    def detect_fund_anomalies(db: Session, days: int = 30) -> List[Dict[str, Any]]:
        """
        检测资金使用异常

        Args:
            db: 数据库会话
            days: 检测天数

        Returns:
            异常资金记录列表
        """
        from app.models.fund import Fund

        since = datetime.now(timezone.utc) - timedelta(days=days)

        # 查询最近的资金记录（软删经费排除）
        funds = (
            db.query(Fund)
            .filter(Fund.is_active == True, Fund.allocation_date >= since)  # noqa: E712
            .all()
        )

        if not funds:
            return []

        # 准备数据
        data = []
        for fund in funds:
            data.append(
                {
                    "id": fund.id,
                    "village_id": fund.village_id,
                    "project_id": fund.project_id,
                    "value": fund.amount or 0,
                    "allocation_date": (fund.allocation_date.isoformat() if fund.allocation_date else None),
                    "purpose": fund.purpose,
                }
            )

        # 检测异常
        anomalies = AnomalyDetectionService.detect_anomalies(
            data=data,
            value_field="value",
            method="isolation_forest" if SKLEARN_AVAILABLE else "iqr",
        )

        return anomalies

    @staticmethod
    def detect_project_progress_anomalies(db: Session) -> List[Dict[str, Any]]:
        """
        检测项目进度异常

        Args:
            db: 数据库会话

        Returns:
            异常项目列表
        """
        from app.models.project import Project

        # 查询进行中的项目（软删项目排除）
        projects = (
            db.query(Project)
            .filter(Project.is_active == True, Project.status == "in_progress")  # noqa: E712
            .all()
        )

        anomalies = []

        for project in projects:
            # 检查进度异常
            if project.start_date and project.end_date:
                total_days = (project.end_date - project.start_date).days
                elapsed_days = (datetime.now(timezone.utc).date() - project.start_date).days

                if total_days > 0:
                    expected_progress = (elapsed_days / total_days) * 100
                    actual_progress = project.progress or 0

                    # 进度偏差超过20%视为异常
                    deviation = abs(expected_progress - actual_progress)
                    if deviation > 20:
                        anomalies.append(
                            {
                                "id": project.id,
                                "name": project.name,
                                "village_id": project.village_id,
                                "expected_progress": round(expected_progress, 2),
                                "actual_progress": actual_progress,
                                "deviation": round(deviation, 2),
                                "type": "progress_deviation",
                            }
                        )

        return anomalies

    @staticmethod
    def detect_data_entry_anomalies(data: List[Dict[str, Any]], field_name: str) -> List[Dict[str, Any]]:
        """
        检测数据录入异常(离群点)

        Args:
            data: 数据列表
            field_name: 字段名

        Returns:
            异常记录列表
        """
        return AnomalyDetectionService.detect_anomalies(data=data, value_field=field_name, method="zscore")
