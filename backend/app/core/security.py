"""
安全模块

提供:
- JWT token 生成与验证
- 密码哈希与校验
- FastAPI 认证依赖
- 安全中间件
- 密码策略
"""

import logging
import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── passlib + bcrypt 兼容性补丁 ──
# bcrypt 4.1+ 对 >72 字节密码抛出 ValueError，passlib 1.7.4 的 bug 检测代码未适配
# bcrypt 5.x 移除了 __about__ 模块，导致 passlib 无法读取版本号而回退到纯 Python
# 实现（验证密码耗时 20-60 秒），见: https://github.com/pyca/bcrypt/issues/684
# 注意：bcrypt>=4.2.0 已在 requirements.txt 中声明，以下补丁在 4.1+ 上为活代码。
try:
    import bcrypt as _bcrypt

    # bcrypt 5.x: 注入缺失的 __about__ 让 passlib 正常识别版本并加载 C 扩展
    if not hasattr(_bcrypt, '__about__'):
        import types as _types
        _bcrypt.__about__ = _types.ModuleType('__about__')
        _bcrypt.__about__.__version__ = _bcrypt.__version__

    # 使用元组比较避免字符串比较的字典序问题（如 '4.10' < '4.2'）
    _bcrypt_version = tuple(int(x) for x in _bcrypt.__version__.split('.')[:2] if x.isdigit())
    if _bcrypt_version >= (4, 1):
        import passlib.handlers.bcrypt as _pb
        _orig_finalize = _pb._BcryptCommon._finalize_backend_mixin.__func__

        def _patched_finalize(cls, name, dryrun):
            try:
                return _orig_finalize(cls, name, dryrun)
            except (ValueError, Exception):
                return True  # 跳过 passlib 的 bcrypt wrap-bug 检测

        _pb._BcryptCommon._finalize_backend_mixin = classmethod(_patched_finalize)
except ValueError:
    logger.debug("bcrypt版本兼容检测跳过（版本不匹配），不影响正常使用")
except Exception as e:
    logger.error("安全模块bcrypt兼容补丁异常: %s", e, exc_info=True)

from fastapi import Depends, HTTPException, Request, status  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # noqa: E402
import jwt  # noqa: E402  # PyJWT（替代 python-jose，CVE-2024-33663/33664 修复）
from jwt import InvalidTokenError as JWTError  # noqa: E402  # 兼容别名
from passlib.context import CryptContext  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


# ── 常量 ──
# 永远不应在生产中硬编码密钥。如果 SECRET_KEY 仍为空（理论上不应发生，
# 因为 config.py 会在模块加载时调用 ensure_runtime_secrets），
# 则生成一个进程内随机密钥并记录严重错误。
def _ensure_secret_key() -> str:
    """确保证书签名密钥可用 — 终极回退。"""
    import secrets as _secrets
    # config.py 已通过 ensure_runtime_secrets() 处理了正常路径。
    # 到达这里意味着配置系统未初始化 — 生成临时密钥 + 错误日志。
    key = os.environ.get("JWT_SECRET_KEY", "") or os.environ.get("SECRET_KEY", "")
    if not key:
        key = _secrets.token_hex(32)
        logger.critical(
            "所有密钥来源均已耗尽，生成了临时会话密钥 — "
            "服务重启后所有 JWT Token 将失效。请检查 runtime_secrets.json 是否存在且权限正确。"
        )
    return key


# 使用统一的 settings.SECRET_KEY，确保与 token_manager 等模块一致
try:
    from app.core.config import settings as _settings
    SECRET_KEY = _settings.SECRET_KEY or _ensure_secret_key()
    ALGORITHM = getattr(_settings, "ALGORITHM", "HS256")
except Exception as _settings_err:
    logger.warning("Failed to load settings for SECRET_KEY, falling back to env vars: %s", _settings_err)
    SECRET_KEY = _ensure_secret_key()
    ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# 角色常量（4 个实用角色；历史角色值统一通过 constants.py normalize_role() 归一化）
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_VIEWER = "viewer"

