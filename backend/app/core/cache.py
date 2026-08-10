"""Cache with async-compatible API."""
import asyncio
import functools
import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SimpleCache:
    """Thread-safe in-memory cache with per-key TTL."""

    def __init__(self, max_size: int = 10_000):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if expires_at > 0 and time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        with self._lock:
            self._evict_if_needed()
            expires_at = time.monotonic() + ttl if ttl > 0 else 0
            self._store[key] = (expires_at, value)

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
):
    """Decorator for sync/async functions, defaults to global cache."""
    instance = cache_instance if cache_instance is not None else default_cache
    _key_fn = key_builder or make_key

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def _aw(*args, **kwargs):
                ck = _key_fn(*args, **kwargs) if _key_fn else f"{func.__name__}:{args}:{kwargs}"
                cv = instance.get(ck)
                if cv is not None:
                    return cv
                r = await func(*args, **kwargs)
                instance.set(ck, r, ttl=ttl)
                return r
            return _aw

        @functools.wraps(func)
        def _sw(*args, **kwargs):
            ck = _key_fn(*args, **kwargs) if _key_fn else f"{func.__name__}:{args}:{kwargs}"
            cv = instance.get(ck)
            if cv is not None:
                return cv
            r = func(*args, **kwargs)
            instance.set(ck, r, ttl=ttl)
            return r
        return _sw

    return decorator


default_cache = SimpleCache()
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
