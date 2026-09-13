"""R9 数据包导入失败记录修复测试（遗留风险治理计划 2026-09-12 第三周批次）。

背景：校验失败的导入路径以 API 层临时文件路径建记录，而该临时文件由
调用方 `finally` 立即 unlink → 记录永久指向不存在文件，`/validate`、
`/download` 恒报"文件不存在"且无修复路径。

修复：失败分支不再落 `file_path`（NULL）+ 保留校验错误明细；端点对
`file_path` 为空返回明确 **409**（有别于"有路径但磁盘缺失"的 404）。
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.data.data.data_packages import (
    get_db,
    get_history_service,
    get_package_service,
    get_permission_service,
)
from app.models.data_package import PackageStatus
from app.schemas.data_package import (
    DataPackageImportResult,
    DataPackageManifest,
    DataPackageValidationResult,
)

BASE = "/api/v1/data-packages"


@contextlib.contextmanager
def _override_deps(client, svc=None, hist=None, perm=None):
    orig = client.app.dependency_overrides.copy()
    if svc is not None:
        client.app.dependency_overrides[get_package_service] = lambda: svc
    if hist is not None:
        client.app.dependency_overrides[get_history_service] = lambda: hist
    if perm is not None:
        client.app.dependency_overrides[get_permission_service] = lambda: perm
    try:
        yield
    finally:
        client.app.dependency_overrides = orig


def _rejected_package():
    pkg = MagicMock()
    pkg.id = 42
    pkg.org_id = 1
    pkg.file_path = None
    pkg.status = PackageStatus.failed.value
    pkg.error_message = "缺少 manifest.json"
    pkg.package_code = "ERR-UNKNOWN-1"
    return pkg


class TestRejectedPackageService:
    """服务层：失败记录不落 file_path。"""

    def test_create_record_accepts_null_path(self):
        from app.services.data_package_service import DataPackageService

        db = MagicMock()
        svc = DataPackageService(db, upload_dir=".")

        package = svc._create_package_record(
            None, "bad.zip", 1, 1,
            status=PackageStatus.failed, error_message="缺少 manifest.json",
        )

        assert package.file_path is None
        assert package.file_size == 0
        assert package.status == PackageStatus.failed.value
        assert package.error_message == "缺少 manifest.json"
        db.add.assert_called_once()
        db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_package_invalid_does_not_persist_temp_path(self):
        """校验失败 → 建记录时首参为 None（不再指向将被删除的临时文件）。"""
        from app.services.data_package_service import DataPackageService

        db = MagicMock()
        svc = DataPackageService(db, upload_dir=".")
        invalid = DataPackageValidationResult(
            is_valid=False, errors=[MagicMock(message="缺少 manifest.json")]
        )
        with patch.object(svc, "validate_package", AsyncMock(return_value=invalid)), patch.object(
            svc, "_create_package_record",
            MagicMock(return_value=MagicMock(id=7, package_code="ERR-UNKNOWN-7")),
        ) as mock_create:
            result = await svc.import_package("/tmp/tmpabc.zip", "bad.zip", 1, 1)

        assert mock_create.call_args[0][0] is None  # file_path 置空
        assert mock_create.call_args[1]["status"] == PackageStatus.failed
        assert "缺少 manifest.json" in mock_create.call_args[1]["error_message"]
        assert isinstance(result, DataPackageImportResult)

    @pytest.mark.asyncio
    async def test_import_package_valid_keeps_path(self):
        """校验通过路径不受影响（仍复制到 upload_dir 并落库）。"""
        from app.services.data_package_service import DataPackageService

        db = MagicMock()
        # db.refresh 替身需回填主键：真实实现由 SQLite 自增 id 回写
        db.refresh.side_effect = lambda pkg: setattr(pkg, "id", 8)
        svc = DataPackageService(db, upload_dir=".")
        manifest = DataPackageManifest(
            org_code="ORG1", data_types=["villages"], record_counts={"villages": 1}
        )
        valid = DataPackageValidationResult(
            is_valid=True, errors=[], manifest=manifest
        )
        with patch.object(svc, "validate_package", AsyncMock(return_value=valid)), patch.object(
            svc, "preview_package_data_from_file", AsyncMock(return_value=[])
        ), patch("shutil.copy"), patch("os.path.getsize", return_value=128), patch.object(
            svc, "_calculate_checksum", MagicMock(return_value="sha256:abc")
        ):
            await svc.import_package("/tmp/tmpabc.zip", "good.zip", 1, 1)

        # 校验通过路径不受 R9 影响：落库记录仍指向复制后的常驻包路径
        record = db.add.call_args[0][0]
        assert record.file_path is not None
        assert record.file_path.endswith(".zip")
        assert record.file_size == 128


class TestRejectedPackageValidateEndpoint:
    """端点层：file_path 为空的明确 409 语义。"""

    def test_validate_no_file_path_returns_409(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = _rejected_package()
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
            resp = client_with_mocked_auth.post(f"{BASE}/42/validate")

        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "已被拒绝" in detail or "校验失败" in detail
        mock_svc.validate_package.assert_not_called()

    def test_validate_with_path_still_works(self, client_with_mocked_auth):
        pkg = _rejected_package()
        pkg.file_path = "/tmp/pkg.zip"
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = pkg
        mock_svc.validate_package = AsyncMock(
            return_value=DataPackageValidationResult(is_valid=True, errors=[])
        )
        with _override_deps(client_with_mocked_auth, svc=mock_svc, hist=MagicMock()):
            resp = client_with_mocked_auth.post(f"{BASE}/42/validate")

        assert resp.status_code == 200
        mock_svc.validate_package.assert_awaited_once_with("/tmp/pkg.zip")


class TestRejectedPackageDownloadEndpoint:
    """端点层：下载对无实体文件的包返回 409。"""

    def test_download_rejected_returns_409(self, client_with_mocked_auth):
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = _rejected_package()
        perm = MagicMock()
        perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=perm):
            resp = client_with_mocked_auth.get(f"{BASE}/42/download")

        assert resp.status_code == 409
        assert "拒绝" in resp.json()["detail"]

    def test_download_with_missing_file_returns_404(self, client_with_mocked_auth):
        pkg = _rejected_package()
        pkg.file_path = "Z:/definitely/missing/pkg.zip"
        mock_svc = MagicMock()
        mock_svc.get_package.return_value = pkg
        perm = MagicMock()
        perm.can_access_organization.return_value = True
        with _override_deps(client_with_mocked_auth, svc=mock_svc, perm=perm):
            resp = client_with_mocked_auth.get(f"{BASE}/42/download")

        assert resp.status_code == 404


def test_get_db_override_unused_placeholder():
    """占位：确保依赖导入被覆盖追踪（本文件仅通过 Depends 覆盖生效）。"""
    assert callable(get_db)
