# -*- coding: utf-8 -*-
"""P2-3 收尾：慢阈值统一收敛到 settings 的接线测试。

覆盖三处原本硬编码、现改为读取 settings 的阈值，并锁定默认值零变化：
- app/middleware/metrics_middleware.py : SLOW_METRICS_THRESHOLD_SECONDS（秒）
- app/middleware/request_id.py         : SLOW_REQUEST_THRESHOLD_MS（毫秒）
- app/core/query_optimizer.py          : SLOW_QUERY_THRESHOLD_MS（毫秒）
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings, settings


# ==============================================================================
# 默认值零变化：新配置项默认值必须严格等于各模块此前的硬编码值
# ==============================================================================


class TestConfigDefaultsPreserveLegacyValues:
    def test_defaults_equal_legacy_hardcoded(self):
        # 用 model_fields 读字段默认值，避免受运行环境变量/ .env 影响
        fields = Settings.model_fields
        assert fields["SLOW_API_MS"].default == 500.0
        assert fields["SLOW_SQL_MS"].default == 200.0
        assert fields["SLOW_QUERY_THRESHOLD_MS"].default == 200.0  # query_optimizer 原 200.0
        assert fields["SLOW_REQUEST_THRESHOLD_MS"].default == 2000.0  # request_id 原 2000
        assert fields["SLOW_METRICS_THRESHOLD_SECONDS"].default == 1.0  # metrics_middleware 原 1.0


# ==============================================================================
# metrics_middleware：阈值来自 settings（秒），构造 store 时读取
# ==============================================================================


class TestMetricsThresholdFromSettings:
    def test_store_reads_settings_threshold(self, monkeypatch):
        from app.middleware.metrics_middleware import _MetricsStore

        monkeypatch.setattr(settings, "SLOW_METRICS_THRESHOLD_SECONDS", 3.5)
        store = _MetricsStore()
        assert store._slow_threshold == 3.5
        # 摘要里暴露的阈值也随 settings 变化
        assert store.get_summary()["slow_threshold_seconds"] == 3.5

    def test_store_threshold_governs_recording(self, monkeypatch):
        from app.middleware.metrics_middleware import _MetricsStore

        monkeypatch.setattr(settings, "SLOW_METRICS_THRESHOLD_SECONDS", 3.5)
        store = _MetricsStore()
        store.record("GET", "/fast", 200, 3.0)   # < 3.5s → 不记
        store.record("GET", "/slow", 200, 4.0)   # > 3.5s → 记
        assert store.get_summary()["slow_request_count"] == 1

    def test_default_threshold_is_one_second(self):
        from app.middleware.metrics_middleware import _MetricsStore

        # 未经 monkeypatch：默认应等于 settings 默认值 1.0（= 原硬编码）
        assert _MetricsStore()._slow_threshold == settings.SLOW_METRICS_THRESHOLD_SECONDS


# ==============================================================================
# request_id：阈值来自 settings（毫秒），请求时读取
# ==============================================================================


def _req(headers=None):
    r = MagicMock()
    r.headers = headers or {}
    r.method = "GET"
    r.url.path = "/x"
    r.state = MagicMock()
    return r


def _resp():
    resp = MagicMock()
    resp.headers = {}
    resp.status_code = 200
    return resp


class TestRequestIdThresholdFromSettings:
    @pytest.mark.asyncio
    async def test_high_threshold_suppresses_warning(self, monkeypatch):
        import app.middleware.request_id as mod

        monkeypatch.setattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 10000.0)
        with patch.object(mod.time, "time", side_effect=[1000.0] + [1003.0] * 20):
            with patch.object(mod.logger, "warning") as warn:
                await mod.RequestIDMiddleware(app=MagicMock()).dispatch(
                    _req(), AsyncMock(return_value=_resp())
                )
        # 3000ms < 10000ms → 不告警
        assert warn.call_count == 0

    @pytest.mark.asyncio
    async def test_low_threshold_triggers_warning(self, monkeypatch):
        import app.middleware.request_id as mod

        monkeypatch.setattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 100.0)
        with patch.object(mod.time, "time", side_effect=[2000.0] + [2001.0] * 20):
            with patch.object(mod.logger, "warning") as warn:
                out = await mod.RequestIDMiddleware(app=MagicMock()).dispatch(
                    _req(), AsyncMock(return_value=_resp())
                )
        # 1000ms > 100ms → 告警
        assert out.status_code == 200
        assert warn.call_count == 1

    def test_request_id_module_no_longer_hardcodes_threshold(self):
        # 模块级常量已移除，阈值改由 settings 提供（防回归：不得再出现硬编码常量）
        import app.middleware.request_id as mod

        assert not hasattr(mod, "SLOW_REQUEST_THRESHOLD_MS")


# ==============================================================================
# query_optimizer：阈值来自 settings（毫秒），track_query 调用时读取
# ==============================================================================


class TestQueryOptimizerThresholdFromSettings:
    def setup_method(self):
        from app.core import query_optimizer as qo

        self._qo = qo
        self._saved = list(qo._slow_query_log)
        qo._slow_query_log.clear()

    def teardown_method(self):
        self._qo._slow_query_log.clear()
        self._qo._slow_query_log.extend(self._saved)

    def test_slow_threshold_from_settings(self, monkeypatch):
        qo = self._qo
        monkeypatch.setattr(settings, "SLOW_QUERY_THRESHOLD_MS", 0.0)
        qo.track_query("tiny-threshold", lambda: "v")
        assert qo._slow_query_log[-1]["slow"] is True

    def test_high_threshold_marks_not_slow(self, monkeypatch):
        qo = self._qo
        monkeypatch.setattr(settings, "SLOW_QUERY_THRESHOLD_MS", 100000.0)
        qo.track_query("huge-threshold", lambda: "v")
        assert qo._slow_query_log[-1]["slow"] is False

    def test_explicit_threshold_still_overrides_settings(self, monkeypatch):
        qo = self._qo
        monkeypatch.setattr(settings, "SLOW_QUERY_THRESHOLD_MS", 100000.0)
        qo.track_query("override", lambda: "v", threshold_ms=0.0)
        assert qo._slow_query_log[-1]["slow"] is True

    def test_no_module_level_threshold_constant(self):
        qo = self._qo
        # 旧硬编码模块变量已移除，改为读 settings
        assert not hasattr(qo, "_slow_threshold_ms")
