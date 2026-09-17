"""Error code definitions.

Centralises error codes used across the application so that API
responses and logging can refer to consistent codes.
"""

from enum import IntEnum


class ErrorCode(IntEnum):
    """Application-level error codes.

    Members are chosen so that the integer value can be used directly in
    JSON responses (alongside the HTTP status code).
    """

    # --- General ---
    UNKNOWN = 0
    SUCCESS = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    VALIDATION_ERROR = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500

    # --- Auth ---
    INVALID_CREDENTIALS = 1001
    TOKEN_EXPIRED = 1002
    TOKEN_INVALID = 1003
    TOKEN_BLACKLISTED = 1004
    ACCOUNT_LOCKED = 1005
    ACCOUNT_DISABLED = 1006
    PASSWORD_EXPIRED = 1007
    WEAK_PASSWORD = 1008

    # --- Permission ---
    INSUFFICIENT_PERMISSIONS = 2001
    ROLE_NOT_FOUND = 2002

    # --- Resource ---
    RESOURCE_NOT_FOUND = 3001
    RESOURCE_ALREADY_EXISTS = 3002
    RESOURCE_DELETED = 3003
    IMPORT_FAILED = 3004
    EXPORT_FAILED = 3005

    # --- File ---
    FILE_TOO_LARGE = 4001
    FILE_TYPE_NOT_ALLOWED = 4002
    FILE_UPLOAD_FAILED = 4003
    FILE_CORRUPTED = 4004

    # --- Database ---
    DB_CONNECTION_FAILED = 5001
    DB_QUERY_FAILED = 5002
    DB_WRITE_FAILED = 5003

    # --- Rate limit ---
    RATE_LIMIT_EXCEEDED = 6001

    # --- External service ---
    EXTERNAL_SERVICE_ERROR = 7001

    # --- Config ---
    CONFIG_INVALID = 8001

    # --- Business ---
    BUSINESS_RULE_VIOLATION = 9001
    WORKFLOW_INVALID_TRANSITION = 9002

    # --- Backward-compat aliases (preserve original code values for legacy consumers) ---
    UNKNOWN_ERROR = 1000
    # Legacy codes that differ from current numbering — use unique values to avoid clashes
    # 注意：此值必须是**未被占用**的；曾误用 4003，与 FILE_UPLOAD_FAILED 撞号后
    # IntEnum 会把它静默变成别名（ErrorCode(4003) 解析为 FILE_UPLOAD_FAILED，
    # 且该成员从迭代中消失）。4001-4004 属 File 段，故取 4005。
    _USER_NOT_FOUND_LEGACY = 4005
    _DATABASE_ERROR_LEGACY = 6000
    _BUSINESS_ERROR_LEGACY = 5000
    _BACKUP_ERROR_LEGACY = 5004
    _NOT_FOUND_LEGACY = 4000
    # Aliases pointing to current canonical codes
    USER_NOT_FOUND = RESOURCE_NOT_FOUND
    DATABASE_ERROR = DB_CONNECTION_FAILED
    BUSINESS_ERROR = BUSINESS_RULE_VIOLATION
    BACKUP_ERROR = DB_WRITE_FAILED


# Human-readable messages (Chinese) keyed by ErrorCode value.
ERROR_MESSAGES = {
    0: "未知错误",
    200: "成功",
    400: "请求参数错误",
    401: "未认证",
    403: "无权访问",
    404: "资源不存在",
    409: "数据冲突",
    422: "请求参数验证失败",
    429: "请求过于频繁",
    500: "服务器内部错误",
    # Auth
    1000: "未知错误",  # UNKNOWN_ERROR legacy
    1001: "用户名或密码错误",
    1002: "令牌已过期",
    1003: "令牌无效",
    1004: "令牌已被吊销",
    1005: "账户已锁定",
    1006: "账户已禁用",
    1007: "密码已过期",
    1008: "密码强度不足",
    # Permission
    2001: "权限不足",
    2002: "角色不存在",
    # Resource
    3001: "资源不存在",
    3002: "资源已存在",
    3003: "资源已删除",
    3004: "导入失败",
    3005: "导出失败",
    # File
    4000: "资源不存在",  # NOT_FOUND legacy
    4001: "文件过大",
    4002: "文件类型不允许",
    4003: "文件上传失败",  # also USER_NOT_FOUND legacy via alias
    4004: "文件已损坏",
    # 原 4003 与 FILE_UPLOAD_FAILED 撞号，故 USER_NOT_FOUND 的 legacy 值分离到 4005
    4005: "用户不存在",
    # Database
    5000: "业务规则违反",  # BUSINESS_ERROR legacy
    5001: "数据库连接失败",
    5002: "数据库查询失败",
    5003: "数据库写入失败",
    5004: "备份失败",  # BACKUP_ERROR legacy
    # Rate limit
    6000: "数据库错误",  # DATABASE_ERROR legacy
    6001: "请求过于频繁，请稍后再试",
    # External
    7001: "外部服务异常",
    # Config
    8001: "配置无效",
    # Business
    9001: "业务规则违反",
    9002: "工作流状态转换无效",
}


def get_error_message(code: ErrorCode) -> str:
    """Return the human-readable message for an :class:`ErrorCode`.

    Args:
        code: The error code.

    Returns:
        The matching message, or a generic fallback.
    """
    return ERROR_MESSAGES.get(code.value, f"错误码 {code}")


# ── Re-export canonical exceptions from exceptions.py (lazy) ──
# AppError and ValidationError are defined in exceptions.py to avoid duplication.
# 注意：不能在模块顶层 `from app.core.exceptions import ...`，否则与
# exceptions.py:44 的 `from app.core.errors import ErrorCode` 构成循环导入，
# 导致后端启动崩溃。改用 PEP 562 模块级 __getattr__ 延迟解析，
# 既保持 `from app.core.errors import AppError, ValidationError` 的向后兼容，
# 又避免加载期循环。
_LAZY_EXCEPTIONS = ("AppError", "ValidationError")


def __getattr__(name: str):
    if name in _LAZY_EXCEPTIONS:
        from app.core import exceptions as _exc

        return getattr(_exc, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ErrorCode", "ERROR_MESSAGES", "get_error_message", "AppError", "ValidationError"]  # noqa: F822
