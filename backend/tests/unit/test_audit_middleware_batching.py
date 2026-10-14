"""审计中间件批量落库契约测试（2026-10-14 系统排查报告 H9）。

旧实现缺陷：每个非跳过请求结束后独立开 session 落库一次（含 GET），
SQLite 单写者模型下与业务事务形成第二个写者竞争，拖慢全站并使 -wal 膨胀。

新契约（语义变化详见 app/core/audit_middleware.py 模块 docstring）：
1. 每请求仅 O(1) 入内存缓冲，无任何 DB I/O；
2. 缓冲达到 _FLUSH_THRESHOLD（25 条）→ 由触发请求在线程池批量落库一次；
3. 不足阈值由 daemon 兜底线程每 _FLUSH_INTERVAL_SECONDS（5 秒）刷写（惰性启动）；
4. atexit 进程退出兜底最终 flush；
5. 落库失败仅 WARNING 并丢弃该批，绝不影响业务请求。
"""
import logging
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from app.core import audit_middleware as am
from app.core.audit_middleware import AuditMiddleware


# ════════════════════════════════════════════════════════════════
# 模块级状态隔离：缓冲 + 兜底线程在每个用例前后重置
# ════════════════════════════════════════════════════════════════
def _stop_flusher_and_clear():
    am._flush_stop_event.set()
    t = am._flusher_thread
    if t is not None and t is not threading.current_thread() and t.is_alive():
        t.join(timeout=2)
    am._flusher_thread = None
    with am._buffer_lock:
        am._buffer.clear()
    am._flush_stop_event.clear()


@pytest.fixture(autouse=True)
def _reset_audit_state():
    _stop_flusher_and_clear()
    yield
    _stop_flusher_and_clear()


def _request(path="/api/v1/funds", method="GET", client_ip="127.0.0.1"):
    client = SimpleNamespace(host=client_ip) if client_ip else None
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        method=method,
        headers={"user-agent": "pytest-agent"},
        client=client,
    )


def _fake_record(seq: int = 0) -> dict:
    """构造与 APIAccessLog 列一一对应的最小审计记录。"""
    return {
        "user_id": None,
        "username": None,
        "endpoint": "/api/v1/funds",
        "method": "GET",
        "response_status": 200,
        "response_time_ms": 5 + seq,
        "ip_address": "127.0.0.1",
        "user_agent": "pytest-agent",
    }


def _call_next():
    return mock.AsyncMock(return_value=SimpleNamespace(status_code=200))


# ════════════════════════════════════════════════════════════════
# 【改前证据】（已归档至修复报告，用例不保留在套件中）：
#   旧实现下 3 个请求 → 3 次 SessionLocal() 实例化（每请求一次独立写）；
#   新契约测试在旧代码上 15/15 失败（模块无 _flush_stop_event 等符号）。
# ════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════
# 缓冲契约：请求结束仅 O(1) 入缓冲，不产生任何落库 I/O
# ════════════════════════════════════════════════════════════════
class TestBuffering:
    @pytest.mark.asyncio
    async def test_below_threshold_no_db_io(self):
        """发 10 个请求（< 阈值 25）→ 0 次落库，记录完整滞留缓冲。"""
        call_next = _call_next()
        with mock.patch.object(am, "_persist_batch") as persist:
            with mock.patch.object(am, "_FLUSH_INTERVAL_SECONDS", 60):
                for _ in range(10):
                    await AuditMiddleware(app=None).dispatch(_request(), call_next)
        persist.assert_not_called()
        assert len(am._buffer) == 10
        record = am._buffer[0]
        assert record["endpoint"] == "/api/v1/funds"
        assert record["method"] == "GET"
        assert record["response_status"] == 200
        assert record["user_agent"] == "pytest-agent"
        assert record["ip_address"] == "127.0.0.1"
        assert record["user_id"] is None
        assert isinstance(record["response_time_ms"], int)

    @pytest.mark.asyncio
    async def test_manual_flush_persists_batch_once_and_empties(self):
        """手动触发 flush → 恰好一次批量落库，行数正确且缓冲清空。"""
        call_next = _call_next()
        with mock.patch.object(am, "_persist_batch") as persist:
            for _ in range(10):
                await AuditMiddleware(app=None).dispatch(_request(), call_next)
            persist.assert_not_called()
            am._flush_pending()
        persist.assert_called_once()
        batch = persist.call_args.args[0]
        assert len(batch) == 10
        assert batch[0]["endpoint"] == "/api/v1/funds"
        assert am._buffer == []

    @pytest.mark.asyncio
    async def test_request_without_client_ip_records_none(self):
        call_next = _call_next()
        await AuditMiddleware(app=None).dispatch(_request(client_ip=None), call_next)
        assert am._buffer[0]["ip_address"] is None

    @pytest.mark.asyncio
    async def test_flusher_thread_is_lazy_started_daemon(self):
        """兜底线程惰性启动：首次入缓冲才创建，且为 daemon。"""
        assert am._flusher_thread is None
        call_next = _call_next()
        with mock.patch.object(am, "_persist_batch"):
            await AuditMiddleware(app=None).dispatch(_request(), call_next)
        t = am._flusher_thread
        assert t is not None and t.daemon and t.is_alive()


