"""维护模式闸门中间件（R7 · 遗留风险治理计划 2026-09-13）。

在维护窗口内拒绝**新的写请求**（503 + Retry-After），读请求原样放行。
注册位置：Audit/RequestLogger 之内、Metrics 之外 —— 被拒请求仍进审计与
访问日志，但不占用数据库与指标采集路径。

用法: app.add_middleware(MaintenanceGateMiddleware)
"""

from starlette.responses import JSONResponse

from app.core.maintenance import should_reject, status


class MaintenanceGateMiddleware:
    """ASGI 中间件：维护窗口内对写方法返回 503。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not should_reject(
            scope.get("method", ""), scope.get("path", "")
        ):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=503,
            content={
                "code": 503,
                "message": "系统正在执行备份恢复，写操作已临时暂停，请稍后重试",
                "data": {"maintenance": status()},
            },
            headers={"Retry-After": "5"},
        )
        await response(scope, receive, send)
