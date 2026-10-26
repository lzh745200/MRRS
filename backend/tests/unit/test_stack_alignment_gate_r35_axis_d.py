# -*- coding: utf-8 -*-
"""R35 门禁 D 轴（请求体必填性）的回归测试。

为什么加这一轴（真实事故）：
2026-10-26 现场反馈，点「新增组织」提交后被拦下，提示「组织编码（行政区划代码）不能为空」，
但前端表单里根本没有组织编码输入框。根因链条：

1. 后端 `schemas/organization.py:OrganizationCreate.code` 是必填
   （`Field(...)`，`min_length=max_length=6`）；
2. 前端 `types/organization.ts:OrganizationCreate.code` 却写成 `code?: string`（可选）；
3. C 轴只比对 response_model，请求体从来没人比 —— 于是「表单少字段」这类缺陷
   既躲过类型检查也躲过门禁，只能由用户撞 422 才发现。

D 轴补上：同名且全局唯一的 Create/Update 契约，必填字段集合必须一致。
本文件锁定三个方向都能被检出，并确认当前仓库零漂移。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "scripts" / "check_stack_alignment.py"

sys.path.insert(0, str(ROOT / "scripts"))


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_stack_alignment_axis_d", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gate(monkeypatch):
    """每个用例都用合成数据，绝不读真实仓库（否则断言会随仓库内容漂移）。"""
    module = _load_gate()
    monkeypatch.setattr(module, "_collect_backend_required_models", lambda: {})
    monkeypatch.setattr(module, "_collect_frontend_required_interfaces", lambda: {})
    return module


def _backend(module, name, fields, required):
    module._collect_backend_required_models = lambda: {
        name: [("backend/app/schemas/x.py", set(fields), set(required))]
    }


def _frontend(module, name, fields, required):
    module._collect_frontend_required_interfaces = lambda: {
        name: [("frontend/src/types/x.ts", set(fields), set(required))]
    }


class TestAxisDDetectsDrift:
    def test_backend_required_but_frontend_optional(self, gate):
        """后端必填、前端写成可选 —— 本次事故的确切形态（code?: string）。"""
        _backend(gate, "OrganizationCreate", {"name", "code"}, {"name", "code"})
        _frontend(gate, "OrganizationCreate", {"name", "code"}, {"name"})
        drift = gate.check_request_shape_alignment()
        assert len(drift) == 1
        assert drift[0]["name"] == "OrganizationCreate"
        assert drift[0]["not_required_in_frontend"] == ["code"]

    def test_backend_required_but_frontend_missing_field(self, gate):
        """后端必填、前端根本没有该字段（表单漏输入的典型形态）。"""
        _backend(
            gate,
            "DataReportCreate",
            {"package_id", "title", "report_type"},
            {"package_id", "title", "report_type"},
        )
        _frontend(gate, "DataReportCreate", {"package_id", "title"}, {"package_id", "title"})
        drift = gate.check_request_shape_alignment()
        assert drift[0]["missing_in_frontend"] == ["report_type"]

    def test_frontend_required_but_backend_optional(self, gate):
        """前端过度约束（表单强制填、后端其实可选）也要报。"""
        _backend(gate, "FooCreate", {"name", "email"}, {"name"})
        _frontend(gate, "FooCreate", {"name", "email"}, {"name", "email"})
        drift = gate.check_request_shape_alignment()
        assert drift[0]["required_only_in_frontend"] == ["email"]

    def test_fully_aligned_is_not_reported(self, gate):
        _backend(gate, "BarCreate", {"name", "code"}, {"name", "code"})
        _frontend(gate, "BarCreate", {"name", "code"}, {"name", "code"})
        assert gate.check_request_shape_alignment() == []


class TestAxisDScopeGuards:
    def test_non_create_update_names_are_ignored(self, gate):
        """只审请求体契约；响应类等其它类的必填差异不归 D 轴管。"""
        _backend(gate, "FooResponse", {"name", "code"}, {"name", "code"})
        _frontend(gate, "FooResponse", {"name"}, {"name"})
        assert gate.check_request_shape_alignment() == []

    def test_ambiguous_same_name_is_skipped(self, gate):
        """同名多义（任一侧不唯一）不配对，避免假阳性。"""
        gate._collect_backend_required_models = lambda: {
            "DupCreate": [
                ("backend/app/schemas/a.py", {"x"}, {"x"}),
                ("backend/app/schemas/b.py", {"y"}, set()),
            ]
        }
        _frontend(gate, "DupCreate", {"x"}, set())
        assert gate.check_request_shape_alignment() == []

    def test_update_suffix_is_covered(self, gate):
        _backend(gate, "ThingUpdate", {"name", "code"}, {"code"})
        _frontend(gate, "ThingUpdate", {"name", "code"}, {"name"})
        drift = gate.check_request_shape_alignment()
        assert drift and drift[0]["not_required_in_frontend"] == ["code"]


class TestCurrentRepoIsClean:
    def test_repo_has_no_request_shape_drift(self):
        """当前仓库四处真实漂移（OrganizationCreate.code / DataReportCreate /
        SupportedVillageCreate / ReportSubscriptionCreate）已全部对齐。"""
        module = _load_gate()
        drift = module.check_request_shape_alignment()
        assert drift == [], "请求体必填性仍有漂移：\n" + "\n".join(
            f"  {d['name']}: {d}" for d in drift
        )

    def test_report_includes_axis_d(self):
        module = _load_gate()
        report = module.run()
        assert "request_shape_drift" in report
        assert report["request_shape_drift"] == []
