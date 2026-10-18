"""
指标采集中间件（ASGI 原生实现）

收集 HTTP 请求性能指标：
- 请求计数（按方法、路径、状态码）
- 请求耗时统计
- 活跃请求数

指标通过内存计数器存储，供 /metrics 端点查询。
"""

import logging
import re
import time
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)

# 不采集指标的路径前缀
_SKIP_PREFIXES = (
    "/health",
    "/metrics",
    "/favicon.ico",
)

# W5-T11：动态段归一的段形状（UUID / 纯数字，含负数）
_UUID_SEGMENT_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)"
)
_NUMERIC_SEGMENT_RE = re.compile(r"/-?\d+(?=/|$)")


def _normalize_path(path: str) -> str:
    """把路径中的动态段（UUID / 数字）替换为 ``{id}``。

    W5-T11：``_path_durations`` 此前直接以原始 path 为键 —— 任何带资源 ID
    的请求都会生成新键（``/api/v1/projects/1``、``/2``、``/3``…），全局单例
    存储随长跑进程无界增长。归一化后同一资源的全部请求共享一个键；
    Starlette 已命中的路由优先用 ``scope["route"].path`` 模板（更精确），
    本函数是其不可用时的兜底。
    """
    if not path:
        return path
    normalized = _UUID_SEGMENT_RE.sub("/{id}", path)
    return _NUMERIC_SEGMENT_RE.sub("/{id}", normalized)


class _MetricsStore:
    """线程安全的指标存储"""

    def __init__(self):
        self._lock = threading.Lock()
        self.request_count = 0
        self.error_count = 0
        self.active_requests = 0
        self.total_duration = 0.0
        self._path_counts = {}  # (method, status) -> count
        self._path_durations = {}  # (method, path) -> [total, count, max]
        self._max_path_keys = 500  # W5-T11：按路径键的容量上限（超出归入 __other__）
        self._slow_requests = []  # [(method, path, duration, timestamp)]
        self._max_slow = 100  # 最多保留 100 条慢请求记录
        # 慢请求阈值（秒）—— 来自 settings（SLOW_METRICS_THRESHOLD_SECONDS），
        # 原硬编码 1.0，默认值保持不变，可经环境变量调优。
        self._slow_threshold = settings.SLOW_METRICS_THRESHOLD_SECONDS
        self._start_time = time.time()

    def record(self, method: str, path: str, status: int, duration: float):
        with self._lock:
            self.request_count += 1
            self.total_duration += duration
            if status >= 400:
                self.error_count += 1
            key = (method, status)
            self._path_counts[key] = self._path_counts.get(key, 0) + 1

            # 按路径统计耗时（W5-T11：容量上限，防指标基数无界增长）
            path_key = (method, path)
            if path_key not in self._path_durations:
                if len(self._path_durations) >= self._max_path_keys:
                    # 已达上限：新路径统一归入 __other__ 桶
                    path_key = (method, "__other__")
                    if path_key not in self._path_durations:
                        self._path_durations[path_key] = [0.0, 0, 0.0]
                else:
                    self._path_durations[path_key] = [0.0, 0, 0.0]
            entry = self._path_durations[path_key]
            entry[0] += duration
            entry[1] += 1
            if duration > entry[2]:
                entry[2] = duration

            # 记录慢请求
            if duration > self._slow_threshold:
                self._slow_requests.append((method, path, duration, time.time()))
                if len(self._slow_requests) > self._max_slow:
                    self._slow_requests = self._slow_requests[-self._max_slow:]

    def inc_active(self):
        with self._lock:
            self.active_requests += 1

    def dec_active(self):
        with self._lock:
            self.active_requests -= 1

    def active_count(self) -> int:
        """当前在途请求数（R7 维护窗口等待归零用，加锁读避免撕裂）。"""
        with self._lock:
            return self.active_requests

    def get_summary(self) -> dict:
        with self._lock:
            avg_duration = (
                self.total_duration / self.request_count
                if self.request_count > 0
                else 0.0
            )
            uptime = time.time() - self._start_time
            error_rate = (
                self.error_count / self.request_count
                if self.request_count > 0
                else 0.0
            )
            # 构建按路径的统计
            top_endpoints = []
            for (method, path), (total, count, max_dur) in sorted(
                self._path_durations.items(), key=lambda x: x[1][0], reverse=True
            )[:10]:
                top_endpoints.append({
                    "method": method,
                    "path": path,
                    "total_duration": round(total, 3),
                    "count": count,
                    "avg_duration": round(total / count, 3) if count > 0 else 0,
                    "max_duration": round(max_dur, 3),
                })
            # 慢请求列表
            slow_reqs = []
            for method, path, dur, ts in reversed(self._slow_requests):
                slow_reqs.append({
                    "method": method,
                    "path": path,
                    "duration": round(dur, 3),
                    "timestamp": ts,
                })
            return {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": round(error_rate, 4),
                "active_requests": self.active_requests,
                "avg_duration": round(avg_duration, 3),
                "uptime_seconds": round(uptime, 1),
                "requests_per_second": round(self.request_count / uptime, 2) if uptime > 0 else 0,
                "by_method_status": {
                    f"{m}_{s}": c for (m, s), c in self._path_counts.items()
                },
                "top_endpoints": top_endpoints,
                "slow_requests": slow_reqs,
                "slow_request_count": len(self._slow_requests),
                "slow_threshold_seconds": self._slow_threshold,
            }


# 全局指标存储（单例）
metrics_store = _MetricsStore()


class MetricsMiddleware:
    """
    ASGI 指标采集中间件

    用法: app.add_middleware(MetricsMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # METRICS_ENABLED 此前零消费（R28 低危项）：关闭时直接透传，
        # 不计数、不耗时统计、不写慢请求（/metrics 端点本身仍在路由层）。
        # 运行时读取 settings 属性，便于运维热切换与测试注入。
        if scope["type"] != "http" or not settings.METRICS_ENABLED:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # 跳过不需要采集的路径
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        start_time = time.time()
        status_code = 0

        def _metric_path() -> str:
            """记录用的路径键：路由模板优先，退化到段形状归一（W5-T11）。"""
            route = scope.get("route")
            template = getattr(route, "path", None) if route is not None else None
            return template or _normalize_path(path)
        # 一次性标志：异常分支已按 500 记录后，finally 不得再按 status_code
        # 记第二次（深审 #33 —— 计数与耗时被重复累加，错误率虚高）。
        recorded = False

        metrics_store.inc_active()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration = time.time() - start_time
            recorded = True
            metrics_store.record(method, _metric_path(), 500, duration)
            raise
        finally:
            duration = time.time() - start_time
            metrics_store.dec_active()
            if status_code > 0 and not recorded:
                metrics_store.record(method, _metric_path(), status_code, duration)
