"""
SQL 查询计数中间件

用于监控每个请求的 SQL 查询数量，
帮助识别 N+1 查询问题。

计数链路：SQLAlchemy after_cursor_execute 事件 → contextvar 计数器 →
中间件结束时写入 request.state → X-Query-Count 响应头 + 超阈值告警。
"""
import contextvars
import logging
import time
from typing import Callable, List, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# 查询计数阈值（超过此值记录警告）
QUERY_COUNT_WARNING_THRESHOLD = 50

# 当前请求的查询计数器（SQLAlchemy 事件无 Request 上下文，用 contextvar 桥接）
_query_counter_ctx: contextvars.ContextVar[Optional[List[int]]] = contextvars.ContextVar(
    "query_counter", default=None
)


def _on_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
) -> None:
    """SQLAlchemy after_cursor_execute 事件：递增当前请求的查询计数（含 N+1 检测数据源）。"""
    counter = _query_counter_ctx.get()
    if counter is not None:
        counter[0] += 1


class QueryCounterMiddleware(BaseHTTPMiddleware):
    """
    SQL 查询计数中间件。

    在每个请求结束后记录 SQL 查询数量。
    当查询数超过阈值时发出警告日志。
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # 初始化查询计数器（挂在 request.state 上 + contextvar 供 SQLAlchemy 事件写入）
        request.state.query_count = 0
        counter: List[int] = [0]
        token = _query_counter_ctx.set(counter)
        try:
            response = await call_next(request)
        finally:
            # 合并事件计数（SQL 查询）与显式递增（兼容旧调用方），写回 request.state
            request.state.query_count = getattr(request.state, "query_count", 0) + counter[0]
            _query_counter_ctx.reset(token)

        # 计算耗时
        duration_ms = (time.time() - start_time) * 1000
        query_count = getattr(request.state, "query_count", 0)

        # 将查询计数添加到响应头
        response.headers["X-Query-Count"] = str(query_count)
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        # 超过阈值则记录警告
        if query_count > QUERY_COUNT_WARNING_THRESHOLD:
            logger.warning(
                f"慢查询警告: {request.method} {request.url.path} "
                f"执行了 {query_count} 条 SQL 查询 "
                f"(耗时 {duration_ms:.1f}ms)"
            )

        return response


def increment_query_count(request: Request) -> None:
    """
    增加查询计数器。

    在 SQLAlchemy 的 after_cursor_execute 事件中调用（兼容旧接口）。
    """
    if hasattr(request, "state") and hasattr(request.state, "query_count"):
        request.state.query_count += 1
