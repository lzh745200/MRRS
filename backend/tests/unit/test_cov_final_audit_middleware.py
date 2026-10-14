"""覆盖 app.core.audit_middleware 缺口。

两部分：
1. JWT 解析成功路径（含 sub 非整数的兜底）；
2. ``_persist_batch`` 的批量落库失败兜底分支——审计落库失败绝不能
   破坏业务请求，只降级为 WARNING（军工合规：审计不可用不等于业务不可用）。

2026-10-14 H9 批量化改约：落库由"每请求一写"改为批量缓冲 + 定量/定时/
退出三重刷写（语义变化见模块 docstring）。原"每请求立即落库"的断言属于
锁定旧实现，已按新契约订正：请求结束仅 O(1) 入缓冲，落库发生在
flush（定量/定时/退出）时。
"""
import logging
import threading
from types import SimpleNamespace
from unittest import mock

import jwt
import pytest

from app.core import audit_middleware as am
from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings


# ── H9 批量化改约：隔离 audit_middleware 模块级缓冲/兜底线程 ──
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


def _make_request(token: str):
    return SimpleNamespace(headers={"Authorization": f"Bearer {token}"})


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _record(**overrides) -> dict:
    """构造与 APIAccessLog 列一一对应的最小审计记录。"""
    base = {
        "user_id": None,
        "username": None,
        "endpoint": "/api/v1/funds",
        "method": "GET",
        "response_status": 200,
        "response_time_ms": 5,
        "ip_address": "10.0.0.8",
        "user_agent": "pytest-agent",
    }
    base.update(overrides)
    return base


class TestExtractUserIdentity:
    """_extract_user_identity：decode 成功后的 sub/username 提取。"""

    def test_valid_token_with_int_sub(self):
        token = _encode({"sub": "123", "username": "alice"})
        user_id, username = AuditMiddleware._extract_user_identity(_make_request(token))
        assert user_id == 123
        assert username == "alice"

    def test_valid_token_with_non_int_sub_falls_back_to_none(self):
        # sub 无法转为 int → (None, username)，覆盖 except (TypeError, ValueError) 分支
        token = _encode({"sub": "not-an-int"})
        user_id, username = AuditMiddleware._extract_user_identity(_make_request(token))
        assert user_id is None
        assert username == "not-an-int"

    def test_no_bearer_header_returns_none_pair(self):
        request = SimpleNamespace(headers={})
        assert AuditMiddleware._extract_user_identity(request) == (None, None)

    def test_invalid_token_returns_none_pair(self):
        # 非法 token → jwt.decode 抛异常 → except 兜底 (None, None)
        user_id, username = AuditMiddleware._extract_user_identity(
            _make_request("not-a-valid-jwt"))
        assert user_id is None
        assert username is None


class TestPersistBatchFailureIsSwallowed:
    """_persist_batch：批量落库失败只记 WARNING 并丢弃该批，不外抛。"""

    def test_session_factory_failure_does_not_propagate(self, caplog):
        with mock.patch(
            "app.core.database.SessionLocal",
            side_effect=RuntimeError("数据库不可用"),
        ):
            with caplog.at_level(logging.WARNING, logger="app.core.audit_middleware"):
                am._persist_batch([_record(user_id=7, username="alice")])

        assert any(
            "批量落库失败" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_commit_failure_closes_session_and_does_not_propagate(self, caplog):
        fake_db = mock.MagicMock()
        with mock.patch("app.core.database.SessionLocal", return_value=fake_db):
            with mock.patch(
                "app.core.audit_middleware.safe_commit",
                side_effect=RuntimeError("commit failed"),
            ):
                with caplog.at_level(logging.WARNING, logger="app.core.audit_middleware"):
                    am._persist_batch([_record(response_status=500)])

        fake_db.add_all.assert_called_once()
        fake_db.close.assert_called_once()
        assert any(
            "批量落库失败" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_batch_without_client_ip_persists_ip_none(self):
        fake_db = mock.MagicMock()
        with mock.patch("app.core.database.SessionLocal", return_value=fake_db):
            with mock.patch("app.core.audit_middleware.safe_commit") as commit:
                am._persist_batch([_record(ip_address=None, response_status=204)])

        commit.assert_called_once_with(fake_db)
        logged = fake_db.add_all.call_args[0][0][0]
        assert logged.ip_address is None
        assert logged.endpoint == "/api/v1/funds"
        assert logged.user_agent == "pytest-agent"


def _dispatch_request(path: str):
    """构造 dispatch 所需的最小 request 替身。"""
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        method="GET",
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )


class TestDispatchSkipPrefixes:
    """dispatch 短路：健康检查/指标/静态资源/文档不入缓冲、不落库。"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        ["/health", "/metrics", "/favicon.ico", "/static/app.js",
         "/uploads/generic/a.pdf", "/docs", "/openapi.json"],
    )
    async def test_skip_paths_short_circuit(self, path):
        call_next = mock.AsyncMock(return_value=SimpleNamespace(status_code=200))
        result = await AuditMiddleware(app=None).dispatch(
            _dispatch_request(path), call_next)
        call_next.assert_awaited_once()
        assert am._buffer == []
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_business_path_is_buffered_then_batch_flushed(self):
        """新契约：业务路径请求结束仅入缓冲，flush 时一次批量落库。"""
        call_next = mock.AsyncMock(return_value=SimpleNamespace(status_code=200))
        with mock.patch.object(am, "_persist_batch") as persist:
            await AuditMiddleware(app=None).dispatch(
                _dispatch_request("/api/v1/funds"), call_next)
            call_next.assert_awaited_once()
            # 请求结束不立即落库（旧契约断言，已按 H9 新契约订正）
            persist.assert_not_called()
            assert len(am._buffer) == 1
            am._flush_pending()
            persist.assert_called_once()
            batch = persist.call_args.args[0]
        assert batch[0]["endpoint"] == "/api/v1/funds"
        assert batch[0]["response_status"] == 200
