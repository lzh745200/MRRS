"""app.core.redis_adapter 的 Redis 连通分支覆盖（R28 重写后新增路径）。

R28 给 RedisAdapter 加了"REDIS_ENABLED=true 时接真实 Redis、不可用则安全降级
进程内内存实现"的分支，但原有用例（test_redis_adapter.py /
test_cov_gap_redis_adapter_p100.py）只走内存实现，导致 _try_connect 的
Redis 路径与 get / set / delete / exists / flush / get_stats / health_check
的 client 分支全部未被覆盖。

本文件用**假 redis 模块**补齐这些分支：不引入 redis 依赖、不发起真实连接，
同时锁定"连接失败绝不阻断业务"的降级契约。
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from app.core import redis_adapter as ra
from app.core.redis_adapter import RedisAdapter, _redis_enabled


def _fake_redis_module(client):
    """构造假 redis 模块（redis.Redis(...) 固定返回给定 client）。"""
    module = types.ModuleType("redis")
    module.Redis = MagicMock(return_value=client)
    return module


@pytest.fixture
def redis_backed():
    """已"连上"Redis 的适配器（client 为 MagicMock，不发真实网络请求）。"""
    with patch.object(ra, "_redis_enabled", return_value=False):
        adapter = RedisAdapter()
    adapter._client = MagicMock()
    return adapter


class TestRedisEnabledFlag:
    def test_reads_true_from_settings(self):
        settings = MagicMock()
        settings.REDIS_ENABLED = True
        with patch("app.core.config.settings", settings):
            assert _redis_enabled() is True

    def test_defaults_to_false_when_attr_absent(self):
        class _Bare:
            pass

        with patch("app.core.config.settings", _Bare()):
            assert _redis_enabled() is False


class TestTryConnect:
    def test_disabled_returns_none(self):
        """REDIS_ENABLED=false（离线单机默认）→ 直接用内存实现。"""
        with patch.object(ra, "_redis_enabled", return_value=False):
            assert RedisAdapter._try_connect() is None

    def test_client_not_installed_falls_back_to_memory(self):
        """REDIS_ENABLED=true 但未安装 redis 客户端 → 降级内存，不阻断业务。"""
        with patch.object(ra, "_redis_enabled", return_value=True), \
                patch.dict(sys.modules, {"redis": None}):
            assert RedisAdapter._try_connect() is None

    def test_connect_success_returns_client(self):
        client = MagicMock()
        client.ping.return_value = True
        module = _fake_redis_module(client)
        with patch.object(ra, "_redis_enabled", return_value=True), \
                patch.dict(sys.modules, {"redis": module}):
            assert RedisAdapter._try_connect() is client
        module.Redis.assert_called_once()
        kwargs = module.Redis.call_args.kwargs
        assert kwargs["socket_connect_timeout"] == 2
        assert kwargs["socket_timeout"] == 2

    def test_ping_failure_falls_back_to_memory(self):
        client = MagicMock()
        client.ping.side_effect = RuntimeError("connection refused")
        module = _fake_redis_module(client)
        with patch.object(ra, "_redis_enabled", return_value=True), \
                patch.dict(sys.modules, {"redis": module}):
            assert RedisAdapter._try_connect() is None


class TestClientBackedReadWrite:
    def test_get_delegates_to_client(self, redis_backed):
        redis_backed._client.get.return_value = "v"
        assert redis_backed.get("k") == "v"
        redis_backed._client.get.assert_called_once_with("k")

    def test_set_with_ttl_uses_ex(self, redis_backed):
        assert redis_backed.set("k", "v", ttl=30) is True
        redis_backed._client.set.assert_called_once_with("k", "v", ex=30)

    def test_set_without_ttl(self, redis_backed):
        assert redis_backed.set("k", "v") is True
        redis_backed._client.set.assert_called_once_with("k", "v")

    def test_delete_delegates(self, redis_backed):
        assert redis_backed.delete("k") is True
        redis_backed._client.delete.assert_called_once_with("k")

    def test_exists_returns_bool(self, redis_backed):
        redis_backed._client.exists.return_value = 1
        assert redis_backed.exists("k") is True
        redis_backed._client.exists.return_value = 0
        assert redis_backed.exists("k") is False

    def test_flush_delegates(self, redis_backed):
        assert redis_backed.flush() is None
        redis_backed._client.flushdb.assert_called_once()

    def test_clear_reports_success_on_redis_backend(self, redis_backed):
        """clear() 在 Redis 后端同样必须显式返回 True（否则端点恒 500）。"""
        assert redis_backed.clear() is True
        redis_backed._client.flushdb.assert_called_once()


class TestClientBackedStats:
    def test_get_stats_reports_redis_keys(self, redis_backed):
        redis_backed._client.dbsize.return_value = 7
        assert redis_backed.get_stats() == {"type": "redis", "keys": 7, "hit_ratio": None}

    def test_get_stats_swallows_dbsize_error(self, redis_backed):
        """dbsize 失败不能让 /performance 观测端点 500，退化为 0。"""
        redis_backed._client.dbsize.side_effect = RuntimeError("down")
        assert redis_backed.get_stats() == {"type": "redis", "keys": 0, "hit_ratio": None}

    def test_health_check_healthy_when_ping_ok(self, redis_backed):
        redis_backed._client.ping.return_value = True
        assert redis_backed.health_check() == {"status": "healthy", "backend": "redis"}

    def test_health_check_unhealthy_when_ping_fails(self, redis_backed):
        redis_backed._client.ping.side_effect = RuntimeError("down")
        assert redis_backed.health_check() == {"status": "unhealthy", "backend": "redis"}
