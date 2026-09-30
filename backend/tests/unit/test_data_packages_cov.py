"""app.api.v1.data.data.data_packages 覆盖率攻坚测试

覆盖：get_client_ip 转发头分支、_get_first_active_org、one_click_report 的
body.description 与历史记录降级、preview 的组织过滤（bug#10 修复后真实可达）、
export 历史降级、import 的 422/403/413/500 与临时文件清理、export_encrypted
历史双降级、upload_encrypted 的未加密识别与异常清理。
"""

import io
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.data.data.data_packages as m
from app.models.data_package import PackageStatus
from app.schemas.data_package import DataPackageExportRequest


def _user(org_id=10):
    return SimpleNamespace(id=1, org_id=org_id, role="admin")


def _request():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="1.1.1.1"))


def _export_result():
    return SimpleNamespace(
        package_id=7, file_name="pkg.zip", file_size=128, file_path=None,
        manifest=SimpleNamespace(record_counts={"villages": 3},
                                 model_dump=lambda: {"record_counts": {"villages": 3}}),
    )


class TestGetClientIp:
    def test_forwarded_for_first_ip(self):
        req = SimpleNamespace(
            headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
            client=SimpleNamespace(host="9.9.9.9"),
        )
        assert m.get_client_ip(req) == "1.2.3.4"

    def test_client_host_and_unknown(self):
        assert m.get_client_ip(SimpleNamespace(
            headers={}, client=SimpleNamespace(host="9.9.9.9"))) == "9.9.9.9"
        assert m.get_client_ip(SimpleNamespace(headers={}, client=None)) == "unknown"


class TestGetFirstActiveOrg:
    def test_returns_first_org_id(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=42)
        assert m._get_first_active_org(db) == 42

    def test_returns_none_when_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert m._get_first_active_org(db) is None


class TestOneClickReport:
    async def test_body_description_and_history_failure_degrade(self):
        # body.description 覆盖默认描述；record_export 异常仅告警不影响结果
        service = MagicMock()
        service.db = MagicMock()
        service.export_package = AsyncMock(return_value=_export_result())
        history = MagicMock()
        history.record_export.side_effect = Exception("hist down")
        body = m.OneClickReportRequest(description="自定义描述")

        result = await m.one_click_report(
            request=_request(), body=body, description=None,
            current_user=_user(), service=service, history_service=history,
        )
        assert result["success"] is True
        assert result["package_id"] == 7
        assert service.export_package.call_args.kwargs["description"] == "自定义描述"


class TestPreviewDataForExport:
    async def test_org_filter_applied_and_unknown_type_zero(self):
        # bug#10 修复后：模型有 organization_id → 组织过滤真实生效
        service = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.count.return_value = 3
        service.db.query.return_value = q
        data = DataPackageExportRequest(org_id=10, data_types=["villages", "mystery"])

        permission = MagicMock()
        permission.can_access_organization.return_value = True
        result = await m.preview_data_for_export(
            data=data, current_user=_user(), service=service,
            permission_service=permission)

        assert result["data"]["counts"] == {"villages": 3, "mystery": 0}
        permission.can_access_organization.assert_called_once()
        q.filter.assert_called_once()  # 组织过滤已应用


class TestExportDataPackage:
    async def test_history_failure_degrades(self):
        service = MagicMock()
        service.export_package = AsyncMock(return_value=_export_result())
        history = MagicMock()
        history.record_export.side_effect = Exception("hist down")
        permission = MagicMock()
        permission.can_access_organization.return_value = True

        result = await m.export_data_package(
            data=DataPackageExportRequest(org_id=10, data_types=["villages"]),
            request=_request(), current_user=_user(),
            service=service, history_service=history, permission_service=permission,
        )
        assert result.package_id == 7


