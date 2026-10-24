"""Tests for app.core.static_files — 100% coverage."""

import os
import sys
from unittest.mock import MagicMock, patch
from fastapi import FastAPI


class TestFindFrontendDir:
    def test_env_var_takes_priority(self):
        with patch.dict(os.environ, {"FRONTEND_DIST_PATH": "/custom/frontend"}), patch(
            "os.path.isfile", return_value=True
        ):
            from app.core.static_files import find_frontend_dir
            result = find_frontend_dir()
            assert result == "/custom/frontend"

    def test_env_var_set_but_no_index_html(self):
        with patch.dict(os.environ, {"FRONTEND_DIST_PATH": "/empty/dir"}), patch(
            "os.path.isfile", return_value=False
        ):
            from app.core.static_files import find_frontend_dir
            result = find_frontend_dir()
            assert result is None

    def test_frozen_meipass(self):
        with patch.dict(os.environ, {}), patch.object(
            sys, "_MEIPASS", "/frozen/app", create=True
        ), patch("os.path.isfile", side_effect=lambda p: "frozen" in p):
            from app.core.static_files import find_frontend_dir
            result = find_frontend_dir()
            assert result is not None
            assert "frozen" in result

    def test_no_candidates_found(self):
        with patch.dict(os.environ, {}), patch.object(
            sys, "_MEIPASS", "", create=True
        ), patch("os.path.isfile", return_value=False):
            from app.core.static_files import find_frontend_dir
            result = find_frontend_dir()
            assert result is None


class TestSetupStaticFiles:
    def test_mounts_uploads(self):
        app = FastAPI()
        with patch(
            "app.core.static_files.settings"
        ) as mock_settings, patch(
            "app.core.static_files.get_uploads_path",
            return_value="/tmp/uploads",
        ), patch("os.makedirs"), patch(
            "app.core.static_files.find_frontend_dir", return_value="/tmp/frontend"
        ), patch(
            "app.core.static_files.StaticFiles", return_value=MagicMock()
        ):
            mock_settings.UPLOAD_DIR = "/tmp/uploads"
            from app.core.static_files import setup_static_files
            result = setup_static_files(app)
            assert result == "/tmp/frontend"

    def test_permission_error_fallback(self):
        app = FastAPI()
        with patch(
            "app.core.static_files.settings"
        ) as mock_settings, patch(
            "app.core.static_files.get_uploads_path",
            return_value="/fallback/uploads",
        ), patch(
            "os.makedirs", side_effect=[PermissionError, None]
        ), patch(
            "app.core.static_files.find_frontend_dir", return_value=None
        ), patch(
            "app.core.static_files.StaticFiles", return_value=MagicMock()
        ):
            mock_settings.UPLOAD_DIR = "/restricted/dir"
            from app.core.static_files import setup_static_files
            result = setup_static_files(app)
            assert result is None

    def test_relative_upload_dir(self):
        app = FastAPI()
        with patch(
            "app.core.static_files.settings"
        ) as mock_settings, patch(
            "app.core.static_files.get_uploads_path",
            return_value="/resolved/uploads",
        ), patch("os.makedirs"), patch(
            "app.core.static_files.find_frontend_dir", return_value="/app/frontend"
        ), patch(
            "app.core.static_files.StaticFiles", return_value=MagicMock()
        ):
            mock_settings.UPLOAD_DIR = "relative/path"
            from app.core.static_files import setup_static_files
            result = setup_static_files(app)
            assert result == "/app/frontend"


class TestOnedirLayoutDiscovery:
    """PyInstaller onedir 真实结构：<resources>/backend/assistance-backend/_internal。

    前端产物在 <resources>/frontend（与 backend 同级）。此用例锁定"上溯三级"推导：
    Electron 侧一旦漏传 FRONTEND_DIST_PATH，后端仍能自己找到前端，避免白屏 404。
    """

    def _make_layout(self, tmp_path):
        resources = tmp_path / "resources"
        meipass = resources / "backend" / "assistance-backend" / "_internal"
        meipass.mkdir(parents=True)
        frontend = resources / "frontend"
        frontend.mkdir(parents=True)
        (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
        return resources, meipass, frontend

    def test_onedir_meipass_resolves_sibling_frontend(self, tmp_path, monkeypatch):
        resources, meipass, frontend = self._make_layout(tmp_path)
        monkeypatch.delenv("FRONTEND_DIST_PATH", raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

        from app.core.static_files import find_frontend_dir

        assert find_frontend_dir() == str(frontend)

    def test_onedir_layout_path_math(self, tmp_path):
        """推导口径锁定：_MEIPASS 上溯三级即 <resources>，前端在其下的 frontend/。

        （不直接调 find_frontend_dir：开发态源码树 frontend/dist 会抢先命中，
        该用例只验证"打包结构下推导出的路径确实指向前端目录"。）
        """
        resources, meipass, frontend = self._make_layout(tmp_path)
        assert (meipass.parent.parent.parent / "frontend").resolve() == frontend.resolve()
        assert (frontend / "index.html").is_file()

    def test_env_var_still_wins_over_layout(self, tmp_path, monkeypatch):
        """Electron 显式传参优先（不破坏既有契约）。"""
        resources, meipass, frontend = self._make_layout(tmp_path)
        other = tmp_path / "explicit"
        other.mkdir()
        (other / "index.html").write_text("<html></html>", encoding="utf-8")
        monkeypatch.setenv("FRONTEND_DIST_PATH", str(other))
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

        from app.core.static_files import find_frontend_dir

        assert find_frontend_dir() == str(other)
