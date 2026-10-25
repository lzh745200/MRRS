# -*- coding: utf-8 -*-
"""请求参数校验错误（422）的中文化 —— 单一事实源

## 为什么需要

FastAPI 的 ``RequestValidationError`` 默认返回::

    {"detail": [{"type": "string_too_short", "loc": ["body", "username"],
                 "msg": "String should have at least 3 characters",
                 "input": "x", "ctx": {"min_length": 3}}, ...]}

这带来三个问题：

1. **前端拿不到可用文案** —— ``detail`` 是数组而非字符串。前端若按
   ``data.detail`` 取字符串会落空，最终把 axios 原文
   ``Request failed with status code 422`` 显示给用户。
2. **文案是英文技术描述** —— "String should have at least 3 characters"
   对基层操作员没有意义。
3. **回显 ``input``** —— 校验失败时把提交值原样回传；登录/注册/改密这类
   请求里 ``input`` 可能含**明文密码**，等于把密码写进响应与前端日志。

本模块把校验错误翻成一条中文可读消息，并**丢弃 ``input``**。

## 输出契约

处理器统一返回（与 ``AppError`` 信封同构，前端既有的
``message`` / ``detail`` 两条读取路径都能拿到可读文案）::

    {
      "code": 422, "success": False,
      "message": "请求参数验证失败：用户名长度不能少于 3 个字符；密码不能为空",
      "detail":  "<同 message>",
      "errors": [{"loc": "username", "msg": "用户名长度不能少于 3 个字符", "type": "string_too_short"}]
    }

``errors`` 保留机器可读性（不含 ``input`` / ``ctx``），最多 20 条。
"""

from __future__ import annotations

from typing import Any, Iterable

# 一次最多回传多少条明细（防止超大请求体刷爆响应）
MAX_ERROR_ITEMS = 20
# 拼进 message 的明细条数（再多用户也读不完，明细仍在 errors 里）
MAX_MESSAGE_ITEMS = 3

# 常见字段名 → 中文标签。未收录的字段回落到原始名（比"字段1"更有用）。
FIELD_LABELS: dict[str, str] = {
    "username": "用户名",
    "password": "密码",
    "old_password": "原密码",
    "new_password": "新密码",
    "confirm_password": "确认密码",
    "email": "邮箱",
    "phone": "手机号",
    "code": "编码",
    "name": "名称",
    "title": "标题",
    "remark": "备注",
    "remarks": "备注",
    "description": "描述",
    "id": "ID",
    "ids": "ID 列表",
    "page": "页码",
    "page_size": "每页条数",
    "year": "年度",
    "date": "日期",
    "amount": "金额",
    "reason": "原因",
    "status": "状态",
    "type": "类型",
    "category": "分类",
    "organization_id": "所属组织",
    "village_id": "所属帮扶村",
    "supported_village_id": "所属帮扶村",
    "project_id": "所属项目",
    "school_id": "所属学校",
    "user_id": "用户",
    "role": "角色",
    "token": "令牌",
    "captcha": "验证码",
    "totp_code": "双因素验证码",
}

# pydantic v2 校验类型 → 中文模板。模板可用 ctx 里的值（缺失则回落通用文案）。
TYPE_TEMPLATES: dict[str, str] = {
    "missing": "{field}不能为空",
    "string_type": "{field}应为文本",
    "int_type": "{field}应为整数",
    "int_parsing": "{field}应为整数",
    "float_type": "{field}应为数字",
    "float_parsing": "{field}应为数字",
    "decimal_parsing": "{field}应为数字",
    "bool_type": "{field}应为是/否",
    "bool_parsing": "{field}应为是/否",
    "list_type": "{field}应为数组",
    "dict_type": "{field}应为对象",
    "none_required": "{field}不能为空",
    "string_too_short": "{field}长度不能少于 {min_length} 个字符",
    "string_too_long": "{field}长度不能超过 {max_length} 个字符",
    "too_short": "{field}至少需要 {min_length} 项",
    "too_long": "{field}最多允许 {max_length} 项",
    "greater_than": "{field}必须大于 {gt}",
    "greater_than_equal": "{field}不能小于 {ge}",
    "less_than": "{field}必须小于 {lt}",
    "less_than_equal": "{field}不能大于 {le}",
    "string_pattern_mismatch": "{field}格式不正确",
    "date_parsing": "{field}日期格式不正确",
    "date_from_datetime_parsing": "{field}日期格式不正确",
    "datetime_parsing": "{field}时间格式不正确",
    "datetime_from_date_parsing": "{field}时间格式不正确",
    "time_parsing": "{field}时间格式不正确",
    "json_invalid": "{field}JSON 格式不正确",
    "json_type": "{field}应为 JSON",
    "literal_error": "{field}取值不在允许范围内",
    "enum": "{field}取值不在允许范围内",
    "extra_forbidden": "{field}不是允许的字段",
    "url_parsing": "{field}不是合法的 URL",
    "email": "{field}不是合法的邮箱",
    "uuid_parsing": "{field}不是合法的 UUID",
}

