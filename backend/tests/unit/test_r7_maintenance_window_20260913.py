"""R7 维护窗口闸门回归（遗留风险治理计划 2026-09-13 · W3-W4 批次）。

覆盖 app/core/maintenance.py + middleware/maintenance_gate.py：
- 写请求拒绝 / 读请求放行 / 豁免路径（恢复入口自身）放行；
- enter/leave/status 状态机与幂等；
- wait_for_idle 的"立即空闲 / 轮询后空闲 / 超时继续"三分支；
- 恢复服务外层维护窗口（窗口内 is_active()=True、结果含 maintenance_window_ms）；
- /health 暴露维护状态。
"""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core import maintenance as mw


@pytest.fixture(autouse=True)
def _clean_maintenance_state():
    mw.leave()
    yield
    mw.leave()


class _CountingStore:
    """active_count() 可编排的替身（模拟在途请求数变化）。"""

    def __init__(self, values):
        self._values = list(values)
        self._lock = threading.Lock()
        self.calls = 0

    def active_count(self):
        with self._lock:
            self.calls += 1
            if len(self._values) > 1:
                return self._values.pop(0)
            return self._values[0]


# ══════════════════════════════════════════════════════════════════
# 判定与状态机
# ══════════════════════════════════════════════════════════════════


class TestShouldReject:
    def test_inactive_state_allows_everything(self):
        assert mw.is_active() is False
        assert mw.should_reject("POST", "/api/v1/schools") is False

    def test_active_state_rejects_writes_only(self):
        mw.enter("test")
        assert mw.should_reject("POST", "/api/v1/schools") is True
        assert mw.should_reject("put", "/api/v1/schools/1") is True
        assert mw.should_reject("PATCH", "/api/v1/schools/1") is True
        assert mw.should_reject("DELETE", "/api/v1/schools/1") is True
        assert mw.should_reject("GET", "/api/v1/schools") is False
        assert mw.should_reject("HEAD", "/api/v1/schools") is False

    def test_active_state_exempts_restore_and_shutdown(self):
        mw.enter("test")
        assert mw.should_reject("POST", "/api/v1/system/backup/restore") is False
        assert mw.should_reject("POST", "/api/v1/shutdown") is False

    def test_empty_method_or_path_is_safe(self):
        mw.enter("test")
        assert mw.should_reject("", "/api/v1/schools") is False
        assert mw.should_reject("POST", "") is True


class TestStateMachine:
    def test_enter_leave_roundtrip(self):
        mw.enter("restore_backup")
        state = mw.status()
        assert state["active"] is True
        assert state["reason"] == "restore_backup"
        assert state["since"]
        mw.leave()
        state = mw.status()
        assert state["active"] is False
        assert state["reason"] is None

    def test_enter_is_idempotent_and_leave_is_safe(self):
        mw.enter("a")
        mw.enter("b")
        assert mw.status()["reason"] == "b"
        mw.leave()
        mw.leave()  # 幂等：重复 leave 不抛
        assert mw.status()["active"] is False


# ══════════════════════════════════════════════════════════════════
# 等待在途请求归零
# ══════════════════════════════════════════════════════════════════


class TestWaitForIdle:
    def test_returns_immediately_when_idle(self, monkeypatch):
        store = _CountingStore([1])  # 仅当前恢复请求自身
        monkeypatch.setattr("app.middleware.metrics_middleware.metrics_store", store)
        waited = mw.wait_for_idle(timeout=1.0)
        assert waited >= 0
        assert store.calls == 1

    def test_waits_until_in_flight_drains(self, monkeypatch):
        from app.core import maintenance as mod

        store = _CountingStore([4, 3, 1])
        monkeypatch.setattr("app.middleware.metrics_middleware.metrics_store", store)
        monkeypatch.setattr(mod, "_POLL_INTERVAL_SECONDS", 0.01)
        waited = mw.wait_for_idle(timeout=5.0)
        assert store.calls == 3
        assert waited >= 0

    def test_timeout_still_returns(self, monkeypatch):
        from app.core import maintenance as mod

        store = _CountingStore([9])
        monkeypatch.setattr("app.middleware.metrics_middleware.metrics_store", store)
        monkeypatch.setattr(mod, "_POLL_INTERVAL_SECONDS", 0.01)
        started = time.perf_counter()
        mw.wait_for_idle(timeout=0.05)
        assert time.perf_counter() - started < 5.0
        assert store.calls > 1


# ══════════════════════════════════════════════════════════════════
# 维护窗口上下文
# ══════════════════════════════════════════════════════════════════


