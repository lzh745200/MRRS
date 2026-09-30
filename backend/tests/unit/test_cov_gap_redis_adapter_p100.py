"""app.core.redis_adapter 缺口补口（.coveragerc fail_under=100）。

缺失行：36-37 —— RedisAdapter.clear()：先 flush() 再显式 return True。
/performance/cache/clear 以返回值判定成败，flush() 返回 None 会让该端点恒 500
（深审 critical），故这里锁定"有返回值且缓存确实被清空"的契约。
"""

from app.core.redis_adapter import RedisAdapter


class TestRedisAdapterClear:
    def test_clear_flushes_and_reports_success(self):
        r = RedisAdapter()
        r.set("a", 1)
        r.set("b", 2)

        assert r.clear() is True          # 显式成功返回值（不是 None）
        assert r._data == {}              # 与 flush() 同语义：真的清空
        assert r.get("a") is None
        assert r.exists("b") is False

    def test_clear_on_empty_adapter_is_idempotent(self):
        r = RedisAdapter()
        assert r.clear() is True
        assert r.clear() is True
        assert r.get_stats() == {"type": "memory", "keys": 0, "hit_ratio": None}

    def test_health_check_reports_memory_backend(self):
        """离线内存适配器恒可用（/health 的缓存探针据此判定）。"""
        r = RedisAdapter()
        assert r.health_check() == {"status": "healthy", "backend": "memory"}
