"""仪表盘缓存初始化失败必须降级为直查，而不是拖垮后端启动。

回归 2026-10-31 打包实测：已存在的 cache.db（含残留 -wal/-shm）使
`diskcache.Cache(...)` 抛 sqlite3.OperationalError（attempt to write a readonly
database / unable to open database file），而 dashboard.py 在 app.api.v1 的导入链上、
原实现只捕 ImportError → 异常穿透后**整个后端启动失败**（8000 端口永不监听）。
"""

import sqlite3
from unittest.mock import patch

import pytest


def _init_with(exc):
    """把 diskcache.Cache 替换成必然抛错，返回降级后的 (cache, ttl)。"""
    import app.api.v1.data.data.dashboard as dash_mod

    with patch("diskcache.Cache", side_effect=exc):
        return dash_mod._init_cache()


class TestDashboardCacheInitDegrade:
    @pytest.mark.parametrize(
        "exc",
        [
            sqlite3.OperationalError("attempt to write a readonly database"),
            sqlite3.OperationalError("unable to open database file"),
            PermissionError("[WinError 5] 拒绝访问。"),
            OSError("disk full"),
        ],
    )
    def test_cache_open_failure_degrades_to_no_cache(self, exc):
        cache, ttl = _init_with(exc)
        assert cache is None
        assert ttl == 0

    def test_cache_dir_create_failure_degrades_to_no_cache(self):
        import app.api.v1.data.data.dashboard as dash_mod

        with patch.object(dash_mod.os, "makedirs", side_effect=PermissionError("denied")):
            cache, ttl = dash_mod._init_cache()
        assert (cache, ttl) == (None, 0)

    def test_success_path_returns_cache_with_ttl(self):
        import app.api.v1.data.data.dashboard as dash_mod

        cache, ttl = dash_mod._init_cache()
        assert cache is not None
        assert ttl == 120

    def test_degraded_helpers_are_noops(self):
        """_cache 为 None 时读/写/清缓存都必须静默跳过（端点照常直查）。"""
        import app.api.v1.data.data.dashboard as dash_mod

        with patch.object(dash_mod, "_cache", None):
            assert dash_mod._get_cached("dashboard:summary") is None
            dash_mod._set_cached("dashboard:summary", {"stats": {}})
            dash_mod.invalidate_dashboard_cache()
