# -*- coding: utf-8 -*-
"""422 校验错误中文化的单元测试。

背景（2026-10-25 反馈）：用户看到 `Request failed with status code 422`。
根因是 FastAPI 的 ``RequestValidationError`` 未被接管 —— 返回的 ``detail``
是**英文数组**且**回显 input**，前端按字符串读 ``detail`` 落空后把 axios
原文展示给用户；input 里可能含明文密码。

本测试锁住三件事：
1. 文案是中文且可读（含字段名）；
2. ``detail`` 是字符串（前端所有取值路径都能拿到）；
3. 响应体**不含 input**（密码等敏感值不回显）。
"""

import pytest
from fastapi.testclient import TestClient

from app.core.validation_errors import (
    MAX_ERROR_ITEMS,
    MAX_MESSAGE_ITEMS,
    _field_label,
    _type_message,
    build_validation_error_payload,
)


class TestFieldLabel:
    @pytest.mark.parametrize(
        "loc,expected",
        [
            (["body", "username"], "用户名"),
            (["query", "page_size"], "每页条数"),
            (["path", "id"], "ID"),
            (["body", "unknown_field"], "unknown_field"),
            (["body", "items", 0, "name"], "items.0.名称"),
            (["body", "profile", "phone"], "profile.手机号"),
        ],
    )
    def test_known_and_unknown_paths(self, loc, expected):
        assert _field_label(loc) == expected

    @pytest.mark.parametrize("loc", [None, "not-a-list", [], ["body"], ["query", "path"]])
    def test_degenerate_locations(self, loc):
        """非列表 / 只剩容器前缀 → 空标签（调用方回落到"该字段"）。"""
        assert _field_label(loc) == ""


class TestTypeMessage:
    @pytest.mark.parametrize(
        "error,expected",
        [
            ({"type": "missing", "loc": ["body", "password"]}, "密码不能为空"),
            (
                {"type": "string_too_short", "loc": ["body", "username"], "ctx": {"min_length": 3}},
                "用户名长度不能少于 3 个字符",
            ),
            (
                {"type": "string_too_long", "loc": ["body", "name"], "ctx": {"max_length": 64}},
                "名称长度不能超过 64 个字符",
            ),
            ({"type": "int_parsing", "loc": ["body", "year"]}, "年度应为整数"),
            ({"type": "greater_than", "loc": ["body", "amount"], "ctx": {"gt": 0}}, "金额必须大于 0"),
            ({"type": "email", "loc": ["body", "email"]}, "邮箱不是合法的邮箱"),
            ({"type": "literal_error", "loc": ["body", "status"]}, "状态取值不在允许范围内"),
        ],
    )
    def test_known_types_use_chinese_template(self, error, expected):
        assert _type_message(error) == expected

    def test_business_value_error_keeps_original_text(self):
        """Pydantic 自定义校验器抛的 ValueError 本身是中文 → 原样保留并补字段名。"""
        error = {"type": "value_error", "loc": ["body", "password"], "msg": "密码不能与用户名相同"}
        assert _type_message(error) == "密码：密码不能与用户名相同"

    def test_value_error_without_loc(self):
        error = {"type": "value_error", "loc": [], "msg": "两次密码不一致"}
        assert _type_message(error) == "两次密码不一致"

    def test_template_missing_ctx_falls_back(self):
        """模板需要 min_length 但 ctx 没给 → 退化为通用描述，绝不抛 KeyError。"""
        error = {"type": "string_too_short", "loc": ["body", "username"]}
        assert _type_message(error) == "用户名填写不合法"

    def test_unknown_type_with_raw_message(self):
        error = {"type": "some_future_type", "loc": ["body", "code"], "msg": "custom english"}
        assert _type_message(error) == "编码：custom english"

    def test_unknown_type_without_message(self):
        error = {"type": "some_future_type", "loc": ["body", "code"]}
        assert _type_message(error) == "编码填写不合法"

    def test_unknown_type_without_loc_and_message(self):
        assert _type_message({"type": "weird"}) == "该字段填写不合法"