ALL_ROLES = [
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_USER,
    ROLE_VIEWER,
]

ADMIN_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN}

# ── 密码上下文 ──
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Bearer token 提取 ──
security_scheme = HTTPBearer(auto_error=False)

# ── bcrypt 密码长度限制 ──
_BCRYPT_MAX_BYTES = 72


# ══════════════════════════════════════════════════════════════
#  密码操作
# ══════════════════════════════════════════════════════════════


def _truncate_password(password: str) -> str:
    """截断密码到 bcrypt 最大长度（72 字节），防止 bcrypt 5.x 抛出 ValueError"""
    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        return encoded[:_BCRYPT_MAX_BYTES].decode("utf-8", errors="ignore")
    return password


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(_truncate_password(password))


def hash_password(password: str) -> str:
    """生成密码哈希（别名）"""
    return get_password_hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验密码"""
    try:
        return pwd_context.verify(_truncate_password(plain_password), hashed_password)
    except ValueError:
        return False  # passlib正常错误：密码格式不匹配
    except Exception as e:
        logger.critical("密码验证模块故障，可能影响所有用户登录: %s", e, exc_info=True)
        raise


def generate_password(length: int = 12, exclude_ambiguous: bool = False) -> str:
    """生成随机密码"""
    if length < 8:
        length = 8
    if exclude_ambiguous:
        alphabet = "abcdefghijkmnpqrstuvwxyzACDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%"
    else:
        alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        # 强制包含大写、小写、数字、特殊字符
        has_special = any(not c.isalnum() for c in password)
        if (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
            and has_special
        ):
            return password


# 向后兼容别名
generate_temp_password = generate_password


# ══════════════════════════════════════════════════════════════
#  敏感字段与日志脱敏
# ══════════════════════════════════════════════════════════════

SENSITIVE_FIELDS = {
    "password", "secret", "token", "key", "authorization",
    "credit_card", "ssn", "id_card", "phone", "email",
}


def sanitize_log_data(data: dict) -> dict:
    """清理日志数据中的敏感信息。

    Args:
        data: 原始数据字典

    Returns:
        已脱敏的数据字典
    """
    import copy

    sanitized = copy.deepcopy(data)
    for key in sanitized:
        key_lower = key.lower()
        if any(s in key_lower for s in SENSITIVE_FIELDS):
            sanitized[key] = "[REDACTED]"
    return sanitized


class CSRFProtection:
    """CSRF 保护工具类"""

    @staticmethod
    def generate_token() -> str:
        """生成 CSRF token"""
        return secrets.token_hex(32)

    @staticmethod
    def validate_token(request_token: str, session_token: str) -> bool:
        """验证 CSRF token"""
        if not request_token or not session_token:
            return False
        return request_token == session_token


# ══════════════════════════════════════════════════════════════
#  JWT Token 操作
# ══════════════════════════════════════════════════════════════


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token_with_machine_code(
    data: dict,
    machine_code: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建绑定机器码的 JWT access token（零信任安全）."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "type": "access",
        "machine_code": machine_code,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token_with_machine_code(
    token: str,
    expected_machine_code: Optional[str] = None,
) -> dict:
    """解码 JWT 并可选验证机器码绑定.

    Args:
        token: JWT 字符串
        expected_machine_code: 期望的机器码，None 则跳过校验（向后兼容）

    Raises:
        ValueError: 机器码不匹配（跨设备盗用检测）
        jwt.JWTError: Token 无效或过期
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if expected_machine_code is not None:
        token_mc = payload.get("machine_code")
        if token_mc and token_mc != expected_machine_code:
            raise ValueError(
                "Token 设备绑定校验失败: "
                f"期望 {expected_machine_code[:12]}..., "
                f"实际 {token_mc[:12]}..."
            )
    return payload


