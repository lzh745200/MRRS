"""viewer 只读中间件（W24 产品决策，2026-10-19，Lead 拍板）。

背景
----
帮助文案与角色选项均声明 viewer（访客）"只能查看数据，不能新增/编辑/删除"，
但后端此前没有任何集中收敛点：只有 funds / fund_lifecycle / offline-map 等
少数模块自行判权，其余业务模块（帮扶村 / 政策 / 学校 / 项目 / 一户一档 …）
对 viewer 完全可写。逐模块补守卫既不彻底也易漂移，故在此集中实现：

- 已认证且令牌 role 为 viewer 的写请求（POST/PUT/PATCH/DELETE）在非白名单
  路径上一律 403；
- 判定所需的 role 来自令牌声明（core.security.build_auth_claims 写入），
  本中间件不查数据库；
- 解析失败 / 无令牌 / 旧令牌无 role 声明 → 放行（fail-open）：认证与授权仍由
  端点自身依赖（get_current_user 及其后的判权）完成，本层只是"只读语义"的
  集中兜底，不承担鉴权职责，绝不把未认证请求变成 403；
- 被拒绝请求写审计日志（AuditLogger，action=viewer_write_denied，含
  method/path/user_id），审计失败不影响 403 响应。

白名单（仅自服务写操作）
------------------------
只放行完成"账户自服务"所必需的写操作，避免首登强制改密 / 退出登录等链路被
本层锁死；业务数据写入一律拦截。个人待办状态（/todos）按决策默认拦截。

中间件顺序
----------
注册位置见 main.py 处注释：本层必须位于 Audit/RequestLogger 之内（后注册者在
外层，故注册在两者之后）以便被拒请求仍进访问审计，并位于 MaintenanceGate /
Metrics 之外（注册在它们之前），使已拒绝请求不触发检修闸门之外的指标与 DB 路径。
"""

import logging
import re
from typing import Optional, Tuple

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 写方法集合：GET/HEAD/OPTIONS 天然只读，不拦截（健康检查/探活均属 GET）。
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

DENIED_MESSAGE = "只读账户（viewer）无权执行写操作，请使用具备写权限的账号"

# 自服务写端点白名单（只放行"账户自身"操作，业务数据写入一律拦截）：
_SELF_SERVICE_WRITE_PATHS = (
    # 认证自服务：登录 / 注销 / 刷新 / 首登改密
    re.compile(r"^/api/v1/auth/(?:login|logout|refresh|change-password)$"),
    # 双因素认证校验（含 /auth/2fa/* 与 /auth/two-factor/* 两种历史形态）
    re.compile(r"^/api/v1/auth/2fa(?:/.*)?$"),
    re.compile(r"^/api/v1/auth/two-factor(?:/.*)?$"),
    # 其他一次性校验端点（verify-*）
    re.compile(r"^/api/v1/auth/verify-[^/]+$"),
    # 修改本人密码：首登强制改密链路必需，否则 must_change_password 的 viewer
    # 将永远无法完成改密（端点自身校验"仅本人/超管可改"）。
    re.compile(r"^/api/v1/users/\d+/password$"),
    # 个人通知偏好（站内信 / 邮件 / 免打扰）
    re.compile(r"^/api/v1/notifications/preferences(?:/.*)?$"),
    # 意见反馈提交
    re.compile(r"^/api/v1/feedback$"),
)


def _is_self_service_write(path: str) -> bool:
    """路径是否属于允许 viewer 执行的"账户自服务"写端点。"""
    return any(pattern.match(path) for pattern in _SELF_SERVICE_WRITE_PATHS)


def _scope_header(scope, header_name: bytes) -> Optional[str]:
    """从 ASGI scope 请求头取首个匹配值（不存在返回 None）。"""
    for name, value in scope.get("headers") or []:
        if name.lower() == header_name:
            return value.decode("latin-1")
    return None


def _bearer_token(scope) -> Optional[str]:
    """从 ASGI scope 的 Authorization 头取 Bearer token（无/格式不符返回 None）。"""
    authorization = _scope_header(scope, b"authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def resolve_viewer_identity(scope) -> Optional[Tuple[Optional[int], Optional[str]]]:
    """令牌为有效 viewer 时返回 (user_id, username)，否则 None。

    只做"签名有效 + role 声明为 viewer"的轻量判定，不查库、不校验黑名单 /
    token_version —— 那些由端点认证依赖负责；返回 None 一律放行。
    """
    token = _bearer_token(scope)
    if not token:
        return None
    try:
        from app.core.security import decode_token

        payload = decode_token(token)
    except Exception:
        logger.debug("viewer 只读中间件：令牌解析异常，放行由端点鉴权处理", exc_info=True)
        return None
    if not payload:
        return None
    raw_role = payload.get("role")
    if not raw_role:
        # 旧令牌（升级前签发）/ 非本系统令牌：fail-open，端点鉴权兜底。
        return None
    from app.core.constants import normalize_role

    if normalize_role(raw_role) != "viewer":
        return None
    return payload.get("uid"), payload.get("sub")


def _audit_denied(scope, user_id, username) -> None:
    """记录 viewer 写操作被拒审计（失败只记日志，绝不影响 403 响应）。"""
    try:
        from app.utils.audit_logger import AuditLevel, AuditLogger

        client = scope.get("client")
        AuditLogger.log(
            action="viewer_write_denied",
            user_id=user_id,
            username=username,
            resource_type="api",
            details={"method": scope.get("method"), "path": scope.get("path")},
            level=AuditLevel.WARNING,
            ip_address=client[0] if client else None,
            user_agent=_scope_header(scope, b"user-agent"),
        )
    except Exception:
        logger.warning("viewer 写操作拒绝审计写入失败", exc_info=True)


class ViewerReadOnlyMiddleware:
    """集中式 viewer 只读中间件（纯 ASGI：不读请求体、不查数据库）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") not in _WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        if _is_self_service_write(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        identity = resolve_viewer_identity(scope)
        if identity is None:
            await self.app(scope, receive, send)
            return
        user_id, username = identity
        _audit_denied(scope, user_id, username)
        response = JSONResponse(
            status_code=403,
            content={
                "code": 403,
                "message": DENIED_MESSAGE,
                "detail": DENIED_MESSAGE,
                "success": False,
            },
        )
        await response(scope, receive, send)
