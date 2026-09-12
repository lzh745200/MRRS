"""
CSRF 保护中间件（W5-T009：HMAC 签名校验升级）

实现 Double Submit Cookie 模式（HMAC 签名增强）：
1. 前端调用 GET /api/v1/auth/csrf-token 获取 raw_token
2. 服务器设置 csrftoken Cookie = HMAC-SHA256(raw_token)（签名版本）
3. 前端在 X-CSRF-Token 头中携带 raw_token（原始版本）
4. 服务器验证：HMAC(header_value) == cookie_value（常量时间比较）

向后兼容：若 cookie/header 为明文（旧版），回退明文比对 + warning 日志。
过期检测：token 内嵌时间戳（{ts}.{random}），超出 CSRF_TOKEN_EXPIRY 即拒绝。

安全基线：即使单机部署也应启用 CSRF 保护，防止同源跨站请求攻击。
"""

import hashlib
import hmac
import logging
import os
import time
from typing import List, Optional

from starlette.datastructures import Headers
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# CSRF Cookie 名称
CSRF_COOKIE_NAME = "csrftoken"

# CSRF Token 有效期（秒），默认 24 小时
CSRF_TOKEN_EXPIRY = 86400

# CSRF 请求头名称
CSRF_HEADER_NAME = "X-CSRF-Token"

# 安全请求方法（无需 CSRF 验证）
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# CSRF 豁免路径前缀（无需 CSRF 验证）
_CSRF_EXEMPT_PATH_PREFIXES: List[str] = [
    "/api/v1/auth/csrf-token",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/shutdown",
    "/health",
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]

# 可信代理 IP 前缀（配置项 TRUSTED_PROXIES 逗号分隔；
# 未配置时仅信任直连 IP，不读取 X-Forwarded-For —— fail-closed）。
_TRUSTED_PROXIES: List[str] = [
    p.strip() for p in os.environ.get("TRUSTED_PROXIES", "").split(",") if p.strip()
]


def generate_csrf_token() -> str:
    """生成 CSRF token

    格式: ``{timestamp}.{random_hex}``
    时间戳内嵌便于过期校验（精确到秒，24h 窗口足够；同一用户多次
    刷新 token 不影响已有 token 在窗口期内有效）。
    """
    ts = int(time.time())
    rand = os.urandom(24).hex()
    return f"{ts}.{rand}"


def sign_csrf_token(token: str, secret_key: Optional[str] = None) -> str:
    """对 CSRF token 进行 HMAC-SHA256 签名

    使用 CSRF_SECRET_KEY 对原始 token 签名，防止 token 篡改。
    前端将签名版本存储在 csrftoken Cookie 中；header 中携带原始 token；
    中间件通过 ``hmac.compare_digest(cookie, HMAC(header))`` 验证。

    Args:
        token: 原始 CSRF token（含时间戳前缀的明文）
        secret_key: 签名密钥，默认从 settings 读取

    Returns:
        HMAC-SHA256 十六进制签名
    """
    if secret_key is None:
        from app.core.config import settings

        secret_key = settings.CSRF_SECRET_KEY or settings.SECRET_KEY

    if isinstance(secret_key, str):
        secret_key = secret_key.encode("utf-8")
    if isinstance(token, str):
        token = token.encode("utf-8")

    return hmac.new(secret_key, token, hashlib.sha256).hexdigest()


def _extract_timestamp(token: str) -> Optional[int]:
    """从 token 中提取时间戳前缀（格式 {ts}.{random}）

    Returns:
        Unix 时间戳（int）或 None（明文 token 无时间戳）
    """
    dot = token.find(".")
    if dot <= 0:
        return None
    try:
        return int(token[:dot])
    except ValueError:
        return None


def _token_expired(token: str) -> bool:
    """检查 token 是否超过 CSRF_TOKEN_EXPIRY 窗口"""
    ts = _extract_timestamp(token)
    if ts is None:
        return False  # 旧格式无时间戳，不做过期判定（避免拒绝合法旧 token）
    return (time.time() - ts) > CSRF_TOKEN_EXPIRY


def _is_path_exempt(path: str) -> bool:
    """检查请求路径是否在 CSRF 豁免列表中"""
    for prefix in _CSRF_EXEMPT_PATH_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def get_client_ip(scope: dict) -> str:
    """获取客户端真实 IP（fail-closed 代理透传）—— 纯 ASGI scope 版（E1）。

    未配置 TRUSTED_PROXIES 时直接返回 scope["client"][0]（直连 IP）；
    配置后检查直连 IP 是否在可信代理列表中，可信时透传 X-Forwarded-For
    首段（真实客户端），不可信时降级为直连 IP（防止伪造 XFF 绕过限流/审计）。

    配置示例::

        TRUSTED_PROXIES=10.0.0.1,172.16.0.0/12
    """
    client = scope.get("client") or ("unknown", 0)
    direct_ip = client[0] if client else "unknown"
    if not _TRUSTED_PROXIES:
        return direct_ip

    # 检查直连 IP 是否为可信代理
    direct_trusted = False
    for trusted in _TRUSTED_PROXIES:
        if "/" in trusted:
            try:
                import ipaddress
                if ipaddress.ip_address(direct_ip) in ipaddress.ip_network(trusted, strict=False):
                    direct_trusted = True
                    break
            except (ValueError, TypeError):
                pass
        elif direct_ip == trusted:
            direct_trusted = True
            break

    if not direct_trusted:
        return direct_ip

    # 直连 IP 可信 → 透传 X-Forwarded-For 首段（真实客户端）
    headers = Headers(scope=scope)
    forwarded_for = headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return direct_ip


