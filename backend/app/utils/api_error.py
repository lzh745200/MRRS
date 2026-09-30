"""
API 错误处理辅助函数

提供统一的错误处理方式，避免在生产环境泄露敏感信息
"""

import functools
import logging
import os
from typing import Callable, Optional, ParamSpec, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

_is_production: Optional[bool] = None


def is_production() -> bool:
    """检查是否为生产环境（带缓存）"""
    global _is_production
    if _is_production is None:
        _is_production = os.environ.get("ENVIRONMENT", "production") == "production"
    return _is_production


def raise_api_error(
    message: str,
    error: Optional[Exception] = None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    log_error: bool = True,
) -> None:
    """
    统一的 API 错误处理函数

    Args:
        message: 用户友好的错误消息
        error: 原始异常（仅用于日志记录）
        status_code: HTTP 状态码
        log_error: 是否记录错误日志
    """
    if log_error and error:
        logger.error(f"{message}: {str(error)}", exc_info=True)

    if is_production():
        raise HTTPException(status_code=status_code, detail=message)
    else:
        detail = f"{message}: {str(error)}" if error else message
        raise HTTPException(status_code=status_code, detail=detail)


def handle_service_error(
    operation: str,
    error: Exception,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> None:
    """
    处理服务层错误

    Args:
        operation: 操作描述（如"获取仪表盘数据"）
        error: 原始异常
        status_code: HTTP 状态码
    """
    raise_api_error(f"{operation}失败", error=error, status_code=status_code)


def safe_api_call(operation: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
    """
    API 安全调用装饰器

    用法:
        @safe_api_call("获取仪表盘数据")
        async def get_dashboard():
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                handle_service_error(operation, e, status_code)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                handle_service_error(operation, e, status_code)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class APIErrorHandler:
    """API 错误处理器上下文管理器"""

    def __init__(self, operation: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.operation = operation
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is None:
            return False
        # with 块内主动抛出的 HTTPException（403/404/422…）必须原样上抛：
        # 此前一律经 handle_service_error 改写成默认 500，状态码语义被抹掉
        # （深审 #80）。handle_service_error 自身必然抛 HTTPException，
        # 故其后无 return —— 不再有"return True 吞掉异常"的误导分支。
        if isinstance(exc_val, HTTPException):
            return False
        handle_service_error(self.operation, exc_val, self.status_code)
