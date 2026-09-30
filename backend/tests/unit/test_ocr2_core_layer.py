"""OCR 第二轮深审修复回归 —— core 层（part-B #7/#10/#13/#15/#20/#21 + part-C #81）+ part-C #80。

覆盖：
1. core/response.py：kwargs 不得覆盖信封保留键（success/code/message/data/errors/detail）；
2. core/money.py：NaN/Inf/超精度 → ValueError（Pydantic 归一为 422，不再 500）；
3. core/error_handler.py：AppError/NotFoundError 为规范类（不再静默降级为 Exception）；
4. core/audit_middleware.py：落库卸载到线程池（不阻塞事件循环）；
5. utils/api_error.py：with 块内 HTTPException 原样上抛（不再被改写成 500）；
6. utils/audit_logger.py：序列化失败绝不冒泡（循环引用降级为摘要）。
"""
import json
import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.core.audit_middleware import AuditMiddleware
from app.core.money import MoneyField, _quantize_4
from app.core.response import error_response, success_response
from app.utils.api_error import APIErrorHandler
from app.utils.audit_logger import AuditAction, AuditLogger, _safe_json


class TestResponseEnvelopeReservedKeys:
    """part-B #20/#21：业务 kwargs 不能覆盖信封字段。

    R16 精化：`success` 是唯一被显式允许的覆盖键（且只接受 bool）——
    `success_response` 的语义是"请求已受理"，但调用方需要表达
    "部分失败/降级"（rbac revoke 有失败项、monitor 读不到数据库文件）时必须生效。
    code/message/data/errors/detail 仍一律丢弃。
    """

    def test_success_response_ignores_reserved_kwargs(self, caplog):
        # errors/detail 不在函数签名里，只能经 **kwargs 传入 —— 必须被忽略
        with caplog.at_level(logging.WARNING, logger="app.core.response"):
            resp = success_response(
                data={"id": 1}, **{"errors": ["x"], "detail": "d"}
            )
        assert resp["success"] is True
        assert resp["code"] == 200
        assert resp["message"] == "success"
        assert resp["data"] == {"id": 1}
        assert "errors" not in resp and "detail" not in resp
        assert "保留键" in caplog.text

    def test_success_bool_override_is_honored(self):
        """显式 success=False 必须生效（部分失败语义，R16 修复静默丢弃）。"""
        assert success_response(data={}, success=False)["success"] is False
        assert success_response(success=False)["success"] is False
        assert success_response(success=True)["success"] is True

    def test_success_non_bool_override_rejected(self, caplog):
        """非 bool 覆盖值被忽略（防 **payload 透传获得任意写能力）。"""
        with caplog.at_level(logging.WARNING, logger="app.core.response"):
            resp = success_response(**{"success": "yes"})
        assert resp["success"] is True
        assert "非布尔" in caplog.text

    def test_error_response_keeps_status_and_success_false(self, caplog):
        # success/data 不在 error_response 签名里，只能经 **kwargs 传入
        with caplog.at_level(logging.WARNING, logger="app.core.response"):
            resp = error_response(code=403, message="无权限", **{"success": True, "data": {"a": 1}})
        assert resp["success"] is False
        assert resp["code"] == 403
        assert resp["message"] == "无权限"
        assert "data" not in resp

    def test_extra_non_reserved_keys_still_merged(self):
        resp = success_response(data=[1], page=2, total=5)
        assert resp["page"] == 2
        assert resp["total"] == 5
        assert resp["success"] is True


class TestMoneyFailClosed:
    """part-B #15：非法金额必须转成 ValueError（Pydantic → 422），不得 500。"""

    def test_none_becomes_zero(self):
        assert _quantize_4(None) == Decimal("0")

    def test_normal_value_quantized_half_up(self):
        assert _quantize_4("1.00005") == Decimal("1.0001")
        assert _quantize_4(Decimal("2.5")) == Decimal("2.5000")

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity"])
    def test_non_finite_rejected(self, bad):
        with pytest.raises(ValueError, match="有限数值"):
            _quantize_4(bad)

    def test_out_of_range_precision_rejected(self):
        with pytest.raises(ValueError, match="超出可量化范围"):
            _quantize_4(1e30)

    def test_unparsable_rejected(self):
        with pytest.raises(ValueError, match="金额格式非法"):
            _quantize_4("not-a-number")

    def test_money_field_nan_is_validation_error_not_500(self):
        class _Payload(BaseModel):
            amount: MoneyField = 0

        assert _Payload(amount="3.14159").amount == 3.1416
        with pytest.raises(ValidationError):
            _Payload(amount=float("nan"))
        with pytest.raises(ValidationError):
            _Payload(amount=1e30)


