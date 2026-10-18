"""Unit test conftest —— 可选重依赖的**兜底替身**（真实包优先）。

W4-T7（2026-10-18）：旧实现用 ``'sklearn' not in sys.modules`` 判定，而
"已安装但尚未 import" 同样满足该条件 —— 只要单元测试树里没人先 import
sklearn，整个测试进程就早早被塞进 MagicMock 替身，真实实现永远走不到
（表面断言通过、真实路径无人验证）。scikit-learn 是 requirements.txt 的
运行时依赖（scipy 随之安装），因此改为先 ``importlib.util.find_spec``
探测真实包；仅在确实缺失的精简环境（未装依赖的窄容器）才退回替身，
保证模块仍可导入、收集不崩。

替身只应作为最后手段：需要特定行为的用例请在本用例内显式 patch（例如
``test_anomaly_detection_service_complete`` 直接 patch 服务模块内的
``SKLEARN_AVAILABLE`` / ``IsolationForest``）。
"""
import sys
from importlib.util import find_spec
from unittest.mock import MagicMock


def _inject_sklearn_mock() -> None:
    """真实 sklearn 缺失时的最小替身（覆盖 app 代码用到的三处 API）。"""
    sklearn_mock = MagicMock()
    sklearn_mock.linear_model.LinearRegression.return_value.fit.return_value = sklearn_mock
    sklearn_mock.linear_model.LinearRegression.return_value.predict.return_value = [100.0, 105.0]
    sklearn_mock.linear_model.LinearRegression.return_value.coef_ = [2.5]
    sklearn_mock.ensemble.IsolationForest.return_value.fit_predict.return_value = [1, 1, -1]
    sklearn_mock.preprocessing.StandardScaler.return_value.fit_transform.return_value = [[0.0, 0.0]]
    sys.modules["sklearn"] = sklearn_mock
    sys.modules["sklearn.linear_model"] = sklearn_mock.linear_model
    sys.modules["sklearn.ensemble"] = sklearn_mock.ensemble
    sys.modules["sklearn.preprocessing"] = sklearn_mock.preprocessing


def _inject_scipy_mock() -> None:
    """真实 scipy 缺失时的最小替身（stats.linregress 一处）。"""
    scipy_mock = MagicMock()
    scipy_mock.stats.linregress.return_value = MagicMock(slope=2.5, intercept=100.0, rvalue=0.9)
    sys.modules["scipy"] = scipy_mock
    sys.modules["scipy.stats"] = scipy_mock.stats


if find_spec("sklearn") is None and "sklearn" not in sys.modules:
    _inject_sklearn_mock()

if find_spec("scipy") is None and "scipy" not in sys.modules:
    _inject_scipy_mock()
