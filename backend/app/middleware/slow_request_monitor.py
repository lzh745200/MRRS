"""
慢请求 & 慢 SQL 监控中间件

零侵入：自动记录所有超过阈值的 API 请求和 SQL 查询。
配合 app/core/performance.py 的 @timed 装饰器使用。

Usage（在 main.py 中注册）:
    from app.middleware.slow_request_monitor import SlowRequestMiddleware
    app.add_middleware(SlowRequestMiddleware, slow_api_ms=500, slow_sql_ms=200)
"""

import logging
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List

logger = logging.getLogger("performance.slow")

# ── 环形缓冲区存储最近 N 条慢记录 ──
_MAX_RECORDS = 200
_slow_apis: Deque[Dict[str, Any]] = deque(maxlen=_MAX_RECORDS)
_slow_sqls: Deque[Dict[str, Any]] = deque(maxlen=_MAX_RECORDS)

# ── 计数器 ──
# R12-2：这些计数由并发线程写入 —— total_requests/slow_api_count 来自 ASGI
# 请求线程，slow_sql_count 来自 SQLAlchemy 游标事件。裸 "+=" 是"读-改-写"
# 三步字节码，交错即丢计数（统计口径失真，随并发度线性放大）。统一走互斥自增。
_counters: Dict[str, int] = {
    "total_requests": 0,
    "slow_api_count": 0,
    "slow_sql_count": 0,
}
_counters_lock = threading.Lock()


def _bump(key: str, delta: int = 1) -> None:
    """互斥自增计数器（并发安全）。"""
    with _counters_lock:
        _counters[key] += delta


def get_slow_api_records(limit: int = 50) -> List[Dict[str, Any]]:
    """获取最近慢 API 记录（最新在前）"""
    return list(reversed(_slow_apis))[:limit]


def get_slow_sql_records(limit: int = 50) -> List[Dict[str, Any]]:
    """获取最近慢 SQL 记录（最新在前）"""
    return list(reversed(_slow_sqls))[:limit]


def get_slow_stats() -> Dict[str, Any]:
    """获取性能统计摘要"""
    apis = list(_slow_apis)
    sqls = list(_slow_sqls)
    with _counters_lock:
        counters = dict(_counters)
    return {
        **counters,
        "slow_api_last_50_avg_ms": round(sum(r["elapsed_ms"] for r in apis[-50:]) / max(len(apis[-50:]), 1), 1),
        "slow_sql_last_50_avg_ms": round(sum(r["elapsed_ms"] for r in sqls[-50:]) / max(len(sqls[-50:]), 1), 1),
        "slow_api_peak_ms": max((r["elapsed_ms"] for r in apis), default=0),
        "slow_sql_peak_ms": max((r["elapsed_ms"] for r in sqls), default=0),
    }


class SlowRequestMiddleware:
    """ASGI 中间件：记录慢 API 和慢 SQL（通过 SQLAlchemy 事件钩子）"""

    def __init__(
        self,
        app,
        slow_api_ms: float = 500,
        slow_sql_ms: float = 200,
    ):
        self.app = app
        self.slow_api_ms = slow_api_ms
        self.slow_sql_ms = slow_sql_ms
        # 注册 SQLAlchemy 事件
        self._install_sql_listener()

    def _install_sql_listener(self):
        """通过 SQLAlchemy before_cursor_execute / after_cursor_execute 捕获慢 SQL"""
        try:
            from sqlalchemy import event
            from app.core.database import engine

            slow_sql_ms = self.slow_sql_ms

            @event.listens_for(engine.sync_engine, "before_cursor_execute")
            def _before(conn, cursor, statement, parameters, context, executemany):
                conn.info["_slow_req_start"] = time.perf_counter()

            @event.listens_for(engine.sync_engine, "after_cursor_execute")
            def _after(conn, cursor, statement, parameters, context, executemany):
                start = conn.info.pop("_slow_req_start", None)
                if start is None:
                    return
                elapsed = (time.perf_counter() - start) * 1000
                if elapsed > slow_sql_ms:
                    _bump("slow_sql_count")
                    sql_short = statement[:200].replace("\n", " ")
                    _slow_sqls.append({
                        "sql": sql_short,
                        "params": str(parameters)[:200] if parameters else None,
                        "elapsed_ms": round(elapsed, 2),
                    })
                    logger.warning(
                        "慢SQL %.2fms: %s | params=%s",
                        elapsed, sql_short, str(parameters)[:100] if parameters else "",
                    )
        except Exception:
            logger.debug("SQLAlchemy 慢 SQL 监听器安装失败（数据库尚未初始化）")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        path = scope.get("path", "?")
        method = scope.get("method", "?")

        async def _send(message):
            if message["type"] == "http.response.start":
                elapsed = (time.perf_counter() - start) * 1000
                _bump("total_requests")
                status = message.get("status", 0)
                if elapsed > self.slow_api_ms:
                    _bump("slow_api_count")
                    _slow_apis.append({
                        "method": method,
                        "path": path,
                        "status": status,
                        "elapsed_ms": round(elapsed, 2),
                    })
                    logger.warning(
                        "慢API %.2fms %s %s → %s",
                        elapsed, method, path, status,
                    )
            await send(message)

        await self.app(scope, receive, _send)
