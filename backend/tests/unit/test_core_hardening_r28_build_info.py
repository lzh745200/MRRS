"""R28 · T1 低危回归：build_info 的 git 探测守卫。

R27 报告（T1 低危项）：
    ``get_build_info()`` 在缺少 ``_build_info.json`` 时**无条件**执行
    ``subprocess.check_output(["git", "rev-parse", ...], timeout=5)``。打包环境
    （PyInstaller/Electron，无 git、无 .git）与未装 git 的离线终端上，这次调用
    只会白等到超时/抛异常后才回退 ``"dev"``，把进程内首次版本查询（含未鉴权的
    ``/health``）拖慢数秒。

R28 修复：
    * 新增 ``_has_git_worktree()`` —— 只有确实存在 ``.git`` 才尝试调用 git；
    * 超时由 5s 收紧到 2s。

本文件锁定：无 git 时不产生子进程；有 git 时仍能取到 hash；取不到时回退 "dev"。
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core import build_info as bi


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    """get_build_info 有进程级缓存，逐条用例重置。"""
    monkeypatch.setattr(bi, "_cached", None)
    yield


class TestHasGitWorktree:
    def test_false_when_no_git_anywhere(self, tmp_path):
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        assert bi._has_git_worktree(deep) is False

    def test_true_when_git_dir_present(self, tmp_path):
        (tmp_path / ".git").mkdir()
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        assert bi._has_git_worktree(deep) is True

    def test_true_when_git_is_file(self, tmp_path):
        """worktree / submodule 的 .git 是文件而非目录（故必须用 exists()）。"""
        deep = tmp_path / "a"
        deep.mkdir()
        (tmp_path / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x", encoding="utf-8")
        assert bi._has_git_worktree(deep) is True

    def test_default_start_points_are_used(self, monkeypatch, tmp_path):
        """不传参时以「本文件位置 + CWD」为起点（默认分支可执行）。

        W25 修复（2026-10-20）：原断言 ``is False`` 依赖「pytest 临时根向上 4 层
        内没有 .git」，而 pytest 的 basetemp 默认落在 rootdir（``backend/``）下，
        向上第 4 层恰好是仓库根 —— **任何 git checkout 内该断言必失败**
        （pr-checks 第 12 段 final coverage gate 恒红）。

        改为在临时根下再下钻 6 层作为起点：仍然走「不传参」的默认分支，
        但 4 层窗口内不可能触及仓库根的 .git，断言与运行环境解耦。
        """
        deep = tmp_path
        for part in ("a", "b", "c", "d", "e", "f"):
            deep = deep / part
        deep.mkdir(parents=True)

        monkeypatch.setattr(bi, "__file__", str(deep / "build_info.py"))
        monkeypatch.setattr(bi.Path, "cwd", classmethod(lambda cls: deep))
        assert bi._has_git_worktree() is False


class TestGetBuildInfoWithoutGit:
    def test_dev_fallback_skips_subprocess(self, monkeypatch):
        """核心修复：无 .git 时不得启动 git 子进程（否则离线首查卡 5s）。"""
        monkeypatch.setattr(bi, "_load", lambda: {})
        monkeypatch.setattr(bi, "_has_git_worktree", lambda start=None: False)
        subprocess_mock = MagicMock(side_effect=AssertionError("不得调用子进程"))
        monkeypatch.setattr(bi.subprocess, "check_output", subprocess_mock)

        info = bi.get_build_info()

        assert info["git_hash"] == "dev"
        assert info["builder"] == "dev"
        subprocess_mock.assert_not_called()

    def test_git_present_uses_short_hash(self, monkeypatch):
        monkeypatch.setattr(bi, "_load", lambda: {})
        monkeypatch.setattr(bi, "_has_git_worktree", lambda start=None: True)
        monkeypatch.setattr(
            bi.subprocess, "check_output",
            MagicMock(return_value=b"abc1234\n"),
        )

        info = bi.get_build_info()

        assert info["git_hash"] == "abc1234"
        assert info["builder"] == "dev"

    def test_git_failure_falls_back_to_dev(self, monkeypatch):
        monkeypatch.setattr(bi, "_load", lambda: {})
        monkeypatch.setattr(bi, "_has_git_worktree", lambda start=None: True)
        monkeypatch.setattr(
            bi.subprocess, "check_output",
            MagicMock(side_effect=OSError("git not found")),
        )

        info = bi.get_build_info()

        assert info["git_hash"] == "dev"

    def test_metadata_present_skips_dev_fallback(self, monkeypatch):
        """有 _build_info.json 时（CI 产物）不探测 git，直接用元数据。"""
        monkeypatch.setattr(bi, "_load", lambda: {"git_hash": "cihash", "build_time": "t", "builder": "ci"})
        subprocess_mock = MagicMock(side_effect=AssertionError("不得调用子进程"))
        monkeypatch.setattr(bi.subprocess, "check_output", subprocess_mock)

        info = bi.get_build_info()

        assert info["git_hash"] == "cihash"
        assert info["builder"] == "ci"
        subprocess_mock.assert_not_called()

    def test_version_is_defaulted_and_cached(self, monkeypatch):
        monkeypatch.setattr(bi, "_load", lambda: {})
        monkeypatch.setattr(bi, "_has_git_worktree", lambda start=None: False)

        first = bi.get_build_info()
        second = bi.get_build_info()

        from app.core.config import settings

        assert first["version"] == settings.PROJECT_VERSION
        assert first is second  # 进程级缓存