class TestErrorHandlerNoSilentDegrade:
    """part-B #10：导入失败不再静默把 AppError/NotFoundError 降级成 Exception。"""

    def test_aliases_are_canonical_exception_classes(self):
        from app.core import error_handler
        from app.core.exceptions import AppError, NotFoundError

        assert error_handler.AppError is AppError
        assert error_handler.NotFoundError is NotFoundError
        assert issubclass(AppError, Exception)

    def test_not_found_error_is_not_plain_exception(self):
        from app.core.error_handler import NotFoundError

        assert NotFoundError is not Exception


class TestAuditMiddlewareOffloadsDbWrite:
    """part-B #7：同步 DB 落库必须卸载到线程池，不阻塞事件循环。"""

    @pytest.mark.asyncio
    async def test_persist_runs_on_worker_thread(self):
        seen = {}

        def _record(**kwargs):
            seen["thread"] = threading.current_thread().name
            seen["path"] = kwargs["request"].url.path

        request = SimpleNamespace(
            url=SimpleNamespace(path="/api/v1/funds"),
            method="GET",
            headers={},
            client=SimpleNamespace(host="127.0.0.1"),
        )
        call_next = mock.AsyncMock(return_value=SimpleNamespace(status_code=200))
        with mock.patch.object(AuditMiddleware, "_persist_api_access_log", mock.MagicMock(side_effect=_record)):
            response = await AuditMiddleware(app=None).dispatch(request, call_next)

        assert response.status_code == 200
        assert seen["path"] == "/api/v1/funds"
        # 必须是工作线程（anyio worker thread），而不是事件循环所在的主线程
        assert seen["thread"] != threading.main_thread().name


class TestAPIErrorHandlerReraisesHTTPException:
    """part-C #80：403/404 不得被改写成默认 500。"""

    def test_http_exception_passthrough(self):
        with pytest.raises(HTTPException) as exc:
            with APIErrorHandler("获取列表"):
                raise HTTPException(status_code=403, detail="无权限访问")
        assert exc.value.status_code == 403
        assert exc.value.detail == "无权限访问"

    def test_generic_exception_becomes_500(self):
        with pytest.raises(HTTPException) as exc:
            with APIErrorHandler("获取列表"):
                raise RuntimeError("boom")
        assert exc.value.status_code == 500

    def test_no_exception_returns_false(self):
        with APIErrorHandler("获取列表") as handler:
            pass
        assert handler.__exit__(None, None, None) is False


class TestAuditLoggerSerialization:
    """part-C #81：details 含不可 JSON 化 / 循环引用时绝不冒泡。"""

    def test_safe_json_handles_datetime_and_decimal(self):
        payload = {"when": datetime.now(timezone.utc), "amount": Decimal("1.50")}
        parsed = json.loads(_safe_json(payload))
        assert parsed["amount"] == "1.50"
        assert isinstance(parsed["when"], str)

    def test_circular_reference_degrades_to_summary(self, caplog):
        payload = {"action": "update"}
        payload["self"] = payload
        with caplog.at_level(logging.WARNING, logger="app.utils.audit_logger"):
            out = _safe_json(payload)
        assert "serialization_error" in out
        assert "序列化失败" in caplog.text

    def test_log_with_unserializable_details_does_not_raise(self):
        class _Orm:  # 模拟 ORM 对象
            def __repr__(self):
                return "<Orm>"

        with mock.patch.object(AuditLogger, "_persist_to_db"):
            AuditLogger.log(
                action=AuditAction.UPDATE,
                user_id=1,
                username="alice",
                details={"orm": _Orm(), "amount": Decimal("9.99")},
            )
