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
