#!/usr/bin/env python
"""门禁自测：scripts/check_unused_scope_params.py 的检测能力（W18 P0-2 防复发）。

为什么门禁必须有自测：
  一个"永远绿灯"的门禁比没有门禁更危险 —— 它会让团队误以为已经防住了。
  本文件用**可控样本**证明该脚本真的能区分「收下不用」与「正确接线」，
  并锁定其已知边界（透传形态不判定），避免后续有人把判据改松却无人察觉。
"""
import importlib.util
import os

import pytest

# 本文件位于 backend/tests/unit/ → 上溯 4 层才到仓库根
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
GATE_PATH = os.path.join(ROOT, "scripts", "check_unused_scope_params.py")


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_unused_scope_params", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def _write(tmp_path, source):
    p = tmp_path / "sample.py"
    p.write_text(source, encoding="utf-8")
    return str(p)


def test_gate_script_exists(gate):
    assert os.path.exists(GATE_PATH)
    assert hasattr(gate, "scan_file")


def test_detects_param_declared_but_never_used(gate, tmp_path):
    """核心判据：收下 data_scope 却完全没用 → 必须判定违规。"""
    src = (
        "def bad_func(db, data_scope, year=None):\n"
        "    return db.query(1).scalar()\n"
    )
    found = gate.scan_file(_write(tmp_path, src))
    assert [(f[1], f[2]) for f in found] == [("bad_func", "data_scope")]


def test_does_not_flag_correctly_wired_function(gate, tmp_path):
    """不误判：真正用模板方法过滤查询的函数。"""
    src = (
        "def good_func(db, data_scope, year=None):\n"
        "    q = db.query(1)\n"
        "    return data_scope.filter_by_org_ids(q, 1)\n"
    )
    assert gate.scan_file(_write(tmp_path, src)) == []


def test_ignores_functions_without_scope_params(gate, tmp_path):
    src = (
        "def plain(db, year):\n"
        "    return db.query(1)\n"
    )
    assert gate.scan_file(_write(tmp_path, src)) == []


def test_detects_each_scope_param_name(gate, tmp_path):
    """三个受控形参名都要能识别。"""
    src = (
        "def a(db, data_scope):\n    return 1\n"
        "def b(db, org_scope):\n    return 1\n"
        "def c(db, scope_filter):\n    return 1\n"
    )
    names = {f[2] for f in gate.scan_file(_write(tmp_path, src))}
    assert names == {"data_scope", "org_scope", "scope_filter"}


def test_known_boundary_passthrough_not_flagged(gate, tmp_path):
    """已知边界：只透传给下游（形参被引用）不算违规。

    这是 AST 判据的固有局限 —— 形参确实"被使用"了，只是没被用来过滤。
    真正的接线正确性由 tests/unit/test_w18_metric_consistency.py 这类
    **行为级**用例保证。此处锁定边界，避免误以为门禁能覆盖透传形态。
    """
    src = (
        "def passthrough(db, data_scope):\n"
        "    return _inner(db, data_scope)\n"
    )
    assert gate.scan_file(_write(tmp_path, src)) == []


def test_unparsable_file_is_skipped_not_crashing(gate, tmp_path):
    assert gate.scan_file(_write(tmp_path, "def broken(:\n")) == []


def test_real_app_tree_has_zero_new_violations(gate):
    """真实代码树基线：修复后应无新增违规（防回归）。"""
    all_found = []
    for path in gate._iter_py_files(gate.APP_DIR):
        all_found.extend(gate.scan_file(path))
    keys = [f"{func}::{param}" for _lineno, func, param in all_found]
    baseline = getattr(gate, "BASELINE", {})
    new = [k for k in keys if not any(k.endswith(b) for b in baseline)]
    assert new == [], f"出现新的作用域形参收下未使用: {new}"
