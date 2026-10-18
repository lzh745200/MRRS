"""覆盖 app.middleware.metrics_middleware 缺口：
- 行 65：慢请求记录超过上限时截断
- 行 144-145：非 HTTP scope（websocket/lifespan）直接透传
- W5-T11：路径动态段归一（路由模板 / UUID / 数字）与 _path_durations 容量上限
"""
import types

from unittest.mock import AsyncMock

from app.middleware.metrics_middleware import MetricsMiddleware, _MetricsStore, _normalize_path


class TestSlowRequestTruncation:
    def test_slow_requests_truncated_to_max(self):
        store = _MetricsStore()
        store._max_slow = 2

        for i in range(3):
            store.record("GET", f"/path-{i}", 200, 2.5)  # 超过默认慢阈值 1.0s

        assert len(store._slow_requests) == 2
        # 保留最近的两条
        assert store._slow_requests[0][1] == "/path-1"
        assert store._slow_requests[1][1] == "/path-2"


class TestNonHttpScope:
    async def test_websocket_scope_passthrough(self):
        app = AsyncMock()
        mw = MetricsMiddleware(app)
        scope = {"type": "websocket", "path": "/ws"}
        receive, send = AsyncMock(), AsyncMock()

        await mw(scope, receive, send)

        app.assert_awaited_once_with(scope, receive, send)


class TestNormalizePath:
    """W5-T11：路径动态段归一（UUID / 数字 → {id}）。"""

    def test_empty_path_returned_unchanged(self):
        assert _normalize_path("") == ""

    def test_numeric_segments_replaced(self):
        assert _normalize_path("/api/v1/projects/123/funds/456") == "/api/v1/projects/{id}/funds/{id}"

    def test_negative_numeric_segment_replaced(self):
        assert _normalize_path("/api/v1/items/-7") == "/api/v1/items/{id}"

    def test_uuid_segment_replaced(self):
        assert _normalize_path(
            "/api/v1/projects/3f2504e0-4f89-11d3-9a0c-0305e82c3301/tasks"
        ) == "/api/v1/projects/{id}/tasks"

    def test_static_path_unchanged(self):
        assert _normalize_path("/api/v1/projects") == "/api/v1/projects"


class TestPathDurationsCapacity:
    """W5-T11：_path_durations 容量上限（新增键归入 __other__ 桶）。"""

    def test_new_paths_collapse_into_other_bucket(self):
        store = _MetricsStore()
        store._max_path_keys = 2
        store.record("GET", "/a", 200, 0.01)
        store.record("GET", "/b", 200, 0.01)
        # 达上限后的新路径 → 归入 __other__（不新建键）
        store.record("GET", "/c", 200, 0.01)
        assert ("GET", "__other__") in store._path_durations
        assert ("GET", "/c") not in store._path_durations
        assert store._path_durations[("GET", "__other__")][1] == 1

        # 桶已存在：后续新路径复用同一桶
        store.record("GET", "/d", 200, 0.01)
        assert store._path_durations[("GET", "__other__")][1] == 2
        assert ("GET", "/d") not in store._path_durations

    def test_existing_path_still_recorded_at_capacity(self):
        store = _MetricsStore()
        store._max_path_keys = 1
        store.record("GET", "/a", 200, 0.01)
        store.record("GET", "/a", 200, 0.02)
        assert store._path_durations[("GET", "/a")][1] == 2


class TestMiddlewareMetricPath:
    """W5-T11：中间件记录键 = 路由模板优先，退化到归一化路径。"""

    @staticmethod
    def _make_app(route_path=None, set_route=True):
        async def app(scope, receive, send):
            if set_route:
                scope["route"] = types.SimpleNamespace(path=route_path)
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b""})

        return app

    async def _run(self, monkeypatch, app, path):
        from app.middleware import metrics_middleware as mm

        store = mm._MetricsStore()
        monkeypatch.setattr(mm, "metrics_store", store)
        monkeypatch.setattr(mm.settings, "METRICS_ENABLED", True, raising=False)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        mw = mm.MetricsMiddleware(app)
        await mw({"type": "http", "path": path, "method": "GET"}, receive, send)
        return store

    async def test_route_template_preferred(self, monkeypatch):
        store = await self._run(
            monkeypatch,
            self._make_app("/api/v1/projects/{project_id}"),
            "/api/v1/projects/123",
        )
        assert ("GET", "/api/v1/projects/{project_id}") in store._path_durations

    async def test_route_without_path_falls_back_to_normalized(self, monkeypatch):
        store = await self._run(monkeypatch, self._make_app(None), "/api/v1/projects/123")
        assert ("GET", "/api/v1/projects/{id}") in store._path_durations

    async def test_no_route_falls_back_to_normalized(self, monkeypatch):
        store = await self._run(
            monkeypatch, self._make_app(set_route=False), "/api/v1/projects/123"
        )
        assert ("GET", "/api/v1/projects/{id}") in store._path_durations
