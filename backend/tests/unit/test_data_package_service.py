"""数据包管理服务单元测试 (100% coverage)"""
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class _MockRecord:
    """Helper: allows __table__ attribute (MagicMock rejects dunder attrs)"""
    pass


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    with patch("app.services.data_package_service.os.makedirs"):
        with patch("app.utils.paths.get_app_data_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/test_pkg")
            from app.services.data_package_service import DataPackageService
            svc = DataPackageService(db=mock_db, upload_dir="/tmp/uploads")
            svc.logger = MagicMock()
            return svc


class TestPackageValidationError:
    async     def test_init(self):
        from app.services.data_package_service import PackageValidationError
        err = PackageValidationError(["err1", "err2", "err3", "err4"])
        assert "数据包验证失败" in str(err)
        assert err.errors == ["err1", "err2", "err3", "err4"]

    async     def test_init_few_errors(self):
        from app.services.data_package_service import PackageValidationError
        err = PackageValidationError(["err1"])
        assert "err1" in str(err)




class TestDataPackageService:
    # ===================== __init__ =====================
    async     def test_init_default_upload_dir(self, mock_db):
        with patch("app.services.data_package_service.os.makedirs"):
            with patch("app.utils.paths.get_app_data_dir") as mock_dir:
                mock_dir.return_value = Path("/tmp/test_app")
                from app.services.data_package_service import DataPackageService
                svc = DataPackageService(db=mock_db)
                assert svc.upload_dir is not None

    async     def test_init_permission_error(self, mock_db):
        with patch("app.services.data_package_service.os.makedirs") as mock_makedirs:
            mock_makedirs.side_effect = [PermissionError("denied"), None]
            with patch("app.utils.paths.get_app_data_dir") as mock_dir:
                mock_dir.return_value = Path("/tmp/test_app")
                from app.services.data_package_service import DataPackageService
                svc = DataPackageService(db=mock_db, upload_dir="/tmp/restricted")
                assert svc.upload_dir is not None

    # ===================== export_package =====================
    async     def test_export_package_org_not_found(self, service):
        service.org_service.get_organization = MagicMock(return_value=None)
        from app.core.exceptions import BusinessError
        with pytest.raises(BusinessError, match="组织不存在"):
            await service.export_package(999, ["villages"], 1)

    async     def test_export_package_success(self, service):
        org = MagicMock()
        org.id = 1
        org.code = "ORG001"
        org.name = "TestOrg"
        service.org_service.get_organization = MagicMock(return_value=org)
        service.db.refresh.side_effect = lambda pkg: setattr(pkg, 'id', 1)

        with patch.object(service, "_export_data_type") as mock_export:
            mock_export.return_value = [{"id": 1, "name": "v1"}]
            with patch.object(service, "_generate_package_code") as mock_code:
                mock_code.return_value = "EXP-ORG001-20240101000000"
                with patch.object(service, "_create_zip_package") as mock_zip:
                    with patch.object(service, "_calculate_checksum") as mock_checksum:
                        mock_checksum.return_value = "sha256:abc"
                        with patch("os.path.getsize", return_value=512):
                            result = await service.export_package(1, ["villages"], 1, description="test")
                            assert result.package_id is not None
                            assert result.file_size == 512
                            service.db.add.assert_called_once()
                            service.db.commit.assert_called()
                            service.db.refresh.assert_called_once()

    async     def test_export_package_skips_unknown_data_type(self, service):
        org = MagicMock()
        org.id = 1
        org.code = "ORG001"
        org.name = "TestOrg"
        service.org_service.get_organization = MagicMock(return_value=org)
        service.db.refresh.side_effect = lambda pkg: setattr(pkg, 'id', 1)

        with patch.object(service, "_export_data_type") as mock_export:
            mock_export.return_value = []
            with patch.object(service, "_generate_package_code") as mock_code:
                mock_code.return_value = "EXP-ORG001-CODE"
                with patch.object(service, "_create_zip_package"):
                    with patch.object(service, "_calculate_checksum") as mc:
                        mc.return_value = "sha256:000"
                        with patch("os.path.getsize", return_value=10):
                            result = await service.export_package(1, ["unknown_type", "villages"], 1)
                            mock_export.assert_called_once()  # only called for "villages"

    # ===================== _export_data_type =====================
    async     def test_export_data_type_with_org_id(self, service):
        model = MagicMock()
        model.org_id = True
        record = _MockRecord()
        tbl = MagicMock()
        col_id = MagicMock()
        col_id.name = "id"
        col_name = MagicMock()
        col_name.name = "name"
        tbl.columns = [col_id, col_name]
        record.__table__ = tbl
        record.id = 1
        record.name = "test"

        q = MagicMock()
        service.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = [record]

        result = service._export_data_type(1, model)
        assert len(result) == 1
        assert result[0]["name"] == "test"

    async     def test_export_data_type_with_organization_id(self, service):
        model = type('FakeModel', (), {'organization_id': True})()
        record = _MockRecord()
        tbl = MagicMock()
        col_id = MagicMock()
        col_id.name = "id"
        tbl.columns = [col_id]
        record.__table__ = tbl
        record.id = 1

        q = MagicMock()
        service.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = [record]

        result = service._export_data_type(1, model)
        assert len(result) == 1

    async     def test_export_data_type_datetime_decimal(self, service):
        model = MagicMock()
        model.org_id = True
        record = _MockRecord()
        tbl = MagicMock()
        col_id = MagicMock(name="id")
        col_id.name = "id"
        col_dt = MagicMock(name="created_at")
        col_dt.name = "created_at"
        col_dec = MagicMock(name="amount")
        col_dec.name = "amount"
        tbl.columns = [col_id, col_dt, col_dec]
        record.__table__ = tbl
        record.id = 1
        record.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        from decimal import Decimal
        record.amount = Decimal("100.50")

        q = MagicMock()
        service.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = [record]

        result = service._export_data_type(1, model)
        assert result[0]["created_at"] == "2024-01-01T00:00:00+00:00"
        assert result[0]["amount"] == 100.5

    async     def test_export_data_type_other_type_str(self, service):
        model = MagicMock()
        model.org_id = True
        record = _MockRecord()
        tbl = MagicMock()
        col = MagicMock(name="meta")
        col.name = "meta"
        tbl.columns = [col]
        record.__table__ = tbl
        class Custom:
            def __str__(self):
                return "custom_str"
        record.meta = Custom()

        q = MagicMock()
        service.db.query.return_value = q
        q.filter.return_value = q
        q.all.return_value = [record]

        result = service._export_data_type(1, model)
        assert result[0]["meta"] == "custom_str"

    # ===================== _create_zip_package =====================
    async     def test_create_zip_package(self, service):
        manifest = MagicMock()
        manifest.model_dump_json.return_value = '{"version": "1.0"}'
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            service._create_zip_package("/tmp/test.zip", manifest, {"villages": [{"id": 1}]})
            assert m.writestr.call_count == 2

    # ===================== validate_package =====================
    async     def test_validate_package_file_not_exists(self, service):
        with patch("os.path.exists", return_value=False):
            result = await service.validate_package("/tmp/nonexistent.zip")
            assert result.is_valid is False
            assert len(result.errors) == 1
            assert result.errors[0].message == "文件不存在"

    async     def test_validate_package_not_zip(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=False):
                result = await service.validate_package("/tmp/test.zip")
                assert result.is_valid is False
                assert len(result.errors) == 1

    async     def test_validate_package_no_manifest(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["data/villages.json"]
                    result = await service.validate_package("/tmp/test.zip")
                    assert result.is_valid is False

    async     def test_validate_package_version_unsupported(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["manifest.json"]
                    m.read.return_value = json.dumps({"version": "9.9", "data_types": []}).encode("utf-8")
                    result = await service.validate_package("/tmp/test.zip")
                    version_errors = [e for e in result.errors if "版本" in e.message]
                    assert len(version_errors) >= 1

    async     def test_validate_package_manifest_parse_error(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["manifest.json"]
                    m.read.return_value = json.dumps({"version": "1.0", "data_types": []}).encode("utf-8")
                    with patch("app.services.data_package_service.DataPackageManifest") as DPM:
                        DPM.side_effect = ValueError("bad manifest")
                        result = await service.validate_package("/tmp/test.zip")
                        manifest_errors = [e for e in result.errors if "manifest格式错误" in e.message]
                        assert len(manifest_errors) >= 1

    async     def test_validate_package_missing_data_file(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["manifest.json", "data/other.json"]
                    m.read.return_value = json.dumps({
                        "version": "1.0", "data_types": ["villages"],
                        "record_counts": {"villages": 5},
                    }).encode("utf-8")
                    result = await service.validate_package("/tmp/test.zip")
                    missing_errors = [e for e in result.errors if "缺少数据文件" in e.message]
                    assert len(missing_errors) >= 1

    async     def test_validate_package_record_count_mismatch(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["manifest.json", "data/villages.json"]
                    m.read.side_effect = [
                        json.dumps({
                            "version": "1.0", "data_types": ["villages"],
                            "record_counts": {"villages": 5},
                        }).encode("utf-8"),
                        json.dumps([{"id": 1}, {"id": 2}]).encode("utf-8"),
                    ]
                    result = await service.validate_package("/tmp/test.zip")
                    assert len(result.warnings) >= 1
                    assert "记录数不匹配" in result.warnings[0]

    async     def test_validate_package_json_decode_error(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["manifest.json", "data/villages.json"]
                    def read_side_effect(name):
                        if name == "manifest.json":
                            return json.dumps({
                                "version": "1.0", "data_types": ["villages"],
                                "record_counts": {"villages": 2},
                            }).encode("utf-8")
                        return b"not valid json"
                    m.read.side_effect = read_side_effect
                    result = await service.validate_package("/tmp/test.zip")
                    json_errors = [e for e in result.errors if "JSON格式错误" in e.message]
                    assert len(json_errors) >= 1

    async     def test_validate_package_bad_zipfile_error(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    mock_zip.side_effect = zipfile.BadZipFile()
                    result = await service.validate_package("/tmp/test.zip")
                    assert not result.is_valid

    async     def test_validate_package_unexpected_exception(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock(return_value=None)
                    m.namelist.return_value = ["manifest.json"]
                    m.read.side_effect = RuntimeError("read failed")
                    result = await service.validate_package("/tmp/test.zip")
                    assert not result.is_valid
                    assert result.errors
                    assert any("read failed" in (e.message or "") for e in result.errors)

    async     def test_validate_package_valid(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.namelist.return_value = ["manifest.json", "data/villages.json"]
                    m.read.side_effect = [
                        json.dumps({
                            "version": "1.0", "data_types": ["villages"],
                            "record_counts": {"villages": 2},
                        }).encode("utf-8"),
                        json.dumps([{"id": 1}, {"id": 2}]).encode("utf-8"),
                    ]
                    result = await service.validate_package("/tmp/test.zip")
                    assert result.is_valid is True

    # ===================== import_package =====================
    async     def test_import_package_validation_fails(self, service):
        from app.schemas.data_package import PackageStatusEnum as RealPSE
        with patch("app.services.data_package_service.PackageStatusEnum") as mock_enum:
            mock_enum.failed = RealPSE.FAILED
            with patch.object(service, "validate_package") as mock_validate:
                mock_validate.return_value.is_valid = False
                mock_validate.return_value.errors = [MagicMock(message="err")]
                mock_validate.return_value.manifest = None
                with patch.object(service, "_create_package_record") as mock_create:
                    mock_create.return_value.id = 1
                    mock_create.return_value.package_code = "ERR-CODE"
                    result = await service.import_package("/tmp/test.zip", "test.zip", 1, 1)
                    assert result.status == "failed"

    async     def test_import_package_success(self, service):
        from app.schemas.data_package import DataPackageManifest, PackageStatusEnum as RealPSE
        service.db.refresh.side_effect = lambda pkg: setattr(pkg, 'id', 42)
        real_manifest = DataPackageManifest(version="1.0", data_types=["villages"], record_counts={"villages": 2}, org_code="ORG001")
        with patch("app.services.data_package_service.PackageStatusEnum") as mock_enum:
            mock_enum.VALIDATED = RealPSE.VALIDATED
            with patch.object(service, "validate_package") as mock_validate:
                mock_validate.return_value.is_valid = True
                mock_validate.return_value.manifest = real_manifest
                with patch.object(service, "_generate_package_code") as mock_code:
                    mock_code.return_value = "IMP-ORG001-CODE"
                    with patch("shutil.copy"):
                        with patch.object(service, "preview_package_data_from_file") as mock_preview:
                            mock_preview.return_value = []
                            with patch("os.path.getsize", return_value=100):
                                with patch.object(service, "_calculate_checksum") as mc:
                                    mc.return_value = "sha256:abc"
                                    result = await service.import_package("/tmp/test.zip", "test.zip", 1, 1)
                                    assert result.status == "validated"

    # ===================== preview_package_data =====================
    async     def test_preview_package_data_not_found(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        result = await service.preview_package_data(999)
        assert result == []

    async     def test_preview_package_data_no_file_path(self, service):
        pkg = MagicMock()
        pkg.file_path = None
        service.db.query.return_value.filter.return_value.first.return_value = pkg
        result = await service.preview_package_data(1)
        assert result == []

    async     def test_preview_package_data_success(self, service):
        pkg = MagicMock()
        pkg.file_path = "/tmp/test.zip"
        service.db.query.return_value.filter.return_value.first.return_value = pkg
        with patch.object(service, "preview_package_data_from_file") as mock_preview:
            mock_preview.return_value = ["preview1"]
            result = await service.preview_package_data(1)
            assert result == ["preview1"]

    # ===================== preview_package_data_from_file =====================
    async     def test_preview_package_data_from_file_success(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            m.read.side_effect = [
                json.dumps({"data_types": ["villages"]}).encode("utf-8"),
                json.dumps([{"id": 1, "name": "v1"}, {"id": 2, "name": "v2"}]).encode("utf-8"),
            ]
            m.namelist.return_value = ["manifest.json", "data/villages.json"]
            result = await service.preview_package_data_from_file("/tmp/test.zip", sample_size=1)
            assert len(result) == 1
            assert result[0].data_type == "villages"
            assert result[0].total == 2
            assert len(result[0].sample) == 1

    async     def test_preview_package_data_from_file_exception(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = Exception("bad")
            result = await service.preview_package_data_from_file("/tmp/test.zip")
            assert result == []

    # ===================== confirm_import =====================
    async     def test_confirm_import_package_not_found(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        from app.core.exceptions import BusinessError
        with pytest.raises(BusinessError, match="数据包不存在"):
            await service.confirm_import(999, 1)

    async     def test_confirm_import_wrong_status(self, service):
        pkg = MagicMock()
        pkg.status = "draft"
        pkg.org_id = 1
        service.db.query.return_value.filter.return_value.first.return_value = pkg
        from app.core.exceptions import BusinessError
        with pytest.raises(BusinessError, match="数据包状态不允许导入"):
            await service.confirm_import(1, 1)

    async     def test_confirm_import_success(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.status = "validated"
        pkg.org_id = 1
        pkg.file_path = "/tmp/test.zip"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
            mock_excl.return_value.__enter__ = MagicMock()
            mock_excl.return_value.__exit__ = MagicMock()
            with patch("zipfile.ZipFile") as mock_zip:
                m = MagicMock()
                mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                mock_zip.return_value.__exit__ = MagicMock()
                m.read.side_effect = [
                    json.dumps({"data_types": ["villages"], "org_code": "ORG001"}).encode("utf-8"),
                    json.dumps([{"id": 1, "name": "v1"}]).encode("utf-8"),
                ]
                m.namelist.return_value = ["manifest.json", "data/villages.json"]
                org = MagicMock()
                org.id = 1
                service.db.query.return_value.filter.return_value.first.side_effect = [pkg, org]

                with patch.object(service, "_bulk_upsert_records") as mock_bulk:
                    mock_bulk.return_value = (1, 0, [])
                    result = await service.confirm_import(1, 1, overwrite_existing=True)
                    assert result.success is True

    async     def test_confirm_import_no_source_org(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.status = "validated"
        pkg.org_id = 1
        pkg.file_path = "/tmp/test.zip"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
            mock_excl.return_value.__enter__ = MagicMock()
            mock_excl.return_value.__exit__ = MagicMock()
            with patch("zipfile.ZipFile") as mock_zip:
                m = MagicMock()
                mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                mock_zip.return_value.__exit__ = MagicMock()
                m.read.side_effect = [
                    json.dumps({"data_types": ["villages"], "org_code": ""}).encode("utf-8"),
                    json.dumps([{"id": 1}]).encode("utf-8"),
                ]
                m.namelist.return_value = ["manifest.json", "data/villages.json"]
                with patch.object(service, "_bulk_upsert_records") as mock_bulk:
                    mock_bulk.return_value = (1, 0, [])
                    result = await service.confirm_import(1, 1, selected_types=["villages"])
                    assert result.success is True

    async     def test_confirm_import_skip_unknown_data_type(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.status = "validated"
        pkg.org_id = 1
        pkg.file_path = "/tmp/test.zip"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
            mock_excl.return_value.__enter__ = MagicMock()
            mock_excl.return_value.__exit__ = MagicMock()
            with patch("zipfile.ZipFile") as mock_zip:
                m = MagicMock()
                mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                mock_zip.return_value.__exit__ = MagicMock()
                m.read.side_effect = [
                    json.dumps({"data_types": ["villages", "unknown_type"], "org_code": "ORG"}).encode("utf-8"),
                    json.dumps([{"id": 1}]).encode("utf-8"),
                ]
                m.namelist.return_value = ["manifest.json", "data/villages.json"]
                org = MagicMock()
                org.id = 1
                service.db.query.return_value.filter.return_value.first.side_effect = [pkg, org]
                with patch.object(service, "_bulk_upsert_records") as mock_bulk:
                    mock_bulk.return_value = (1, 0, [])
                    result = await service.confirm_import(1, 1)
                    assert result.success is True

    async     def test_confirm_import_missing_data_file(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.status = "validated"
        pkg.org_id = 1
        pkg.file_path = "/tmp/test.zip"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
            mock_excl.return_value.__enter__ = MagicMock()
            mock_excl.return_value.__exit__ = MagicMock()
            with patch("zipfile.ZipFile") as mock_zip:
                m = MagicMock()
                mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                mock_zip.return_value.__exit__ = MagicMock()
                m.read.return_value = json.dumps({"data_types": ["villages"], "org_code": "ORG"}).encode("utf-8")
                m.namelist.return_value = ["manifest.json"]
                org = MagicMock()
                org.id = 1
                service.db.query.return_value.filter.return_value.first.side_effect = [pkg, org]
                with patch.object(service, "_bulk_upsert_records") as mock_bulk:
                    result = await service.confirm_import(1, 1)
                    mock_bulk.assert_not_called()
                    assert result.success is True

    async     def test_confirm_import_exception_rollback(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.status = "validated"
        pkg.org_id = 1
        pkg.file_path = "/tmp/test.zip"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
            mock_excl.side_effect = Exception("lock error")
            result = await service.confirm_import(1, 1)
            assert result.success is False
            service.db.rollback.assert_called_once()
            assert pkg.status == "failed"

    # ===================== _bulk_upsert_records =====================
    def _make_sqlite_insert_mock(self, excluded_cols=None):
        """Helper to build sqlite_insert mock chain for bulk_upsert tests"""
        mock_fn = MagicMock()
        mock_stmt = MagicMock()
        mock_fn.return_value = mock_stmt
        mock_stmt.values.return_value = mock_stmt
        mock_stmt.excluded = excluded_cols or []
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_stmt.on_conflict_do_nothing.return_value = mock_stmt
        return patch("app.services.data_package_service.sqlite_insert", mock_fn), mock_stmt

    async     def test_bulk_upsert_empty_records(self, service):
        imp, skip, errs = service._bulk_upsert_records(MagicMock(), [], 1, True)
        assert imp == 0
        assert skip == 0

    async     def test_bulk_upsert_with_overwrite(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        excluded = [MagicMock(name="id"), MagicMock(name="name")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="name")}
            records = [{"id": 1, "name": "test", "extra": "ignored"}]
            patcher, stmt = self._make_sqlite_insert_mock(excluded)
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 1, True)
                assert imp == 1
                service.db.execute.assert_called_once()

    async     def test_bulk_upsert_without_overwrite(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="name")}
            records = [{"id": 1, "name": "test"}]
            patcher, stmt = self._make_sqlite_insert_mock()
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 1, False)
                assert imp == 1

    async     def test_bulk_upsert_datetime_parsing(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="updated_at"), MagicMock(key="org_id")}
            records = [{"id": 1, "updated_at": "2024-01-15T10:30:00"}]
            patcher, stmt = self._make_sqlite_insert_mock()
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 1, False)
                assert imp == 1

    async     def test_bulk_upsert_datetime_parsing_failure(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="name")}
            records = [{"id": 1, "name": "badTformat"}]
            patcher, stmt = self._make_sqlite_insert_mock()
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 1, True)
                assert imp > 0

    async     def test_bulk_upsert_org_id_injection(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="organization_id")}
            records = [{"id": 1}]
            patcher, stmt = self._make_sqlite_insert_mock()
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 42, True)
                assert imp == 1

    async     def test_bulk_upsert_org_id_alt(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="name"), MagicMock(key="org_id")}
            records = [{"id": 1, "name": "test"}]
            patcher, stmt = self._make_sqlite_insert_mock()
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 99, True)
                assert imp == 1

    async     def test_bulk_upsert_record_clean_error(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id")}
            records = [MagicMock()]  # can't iterate
            records[0].items.side_effect = AttributeError("no items")
            imp, skip, errs = service._bulk_upsert_records(model, records, 1, True)
            assert len(errs) >= 1

    async     def test_bulk_upsert_execute_error(self, service):
        model = MagicMock()
        model.__tablename__ = "test_table"
        mapper = MagicMock()
        mapper.primary_key = [MagicMock(name="id")]
        with patch("app.services.data_package_service.inspect", return_value=mapper):
            mapper.column_attrs = {MagicMock(key="id"), MagicMock(key="name")}
            records = [{"id": 1, "name": "test"}]
            service.db.execute.side_effect = Exception("db error")
            patcher, stmt = self._make_sqlite_insert_mock()
            with patcher:
                imp, skip, errs = service._bulk_upsert_records(model, records, 1, True)
                assert len(errs) >= 1
                service.db.rollback.assert_called()

    # ===================== export_encrypted_package =====================
    async     def test_export_encrypted_no_password(self, service):
        org = MagicMock()
        org.id = 1
        org.code = "O"
        org.name = "O"
        service.org_service.get_organization = MagicMock(return_value=org)
        service.db.refresh.side_effect = lambda pkg: setattr(pkg, 'id', 1)

        with patch.object(service, "_export_data_type") as me:
            me.return_value = []
            with patch.object(service, "_generate_package_code") as mc:
                mc.return_value = "EXP-O-CODE"
                with patch.object(service, "_create_zip_package"):
                    with patch.object(service, "_calculate_checksum") as mch:
                        mch.return_value = "sha256:0"
                        with patch("os.path.getsize", return_value=10):
                            with patch.object(service, "get_package") as mg:
                                mg.return_value = None
                                result = await service.export_encrypted_package(1, ["villages"], 1)
                                assert result.file_name.endswith(".zip")

    async     def test_export_encrypted_with_password(self, service):
        org = MagicMock()
        org.id = 1
        org.code = "O"
        org.name = "O"
        service.org_service.get_organization = MagicMock(return_value=org)
        service.db.refresh.side_effect = lambda pkg: setattr(pkg, 'id', 1)

        with patch.object(service, "_export_data_type") as me:
            me.return_value = []
            with patch.object(service, "_generate_package_code") as mc:
                mc.return_value = "EXP-O-CODE"
                with patch.object(service, "_create_zip_package"):
                    with patch.object(service, "_calculate_checksum") as mch:
                        mch.return_value = "sha256:0"
                        with patch("os.path.getsize", return_value=10):
                            with patch("app.services.password_encryption_service.PasswordEncryptionService.encrypt_file") as m_enc:
                                m_enc.return_value = ("salt123", 100000)
                                with patch.object(service, "get_package") as mg:
                                    pkg = MagicMock()
                                    mg.return_value = pkg
                                    result = await service.export_encrypted_package(1, ["villages"], 1, password="secret")
                                    assert result.file_name.endswith(".enc")
                                    assert pkg.is_encrypted is True

    async     def test_export_encrypted_cleanup_original(self, service):
        org = MagicMock()
        org.id = 1
        org.code = "O"
        org.name = "O"
        service.org_service.get_organization = MagicMock(return_value=org)
        service.db.refresh.side_effect = lambda pkg: setattr(pkg, 'id', 1)

        with patch.object(service, "_export_data_type") as me:
            me.return_value = []
            with patch.object(service, "_generate_package_code") as mc:
                mc.return_value = "EXP-O-CODE"
                with patch.object(service, "_create_zip_package"):
                    with patch.object(service, "_calculate_checksum") as mch:
                        mch.return_value = "sha256:0"
                        with patch("os.path.getsize", side_effect=[10, 20, 30]):
                            with patch("app.services.password_encryption_service.PasswordEncryptionService.encrypt_file") as m_enc:
                                m_enc.return_value = ("salt", 100000)
                                with patch("os.path.exists", return_value=True):
                                    with patch("os.remove") as m_rem:
                                        with patch.object(service, "get_package") as mg:
                                            pkg = MagicMock()
                                            mg.return_value = pkg
                                            result = await service.export_encrypted_package(1, ["villages"], 1, password="secret")
                                            m_rem.assert_called_once()

    # ===================== import_encrypted_package =====================
    async     def test_import_encrypted_not_encrypted(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            m.read.return_value = b"{}"
            with patch.object(service, "import_package") as mi:
                mi.return_value = "imported"
                result = await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1)
                assert result == "imported"

    async     def test_import_encrypted_is_encrypted_no_password(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = zipfile.BadZipFile("bad")
            from app.core.exceptions import BusinessError
            with pytest.raises(BusinessError, match="请提供密码"):
                await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password=None)

    async     def test_import_encrypted_decrypt_success(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = zipfile.BadZipFile("bad")
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file_auto", create=True) as m_dec:
                with patch.object(service, "import_package") as mi:
                    mi.return_value = "result"
                    r = await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password="secret")
                    assert r == "result"

    async     def test_import_encrypted_invalid_password(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = zipfile.BadZipFile("bad")
            from app.services.password_encryption_service import InvalidPasswordError
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file_auto", create=True) as m_dec:
                m_dec.side_effect = InvalidPasswordError()
                from app.core.exceptions import BusinessError
                with pytest.raises(BusinessError, match="密码错误"):
                    await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password="wrong")

    async     def test_import_encrypted_attribute_error(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = zipfile.BadZipFile("bad")
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file_auto", create=True) as m_dec:
                m_dec.side_effect = AttributeError("no method")
                from app.core.exceptions import BusinessError
                with pytest.raises(BusinessError, match="加密文件解析失败"):
                    await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password="secret")

    async     def test_import_encrypted_key_error(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            m.read.side_effect = KeyError("manifest.json")
            with patch.object(service, "import_package") as mi:
                mi.return_value = "result"
                r = await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password="secret")
                assert r == "result"

    async     def test_import_encrypted_temp_cleanup(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = zipfile.BadZipFile("bad")
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file_auto", create=True) as m_dec:
                with patch.object(service, "import_package") as mi:
                    mi.side_effect = Exception("import failed")
                    with patch("os.path.exists", return_value=True):
                        with patch("os.remove") as m_rem:
                            with pytest.raises(Exception):
                                await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password="secret")
                            m_rem.assert_called_once()

    async     def test_import_encrypted_remove_fail(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = zipfile.BadZipFile("bad")
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file_auto", create=True) as m_dec:
                with patch.object(service, "import_package") as mi:
                    mi.side_effect = Exception("import failed")
                    with patch("os.path.exists", return_value=True):
                        with patch("os.remove", side_effect=OSError("access denied")):
                            with pytest.raises(Exception):
                                await service.import_encrypted_package("/tmp/test.zip", "test.zip", 1, 1, password="secret")

    # ===================== decrypt_and_preview_package =====================
    async     def test_decrypt_and_preview_package_not_found(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        from app.core.exceptions import BusinessError
        with pytest.raises(BusinessError, match="数据包不存在"):
            await service.decrypt_and_preview_package(999, "pwd")

    async     def test_decrypt_and_preview_not_encrypted(self, service):
        pkg = MagicMock()
        pkg.is_encrypted = False
        service.db.query.return_value.filter.return_value.first.return_value = pkg
        from app.core.exceptions import BusinessError
        with pytest.raises(BusinessError, match="未加密"):
            await service.decrypt_and_preview_package(1, "pwd")

    async     def test_decrypt_and_preview_invalid_password(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.is_encrypted = True
        pkg.file_path = "/tmp/enc.zip"
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        pkg.package_code = "CODE"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        from app.services.password_encryption_service import InvalidPasswordError
        with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file") as m_dec:
            m_dec.side_effect = InvalidPasswordError()
            from app.core.exceptions import BusinessError
            with pytest.raises(BusinessError, match="密码错误"):
                await service.decrypt_and_preview_package(1, "wrong")

    async     def test_decrypt_and_preview_success(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.is_encrypted = True
        pkg.file_path = "/tmp/enc.zip"
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        pkg.package_code = "CODE"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        real_manifest = {"version": "1.0", "data_types": []}
        with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file"):
            with patch.object(service, "validate_package") as m_val:
                m_val.return_value.is_valid = True
                m_val.return_value.manifest = real_manifest
                result = await service.decrypt_and_preview_package(1, "pwd")
                assert result.status == "validated"

    async     def test_decrypt_and_preview_validation_fails(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.is_encrypted = True
        pkg.file_path = "/tmp/enc.zip"
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        pkg.package_code = "CODE"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file"):
            with patch.object(service, "validate_package") as m_val:
                m_val.return_value.is_valid = False
                m_val.return_value.errors = [MagicMock(message="err")]
                from app.services.data_package_service import PackageValidationError
                with pytest.raises(PackageValidationError):
                    await service.decrypt_and_preview_package(1, "pwd")

    async     def test_decrypt_and_preview_cleanup(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.is_encrypted = True
        pkg.file_path = "/tmp/enc.zip"
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        pkg.package_code = "CODE"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        real_manifest = {"version": "1.0", "data_types": []}
        with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file"):
            with patch.object(service, "validate_package") as m_val:
                m_val.return_value.is_valid = True
                m_val.return_value.manifest = real_manifest
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove") as m_rem:
                        await service.decrypt_and_preview_package(1, "pwd")
                        m_rem.assert_called_once()

    async     def test_decrypt_and_preview_cleanup_fail(self, service):
        pkg = MagicMock()
        pkg.id = 1
        pkg.is_encrypted = True
        pkg.file_path = "/tmp/enc.zip"
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        pkg.package_code = "CODE"
        service.db.query.return_value.filter.return_value.first.return_value = pkg

        real_manifest = {"version": "1.0", "data_types": []}
        with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file"):
            with patch.object(service, "validate_package") as m_val:
                m_val.return_value.is_valid = True
                m_val.return_value.manifest = real_manifest
                with patch("os.path.exists", return_value=True):
                    with patch("os.remove", side_effect=OSError("access")):
                        await service.decrypt_and_preview_package(1, "pwd")

    # ===================== confirm_import_with_conflict_resolution =====================
    async     def test_confirm_with_conflict_resolution_pkg_not_found(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        from app.core.exceptions import BusinessError
        with pytest.raises(BusinessError, match="数据包不存在"):
            await service.confirm_import_with_conflict_resolution(999)

    async     def test_confirm_with_conflict_wrong_status(self, service):
        pkg = MagicMock()
        pkg.status = "draft"
        pkg.is_encrypted = False
        pkg.file_path = "/tmp/test.zip"
        with patch.object(service, "get_package", return_value=pkg):
            from app.core.exceptions import BusinessError
            with pytest.raises(BusinessError, match="数据包状态不正确"):
                await service.confirm_import_with_conflict_resolution(1)

    async     def test_confirm_with_conflict_encrypted_no_password(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = True
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        with patch.object(service, "get_package", return_value=pkg):
            result = await service.confirm_import_with_conflict_resolution(1)
            assert result["success"] is False
            assert "加密包" in result["message"]

    async     def test_confirm_with_conflict_encrypted_wrong_password(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = True
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        with patch.object(service, "get_package", return_value=pkg):
            from app.services.password_encryption_service import InvalidPasswordError
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file") as m_dec:
                m_dec.side_effect = InvalidPasswordError()
                result = await service.confirm_import_with_conflict_resolution(1, password="wrong")
                assert result["success"] is False
                assert "密码" in result["message"]

    async     def test_confirm_with_conflict_encrypted_success(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = True
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        pkg.org_id = 1
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        with patch.object(service, "get_package", return_value=pkg):
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file"):
                with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
                    mock_excl.return_value.__enter__ = MagicMock()
                    mock_excl.return_value.__exit__ = MagicMock()
                    with patch("zipfile.ZipFile") as mock_zip:
                        m = MagicMock()
                        mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                        mock_zip.return_value.__exit__ = MagicMock()
                        m.read.return_value = json.dumps({"data_types": ["villages"]}).encode("utf-8")
                        m.namelist.return_value = ["manifest.json", "data/villages.json"]
                        resolver = MagicMock()
                        with patch("app.services.smart_conflict_resolver.SmartConflictResolver") as m_resolver:
                            m_resolver.return_value = resolver
                            with patch("os.path.exists", return_value=True):
                                with patch("os.remove") as mock_remove:
                                    result = await service.confirm_import_with_conflict_resolution(1, password="pwd")
                                    assert result["success"] is True
                                    mock_remove.assert_called_once()

    async     def test_confirm_with_conflict_encrypted_cleanup_oserror(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = True
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        pkg.org_id = 1
        pkg.encryption_salt = "salt"
        pkg.encryption_iterations = 100000
        with patch.object(service, "get_package", return_value=pkg):
            with patch("app.services.password_encryption_service.PasswordEncryptionService.decrypt_file"):
                with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
                    mock_excl.side_effect = Exception("import failed")
                    with patch("os.path.exists", return_value=True):
                        with patch("os.remove", side_effect=OSError("permission denied")):
                            result = await service.confirm_import_with_conflict_resolution(1, password="pwd")
                            assert result["success"] is False

    async     def test_confirm_with_conflict_not_encrypted_success(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = False
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        pkg.org_id = 1
        with patch.object(service, "get_package", return_value=pkg):
            with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
                mock_excl.return_value.__enter__ = MagicMock()
                mock_excl.return_value.__exit__ = MagicMock()
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.read.return_value = json.dumps({"data_types": ["villages"]}).encode("utf-8")
                    m.namelist.return_value = ["manifest.json", "data/villages.json"]
                    resolver = MagicMock()
                    with patch("app.services.smart_conflict_resolver.SmartConflictResolver") as m_resolver:
                        m_resolver.return_value = resolver
                        result = await service.confirm_import_with_conflict_resolution(1)
                        assert result["success"] is True

    async     def test_confirm_with_conflict_skip_unknown_data_type(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = False
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        pkg.org_id = 1
        with patch.object(service, "get_package", return_value=pkg):
            with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
                mock_excl.return_value.__enter__ = MagicMock()
                mock_excl.return_value.__exit__ = MagicMock()
                with patch("zipfile.ZipFile") as mock_zip:
                    m = MagicMock()
                    mock_zip.return_value.__enter__ = MagicMock(return_value=m)
                    mock_zip.return_value.__exit__ = MagicMock()
                    m.read.return_value = json.dumps({"data_types": ["villages", "unknown_one", "unknown_two"]}).encode("utf-8")
                    m.namelist.return_value = ["manifest.json"]
                    resolver = MagicMock()
                    with patch("app.services.smart_conflict_resolver.SmartConflictResolver") as m_resolver:
                        m_resolver.return_value = resolver
                        result = await service.confirm_import_with_conflict_resolution(1)
                        assert result["success"] is True

    async     def test_confirm_with_conflict_exception(self, service):
        pkg = MagicMock()
        pkg.status = "validated"
        pkg.is_encrypted = False
        pkg.id = 1
        pkg.file_path = "/tmp/test.zip"
        pkg.org_id = 1
        with patch.object(service, "get_package", return_value=pkg):
            with patch("app.services.data_package_service.db_coordinator.exclusive_write") as mock_excl:
                mock_excl.side_effect = Exception("error")
                result = await service.confirm_import_with_conflict_resolution(1)
                assert result["success"] is False
                assert pkg.status == "failed"

    # ===================== helper methods =====================
    def test_generate_package_code(self, service):
        code = service._generate_package_code("ORG001", "EXP")
        assert code.startswith("EXP-ORG001-")

    def test_generate_package_code_none_org(self, service):
        code = service._generate_package_code(None, "IMP")
        assert code.startswith("IMP-UNKNOWN-")

    def test_calculate_checksum(self, service):
        with patch("builtins.open") as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
            mock_file.read.side_effect = [b"hello", b""]
            result = service._calculate_checksum("/tmp/test.zip")
            assert result.startswith("sha256:")

    def test_create_package_record(self, service):
        with patch("os.path.exists", return_value=True):
            with patch("os.path.getsize", return_value=100):
                result = service._create_package_record("/tmp/test.zip", "test.zip", 1, 1, MagicMock(value="failed"), error_message="err")
                assert result is not None
                service.db.add.assert_called_once()
                service.db.commit.assert_called()
                service.db.refresh.assert_called_once()

    def test_create_package_record_not_exists(self, service):
        with patch("os.path.exists", return_value=False):
            result = service._create_package_record("/tmp/none.zip", "none.zip", 1, 1, MagicMock(value="failed"))
            assert result is not None

    def test_get_package(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = "pkg"
        result = service.get_package(1)
        assert result == "pkg"

    def test_get_packages_by_org(self, service):
        q = MagicMock()
        service.db.query.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = ["pkg1", "pkg2"]

        result = service.get_packages_by_org(1)
        assert len(result) == 2

    def test_get_packages_by_org_with_filters(self, service):
        q = MagicMock()
        service.db.query.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = ["pkg"]

        result = service.get_packages_by_org(1, status="validated", type_filter="report")
        assert len(result) == 1
