"""覆盖 app.core.audit_middleware 缺口。

两部分：
1. JWT 解析成功路径（含 sub 非整数的兜底）；
2. ``_persist_api_access_log`` 的落库失败兜底分支——审计落库失败绝不能
   破坏业务请求，只降级为 WARNING（军工合规：审计不可用不等于业务不可用）。
"""
import logging
from types import SimpleNamespace
from unittest import mock

import jwt

from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings


def _make_request(token: str):
    return SimpleNamespace(headers={"Authorization": f"Bearer {token}"})


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _persist_request():
    """构造 _persist_api_access_log 所需的最小 request 替身。"""
    return SimpleNamespace(
        client=SimpleNamespace(host="10.0.0.8"),
        headers={"user-agent": "pytest-agent"},
        url=SimpleNamespace(path="/api/v1/funds"),
        method="GET",
    )


class TestExtractUserIdentity:
    """_extract_user_identity 行 69-74：decode 成功后的 sub/username 提取。"""

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


class TestPersistApiAccessLogFailureIsSwallowed:
    """_persist_api_access_log 行 106-108：落库失败只记 WARNING，不外抛。"""

    def test_session_factory_failure_does_not_propagate(self, caplog):
        with mock.patch(
            "app.core.database.SessionLocal",
            side_effect=RuntimeError("数据库不可用"),
        ):
            with caplog.at_level(logging.WARNING, logger="app.core.audit_middleware"):
                AuditMiddleware._persist_api_access_log(
                    request=_persist_request(),
                    response_status=200,
                    duration_ms=12,
                    user_id=7,
                    username="alice",
                )

        assert any(
            "api_access_logs 落库失败" in r.message and r.levelno == logging.WARNING
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
                    AuditMiddleware._persist_api_access_log(
                        request=_persist_request(),
                        response_status=500,
                        duration_ms=30,
                        user_id=None,
                        username=None,
                    )

        fake_db.add.assert_called_once()
        fake_db.close.assert_called_once()
        assert any(
            "api_access_logs 落库失败" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )

    def test_missing_client_still_persists_without_ip(self):
        fake_db = mock.MagicMock()
        request = _persist_request()
        request.client = None
        with mock.patch("app.core.database.SessionLocal", return_value=fake_db):
            with mock.patch("app.core.audit_middleware.safe_commit") as commit:
                AuditMiddleware._persist_api_access_log(
                    request=request,
                    response_status=204,
                    duration_ms=5,
                    user_id=None,
                    username=None,
                )

        commit.assert_called_once_with(fake_db)
        logged = fake_db.add.call_args[0][0]
        assert logged.ip_address is None
        assert logged.endpoint == "/api/v1/funds"
        assert logged.user_agent == "pytest-agent"
