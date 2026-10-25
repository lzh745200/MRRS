"""覆盖 app.core.exceptions 缺口：Pydantic 验证错误与全局异常处理器。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import register_exception_handlers


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    class _Payload(BaseModel):
        x: int

    @app.get("/trigger-validation")
    def _trigger_validation():
        # 端点内抛出 pydantic.ValidationError（非 FastAPI 请求校验错误）
        _Payload(x="not-an-int")

    @app.get("/trigger-generic")
    def _trigger_generic():
        raise RuntimeError("boom")

    return app


class TestExceptionHandlers:
    def test_pydantic_validation_error_returns_422(self):
        client = TestClient(_build_app(), raise_server_exceptions=False)
        resp = client.get("/trigger-validation")
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == 422
        # 2026-10-25：message 改为「请求参数验证失败」+ 首条中文明细，
        # 同时 detail 与 message 同值（兼容读 detail 的视图）。
        assert body["message"].startswith("请求参数验证失败")
        assert body["detail"] == body["message"]
        assert body["success"] is False
        assert isinstance(body["errors"], list) and body["errors"]
        # 明细只保留 loc/msg/type，且不回显 input（可能含明文密码）
        assert set(body["errors"][0]) == {"loc", "msg", "type"}

    def test_unhandled_exception_returns_500(self):
        client = TestClient(_build_app(), raise_server_exceptions=False)
        resp = client.get("/trigger-generic")
        assert resp.status_code == 500
        assert resp.json() == {"code": 500, "message": "服务器内部错误", "success": False}