def create_refresh_token(data: dict) -> str:
    """创建 JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug(f"JWT 解码失败: {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  FastAPI 认证依赖
# ══════════════════════════════════════════════════════════════


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[object]:
    """
    获取当前登录用户（FastAPI 依赖）。

    从 Authorization: Bearer <token> 提取 JWT，解码后查询数据库。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌内容",
        )

    # 延迟导入避免循环依赖
    from app.core.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )
        # 验证 token_version：支持强制下线所有会话
        token_version = payload.get("token_version")
        if token_version is not None and int(token_version) != (getattr(user, "token_version_safe", 0) or 0):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌已失效（版本不匹配），请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # 审计归因：将当前用户 ID 写入 ContextVar，供 SQLAlchemy 事件级审计
        # （audit_event_handler）在 commit/flush 时读取，实现写操作可追责到人。
        # ContextVar 为请求任务级隔离，请求结束后自动复位为默认值 None。
        try:
            from app.middleware.audit_context import set_current_user

            set_current_user(getattr(user, "id", None))
        except Exception:
            # 审计归因不应阻断主流程
            pass
        return user
    finally:
        db.close()


async def get_current_active_user(
    current_user=Depends(get_current_user),
):
    """获取当前活跃用户（未禁用）"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="未认证")
    if hasattr(current_user, "is_active") and not current_user.is_active:
        raise HTTPException(status_code=403, detail="账户已禁用")
    return current_user


def require_admin():
    """
    要求管理员权限（FastAPI 依赖工厂）。

    用法: Depends(require_admin()) — 注意有括号，返回依赖函数。
    """

    async def _admin_checker(
        current_user=Depends(get_current_active_user),
    ):
        if current_user is None:
            raise HTTPException(status_code=401, detail="未认证")
        role = getattr(current_user, "role", "")
        is_superuser = getattr(current_user, "is_superuser", False)
        if role not in ADMIN_ROLES and not is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限",
            )
        return current_user

    return _admin_checker


def require_roles(*allowed_roles):
    """要求指定角色（FastAPI 依赖工厂）"""

    async def _check(current_user=Depends(get_current_active_user)):
        if current_user is None:
            raise HTTPException(status_code=401, detail="未认证")
        role = getattr(current_user, "role", "")
        is_superuser = getattr(current_user, "is_superuser", False)
        if role not in allowed_roles and not is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(allowed_roles)}",
            )
        return current_user

    return _check


# ══════════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════════


class RateLimitExceeded(Exception):
    """速率限制超出异常"""

    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        self.message = message
        super().__init__(self.message)


# SQL 注入检测模式
SQL_INJECTION_PATTERNS = [
    r"(?i)(\bUNION\b.*\bSELECT\b)",
    r"(?i)(\bDROP\b\s+\bTABLE\b)",
    r"(?i)(\bALTER\b\s+\bTABLE\b)",
    r"(?i)(\bINSERT\b\s+\bINTO\b)",
    r"(?i)(\bDELETE\b\s+\bFROM\b)",
    r"(?i)(\bUPDATE\b\s+\bSET\b)",
    r"(?i)(\bEXEC\b|\bEXECUTE\b)",
    r"(?i)(--\s)",
    r"(?i)(;)\s*$",
    r"(?i)(\/\*)",
]


def check_sql_injection(value: str) -> bool:
    """检查字符串是否包含 SQL 注入模式。

    Returns:
        True 如果检测到潜在注入，否则 False
    """
    import re
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value):
            return True
    return False


def sanitize_input(value: str) -> str:
    """清理用户输入，移除危险字符。

    Args:
        value: 原始输入

    Returns:
        清理后的字符串
    """
    if not value or not isinstance(value, str):
        return value or ""
    # 移除常见 SQL 注入字符
    sanitized = value.replace("'", "''")
    sanitized = sanitized.replace(";", "")
    sanitized = sanitized.replace("--", "")
    sanitized = sanitized.replace("/*", "")
    sanitized = sanitized.replace("*/", "")
    return sanitized


# ── 内存速率限制器（slowapi 回退） ──
import time  # noqa: E402
import threading  # noqa: E402
from app.core.transaction import safe_commit  # noqa: E402

_rate_limit_store: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()
_last_rate_limit_cleanup: float = 0.0


def _cleanup_expired_rate_keys(now: float, max_window: int = 300) -> None:
    """清理 _rate_limit_store 中所有已过期的键，防止内存泄漏。"""
    global _last_rate_limit_cleanup
    # 节流：最多每 60 秒执行一次全局清理
    if now - _last_rate_limit_cleanup < 60:
        return
    _last_rate_limit_cleanup = now
    cutoff = now - max_window
    expired = [k for k, v in _rate_limit_store.items() if not v or all(t <= cutoff for t in v)]
    for k in expired:
        del _rate_limit_store[k]
    if expired:
        logger.debug("速率限制器清理: 移除 %d 个过期键", len(expired))


async def check_rate_limit(
    request=None,
    key: str = None,
    limit: int = 60,
    window: int = 60,
    **kwargs
) -> bool:
    """速率限制检查。

    优先使用 slowapi 中间件；当 slowapi 不可用时，使用内置内存速率限制器。
    内置限制器采用滑动窗口算法，默认 60次/分钟。

    Args:
        request: FastAPI Request（slowapi 兼容参数）
        key: 速率限制键（通常为 IP 或用户名）
        limit: 窗口内最大请求数
        window: 时间窗口（秒）

    Returns:
        bool: True=允许请求，False=速率超限
    """
    if key is None:
        # 无键时放行（调用方需提供有意义的键）
        return True

    now = time.monotonic()
    with _rate_limit_lock:
        # 周期性清理所有过期键（最多每 60 秒一次）
        _cleanup_expired_rate_keys(now)

        timestamps = _rate_limit_store.get(key, [])
        # 清理过期时间戳（滑动窗口）
        cutoff = now - window
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= limit:
            _rate_limit_store[key] = timestamps
            return False
        timestamps.append(now)
        _rate_limit_store[key] = timestamps
        return True


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def is_local_request(request: Request) -> bool:
    """判断是否为本地请求"""
    ip = get_client_ip(request)
    return ip in ("127.0.0.1", "::1", "localhost")


# ══════════════════════════════════════════════════════════════
#  密码策略
# ══════════════════════════════════════════════════════════════


class PasswordPolicy:
    """密码策略验证"""

    MIN_LENGTH = 12
    REQUIRE_UPPER = True
    REQUIRE_LOWER = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    # 白名单：与前端正则 /[!@#$%^&*()\-_=+\[\]{}|;:,.<>?/ 一致
    SPECIAL_WHITELIST = set("!@#$%^&*()-_=+[]{}|;:,.<>?")
    # 弱密码黑名单
    WEAK_PASSWORD_PREFIXES = ("admin", "root", "123", "password", "qwerty")
    # 密码不能包含用户名
    FORBIDDEN_USERNAME_PARTS = []

    @staticmethod
    def validate(password: str, username: str = "") -> tuple:
        """
        验证密码是否符合策略。

        Args:
            password: 密码字符串
            username: 用户名（可选），用于弱密码验证

        Returns:
            (is_valid: bool, error_message: str)
        """
        if not password or len(password) < PasswordPolicy.MIN_LENGTH:
            return False, f"密码长度至少 {PasswordPolicy.MIN_LENGTH} 位"
        if PasswordPolicy.REQUIRE_UPPER and not any(c.isupper() for c in password):
            return False, "密码必须包含大写字母(A-Z)"
        if PasswordPolicy.REQUIRE_LOWER and not any(c.islower() for c in password):
            return False, "密码必须包含小写字母(a-z)"
        if PasswordPolicy.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            return False, "密码必须包含数字(0-9)"
        if PasswordPolicy.REQUIRE_SPECIAL and not any(c in PasswordPolicy.SPECIAL_WHITELIST for c in password):
            return False, f"密码必须包含特殊字符({', '.join(sorted(PasswordPolicy.SPECIAL_WHITELIST))})"
        if len(password) > 20:
            return False, "密码长度不能超过20位"
        # 弱密码检查
        if any(password.lower().startswith(pf) for pf in PasswordPolicy.WEAK_PASSWORD_PREFIXES):
            return False, "密码太弱，不能以admin/root/123/password/qwerty等开头"
        # 密码不能包含用户名（如果有）
        if username and any(part in password.lower() for part in username.lower().split()):
            return False, "密码不能包含用户名"
        return True, ""

    @staticmethod
    def validate_username(username: str) -> tuple:
        """
        验证用户名格式。

        Returns:
            (is_valid: bool, error_message: str)
        """
        if not username or not isinstance(username, str):
            return False, "用户名不能为空"
        username = username.strip()
        if len(username) < 3:
            return False, "用户名长度至少3个字符"
        if len(username) > 20:
            return False, "用户名长度不能超过20个字符"
        # Allow alphanumeric, underscore, dash, and Chinese characters
        import re
        if not re.match(r'^[\w\-一-龥]+$', username):
            return False, "用户名只能包含字母、数字、下划线、短横线和中文字符"
        return True, ""


# ══════════════════════════════════════════════════════════════
#  安全中间件
# ══════════════════════════════════════════════════════════════


class SecurityHeadersMiddleware:
    """安全响应头中间件"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                path = scope.get("path", "")
                method = scope.get("method", "")

                security_headers = [
                    (b"X-Content-Type-Options", b"nosniff"),
                    (b"X-Frame-Options", b"DENY"),
                    (b"X-XSS-Protection", b"1; mode=block"),
                    (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
                ]

                # Cache-Control: 静态资源和参考数据可缓存，变更数据不缓存
                if method == "GET":
                    if any(path.startswith(p) for p in ("/static/", "/assets/", "/frontend/")):
                        security_headers.append((b"Cache-Control", b"public, max-age=86400"))
                    elif any(path.startswith(p) for p in ("/api/v1/data/", "/api/v1/policy/")):
                        security_headers.append((b"Cache-Control", b"private, max-age=300"))

                existing = {h[0].lower() for h in message.get("headers", [])}
                for name, value in security_headers:
                    if name.lower() not in existing:
                        message["headers"] = list(message.get("headers", [])) + [
                            (name, value)
                        ]
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ══════════════════════════════════════════════════════════════
#  审计日志服务
# ══════════════════════════════════════════════════════════════


class AuditLogService:
    """审计日志服务"""

    def __init__(self, db=None):
        self.db = db

    @staticmethod
    async def log(
        db: Session = None,
        user_id: int = None,
        action: str = "",
        resource: str = "",
        resource_id: str = "",
        details: str = "",
        ip_address: str = "",
        **kwargs,
    ):
        """记录审计日志"""
        if db is None:
            return
        try:
            from app.models.audit import AuditLog

            # 字段名映射：方法签名用业务友好名，AuditLog 模型用规范列名
            # - resource → resource_type（模型列名）
            # - ip_address → user_ip（模型列名）
            # - details → metadata_（JSON 字段，存储额外详情；模型无 details 列）
            log_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource,
                resource_id=str(resource_id) if resource_id else None,
                metadata_={"details": details} if details else None,
                user_ip=ip_address or None,
            )
            db.add(log_entry)
            safe_commit(db)
        except Exception as e:
            logger.warning(f"审计日志写入失败: {e}")
            try:
                db.rollback()
            except Exception as rb_err:
                logger.warning(f"审计日志回滚失败: {rb_err}")


# ══════════════════════════════════════════════════════════════
#  安全常量
# ══════════════════════════════════════════════════════════════

# 安全响应头字典（供 SecurityHeadersMiddleware 使用）
SECURITY_HEADERS: dict = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# 敏感数据检测模式（供 sanitize_log_data 使用）
SENSITIVE_PATTERNS: list = [
    (r"\b\d{16}\b", "[CREDIT_CARD]"),
    (r"\b\d{15,19}\b", "[ID_CARD]"),
    (r"\b1[3-9]\d{9}\b", "[PHONE]"),
    (r"password\s*[:=]\s*\S+", "password=[REDACTED]"),
    (r"token\s*[:=]\s*\S+", "token=[REDACTED]"),
    (r"Bearer\s+\S+", "Bearer [REDACTED]"),
]
