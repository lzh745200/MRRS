# -*- coding: utf-8 -*-
"""
请求体键名转换中间件 + 响应信封最小补全

1. 请求体: 前端 camelCase JSON 键 → snake_case(Pydantic 字段一致)
2. 响应: 对裸 dict JSON 响应补全信封元数据(success/code),不改变数据层级。
   - 已含 success 或 code 的响应跳过
   - 裸 list/标量跳过(前端拦截器已兼容)
   - 文件/流式响应跳过
"""
import json
from typing import Any, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.utils.common import StringHelper  # noqa: E402


def _convert_keys(obj: Any, converter) -> Any:
    """递归转换对象中所有的字符串键名；返回 (converted_obj, changed)"""
    if isinstance(obj, dict):
        new: Dict[str, Any] = {}
        changed = False
        for k, v in obj.items():
            if isinstance(k, str):
                new_key = converter(k)
                if new_key != k:
                    changed = True
            else:
                new_key = k
            inner, inner_changed = _convert_keys(v, converter)
            new[new_key] = inner
            if inner_changed:
                changed = True
        return new, changed
    if isinstance(obj, list):
        items = [_convert_keys(item, converter) for item in obj]
        return [i[0] for i in items], any(i[1] for i in items)
    return obj, False


def _patch_envelope(data: Any) -> Dict[str, Any]:
    """裸 dict → 补全 success/code 元数据(不改变数据层级,向前端/后端测试兼容)"""
    if not isinstance(data, dict):
        return data
    if 'success' in data or 'code' in data:
        return data
    patch = {"code": 200, "success": True}
    if 'message' not in data:
        patch["message"] = "success"
    # 保持键顺序: 元数据在前,原数据在后
    merged = dict(patch)
    merged.update(data)
    return merged


class CamelToSnakeMiddleware(BaseHTTPMiddleware):
    """
    HTTP 中间件：
    1. 请求体 camelCase → snake_case
    2. 响应裸 dict 自动补全 code/success 元数据(最小补全,不包 data 层)
    """

    async def dispatch(self, request: Request, call_next):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.body()
            if body:
                try:
                    data = json.loads(body)
                    converted, changed = _convert_keys(data, StringHelper.to_snake_case)
                    if changed:
                        request._body = json.dumps(
                            converted, ensure_ascii=False
                        ).encode("utf-8")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass  # 非 JSON 体保持原样

        response = await call_next(request)

        # ── 响应信封最小补全 ──
        try:
            resp_content_type = response.headers.get("content-type", "")
            if "application/json" not in resp_content_type:
                return response
            if response.status_code >= 400:
                return response  # 错误响应由异常处理器生成
            body_bytes = getattr(response, "body", None)
            if not body_bytes:
                return response

            parsed = json.loads(body_bytes.decode("utf-8"))
            patched = _patch_envelope(parsed)
            if patched is parsed:
                return response

            new_response = JSONResponse(
                content=patched,
                status_code=response.status_code,
            )
            # headers 必须整体复制（CORS/Set-Cookie/X-Request-Id/缓存头都在里面，
            # 裸 JSONResponse 会全部丢掉，深审 #32）；content-length 由
            # JSONResponse 依新 body 重算，不能沿用旧值。background 同样透传，
            # 否则后台任务（如审计/清理）被静默丢弃。
            for header_name, header_value in response.headers.items():
                if header_name.lower() == "content-length":
                    continue
                new_response.headers[header_name] = header_value
            new_response.background = response.background
            return new_response
        except Exception:
            return response
