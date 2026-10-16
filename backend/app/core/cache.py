"""Cache with async-compatible API."""
import asyncio
import functools
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


class SimpleCache:
    """Thread-safe in-memory cache with per-key TTL and LRU eviction.

    容量淘汰为真 LRU（OrderedDict + move_to_end）：命中与覆盖写都会把键移到
    队尾，容量满时淘汰队首（最久未使用）。旧实现淘汰"最早写入"（FIFO），
    热点键会被一次性冷键按写入顺序挤掉（R28 低危项）。

    ``cache_none``：True 时被缓存的结果可以是 None，由 ``get_entry`` 以
    ``(hit, value)`` 区分"缓存了 None"与"未命中"；``get`` 仍返回 None，
    对既有调用方完全兼容。默认 False 保持历史语义（None 视作未命中重算，
    ``cached`` 装饰器不会把 None 当作可复用结果）。
    """

    def __init__(self, max_size: int = 10_000, cache_none: bool = False):
        self._store: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self.cache_none = cache_none
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> Optional[Any]:
        """命中（且未过期）时返回缓存值，否则 None。

        注意：缓存值本身为 None 时返回的也是 None——需要区分两种情况请用
        ``get_entry``（``cache_none=True`` 语义）。
        """
        hit, value = self.get_entry(key)
        return value if hit else None

    def get_entry(self, key: str) -> Tuple[bool, Any]:
        """返回 ``(hit, value)``：hit=True 表示键存在且未过期（值可能为 None）。"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return False, None
            expires_at, value = entry
            if expires_at > 0 and time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return False, None
            self._hits += 1
            self._store.move_to_end(key)  # LRU：命中即刷新最近使用顺序
            return True, value

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        with self._lock:
            self._evict_if_needed()
            expires_at = time.monotonic() + ttl if ttl > 0 else 0
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_by_prefix(self, prefix: str) -> int:
        """Delete all keys starting with *prefix*. Returns count deleted."""
        with self._lock:
            keys_to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
            return len(keys_to_delete)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def close(self) -> None:
        pass

    def _evict_if_needed(self) -> None:
        """容量满时淘汰最久未使用项（LRU 队首）；空库时退出，避免死循环。"""
        while len(self._store) >= self._max_size:
            try:
                oldest = next(iter(self._store))
                del self._store[oldest]
            except StopIteration:
                break


class CacheManager:
    """Async wrapper enabling `await cache_manager.get(key)` syntax."""

    def __init__(self, backend: SimpleCache):
        self._b = backend

    async def get(self, key: str) -> Optional[Any]:
        return self._b.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._b.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        self._b.delete(key)

    async def delete_by_prefix(self, prefix: str) -> int:
        """Delete all keys starting with *prefix*. Returns count deleted."""
        return self._b.delete_by_prefix(prefix)

    async def clear(self) -> None:
        self._b.clear()

    def close(self) -> None:
        self._b.close()


def cached(
    cache_instance: Optional[SimpleCache] = None,
    ttl: int = 3600,
    key_builder: Optional[Callable[..., str]] = None,
    make_key: Optional[Callable[..., str]] = None,
    cache_none: Optional[bool] = None,
):
    """Decorator for sync/async functions, defaults to global cache.

    Args:
        cache_none: None（默认）沿用缓存实例的 ``cache_none`` 设置；显式传
            True/False 可覆盖。True 时被装饰函数返回的 None 也会被复用
            （经 ``SimpleCache.get_entry`` 判定命中）；False 保持历史语义
            ——None 视作未命中，每次重算。
    """
    instance = cache_instance if cache_instance is not None else default_cache
    _key_fn = key_builder or make_key
    _use_none = getattr(instance, "cache_none", False) if cache_none is None else cache_none

    def _lookup(ck: str) -> Tuple[bool, Any]:
        if _use_none:
            return instance.get_entry(ck)
        value = instance.get(ck)
        return value is not None, value

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def _aw(*args, **kwargs):
                ck = _key_fn(*args, **kwargs) if _key_fn else f"{func.__name__}:{args}:{kwargs}"
                hit, cv = _lookup(ck)
                if hit:
                    return cv
                r = await func(*args, **kwargs)
                instance.set(ck, r, ttl=ttl)
                return r
            return _aw

        @functools.wraps(func)
        def _sw(*args, **kwargs):
            ck = _key_fn(*args, **kwargs) if _key_fn else f"{func.__name__}:{args}:{kwargs}"
            hit, cv = _lookup(ck)
            if hit:
                return cv
            r = func(*args, **kwargs)
            instance.set(ck, r, ttl=ttl)
            return r
        return _sw

    return decorator


default_cache = SimpleCache(max_size=settings.CACHE_MAX_SIZE)
cache_manager = CacheManager(default_cache)
cache = cache_manager


async def get_cache_service():
    """Return the async-compatible cache manager."""
    return cache_manager


cache_result = cached


# Backward-compat: CacheManager._cache property
# Backward-compat _cache property with getter/setter
_compat_cache_attr = "_cache_data"
if not hasattr(CacheManager, "_cache") or isinstance(getattr(CacheManager, "_cache", None), property):
    @property
    def _cache(self):
        if not hasattr(self, "_cache_data"):
            object.__setattr__(self, "_cache_data", {})
        return object.__getattribute__(self, "_cache_data")

    @_cache.setter
    def _cache(self, value):
        object.__setattr__(self, "_cache_data", value)

    @_cache.deleter
    def _cache(self):
        object.__setattr__(self, "_cache_data", {})
    CacheManager._cache = _cache
