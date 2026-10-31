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

    def test_degraded_helpers_are_noops(self, monkeypatch):
        """缓存降级后读/写/清都必须静默跳过（端点照常直查），且不再尝试初始化。"""
        import app.api.v1.data.data.dashboard as dash_mod

        monkeypatch.setattr(dash_mod, "_cache", None)
        monkeypatch.setattr(dash_mod, "_cache_initialized", True)
        assert dash_mod._get_cached("dashboard:summary") is None
        dash_mod._set_cached("dashboard:summary", {"stats": {}})
        dash_mod.invalidate_dashboard_cache()


class TestDashboardCacheLazyInit:
    """缓存必须懒初始化：导入期不做任何磁盘 I/O，失败也只尝试一次。

    2026-10-31 打包实测：模块导入期构造 diskcache 时若缓存目录不可写，
    diskcache 的 _execute_with_retry 会长时间重试 → 后端进程活着但 8000 端口
    永不监听。改成首次访问才初始化后，启动链路与缓存可用性彻底解耦。
    """

    def test_lazy_init_runs_once(self, monkeypatch):
        import app.api.v1.data.data.dashboard as dash_mod

        sentinel = object()
        calls = []

        def fake_init():
            calls.append(1)
            return sentinel, 120

        monkeypatch.setattr(dash_mod, "_cache", None)
        monkeypatch.setattr(dash_mod, "_CACHE_TTL", 0)
        monkeypatch.setattr(dash_mod, "_cache_initialized", False)
        monkeypatch.setattr(dash_mod, "_init_cache", fake_init)

        assert dash_mod._get_cache() is sentinel
        assert dash_mod._get_cache() is sentinel
        assert len(calls) == 1
        assert dash_mod._CACHE_TTL == 120

    def test_failure_is_not_retried(self, monkeypatch):
        import app.api.v1.data.data.dashboard as dash_mod

        calls = []

        def fake_init():
            calls.append(1)
            return None, 0

        monkeypatch.setattr(dash_mod, "_cache", None)
        monkeypatch.setattr(dash_mod, "_cache_initialized", False)
        monkeypatch.setattr(dash_mod, "_init_cache", fake_init)

        assert dash_mod._get_cache() is None
        assert dash_mod._get_cache() is None
        assert len(calls) == 1

    def test_helpers_read_write_clear_through_cache(self, monkeypatch):
        import app.api.v1.data.data.dashboard as dash_mod

        class FakeCache:
            def __init__(self):
                self.data = {}
                self.expire = {}

            def get(self, key):
                return self.data.get(key)

            def set(self, key, value, expire=None):
                self.data[key] = value
                self.expire[key] = expire

            def clear(self):
                self.data.clear()

        fake = FakeCache()
        monkeypatch.setattr(dash_mod, "_cache", fake)
        monkeypatch.setattr(dash_mod, "_CACHE_TTL", 120)
        monkeypatch.setattr(dash_mod, "_cache_initialized", True)

        dash_mod._set_cached("k", {"a": 1})
        assert dash_mod._get_cached("k") == {"a": 1}
        assert fake.expire["k"] == 120
        dash_mod._set_cached("k2", {"b": 2}, ttl=30)
        assert fake.expire["k2"] == 30
        dash_mod.invalidate_dashboard_cache()
        assert fake.data == {}

    def test_helper_errors_are_swallowed(self, monkeypatch):
        import app.api.v1.data.data.dashboard as dash_mod

        class BadCache:
            def get(self, key):
                raise RuntimeError("read failed")

            def set(self, key, value, expire=None):
                raise RuntimeError("write failed")

            def clear(self):
                raise RuntimeError("clear failed")

        monkeypatch.setattr(dash_mod, "_cache", BadCache())
        monkeypatch.setattr(dash_mod, "_cache_initialized", True)

        assert dash_mod._get_cached("k") is None
        dash_mod._set_cached("k", 1)
        dash_mod.invalidate_dashboard_cache()
