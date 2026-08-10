"""
认证 API 模块

提供用户认证相关的API接口，包括：
- 用户登录
- 用户注册
- 令牌刷新
- 登出
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.transaction import safe_commit
from app.core.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.core.exceptions import ValidationError as BizValidationError
from app.core.security import PasswordPolicy, check_rate_limit, get_client_ip
from app.core.security import get_current_user as _get_current_user
from app.core.security import is_local_request
from app.core.security import verify_password
from app.core.token_manager import token_manager
from app.schemas.auth import LoginData, LoginRequest, LoginResponse, TwoFactorLoginVerifyRequest, UserInfo
from app.schemas.user import UserCreate
from app.services.user_service import UserService
from app.utils.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

# 登录专用速率限制参数：同一 IP 每分钟最多 5 次
_LOGIN_RATE_LIMIT = 5
_LOGIN_RATE_WINDOW = 60  # 秒

# 注册专用速率限制参数：同一 IP 每分钟最多 3 次
_REGISTER_RATE_LIMIT = 3
_REGISTER_RATE_WINDOW = 60  # 秒

# Token刷新速率限制参数：同一 IP 每分钟最多 10 次
_REFRESH_RATE_LIMIT = 10
_REFRESH_RATE_WINDOW = 60  # 秒

# 登录锁定参数（从配置统一读取，与 config.py 保持一致）
from app.core.config import settings as _settings  # noqa: E402

_MAX_FAILED_ATTEMPTS = _settings.MAX_FAILED_LOGIN_ATTEMPTS
_LOCKOUT_MINUTES = _settings.ACCOUNT_LOCKOUT_MINUTES
_PASSWORD_EXPIRE_DAYS = _settings.PASSWORD_EXPIRE_DAYS


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建JWT访问令牌（兼容旧调用）"""
    subject = data.get("sub", "")
    return token_manager.create_access_token(subject, expires_delta=expires_delta)


def _check_account_lockout(
    user, username: str, db: Session, now: Optional[datetime] = None
) -> None:
    """检查账户锁定状态并处理过期锁定自动清理。

    委托给 LockoutService 统一处理，供 login、refresh_token 等认证端点复用。
    """
    from app.services.lockout_service import get_lockout_service
    svc = get_lockout_service()
    svc.check_locked(user, username, db, now=now)


router = APIRouter(prefix="/auth", tags=["认证"])


