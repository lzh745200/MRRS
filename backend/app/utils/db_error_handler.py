"""
数据库操作错误处理装饰器

提供统一的数据库事务错误处理
"""

import functools
import logging
from typing import Any, Callable, TypeVar

from fastapi import HTTPException
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessError
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _extract_db_session(args, kwargs) -> Session | None:
    for arg in args:
        if isinstance(arg, Session):
            return arg
    return kwargs.get("db")


def _handle_db_exception(func_name: str, db: Session | None, exc: Exception) -> None:
    if db:
        db.rollback()

    if isinstance(exc, IntegrityError):
        logger.error(f"Database integrity error in {func_name}: {exc}")
        error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        if "UNIQUE constraint failed" in error_msg or "duplicate key" in error_msg.lower():
            raise HTTPException(status_code=409, detail="数据已存在，请检查唯一性约束")
        if "FOREIGN KEY constraint failed" in error_msg:
            raise HTTPException(status_code=400, detail="关联数据不存在或已被删除")
        raise HTTPException(status_code=400, detail=f"数据完整性错误: {error_msg[:100]}")

    if isinstance(exc, OperationalError):
        logger.error(f"Database operational error in {func_name}: {exc}")
        _op_msg = str(exc).lower()
        if "disk" in _op_msg or "full" in _op_msg:
            raise HTTPException(status_code=503, detail="磁盘空间不足，请清理后重试")
        raise HTTPException(status_code=503, detail="数据库操作失败，请稍后重试")

    if isinstance(exc, (HTTPException, BusinessError)):
        raise exc

    if isinstance(exc, SQLAlchemyError):
        logger.error(f"Database error in {func_name}: {exc}")
        raise HTTPException(status_code=500, detail="数据库错误，请联系管理员")

    logger.error(f"Unexpected error in {func_name}: {exc}", exc_info=True)
    raise HTTPException(status_code=500, detail=f"操作失败: {str(exc)[:100]}")


def handle_db_errors(func: F) -> F:
    """
    数据库操作错误处理装饰器

    自动处理常见的数据库错误并回滚事务
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = _extract_db_session(args, kwargs)
        try:
            return func(*args, **kwargs)
        except (IntegrityError, OperationalError, SQLAlchemyError, HTTPException, BusinessError, Exception) as e:
            _handle_db_exception(func.__name__, db, e)

    return wrapper  # type: ignore


def handle_db_errors_async(func: F) -> F:
    """
    异步数据库操作错误处理装饰器
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        db = _extract_db_session(args, kwargs)
        try:
            return await func(*args, **kwargs)
        except (IntegrityError, OperationalError, SQLAlchemyError, HTTPException, BusinessError, Exception) as e:
            _handle_db_exception(func.__name__, db, e)

    return wrapper  # type: ignore


class DBTransaction:
    """
    数据库事务上下文管理器

    使用示例:
    ```python
    with DBTransaction(db):
        # 数据库操作
        db.add(obj)
        safe_commit(db)
    ```
    """

    def __init__(self, db: Session, auto_commit: bool = False):
        self.db = db
        self.auto_commit = auto_commit

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 发生异常，回滚
            self.db.rollback()
            logger.error(f"Transaction rolled back due to {exc_type.__name__}: {exc_val}")
            return False

        if self.auto_commit:
            try:
                safe_commit(self.db)
            except Exception as e:
                self.db.rollback()
                logger.error(f"Commit failed: {e}")
                raise

        return True
