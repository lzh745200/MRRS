"""
认证 API 模块

提供用户认证相关的API接口，包括：
- 用户登录
- 令牌刷新
- 登出

账号不再支持自助注册：账号由管理员或权限包创建。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.constants import normalize_role
from app.core.database import get_db
from app.core.response import success_response
from app.core.transaction import safe_commit
from app.core.exceptions import InvalidCredentialsError
from app.core.security import build_auth_claims, check_rate_limit, get_client_ip
from app.core.security import enforce_credential_not_expired
from app.core.security import get_current_user as _get_current_user
from app.core.security import is_local_request
from app.core.security import verify_password
from app.core.token_manager import token_manager
from app.schemas.auth import LoginData, LoginRequest, LoginResponse, TwoFactorLoginVerifyRequest, UserInfo
from app.services.user_service import UserService
from app.utils.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


def _user_info_is_superuser(user) -> bool:
    """登录响应契约中的超级管理员标记（单一事实源）。

    只认同「真超管」：数据库 ``is_superuser`` 标志，或 ``role == "super_admin"``。
    部门级管理员（``role == "admin"``）**不得**被标记为超管——此前
    ``user.is_superuser or normalize_role(user.role) in ADMIN_ROLES`` 把
    部门级 admin 也标成 is_superuser=True，而后端内部的严格口径
    （core/permission_utils.is_superuser、menus.py 超管菜单豁免、数据权限 R28）
    只认真超管，于是前端所有 ``is_superuser === true`` 判定（菜单旁路、
    模块权限代理、角色选项过滤等）都被污染：部门级 admin 在本地被当成超管
    显示全量菜单/全量 tab/全部权限，而后端按严格口径拒绝——正是
    menu.ts 注释所警告的「本地可见、后端拒绝」不一致。
    """
    if getattr(user, "is_superuser", False):
        return True
    return normalize_role(getattr(user, "role", None)) == "super_admin"


# 登录专用速率限制参数：同一 IP 每分钟最多 5 次
_LOGIN_RATE_LIMIT = 5
_LOGIN_RATE_WINDOW = 60  # 秒

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


def _handle_failed_login(
    user,
    username: str,
    db,
    now,
    client_ip: str,
    user_agent: str | None,
    failure_reason: str = "密码错误",
):
    """处理认证失败：递增计数、达阈值锁定、写审计日志。

    返回本次失败后的累计失败次数，供调用方决定是否进一步处置
    （例如 2FA 失败达阈值时吊销临时令牌）。
    """
    failed_count = 0
    try:
        # W2-T6：经 lockout_service 原子递增（SQL 端 COALESCE+CASE+RETURNING），
        # 达到阈值自动设置 locked_until，替代此处读-改-写。
        from app.services.lockout_service import get_lockout_service

        failed_count = get_lockout_service().record_failed(user, db)
        if failed_count >= _MAX_FAILED_ATTEMPTS:
            logger.warning(
                "账户已锁定: user=%s, 连续失败%d次, 锁定至%s",
                username, failed_count, now + timedelta(minutes=_LOCKOUT_MINUTES),
            )
    except Exception as e:
        logger.error(f"更新失败计数时出错: {e}", exc_info=True)
        db.rollback()
    AuditLogger.log_login(
        user_id=user.id, username=username, success=False,
        ip_address=client_ip, user_agent=user_agent,
        failure_reason=f"{failure_reason}（失败{failed_count}次）",
    )
    return failed_count


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
        request=request,
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

    # P3：账号开通包的初始 OTP 有独立有效期，过期后必须由管理员重置。
    from app.core.security import enforce_credential_not_expired

    enforce_credential_not_expired(user, now, request)

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

    # 登录成功：先判定是否首登，再写 last_login（顺序不能反）
    was_first_login = getattr(user, "last_login", None) is None
    if getattr(user, "failed_login_count", 0) or getattr(user, "locked_until", None):
        user.failed_login_count = 0
        user.locked_until = None
    user.last_login = now
    safe_commit(db)

    # 创建双Token（带 token_version，支持真正吊销）
    tokens = token_manager.create_token_pair(
        user.username,
        extra_claims=build_auth_claims(user),
    )
    access_token = tokens["access_token"]
    refresh_token_str = tokens["refresh_token"]

    # 登记登录会话（2026-10-14）：使"活跃会话列表 / 按会话精确吊销"可用。
    # 失败只记日志、不阻断登录（见 session_service.record_login_session）。
    from app.services.session_service import record_login_session

    record_login_session(db, user, tokens, request)

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
        is_superuser=_user_info_is_superuser(user),
        organization_id=getattr(user, "organization_id", None),
        organization_name=getattr(user, "organization_name", "") or "",
        permissions=getattr(user, "permissions_list", []) or [],
        allowed_menus=getattr(user, "allowed_menus_list", None),
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
        is_first_login=was_first_login,
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
        request=request,
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
    except Exception as exc:  # noqa: BLE001 - 任何解码失败都视为无效令牌
        # 不是静默兜底：解码失败的原因（过期 / 被篡改 / 密钥不匹配）必须留痕，
        # 否则线上只能看到 401，分不清是用户令牌过期还是服务端密钥配置错。
        logger.info("二次验证临时令牌解码失败: %s", exc)
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

    # 已锁定账户直接拒绝（与 /auth/login 同口径：锁定期间不再校验任何凭据）
    _check_account_lockout(user, username, db)

    # 验证 TOTP / 备用码
    from app.services.two_factor_service import TwoFactorService

    if not TwoFactorService.verify_login(db, user, verify_request.code):
        # W15 深审 #4：2FA 校验失败必须与登录路径同口径——计入失败计数，
        # 达阈值时锁定账户并吊销 temp_token。修复前失败只写审计日志、既不计数
        # 也不吊销临时令牌，攻击者凭一个 temp_token 即可无限次枚举动态码。
        failed_count = _handle_failed_login(
            user,
            username,
            db,
            datetime.now(timezone.utc),
            client_ip,
            request.headers.get("user-agent"),
            failure_reason="2FA验证码错误",
        )
        if failed_count >= _MAX_FAILED_ATTEMPTS:
            token_manager.revoke_token(verify_request.temp_token)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"账户已锁定，请{_LOCKOUT_MINUTES}分钟后再试",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="验证码错误，请重试",
        )

    # 2FA 验证通过 — 吊销 temp_token，签发正式令牌
    token_manager.revoke_token(verify_request.temp_token)

    # 重置失败计数；先判定首登，再写 last_login
    was_first_login = getattr(user, "last_login", None) is None
    if getattr(user, "failed_login_count", 0) or getattr(user, "locked_until", None):
        user.failed_login_count = 0
        user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    safe_commit(db)

    # 创建正式双Token
    tokens = token_manager.create_token_pair(
        user.username,
        extra_claims=build_auth_claims(user),
    )
    access_token = tokens["access_token"]
    refresh_token_str = tokens["refresh_token"]

    # 登记登录会话（2026-10-14）：使"活跃会话列表 / 按会话精确吊销"可用。
    # 失败只记日志、不阻断登录（见 session_service.record_login_session）。
    from app.services.session_service import record_login_session

    record_login_session(db, user, tokens, request)

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
        is_superuser=_user_info_is_superuser(user),
        organization_id=getattr(user, "organization_id", None),
        organization_name=getattr(user, "organization_name", "") or "",
        permissions=getattr(user, "permissions_list", []) or [],
        allowed_menus=getattr(user, "allowed_menus_list", None),
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
        is_first_login=was_first_login,
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
            "is_superuser": _user_info_is_superuser(user),
            "organization_id": getattr(user, "organization_id", None),
            "organization_name": getattr(user, "organization_name", "") or "",
            "permissions": getattr(user, "permissions_list", []) or [],
        },
        "message": "ok",
    }


def _bump_token_version(db: Session, username):
    """W1-T5 (ADR-0001): bump token_version so all existing JWTs die immediately."""
    try:
        if not username:
            return
        _svc_user = UserService(db).get_user_by_username(username)
        if _svc_user is None:
            return
        setattr(_svc_user, "token_version",
                (getattr(_svc_user, "token_version", 0) or 0) + 1)
        safe_commit(db)
    except Exception as e:
        db.rollback()
        logger.warning("bump token_version failed on logout: %s", e)


def _audit_logout(request: Request, user_id, username):
    """Write logout audit log."""
    if not (user_id and username):
        return
    client_ip = get_client_ip(request)
    from app.utils.audit_logger import AuditAction

    AuditLogger.log(
        action=AuditAction.LOGOUT,
        user_id=user_id,
        username=username,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )


def _resolve_identity_from_token(db: Session, credentials):
    """从 Bearer token 解析 (user_id, username)，失败静默（登出尽力而为）。"""
    if not (credentials and credentials.credentials):
        return None, None
    try:
        payload = token_manager.decode_token(credentials.credentials)
        username = payload.get("sub") if payload else None
        if not username:
            return None, None
        user = UserService(db).get_user_by_username(username)
        return (user.id if user else None), username
    except Exception as e:
        logger.debug("从 token 获取用户信息失败: %s", e, exc_info=True)
        return None, None


async def _revoke_request_tokens(request: Request, credentials):
    """吊销请求携带的 access/refresh token（refresh 可选，向后兼容空 body）。"""
    if credentials and credentials.credentials:
        token_manager.revoke_token(credentials.credentials)
    try:
        body = await request.json()
        if isinstance(body, dict):
            refresh_token = body.get("refresh_token")
            if refresh_token and isinstance(refresh_token, str):
                token_manager.revoke_token(refresh_token)
    except Exception as e:
        logger.debug("吊销 refresh_token 失败，body 可能为空或非 JSON: %s", e)


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
    user_id, username = _resolve_identity_from_token(db, credentials)

    # 吊销本次请求携带的令牌
    await _revoke_request_tokens(request, credentials)

    # W1-T5（ADR-0001）：递增 token_version 使该用户全部现存 JWT（含
    # 未随请求提交的其他会话/被窃 refresh token）立即失效。
    _bump_token_version(db, username)
    _audit_logout(request, user_id, username)

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
        request=request,
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

        username = cast(str, payload.get("sub"))
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

        # P3 闭合：初始凭据过期必须同时拦截 refresh，而不能只拦登录。
        # 否则开通包账号在 credential_expires_at 过后，仍可用旧 refresh token
        # 持续换发 access，最长可绕过到每日停机任务执行。
        enforce_credential_not_expired(user, datetime.now(timezone.utc), request)

        # W1-T5（ADR-0001）token_version 吊销校验 —— refresh 链路此前**缺失**：
        # validate_token 只验签名/jti 黑名单/type，不比对版本；而 access 链路
        # （security.get_current_user）有该校验。后果：登出（_bump_token_version）
        # 或管理员强退（system/admin.py 递增 token_version）之后，**未随登出请求提交**的
        # refresh token（其他设备的、或被窃的）不在 jti 黑名单里，仍能换发一枚
        # 带"新版本号"的合法 access —— 版本吊销在 refresh 面完全失效。
        # 这里补齐与 access 链路同口径的比对；不改版本即 401 并吊销该 refresh。
        _payload_version = payload.get("token_version")
        _current_version = getattr(user, "token_version_safe", 0) or 0
        if _payload_version is None or int(_payload_version) != _current_version:
            token_manager.revoke_token(token, "token_version 不匹配")
            logger.warning(
                "refresh 被拒：token_version 不匹配 user=%s payload=%s current=%s",
                username, _payload_version, _current_version,
            )
            raise HTTPException(status_code=401, detail="令牌已失效，请重新登录")

        # 会话跟随令牌轮换：jti 必须在吊销旧令牌之前取出（入黑名单后再解析会失败）；
        # 会话行的更新在下方新令牌签发后执行，否则"按会话吊销"会吊销到已废弃的旧 jti
        # （表面成功、实际失效的安全缺口）。
        old_session_jti = payload.get("jti")

        # 吊销旧 token（加入黑名单使其立即失效）
        token_manager.revoke_token(token)

        # 签发新的 token pair（轮换 refresh_token 防止重放攻击）
        new_tokens = token_manager.create_token_pair(
            username,
            extra_claims=build_auth_claims(user),
        )
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]

        # 把会话指向新 jti（见上方 old_session_jti 说明）
        from app.services.session_service import update_session_on_refresh

        update_session_on_refresh(db, old_session_jti, new_tokens)

        user_info = UserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role or "user",
            is_active=user.is_active if user.is_active is not None else True,
            is_superuser=_user_info_is_superuser(user),
            organization_id=getattr(user, "organization_id", None),
            organization_name=getattr(user, "organization_name", "") or "",
            permissions=getattr(user, "permissions_list", []) or [],
            allowed_menus=getattr(user, "allowed_menus_list", None),
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
        request=request,
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

    # W5-T009: cookie 存储 HMAC 签名版本；前端从响应体取 raw token 放 header
    # 中间件验证: HMAC(header) == cookie
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=signed_token,  # 存储 HMAC 签名（W5-T009 升级）
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


@router.get("/public-config", summary="登录页公开配置（无需登录）")
async def public_config() -> Any:
    """登录页需要的公开配置（**不含任何敏感信息**，可公开）。

    产品不提供自助注册（账号由管理员或权限包创建），故本端点**不再**返回
    ``self_register_enabled``。只保留登录页必需的**非敏感**策略参数：

    ``lockout_minutes`` / ``max_failed_attempts`` —— 后端会返回
    ``423 账户已锁定，请X分钟后再试`` 与 ``429 登录尝试过于频繁``，
    前端据此显示锁定倒计时与剩余尝试次数。

    刻意**不**返回的字段（避免"看着有、其实假"）：
    * 单位名称 / 单位码等组织信息 —— 登录前不泄露部署单位身份；
    * 全局"是否强制 2FA" —— 本系统 2FA 是**按用户**开启（``users.two_factor_enabled``），
      不存在全局开关；硬造一个恒为 false 的字段只会误导调用方。
    """
    return success_response(data={
        "lockout_minutes": int(_LOCKOUT_MINUTES),
        "max_failed_attempts": int(_MAX_FAILED_ATTEMPTS),
    })
