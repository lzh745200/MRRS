"""W27 P1 回归：同步链覆盖率门禁（`scripts/check_sync_coverage.py`）。

## 为什么要测门禁本身
W26-P0-6 的根因是「`data_reports` 不在任何同步链」——这类缺口**不报错、不变红**，
只能靠门禁发现。而门禁自身写错的形态历史上真实发生过：
`scan_bare_returns.py` 曾因路径拼错恒报 0、且从未被任何 workflow 调用，
"门禁全绿"其实是假绿。

因此这里同时锁定：
1. 当前仓库**必须通过**（17 张跨机表全部可达）；
2. 口径**必须能失败**：把某表从同步链摘掉 / 把特殊通道函数改名 → 必须报缺口；
3. 门禁确实**接进了 CI**（`pr-checks.yml` 有对应步骤），防再次出现"写了但没接线"。
"""

import contextlib
import importlib.util
import io
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND_ROOT / "scripts" / "check_sync_coverage.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_sync_coverage", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def _run(gate, argv):
    """调用门禁并**吞掉它的 stdout**。

    见 `test_w27_no_assert_gate.py::_run` 的详细说明：门禁输出含中文，
    Windows cp936 下写入 pytest 的 fd 捕获临时文件后，后续 `capfd/capsys`
    用例读取会 `UnicodeDecodeError`（表现为一批**无关**用例集体 ERROR）。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return gate.main(argv), buf.getvalue()


class TestGatePassesToday:
    def test_repository_passes(self, gate):
        rc, _out = _run(gate, []); assert rc == 0

    def test_list_mode_returns_zero(self, gate):
        rc, _out = _run(gate, ["--list"]); assert rc == 0

    def test_report_ledger_declared_as_special_channel(self, gate):
        """上报台账是用特殊通道（规范化台账）接的，必须登记在案。"""
        assert "data_reports" in gate.MULTI_MACHINE_TABLES
        assert "data_reports" in gate.SPECIAL_CHANNELS

    def test_all_soft_delete_business_tables_declared(self, gate):
        """核心 4 类主数据必须在跨机清单里（漏登记 = 门禁看不见）。"""
        for table in ("supported_villages", "projects", "funds", "schools"):
            assert table in gate.MULTI_MACHINE_TABLES


class TestGateCanFail:
    def test_missing_table_from_chains_is_reported(self, gate, monkeypatch):
        """把一张表从两条链里都摘掉 → 必须报缺口（门禁不是恒绿）。"""
        monkeypatch.setitem(gate.MULTI_MACHINE_TABLES, "not_in_any_chain", "测试用未接入表")
        rc, _out = _run(gate, []); assert rc == 1

    def test_declared_special_channel_must_be_called(self, gate, monkeypatch, tmp_path):
        """特殊通道函数名在源码中不存在 → 必须报「声明了但没实现」。"""
        monkeypatch.setitem(
            gate.MULTI_MACHINE_TABLES, "ghost_table", "测试用幽灵表"
        )
        monkeypatch.setitem(
            gate.SPECIAL_CHANNELS, "ghost_table", ("_ghost_export_fn", "_ghost_import_fn")
        )
        rc, _out = _run(gate, []); assert rc == 1

    def test_function_called_detects_calls_only(self, gate):
        """`_function_called` 只认调用，不认定义/注释 —— 防假阳性通过。"""
        src = "def foo():\n    pass\n# foo( 在注释里\n"
        assert gate._function_called(src, "foo") is False
        src2 = "def foo():\n    pass\nfoo()\n"
        assert gate._function_called(src2, "foo") is True

    def test_dict_literal_keys_parses_ast(self, gate):
        src = 'DATA_TYPE_MODELS = {\n    "a": 1,\n    "b": 2,\n}\n'
        assert gate._dict_literal_keys(src, "DATA_TYPE_MODELS") == {"a", "b"}

    def test_dict_literal_keys_handles_call_form(self, gate):
        src = 'X = dict(alpha=1, beta=2)\n'
        assert gate._dict_literal_keys(src, "X") == {"alpha", "beta"}


class TestGateWiredIntoCi:
    def test_pr_checks_calls_gate(self):
        ci = (BACKEND_ROOT.parent / ".github" / "workflows" / "pr-checks.yml").read_text(
            encoding="utf-8"
        )
        assert "check_sync_coverage.py" in ci, (
            "门禁脚本存在但未接入 CI —— 这正是 scan_bare_returns 历史失效的形态"
        )
