"""R32 覆盖率攻坚 —— app/core + app/middleware + app/main 语句 / 分支缺口补全。

覆盖：
- core/logging_config.py: 118-120（异常栈脱敏写入 exc_text）、121-123（渲染失败静默兜底）、
  154（JsonFormatter 输出 exception 字段）
- core/security.py: 589（限流总开关关闭时短路放行）、591 / 593（limit / window 回退 settings）
- core/token_blacklist.py: 164-166 / 168-169（节流全量清理 + debug 留痕）、
  170-176 / 181-188（永久条目超上限降级为超长 TTL）
- core/token_manager.py: 263（刷新令牌携带原令牌非保留声明）
- middleware/camel_to_snake.py: 75->74（跳过前导空白）、77（全空白 body）、140-141（响应信封补全异常兜底）
- main.py: 246->253（响应无 content-type 头时循环自然结束）

不写真实用户目录（secrets 隔离见 test_cov_gap_r32_secrets.py）。
"""

import asyncio
import json
import logging
import sys
import time
from unittest.mock import AsyncMock, MagicMock


# ══════════════════════════════════════════════════════════════════
#  app/core/logging_config.py
# ══════════════════════════════════════════════════════════════════


def _exc_record(msg="boom"):
    try:
        raise ValueError("身份证 110101199001011234")
    except ValueError:
        return logging.LogRecord("t", logging.ERROR, __file__, 1, msg, None, sys.exc_info())


class TestSensitiveDataFilterExcInfo:
    def test_exc_text_is_redacted(self):
        """有 exc_info 且 exc_text 为空 → 提前渲染并脱敏（118-120）。"""
        from app.core.logging_config import SensitiveDataFilter

        record = _exc_record()
        assert SensitiveDataFilter().filter(record) is True
        assert record.exc_text
        assert "110101199001011234" not in record.exc_text
        assert "***" in record.exc_text

    def test_exc_render_failure_is_swallowed(self, monkeypatch):
        """traceback 渲染抛错 → 静默保持 exc_text 为空，不阻断日志（121-123）。"""
        from app.core.logging_config import SensitiveDataFilter

        def _boom(self, exc_info):
            raise RuntimeError("cannot render traceback")

        monkeypatch.setattr(logging.Formatter, "formatException", _boom)
        record = _exc_record()
        assert SensitiveDataFilter().filter(record) is True
        assert not record.exc_text


class TestJsonFormatterExcInfo:
    def test_exception_field_present(self):
        """JsonFormatter 对带异常记录输出 exception 字段（154）。"""
        from app.core.logging_config import JsonFormatter

        out = JsonFormatter().format(_exc_record())
        assert "exception" in json.loads(out)


# ══════════════════════════════════════════════════════════════════
#  app/core/security.py
# ══════════════════════════════════════════════════════════════════


class TestCheckRateLimitSettingsFallback:
    async def test_disabled_short_circuits(self, monkeypatch):
        """RATE_LIMIT_ENABLED=False → 直接放行（589）。"""
        from app.core.config import settings
        from app.core.security import check_rate_limit

        monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False, raising=False)
        assert await check_rate_limit("r32-disabled", request=MagicMock()) is True

    async def test_limit_and_window_fall_back_to_settings(self, monkeypatch):
        """limit/window 未显式传入 → 回退 settings 每分钟额度与 60 秒窗口（591 / 593）。"""
        from app.core.config import settings
        from app.core.security import check_rate_limit

        monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 120, raising=False)
        assert await check_rate_limit("r32-defaults", request=MagicMock()) is True


# ══════════════════════════════════════════════════════════════════
#  app/core/token_blacklist.py
# ══════════════════════════════════════════════════════════════════


