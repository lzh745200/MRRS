"""P2-4 启动优化：map.py diskcache 缓存惰性初始化单元测试。

改造前：模块导入期即执行 ``os.makedirs(CACHE_DIR)`` + ``diskcache.Cache(...)``
（实测中位 ~130ms，含磁盘 I/O），拖慢 import app.main 冷启动。
改造后：仅保留廉价的模块级 import，真正的 Cache 构造推迟到首次使用
（``_get_map_cache``），且保持线程安全、参数不变。

本文件锁定以下契约：
- ``_get_map_cache``：首次调用构造、二次调用复用同一实例（单例）；
- ``_get_map_cache``：外部已注入 mock / None 时直接沿用，不覆盖；
- ``_build_map_cache``：diskcache 缺失时返回 None（功能降级）；
- ``_clear_map_cache_if_ready``：哨兵 / None 时跳过，就绪时调用 clear；
- 惰性语义：模块导入完成后 ``_map_cache`` 仍为未初始化哨兵（无 import 期磁盘 I/O）。
"""

import importlib
from unittest.mock import MagicMock

import app.api.v1.map as map_mod


class TestGetMapCacheLazy:
    def test_first_call_builds_real_cache(self, monkeypatch):
        """哨兵状态下首次调用触发真实构造，返回可用缓存实例。"""
        monkeypatch.setattr(map_mod, "_map_cache", map_mod._UNSET)
        cache = map_mod._get_map_cache()
        try:
            assert cache is not None
            assert type(cache).__name__ == "Cache"
        finally:
            cache.close()

    def test_second_call_returns_same_instance(self, monkeypatch):
        """第二次调用复用首次构造的实例（单例）。"""
        monkeypatch.setattr(map_mod, "_map_cache", map_mod._UNSET)
        first = map_mod._get_map_cache()
        second = map_mod._get_map_cache()
        try:
            assert first is second
        finally:
            first.close()

    def test_respects_preset_mock(self, monkeypatch):
        """外部已注入 mock 时直接沿用，不触发构造（保证测试可注入）。"""
        mock = MagicMock()
        monkeypatch.setattr(map_mod, "_map_cache", mock)
        assert map_mod._get_map_cache() is mock

    def test_respects_preset_none(self, monkeypatch):
        """外部置为 None（禁用缓存）时直接返回 None，不触发构造。"""
        monkeypatch.setattr(map_mod, "_map_cache", None)
        assert map_mod._get_map_cache() is None

    def test_diskcache_missing_returns_none(self, monkeypatch):
        """diskcache 不可用时 _build_map_cache 返回 None（降级为无缓存）。"""
        monkeypatch.setattr(map_mod, "_dc", None)
        monkeypatch.setattr(map_mod, "_map_cache", map_mod._UNSET)
        assert map_mod._get_map_cache() is None


class TestClearMapCacheIfReady:
    def test_skips_when_unset(self, monkeypatch):
        """未初始化（哨兵）时清空操作应无副作用且不触发构造。"""
        monkeypatch.setattr(map_mod, "_map_cache", map_mod._UNSET)
        map_mod._clear_map_cache_if_ready()
        assert map_mod._map_cache is map_mod._UNSET

    def test_skips_when_none(self, monkeypatch):
        """缓存禁用（None）时清空操作不应抛错。"""
        monkeypatch.setattr(map_mod, "_map_cache", None)
        map_mod._clear_map_cache_if_ready()

    def test_clears_when_ready(self, monkeypatch):
        """缓存就绪时调用 clear 一次。"""
        mock = MagicMock()
        monkeypatch.setattr(map_mod, "_map_cache", mock)
        map_mod._clear_map_cache_if_ready()
        mock.clear.assert_called_once()


class TestLazyImportNoDiskIO:
    def test_import_does_not_build_cache(self):
        """重新导入后 _map_cache 仍为未初始化哨兵——证明 import 期无 Cache 构造。"""
        importlib.reload(map_mod)
        assert map_mod._map_cache is map_mod._UNSET
