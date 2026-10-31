"""app.api.v1.system.cache 覆盖率攻坚测试

直接 async 调用端点函数，覆盖缓存统计与清除两个端点的正常/异常分支。
缓存后端用真实的 SimpleCache 实例（经 patch.object 替换模块别名，自动还原），
不 mock 被测逻辑本身。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.system.cache as m
from app.core.cache import CacheManager, SimpleCache

ADMIN = SimpleNamespace(is_superuser=True, role="super_admin", username="admin1")
NORMAL = SimpleNamespace(is_superuser=False, role="user", username="bob")


class TestGetCacheStats:
    async def test_stats_with_items_and_hits(self):
        backend = SimpleCache()
        backend.set("alpha", "v1")
        backend.set("beta", {"nested": 1})
        backend._hits = 3
        backend._misses = 1
        with patch.object(m, "default_cache", backend):
            result = await m.get_cache_stats(current_user=MagicMock())
        assert result["success"] is True
        data = result["data"]
        assert data["item_count"] == 2
        assert data["max_size"] == backend._max_size
        assert data["hits"] == 3
        assert data["misses"] == 1
        assert data["total_requests"] == 4
        assert data["hit_rate"] == 75.0
        assert data["estimated_size_bytes"] > 0
        assert data["estimated_size_mb"] == round(data["estimated_size_bytes"] / 1024 / 1024, 2)
        assert data["backend_type"] == "memory"

    async def test_empty_cache_zero_hit_rate(self):
        backend = SimpleCache()
        with patch.object(m, "default_cache", backend):
            result = await m.get_cache_stats(current_user=MagicMock())
        data = result["data"]
        assert data["item_count"] == 0
        assert data["total_requests"] == 0
        assert data["hit_rate"] == 0.0
        assert data["estimated_size_bytes"] == 0

    async def test_backend_error_becomes_500(self):
        with patch.object(m, "default_cache", object()):
            with pytest.raises(HTTPException) as exc_info:
                await m.get_cache_stats(current_user=MagicMock())
        assert exc_info.value.status_code == 500
        assert "获取缓存统计失败" in exc_info.value.detail


class TestClearCache:
    async def test_non_admin_forbidden(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.clear_cache(db=MagicMock(), current_user=NORMAL)
        assert exc_info.value.status_code == 403
        # SEC-2（2026-10-31）：清缓存由 require_admin 把关（部门级 admin 可执行），
        # 原文案「仅超级管理员可清除缓存」与实现不符，已改为「需要管理员权限」。
        assert "需要管理员权限" in exc_info.value.detail

    async def test_admin_clears_and_resets_counters(self):
        backend = SimpleCache()
        backend.set("k1", "v1")
        backend.set("k2", "v2")
        backend._hits = 7
        backend._misses = 2
        manager = CacheManager(backend)
        with patch.object(m, "default_cache", backend), patch.object(m, "cache_manager", manager):
            result = await m.clear_cache(db=MagicMock(), current_user=ADMIN)
        assert result["success"] is True
        assert result["data"]["cleared_keys"] == 2
        assert result["data"]["timestamp"] > 0
        assert "2" in result["message"]
        # 缓存确实被清空、计数器被重置
        assert len(backend._store) == 0
        assert backend._hits == 0
        assert backend._misses == 0

    async def test_clear_failure_becomes_500(self):
        backend = SimpleCache()
        manager = CacheManager(backend)
        manager.clear = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(m, "default_cache", backend), patch.object(m, "cache_manager", manager):
            with pytest.raises(HTTPException) as exc_info:
                await m.clear_cache(db=MagicMock(), current_user=ADMIN)
        assert exc_info.value.status_code == 500
        assert "清除缓存失败" in exc_info.value.detail
