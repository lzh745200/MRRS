# -*- coding: utf-8 -*-
"""CI 抖动账本脚本的回归（`scripts/ci_flake_report.py`）。

背景（2026-10-17）：三条后端流水线都带 `--reruns`，但没有任何地方记录
"哪个用例重跑过"——实测当天 PR Checks 日志确有 `1 rerun`，无人知道是哪个用例。
本文件锁定账本脚本的解析与门禁行为：

1. **逐条清单**来自 `-rR` 的 `RERUN <nodeid>` 行（实测 JUnit XML 不记录 rerun）；
2. **汇总计数**来自 pytest 汇总行 `... 1 rerun in ...`；
3. **门禁语义**：`--max-reruns` 硬失败、`--warn-reruns` 仅告警、日志缺失默认告警不失败
   （步骤早于日志创建即失败时，不能让账本步骤再添一次假失败）。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "ci_flake_report.py"

_spec = importlib.util.spec_from_file_location("ci_flake_report", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_TAIL = "12716 passed, 10 warnings, 1 rerun in 1234.56s"


class TestLogParsing:
    def test_named_reruns_and_summary(self, tmp_path):
        log = tmp_path / "pytest.log"
        log.write_text(
            "..\n"
            "RERUN tests/unit/test_a.py::test_flaky\n"
            "R.\n"
            "RERUN tests/unit/test_a.py::test_flaky\n"
            "..\n"
            "=========================== rerun test summary info ===========================\n"
            "RERUN tests/unit/test_a.py::test_flaky\n"
            "=========================\n"
            + _TAIL + "\n",
            encoding="utf-8",
        )
        names, summary = mod.parse_log(log)
        assert names == {"tests/unit/test_a.py::test_flaky": 3}
        assert summary == 1

    def test_plain_pass_line_is_not_counted(self, tmp_path):
        log = tmp_path / "pytest.log"
        log.write_text("12716 passed, 10 warnings in 1234.56s\n", encoding="utf-8")
        names, summary = mod.parse_log(log)
        assert names == {}
        assert summary == 0

    def test_missing_log_returns_none(self, tmp_path):
        assert mod.parse_log(tmp_path / "nope.log") is None


class TestThresholds:
    def test_warn_only_does_not_fail(self, tmp_path, capsys):
        log = tmp_path / "pytest.log"
        log.write_text(_TAIL + "\n", encoding="utf-8")
        report, code = mod.build_report([str(log)], warn_threshold=0, max_threshold=None)
        assert code == 0
        assert "告警" in report

    def test_max_threshold_fails(self, tmp_path, capsys):
        log = tmp_path / "pytest.log"
        log.write_text(_TAIL + "\n", encoding="utf-8")
        report, code = mod.build_report([str(log)], warn_threshold=None, max_threshold=0)
        assert code == 1
        assert "失败" in report

    def test_no_threshold_never_fails(self, tmp_path):
        log = tmp_path / "pytest.log"
        log.write_text(_TAIL + "\n", encoding="utf-8")
        report, code = mod.build_report([str(log)], warn_threshold=None, max_threshold=None)
        assert code == 0
        assert "1 rerun" in report

    def test_missing_log_is_only_a_warning(self, tmp_path):
        report, code = mod.build_report([str(tmp_path / "nope.log")], None, None)
        assert code == 0
        assert "缺失日志" in report


class TestCli:
    def test_cli_writes_report_and_exits_zero(self, tmp_path):
        log = tmp_path / "pytest.log"
        log.write_text("RERUN tests/unit/test_x.py::test_y\n" + _TAIL + "\n", encoding="utf-8")
        out = tmp_path / "flaky-report.txt"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--log", str(log), "--out", str(out)],
            capture_output=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
        )
        assert result.returncode == 0, result.stdout
        assert out.exists()
        assert "tests/unit/test_x.py::test_y" in out.read_text(encoding="utf-8")

    def test_cli_strict_missing_fails(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--log", str(tmp_path / "nope.log"),
             "--out", str(tmp_path / "r.txt"), "--strict-missing"],
            capture_output=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
        )
        assert result.returncode == 1
        assert "::warning::" in result.stdout
