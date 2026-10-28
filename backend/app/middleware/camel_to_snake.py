# -*- coding: utf-8 -*-
"""请求体键名转换中间件 + 响应信封最小补全

1. 请求体: 前端 camelCase JSON 键 → snake_case(Pydantic 字段一致)
2. 响应: 对裸 dict JSON 响应补全信封元数据(success/code),不改变数据层级。
   - 已含 success 或 code 的响应跳过
   - 裸 list/标量跳过(前端拦截器已兼容)
   - 文件/流式响应跳过

M33（R27 性能排查）：旧实现对**每个** application/json 响应都完整解码 → 递归遍历
→ 重新序列化，且重建 JSONResponse（复制全部响应头 + background）。即使绝大多数
响应已是标准信封（`{"code":...,"success":...}`），也要付出一次 json.loads 与一次
json.dumps 的代价（大列表响应尤其昂贵），并被 BaseHTTPMiddleware 的响应缓冲放大。

现契约（行为等价，仅省去无谓解析）：
- **仅对"顶层裸 dict"补信封**——顶层含 success/code 的响应直接放行（不再解析 body）；
  顶层是 list/标量/流式的响应同样直接放行（与旧实现一致，旧实现也不会改写它们）。
- 判定只看 body 的**首个非空白字节**：信封响应以 `{` 开头且必然带 code/success，
  裸 dict 里可能内嵌 `"code"`（如 `{"data":{"code":1}}`），故不能用子串匹配；
  但 `[`/`"`/数字/`true`/`false`/`null` 开头必然不是可补信封的 dict。
- 真正需要补信封时才解码 → 补 → 重建响应（沿用旧实现：完整复制响应头、
  跳过 content-length、透传 background）。
"""
import logging
import json
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.utils.common import StringHelper  # noqa: E402

logger = logging.getLogger(__name__)


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


def _first_non_whitespace_byte(body: bytes) -> Optional[int]:
    """返回 body 首个非空白字节；全空白/空 body 返回 None。"""
    for byte in body:
        if byte not in (0x20, 0x09, 0x0A, 0x0D):
            return byte
    return None


def _needs_envelope(body: bytes) -> bool:
    """廉价判定：仅顶层裸 dict 需要补信封，其余一律免解析。"""
    return _first_non_whitespace_byte(body) == 0x7B  # "{"


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
            if not body_bytes or not _needs_envelope(body_bytes):
                # 非"顶层裸 dict"（含已是标准信封的绝大多数响应）无需解析
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
        except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
            logger.warning('dispatch 兜底失败（已降级）: %s', exc, exc_info=True)
            return response
