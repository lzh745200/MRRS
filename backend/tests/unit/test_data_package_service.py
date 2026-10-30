"""数据包管理服务单元测试 (100% coverage)

W18 收口说明：
- `_export_data_type` 已改为 raw SQL 取数（W18-D8：PII 密文出包，禁止 ORM 解密；
  表名/列名取自模型元数据，过滤值走 `text()` 绑定参数）。测试改为 mock
  `db.execute(...).fetchall()` 返回行，并提供带 `__tablename__`/`__table__` 的
  fake model（MagicMock 拒绝 dunder 属性，旧写法会 AttributeError）。
- `_bulk_upsert_records` 已改为「按记录实际携带键集合分组 + 逐批 stmt + rowcount
  计数 + 每组 SAVEPOINT」（M29/W18-D1/D4）。测试改用真实 SQLAlchemy 声明式替身
  模型（含 DateTime/String 列）驱动真实清洗/分组/编译路径，只 mock 数据库会话。
"""
import json
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.orm import declarative_base


class _MockRecord:
    """Helper: allows __table__ attribute (MagicMock rejects dunder attrs)"""
    pass


# ── W18：_export_data_type raw SQL 用例的模型替身 ──
class _FakeColumn:
    def __init__(self, name):
        self.name = name


class _FakeTable:
    def __init__(self, *column_names):
        self.columns = [_FakeColumn(name) for name in column_names]


def _export_model(tablename, column_names, **attrs):
    """构造 _export_data_type 所需的最小模型替身：表名 + 列元数据 + 可选属性。"""
    namespace = {
        "__tablename__": tablename,
        "__table__": _FakeTable(*column_names),
    }
    namespace.update(attrs)
    return type("FakeModel_" + tablename, (), namespace)


def _fetchall_result(rows):
    """mock `db.execute(...)` 返回的行集。

    生产实现已改为逐行迭代（流式导出，不再 ``fetchall()``），因此直接返回
    可迭代的行元组列表；保留原函数名避免大范围改测试。
    """
    return rows


# ── W18：_bulk_upsert_records 用例的真实声明式模型替身 ──
_UpsertBase = declarative_base()


class _UpsertModel(_UpsertBase):
    """带 organization_id + DateTime 列的最小可 upsert 模型。"""

    __tablename__ = "w18_upsert_probe"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    updated_at = Column(DateTime)
    organization_id = Column(Integer)


class _UpsertOrgIdModel(_UpsertBase):
    """只有 org_id（旧列名）的最小可 upsert 模型。"""

    __tablename__ = "w18_upsert_orgid_probe"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    org_id = Column(Integer)


class _UpsertBareModel(_UpsertBase):
    """既无 organization_id 也无 org_id 列的最小可 upsert 模型。"""

    __tablename__ = "w18_upsert_bare_probe"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))


def _compiled_sql(stmt):
    """把 sqlite insert 语句按 sqlite 方言编译成字符串（含 ON CONFLICT 子句）。"""
    return str(stmt.compile(dialect=sqlite_dialect.dialect())).upper()


def _compiled_params(stmt):
    """取编译后的绑定参数（多行 VALUES 的参数名带 `_m<idx>` 后缀，归一为列名）。"""
    compiled = stmt.compile(dialect=sqlite_dialect.dialect())
    params = {}
    for key, value in compiled.params.items():
        base = key.rsplit("_m", 1)[0] if "_m" in key else key
        params[base] = value
    return params


