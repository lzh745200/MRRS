"""W27 P1 回归：零断言测试棘轮门禁（`scripts/check_no_assert_tests.py`）。

## 背景
`tests/test_approval_idempotency.py` 曾有 **10 个测试函数体全是 `pass`** ——
不建数据、不调被测代码、不写断言。重写当轮立刻挖出「重复提交产生 2 条待审批任务」
的真实缺陷。空壳测试比没有测试更糟：它制造虚假安全感，且会让覆盖率统计变绿。

本门禁把"每个测试函数必须有断言"做成棘轮（只减不增）。

## 本文件锁定
1. 仓库当前**通过**，且基线条目唯一（同一文件内多个测试类可有同名方法；
   只用 `文件::方法名` 会产生重复条目 → 基线与实际计数永远对不上，
   这类"门禁自身不稳定"比没有门禁更糟）；
2. 门禁**能失败**：新增零断言测试 → NEW>0 → 退出码 1；
3. 三类断言都算覆盖：`assert` 语句、mock 的 `assert_*`、`pytest.raises`（含 with 形式）；
4. `@pytest.mark.no_assert` 是唯一的显式豁免通道；
5. 门禁确实**接进了 CI**。
"""

import contextlib
import importlib.util
import io
import textwrap
import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND_ROOT / "scripts" / "check_no_assert_tests.py"


