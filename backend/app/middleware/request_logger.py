"""
请求日志中间件（ASGI 原生实现）

记录每个 HTTP 请求的详细信息：
- 请求方法、路径、查询参数
- 客户端 IP
- User-Agent
- 响应状态码
- 请求耗时

跳过静态资源和健康检查路径。
"""

import logging
import os
import time

logger = logging.getLogger("app.request")

# 可信代理（直连对端地址）：只有对端本身可信时，X-Forwarded-For / X-Real-IP
# 才有意义。否则任何客户端都能伪造日志中的来源 IP（深审 #34 —— 溯源证据不可信）。
# 默认覆盖本机回环与 TestClient；反代部署时用 TRUSTED_PROXIES 追加（逗号分隔）。
_DEFAULT_TRUSTED_PROXIES = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def _trusted_proxies() -> frozenset:
    """可信代理集合 = 默认回环集合 ∪ 环境变量 TRUSTED_PROXIES（逗号分隔）。"""
    extra = os.environ.get("TRUSTED_PROXIES", "")
    if not extra:
        return _DEFAULT_TRUSTED_PROXIES
    return _DEFAULT_TRUSTED_PROXIES | {item.strip() for item in extra.split(",") if item.strip()}


# 不记录日志的路径前缀
_SKIP_PREFIXES = (
    "/health",
    "/metrics",
    "/favicon.ico",
    "/static/",
)


def _get_client_ip(scope: dict) -> str:
    """从 ASGI scope 中提取客户端 IP（不可信对端一律用 socket 地址）"""
    client = scope.get("client")
    peer_ip = client[0] if client else None

    if peer_ip and peer_ip in _trusted_proxies():
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.decode("utf-8", errors="replace").split(",")[0].strip()
        real_ip = headers.get(b"x-real-ip")
        if real_ip:
            return real_ip.decode("utf-8", errors="replace").strip()

    if peer_ip:
        return peer_ip
    return "unknown"


def _get_user_agent(scope: dict) -> str:
    """从 ASGI headers 中提取 User-Agent"""
    headers = dict(scope.get("headers", []))
    ua = headers.get(b"user-agent", b"")
    return ua.decode("utf-8", errors="replace")[:200]


class RequestLoggerMiddleware:
    """
    ASGI 请求日志中间件

    用法: app.add_middleware(RequestLoggerMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # 跳过不需要记录的路径
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")
        client_ip = _get_client_ip(scope)
        user_agent = _get_user_agent(scope)
        start_time = time.time()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                "%s %s - ERROR (%.3fs) ip=%s ua=%s error=%s",
                method,
                path,
                duration,
                client_ip,
                user_agent,
                exc,
            )
            raise
        finally:
            duration = time.time() - start_time
            if status_code > 0:
                logger.info(
                    "%s %s%s - %d (%.3fs) ip=%s ua=%s",
                    method,
                    path,
                    f"?{query_string}" if query_string else "",
                    status_code,
                    duration,
                    client_ip,
                    user_agent,
                )
