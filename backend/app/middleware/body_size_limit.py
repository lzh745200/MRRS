"""全局请求体大小限制中间件。

非文件上传端点限制为 10MB，防止恶意超大 JSON 请求。

策略（OCR-2026-09-17 收紧）：
1. 不信任客户端声明的 Content-Length：所有受限请求按 ASGI 消息流累计
   **真实**字节数，累计超限即中断下游读取（伪造小 Content-Length 无效）。
   Content-Length 预检仅作为"提前拒绝"的快速路径，不作为放行依据。
2. multipart/form-data 只对确实接收上传的路径放宽（分级上限）；其余路径
   伪造该 Content-Type 也一律按全局上限判定，无法绕过 10MB 限制。
3. Content-Length 头存在但畸形（非十进制/负数）时 fail-closed 返回 400，
   不再静默放行。
4. 以下业务路径可能接收大 JSON 批量数据，非 multipart 请求沿用放行策略
   （这些端点自身有限长读取防线）。
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 可能接收大体积 JSON / 批量数据的路径前缀
# 这些端点要么直接处理文件上传，要么处理大批量 JSON 导入/批量操作
LARGE_PAYLOAD_PATH_PREFIXES = (
    # 文件上传 / 导入导出
    "/api/v1/import",
    "/api/v1/import-export",
    "/api/v1/data-sync",
    "/api/v1/data/packages",
    # 业务模块（含文件上传或批量操作端点）
    "/api/v1/schools",
    "/api/v1/policies",
    "/api/v1/projects",
    "/api/v1/funds",
    "/api/v1/supported-villages",
    "/api/v1/rural-works",
    "/api/v1/rural-tasks",
    "/api/v1/report-templates",
    "/api/v1/permission-packages",
    # 系统管理（备份恢复、配置包导入）
    "/api/v1/system/backup",
    "/api/v1/system/config-package",
    # 批量操作
    "/api/v1/batch",
    # 用户（头像上传）
    "/api/v1/users",
)

# multipart 请求体分级上限（仅用于确实接收上传的路径）
# 各上传端点自身业务上限更严格（Excel 10MB / 头像 2MB / 附件 50MB），
# 这里只兜底防「超大 body 打爆内存」：
MULTIPART_BODY_LIMITS = (
    # 备份恢复需支持最大 10GB 压缩包（对齐 system/backup._MAX_RESTORE_UPLOAD_BYTES）
    ("/api/v1/system/backup", 10 * 1024 * 1024 * 1024),
    # 权限包导入 512MB（对齐 permission_package API 上限）
    ("/api/v1/permission-packages", 512 * 1024 * 1024),
    # 数据同步导入 512MB
    ("/api/v1/data-sync", 512 * 1024 * 1024),
)
# 其余 multipart 端点默认上限
DEFAULT_MULTIPART_BODY_LIMIT = 512 * 1024 * 1024

# 仅按媒体类型（忽略 boundary 等参数）精确匹配，避免子串匹配被伪造绕过
MULTIPART_MEDIA_TYPE = "multipart/form-data"


def _multipart_limit_for(path: str) -> int:
    """返回该路径的 multipart 请求体上限（前缀匹配取第一个命中的分级）。"""
    for prefix, limit in MULTIPART_BODY_LIMITS:
        if path.startswith(prefix):
            return limit
    return DEFAULT_MULTIPART_BODY_LIMIT


def _declared_content_length(request: Request):
    """解析 Content-Length 头。

    Returns:
        整数值；头不存在返回 None。

    Raises:
        ValueError: 头存在但畸形（非十进制、负数、空串）。
    """
    raw = request.headers.get("content-length")
    if raw is None:
        return None
    value = raw.strip()
    if not value.isdigit():
        raise ValueError(f"malformed content-length: {raw!r}")
    return int(value)


def _resolve_body_limit(request: Request, max_body_size: int):
    """计算本次请求允许的累计字节上限；None 表示不限（批量 JSON 端点）。"""
    path = request.url.path
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    is_upload_path = any(path.startswith(p) for p in LARGE_PAYLOAD_PATH_PREFIXES)

    if media_type == MULTIPART_MEDIA_TYPE:
        multipart_limit = _multipart_limit_for(path)
        if is_upload_path:
            return multipart_limit
        # 非上传路径伪造 multipart 头：收紧到全局上限，防止绕过 10MB 限制
        return min(multipart_limit, max_body_size)
    if is_upload_path:
        return None
    return max_body_size


class _BodyTooLarge(Exception):
    """流式累计字节超限（内部信号，用于中断下游请求体读取）。"""

    def __init__(self, received: int, limit: int):
        super().__init__(f"request body exceeded {limit} bytes (received {received})")
        self.received = received
        self.limit = limit


def _is_body_too_large(exc: BaseException) -> bool:
    """异常（可能是 anyio TaskGroup 包装的 ExceptionGroup）是否源自本中间件超限信号。"""
    if isinstance(exc, _BodyTooLarge):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(_is_body_too_large(item) for item in exc.exceptions)
    return False


class _StreamingBodyGuard:
    """按真实字节数判定请求体上限的 ASGI receive 包装器。

    只累计 http.request 消息体中实际到达的字节，与客户端声明的
    Content-Length 无关；超限立即抛 _BodyTooLarge 中断请求处理。
    """

    def __init__(self, receive, limit: int):
        self._receive = receive
        self._limit = limit
        self._received = 0

    @property
    def received(self) -> int:
        return self._received

    async def receive(self):
        message = await self._receive()
        if message.get("type") == "http.request":
            body = message.get("body") or b""
            self._received += len(body)
            if self._received > self._limit:
                raise _BodyTooLarge(self._received, self._limit)
        return message


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        is_multipart = media_type == MULTIPART_MEDIA_TYPE

        try:
            declared = _declared_content_length(request)
        except ValueError as exc:
            logger.warning(
                "畸形 Content-Length 被拒绝: %s %s (%s)",
                request.method,
                path,
                exc,
            )
            return JSONResponse(
                status_code=400,
                content={"detail": "Content-Length 请求头非法"},
            )

        limit = _resolve_body_limit(request, self.max_body_size)

        # 快速路径：声明值已超限时无需读取请求体
        if limit is not None and declared is not None and declared > limit:
            return self._reject_413(request, limit, is_multipart)

        receive = getattr(request, "_receive", None)
        if limit is not None and receive is not None:
            # 慢路径：按真实到达字节兜底（伪造小 Content-Length 在此被拦下）
            guard = _StreamingBodyGuard(receive, limit)
            request._receive = guard.receive
            try:
                response = await call_next(request)
            except BaseException as exc:  # noqa: BLE001 - 仅识别自身上限信号，其余原样抛出
                if not _is_body_too_large(exc):
                    raise
                logger.warning(
                    "请求体流式超限被拒绝: %s %s (limit=%d, exception=%s)",
                    request.method,
                    path,
                    limit,
                    exc,
                )
                return self._reject_413(request, limit, is_multipart)
            return response

        return await call_next(request)

    @staticmethod
    def _reject_413(request: Request, limit: int, is_multipart: bool) -> JSONResponse:
        logger.warning(
            "请求体过大被拒绝: %s %s (%dMB 上限)",
            request.method,
            request.url.path,
            limit // 1024 // 1024,
        )
        if is_multipart:
            detail = (
                "上传内容超过大小限制 "
                f"({limit // 1024 // 1024}MB)，请拆分或压缩后重试"
            )
        else:
            detail = f"请求体超过大小限制 ({limit // 1024 // 1024}MB)"
        return JSONResponse(status_code=413, content={"detail": detail})
