"""全局请求体大小限制中间件。

非文件上传端点限制为 10MB，防止恶意超大 JSON 请求。

策略（R2，2026-09-12 收紧）：
1. multipart/form-data 请求按 Content-Length 分级预检（原实现一律放行，
   端点层"先整包读入内存后校验"的防线无法阻止内存峰值，单请求即可 OOM）
2. 以下业务路径可能接收大 JSON 批量数据，也一并放行
3. 其余非 multipart 请求超过 10MB 返回 413

注：Content-Length 预检可拦截所有常规客户端（浏览器/axios/curl）；
Transfer-Encoding: chunked 的流式计量留待纯 ASGI 改造（见遗留风险计划 R2）。
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

# multipart 请求体分级上限（Content-Length 预检）
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


def _multipart_limit_for(path: str) -> int:
    """返回该路径的 multipart 请求体上限（前缀匹配取第一个命中的分级）。"""
    for prefix, limit in MULTIPART_BODY_LIMITS:
        if path.startswith(prefix):
            return limit
    return DEFAULT_MULTIPART_BODY_LIMIT


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        content_type = request.headers.get("content-type", "")

        is_multipart = "multipart/form-data" in content_type
        is_large_payload_path = any(
            request.url.path.startswith(p) for p in LARGE_PAYLOAD_PATH_PREFIXES
        )

        if is_multipart and content_length:
            # R2：multipart 分级预检（原实现一律放行 → 单请求可打爆内存）
            limit = _multipart_limit_for(request.url.path)
            try:
                if int(content_length) > limit:
                    logger.warning(
                        "multipart 请求体过大被拒绝: %s %s (%s bytes > %d)",
                        request.method,
                        request.url.path,
                        content_length,
                        limit,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                "上传内容超过大小限制 "
                                f"({limit // 1024 // 1024}MB)，请拆分或压缩后重试"
                            )
                        },
                    )
            except (ValueError, TypeError):
                pass

        if not is_multipart and not is_large_payload_path and content_length:
            try:
                if int(content_length) > self.max_body_size:
                    logger.warning(
                        "请求体过大被拒绝: %s %s (%s bytes)",
                        request.method,
                        request.url.path,
                        content_length,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"请求体超过大小限制 ({self.max_body_size // 1024 // 1024}MB)"},
                    )
            except (ValueError, TypeError):
                pass

        return await call_next(request)
