"""`scripts/check_nightly_test_parity.py` 门禁单测。

背景（2026-10-25）：Nightly 的 6 段分组漏了 `backend/tests/*.py` 根目录测试，
导致 `app/api/v1/permission_packs.py` 夜间覆盖率仅 38%、Nightly 恒红，而 PR Checks 全绿。
本门禁机械比对"Nightly 声明覆盖的 tests 路径"与"backend/tests 实际测试文件"。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_nightly_test_parity.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_nightly_test_parity", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mod = _load()


class TestRepoParity:
    def test_repository_is_covered(self):
        patterns, missing = mod.missing_tests()
        assert "tests/test_*.py" in patterns
        assert missing == []

    def test_cli_passes(self):
        assert mod.main([]) == 0


class TestDetectsGap:
    def _fake_workflow(self, tmp_path, body: str) -> Path:
        wf = tmp_path / "nightly-full.yml"
        wf.write_text(body, encoding="utf-8")
        return wf

    def test_missing_root_tests_are_reported(self, tmp_path):
        wf = self._fake_workflow(
            tmp_path,
            "run: cd backend && bash ../scripts/ci_backend_test_segment.sh "
            "--name seg1 --mode first tests/integration tests/security\n",
        )
        _patterns, missing = mod.missing_tests(wf)
        assert "tests/test_permission_packs.py" in missing
        assert any(p.startswith("tests/unit/") for p in missing)

    def test_full_coverage_has_no_missing(self, tmp_path):
        wf = self._fake_workflow(
            tmp_path,
            "run: cd backend && bash ../scripts/ci_backend_test_segment.sh "
            "--name seg1 --mode first tests/integration tests/security tests/test_*.py tests/unit\n",
        )
        _patterns, missing = mod.missing_tests(wf)
        assert missing == []


class TestPatternExtraction:
    def test_ignores_non_tests_tokens(self, tmp_path):
        wf = tmp_path / "w.yml"
        wf.write_text(
            "run: cd backend && bash ../scripts/ci_backend_test_segment.sh --name x --mode final tests/unit\n"
            "other: pytest unrelated\n",
            encoding="utf-8",
        )
        patterns = mod.nightly_patterns(wf)
        assert patterns == ["tests/unit"]