# 这些类型的 msg 本身已是业务中文（Pydantic 的 ValueError / 自定义校验器），
# 直接使用原文比套模板更准确。
_VERBATIM_TYPES = frozenset({"value_error", "assertion_error"})

_GENERIC_MESSAGE = "请求参数验证失败"


def _field_label(loc: Any) -> str:
    """把 ``loc`` 元组转成中文字段标签。

    ``["body", "username"]`` → ``"用户名"``；``["body", "items", 0, "name"]`` →
    ``"items.0.name"``（数组下标无法映射中文，保留原样）。
    """
    if not isinstance(loc, (list, tuple)):
        return ""
    parts = [str(part) for part in loc if str(part) not in ("body", "query", "path", "header", "cookie")]
    if not parts:
        return ""
    # 只有最后一段是"字段本身"，前面是容器路径；容器名不翻译
    tail = parts[-1]
    label = FIELD_LABELS.get(tail, tail)
    if len(parts) == 1:
        return label
    return ".".join(parts[:-1] + [label])


def _type_message(error: dict) -> str:
    """单条校验错误 → 中文文案。"""
    err_type = str(error.get("type") or "")
    field = _field_label(error.get("loc"))
    raw_msg = error.get("msg")
    raw_msg = raw_msg if isinstance(raw_msg, str) else ""

    if err_type in _VERBATIM_TYPES and raw_msg:
        # 业务校验器给出的中文原文，原样保留（带上字段名更清楚）
        return f"{field}：{raw_msg}" if field else raw_msg

    template = TYPE_TEMPLATES.get(err_type)
    if template is not None:
        values: dict[str, Any] = {"field": field or "该字段"}
        ctx = error.get("ctx")
        if isinstance(ctx, dict):
            values.update({key: value for key, value in ctx.items() if isinstance(value, (str, int, float))})
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            # ctx 缺模板占位符 → 退化为不带数量的通用描述
            return f"{field or '该字段'}填写不合法"

    # 未知类型：优先用原始 msg（至少比空字符串有用），否则通用文案
    if raw_msg:
        return f"{field}：{raw_msg}" if field else raw_msg
    return f"{field or '该字段'}填写不合法"


def build_validation_error_payload(errors: Iterable[Any] | None) -> dict:
    """把 pydantic 的 ``exc.errors()`` 转成统一的中文错误响应体。

    - 丢弃 ``input``（可能含明文密码等敏感值），也丢弃非标量 ``ctx``；
    - ``message`` 只拼前 ``MAX_MESSAGE_ITEMS`` 条，明细仍在 ``errors`` 里；
    - ``errors`` 为空时给出通用文案，绝不返回空 message。
    """
    normalized: list[dict] = []
    for error in errors or []:
        if not isinstance(error, dict):
            continue
        normalized.append(
            {
                "loc": _field_label(error.get("loc")),
                "msg": _type_message(error),
                "type": str(error.get("type") or ""),
            }
        )
        if len(normalized) >= MAX_ERROR_ITEMS:
            break

    if not normalized:
        message = _GENERIC_MESSAGE
    else:
        # 同一条消息可能重复（同一字段多个约束），去重后再拼
        seen: list[str] = []
        for item in normalized:
            if item["msg"] and item["msg"] not in seen:
                seen.append(item["msg"])
        head = "；".join(seen[:MAX_MESSAGE_ITEMS])
        message = f"{_GENERIC_MESSAGE}：{head}" if head else _GENERIC_MESSAGE

    return {
        "code": 422,
        "success": False,
        "message": message,
        # 兼容直接读 detail 的视图（历史各页面写法不一）
        "detail": message,
        "errors": normalized,
    }