class CSRFMiddleware:
    """CSRF 保护中间件（HMAC 签名验证）—— 纯 ASGI 实现（架构评估 E1）。

    历史问题：原实现基于 ``BaseHTTPMiddleware``，其自身注释即承认会导致
    h11 协议错误（流式/大 body 请求形态下），"开=带病、关=裸奔"两难。
    本实现改为纯 ASGI 中间件（直接操作 scope/receive/send），不再经过
    BaseHTTPMiddleware 的响应缓冲与任务包装，消除协议层冲突；
    验证逻辑与原实现逐分支一致。

    验证逻辑:
    1. 非 HTTP scope（lifespan/websocket）直接放行
    2. GET/HEAD/OPTIONS 请求直接放行
    3. 豁免路径直接放行
    4. POST/PUT/DELETE/PATCH 请求需要携带有效的 X-CSRF-Token 头
    5. 新流程：HMAC(header_value) == cookie_value（签名验证）
    6. 回退：cookie/header 明文相同（旧版兼容，warning 日志）
    7. 过期检测：token 内嵌时间戳超过 CSRF_TOKEN_EXPIRY 即拒绝
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # 非 HTTP scope（lifespan 等）直接放行
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 延迟导入避免循环依赖
        from app.core.config import settings

        # CSRF 未启用时直接放行
        if not getattr(settings, "CSRF_ENABLED", False):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")

        # 安全方法直接放行
        if method in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        # 豁免路径直接放行
        if _is_path_exempt(path):
            await self.app(scope, receive, send)
            return

        # 本机内部通道豁免：Electron 自动备份携带启动时注入环境变量的
        # X-Internal-Backup 密钥（与 shutdown 端点同一内部密钥模式）
        internal_key = os.getenv("INTERNAL_BACKUP_KEY", "")
        if internal_key and headers.get("X-Internal-Backup", "") == internal_key:
            await self.app(scope, receive, send)
            return

        # ── 状态变更请求（POST/PUT/DELETE/PATCH）验证 CSRF token ──
        cookies = self._parse_cookies(headers)
        csrf_cookie = cookies.get(CSRF_COOKIE_NAME, "")
        csrf_header = headers.get(CSRF_HEADER_NAME, "")

        if not csrf_cookie or not csrf_header:
            client_ip = get_client_ip(scope)
            logger.warning(
                "CSRF 验证失败：缺少 token | method=%s path=%s cookie=%s header=%s ip=%s",
                method,
                path,
                "present" if csrf_cookie else "missing",
                "present" if csrf_header else "missing",
                client_ip,
            )
            response = self._forbidden("CSRF 验证失败：请先调用 GET /api/v1/auth/csrf-token 获取 token")
            await response(scope, receive, send)
            return

        # ── 过期检测 ──
        # 优先检查 header（raw token 含时间戳）；若为旧格式则检查 cookie
        if _token_expired(csrf_header) or _token_expired(csrf_cookie):
            logger.warning(
                "CSRF 验证失败：token 已过期 | method=%s path=%s",
                method,
                path,
            )
            response = self._forbidden("CSRF token 已过期，请重新获取")
            await response(scope, receive, send)
            return

        # ── HMAC 签名校验（新流程）──
        # cookie = HMAC(raw_token)，header = raw_token
        # 验证：HMAC(header) == cookie
        signed_header = sign_csrf_token(csrf_header)
        if hmac.compare_digest(signed_header, csrf_cookie):
            await self.app(scope, receive, send)
            return

        # ── 回退：明文比对（旧版兼容，warning 标记退化路径）──
        if hmac.compare_digest(csrf_cookie, csrf_header):
            logger.warning(
                "CSRF 验证通过（退化路径：明文比对，建议升级前端使用签名流程）"
                " | method=%s path=%s ip=%s",
                method,
                path,
                get_client_ip(scope),
            )
            await self.app(scope, receive, send)
            return

        # ── 两种验证均失败 ──
        logger.warning(
            "CSRF 验证失败：token 不匹配 | method=%s path=%s ip=%s",
            method,
            path,
            get_client_ip(scope),
        )
        response = self._forbidden("CSRF token 无效或已过期，请重新获取")
        await response(scope, receive, send)

    @staticmethod
    def _parse_cookies(headers: Headers) -> dict:
        """从请求头解析 Cookie（纯 ASGI：不经 Request.cookies 以减少对象构建）。

        与原实现的 `Request.cookies` 保持等价：starlette 走
        `http.cookies._unquote`，会把 RFC 6265 允许的**带引号值**去掉引号
        （如 `csrftoken="1757....abc"`）。此处显式去引号，避免该形态在
        E1 改写后从"通过"变成 403。
        """
        cookies: dict = {}
        for raw in headers.getlist("cookie"):
            for part in raw.split(";"):
                name, _, value = part.strip().partition("=")
                if name:
                    cookies[name] = value.strip().strip('"')
        return cookies

    @staticmethod
    def _forbidden(message: str) -> Response:
        return JSONResponse(
            status_code=403,
            content={"code": 403, "message": message, "data": None},
        )
