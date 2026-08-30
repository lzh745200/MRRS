"""Redis adapter — stub (Redis is optional in offline deployment)."""
import logging

logger = logging.getLogger(__name__)


class RedisAdapter:
    """No-op Redis adapter for offline/single-machine deployments."""

    def __init__(self):
        self._data = {}

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value, ttl: int = None):
        self._data[key] = value
        return True

    def delete(self, key: str):
        self._data.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        return key in self._data

    def flush(self):
        self._data.clear()

    def get_stats(self) -> dict:
        """缓存统计（离线内存适配器：返回键规模等基础指标）"""
        return {
            "type": "memory",
            "keys": len(self._data),
            "hit_ratio": None,  # 内存适配器不统计命中
        }

    def health_check(self) -> dict:
        """健康状态（离线内存适配器恒可用）"""
        return {"status": "healthy", "backend": "memory"}


redis_adapter = RedisAdapter()
