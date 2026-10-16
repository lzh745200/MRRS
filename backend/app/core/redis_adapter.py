"""Redis adapter — Redis is optional in offline deployment.

R28 低危项（R27 排查）：
- 进程内内存字典原无锁：FastAPI 线程池 / 后台任务并发读写同一 dict 存在竞态
  （CPython 单次操作原子不等于"读改写"原子）→ 全部内存分支加 ``threading.Lock``。
- ``settings.REDIS_ENABLED`` 原零消费（字段定义了但从未被读取）→ 现决定是否
  尝试连接真实 Redis。离线单机部署（默认 False）行为不变，仍为进程内实现；
  REDIS_ENABLED=true 但客户端未安装或连接失败时**安全降级**进程内实现并
  ``logger.warning``，绝不因缓存后端不可用阻断业务（不新增第三方依赖，
  ``redis`` 仅按需 import）。
"""

import logging
import threading

logger = logging.getLogger(__name__)


def _redis_enabled() -> bool:
    """读取 settings.REDIS_ENABLED（运行时求值，便于测试与热切换）。"""
    from app.core.config import settings

    return bool(getattr(settings, "REDIS_ENABLED", False))


class RedisAdapter:
    """Redis 适配器：可用时走真实 Redis，否则为进程内内存实现（离线契约）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}
        self._client = self._try_connect()

    @staticmethod
    def _try_connect():
        """按 REDIS_ENABLED 尝试构建可用客户端；不可用时返回 None（降级内存）。"""
        if not _redis_enabled():
            return None
        try:
            import redis  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("REDIS_ENABLED=true 但未安装 redis 客户端，降级为进程内内存实现")
            return None
        from app.core.config import settings

        try:
            client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "localhost"),
                port=int(getattr(settings, "REDIS_PORT", 6379)),
                db=int(getattr(settings, "REDIS_DB", 0)),
                password=getattr(settings, "REDIS_PASSWORD", None),
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
        except Exception as e:
            logger.warning("连接 Redis 失败，降级为进程内内存实现: %s", e)
            return None
        logger.info("Redis 适配器已连接真实 Redis 服务")
        return client

    # ── 基础读写 ──

    def get(self, key: str):
        if self._client is not None:
            return self._client.get(key)
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value, ttl: int = None):
        if self._client is not None:
            if ttl:
                self._client.set(key, value, ex=ttl)
            else:
                self._client.set(key, value)
            return True
        with self._lock:
            self._data[key] = value
        return True

    def delete(self, key: str):
        if self._client is not None:
            self._client.delete(key)
            return True
        with self._lock:
            self._data.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        if self._client is not None:
            return bool(self._client.exists(key))
        with self._lock:
            return key in self._data

    def flush(self):
        if self._client is not None:
            self._client.flushdb()
            return
        with self._lock:
            self._data.clear()

    def clear(self) -> bool:
        """清空缓存并显式报告成功。

        /performance/cache/clear 以返回值判定成败；flush() 历史上返回 None
        会让该端点恒 500（深审 critical），故提供带返回值的 clear()。
        """
        self.flush()
        return True

    def get_stats(self) -> dict:
        """缓存统计（Redis 后端返回 key 规模；内存后端返回键数）。"""
        if self._client is not None:
            try:
                keys = int(self._client.dbsize())
            except Exception as e:
                logger.warning("读取 Redis key 数量失败: %s", e)
                keys = 0
            return {
                "type": "redis",
                "keys": keys,
                "hit_ratio": None,  # 未启用 Redis 命中统计
            }
        with self._lock:
            keys = len(self._data)
        return {
            "type": "memory",
            "keys": keys,
            "hit_ratio": None,  # 内存适配器不统计命中
        }

    def health_check(self) -> dict:
        """健康状态：Redis 后端 ping 失败即报 unhealthy（供 /performance 观测）。"""
        if self._client is not None:
            try:
                ok = bool(self._client.ping())
            except Exception as e:
                logger.warning("Redis ping 失败: %s", e)
                ok = False
            return {
                "status": "healthy" if ok else "unhealthy",
                "backend": "redis",
            }
        return {"status": "healthy", "backend": "memory"}


redis_adapter = RedisAdapter()
