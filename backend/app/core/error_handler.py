"""Error handler utilities.

Provides helper functions for constructing consistent error responses and
registering FastAPI exception handlers.
"""

import logging

from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
app_logger = logger  # backward compatibility alias


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

# Backward compat aliases — canonical definitions in app.core.exceptions
# （仅保留有外部引用的 AppError/NotFoundError；BadRequestError/ForbiddenError/
#   ConflictError/ServerError 四个别名零引用，2026-08-29 死代码清理移除）
# 直接导入，禁止 ImportError 静默降级（深审 #10）：此处一旦退化，
# AppError 变成 Exception、NotFoundError 变成 Exception，所有
# isinstance 判定与异常处理器都会静默失效（本该 404 的变成 500，或反之）。
# 真出现导入失败应当在启动期就炸掉，而不是把错误语义悄悄改掉。
from app.core.exceptions import (  # noqa: E402,F401 — 兼容别名，供外部 `from app.core.error_handler import AppError` 使用
    AppError,
    NotFoundError,
)

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


def forbidden_response(message: str = "无权访问") -> JSONResponse:
    """Return a standard 403 JSON response."""
    return JSONResponse(
        status_code=403,
        content=error_response(403, message),
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


# ---------------------------------------------------------------------------
# Convenience: handle known HTTP status subclasses
# ---------------------------------------------------------------------------


class BusinessLogicError(AppError):
    status_code = 400
