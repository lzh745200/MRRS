"""Unit test conftest — provides mocks for optional heavy dependencies."""
import sys
from unittest.mock import MagicMock

# Mock sklearn if not installed (heavy ML dependency, optional)
if 'sklearn' not in sys.modules:
    sklearn_mock = MagicMock()
    sklearn_mock.linear_model.LinearRegression.return_value.fit.return_value = sklearn_mock
    sklearn_mock.linear_model.LinearRegression.return_value.predict.return_value = [100.0, 105.0]
    sklearn_mock.linear_model.LinearRegression.return_value.coef_ = [2.5]
    sklearn_mock.ensemble.IsolationForest.return_value.fit_predict.return_value = [1, 1, -1]
    sys.modules['sklearn'] = sklearn_mock
    sys.modules['sklearn.linear_model'] = sklearn_mock.linear_model
    sklearn_mock.preprocessing.StandardScaler.return_value.fit_transform.return_value = [[0.0, 0.0]]
    sys.modules['sklearn.ensemble'] = sklearn_mock.ensemble
    sys.modules['sklearn.preprocessing'] = sklearn_mock.preprocessing

if 'scipy' not in sys.modules:
    scipy_mock = MagicMock()
    scipy_mock.stats.linregress.return_value = MagicMock(slope=2.5, intercept=100.0, rvalue=0.9)
    sys.modules['scipy'] = scipy_mock
    sys.modules['scipy.stats'] = scipy_mock.stats