def _handle_failed_login(user, username: str, db, now, client_ip: str, user_agent: str | None):
    """处理登录失败：递增计数、锁定、审计日志。"""
    failed_count = 0
    try:
        db.refresh(user)
        user.failed_login_count = (user.failed_login_count or 0) + 1
        failed_count = user.failed_login_count
        if failed_count >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
        safe_commit(db)
        logger.info(f"登录失败: user={username}, failed_count={failed_count}/{_MAX_FAILED_ATTEMPTS}")
        if failed_count >= _MAX_FAILED_ATTEMPTS:
            logger.warning(
                "账户已锁定: user=%s, 连续失败%d次, 锁定到%s",
                username, failed_count, now + timedelta(minutes=_LOCKOUT_MINUTES),
            )
    except Exception as e:
        logger.error(f"更新失败计数时出错: {e}", exc_info=True)
        db.rollback()
    AuditLogger.log_login(
        user_id=user.id, username=username, success=False,
        ip_address=client_ip, user_agent=user_agent,
        failure_reason=f"密码错误（失败{failed_count}次）",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """用户登录

    验证用户凭据并返回访问令牌。
    同一 IP 每分钟最多允许 5 次登录尝试。

    Args:
        login_request: 登录请求数据，包含用户名和密码
        request: HTTP 请求对象（用于获取客户端 IP）
        db: 数据库会话

    Returns:
        LoginResponse: 登录响应数据，包含访问令牌

    Raises:
        HTTPException: 当用户名或密码错误时抛出401错误
        HTTPException: 当超过速率限制时抛出429错误
    """
    # 登录速率限制
    client_ip = get_client_ip(request)
    is_allowed = await check_rate_limit(
        key=f"login:{client_ip}",
        limit=_LOGIN_RATE_LIMIT,
        window=_LOGIN_RATE_WINDOW,
    )
    if not is_allowed:
        logger.warning("登录速率限制触发: IP=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
        )

    user_service = UserService(db)
    user = user_service.get_user_by_username(login_request.username)

    if not user:
        # 记录登录失败审计日志
        AuditLogger.log_login(
            user_id=0,
            username=login_request.username,
            success=False,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            failure_reason="用户不存在",
        )
        raise InvalidCredentialsError()

    # 检查用户是否已激活（审核通过）
    if not user.is_active:
        logger.warning(f"未激活用户尝试登录: username={login_request.username}")
        AuditLogger.log_login(
            user_id=user.id,
            username=login_request.username,
            success=False,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            failure_reason="用户未激活",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的账户尚未激活，请联系管理员进行审核",
        )

    # 检查账户锁定状态
    now = datetime.now(timezone.utc)
    _check_account_lockout(user, login_request.username, db, now=now)

    if not verify_password(login_request.password, user.hashed_password):
        _handle_failed_login(
            user, login_request.username, db, now, client_ip,
            request.headers.get("user-agent"),
        )
        raise InvalidCredentialsError()

    # 验证机器码（如果用户已绑定机器码）
    from app.services.machine_code_service import MachineCodeService

    machine_service = MachineCodeService(db)
    current_machine_code = machine_service.get_machine_code()

    if not machine_service.verify_user_machine(user.id, current_machine_code):
        # 记录登录失败审计日志
        AuditLogger.log_login(
            user_id=user.id,
            username=login_request.username,
            success=False,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            failure_reason="未授权的机器",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您的账户未授权在此机器上登录，请联系管理员",
        )

    # ── 双因素认证检查 ──
    # 密码和机器码均通过后，检查用户是否启用了 2FA
    from app.services.two_factor_service import TwoFactorService

    if TwoFactorService.is_enabled(db, user):
        # 签发短期临时令牌（5分钟有效），用于 2FA 验证后换取正式令牌
        temp_tokens = token_manager.create_token_pair(
            user.username,
            extra_claims={"two_factor_pending": True},
            access_ttl_minutes=5,
        )
        return LoginResponse(
            code=200,
            data=None,
            message="需要双因素认证",
            two_factor_required=True,
            temp_token=temp_tokens["access_token"],
        )

    # 登录成功：重置失败计数和锁定状态
    if getattr(user, "failed_login_count", 0) or getattr(user, "locked_until", None):
        user.failed_login_count = 0
        user.locked_until = None
    user.last_login = now
    safe_commit(db)

    # 创建双Token（带 token_version，支持真正吊销）
    tokens = token_manager.create_token_pair(
        user.username,
        extra_claims={"token_version": user.token_version_safe},
    )
    access_token = tokens["access_token"]
    refresh_token_str = tokens["refresh_token"]

    # 确保管理员角色正确：is_superuser=True 时强制使用 super_admin 角色
    user_role = user.role or "user"
    if user.is_superuser and user_role not in ["admin", "super_admin"]:
        user_role = "super_admin"

    user_info = UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user_role,
        is_active=user.is_active if user.is_active is not None else True,
        is_superuser=user.is_superuser or user.role in ("admin", "super_admin"),
        organization_id=getattr(user, "organization_id", None),
        organization_name=getattr(user, "organization_name", "") or "",
        permissions=getattr(user, "permissions_list", []) or [],
        allowed_menus=getattr(user, "allowed_menus", None),
        allowed_menus_list=getattr(user, "allowed_menus_list", None),
    )

    must_change = getattr(user, "must_change_password", False) or False

    # 密码过期检查
    password_expired = False
    pw_changed_at = getattr(user, "password_changed_at", None)
    if pw_changed_at:
        if pw_changed_at.tzinfo is None:
            pw_changed_at = pw_changed_at.replace(tzinfo=timezone.utc)
        if (now - pw_changed_at).days > _PASSWORD_EXPIRE_DAYS:
            password_expired = True
            must_change = True

    msg = "登录成功"
    if must_change:
        msg = "密码已过期，请修改密码" if password_expired else "首次登录请修改密码"

    # 记录登录成功审计日志
    AuditLogger.log_login(
        user_id=user.id,
        username=user.username,
        success=True,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )

    return LoginResponse(
        code=200,
        data=LoginData(access_token=access_token, token_type="bearer", user=user_info),
        message=msg,
        must_change_password=must_change,
        refresh_token=refresh_token_str,
    )


