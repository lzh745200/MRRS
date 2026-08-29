"""Exception handlers and custom exceptions."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


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

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "服务器内部错误", "success": False},
        )
