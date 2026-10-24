# -*- coding: utf-8 -*-
"""R36 · 时钟漂移检查的 TTL 缓存与 /health 载荷形状（`app/startup/preflight.py`）

`/health` 会被 Electron/监控高频轮询，若每次都跑一次 "最近审计时间" 查询，
等于给热路径加一条 DB 查询。``clock_health()`` 因此带 TTL 缓存：
- 首次调用执行真实检查并缓存；
- TTL 内重复调用直接返回缓存（不查库）；
- TTL 过期后重新检查（长跑机器上的时钟漂移才能被发现）；
- 返回值固定为 ``{status, behind_days}``（不把 reason/异常原文带到无认证端点）。
"""
from unittest.mock import patch

import pytest

from app.startup import preflight


@pytest.fixture(autouse=True)
def _reset_cache():
    preflight._clock_cache.clear()
    preflight._clock_cache_at = None
    yield
    preflight._clock_cache.clear()
    preflight._clock_cache_at = None


class TestClockHealthCache:
    def test_first_call_checks_and_caches(self):
        with patch.object(
            preflight,
            "_check_clock_drift",
            return_value={"status": "ok", "behind_days": 0.2},
        ) as check:
            first = preflight.clock_health()
            second = preflight.clock_health()

        assert first == {"status": "ok", "behind_days": 0.2}
        assert second == first
        check.assert_called_once()  # TTL 内不重复查库

    def test_rechecks_after_ttl_expiry(self):
        with patch.object(
            preflight, "_check_clock_drift", return_value={"status": "ok", "behind_days": 0.0}
        ), patch.object(preflight.time, "monotonic", return_value=1000.0), patch.object(
            preflight, "_check_clock_drift", return_value={"status": "ok", "behind_days": 0.0}
        ) as check:
            preflight.clock_health()
            # 超过 TTL（默认 120s）
            with patch.object(preflight.time, "monotonic", return_value=1000.0 + 121):
                preflight.clock_health()

        assert check.call_count == 2

    def test_warning_shape_passthrough(self):
        with patch.object(
            preflight,
            "_check_clock_drift",
            return_value={
                "status": "warning",
                "reason": "system_clock_behind_data",
                "behind_days": 5.5,
            },
        ):
            payload = preflight.clock_health()

        assert payload == {"status": "warning", "behind_days": 5.5}
        assert "reason" not in payload  # 无认证端点只出二元组

    def test_unknown_shape_has_none_behind_days(self):
        with patch.object(
            preflight,
            "_check_clock_drift",
            return_value={"status": "unknown", "error_type": "OperationalError"},
        ):
            payload = preflight.clock_health()

        assert payload == {"status": "unknown", "behind_days": None}

    def test_explicit_max_age_zero_forces_recheck(self):
        with patch.object(
            preflight, "_check_clock_drift", return_value={"status": "ok", "behind_days": 0.0}
        ) as check:
            preflight.clock_health()
            preflight.clock_health(max_age_seconds=0)

        assert check.call_count == 2


class TestClockDriftDetection:
    """真实判定分支（不只走 mock 的 clock_health 缓存层）。"""

    def test_behind_data_returns_warning(self):
        from datetime import datetime, timedelta, timezone

        future = datetime.now(timezone.utc) + timedelta(days=3)
        with patch.object(preflight, "_latest_audit_time", return_value=future):
            result = preflight._check_clock_drift()

        assert result["status"] == "warning"
        assert result["reason"] == "system_clock_behind_data"
        assert result["behind_days"] >= 3.0

    def test_naive_timestamp_treated_as_utc_and_ok(self):
        from datetime import datetime, timedelta

        recent = datetime.utcnow() - timedelta(hours=1)  # naive：按 UTC 解释
        with patch.object(preflight, "_latest_audit_time", return_value=recent):
            result = preflight._check_clock_drift()

        assert result["status"] == "ok"
        assert result["behind_days"] == 0.0


class TestPreflightContractUnchanged:
    def test_run_preflight_checks_still_includes_clock_and_only_warns(self):
        with patch.object(
            preflight,
            "_check_clock_drift",
            return_value={"status": "warning", "behind_days": 9.0},
        ), patch.object(
            preflight, "_check_disk_free", return_value={"status": "ok"}
        ), patch.object(
            preflight, "_check_db_writable", return_value={"status": "ok"}
        ), patch.object(
            preflight, "_check_encryption_key", return_value={"status": "ok"}
        ):
            results = preflight.run_preflight_checks()  # 只告警，不抛错

        assert results["clock"]["status"] == "warning"
        assert set(results) == {"disk", "database_writable", "clock", "encryption_key"}

    def test_clock_check_never_raises_on_db_failure(self):
        with patch.object(
            preflight, "_latest_audit_time", side_effect=RuntimeError("db down")
        ):
            result = preflight._check_clock_drift()

        assert result["status"] == "unknown"
        assert result["error_type"] == "RuntimeError"

    def test_clock_check_no_data_is_ok(self):
        with patch.object(preflight, "_latest_audit_time", return_value=None):
            result = preflight._check_clock_drift()

        assert result == {"status": "ok", "reason": "no_data"}