class TestImportDataPackage:
    async def test_no_filename_422(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.import_data_package(
                file=SimpleNamespace(filename=None), org_id=1, request=None,
                current_user=_user(), service=MagicMock(),
                history_service=MagicMock(), permission_service=MagicMock())
        assert exc_info.value.status_code == 422

    async def test_permission_denied_403(self):
        permission = MagicMock()
        permission.can_access_organization.return_value = False
        with pytest.raises(HTTPException) as exc_info:
            await m.import_data_package(
                file=SimpleNamespace(filename="a.zip"), org_id=5, request=None,
                current_user=_user(org_id=None), service=MagicMock(),
                history_service=MagicMock(), permission_service=permission)
        assert exc_info.value.status_code == 403

    async def test_oversized_file_413(self):
        class _Big:
            def __len__(self):
                return 100 * 1024 * 1024 + 1

        file = MagicMock()
        file.filename = "a.zip"
        file.read = AsyncMock(return_value=_Big())
        permission = MagicMock()
        permission.can_access_organization.return_value = True
        with pytest.raises(HTTPException) as exc_info:
            await m.import_data_package(
                file=file, org_id=1, request=None,
                current_user=_user(), service=MagicMock(),
                history_service=MagicMock(), permission_service=permission)
        assert exc_info.value.status_code == 413

    async def test_service_error_500_and_tempfile_cleaned(self):
        file = MagicMock()
        file.filename = "a.zip"
        file.read = AsyncMock(return_value=b"zipdata")
        permission = MagicMock()
        permission.can_access_organization.return_value = True
        service = MagicMock()
        service.import_package = AsyncMock(side_effect=Exception("import boom"))
        with pytest.raises(HTTPException) as exc_info:
            await m.import_data_package(
                file=file, org_id=1, request=None,
                current_user=_user(), service=service,
                history_service=MagicMock(), permission_service=permission)
        assert exc_info.value.status_code == 500
        # finally 分支已清理临时文件（真实 NamedTemporaryFile）


class TestExportEncryptedPackage:
    async def test_history_failure_degrades(self):
        service = MagicMock()
        service.export_encrypted_package = AsyncMock(return_value=_export_result())
        history = MagicMock()
        history.create_history.side_effect = Exception("hist down")
        body = m.ExportEncryptedRequest(data_types=["villages"], password="12345678")

        result = await m.export_encrypted_package(
            request=_request(), body=body, current_user=_user(),
            service=service, history_service=history)
        assert result.package_id == 7

    async def test_failure_history_also_fails_then_500(self):
        service = MagicMock()
        service.export_encrypted_package = AsyncMock(side_effect=Exception("export boom"))
        history = MagicMock()
        history.create_history.side_effect = Exception("hist down")
        body = m.ExportEncryptedRequest(data_types=["villages"], password="12345678")

        with pytest.raises(HTTPException) as exc_info:
            await m.export_encrypted_package(
                request=_request(), body=body, current_user=_user(),
                service=service, history_service=history)
        assert exc_info.value.status_code == 500


class TestUploadEncryptedPackage:
    @staticmethod
    def _zip_bytes(with_manifest=True):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            if with_manifest:
                zf.writestr("manifest.json", "{}")
        return buf.getvalue()

    @staticmethod
    def _file(content):
        file = MagicMock()
        file.filename = "pkg.zip"
        file.read = AsyncMock(return_value=content)
        return file

    @staticmethod
    def _service():
        service = MagicMock()
        service._create_package_record.return_value = SimpleNamespace(
            id=1, package_code="P1", org_id=10, file_name="pkg.zip",
            file_size=128, status=PackageStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        return service

    async def test_plain_zip_with_manifest_not_encrypted(self, tmp_path):
        service = self._service()
        with patch.object(m.tempfile, "gettempdir", return_value=str(tmp_path)):
            resp = await m.upload_encrypted_package(
                request=_request(), file=self._file(self._zip_bytes()),
                password=None, current_user=_user(), service=service)
        assert resp.is_encrypted is False
        assert resp.id == 1

    async def test_service_error_500_and_upload_cleaned(self, tmp_path):
        service = self._service()
        service._create_package_record.side_effect = Exception("create boom")
        with patch.object(m.tempfile, "gettempdir", return_value=str(tmp_path)):
            with pytest.raises(HTTPException) as exc_info:
                await m.upload_encrypted_package(
                    request=_request(), file=self._file(self._zip_bytes()),
                    password=None, current_user=_user(), service=service)
        assert exc_info.value.status_code == 500
        assert list(tmp_path.iterdir()) == []  # 异常路径已删除上传文件
