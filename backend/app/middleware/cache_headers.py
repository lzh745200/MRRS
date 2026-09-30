"""HTTP 缓存头中间件 — 对静态/低变化数据添加 Cache-Control 头。

减少重复 API 请求的数据库查询：浏览器和前端可缓存 30s-5min。

OCR-2026-09-17 收紧：
1. 只对成功的 GET 响应注入（错误/重定向/写请求一律不加，避免 401/404/500
   被标成 public 缓存）。
2. 路由已显式设置 Cache-Control 时一律尊重（例如组织树端点的 no-store），
   中间件不得覆盖。
"""

from starlette.middleware.base import BaseHTTPMiddleware

# 缓存策略配置: (路径前缀, Cache-Control 值)
# 注意：统计/概览类端点不缓存——增删改后必须立即可见，否则用户体验为"数据没更新"。
CACHE_RULES = [
    # 筛选选项 / 字典数据 — 5 分钟（极少变化）
    ("/api/v1/supported-villages/filter-options", "public, max-age=300"),
    ("/api/v1/organizations/tree", "public, max-age=300"),
    # 静态资源 — 1 小时
    ("/assets/", "public, max-age=3600, immutable"),
    ("/images/", "public, max-age=3600, immutable"),
]


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """对匹配路径的成功 GET 响应添加 Cache-Control 响应头。"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # 仅成功的 GET：错误响应绝不缓存，写请求无缓存语义
        if request.method != "GET":
            return response
        if not 200 <= response.status_code < 300:
            return response
        # 尊重路由显式设置（no-store / no-cache / 自定义 max-age）
        if response.headers.get("cache-control"):
            return response

        path = request.url.path
        for prefix, cache_value in CACHE_RULES:
            if path.startswith(prefix):
                response.headers["Cache-Control"] = cache_value
                break
        return response