# ════════════════════════════════════════════════════════════════
# 定量刷写：缓冲达到阈值 → 恰好一次批量落库
# ════════════════════════════════════════════════════════════════
class TestThresholdFlush:
    @pytest.mark.asyncio
    async def test_threshold_triggers_single_batch_flush(self):
        """发 25 个请求 → 恰好 1 次批量落库（25 行），缓冲清空。"""
        call_next = _call_next()
        with mock.patch.object(am, "_persist_batch") as persist:
            with mock.patch.object(am, "_FLUSH_INTERVAL_SECONDS", 60):
                for _ in range(am._FLUSH_THRESHOLD):
                    await AuditMiddleware(app=None).dispatch(_request(), call_next)
        persist.assert_called_once()
        batch = persist.call_args.args[0]
        assert len(batch) == am._FLUSH_THRESHOLD
        assert am._buffer == []


# ════════════════════════════════════════════════════════════════
# 定时兜底：不足阈值时推进时间 → 余量被刷掉
# ════════════════════════════════════════════════════════════════
class TestTimedFlush:
    def test_timer_flushes_remainder_below_threshold(self):
        with mock.patch.object(am, "_persist_batch") as persist:
            with mock.patch.object(am, "_FLUSH_INTERVAL_SECONDS", 0.05):
                am._enqueue_record(_fake_record(0))
                am._enqueue_record(_fake_record(1))
                deadline = time.monotonic() + 3
                while am._buffer and time.monotonic() < deadline:
                    time.sleep(0.02)
        assert am._buffer == []
        persist.assert_called_once()
        assert len(persist.call_args.args[0]) == 2

    def test_flusher_thread_stops_on_stop_event(self):
        am._enqueue_record(_fake_record())
        t = am._flusher_thread
        assert t is not None and t.is_alive()
        am._flush_stop_event.set()
        t.join(timeout=2)
        assert not t.is_alive()


# ════════════════════════════════════════════════════════════════
# 失败隔离：落库失败仅 WARNING 并丢弃该批，绝不影响请求
# ════════════════════════════════════════════════════════════════
class TestFailureIsolation:
    def test_flush_pending_empty_buffer_is_noop(self):
        with mock.patch.object(am, "_persist_batch") as persist:
            am._flush_pending()
        persist.assert_not_called()

    def test_persist_batch_empty_records_is_noop(self):
        with mock.patch("app.core.database.SessionLocal") as session_local:
            am._persist_batch([])
        session_local.assert_not_called()

    def test_session_factory_failure_discards_batch_with_warning(self, caplog):
        for seq in range(3):
            am._enqueue_record(_fake_record(seq))
        with mock.patch(
            "app.core.database.SessionLocal",
            side_effect=RuntimeError("数据库不可用"),
        ):
            with caplog.at_level(logging.WARNING, logger="app.core.audit_middleware"):
                am._flush_pending()  # 不应抛出
        assert am._buffer == []
        assert any(
            "批量落库失败" in r.message
            and "丢弃 3 条" in r.message
            and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_commit_failure_discards_batch_with_warning(self, caplog):
        am._enqueue_record(_fake_record())
        fake_db = mock.MagicMock()
        with mock.patch("app.core.database.SessionLocal", return_value=fake_db):
            with mock.patch(
                "app.core.audit_middleware.safe_commit",
                side_effect=RuntimeError("commit failed"),
            ):
                with caplog.at_level(logging.WARNING, logger="app.core.audit_middleware"):
                    am._flush_pending()  # 不应抛出
        fake_db.add_all.assert_called_once()
        fake_db.close.assert_called_once()
        assert am._buffer == []
        assert any(
            "批量落库失败" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_dispatch_returns_200_even_when_persist_fails(self, caplog):
        """定量刷写落库失败 → 请求仍 200，仅 WARNING。"""
        call_next = _call_next()
        with mock.patch.object(am, "_FLUSH_THRESHOLD", 1):
            with mock.patch(
                "app.core.database.SessionLocal",
                side_effect=RuntimeError("数据库不可用"),
            ):
                with caplog.at_level(logging.WARNING, logger="app.core.audit_middleware"):
                    response = await AuditMiddleware(app=None).dispatch(
                        _request(), call_next)
        assert response.status_code == 200
        assert am._buffer == []
        assert any(
            "批量落库失败" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )


# ════════════════════════════════════════════════════════════════
# 进程退出兜底：atexit 最终 flush
# ════════════════════════════════════════════════════════════════
class TestExitSafety:
    def test_final_flush_drains_remainder_and_sets_stop_event(self):
        with mock.patch.object(am, "_persist_batch") as persist:
            am._enqueue_record(_fake_record())
            am._final_flush()
        persist.assert_called_once()
        assert am._buffer == []
        assert am._flush_stop_event.is_set()

    def test_atexit_registration_on_import(self):
        """模块导入即注册 atexit 最终 flush。"""
        import importlib

        with mock.patch("atexit.register") as register:
            importlib.reload(am)
        register.assert_called_once_with(am._final_flush)
