"""W1-T2 安全回归：权限配置包上传/确认的认证与路径净化。

工单 .scratch/w1-security-redline/002
- /import：未认证仅限本机（与 /confirm 同策略）；文件名 basename 净化
- /confirm：文件名同样净化（历史缺陷可致任意文件删除）
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app

ZIP_MAGIC = b"PK\x03\x04"


@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch("app.middleware.camel_to_snake._convert_keys",
               side_effect=lambda obj, converter: (obj, False)):
        yield


@pytest.fixture
def env():
    """返回 (TestClient, mock_db, upload_dir)，并隔离上传目录。"""
    db = MagicMock()
    upload_dir = os.path.join(os.path.realpath(os.getcwd()), ".pp_test_uploads")
    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    tc = TestClient(app, raise_server_exceptions=False)
    with patch("app.utils.paths.get_uploads_path",
               side_effect=lambda *a: upload_dir):
        yield tc, db, upload_dir
    app.dependency_overrides = _original
    # 清理测试上传目录
    if os.path.isdir(upload_dir):
        for name in os.listdir(upload_dir):
            try:
                os.unlink(os.path.join(upload_dir, name))
            except OSError:
                pass
        try:
            os.rmdir(upload_dir)
        except OSError:
            pass


class TestImportAuthGate:
    """离线首导场景保留，但未认证调用必须来自本机。"""

    def test_unauthenticated_remote_rejected(self, env):
        tc, _, _ = env
        resp = tc.post(
            "/api/v1/permission-packages/import",
            files={"file": ("pkg.zip", ZIP_MAGIC, "application/zip")},
        )
        assert resp.status_code == 403
        assert "本机" in resp.json()["detail"]

    def test_unauthenticated_loopback_allowed(self, env):
        tc, db, upload_dir = env
        svc = MagicMock()
        svc.import_package.return_value = {"success": True}
        with patch("app.api.v1.permission_package._client_is_loopback", return_value=True), \
             patch("app.api.v1.permission_package.PermissionPackageService", return_value=svc):
            resp = tc.post(
                "/api/v1/permission-packages/import",
                files={"file": ("pkg.zip", ZIP_MAGIC + b"payload", "application/zip")},
            )
        assert resp.status_code == 200
        # 文件必须落在净化后的上传目录内
        svc.import_package.assert_called_once()
        used_path = svc.import_package.call_args[0][0]
        assert os.path.realpath(used_path).startswith(os.path.realpath(upload_dir))


class TestImportPathSanitize:
    def test_traversal_dotdot_rejected(self, env):
        tc, _, _ = env
        with patch("app.api.v1.permission_package._client_is_loopback", return_value=True):
            resp = tc.post(
                "/api/v1/permission-packages/import",
                files={"file": ("../../evil.zip", ZIP_MAGIC, "application/zip")},
            )
        assert resp.status_code == 400

    def test_backslash_traversal_rejected(self, env):
        tc, _, _ = env
        with patch("app.api.v1.permission_package._client_is_loopback", return_value=True):
            resp = tc.post(
                "/api/v1/permission-packages/import",
                files={"file": ("..\\evil.zip", ZIP_MAGIC, "application/zip")},
            )
        assert resp.status_code == 400

    def test_non_zip_rejected(self, env):
        tc, _, _ = env
        with patch("app.api.v1.permission_package._client_is_loopback", return_value=True):
            resp = tc.post(
                "/api/v1/permission-packages/import",
                files={"file": ("evil.exe", ZIP_MAGIC, "application/octet-stream")},
            )
        assert resp.status_code == 400


class TestConfirmPathSanitize:
    def test_confirm_traversal_rejected(self, env):
        """/confirm 的 file_name 同样必须净化（历史缺陷：finally 无条件 unlink）。"""
        tc, _, _ = env
        outside = os.path.join(os.path.realpath(os.getcwd()), ".pp_outside_target.zip")
        with open(outside, "wb") as f:
            f.write(ZIP_MAGIC)
        try:
            # 反斜杠形式（%5C）保持单段路径可到达 handler，是 Windows 下的
            # 真实遍历向量；正斜杠多段路径在路由层即 404/405，无需业务防护。
            traversal = "..%5Cbackend%5C.pp_outside_target.zip"
            with patch("app.api.v1.permission_package._client_is_loopback", return_value=True):
                resp = tc.post(f"/api/v1/permission-packages/confirm/{traversal}")
            assert resp.status_code == 400
            # 目标文件未被删除（任意文件删除缺陷已封堵）
            assert os.path.exists(outside)
        finally:
            if os.path.exists(outside):
                os.unlink(outside)

    def test_confirm_missing_file_404(self, env):
        tc, _, _ = env
        with patch("app.api.v1.permission_package._client_is_loopback", return_value=True):
            resp = tc.post("/api/v1/permission-packages/confirm/normal_pkg.zip")
        assert resp.status_code == 404
