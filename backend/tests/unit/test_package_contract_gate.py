# -*- coding: utf-8 -*-
"""check_package_contract.py 的契约棘轮回归用例（P0-F3）。

门禁存在的原因：离线多机同步依赖 manifest 的字段契约；一旦删字段/改类型/改必填，
介质到了地方才发现——这批用例守住「真的会失败，而不是永远绿」。
"""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

import pytest

GATE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_package_contract.py"
spec = spec_from_file_location("check_package_contract", GATE_PATH)
gate = module_from_spec(spec)
spec.loader.exec_module(gate)


class _Field:
    def __init__(self, ann: str, required: bool):
        self.annotation = ann
        self._req = required

    def is_required(self):
        return self._req


class _Manifest:
    model_fields: dict = {}


class _EnumMember:
    def __init__(self, value):
        self.value = value


class _PkgType:
    report = _EnumMember("report")
    task = _EnumMember("task")
    update = _EnumMember("update")


def _snap(fields=None, enums=None):
    return {
        "manifest_cls": "DataPackageManifest",
        "fields": fields or {"a": {"annotation": "str", "required": True}},
        "package_type_values": enums if enums is not None else ["report", "task", "update"],
    }


def test_gate_loads_manifest_from_real_schema():
    """真 schema 能加载且字段数期望非零（契约素材源自真实 models，不 mock）。"""
    manifest_cls, pkg_type = gate._load_manifest_class()
    snap = gate.contract_snapshot(manifest_cls, pkg_type)
    assert len(snap["fields"]) >= 15, "manifest 字段数异常少，可能导入错模型"
    assert "report" in snap["package_type_values"]


def test_no_change_returns_empty_problems():
    b = _snap()
    c = _snap()
    assert gate.diff_snapshot(b, c) == []


def test_removed_field_is_caught():
    b = _snap({"a": {"annotation": "str", "required": True}, "gone": {"annotation": "int", "required": False}})
    c = _snap({"a": {"annotation": "str", "required": True}})
    problems = gate.diff_snapshot(b, c)
    assert any("删除字段" in p and "gone" in p for p in problems)


def test_added_field_is_caught():
    b = _snap()
    c = _snap({"a": {"annotation": "str", "required": True}, "newer": {"annotation": "int", "required": False}})
    problems = gate.diff_snapshot(b, c)
    assert any("新增字段" in p and "newer" in p for p in problems)


def test_type_change_is_caught():
    b = _snap({"a": {"annotation": "str", "required": True}})
    c = _snap({"a": {"annotation": "Optional[str]", "required": True}})
    problems = gate.diff_snapshot(b, c)
    assert any("字段类型变化" in p and "a" in p for p in problems)


def test_required_change_is_caught():
    b = _snap({"a": {"annotation": "str", "required": False}})
    c = _snap({"a": {"annotation": "str", "required": True}})
    problems = gate.diff_snapshot(b, c)
    assert any("字段必填性变化" in p for p in problems)


def test_enum_removed_is_caught():
    b = _snap(enums=["report", "task", "update"])
    c = _snap(enums=["report", "task"])
    problems = gate.diff_snapshot(b, c)
    assert any("移除枚举值" in p and "update" in p for p in problems)


def test_enum_added_is_caught():
    b = _snap(enums=["report"])
    c = _snap(enums=["report", "archive"])
    problems = gate.diff_snapshot(b, c)
    assert any("新增枚举值" in p and "archive" in p for p in problems)


def test_diff_output_is_deterministic_order():
    b = _snap({"z": {"annotation": "str", "required": True}, "m": {"annotation": "int", "required": True}, "a": {"annotation": "float", "required": True}})
    c = _snap()
    problems = gate.diff_snapshot(b, c)
    # 输出必须稳定：删除字段按字母序，再跟类型/必填变化（也是按字段名排序固定的）
    assert problems == ["删除字段: m", "删除字段: z", "字段类型变化: a: float -> str"]