class TestMaintenanceWindow:
    def test_window_sets_and_clears_state(self, monkeypatch):
        from app.core import maintenance as mod

        store = _CountingStore([1])
        monkeypatch.setattr("app.middleware.metrics_middleware.metrics_store", store)
        seen = {}
        with mod.maintenance_window("restore_backup") as window:
            seen["active"] = mw.is_active()
            seen["reason"] = mw.status()["reason"]
            seen["waited"] = window.waited_ms
        assert seen["active"] is True
        assert seen["reason"] == "restore_backup"
        assert mw.is_active() is False
        assert mw.status()["last_window_ms"] >= 0
        assert mw.status()["last_waited_ms"] >= 0

    def test_window_clears_state_on_exception(self, monkeypatch):
        from app.core import maintenance as mod

        monkeypatch.setattr(
            "app.middleware.metrics_middleware.metrics_store", _CountingStore([1])
        )
        with pytest.raises(RuntimeError):
            with mod.maintenance_window("restore_backup"):
                raise RuntimeError("恢复途中炸了")
        assert mw.is_active() is False

    def test_elapsed_ms_zero_before_start(self):
        assert mw.MaintenanceWindow("x").elapsed_ms() == 0


# ══════════════════════════════════════════════════════════════════
# 中间件
# ══════════════════════════════════════════════════════════════════


def _gate_app():
    from app.middleware.maintenance_gate import MaintenanceGateMiddleware

    async def write_endpoint(request):
        return PlainTextResponse("written")

    async def read_endpoint(request):
        return PlainTextResponse("read")

    app = Starlette(
        routes=[
            Route("/api/v1/schools", write_endpoint, methods=["POST"]),
            Route("/api/v1/schools", read_endpoint, methods=["GET"]),
            Route("/api/v1/system/backup/restore", write_endpoint, methods=["POST"]),
        ]
    )
    app.add_middleware(MaintenanceGateMiddleware)
    return TestClient(app)


class TestMaintenanceGateMiddleware:
    def test_writes_pass_when_inactive(self):
        client = _gate_app()
        assert client.post("/api/v1/schools").status_code == 200

    def test_reads_pass_when_active(self):
        mw.enter("restore_backup")
        client = _gate_app()
        assert client.get("/api/v1/schools").status_code == 200

    def test_writes_rejected_when_active(self):
        mw.enter("restore_backup")
        client = _gate_app()
        resp = client.post("/api/v1/schools")
        assert resp.status_code == 503
        assert resp.headers["Retry-After"] == "5"
        body = resp.json()
        assert body["code"] == 503
        assert body["data"]["maintenance"]["active"] is True

    def test_exempt_path_still_served(self):
        mw.enter("restore_backup")
        client = _gate_app()
        assert client.post("/api/v1/system/backup/restore").status_code == 200


# ══════════════════════════════════════════════════════════════════
# 恢复服务接线 + /health 可见性
# ══════════════════════════════════════════════════════════════════


class TestRestoreIntegration:
    def test_restore_runs_inside_window(self, monkeypatch, tmp_path):
        from app.services.backup_service import BackupService

        monkeypatch.setattr(
            "app.middleware.metrics_middleware.metrics_store", _CountingStore([1])
        )
        observed = {}

        def fake_impl(self, backup_file_path, password=None):
            observed["active"] = mw.is_active()
            observed["reason"] = mw.status()["reason"]
            return {"success": True}

        monkeypatch.setattr(BackupService, "_restore_backup_impl", fake_impl, raising=True)
        svc = BackupService.__new__(BackupService)
        result = BackupService.restore_backup(svc, str(tmp_path / "b.zip"))
        assert observed["active"] is True
        assert observed["reason"] == "restore_backup"
        assert mw.is_active() is False
        assert result["success"] is True
        assert "maintenance_window_ms" in result

    def test_health_exposes_maintenance_status(self):
        from app.main import app

        mw.enter("restore_backup")
        try:
            resp = TestClient(app).get("/health")
        finally:
            mw.leave()
        assert resp.status_code == 200
        maintenance = resp.json()["maintenance"]
        assert maintenance["active"] is True
        assert maintenance["reason"] == "restore_backup"


class TestMetricsActiveCount:
    def test_active_count_tracks_increment_and_decrement(self):
        from app.middleware.metrics_middleware import metrics_store

        before = metrics_store.active_count()
        metrics_store.inc_active()
        assert metrics_store.active_count() == before + 1
        metrics_store.dec_active()
        assert metrics_store.active_count() == before
