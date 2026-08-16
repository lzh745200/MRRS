"""
缓存服务模块
提供智能缓存策略、缓存失效、缓存预热等功能
"""

import hashlib
import inspect
import json
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from app.core.cache import cache_manager
from app.core.config import settings
from app.core.transaction import safe_commit  # noqa: F401

logger = logging.getLogger(__name__)


class CacheStrategy:
    """缓存策略"""

    # 缓存时间（秒）
    SHORT = 60  # 1分钟
    MEDIUM = 300  # 5分钟
    LONG = 3600  # 1小时
    VERY_LONG = 86400  # 1天

    # 缓存键前缀
    USER_PREFIX = "user:"
    VILLAGE_PREFIX = "village:"
    DATA_PREFIX = "data:"
    API_PREFIX = "api:"
    STATS_PREFIX = "stats:"


class CacheService:
    """缓存服务类"""

    def __init__(self):
        self.cache_manager = cache_manager
        self.cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在返回None
        """
        try:
            value = await self.cache_manager.get(key)
            if value is not None:
                self.cache_stats["hits"] += 1
                logger.debug(f"Cache hit: {key}")
            else:
                self.cache_stats["misses"] += 1
                logger.debug(f"Cache miss: {key}")
            return value
        except Exception as e:
            logger.error(f"Error getting cache: {e}")
            self.cache_stats["misses"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认使用配置的默认值

        Returns:
            是否设置成功
        """
        try:
            if ttl is None:
                ttl = settings.CACHE_DEFAULT_TTL

            await self.cache_manager.set(key, value, ttl=ttl)
            self.cache_stats["sets"] += 1
            logger.debug(f"Cache set: {key}, ttl: {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        try:
            result = await self.cache_manager.delete(key)
            if result:
                self.cache_stats["deletes"] += 1
                logger.debug(f"Cache deleted: {key}")
            return result
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        try:
            value = await self.cache_manager.get(key)
            return value is not None
        except Exception as e:
            logger.error(f"Error checking cache existence: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        清除匹配模式的缓存

        Args:
            pattern: 匹配模式（支持通配符 *）

        Returns:
            清除的缓存数量
        """
        # 注意：diskcache 不支持模式匹配，需要遍历所有键
        # 这里是一个简化实现
        try:
            # 由于 diskcache 不支持模式匹配，这里返回0
            # 实际应用中可能需要维护一个键的索引
            logger.warning(f"Pattern-based cache clearing not fully supported: {pattern}")
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
            return 0

    async def invalidate_related_cache(self, resource_type: str, resource_id: Optional[str] = None) -> int:
        """
        失效相关缓存

        Args:
            resource_type: 资源类型（如 'user', 'village', 'data'）
            resource_id: 资源ID（可选）

        Returns:
            失效的缓存数量
        """
        try:
            count = 0

            # 失效特定资源的缓存
            if resource_id:
                key = f"{resource_type}:{resource_id}"
                if await self.delete(key):
                    count += 1

            # 失效资源列表缓存
            list_key = f"{resource_type}:list"
            if await self.delete(list_key):
                count += 1

            # 失效资源统计缓存
            stats_key = f"{CacheStrategy.STATS_PREFIX}{resource_type}"
            if resource_id:
                stats_key = f"{stats_key}:{resource_id}"
            if await self.delete(stats_key):
                count += 1

            logger.info(f"Invalidated {count} cache entries for {resource_type}")
            return count
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0

    async def warm_up_cache(self, data_loader: Callable[[str], Any], keys: List[str]) -> int:
        """
        缓存预热

        Args:
            data_loader: 数据加载函数
            keys: 要预热的缓存键列表

        Returns:
            预热的缓存数量
        """
        count = 0
        for key in keys:
            try:
                # 检查是否已缓存
                if not await self.exists(key):
                    # 加载数据并缓存
                    value = await data_loader(key)
                    if value is not None:
                        await self.set(key, value)
                        count += 1
            except Exception as e:
                logger.error(f"Error warming up cache for {key}: {e}")

        logger.info(f"Warmed up {count} cache entries")
        return count

    def get_cache_stats(self) -> Dict[str, int]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        return self.cache_stats.copy()

    def reset_cache_stats(self) -> None:
        """重置缓存统计信息"""
        self.cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}


def cache_key(*args, **kwargs) -> str:
    """
    生成缓存键

    Args:
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        缓存键
    """
    # 将参数转换为字符串
    key_parts = []

    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # 对于复杂对象，使用哈希
            key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode(), usedforsecurity=False).hexdigest())

    # 添加关键字参数
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        raw = hashlib.md5(json.dumps(sorted_kwargs, sort_keys=True).encode(), usedforsecurity=False)
        key_parts.append(raw.hexdigest())

    return ":".join(key_parts)


def cached(
    ttl: int = CacheStrategy.MEDIUM,
    key_prefix: Optional[str] = None,
    key_func: Optional[Callable] = None,
):
    """
    缓存装饰器

    Args:
        ttl: 缓存时间（秒）
        key_prefix: 缓存键前缀
        key_func: 自定义缓存键生成函数

    使用方法:
        @cached(ttl=CacheStrategy.LONG, key_prefix="user:")
        async def get_user(user_id: int):
            return db.query(User).filter(User.id == user_id).first()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key_value = key_func(*args, **kwargs)
            else:
                cache_key_value = cache_key(func.__name__, *args, **kwargs)

            if key_prefix:
                cache_key_value = f"{key_prefix}{cache_key_value}"

            # 尝试从缓存获取
            cache_service = CacheService()
            cached_value = await cache_service.get(cache_key_value)

            if cached_value is not None:
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 缓存结果
            if result is not None:
                await cache_service.set(cache_key_value, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def cache_result(ttl: int = CacheStrategy.MEDIUM, key_generator: Optional[Callable] = None):
    """
    结果缓存装饰器（同步版本）

    Args:
        ttl: 缓存时间（秒）
        key_generator: 自定义缓存键生成函数

    使用方法:
        @cache_result(ttl=CacheStrategy.LONG)
        def get_user(user_id: int):
            return db.query(User).filter(User.id == user_id).first()
    """

    def decorator(func: Callable) -> Callable:
        # 在装饰时检查一次，避免每次调用都检查
        _is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_generator:
                cache_key_value = key_generator(*args, **kwargs)
            else:
                cache_key_value = cache_key(func.__name__, *args, **kwargs)

            # 尝试从缓存获取
            cache_service = CacheService()
            cached_value = await cache_service.get(cache_key_value)

            if cached_value is not None:
                return cached_value

            # 执行函数
            if _is_async:
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 缓存结果
            if result is not None:
                await cache_service.set(cache_key_value, result, ttl=ttl)

            return result

        return wrapper

    return decorator


# 缓存失效装饰器
def cache_invalidate(resource_type: str, resource_id_arg: Optional[str] = None):
    """
    缓存失效装饰器

    Args:
        resource_type: 资源类型
        resource_id_arg: 资源ID参数名

    使用方法:
        @cache_invalidate(resource_type="user", resource_id_arg="user_id")
        async def update_user(user_id: int, data: dict):
            user = db.query(User).filter(User.id == user_id).first()
            for key, value in data.items():
                setattr(user, key, value)
            safe_commit(db)
            return user
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 执行函数
            result = await func(*args, **kwargs)

            # 失效缓存
            cache_service = CacheService()
            resource_id = None

            if resource_id_arg:
                resource_id = kwargs.get(resource_id_arg)
                if not resource_id and args:
                    # 尝试从位置参数获取
                    # 这里简化处理，实际需要更复杂的逻辑
                    pass

            await cache_service.invalidate_related_cache(resource_type, resource_id)

            return result

        return wrapper

    return decorator


# 缓存指标记录器
class CacheMetrics:
    """Simple hit/miss counter for cache operations."""

    def __init__(self):
        self.hits = 0
        self.misses = 0

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    def stats(self) -> Dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}


metrics = CacheMetrics()


class EntityCacheManager:
    """泛型实体缓存管理器

    统一替代 ProjectCacheManager / VillageCacheManager /
    SchoolCacheManager / UserCacheManager / StatisticsCacheManager
    中重复的 get_list / get_detail / get_stats / invalidate 模式。

    Usage:
        village_cache = EntityCacheManager("village")
        village_cache.get("stats")               # 同步获取
        village_cache.set("stats", data, ttl=600) # 同步设置
        village_cache.invalidate("stats")         # 删除
    """

    DEFAULT_TTL = 600  # 10 minutes

    def __init__(self, entity: str, ttl: Optional[int] = None):
        self.entity = entity
        self.ttl = ttl or self.DEFAULT_TTL
        self._cache = cache_manager  # CacheManager async wrapper

    def _key(self, suffix: str) -> str:
        return f"{self.entity}:{suffix}"

    def get(self, suffix: str) -> Optional[Any]:
        """Synchronous cache get."""
        key = self._key(suffix)
        value = self._cache._b.get(key)
        if value is not None:
            metrics.record_hit()
        else:
            metrics.record_miss()
        return value

    def set(self, suffix: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Synchronous cache set."""
        return self._cache._b.set(self._key(suffix), value, ttl=ttl or self.ttl)

    def invalidate(self, suffix: str) -> bool:
        """Delete a specific cache entry."""
        return self._cache._b.delete(self._key(suffix))

    def invalidate_all(self) -> None:
        """Invalidate all entries for this entity (list + stats)."""
        for suffix in ("list", "stats", "detail"):
            self._cache._b.delete(self._key(suffix))


# 创建全局缓存服务实例
cache_service = CacheService()
