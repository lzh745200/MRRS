"""`scripts/check_constants_sync.py` 门禁单测。

背景（2026-10-25 真实 CI 失败）：`MAX_PAGE_SIZE` 100→200，但
`tests/unit/test_svc_batch.py::test_h10` 仍断言 100，本地只跑相关套件没发现，
CI 的 seg10 才红 → PR Checks 红 → 发布门禁拒绝出包。
本门禁把这类"常量改了、测试没改"的漂移变成提交前可拦截的问题。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_constants_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_constants_sync", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mod = _load()


class TestParseConstants:
    def test_parses_top_level_literals_only(self, tmp_path):
        src = tmp_path / "constants.py"
        src.write_text(
            "MAX_PAGE_SIZE = 200\n"
            "DEFAULT_PAGE_SIZE = 20\n"
            "ANALYTICS_CACHE_PREFIX = 'analytics:'\n"
            "ENABLED = True\n"
            "lower = 1\n"  # 非全大写 → 忽略
            "DERIVED = MAX_PAGE_SIZE * 2\n"  # 非字面量 → 忽略
            "def f():\n    X = 1\n",
            encoding="utf-8",
        )
        values = mod.parse_constants(src)
        assert values == {
            "MAX_PAGE_SIZE": 200,
            "DEFAULT_PAGE_SIZE": 20,
            "ANALYTICS_CACHE_PREFIX": "analytics:",
            "ENABLED": True,
        }

    def test_missing_file_raises(self, tmp_path):
        # 断言消息里带路径：只写 pytest.raises 上下文属于"零断言"，
        # 会被 scripts/check_no_assert_tests.py 的棘轮判为新增违规。
        with pytest.raises(FileNotFoundError) as ei:
            mod.parse_constants(tmp_path / "nope.py")
        assert "nope.py" in str(ei.value)


class TestCheck:
    def _dirs(self, tmp_path, code: str) -> list[Path]:
        d = tmp_path / "tests"
        d.mkdir()
        (d / "test_x.py").write_text(code, encoding="utf-8")
        return [d]

    def test_detects_stale_assertion(self, tmp_path):
        problems = mod.check({"MAX_PAGE_SIZE": 200}, self._dirs(tmp_path, "assert MAX_PAGE_SIZE == 100\n"))
        assert len(problems) == 1
        assert "MAX_PAGE_SIZE" in problems[0] and "200" in problems[0]

    def test_accepts_matching_assertion(self, tmp_path):
        problems = mod.check({"MAX_PAGE_SIZE": 200}, self._dirs(tmp_path, "assert MAX_PAGE_SIZE == 200\n"))
        assert problems == []

    def test_accepts_reverse_equality(self, tmp_path):
        problems = mod.check({"MAX_PAGE_SIZE": 200}, self._dirs(tmp_path, "assert 200 == MAX_PAGE_SIZE\n"))
        # 反向写法不在本门禁口径内（词法级 NAME == literal），不误报
        assert problems == []

    def test_ignores_unknown_constant(self, tmp_path):
        problems = mod.check({"MAX_PAGE_SIZE": 200}, self._dirs(tmp_path, "assert OTHER_CONST == 1\n"))
        assert problems == []

    def test_ignores_variable_comparison(self, tmp_path):
        problems = mod.check({"MAX_PAGE_SIZE": 200}, self._dirs(tmp_path, "assert MAX_PAGE_SIZE == other\n"))
        assert problems == []

    def test_string_constant(self, tmp_path):
        problems = mod.check(
            {"ANALYTICS_CACHE_PREFIX": "analytics:"},
            self._dirs(tmp_path, "assert ANALYTICS_CACHE_PREFIX == 'analytics'\n"),
        )
        assert len(problems) == 1


class TestCli:
    def test_json_output_on_clean_tree(self, tmp_path, capsys):
        d = tmp_path / "tests"
        d.mkdir()
        (d / "test_x.py").write_text("assert MAX_PAGE_SIZE == 200\n", encoding="utf-8")
        rc = mod.main(["--json", "--dirs", str(d)])
        out = capsys.readouterr().out.strip()
        assert rc == 0
        assert '"problems": []' in out

    def test_exit_1_on_drift(self, tmp_path, capsys):
        d = tmp_path / "tests"
        d.mkdir()
        (d / "test_x.py").write_text("assert MAX_PAGE_SIZE == 100\n", encoding="utf-8")
        rc = mod.main(["--dirs", str(d)])
        assert rc == 1
        assert "常量断言漂移" in capsys.readouterr().out
