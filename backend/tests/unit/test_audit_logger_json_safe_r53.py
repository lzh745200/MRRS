# -*- coding: utf-8 -*-
"""_json_safe_value 的两个防御分支（2026-10-30 补，Nightly 覆盖率 99.97% 就缺这两处）。

Nightly 报告：app/utils/audit_logger.py 96.03%，Missing 51, 54-56
  - 51     → value is None 的提前返回
  - 54-56  → json.dumps 抛 TypeError/ValueError 时的降级分支
"""
from app.utils.audit_logger import _json_safe_value


def test_none_returns_none():
    """第 51 行：None 直接返回 None（不进入 json round-trip）。"""
    assert _json_safe_value(None) is None


def test_serialization_failure_degrades_to_summary():
    """第 54-56 行：无法序列化时降级为 {"_unserializable": ...} 而不是抛出去。

    用**循环引用**触发（json 对循环引用抛 ValueError: Circular reference detected；
    这是 `default=str` 也救不了的情形）。
    """
    cyclic = {}
    cyclic["self"] = cyclic

    out = _json_safe_value(cyclic)

    assert isinstance(out, dict)
    assert "_unserializable" in out
    assert len(out["_unserializable"]) <= 2000


def test_serializable_roundtrip_keeps_value():
    """正常路径不受影响：dict/list/数值原样保留。"""
    assert _json_safe_value({"a": 1, "b": [1, 2]}) == {"a": 1, "b": [1, 2]}
    assert _json_safe_value("x") == "x"
    assert _json_safe_value(0) == 0
