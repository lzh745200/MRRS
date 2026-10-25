"""`scripts/release_tag.py` 发布入口单测（纯逻辑 + dry-run，不真的打 tag/推送）。

背景：2026-10-25 两次 tag 构建失败（v1.18.4 / v1.18.5）都源于"main 的 PR Checks 未绿就打了 tag"，
构建内的 `check_release_gate.py` 只能拒绝，无法阻止错误动作本身。
`release_tag.py` 把"绿了才打 tag"变成唯一入口。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "release_tag.py"


def _load():
    spec = importlib.util.spec_from_file_location("release_tag", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mod = _load()


class TestValidateTag:
    def test_accepts_matching_version(self):
        with patch.object(mod, "read_version", return_value="1.18.6"):
            ok, msg = mod.validate_tag("v1.18.6")
        assert ok is True and msg == ""

    def test_rejects_bad_format(self):
        with patch.object(mod, "read_version", return_value="1.18.6"):
            ok, msg = mod.validate_tag("1.18.6")
        assert ok is False and "vX.Y.Z" in msg

    def test_rejects_version_mismatch(self):
        with patch.object(mod, "read_version", return_value="1.18.6"):
            ok, msg = mod.validate_tag("v1.18.5")
        assert ok is False and "不一致" in msg

    def test_rejects_prerelease_suffix_style(self):
        with patch.object(mod, "read_version", return_value="1.18.6"):
            ok, _ = mod.validate_tag("v1.18.6-rc1")
        assert ok is False


class TestMainRefusesWithoutGreenCi:
    def test_refuses_when_worktree_dirty(self, capsys):
        with patch.object(mod, "read_version", return_value="1.18.6"), patch.object(
            mod, "current_branch", return_value="main"
        ), patch.object(mod, "is_worktree_clean", return_value=False), patch.object(
            mod, "tag_exists_locally", return_value=False
        ), patch.object(mod, "changelog_recorded", return_value=(True, "")):
            rc = mod.main(["--tag", "v1.18.6"])
        assert rc == 1
        assert "工作区不干净" in capsys.readouterr().out

    def test_refuses_on_non_main_branch(self, capsys):
        with patch.object(mod, "read_version", return_value="1.18.6"), patch.object(
            mod, "current_branch", return_value="feature/x"
        ), patch.object(mod, "is_worktree_clean", return_value=True), patch.object(
            mod, "tag_exists_locally", return_value=False
        ), patch.object(mod, "changelog_recorded", return_value=(True, "")):
            rc = mod.main(["--tag", "v1.18.6"])
        assert rc == 1
        assert "发布必须从 main 切" in capsys.readouterr().out

    def test_refuses_when_ci_not_green(self, capsys):
        with patch.object(mod, "read_version", return_value="1.18.6"), patch.object(
            mod, "current_branch", return_value="main"
        ), patch.object(mod, "is_worktree_clean", return_value=True), patch.object(
            mod, "tag_exists_locally", return_value=False
        ), patch.object(mod, "changelog_recorded", return_value=(True, "")), patch.object(
            mod, "head_sha", return_value="a" * 40
        ), patch.object(mod, "ci_green", return_value=(False, "no completed run")):
            rc = mod.main(["--tag", "v1.18.6"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "NOT GREEN" in out
        assert "禁止打 tag" in out

    def test_dry_run_ok_when_all_green(self, capsys):
        with patch.object(mod, "read_version", return_value="1.18.6"), patch.object(
            mod, "current_branch", return_value="main"
        ), patch.object(mod, "is_worktree_clean", return_value=True), patch.object(
            mod, "tag_exists_locally", return_value=False
        ), patch.object(mod, "changelog_recorded", return_value=(True, "")), patch.object(
            mod, "head_sha", return_value="b" * 40
        ), patch.object(mod, "ci_green", return_value=(True, "")):
            rc = mod.main(["--tag", "v1.18.6"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "dry-run 通过" in out

    def test_apply_runs_git_tag_and_push(self):
        calls: list[list[str]] = []

        def fake_run(cmd, check=False):
            calls.append(cmd)

            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()

        with patch.object(mod, "read_version", return_value="1.18.6"), patch.object(
            mod, "current_branch", return_value="main"
        ), patch.object(mod, "is_worktree_clean", return_value=True), patch.object(
            mod, "tag_exists_locally", return_value=False
        ), patch.object(mod, "changelog_recorded", return_value=(True, "")), patch.object(
            mod, "head_sha", return_value="c" * 40
        ), patch.object(mod, "ci_green", return_value=(True, "")), patch.object(mod, "_run", fake_run):
            rc = mod.main(["--tag", "v1.18.6", "--apply"])
        assert rc == 0
        assert ["git", "tag", "v1.18.6", "c" * 40] in calls
        assert ["git", "push", "origin", "v1.18.6"] in calls