class TestBuildPayload:
    def test_empty_errors_gives_generic_chinese(self):
        payload = build_validation_error_payload(None)
        assert payload["code"] == 422
        assert payload["success"] is False
        assert payload["message"]
        assert payload["detail"] == payload["message"]
        assert payload["errors"] == []

    def test_empty_list_also_generic(self):
        assert build_validation_error_payload([])["message"] == "请求参数验证失败"

    def test_message_is_string_and_detail_mirrors_it(self):
        payload = build_validation_error_payload(
            [{"type": "missing", "loc": ["body", "password"], "msg": "Field required", "input": "secret"}]
        )
        assert isinstance(payload["message"], str)
        assert isinstance(payload["detail"], str)
        assert payload["detail"] == payload["message"]
        assert payload["message"].startswith("请求参数验证失败：")

    def test_input_is_never_echoed(self):
        """敏感提交值（如密码）绝不出现在响应里。"""
        payload = build_validation_error_payload(
            [
                {
                    "type": "string_too_short",
                    "loc": ["body", "password"],
                    "msg": "String should have at least 6 characters",
                    "input": "p@ssw0rd-PLAINTEXT",
                    "ctx": {"min_length": 6},
                }
            ]
        )
        assert "PLAINTEXT" not in repr(payload)
        # 明细只保留 loc/msg/type 三个键
        assert set(payload["errors"][0]) == {"loc", "msg", "type"}

    def test_non_dict_items_are_skipped(self):
        payload = build_validation_error_payload([None, "junk", 42])
        assert payload["errors"] == []
        assert payload["message"] == "请求参数验证失败"

    def test_duplicate_messages_are_deduped_in_message(self):
        same = {"type": "missing", "loc": ["body", "password"]}
        payload = build_validation_error_payload([same, dict(same)])
        assert payload["message"] == "请求参数验证失败：密码不能为空"
        # 明细仍保留两条（机器可读需完整）
        assert len(payload["errors"]) == 2

    def test_message_caps_at_max_items(self):
        errors = [
            {"type": "missing", "loc": ["body", f"field_{i}"]} for i in range(MAX_MESSAGE_ITEMS + 3)
        ]
        payload = build_validation_error_payload(errors)
        parts = payload["message"].split("：", 1)[1].split("；")
        assert len(parts) == MAX_MESSAGE_ITEMS

    def test_errors_caps_at_max_items(self):
        errors = [
            {"type": "missing", "loc": ["body", f"field_{i}"]} for i in range(MAX_ERROR_ITEMS + 10)
        ]
        payload = build_validation_error_payload(errors)
        assert len(payload["errors"]) == MAX_ERROR_ITEMS


class TestRealHttp422:
    """真实 HTTP 路径：确认 422 的响应形状与文案。"""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        return TestClient(app)

    def test_login_missing_password_returns_chinese_string_detail(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin"})
        assert resp.status_code == 422
        body = resp.json()
        assert isinstance(body["message"], str)
        assert isinstance(body["detail"], str)
        assert body["detail"] == body["message"]
        assert "密码" in body["detail"]
        # 绝不是英文技术串，也不是数组
        assert "Request failed" not in body["detail"]
        assert "Field required" not in body["detail"]

    def test_login_short_username_mentions_length(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "a", "password": "zgcZGC733035#"})
        assert resp.status_code == 422
        assert "用户名" in resp.json()["message"]

    def test_password_is_not_echoed_in_422(self, client):
        secret = "PlaintextSecret123!"
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": secret})
        # 该请求本身可能合法（200/423），只有 422 才需要检查回显
        if resp.status_code == 422:
            assert secret not in resp.text
        else:
            # 换一个必然 422 的形状，确认密码仍不回显
            bad = client.post("/api/v1/auth/login", json={"username": "admin", "password": ""})
            assert bad.status_code == 422
            assert secret not in bad.text