@pytest.fixture
def mock_db():
    db = MagicMock()
    # W18-D4：_bulk_upsert_records 改按真实 rowcount 计数（DO NOTHING 不计），
    # mock execute 必须模拟真实 CursorResult 契约 —— rowcount 是 int。
    result = MagicMock()
    result.rowcount = 1
    db.execute.return_value = result
    db.begin_nested.return_value.__enter__ = MagicMock(return_value=None)
    db.begin_nested.return_value.__exit__ = MagicMock(return_value=False)
    # W18-D1：_classify_import_records 会查「导入 id 是否已存在」——
    # mock 契约：query(...).filter(...).all() 返回空（主键全空闲 → 走 INSERT 分支）
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = []
    db.query.return_value = q
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

        with patch.object(service, "_iter_export_data_type") as mock_export:
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

        with patch.object(service, "_iter_export_data_type") as mock_export:
            mock_export.return_value = iter([])
            with patch.object(service, "_generate_package_code") as mock_code:
                mock_code.return_value = "EXP-ORG001-CODE"
                with patch.object(service, "_create_zip_package"):
                    with patch.object(service, "_calculate_checksum") as mc:
                        mc.return_value = "sha256:000"
                        with patch("os.path.getsize", return_value=10):
                            result = await service.export_package(1, ["unknown_type", "villages"], 1)
                            mock_export.assert_called_once()  # only called for "villages"

    # ===================== _export_data_type（W18-D8 raw SQL） =====================
    async     def test_export_data_type_with_org_id(self, service):
        """模型有 org_id → SQL 追加 org_id 过滤；行元组按列名转 dict。"""
        model = _export_model("w18_export_schools", ["id", "name"], org_id=1)
        service.db.execute.return_value = _fetchall_result([(1, "test")])

        result = service._export_data_type(1, model)

        assert result == [{"id": 1, "name": "test"}]
        stmt, params = service.db.execute.call_args.args
        sql = str(stmt)
        assert "FROM w18_export_schools" in sql
        assert "org_id = :org_id" in sql
        assert params == {"org_id": 1}

    async     def test_export_data_type_with_organization_id(self, service):
        """模型无 org_id 但有 organization_id → 用 organization_id 过滤。"""
        model = _export_model(
            "w18_export_villages", ["id", "village_name"], organization_id=1
        )
        service.db.execute.return_value = _fetchall_result([(7, "某村")])

        result = service._export_data_type(1, model)

        assert result == [{"id": 7, "village_name": "某村"}]
        stmt, params = service.db.execute.call_args.args
        assert "organization_id = :org_id" in str(stmt)
        assert params == {"org_id": 1}

    async     def test_export_data_type_datetime_decimal(self, service):
        """datetime → ISO 串；Decimal → float（JSON 可序列化）。"""
        from decimal import Decimal

        model = _export_model("w18_export_funds", ["id", "created_at", "amount"], org_id=1)
        service.db.execute.return_value = _fetchall_result([
            (1, datetime(2024, 1, 1, tzinfo=timezone.utc), Decimal("100.50")),
        ])

        result = service._export_data_type(1, model)

        assert result[0]["created_at"] == "2024-01-01T00:00:00+00:00"
        assert result[0]["amount"] == 100.5

    async     def test_export_data_type_other_type_str(self, service):
        """非 JSON 原生类型（如自定义对象）→ str() 兜底。"""
        class Custom:
            def __str__(self):
                return "custom_str"

        model = _export_model("w18_export_meta", ["meta"], org_id=1)
        service.db.execute.return_value = _fetchall_result([(Custom(),)])

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
            assert m.writestr.call_count == 1  # manifest.json
            assert m.open.call_count == 1  # data/villages.json（逐行写入）

    # ===================== validate_package =====================
    async def test_validate_package_blocking_io_leaves_event_loop_thread(self, service):
        """ZIP 校验的同步 I/O 必须在线程池执行，不能只是 async 空壳。"""
        caller_thread = threading.get_ident()
        io_threads = []
        with patch("os.path.exists", side_effect=lambda _path: io_threads.append(threading.get_ident()) or False):
            result = await service.validate_package("/tmp/nonexistent.zip")

        assert not result.is_valid
        assert io_threads and io_threads[0] != caller_thread

    async def test_preview_package_blocking_io_leaves_event_loop_thread(self, service):
        """预览解包同样不得占住事件循环线程。"""
        caller_thread = threading.get_ident()
        io_threads = []

        def _record_thread(*_args, **_kwargs):
            io_threads.append(threading.get_ident())
            raise zipfile.BadZipFile("stop after thread probe")

        with patch("zipfile.ZipFile", side_effect=_record_thread):
            assert await service.preview_package_data_from_file("/tmp/probe.zip") == []

        assert io_threads and io_threads[0] != caller_thread

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

    async     def test_validate_package_zip_bomb_http_exception(self, service):
        """解压后超限（ensure_zip_within_limit 抛 HTTPException）→ 可读业务结论。"""
        from fastapi import HTTPException

        with patch("os.path.exists", return_value=True):
            with patch("zipfile.is_zipfile", return_value=True):
                with patch("zipfile.ZipFile"):
                    with patch(
                        "app.services.data_package_service.ensure_zip_within_limit",
                        side_effect=HTTPException(status_code=400, detail="解压后超过大小限制"),
                    ):
                        result = await service.validate_package("/tmp/bomb.zip")
        assert not result.is_valid
        assert result.errors[0].field == "file"
        assert "解压后超过大小限制" in result.errors[0].message

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
        # R9：不再 patch PackageStatusEnum——原写法用 mock 掩盖了
        # `PackageStatusEnum.failed` 的大小写缺陷（真实成员为大写 FAILED，
        # 生产路径必抛 AttributeError 被端点兜底成 500）。此处直接断言真实行为，
        # 并断言失败记录不落临时文件路径（file_path=None）。
        with patch.object(service, "validate_package") as mock_validate:
            mock_validate.return_value.is_valid = False
            mock_validate.return_value.errors = [MagicMock(message="err")]
            mock_validate.return_value.manifest = None
            with patch.object(service, "_create_package_record") as mock_create:
                mock_create.return_value.id = 1
                mock_create.return_value.package_code = "ERR-CODE"
                result = await service.import_package("/tmp/test.zip", "test.zip", 1, 1)
                assert result.status == "failed"
                assert mock_create.call_args[0][0] is None

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
    async     def test_bulk_upsert_empty_records(self, service):
        imp, skip, errs = service._bulk_upsert_records(_UpsertModel, [], 1, True)
        assert imp == 0
        assert skip == 0
        assert errs == []

    async     def test_bulk_upsert_with_overwrite(self, service):
        """覆盖模式：逐批编译 upsert；UPDATE SET 只含记录真实携带的列（M29）。"""
        records = [{"id": 1, "name": "test", "extra": "ignored"}]
        imp, skip, errs = service._bulk_upsert_records(_UpsertModel, records, 1, True)
        assert (imp, skip, errs) == (1, 0, [])
        service.db.execute.assert_called_once()
        compiled = _compiled_sql(service.db.execute.call_args.args[0])
        assert "DO UPDATE" in compiled
        assert "EXCLUDED.NAME" in compiled
        # 记录未携带 updated_at → 不得出现在 UPDATE SET（否则会清空既有列）
        assert "UPDATED_AT" not in compiled
        # 非模型列 extra 被清洗丢弃
        assert "EXTRA" not in compiled

    async     def test_bulk_upsert_without_overwrite(self, service):
        """非覆盖模式 → DO NOTHING；rowcount=0 不得计为 imported（W18-D4）。"""
        service.db.execute.return_value.rowcount = 0
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "name": "test"}], 1, False
        )
        assert (imp, skip, errs) == (0, 1, [])
        compiled_sql = _compiled_sql(service.db.execute.call_args.args[0])
        assert "DO NOTHING" in compiled_sql

    async     def test_bulk_upsert_datetime_parsing(self, service):
        """DateTime 列 ISO 串（带 Z）→ aware 归一为 naive UTC 后写入。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "updated_at": "2024-01-15T10:30:00Z"}], 1, False
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["updated_at"] == datetime(2024, 1, 15, 10, 30)
        assert params["updated_at"].tzinfo is None

    async     def test_bulk_upsert_datetime_parsing_failure(self, service):
        """DateTime 列非 ISO 字符串 → ValueError 兜底，按原值写入不丢数据。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "updated_at": "badTformat"}], 1, True
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["updated_at"] == "badTformat"

    async     def test_bulk_upsert_iso_string_on_non_datetime_column(self, service):
        """非 DateTime 列但形如 ISO 的字符串：沿用通用 "T" 解析分支（aware 归一）。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "name": "2024-01-15T10:30:00Z"}], 1, True
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["name"] == datetime(2024, 1, 15, 10, 30)

    async     def test_bulk_upsert_naive_datetime_and_generic_iso(self, service):
        """DateTime 列 naive ISO 串 → 原样解析为 datetime（tzinfo 为空分支）。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "updated_at": "2024-01-15T10:30:00"}], 1, False
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["updated_at"] == datetime(2024, 1, 15, 10, 30)

    async     def test_bulk_upsert_generic_t_string_invalid_value_kept(self, service):
        """非 DateTime 列含 "T" 但非 ISO → ValueError 兜底，按原字符串写入。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "name": "badTformat"}], 1, False
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["name"] == "badTformat"

    async     def test_bulk_upsert_naive_iso_string_on_non_datetime_column(self, service):
        """非 DateTime 列的 naive ISO 串 → 通用 "T" 解析分支（无时区归一路径）。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "name": "2024-01-15T10:30:00"}], 1, False
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["name"] == datetime(2024, 1, 15, 10, 30)

    async     def test_bulk_upsert_aware_datetime_value_on_non_datetime_column(self, service):
        """非 DateTime 列的 aware datetime 值 → 归一为 naive UTC。"""
        aware = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "name": aware}], 1, False
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["name"] == datetime(2024, 1, 15, 10, 30)
        assert params["name"].tzinfo is None

    async     def test_bulk_upsert_model_without_org_columns(self, service):
        """模型既无 organization_id 也无 org_id → 不注入组织（保留原记录）。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertBareModel, [{"id": 1, "name": "x"}], 42, True
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert "organization_id" not in params
        assert "org_id" not in params

    async     def test_bulk_upsert_record_without_primary_key(self, service):
        """记录未携带主键 → 跳过「已有 id」查询（ids 为空），直接按插入处理。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"name": "无 id 导入"}], 1, False
        )
        assert (imp, skip, errs) == (1, 0, [])
        service.db.query.assert_not_called()
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["name"] == "无 id 导入"

    async     def test_bulk_upsert_relocated_insert_counts_once(self, service):
        """主键已占用且业务键不同 → 去掉主键改号插入，成功计 1（W18-D1）。

        必须用注册了业务键的真实模型（School，业务键=organization_id）；
        未登记模型无法判定身份，会保守归入 same。
        """
        from app.models.school import School

        svc = service
        q_existing = MagicMock()
        q_existing.filter.return_value.all.return_value = [(1,)]
        q_local = MagicMock()
        q_local.filter.return_value.first.return_value = SimpleNamespace(organization_id=2)
        svc.db.query.side_effect = [q_existing, q_local]

        imp, skip, errs = svc._bulk_upsert_records(
            School, [{"id": 1, "name": "撞 id 的外部学校"}], 1, True
        )
        assert (imp, skip, errs) == (1, 0, [])
        # 改号插入只执行一次（不进入分组 upsert）
        service.db.execute.assert_called_once()
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert "id" not in params
        assert params["name"] == "撞 id 的外部学校"

    async     def test_bulk_upsert_org_id_injection(self, service):
        """组织注入：模型有 organization_id 列时以调用方 org_id 覆盖包内值。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "organization_id": 999}], 42, True
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["organization_id"] == 42

    async     def test_bulk_upsert_org_id_alt(self, service):
        """旧列名 org_id 同样注入调用方组织（兼容模型差异）。"""
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertOrgIdModel, [{"id": 1, "name": "test"}], 99, True
        )
        assert (imp, skip, errs) == (1, 0, [])
        params = _compiled_params(service.db.execute.call_args.args[0])
        assert params["org_id"] == 99

    async     def test_bulk_upsert_record_clean_error(self, service):
        """单行清洗抛错 → 记入 errors，不中断整批（其余行正常写入）。"""
        broken = MagicMock()
        broken.items.side_effect = AttributeError("no items")
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [broken, {"id": 2, "name": "ok"}], 1, True
        )
        assert len(errs) == 1
        assert imp == 1

    async     def test_bulk_upsert_execute_error(self, service):
        """批量执行异常只回滚本组 SAVEPOINT，如实计 0，不整事务回滚。"""
        service.db.execute.side_effect = Exception("db error")
        imp, skip, errs = service._bulk_upsert_records(
            _UpsertModel, [{"id": 1, "name": "test"}], 1, True
        )
        assert len(errs) >= 1
        assert imp == 0, "失败的批次必须如实计 0"
        # 2026-09-30 深审修复：断言使用 SAVEPOINT（而非整事务 rollback），
        # 避免丢弃同外层事务内已导入的前序数据类型。
        service.db.begin_nested.assert_called_once()
        savepoint = service.db.begin_nested.return_value
        assert savepoint.__exit__.called, "异常必须由 SAVEPOINT 上下文回滚"
        assert savepoint.__exit__.call_args.args[0] is Exception

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
                # v1.12.9：解密预览成功必须把包推进到 validated 并落库，
                # 否则 confirm-import 因状态仍是 pending 直接拒绝（三步链路恒失败）
                assert pkg.status == "validated"
                service.db.commit.assert_called()

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