def _run(gate, argv):
    """调用门禁并**吞掉它的 stdout**。

    ## 为什么必须重定向（实测踩到）
    门禁脚本的输出含中文。Windows 控制台默认 cp936，而 pytest 的 **fd 级捕获**
    （`capfd`）把 stdout 落到临时文件后用 **utf-8** 读取 —— 中文以 GBK 字节写入后，
    后续任何 `capsys/capfd` 用例在 `readouterr()` 时直接
    `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb8 in position 64`。
    该错误发生在**收集/捕获层**，表现成与日志无关的用例集体 ERROR，
    极难定位（本轮实测 751 errors）。
    重定向到内存缓冲即可让中文不进入 fd 捕获，且不影响被测逻辑。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return gate.main(argv), buf.getvalue()


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_no_assert_tests", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def _fn(source: str) -> ast.AST:
    """取源码中**第一个函数定义**节点（源码可能先有 import 等语句）。"""
    tree = ast.parse(textwrap.dedent(source))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    raise AssertionError("源码中没有函数定义")


class TestGatePassesToday:
    def test_repository_passes(self, gate):
        rc, _out = _run(gate, []); assert rc == 0

    def test_baseline_entries_are_unique(self, gate):
        """基线不能有重复键 —— 否则基线与实际计数永远对不上。"""
        violations = gate.collect_violations()
        assert len(violations) == len(set(violations))

    def test_identifiers_include_class_path(self, gate):
        """同一文件多个测试类可以有同名方法，标识必须带类路径。"""
        violations = gate.collect_violations()
        # 形如 tests/...::TestX::test_y 或 tests/...::test_y（模块级）
        assert all("::" in v for v in violations)
        # 若某文件存在同名方法，其标识必须互不相同
        assert len(violations) == len(set(violations))


class TestAssertionDetection:
    def test_plain_assert_counts(self, gate):
        fn = _fn("def test_x():\n    assert 1 == 1\n")
        assert gate._has_assertion(fn) is True

    def test_mock_assert_counts(self, gate):
        for call in ("assert_called_once()", "assert_not_called()",
                     "assert_called_with(1)", "assert_awaited_once()"):
            fn = _fn(f"def test_x():\n    mock.{call}\n")
            assert gate._has_assertion(fn) is True, call

    def test_pytest_raises_call_form_counts(self, gate):
        fn = _fn("def test_x():\n    pytest.raises(ValueError)\n")
        assert gate._has_assertion(fn) is True

    def test_pytest_raises_with_form_counts(self, gate):
        fn = _fn(
            "def test_x():\n"
            "    with pytest.raises(ValueError):\n"
            "        boom()\n"
        )
        assert gate._has_assertion(fn) is True

    def test_bare_call_is_not_assertion(self, gate):
        fn = _fn("def test_x():\n    do_something()\n")
        assert gate._has_assertion(fn) is False

    def test_pass_only_is_not_assertion(self, gate):
        """这正是原始空壳测试的形态。"""
        fn = _fn("def test_x():\n    pass\n")
        assert gate._has_assertion(fn) is False

    def test_exempt_marker_recognised(self, gate):
        fn = _fn(
            "import pytest\n"
            "@pytest.mark.no_assert\n"
            "def test_x():\n    pass\n"
        )
        assert gate._is_exempt(fn) is True

    def test_no_marker_is_not_exempt(self, gate):
        fn = _fn("def test_x():\n    pass\n")
        assert gate._is_exempt(fn) is False


class TestGateCanFail:
    def test_new_zero_assertion_test_fails(self, gate, monkeypatch):
        """新增一个零断言测试 → 必须 NEW>0 且退出码 1。"""
        monkeypatch.setattr(
            gate, "collect_violations",
            lambda: gate.__dict__["_orig"]() + ["tests/unit/fake.py::test_new_shell"]
            if "_orig" in gate.__dict__ else ["tests/unit/fake.py::test_new_shell"],
        )
        rc, _out = _run(gate, []); assert rc == 1

    def test_fixed_entries_do_not_fail(self, gate, monkeypatch):
        """条目减少（修好了）不失败，只提示可收紧基线。"""
        monkeypatch.setattr(gate, "collect_violations", lambda: [])
        monkeypatch.setattr(gate, "_load_baseline", lambda: {"tests/x.py::test_old"})
        rc, _out = _run(gate, []); assert rc == 0


class TestGateCannotBeBypassed:
    """实测发现的两个绕过口子（已修，此处锁定）。

    ① **BOM 绕过**：Windows 下 PowerShell `Set-Content -Encoding UTF8` / 记事本会写
       BOM；用 `encoding="utf-8"` 读取会让 `ast.parse` 抛
       "invalid non-printable character U+FEFF"，而原实现 `except SyntaxError: continue`
       **静默跳过该文件** → 加个 BOM 就能让空壳测试对门禁不可见（已实测绕过）。
    ② **语法错误绕过**：同样被静默跳过 → 任何无法解析的测试文件都成了盲区。
    """

    @staticmethod
    def _sandbox(tmp_path, monkeypatch, gate):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        monkeypatch.setattr(gate, "TESTS_DIR", tests_dir)
        monkeypatch.setattr(gate, "BACKEND_ROOT", tmp_path)
        return tests_dir

    def test_bom_encoded_empty_test_is_detected(self, gate, tmp_path, monkeypatch):
        tests_dir = self._sandbox(tmp_path, monkeypatch, gate)
        # 带 BOM（\ufeff）+ 空壳测试体
        (tests_dir / "test_bom.py").write_text(
            "\ufeffdef test_shell():\n    pass\n", encoding="utf-8"
        )
        violations = gate.collect_violations()
        assert violations == ["tests/test_bom.py::test_shell"], (
            "BOM 文件被静默跳过 —— 门禁可被绕过"
        )

    def test_unparsable_file_raises_instead_of_silent_skip(self, gate, tmp_path, monkeypatch):
        tests_dir = self._sandbox(tmp_path, monkeypatch, gate)
        (tests_dir / "test_broken.py").write_text(
            "def test_x(:\n    pass\n", encoding="utf-8"
        )
        with pytest.raises(RuntimeError) as ei:
            gate.collect_violations()
        assert "无法解析" in str(ei.value)

    def test_normal_file_still_works(self, gate, tmp_path, monkeypatch):
        tests_dir = self._sandbox(tmp_path, monkeypatch, gate)
        (tests_dir / "test_ok.py").write_text(
            "def test_a():\n    assert 1 == 1\n\ndef test_b():\n    pass\n",
            encoding="utf-8",
        )
        assert gate.collect_violations() == ["tests/test_ok.py::test_b"]


class TestGateWiredIntoCi:
    def test_pr_checks_calls_gate(self):
        ci = (BACKEND_ROOT.parent / ".github" / "workflows" / "pr-checks.yml").read_text(
            encoding="utf-8"
        )
        assert "check_no_assert_tests.py" in ci, (
            "门禁脚本存在但未接入 CI —— 这正是 scan_bare_returns 历史失效的形态"
        )
