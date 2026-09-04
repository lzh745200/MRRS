"""
趋势预测服务
使用时间序列分析预测未来趋势
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Prophet 初始化超时（秒）— Windows 上 cmdstanpy 可能因 where.exe 挂起
_PROPHET_TIMEOUT = 10

# 尝试导入Prophet
try:
    from prophet import Prophet

    # 可选依赖 prophet 的“成功导入”分支：仅在环境安装了 prophet 时执行，
    # 与下方 ImportError 分支互斥；CI/测试环境未安装 prophet，故对称豁免。
    PROPHET_AVAILABLE = True  # pragma: no cover
    logger.info("Prophet 已加载，趋势预测功能可用")  # pragma: no cover
except ImportError as e:  # pragma: no cover
    PROPHET_AVAILABLE = False  # pragma: no cover
    logger.warning(f"Prophet未安装,趋势预测功能将受限: {e}")  # pragma: no cover


class TrendPredictionService:
    """趋势预测服务"""

    @staticmethod
    def predict_time_series(
        historical_data: List[Dict[str, Any]],
        periods: int = 12,
        date_field: str = "date",
        value_field: str = "value",
        method: str = "prophet",
    ) -> Dict[str, Any]:
        """
        时间序列预测

        Args:
            historical_data: 历史数据列表
            periods: 预测周期数
            date_field: 日期字段名
            value_field: 值字段名
            method: 预测方法(prophet/moving_average/linear)

        Returns:
            预测结果字典
        """
        if not historical_data:
            return {
                "predictions": [],
                "confidence_intervals": [],
                "method": method,
                "error": "历史数据为空",
            }

        try:
            if method == "prophet" and PROPHET_AVAILABLE:  # pragma: no cover
                # Prophet 在 Windows 上可能因 cmdstanpy/where.exe 挂起，添加超时保护
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        TrendPredictionService._predict_with_prophet,
                        historical_data, periods, date_field, value_field,
                    )
                    try:
                        return future.result(timeout=_PROPHET_TIMEOUT)
                    except FuturesTimeoutError:
                        logger.warning("Prophet 预测超时，回退到线性回归")
                        return TrendPredictionService._predict_with_linear(
                            historical_data, periods, date_field, value_field
                        )
            elif method == "moving_average":
                return TrendPredictionService._predict_with_moving_average(
                    historical_data, periods, date_field, value_field
                )
            else:
                return TrendPredictionService._predict_with_linear(historical_data, periods, date_field, value_field)
        except Exception as e:
            logger.error(f"趋势预测失败: {e}")
            return {
                "predictions": [],
                "confidence_intervals": [],
                "method": method,
                "error": str(e),
            }

    @staticmethod
    def _predict_with_prophet(  # pragma: no cover
        historical_data: List[Dict[str, Any]],
        periods: int,
        date_field: str,
        value_field: str,
    ) -> Dict[str, Any]:
        """使用Prophet进行预测"""
        # 准备数据
        df = pd.DataFrame(historical_data)
        df = df.rename(columns={date_field: "ds", value_field: "y"})

        # 确保日期格式正确
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds")

        # 创建并训练模型
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=0.95,
        )
        model.fit(df)

        # 生成未来日期
        future = model.make_future_dataframe(periods=periods, freq="ME")
        forecast = model.predict(future)

        # 提取预测结果
        predictions = []
        confidence_intervals = []

        for idx in range(len(df), len(forecast)):
            row = forecast.iloc[idx]
            predictions.append(
                {
                    "date": row["ds"].strftime("%Y-%m-%d"),
                    "value": round(float(row["yhat"]), 2),
                }
            )
            confidence_intervals.append(
                {
                    "date": row["ds"].strftime("%Y-%m-%d"),
                    "lower": round(float(row["yhat_lower"]), 2),
                    "upper": round(float(row["yhat_upper"]), 2),
                }
            )

        return {
            "predictions": predictions,
            "confidence_intervals": confidence_intervals,
            "method": "prophet",
            "model_params": {"yearly_seasonality": True, "interval_width": 0.95},
        }

    @staticmethod
    def _predict_with_moving_average(
        historical_data: List[Dict[str, Any]],
        periods: int,
        date_field: str,
        value_field: str,
        window: int = 3,
    ) -> Dict[str, Any]:
        """使用移动平均进行预测"""
        df = pd.DataFrame(historical_data)
        df = df.sort_values(date_field)

        values = df[value_field].values

        # 计算移动平均
        if len(values) < window:
            window = len(values)

        predictions = []
        last_date = pd.to_datetime(df[date_field].iloc[-1])

        # 使用最后window个值的平均值作为预测
        avg_value = np.mean(values[-window:])

        for i in range(1, periods + 1):
            pred_date = last_date + pd.DateOffset(months=i)
            predictions.append(
                {
                    "date": pred_date.strftime("%Y-%m-%d"),
                    "value": round(float(avg_value), 2),
                }
            )

        return {
            "predictions": predictions,
            "confidence_intervals": [],
            "method": "moving_average",
            "model_params": {"window": window},
        }

    @staticmethod
    def _predict_with_linear(
        historical_data: List[Dict[str, Any]],
        periods: int,
        date_field: str,
        value_field: str,
    ) -> Dict[str, Any]:
        """使用线性回归进行预测"""
        df = pd.DataFrame(historical_data)
        df = df.sort_values(date_field)
        df["timestamp"] = pd.to_datetime(df[date_field]).astype(np.int64) // 10**9

        X = df["timestamp"].values.reshape(-1, 1)
        y = df[value_field].values

        # 最小二乘一次拟合（替代死代码清理移除的 sklearn.LinearRegression）
        # 样本不足时 polyfit 发出病态条件警告属预期降级路径，局部抑制；
        # 不按类别过滤 —— RankWarning 在 numpy 2.x 已移入 exceptions 且跨版本不稳
        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            slope, intercept = np.polyfit(X.ravel(), y, 1)

        # 预测
        last_date = pd.to_datetime(df[date_field].iloc[-1])
        predictions = []

        for i in range(1, periods + 1):
            pred_date = last_date + pd.DateOffset(months=i)
            pred_timestamp = pred_date.timestamp()
            pred_value = slope * pred_timestamp + intercept

            predictions.append(
                {
                    "date": pred_date.strftime("%Y-%m-%d"),
                    "value": round(float(pred_value), 2),
                }
            )

        return {
            "predictions": predictions,
            "confidence_intervals": [],
            "method": "linear_regression",
            "model_params": {
                "coefficient": float(slope),
                "intercept": float(intercept),
            },
        }

    @staticmethod
    def predict_income_trend(historical_data: List[Dict[str, Any]], years_ahead: int = 3) -> Dict[str, Any]:
        """
        预测收入趋势 (兼容测试API)

        Args:
            historical_data: 历史数据列表，每项包含year和income
            years_ahead: 预测年数

        Returns:
            预测结果
        """
        if not historical_data:
            return {"predictions": [], "error": "至少需要2个数据点"}

        # 单次遍历：转换数据格式并计数
        formatted_data = [
            {"date": f"{item['year']}-01-01", "value": item["income"]}
            for item in historical_data
            if item.get("year") and item.get("income") is not None
        ]

        if len(formatted_data) < 2:
            return {"predictions": [], "error": "有效数据点不足"}

        # 预测
        return TrendPredictionService.predict_time_series(
            historical_data=formatted_data,
            periods=years_ahead,
            method="linear",  # 使用线性回归，不依赖prophet
        )

    @staticmethod
    def predict_village_income(db: Session, village_id: int, periods: int = 12) -> Dict[str, Any]:  # pragma: no cover
        """
        预测村庄收入趋势

        Args:
            db: 数据库会话
            village_id: 村庄ID
            periods: 预测周期数(月)

        Returns:
            预测结果
        """
        from app.models.annual_income import AnnualIncome

        # 查询历史收入数据（AnnualIncome 外键为 supported_village_id，人均收入按年份列存储）
        income_records = (
            db.query(AnnualIncome)
            .filter(AnnualIncome.supported_village_id == village_id)
            .order_by(AnnualIncome.year)
            .all()
        )

        if not income_records:
            return {"predictions": [], "error": "无历史收入数据"}

        # 准备数据
        historical_data = []
        for record in income_records:
            value = getattr(record, f"per_capita_income_{record.year}", 0)
            historical_data.append({"date": f"{record.year}-01-01", "value": float(value or 0)})

        # 预测
        return TrendPredictionService.predict_time_series(
            historical_data=historical_data,
            periods=periods,
            method="prophet" if PROPHET_AVAILABLE else "linear",
        )

    @staticmethod
    def predict_village_population(  # pragma: no cover
        db: Session, village_id: int, periods: int = 12
    ) -> Dict[str, Any]:
        """
        预测村庄人口趋势

        Args:
            db: 数据库会话
            village_id: 村庄ID
            periods: 预测周期数(月)

        Returns:
            预测结果
        """
        from app.models.annual_population import AnnualPopulation

        # 查询历史人口数据（AnnualPopulation 外键为 supported_village_id，人口字段为 population）
        population_records = (
            db.query(AnnualPopulation)
            .filter(AnnualPopulation.supported_village_id == village_id)
            .order_by(AnnualPopulation.year)
            .all()
        )

        if not population_records:
            return {"predictions": [], "error": "无历史人口数据"}

        # 准备数据
        historical_data = []
        for record in population_records:
            historical_data.append({"date": f"{record.year}-01-01", "value": record.population or 0})

        # 预测
        return TrendPredictionService.predict_time_series(
            historical_data=historical_data,
            periods=periods,
            method="prophet" if PROPHET_AVAILABLE else "linear",
        )
