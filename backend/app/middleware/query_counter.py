"""
SQL 查询计数中间件

用于监控每个请求的 SQL 查询数量，
帮助识别 N+1 查询问题。
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# 查询计数阈值（超过此值记录警告）
QUERY_COUNT_WARNING_THRESHOLD = 50


class QueryCounterMiddleware(BaseHTTPMiddleware):
    """
    SQL 查询计数中间件。

    在每个请求结束后记录 SQL 查询数量。
    当查询数超过阈值时发出警告日志。
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # 初始化查询计数器（挂在 request.state 上）
        request.state.query_count = 0

        response = await call_next(request)

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

    在 SQLAlchemy 的 after_cursor_execute 事件中调用。
    """
    if hasattr(request, "state") and hasattr(request.state, "query_count"):
        request.state.query_count += 1
