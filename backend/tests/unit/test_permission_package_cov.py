"""app.api.v1.permission_package 覆盖率攻坚测试

覆盖 4 个端点全部分支：
- export：成功 / 失败 500 / body 为 None
- download：文件不存在 404 / 正常 FileResponse
- import：非 zip 400 / 成功 / 异常清理+500 / 清理 OSError 降级
- confirm：文件缺失 404 / 成功 / 失败 500 / 异常时 finally 清理 / 清理 OSError 降级
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.permission_package as pp


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


def _req():
    """W1-T2 新签名所需的 Request 桩（loopback 地址）。"""
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


@pytest.fixture
def svc():
    with patch.object(pp, "PermissionPackageService") as m:
        yield m.return_value


class TestExport:
    def test_success(self, svc):
        svc.export_package.return_value = {"success": True, "file": "x.zip"}
        body = SimpleNamespace(password="p", description="d")
        resp = pp.export_permission_package(body, _admin(), MagicMock())
        assert resp.status_code == 200

    def test_failure_500(self, svc):
        svc.export_package.return_value = {"success": False, "message": "打包错误"}
        with pytest.raises(HTTPException) as exc_info:
            pp.export_permission_package(None, _admin(), MagicMock())
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "打包错误"


class TestDownload:
    def test_not_found_404(self, tmp_path):
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                pp.download_permission_package("missing.zip", _admin())
        assert exc_info.value.status_code == 404

    def test_success(self, tmp_path):
        f = tmp_path / "pkg.zip"
        f.write_bytes(b"PK")
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            resp = pp.download_permission_package("pkg.zip", _admin())
        assert resp.media_type == "application/zip"


class TestImport:
    async def test_not_zip_400(self):
        file = SimpleNamespace(filename="data.txt")
        with pytest.raises(HTTPException) as exc_info:
            await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 400

    async def test_success(self, svc, tmp_path):
        svc.import_package.return_value = {"success": True, "preview": {}}
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=b"PK"))
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            resp = await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert resp.status_code == 200
        assert (tmp_path / "pkg.zip").exists()

    async def test_exception_cleanup_500(self, svc, tmp_path):
        svc.import_package.side_effect = RuntimeError("bad zip")
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=b"PK"))
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 500
        assert "bad zip" in exc_info.value.detail
        assert not (tmp_path / "pkg.zip").exists()  # 异常时文件已清理

    async def test_exception_cleanup_oserror_degrades(self, svc, tmp_path):
        svc.import_package.side_effect = RuntimeError("bad zip")
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=b"PK"))
        with (
            patch("app.utils.paths.get_uploads_path", return_value=tmp_path),
            patch.object(pp.os, "unlink", side_effect=OSError("locked")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 500


class TestConfirm:
    def test_file_missing_404(self, svc, tmp_path):
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package("missing.zip", SimpleNamespace(overwrite_existing=False), _admin(), MagicMock())
        assert exc_info.value.status_code == 404

    def test_success(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.return_value = {"success": True}
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            resp = pp.confirm_import_permission_package("pkg.zip", SimpleNamespace(overwrite_existing=True), _admin(), MagicMock())
        assert resp.status_code == 200
        assert not (tmp_path / "pkg.zip").exists()  # 成功后清理

    def test_failure_500(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.return_value = {"success": False, "message": "校验失败"}
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package("pkg.zip", SimpleNamespace(overwrite_existing=False), _admin(), MagicMock())
        assert exc_info.value.status_code == 500

    def test_service_raises_still_cleans_up(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.side_effect = RuntimeError("crash")
        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            with pytest.raises(RuntimeError):
                pp.confirm_import_permission_package("pkg.zip", SimpleNamespace(overwrite_existing=False), _admin(), MagicMock())
        assert not (tmp_path / "pkg.zip").exists()

    def test_cleanup_oserror_degrades(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.return_value = {"success": True}
        with (
            patch("app.utils.paths.get_uploads_path", return_value=tmp_path),
            patch.object(pp.os, "unlink", side_effect=OSError("locked")),
        ):
            resp = pp.confirm_import_permission_package("pkg.zip", SimpleNamespace(overwrite_existing=False), _admin(), MagicMock())
        assert resp.status_code == 200

