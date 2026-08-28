"""Error handler utilities.

Provides helper functions for constructing consistent error responses and
registering FastAPI exception handlers.
"""

import logging
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
app_logger = logger  # backward compatibility alias


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

# Backward compat aliases — canonical definitions in app.core.exceptions
# （仅保留有外部引用的 AppError/NotFoundError；BadRequestError/ForbiddenError/
#   ConflictError/ServerError 四个别名零引用，2026-08-29 死代码清理移除）
try:
    from app.core.exceptions import (
        AppError,
        NotFoundError,
    )
except ImportError:  # pragma: no cover
    AppError = Exception  # type: ignore
    NotFoundError = Exception  # type: ignore

# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def error_response(
    code: int = 500,
    message: str = "服务器内部错误",
    *,
    details: Any = None,
    success: bool = False,
) -> Dict[str, Any]:
    """Build a standardised JSON error response body.

    Args:
        code: HTTP status code.
        message: Human-readable error message.
        details: Optional extra payload (e.g. validation errors).
        success: Always ``False`` for error responses.
    """
    body: Dict[str, Any] = {
        "code": code,
        "message": message,
        "success": success,
    }
    if details is not None:
        body["details"] = details
    return body


def not_found_response(
    resource: str = "资源",
    resource_id: Optional[str] = None,
) -> JSONResponse:
    """Return a standard 404 JSON response.

    Args:
        resource: Resource name (e.g. ``"用户"``).
        resource_id: Optional resource identifier.
    """
    msg = f"{resource}不存在" if resource_id is None else f"{resource} (id={resource_id}) 不存在"
    return JSONResponse(
        status_code=404,
        content=error_response(404, msg),
    )


def bad_request_response(message: str = "请求参数错误") -> JSONResponse:
    """Return a standard 400 JSON response."""
    return JSONResponse(
        status_code=400,
        content=error_response(400, message),
    )


def forbidden_response(message: str = "无权访问") -> JSONResponse:
    """Return a standard 403 JSON response."""
    return JSONResponse(
        status_code=403,
        content=error_response(403, message),
    )


def conflict_response(message: str = "数据冲突") -> JSONResponse:
    """Return a standard 409 JSON response."""
    return JSONResponse(
        status_code=409,
        content=error_response(409, message),
    )


def server_error_response(message: str = "服务器内部错误") -> JSONResponse:
    """Return a standard 500 JSON response."""
    return JSONResponse(
        status_code=500,
        content=error_response(500, message),
    )


# ---------------------------------------------------------------------------
# FastAPI handler registration
# ---------------------------------------------------------------------------


def register_handlers(
    app: FastAPI,
    *,
    extra_handlers: Optional[Dict[type[Exception], Callable]] = None,
) -> None:
    """Register default and extra exception handlers on a FastAPI app.

    Args:
        app: The FastAPI application instance.
        extra_handlers: Optional mapping of exception class -> handler coroutine.
    """
    # The main exception handler registration is performed in
    # :mod:`app.core.exceptions`.  This function serves as a convenience
    # wrapper that can optionally add extra handlers.
    try:
        from app.core.exceptions import register_exception_handlers

        register_exception_handlers(app)
    except ImportError:  # pragma: no cover
        logger.debug("app.core.exceptions not found; skipping default handlers")
        # Register a minimal fallback

        @app.exception_handler(Exception)
        async def _global_handler(request: Request, exc: Exception) -> JSONResponse:
            logger.error("Unhandled exception: %s", exc, exc_info=True)
            return server_error_response()

    if extra_handlers:
        for exc_class, handler in extra_handlers.items():
            app.add_exception_handler(exc_class, handler)


# ---------------------------------------------------------------------------
# Convenience: handle known HTTP status subclasses
# ---------------------------------------------------------------------------


def http_status_to_message(status_code: int) -> str:
    """Return a default Chinese message for common HTTP status codes."""
    messages = {
        400: "请求参数错误",
        401: "未认证",
        403: "无权访问",
        404: "资源不存在",
        405: "不允许的请求方法",
        409: "数据冲突",
        422: "请求参数验证失败",
        429: "请求过于频繁",
        500: "服务器内部错误",
        502: "网关错误",
        503: "服务不可用",
    }
    return messages.get(status_code, f"HTTP {status_code}")


class BusinessLogicError(AppError):
    status_code = 400
