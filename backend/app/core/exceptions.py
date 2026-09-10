"""Exception handlers and custom exceptions."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

logger = logging.getLogger(__name__)


# ── 数据库异常 → HTTP 映射（单一事实源） ──
# `@handle_db_errors` 装饰器（app/utils/db_error_handler.py）与全局异常处理器
# 共用本映射：同一种数据库错误在两条路径上必须得到同样的状态码与文案，
# 否则"某个端点忘了加装饰器"就会把用户输入错误暴露成 500。
#
# 有装饰器的端点只有一小部分，R22 sweep 实测 8 个未装饰端点（/funds、/funds/apply、
# /fund-budgets/transactions、/fund-lifecycle/allocation-orders、/organizations、
# /policies/categories、/projects、/user-management）在传入不存在的关联 ID 时
# 直接 500/503（日志 `sqlite3.OperationalError: FOREIGN KEY constraint failed`）。
# 全局处理器是这条规则的兜底：约束类错误 = 用户输入可纠正 → 4xx。
def map_db_exception(exc: Exception) -> HTTPException | None:
    """把数据库异常翻译为 HTTPException；不是约束类错误返回 None。

    注意：SQLite 把外键冲突报成 ``OperationalError`` 而非 ``IntegrityError``，
    所以两类都要看。文案**不得**内插异常原文（W1 #6）：原文含表名/列名与 SQL
    片段，只进日志。
    """
    if isinstance(exc, IntegrityError):
        raw = str(getattr(exc, "orig", None) or exc)
        low = raw.lower()
        if "unique constraint failed" in low or "duplicate key" in low:
            return HTTPException(status_code=409, detail="数据已存在，请检查唯一性约束")
        if "foreign key constraint failed" in low:
            return HTTPException(status_code=400, detail="关联数据不存在或已被删除")
        return HTTPException(status_code=400, detail="数据完整性错误，请检查提交的数据")

    if isinstance(exc, OperationalError):
        low = str(getattr(exc, "orig", None) or exc).lower()
        if "foreign key constraint failed" in low:
            return HTTPException(status_code=400, detail="关联数据不存在或已被删除")
        if "unique constraint failed" in low or "duplicate key" in low:
            return HTTPException(status_code=409, detail="数据已存在，请检查唯一性约束")
        if "not null constraint failed" in low:
            return HTTPException(status_code=400, detail="数据完整性错误，请检查提交的数据")
        if "check constraint failed" in low:
            return HTTPException(status_code=400, detail="数据完整性错误，请检查提交的数据")

    return None


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 400, code=None, details=None, **kwargs):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}

    def __str__(self):
        return self.message

    @staticmethod
    def not_found(resource: str = "资源"):
        return AppError(f"{resource}不存在", 404)

    @staticmethod
    def bad_request(message: str = "请求参数错误"):
        return AppError(message, 400)

    @staticmethod
    def forbidden(message: str = "无权访问"):
        return AppError(message, 403)

    @staticmethod
    def conflict(message: str = "数据冲突"):
        return AppError(message, 409)


# ── Re-export ErrorCode helpers from sibling errors module ──
from app.core.errors import ErrorCode  # noqa: E402


class BusinessError(AppError):
    """Business logic error."""

    def __init__(self, message: str = "业务错误", status_code: int = 400,
                 code=ErrorCode.BUSINESS_ERROR, details=None, **kwargs):
        super().__init__(message, status_code, code=code, details=details, **kwargs)


# ── Custom ValidationError (overrides Pydantic re-export for app-level usage) ──
class _ValidationError(AppError):
    """Application-level validation error."""

    def __init__(self, message: str = "数据验证失败", field: str = "", **kwargs):
        from app.core.errors import ErrorCode as EC
        super().__init__(message, status_code=400, code=EC.VALIDATION_ERROR, **kwargs)
        self.field = field
        if field:
            self.details["field"] = field


# Export as ValidationError (overrides Pydantic's ValidationError for our API)
ValidationError = _ValidationError


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, resource: str = "资源", identifier: str = ""):
        msg = f"{resource}不存在" if not identifier else f"{resource}({identifier})不存在"
        super().__init__(msg, 404)
        if identifier:
            self.details["identifier"] = identifier


class ConflictError(AppError):
    """Data conflict."""

    def __init__(self, message: str = "数据冲突"):
        super().__init__(message, 409)


class DatabaseError(AppError):
    """Database operation error."""

    def __init__(self, message: str = "数据库操作失败"):
        super().__init__(message, 500)


class InvalidCredentialsError(BusinessError):
    """Invalid login credentials."""

    def __init__(self, message: str = "用户名或密码错误"):
        super().__init__(message, 401)


class UserAlreadyExistsError(BusinessError):
    """User already exists (duplicate registration)."""

    def __init__(self, message: str = "用户已存在"):
        super().__init__(message, 409)


# ── Backward-compat aliases (extend BusinessError for isinstance checks) ──

class NotFoundException(BusinessError):
    def __init__(self, msg="Not found"):
        super().__init__(msg, 404)


class AuthenticationException(BusinessError):
    def __init__(self, msg="Authentication failed"):
        super().__init__(msg, 401)


# ── Exception handlers ──

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": exc.message, "success": False},
        )

    @app.exception_handler(PydanticValidationError)
    async def validation_error_handler(request: Request, exc: PydanticValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": 422, "message": "请求参数验证失败", "success": False, "errors": exc.errors()},
        )

    async def _db_constraint_handler(request: Request, exc: Exception):
        """IntegrityError / OperationalError 的统一出口。

        约束类错误（外键/唯一/NOT NULL/CHECK）映射为 4xx —— 属用户可纠正的输入
        问题；其余 OperationalError 维持既有 500 语义（真实服务端故障），不改变
        任何现存行为。
        同时给出 `message`（信封风格，axios 拦截器读）与 `detail`（HTTPException
        风格，各视图的 `e.response.data.detail` 读）两个键。
        """
        mapped = map_db_exception(exc)
        if mapped is None:
            logger.error(
                "数据库错误 %s %s: %s", request.method, request.url.path, exc, exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={"code": 500, "message": "服务器内部错误", "success": False},
            )
        logger.error(
            "数据库约束错误 %s %s: %s", request.method, request.url.path, exc, exc_info=True
        )
        return JSONResponse(
            status_code=mapped.status_code,
            content={
                "code": mapped.status_code,
                "message": mapped.detail,
                "detail": mapped.detail,
                "success": False,
            },
        )

    app.add_exception_handler(IntegrityError, _db_constraint_handler)
    app.add_exception_handler(OperationalError, _db_constraint_handler)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "服务器内部错误", "success": False},
        )