class TestBlacklistCleanup:
    def test_cleanup_removes_expired_and_logs(self, monkeypatch, caplog):
        """节流到期 → 全量清理过期条目并 debug 留痕（164-166 / 168-169）。"""
        import app.core.token_blacklist as tb

        monkeypatch.setattr(tb, "_blacklist", {"expired-jti": time.time() - 5})
        monkeypatch.setattr(tb, "_last_cleanup_at", 0.0)

        with caplog.at_level(logging.DEBUG, logger="app.core.token_blacklist"):
            tb._cleanup_expired()

        assert "expired-jti" not in tb._blacklist
        assert any("清理过期黑名单条目" in r.getMessage() for r in caplog.records)

    def test_permanent_overflow_is_degraded(self, monkeypatch, caplog):
        """永久条目超上限 → 最早溢出条目降级为超长 TTL 并 warning（170-176 / 181-188）。"""
        import app.core.token_blacklist as tb

        monkeypatch.setattr(
            tb, "_blacklist", {"p1": tb._PERMANENT, "p2": tb._PERMANENT, "p3": tb._PERMANENT}
        )
        monkeypatch.setattr(tb, "_last_cleanup_at", 0.0)
        monkeypatch.setattr(tb, "_MAX_PERMANENT_ENTRIES", 1)

        with caplog.at_level(logging.WARNING, logger="app.core.token_blacklist"):
            tb._cleanup_expired()

        degraded = [jti for jti, exp in tb._blacklist.items() if exp != tb._PERMANENT]
        assert len(degraded) == 2
        assert any("永久吊销条目超过上限" in r.getMessage() for r in caplog.records)


# ══════════════════════════════════════════════════════════════════
#  app/core/token_manager.py
# ══════════════════════════════════════════════════════════════════


class TestRefreshAccessToken:
    def test_carries_non_reserved_claims(self, monkeypatch):
        """刷新时必须把原令牌的非保留声明（token_version 等）带入新令牌（262-263）。"""
        import app.core.token_manager as tm

        monkeypatch.setattr(
            tm,
            "validate_token",
            lambda token, token_type="access": (True, {"sub": "u1", "token_version": 7}, None),
        )
        monkeypatch.setattr(tm, "revoke_token", lambda token, reason="": True)

        captured = {}

        def _create(subject, extra_claims=None, **kwargs):
            captured["subject"] = subject
            captured["extra_claims"] = extra_claims
            return {"access_token": "a", "refresh_token": "r"}

        monkeypatch.setattr(tm, "create_token_pair", _create)

        ok, pair, err = tm.refresh_access_token("refresh-token")
        assert ok is True and err is None
        assert pair == {"access_token": "a", "refresh_token": "r"}
        assert captured["subject"] == "u1"
        assert captured["extra_claims"] == {"token_version": 7}


# ══════════════════════════════════════════════════════════════════
#  app/middleware/camel_to_snake.py
# ══════════════════════════════════════════════════════════════════


class TestFirstNonWhitespaceByte:
    def test_skips_leading_whitespace(self):
        """前导空白字节 → 继续循环（75->74），最终命中 '{'。"""
        from app.middleware.camel_to_snake import _first_non_whitespace_byte

        assert _first_non_whitespace_byte(b" \t\r\n{}") == 0x7B

    def test_all_whitespace_returns_none(self):
        """全空白 / 空 body → None（77）。"""
        from app.middleware.camel_to_snake import _first_non_whitespace_byte

        assert _first_non_whitespace_byte(b" \t\r\n") is None
        assert _first_non_whitespace_byte(b"") is None


class TestCamelMiddlewareEnvelope:
    async def test_invalid_utf8_envelope_body_returns_original(self):
        """响应体首字节为 '{' 但非合法 UTF-8 → 解析异常兜底返回原响应（140-141）。"""
        from app.middleware.camel_to_snake import CamelToSnakeMiddleware

        mw = CamelToSnakeMiddleware(AsyncMock())
        request = MagicMock()
        request.headers.get.return_value = "application/json"
        request.body = AsyncMock(return_value=b"{}")

        response = MagicMock()
        response.headers.get.return_value = "application/json"
        response.status_code = 200
        response.body = b'{"a":\xff}'

        call_next = AsyncMock(return_value=response)
        result = await mw.dispatch(request, call_next)

        assert result is response


# ══════════════════════════════════════════════════════════════════
#  app/main.py
# ══════════════════════════════════════════════════════════════════


class TestPathAndCharsetMiddleware:
    def test_response_without_content_type_header(self):
        """响应头里没有 content-type → for 循环自然结束（246->253），头原样透传。"""
        from app.main import _PathAndCharsetMiddleware

        captured = []

        async def fake_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(message):
            captured.append(message)

        mw = _PathAndCharsetMiddleware(fake_app)
        scope = {"type": "http", "path": "/no-ct", "headers": [], "query_string": b""}
        asyncio.run(mw(scope, None, send))

        assert captured[0]["headers"] == []
