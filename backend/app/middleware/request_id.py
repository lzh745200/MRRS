"""
请求ID链路追踪中间件

为每个HTTP请求生成唯一的请求ID，便于日志关联和问题排查。
- 响应头中自动添加 X-Request-ID
- 请求上下文中可通过 request.state.request_id 获取
- 日志中自动注入 request_id 字段
"""

import logging
import re
import time
import uuid
from contextvars import ContextVar

import anyio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.constants import HTTP_CLIENT_CLOSED_REQUEST

logger = logging.getLogger(__name__)

# X-Request-ID 合法格式：仅允许字母数字、连字符、下划线，最长 64 字符
_VALID_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

# 慢请求阈值（毫秒）已收敛到 settings.SLOW_REQUEST_THRESHOLD_MS（原硬编码 2000），
# 在 dispatch 中于请求时读取，便于经环境变量调优而无需改代码。

# 上下文变量：在异步环境中安全传递请求ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """获取当前请求ID（供日志模块使用）"""
    return request_id_var.get("")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件

    功能：
    1. 为每个请求生成/提取唯一ID
    2. 在响应头中返回 X-Request-ID
    3. 记录请求耗时
    4. 设置上下文变量供日志使用
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 优先使用客户端传入的请求ID（便于前后端链路关联）
        # 客户端传入的值必须通过格式验证，防止日志注入/响应头污染
        client_req_id = request.headers.get("X-Request-ID", "")
        if client_req_id and _VALID_REQUEST_ID_RE.match(client_req_id):
            req_id = client_req_id
        else:
            req_id = uuid.uuid4().hex[:16]

        # 存储到请求状态和上下文变量
        request.state.request_id = req_id
        token = request_id_var.set(req_id)

        start_time = time.time()
        try:
            response = await call_next(request)
        except anyio.EndOfStream:
            # 客户端连接已断开，返回空响应避免 RuntimeError
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(
                "客户端连接断开 | rid=%s | %s %s | %.1fms",
                req_id,
                request.method,
                request.url.path,
                elapsed_ms,
            )
            return JSONResponse(
                status_code=HTTP_CLIENT_CLOSED_REQUEST,
                content={"detail": "客户端关闭了连接"},
            )
        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                "请求异常 | rid=%s | %s %s | %.1fms | %s",
                req_id,
                request.method,
                request.url.path,
                elapsed_ms,
                exc,
            )
            raise
        finally:
            request_id_var.reset(token)

        elapsed_ms = (time.time() - start_time) * 1000

        # 在响应头中返回请求ID
        response.headers["X-Request-ID"] = req_id

        # 慢请求警告（阈值来自 settings，调用时读取）
        if elapsed_ms > settings.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                "慢请求 | rid=%s | %s %s | %.1fms | status=%d",
                req_id,
                request.method,
                request.url.path,
                elapsed_ms,
                response.status_code,
            )
        elif logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "请求完成 | rid=%s | %s %s | %.1fms | status=%d",
                req_id,
                request.method,
                request.url.path,
                elapsed_ms,
                response.status_code,
            )

        return response


class RequestIDLogFilter(logging.Filter):
    """日志过滤器：自动在日志记录中注入 request_id 字段"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True
