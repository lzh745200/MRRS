"""补齐 app.utils.api_error 覆盖率缺口。

目标行：
- 96：safe_api_call 同步包装器对 HTTPException 直接 re-raise
- 119-128：APIErrorHandler.__exit__ 的异常语义（深审 #80 后为 fail-loud）
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.utils.api_error import APIErrorHandler, safe_api_call


class TestSafeApiCallSyncHttpException:
    def test_http_exception_reraised(self):
        @safe_api_call("测试操作")
        def boom():
            raise HTTPException(status_code=400, detail="bad request")

        with pytest.raises(HTTPException):
            boom()


class TestAPIErrorHandlerExit:
    def test_non_http_exception_delegates_to_handle_service_error(self):
        """普通异常交给 handle_service_error（真实实现会转 HTTPException，故此处以
        替身观测委派行为，并确认 __exit__ 不再自行吞掉异常——fail-loud，深审 #80）。"""
        with patch("app.utils.api_error.handle_service_error") as mock_handle:
            with pytest.raises(ValueError, match="boom"):
                with APIErrorHandler("测试操作"):
                    raise ValueError("boom")

        mock_handle.assert_called_once()
        assert mock_handle.call_args[0][0] == "测试操作"
        assert isinstance(mock_handle.call_args[0][1], ValueError)

    def test_non_http_exception_becomes_http_500(self):
        """未打替身时，普通异常被 handle_service_error 转为 HTTPException（真实语义）。"""
        with pytest.raises(HTTPException) as exc_info:
            with APIErrorHandler("测试操作"):
                raise ValueError("boom")

        assert exc_info.value.status_code == 500

    def test_http_exception_propagates_unchanged(self):
        """with 块内主动抛出的 HTTPException 原样上抛，状态码语义不被改写（深审 #80）。"""
        with pytest.raises(HTTPException) as exc_info:
            with APIErrorHandler("测试操作"):
                raise HTTPException(status_code=404, detail="not found")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "not found"

    def test_no_exception_returns_false(self):
        """无异常时 __exit__ 返回 False（不抑制）。"""
        handler = APIErrorHandler("测试操作")
        assert handler.__exit__(None, None, None) is False