@router.post("/two-factor/verify-login", response_model=LoginResponse)
async def two_factor_verify_login(
    verify_request: TwoFactorLoginVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """双因素认证登录验证

    使用登录时返回的 temp_token 和 TOTP 验证码完成二次验证，
    验证成功后返回正式的访问令牌。

    Args:
        verify_request: 包含 temp_token 和 TOTP 验证码
        request: HTTP 请求对象
        db: 数据库会话

    Returns:
        LoginResponse: 正式登录响应（含 access_token）
    """
    # 速率限制：复用登录限制
    client_ip = get_client_ip(request)
    is_allowed = await check_rate_limit(
        key=f"login:{client_ip}",
        limit=_LOGIN_RATE_LIMIT,
        window=_LOGIN_RATE_WINDOW,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="验证尝试过于频繁，请稍后再试",
        )

    # 验证 temp_token
    try:
        payload = token_manager.decode_token(verify_request.temp_token, expected_type="access")
    except Exception:
        payload = None

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="临时令牌无效或已过期，请重新登录",
        )

    # 确认是 2FA pending token
    if not payload.get("two_factor_pending"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的临时令牌",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的临时令牌",
        )

    # 查找用户
    user_service = UserService(db)
    user = user_service.get_user_by_username(username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )

    # 验证 TOTP / 备用码
    from app.services.two_factor_service import TwoFactorService

    if not TwoFactorService.verify_login(db, user, verify_request.code):
        AuditLogger.log_login(
            user_id=user.id,
            username=username,
            success=False,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            failure_reason="2FA验证码错误",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="验证码错误，请重试",
        )

    # 2FA 验证通过 — 吊销 temp_token，签发正式令牌
    token_manager.revoke_token(verify_request.temp_token)

    # 重置失败计数
    if getattr(user, "failed_login_count", 0) or getattr(user, "locked_until", None):
        user.failed_login_count = 0
        user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    safe_commit(db)

    # 创建正式双Token
    tokens = token_manager.create_token_pair(
        user.username,
        extra_claims={"token_version": user.token_version_safe},
    )
    access_token = tokens["access_token"]
    refresh_token_str = tokens["refresh_token"]

    # 构建用户信息
    user_role = user.role or "user"
    if user.is_superuser and user_role not in ["admin", "super_admin"]:
        user_role = "super_admin"

    user_info = UserInfo(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user_role,
        is_active=user.is_active if user.is_active is not None else True,
        is_superuser=user.is_superuser or user.role in ("admin", "super_admin"),
        organization_id=getattr(user, "organization_id", None),
        organization_name=getattr(user, "organization_name", "") or "",
        permissions=getattr(user, "permissions_list", []) or [],
        allowed_menus=getattr(user, "allowed_menus", None),
        allowed_menus_list=getattr(user, "allowed_menus_list", None),
    )

    must_change = getattr(user, "must_change_password", False) or False

    # 密码过期检查
    password_expired = False
    pw_changed_at = getattr(user, "password_changed_at", None)
    now = datetime.now(timezone.utc)
    if pw_changed_at:
        if pw_changed_at.tzinfo is None:
            pw_changed_at = pw_changed_at.replace(tzinfo=timezone.utc)
        if (now - pw_changed_at).days > _PASSWORD_EXPIRE_DAYS:
            password_expired = True
            must_change = True

    msg = "登录成功"
    if must_change:
        msg = "密码已过期，请修改密码" if password_expired else "首次登录请修改密码"

    AuditLogger.log_login(
        user_id=user.id,
        username=user.username,
        success=True,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )

    return LoginResponse(
        code=200,
        data=LoginData(access_token=access_token, token_type="bearer", user=user_info),
        message=msg,
        must_change_password=must_change,
        refresh_token=refresh_token_str,
    )


