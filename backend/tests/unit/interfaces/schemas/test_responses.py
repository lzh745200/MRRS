"""
统一响应模型测试

测试 app/interfaces/schemas/responses.py 模块
"""
import pytest
from app.interfaces.schemas.responses import BaseResponse, ResponseModel


class TestResponseModel:
    def test_default_values(self):
        resp = ResponseModel()
        assert resp.code == 200
        assert resp.data is None
        assert resp.message == "success"
        assert resp.success is True  # 与 success_response 信封对齐（前端 res.success 判断依赖）

    def test_custom_values(self):
        resp = ResponseModel(code=404, data={"error": "not found"}, message="Not Found")
        assert resp.code == 404
        assert resp.data == {"error": "not found"}
        assert resp.message == "Not Found"


class TestBaseResponse:
    def test_success_default(self):
        resp = BaseResponse.success()
        assert resp.code == 200
        assert resp.data is None
        assert resp.message == "success"

    def test_success_with_data(self):
        resp = BaseResponse.success(data={"id": 1, "name": "test"})
        assert resp.code == 200
        assert resp.data == {"id": 1, "name": "test"}
        assert resp.message == "success"

    def test_success_with_custom_message(self):
        resp = BaseResponse.success(data="ok", message="操作成功")
        assert resp.message == "操作成功"
        assert resp.data == "ok"

    def test_success_with_custom_code(self):
        resp = BaseResponse.success(data=[], message="created", code=201)
        assert resp.code == 201

    def test_error_default(self):
        resp = BaseResponse.error()
        assert resp.code == 400
        assert resp.data is None
        assert resp.message == "error"

    def test_error_with_message(self):
        resp = BaseResponse.error(message="参数错误")
        assert resp.code == 400
        assert resp.message == "参数错误"

    def test_error_with_custom_code(self):
        resp = BaseResponse.error(message="未授权", code=401)
        assert resp.code == 401
        assert resp.message == "未授权"

    def test_error_with_data(self):
        resp = BaseResponse.error(message="验证失败", code=422, data={"field": "name"})
        assert resp.code == 422
        assert resp.data == {"field": "name"}

    def test_generic_type_inference(self):
        resp = BaseResponse[int](data=42)
        assert resp.data == 42

    def test_serialization(self):
        resp = BaseResponse.success(data="hello")
        d = resp.model_dump()
        assert d == {"code": 200, "data": "hello", "message": "success"}
