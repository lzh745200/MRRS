"""`scripts/check_changelog.py` 门禁的回归测试（W27 交付后追加）。

## 为什么要给门禁本身写测试

门禁的价值在于"能红"——一个永远返回 0 的检查等于没有。
本文件对每条规则都构造一个**必须被判红**的输入（负向用例），
并用真实仓库文件跑一次正向用例，防止有人把校验逻辑改成空转。

同时锁定一个刻意的设计取舍：**不追溯历史遗留段**
（早期 `未发布` / `Unreleased` / `1.2.0-build` 之类占位与重复段），
只保证"从今往后不再新增问题"。
"""

import datetime as dt
import importlib.util
import pathlib
import subprocess
import sys

import pytest

# backend/tests/unit/test_changelog_gate.py → 上溯 3 级才是仓库根
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_changelog.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_changelog_mod", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load()


TODAY = dt.date(2026, 10, 25)


class TestParseEntries:
    def test_parses_version_date_title_and_bullets(self, mod):
        text = (
            "# 更新日志\n\n"
            "## [1.2.3] - 2026-10-24 — 一句话主题\n\n"
            "### Added\n\n- 第一条\n- 第二条\n\n"
            "## [1.2.2] - 2026-10-23\n\n- 旧条目\n"
        )
        entries = mod.parse_entries(text)
        assert [e["version"] for e in entries] == ["1.2.3", "1.2.2"]
        assert entries[0]["date"] == "2026-10-24"
        assert entries[0]["title"] == "一句话主题"
        assert len(entries[0]["bullets"]) == 2
        assert entries[1]["title"] == ""
        assert len(entries[1]["bullets"]) == 1

    def test_ignores_lines_before_first_header(self, mod):
        entries = mod.parse_entries("# 标题\n\n前言不计入\n\n## [1.0.0] - 2026-01-01\n\n- x\n")
        assert len(entries) == 1
        assert entries[0]["version"] == "1.0.0"


class TestValidatePositive:
    def test_clean_changelog_passes(self, mod):
        text = (
            "## [1.18.1] - 2026-10-24 — 主题\n\n- 变更\n\n"
            "## [1.18.0] - 2026-10-24 — 主题\n\n- 变更\n"
        )
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY)
        assert problems == []

    def test_legacy_garbage_below_window_is_tolerated(self, mod):
        """窗口外的历史遗留段不追溯（这是刻意的取舍，不是漏检）。"""
        text = (
            "## [1.18.1] - 2026-10-24 — 主题\n\n- 变更\n\n"
            "## [1.18.0] - 2026-10-24 — 主题\n\n- 变更\n\n"
            "## [1.17.0] - 2026-10-23 — 主题\n\n- 变更\n\n"
            "## [未发布] - 2026-01-01\n\n- 占位\n\n"
            "## [1.15.8] - 2026-01-01\n\n- 旧\n\n"
            "## [1.15.8] - 2026-01-02\n\n- 重复段\n"
        )
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY, strict_top=3)
        assert problems == []


class TestValidateNegative:
    def test_empty_changelog_rejected(self, mod):
        problems = mod.validate([], "1.18.1", today=TODAY)
        assert problems and "未找到任何" in problems[0]

    def test_current_version_missing_rejected(self, mod):
        text = "## [1.18.0] - 2026-10-24 — 主题\n\n- 变更\n"
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY)
        assert any("当前版本 `1.18.1` 在 CHANGELOG 中没有条目" in p for p in problems)

    def test_empty_section_rejected(self, mod):
        text = "## [1.18.1] - 2026-10-24 — 主题\n\n### Added\n\n## [1.18.0] - 2026-10-24\n\n- 变更\n"
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY)
        assert any("只有标题没有条目" in p for p in problems)

    def test_missing_title_on_newest_rejected(self, mod):
        text = "## [1.18.1] - 2026-10-24\n\n- 变更\n"
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY)
        assert any("缺少标题" in p for p in problems)

    def test_out_of_order_rejected(self, mod):
        text = (
            "## [1.17.0] - 2026-10-20 — 旧\n\n- 变更\n\n"
            "## [1.18.1] - 2026-10-24 — 新\n\n- 变更\n"
        )
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY)
        assert any("严格降序" in p for p in problems)

    def test_invalid_version_format_in_window_rejected(self, mod):
        text = "## [Unreleased] - 2026-10-24 — 主题\n\n- 变更\n"
        problems = mod.validate(mod.parse_entries(text), None, today=TODAY)
        assert any("不是 x.y.z 形式" in p for p in problems)

    def test_future_date_rejected_globally(self, mod):
        text = "## [1.18.1] - 2026-12-31 — 主题\n\n- 变更\n"
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY)
        assert any("晚于今天" in p for p in problems)

    def test_strict_top_zero_still_checks_one(self, mod):
        """strict_top 传 0/负数时至少校验最新一段，避免"关掉门禁"。"""
        text = "## [1.18.1] - 2026-10-24 — 主题\n\n### Added\n"
        problems = mod.validate(mod.parse_entries(text), "1.18.1", today=TODAY, strict_top=0)
        assert any("只有标题没有条目" in p for p in problems)


class TestRepositoryPasses:
    def test_real_repository_changelog_passes(self):
        """真实仓库当前状态必须通过（否则 CI 会红，本用例会先红）。"""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "[changelog] OK" in proc.stdout

    def test_missing_file_exits_nonzero(self, tmp_path):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--changelog", str(tmp_path / "nope.md")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode == 1
        assert "找不到" in proc.stderr

    def test_ci_wiring_present(self):
        """门禁必须真的接进 CI —— 否则脚本写得再好也是摆设。"""
        workflow = (REPO_ROOT / ".github" / "workflows" / "pr-checks.yml").read_text(
            encoding="utf-8"
        )
        assert "check_changelog.py" in workflow