async def verify_token(token: str, token_type: str = "access_token") -> Optional[dict]:
    """验证令牌并返回用户信息

    使用 token_manager 统一解码（含黑名单检查 + LRU 缓存），
    避免绕过已吊销 token 的安全检查。

    Args:
        token: JWT令牌字符串
        token_type: 令牌类型

    Returns:
        Optional[dict]: 用户信息字典，验证失败返回None
    """
    try:
        payload = token_manager.decode_token(token)
        if not payload:
            return None
        username = payload.get("sub")
        if username is None:
            return None
        return {"username": username, "token_type": token_type}
    except Exception as e:
        logger.warning("Token验证失败: %s", e, exc_info=True)
        return None


@router.get("/me")
async def get_current_user_info(
    current_user=Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户信息"""
    user_service = UserService(db)
    user = user_service.get_user_by_username(current_user.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    # 确保管理员角色正确：is_superuser=True 时强制使用 super_admin 角色
    user_role = user.role or "user"
    if user.is_superuser and user_role not in ["admin", "super_admin"]:
        user_role = "super_admin"

    return {
        "code": 200,
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.full_name,
            "full_name": user.full_name,
            "role": user_role,
            "is_active": user.is_active if user.is_active is not None else True,
            "is_superuser": user.is_superuser or user.role in ("admin", "super_admin"),
            "organization_id": getattr(user, "organization_id", None),
            "organization_name": getattr(user, "organization_name", "") or "",
            "permissions": getattr(user, "permissions_list", []) or [],
        },
        "message": "ok",
    }


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> dict:
    """用户登出

    将当前 access_token 加入黑名单使其立即失效。
    可选在请求体中传递 refresh_token 一并吊销，防止已注销的 refresh_token 被重用。
    """
    # 获取用户信息用于审计日志
    user_id = None
    username = None
    if credentials and credentials.credentials:
        try:
            payload = token_manager.decode_token(credentials.credentials)
            if payload:
                username = payload.get("sub")
                # 从数据库获取用户ID
                if username:
                    user_service = UserService(db)
                    user = user_service.get_user_by_username(username)
                    if user:
                        user_id = user.id
        except Exception as e:
            logger.debug("从 token 获取用户信息失败: %s", e, exc_info=True)

    # 吊销 Authorization 头中的 access_token
    if credentials and credentials.credentials:
        token_manager.revoke_token(credentials.credentials)
    # 吊销请求体中的 refresh_token（可选，向后兼容空 body）
    try:
        body = await request.json()
        if isinstance(body, dict):
            refresh_token = body.get("refresh_token")
            if refresh_token and isinstance(refresh_token, str):
                token_manager.revoke_token(refresh_token)
    except Exception as e:
        logger.debug("吊销 refresh_token 失败，body 可能为空或非 JSON: %s", e)

    # 记录登出审计日志
    if user_id and username:
        client_ip = get_client_ip(request)
        from app.utils.audit_logger import AuditAction

        AuditLogger.log(
            action=AuditAction.LOGOUT,
            user_id=user_id,
            username=username,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )

    return {"code": 200, "message": "登出成功"}


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(request: Request, token: str = Body(..., embed=True), db: Session = Depends(get_db)) -> Any:
    """刷新访问令牌

    仅接受 refresh_token，返回新的 access_token + refresh_token 对。
    旧 refresh_token 会被立即吊销（轮换机制，防止重放攻击）。

    Args:
        token: refresh_token（通过请求体传递）
        db: 数据库会话

    Returns:
        LoginResponse: 新的访问令牌响应
    """
    # Token刷新速率限制
    client_ip = get_client_ip(request)
    is_allowed = await check_rate_limit(
        key=f"refresh:{client_ip}",
        limit=_REFRESH_RATE_LIMIT,
        window=_REFRESH_RATE_WINDOW,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="刷新频率过高，请稍后再试",
        )

    try:
        # 仅接受 refresh_token，不再回退接受 access_token
        payload = token_manager.decode_token(token, expected_type="refresh")
        if not payload:
            raise HTTPException(status_code=401, detail="无效的刷新令牌，请使用 refresh_token")

        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="无效的令牌")

        # 验证用户仍存在且活跃
        user_service = UserService(db)
        user = user_service.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="用户已被禁用")

        # 检查账户锁定状态
        _check_account_lockout(user, username, db)

        # 吊销旧 token（加入黑名单使其立即失效）
        token_manager.revoke_token(token)

        # 签发新的 token pair（轮换 refresh_token 防止重放攻击）
        new_tokens = token_manager.create_token_pair(
            username,
            extra_claims={"token_version": user.token_version_safe},
        )
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]

        user_info = UserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role or "user",
            is_active=user.is_active if user.is_active is not None else True,
            is_superuser=user.is_superuser or user.role in ("admin", "super_admin"),
            organization_id=getattr(user, "organization_id", None),
            organization_name=getattr(user, "organization_name", "") or "",
            permissions=getattr(user, "permissions_list", []) or [],
            allowed_menus=getattr(user, "allowed_menus", None),
            allowed_menus_list=getattr(user, "allowed_menus_list", None),
        )

        return LoginResponse(
            code=200,
            data=LoginData(access_token=new_access_token, token_type="bearer", user=user_info),
            message="令牌刷新成功",
            refresh_token=new_refresh_token,
        )

    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        logger.warning(f"Token refresh failed due to invalid token format: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌格式无效",
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期或无效",
        )


@router.get("/csrf-token")
async def get_csrf_token(request: Request, response: Response) -> dict:
    """获取 CSRF token

    前端在发起状态变更请求（POST/PUT/DELETE/PATCH）前，
    需要先调用此接口获取 CSRF token。接口会同时：
    1. 在响应体中返回 token（前端可缓存到内存）
    2. 在响应中设置 csrf_token Cookie（httponly=False，前端 JS 可读取）

    前端需在后续请求的 X-CSRF-Token 请求头中携带 token 原始值。

    Returns:
        dict: 包含 CSRF token 的响应
    """
    client_ip = get_client_ip(request)
    is_allowed = await check_rate_limit(
        key=f"csrf:{client_ip}",
        limit=30,
        window=60,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="CSRF token 请求过于频繁，请稍后再试",
        )

    from app.middleware.csrf_middleware import (
        CSRF_COOKIE_NAME,
        CSRF_TOKEN_EXPIRY,
        generate_csrf_token,
        sign_csrf_token,
    )

    token = generate_csrf_token()
    signed_token = sign_csrf_token(token)

    # 同时设置 cookie，确保前端 JS 可通过 document.cookie 读取
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,  # 存储原始 token
        max_age=CSRF_TOKEN_EXPIRY,
        httponly=False,  # 允许 JS 读取（Double Submit Cookie 模式必需）
        secure=_settings.ENVIRONMENT == "production" and not is_local_request(request),
        samesite="strict",
    )

    return {
        "code": 200,
        "data": {
            "csrf_token": token,
            "csrf_signed_token": signed_token,
        },
        "message": "CSRF token 获取成功",
    }


@router.post("/register", response_model=LoginResponse)
async def register_user(
    request: Request,
    username: str = Body(..., description="用户名"),
    password: str = Body(..., description="密码"),
    pass_code: str = Body(..., description="通行码（激活码）"),
    full_name: Optional[str] = Body(None, description="姓名"),
    email: Optional[str] = Body(None, description="邮箱"),
    db: Session = Depends(get_db),
) -> Any:
    """用户注册（通过通行码）

    普通用户可以使用管理员提供的通行码进行注册。
    注册成功后，用户账户将绑定到当前机器。

    Args:
        username: 用户名
        password: 密码
        pass_code: 通行码（由管理员生成）
        full_name: 姓名（可选）
        email: 邮箱（可选）
        db: 数据库会话

    Returns:
        LoginResponse: 注册成功后返回的访问令牌

    Raises:
        HTTPException: 通行码无效、用户名已存在、密码不符合策略
    """
    from app.services.machine_code_service import MachineCodeService

    # 注册速率限制
    client_ip = get_client_ip(request)
    is_allowed = await check_rate_limit(
        key=f"register:{client_ip}",
        limit=_REGISTER_RATE_LIMIT,
        window=_REGISTER_RATE_WINDOW,
    )
    if not is_allowed:
        logger.warning("注册速率限制触发: IP=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="注册尝试过于频繁，请稍后再试",
        )

    # 用户名验证
    is_valid, msg = PasswordPolicy.validate_username(username)
    if not is_valid:
        raise BizValidationError(message=msg, field="username")

    # 密码验证（传入用户名做弱密码检查）
    is_valid, msg = PasswordPolicy.validate(password, username=username)
    if not is_valid:
        raise BizValidationError(message=msg, field="password")

    # 获取当前机器码
    machine_service = MachineCodeService(db)
    current_machine_code = machine_service.get_machine_code()

    # 验证通行码（去除首尾空白，防止复制粘贴带入空格）
    machine_record = machine_service.verify_pass_code(pass_code.strip(), current_machine_code)
    if not machine_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="通行码无效或已被使用，请联系管理员获取新的通行码",
        )

    user_service = UserService(db)

    # 检查用户名是否已存在
    if user_service.get_user_by_username(username):
        raise UserAlreadyExistsError(username)

    # 检查邮箱唯一性
    if email and user_service.get_user_by_email(email):
        raise BizValidationError(message="该邮箱已被注册", field="email")

    try:
        # 创建用户数据
        user_create = UserCreate(
            username=username,
            password=password,
            email=email or f"{username}@local.system",
            full_name=full_name or username,
            role_id=None,
            is_active=True,
            is_superuser=False,
        )

        # 创建新用户（create_user 期望 dict；model_dump 转换 pydantic 对象）
        user = user_service.create_user(user_create.model_dump())

        # 激活机器码（绑定到用户）
        machine_service.activate_machine_code(machine_record, user.id)

        # 如果通行码关联了组织，自动绑定用户到该组织
        if machine_record.organization_id:
            user.organization_id = machine_record.organization_id
            safe_commit(db)
            logger.info(
                "用户 %s 已自动绑定到组织 id=%s",
                user.username,
                machine_record.organization_id,
            )

        # 创建访问令牌
        access_token = token_manager.create_access_token(user.username)

        user_info = UserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role or "user",
            is_active=user.is_active if user.is_active is not None else True,
            is_superuser=user.is_superuser or user.role in ("admin", "super_admin"),
            allowed_menus=getattr(user, "allowed_menus", None),
            allowed_menus_list=getattr(user, "allowed_menus_list", None),
        )

        logger.info(f"用户注册成功: username={username}, machine_code={current_machine_code[:16]}...")

        return LoginResponse(
            code=200,
            data=LoginData(access_token=access_token, token_type="bearer", user=user_info),
            message="注册成功",
        )

    except (HTTPException, UserAlreadyExistsError, BizValidationError):
        raise
    except Exception as e:
        logger.error("注册用户失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册失败，请稍后重试",
        )
