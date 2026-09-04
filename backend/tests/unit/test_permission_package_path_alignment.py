"""权限包导出/下载路径对齐回归（2026-09-04）

历史缺陷（用户报障「导出权限包却没有生成」的后端根因）：
`export_package` 用**静态**解析器 `get_uploads_path()` 写 ZIP，而 download /
import / confirm 三个端点用**运行时**解析器 `get_runtime_uploads_path()`
（优先读 `UPLOAD_DIR` 环境变量，Electron 打包时由 main.js 注入
`userData/uploads`）。两者在打包环境下指向不同目录 —— 导出接口已返回
`success: true`，下载却恒 404「文件不存在或已被清理」。

本文件刻意**不 patch 任何路径解析器**：既有的
`test_permission_package_upload_safety.py` 把两个解析器 patch 到同一目录，
`test_cov_final_permission_package_service.py` 只 patch 静态那个并仅断言
`success`，因此都结构上看不见这条分叉。这里用真实的 `UPLOAD_DIR` 环境走完整
写→读链路来锁定不变量：

1. `UPLOAD_DIR` 存在时，导出文件必须落在运行时目录下
2. 导出的 `file_name` 必须能被 download 端点解析到（返回 FileResponse 而非 404）
3. 静态目录与运行时目录分叉时，导出不得写入静态目录
"""

import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.v1.permission_package as pp
from app.models.base import Base as ModelBase
from app.services.permission_package_service import PermissionPackageService
from app.utils.paths import get_runtime_uploads_path, get_uploads_path


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


@pytest.fixture
def diverged_uploads(tmp_path, monkeypatch):
    """让运行时目录与静态目录真实分叉（模拟 Electron 注入 UPLOAD_DIR）。

    返回 (db 会话, 运行时上传根, 静态上传根)。conftest 已把
    BUMOFU_BACKEND_DIR_OVERRIDE 指向会话临时根，故静态根 != tmp_path。
    """
    runtime_root = tmp_path / "runtime_uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(runtime_root))

    engine = create_engine("sqlite://")
    ModelBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    static_root = get_uploads_path()
    # 前置校验：两个解析器必须真的指向不同目录，否则本测试沦为空断言
    assert Path(static_root).resolve() != Path(runtime_root).resolve(), (
        "静态与运行时上传目录未分叉，测试前提不成立"
    )

    yield db, runtime_root, Path(static_root)

    db.close()
    engine.dispose()


class TestExportWritesToRuntimeDir:
    def test_exported_zip_lands_under_runtime_uploads(self, diverged_uploads):
        db, runtime_root, _ = diverged_uploads
        result = PermissionPackageService(db).export_package(description="对齐回归")

        assert result["success"] is True
        expected_dir = get_runtime_uploads_path("permission_packages")
        assert Path(result["file_path"]).parent.resolve() == Path(expected_dir).resolve()
        assert Path(result["file_path"]).is_file()
        assert Path(result["file_path"]).stat().st_size > 0

    def test_exported_zip_not_written_to_static_dir(self, diverged_uploads):
        """分叉时静态目录必须为空 —— 否则说明又写回了错误的一侧。"""
        db, _, static_root = diverged_uploads
        result = PermissionPackageService(db).export_package()

        static_pkg_dir = static_root / "permission_packages"
        assert not (static_pkg_dir / result["file_name"]).exists()

    def test_exported_zip_is_valid_package(self, diverged_uploads):
        db, _, _ = diverged_uploads
        result = PermissionPackageService(db).export_package()

        with zipfile.ZipFile(result["file_path"], "r") as zf:
            names = set(zf.namelist())
        assert "manifest.json" in names
        assert "data/roles.json" in names


class TestExportThenDownloadRoundtrip:
    def test_download_endpoint_serves_exported_file(self, diverged_uploads):
        """端到端：导出的 file_name 必须能被 download 端点找到。

        缺陷态下这里抛 404「文件不存在或已被清理」——正是用户看到的
        "提示导出成功却没有文件"。
        """
        db, _, _ = diverged_uploads
        result = PermissionPackageService(db).export_package()

        resp = pp.download_permission_package(result["file_name"], _admin())
        assert resp.status_code == 200
        assert resp.media_type == "application/zip"
        assert Path(resp.path).resolve() == Path(result["file_path"]).resolve()

    def test_download_after_export_with_password(self, diverged_uploads):
        db, _, _ = diverged_uploads
        result = PermissionPackageService(db).export_package(password="S3cret!pwd")

        resp = pp.download_permission_package(result["file_name"], _admin())
        assert resp.status_code == 200
        # 口令加密后文件内容不再是明文 ZIP，但文件必须真实存在于运行时目录
        assert Path(result["file_path"]).is_file()

    def test_missing_file_still_404(self, diverged_uploads):
        """反向对照：未导出的文件名仍须 404，证明上面的 200 不是因为端点失效。"""
        with pytest.raises(HTTPException) as exc_info:
            pp.download_permission_package("never_exported.zip", _admin())
        assert exc_info.value.status_code == 404


class TestImportResolvesSameDir:
    def test_import_resolver_agrees_with_export_dir(self, diverged_uploads):
        """导入侧的解析结果必须与导出目录一致（同一运行时根）。"""
        db, _, _ = diverged_uploads
        result = PermissionPackageService(db).export_package()

        resolved = pp._resolve_package_upload_path(result["file_name"])
        assert Path(resolved).resolve() == Path(result["file_path"]).resolve()
        assert os.path.isfile(resolved)
