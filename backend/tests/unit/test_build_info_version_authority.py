# -*- coding: utf-8 -*-
"""build_info 版本口径：settings.PROJECT_VERSION 是唯一权威，陈旧指纹不得覆盖。"""

import json
from pathlib import Path

import pytest

from app.core import build_info as bi


@pytest.fixture(autouse=True)
def _reset_cache():
    bi._cached = None
    yield
    bi._cached = None


class TestVersionAuthority:
    def test_fingerprint_version_overridden_by_settings(self, tmp_path, monkeypatch):
        """外壳残留旧 _build_info.json（如 1.15.7）不得让 /health 报旧版本。"""
        fp = tmp_path / "_build_info.json"
        fp.write_text(
            json.dumps({"version": "1.15.7", "git_hash": "abc123", "builder": "ci"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", fp)
        # 模拟打包外壳（无 .git）：此时才允许沿用冻结指纹
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: False)

        from app.core.config import settings

        info = bi.get_build_info()
        assert info["version"] == settings.PROJECT_VERSION
        # 指纹提供的信息仍然保留
        assert info["git_hash"] == "abc123"
        assert info["builder"] == "ci"

    def test_no_file_uses_settings_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", tmp_path / "missing.json")
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: False)

        from app.core.config import settings

        info = bi.get_build_info()
        assert info["version"] == settings.PROJECT_VERSION
        assert info["git_hash"] == "dev"
        assert info["builder"] == "dev"

    def test_matching_fingerprint_kept(self, tmp_path, monkeypatch):
        from app.core.config import settings

        fp = tmp_path / "_build_info.json"
        fp.write_text(
            json.dumps(
                {
                    "version": settings.PROJECT_VERSION,
                    "git_hash": "same",
                    "builder": "ci",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", fp)
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: False)

        info = bi.get_build_info()
        assert info["version"] == settings.PROJECT_VERSION
        assert info["git_hash"] == "same"

    def test_non_dict_json_treated_as_missing(self, tmp_path, monkeypatch):
        fp = tmp_path / "_build_info.json"
        fp.write_text('["a", "b"]', encoding="utf-8")
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", fp)
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: False)

        from app.core.config import settings

        info = bi.get_build_info()
        assert info["version"] == settings.PROJECT_VERSION

    def test_corrupt_json_treated_as_missing(self, tmp_path, monkeypatch):
        fp = tmp_path / "_build_info.json"
        fp.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", fp)
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: False)

        from app.core.config import settings

        info = bi.get_build_info()
        assert info["version"] == settings.PROJECT_VERSION

    def test_git_hash_resolved_when_worktree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", tmp_path / "missing.json")
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: True)

        fake = type("R", (), {"decode": lambda self: "deadbee\n"})()
        monkeypatch.setattr(bi.subprocess, "check_output", lambda *a, **k: fake)

        info = bi.get_build_info()
        assert info["git_hash"] == "deadbee"

    def test_git_failure_falls_back_to_dev(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", tmp_path / "missing.json")
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: True)

        def _boom(*a, **k):
            raise RuntimeError("git missing")

        monkeypatch.setattr(bi.subprocess, "check_output", _boom)
        info = bi.get_build_info()
        assert info["git_hash"] == "dev"

    def test_cached_after_first_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bi, "_BUILD_INFO_FILE", tmp_path / "missing.json")
        monkeypatch.setattr(bi, "_has_git_worktree", lambda *a, **k: False)

        first = bi.get_build_info()
        second = bi.get_build_info()
        assert first is second


class TestHasGitWorktree:
    def test_true_inside_repository(self):
        # 仓库内任意路径上溯都能命中 .git（tmp_path 也在仓库内，故不能用它模拟"无 .git"）
        assert bi._has_git_worktree(Path(__file__).resolve().parent) is True

    def test_false_at_drive_root(self):
        # 盘根没有父级、也没有 .git → False（覆盖循环结束分支）
        assert bi._has_git_worktree(Path("C:/")) is False
