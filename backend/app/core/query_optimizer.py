"""Query optimization helpers.

Provides utilities for building efficient SQLAlchemy queries, monitoring
slow queries, detecting N+1 query patterns, and applying common
optimisations (eager loading, indexing hints, etc.).
"""

import threading as _threading
import functools
import logging
import time
from typing import Any, Callable, List, Optional, Tuple

from sqlalchemy.orm import Query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Eager-loading helpers
# ---------------------------------------------------------------------------


def paginate(
    query: Query,
    page: int = 1,
    page_size: int = 20,
    *,
    max_page_size: int = 200,
) -> Tuple[List[Any], int, int]:
    """Paginate a SQLAlchemy query and return ``(items, total, pages)``.

    Args:
        query: The SQLAlchemy Query object.
        page: 1-indexed page number.
        page_size: Items per page.
        max_page_size: Safety cap on page size.

    Returns:
        A tuple of ``(items, total_count, total_pages)``.
    """
    import math

    page = max(1, page)
    page_size = min(max(page_size, 1), max_page_size)
    total = query.count()
    pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    page = min(page, pages)
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total, pages


# ---------------------------------------------------------------------------
# Slow query monitoring
# ---------------------------------------------------------------------------


_slow_query_log: List[dict] = []
_slow_query_lock = _threading.Lock()
_slow_threshold_ms: float = 200.0


def track_query(
    label: str,
    query_fn: Callable[[], Any],
    *,
    threshold_ms: Optional[float] = None,
) -> Any:
    """Execute a query function and log it if it exceeds the threshold.

    Args:
        label: A short label for the query (e.g. ``"list_users"``).
        query_fn: Zero-argument callable that executes the query.
        threshold_ms: Override the global slow-threshold for this call.

    Returns:
        The return value of *query_fn*.
    """
    start = time.perf_counter()
    result = query_fn()
    elapsed = (time.perf_counter() - start) * 1000

    threshold = threshold_ms if threshold_ms is not None else _slow_threshold_ms
    if threshold > 0 and elapsed > threshold:
        logger.warning("慢查询 %s: %.2f ms (> %.0f ms)", label, elapsed, threshold)
    else:
        logger.debug("查询 %s: %.2f ms", label, elapsed)

    with _slow_query_lock:
        _slow_query_log.append({"label": label, "elapsed_ms": elapsed, "slow": elapsed > threshold})
        if len(_slow_query_log) > 500:
            _slow_query_log[:] = _slow_query_log[-500:]

    return result


def get_slow_queries(limit: int = 50) -> List[dict]:
    """Return recent slow queries (sorted slowest-first).

    Args:
        limit: Maximum entries to return.

    Returns:
        List of dicts with keys ``label``, ``elapsed_ms``, ``slow``.
    """
    with _slow_query_lock:
        return sorted(
            _slow_query_log, key=lambda e: e["elapsed_ms"], reverse=True
        )[:limit]


# ---------------------------------------------------------------------------
# N+1 query detection
# ---------------------------------------------------------------------------

# Thread-local query counter (incremented by the query_counter middleware or
# manually via ``increment_query_count``).

_query_counter = _threading.local()


def _ensure_counter() -> None:
    if not hasattr(_query_counter, "count"):
        _query_counter.count = 0


def get_query_count() -> int:
    """Return the current per-thread query count."""
    _ensure_counter()
    return _query_counter.count


def reset_query_count() -> None:
    """Reset the per-thread query counter to zero."""
    _query_counter.count = 0


def analyze_n_plus_one(threshold: int = 20):
    """Decorator to detect potential N+1 query patterns in service methods.

    Logs a warning when the decorated function executes more than *threshold*
    database queries, which is a strong indicator of N+1 eager-loading
    problems.

    Usage::

        @analyze_n_plus_one(threshold=15)
        def get_village_list(db: Session) -> list[SupportedVillage]:
            ...

    Args:
        threshold: Maximum number of queries before a warning is emitted.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            reset_query_count()
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                query_count = get_query_count()
                if query_count > threshold:
                    logger.warning(
                        "可能的 N+1 查询: %s 执行了 %d 次数据库查询 (阈值 %d), 耗时 %.1fms",
                        func.__qualname__,
                        query_count,
                        threshold,
                        elapsed,
                    )
            return result

        return wrapper

    return decorator
