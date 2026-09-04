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
        body = SimpleNamespace(password="p", description="d", role_names=None)
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
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                pp.download_permission_package("missing.zip", _admin())
        assert exc_info.value.status_code == 404

    def test_success(self, tmp_path):
        f = tmp_path / "pkg.zip"
        f.write_bytes(b"PK")
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
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
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            resp = await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert resp.status_code == 200
        assert (tmp_path / "pkg.zip").exists()

    async def test_exception_cleanup_500(self, svc, tmp_path):
        svc.import_package.side_effect = RuntimeError("bad zip")
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 500
        # W1-T8：内部异常细节不再直出，统一为通用文案
        assert "导入预览失败" in exc_info.value.detail
        assert "bad zip" not in exc_info.value.detail
        assert not (tmp_path / "pkg.zip").exists()  # 异常时文件已清理

    async def test_exception_cleanup_oserror_degrades(self, svc, tmp_path):
        svc.import_package.side_effect = RuntimeError("bad zip")
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch.object(pp.os, "unlink", side_effect=OSError("locked")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 500

    async def test_oversize_413_and_cleanup(self, svc, tmp_path):
        """覆盖 210-211（超限 413）与 213-216（BaseException 清理后重抛）"""
        file = SimpleNamespace(
            filename="pkg.zip",
            read=AsyncMock(side_effect=[b"PK\x03\x04", b"moredata", b""]),
        )
        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch.object(pp, "_MAX_PACKAGE_UPLOAD_BYTES", 8),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 413
        assert not (tmp_path / "pkg.zip").exists()  # 零磁盘残留

    async def test_encrypted_package_writeback(self, svc, tmp_path):
        """覆盖 245-247 —— 加密包预览成功后内存明文写回保存路径"""
        svc.import_package.return_value = {
            "success": True, "preview": {}, "_decrypted_bytes": b"PLAINTEXT",
        }
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            resp = await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert resp.status_code == 200
        assert (tmp_path / "pkg.zip").read_bytes() == b"PLAINTEXT"

    async def test_machine_code_failure_degrades(self, svc, tmp_path):
        """覆盖 230-231 —— 机器码获取失败 → 空串降级，导入继续"""
        svc.import_package.return_value = {"success": True, "preview": {}}
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch.object(pp, "SessionLocal", side_effect=Exception("db down")),
        ):
            resp = await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert resp.status_code == 200
        assert svc.import_package.call_args.kwargs.get("current_machine_code") == ""

    async def test_http_exception_cleanup(self, svc, tmp_path):
        """覆盖 255-257 —— service 抛 HTTPException 时清理文件并透传状态码"""
        svc.import_package.side_effect = HTTPException(status_code=422, detail="校验失败")
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                await pp.import_permission_package(_req(), file, _admin(), MagicMock())
        assert exc_info.value.status_code == 422
        assert not (tmp_path / "pkg.zip").exists()


class TestResolveUploadPath:
    def test_realpath_escape_rejected_400(self, tmp_path):
        """覆盖 74 —— basename 校验通过但 realpath 后逃逸目录（符号链接场景）→ 400"""
        calls = {"n": 0}

        def fake_realpath(_p):
            calls["n"] += 1
            if calls["n"] == 1:
                return str(tmp_path)            # real_dir
            return "C:/Windows/evil.zip"        # file_path 逃逸

        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch.object(pp.os.path, "realpath", side_effect=fake_realpath),
        ):
            with pytest.raises(HTTPException) as exc_info:
                pp._resolve_package_upload_path("pkg.zip")
        assert exc_info.value.status_code == 400
        assert "非法文件路径" in exc_info.value.detail


class TestConfirm:
    @staticmethod
    def _body(**kw):
        return SimpleNamespace(overwrite_existing=False, mode=None, **kw)

    def test_file_missing_404(self, svc, tmp_path):
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package(
                    "missing.zip", self._body(), _admin(), MagicMock()
                )
        assert exc_info.value.status_code == 404

    def test_success(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.return_value = {"success": True}
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            resp = pp.confirm_import_permission_package(
                "pkg.zip", SimpleNamespace(overwrite_existing=True, mode=None), _admin(), MagicMock()
            )
        assert resp.status_code == 200
        assert not (tmp_path / "pkg.zip").exists()  # 成功后清理

    def test_failure_500(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.return_value = {"success": False, "message": "校验失败"}
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package(
                    "pkg.zip", self._body(), _admin(), MagicMock()
                )
        assert exc_info.value.status_code == 500

    def test_service_raises_still_cleans_up(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.side_effect = RuntimeError("crash")
        with patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            with pytest.raises(RuntimeError):
                pp.confirm_import_permission_package(
                    "pkg.zip", self._body(), _admin(), MagicMock()
                )
        assert not (tmp_path / "pkg.zip").exists()

    def test_cleanup_oserror_degrades(self, svc, tmp_path):
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        svc.confirm_import.return_value = {"success": True}
        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch.object(pp.os, "unlink", side_effect=OSError("locked")),
        ):
            resp = pp.confirm_import_permission_package(
                "pkg.zip", SimpleNamespace(overwrite_existing=True, mode=None), _admin(), MagicMock()
            )
        assert resp.status_code == 200
