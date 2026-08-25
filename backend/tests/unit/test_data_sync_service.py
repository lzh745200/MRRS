"""数据同步服务单元测试 (100% coverage)"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def service():
    with patch("app.utils.paths.get_app_data_dir") as mock_dir:
        mock_dir.return_value = Path("/tmp/test_sync")
        with patch("pathlib.Path.mkdir"):
            from app.services.data_sync_service import DataSyncService
            svc = DataSyncService()
            svc.logger = MagicMock()
            svc.sync_dir = Path("/tmp/test_sync")
            yield svc


@pytest.fixture
def mock_db():
    with patch("app.services.data_sync_service.get_db") as m:
        db = MagicMock(name="db_session")
        m.return_value = iter([db])
        yield db


@pytest.fixture
def service_with_db(service, mock_db):
    service._db = mock_db
    yield service, mock_db


class MockRow:
    def __init__(self, **kwargs):
        self._mapping = kwargs
        self._keys = list(kwargs.keys())
        for k, v in kwargs.items():
            setattr(self, k, v)

    def keys(self):
        return self._keys

    def __iter__(self):
        return iter(self._mapping.values())

    def __getitem__(self, key):
        return self._mapping[key]


class TestExportConfig:
    def test_defaults(self):
        from app.services.data_sync_service import ExportConfig
        cfg = ExportConfig()
        assert cfg.since is None
        assert cfg.modules is None
        assert cfg.include_files is False
        assert cfg.user_id is None
        assert cfg.user_name is None


class TestDataSyncService:
    # ===================== _get_db_context =====================
    def test_get_db_context_normal(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with service._get_db_context() as db_out:
                assert db_out is db
            db.close.assert_called_once()

    def test_get_db_context_close_error(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            db.close.side_effect = Exception("close fail")
            mock_get_db.return_value = iter([db])
            with service._get_db_context():
                pass
            service.logger.error.assert_called_with("关闭数据库连接失败: close fail")

    # ===================== export_incremental =====================
    @pytest.mark.asyncio
    async def test_export_incremental_success(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as mock_export:
                mock_export.return_value = [{"id": 1, "name": "test"}]
                with patch.object(service, "_save_export_package", new_callable=AsyncMock) as mock_save:
                    pkg_path = Path("/tmp/test_sync/export_20240101_120000.zip")
                    mock_save.return_value = pkg_path
                    with patch.object(Path, "exists", return_value=True):
                        with patch.object(Path, "stat") as ms:
                            ms.return_value.st_size = 1024
                            from datetime import datetime, timezone
                            from app.services.data_sync_service import ExportConfig
                            config = ExportConfig(
                                since=datetime(2024, 1, 1, tzinfo=timezone.utc),
                                modules=["supported_villages"], user_id=1, user_name="admin",
                            )
                            result = await service.export_incremental(config)
                            assert result["success"] is True
                            assert "errors" not in result
                            assert result["success"] is True
                            assert result["total_records"] == 1

    @pytest.mark.asyncio
    async def test_export_incremental_skip_unknown_table(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as mock_export:
                with patch.object(service, "_save_export_package", new_callable=AsyncMock) as mock_save:
                    mock_save.return_value = Path("/tmp/fake.zip")
                    with patch.object(Path, "exists", return_value=True):
                        with patch.object(Path, "stat") as ms:
                            ms.return_value.st_size = 0
                            from app.services.data_sync_service import ExportConfig
                            config = ExportConfig(modules=["unknown_table"])
                            result = await service.export_incremental(config)
                            # W2-T1：未知表被过滤，不产生错误
                            assert mock_export.assert_not_called() is None
                            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_export_incremental_export_table_error(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as mock_export:
                mock_export.side_effect = Exception("export fail")
                with patch.object(service, "_save_export_package", new_callable=AsyncMock) as mock_save:
                    pkg_path = Path("/tmp/test_sync/pkg.zip")
                    mock_save.return_value = pkg_path
                    with patch.object(Path, "exists", return_value=True):
                        with patch.object(Path, "stat") as ms:
                            ms.return_value.st_size = 100
                            from app.services.data_sync_service import ExportConfig
                            config = ExportConfig(since=None, modules=["supported_villages"])
                            result = await service.export_incremental(config)
                            # W2-T1 新契约：异常显式上报
                            assert result["success"] is False
                            assert "supported_villages" in result["errors"]

    @pytest.mark.asyncio
    async def test_export_incremental_general_exception(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            mock_get_db.side_effect = Exception("big fail")
            from app.services.data_sync_service import ExportConfig
            from app.core.error_handler import BusinessLogicError
            with pytest.raises(BusinessLogicError, match="数据导出失败"):
                await service.export_incremental(ExportConfig())

    # ===================== _export_table_data =====================
    @pytest.mark.asyncio
    async def test_export_table_data_with_since(self, service):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.fetchall.return_value = [(1, "village")]
        result_mock.keys.return_value = ["id", "name"]
        db.execute.return_value = result_mock
        from datetime import datetime, timezone
        records = await service._export_table_data(db, "supported_villages", since=datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_export_table_data_without_since(self, service):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.fetchall.return_value = [(1, "test")]
        result_mock.keys.return_value = ["id", "name"]
        db.execute.return_value = result_mock
        records = await service._export_table_data(db, "supported_villages")
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_export_table_data_with_datetime(self, service):
        db = MagicMock()
        from datetime import datetime, timezone
        dt_val = datetime(2024, 6, 15, tzinfo=timezone.utc)
        result_mock = MagicMock()
        result_mock.fetchall.return_value = [(1, dt_val)]
        result_mock.keys.return_value = ["id", "created_at"]
        db.execute.return_value = result_mock
        records = await service._export_table_data(db, "supported_villages")
        assert records[0]["created_at"] == dt_val.isoformat()

    @pytest.mark.asyncio
    async def test_export_table_data_with_bytes(self, service):
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.fetchall.return_value = [(1, b"\x00\x01\x02")]
        result_mock.keys.return_value = ["id", "data"]
        db.execute.return_value = result_mock
        records = await service._export_table_data(db, "supported_villages")
        assert records[0]["data"] == b"\x00\x01\x02".hex()

    @pytest.mark.asyncio
    async def test_export_table_data_exception(self, service):
        """W2-T1 新契约：导出异常向上传播，不再吞成空列表。"""
        db = MagicMock()
        db.execute.side_effect = Exception("query fail")
        with pytest.raises(Exception, match="query fail"):
            await service._export_table_data(db, "supported_villages")

    @pytest.mark.asyncio
    async def test_export_table_data_invalid_table_name(self, service):
        """W2-T1 新契约：非法表名异常向上传播。"""
        db = MagicMock()
        with patch.object(service, "_validate_table_name", side_effect=ValueError("invalid")):
            with pytest.raises(ValueError, match="invalid"):
                await service._export_table_data(db, "bad table")

    # ===================== _save_export_package =====================
    @pytest.mark.asyncio
    async def test_save_export_package(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            pkg_path = await service._save_export_package({"key": "val"}, "test_pkg", False)
            m.writestr.assert_called_once()
            assert str(pkg_path).endswith(".zip")

    @pytest.mark.asyncio
    async def test_save_export_package_with_files(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            with patch("app.utils.paths.get_uploads_path") as mock_uploads:
                up = MagicMock(spec=Path)
                up.exists.return_value = True
                up.resolve.return_value = up
                file_item = MagicMock(spec=Path)
                file_item.is_file.return_value = True
                file_item.resolve.return_value = file_item
                file_item.relative_to.return_value = Path("uploads/photo.jpg")
                up.rglob.return_value = [file_item]
                mock_uploads.return_value = up
                pkg_path = await service._save_export_package({"key": "val"}, "test_files", True)
                m.writestr.assert_called()
                m.write.assert_called_once()
                assert str(pkg_path).endswith(".zip")

    @pytest.mark.asyncio
    async def test_save_export_package_skip_unsafe(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            with patch("app.utils.paths.get_uploads_path") as mock_uploads:
                up = MagicMock(spec=Path)
                unsafe_file = MagicMock(spec=Path)
                unsafe_file.is_file.return_value = True
                unsafe_file.resolve.side_effect = ValueError("outside")
                up.exists.return_value = True
                up.resolve.return_value = up
                up.rglob.return_value = [unsafe_file]
                mock_uploads.return_value = up
                await service._save_export_package({"key": "val"}, "test_unsafe", True)
                m.write.assert_not_called()
                service.logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_export_package_uploads_not_exists(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            with patch("app.utils.paths.get_uploads_path") as mock_uploads:
                up = MagicMock(spec=Path)
                up.exists.return_value = False
                mock_uploads.return_value = up
                await service._save_export_package({"key": "val"}, "test_noupload", True)
                m.writestr.assert_called_once()
                m.write.assert_not_called()

    # ===================== import_package =====================
    @pytest.mark.asyncio
    async def test_import_package_success(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.get_db") as mock_get_db:
                db = MagicMock()
                mock_get_db.return_value = iter([db])
                with patch.object(service, "_load_import_package", new_callable=AsyncMock) as mock_load:
                    mock_load.return_value = {
                        "export_info": {"package_name": "test_export"},
                        "data": {"supported_villages": [{"id": 1, "name": "v1"}]},
                    }
                    with patch.object(service, "_import_table_data", new_callable=AsyncMock) as mock_imp:
                        mock_imp.return_value = {"total": 1, "success": 1, "failed": 0, "conflicts": []}
                        result = await service.import_package("/tmp/test.zip", strategy="skip", user_id=1, user_name="admin")
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_import_package_file_not_exists(self, service):
        from app.core.error_handler import BusinessLogicError
        with pytest.raises(BusinessLogicError, match="数据包文件不存在"):
            await service.import_package("/tmp/nonexistent.zip")

    @pytest.mark.asyncio
    async def test_import_package_invalid_format(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch.object(service, "_load_import_package", new_callable=AsyncMock) as mock_load:
                mock_load.return_value = {}
                from app.core.error_handler import BusinessLogicError
                with pytest.raises(BusinessLogicError, match="数据包格式错误"):
                    await service.import_package("/tmp/test.zip")

    @pytest.mark.asyncio
    async def test_import_package_table_not_in_syncable(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.get_db") as mock_get_db:
                db = MagicMock()
                mock_get_db.return_value = iter([db])
                with patch.object(service, "_load_import_package", new_callable=AsyncMock) as mock_load:
                    mock_load.return_value = {"export_info": {}, "data": {"unknown_table": [{"id": 1}]}}
                    with patch.object(service, "_import_table_data", new_callable=AsyncMock) as mock_imp:
                        result = await service.import_package("/tmp/test.zip")
                        mock_imp.assert_not_called()
                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_import_package_table_import_error(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.get_db") as mock_get_db:
                db = MagicMock()
                mock_get_db.return_value = iter([db])
                with patch.object(service, "_load_import_package", new_callable=AsyncMock) as mock_load:
                    mock_load.return_value = {"export_info": {}, "data": {"supported_villages": [{"id": 1}]}}
                    with patch.object(service, "_import_table_data", new_callable=AsyncMock) as mock_imp:
                        mock_imp.side_effect = Exception("import error")
                        result = await service.import_package("/tmp/test.zip")
                        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_import_package_general_exception(self, service):
        with patch.object(service, "_load_import_package", new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = Exception("big fail")
            from app.core.error_handler import BusinessLogicError
            with pytest.raises(BusinessLogicError, match="数据导入失败"):
                await service.import_package("/tmp/test.zip")

    # ===================== _load_import_package =====================
    @pytest.mark.asyncio
    async def test_load_import_package_success(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            m = MagicMock()
            mock_zip.return_value.__enter__ = MagicMock(return_value=m)
            mock_zip.return_value.__exit__ = MagicMock()
            file_ctx = MagicMock()
            file_ctx.__enter__.return_value.read.return_value = json.dumps({"key": "val"}).encode("utf-8")
            m.open.return_value = file_ctx
            result = await service._load_import_package(Path("/tmp/test_pkg.zip"))
            assert result == {"key": "val"}

    @pytest.mark.asyncio
    async def test_load_import_package_failure(self, service):
        with patch("zipfile.ZipFile") as mock_zip:
            mock_zip.side_effect = Exception("bad zip")
            result = await service._load_import_package(Path("/tmp/test_pkg.zip"))
            assert result == {}

    # ===================== _import_table_data =====================
    @pytest.mark.asyncio
    async def test_import_skip_existing(self, service):
        db = MagicMock()
        existing = MagicMock()
        existing.keys.return_value = ["id", "name"]
        db.execute.return_value.fetchone.return_value = existing
        result = await service._import_table_data(db, "supported_villages", [{"id": 1}], "skip", 1)
        assert result["success"] == 1
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_overwrite(self, service):
        db = MagicMock()
        existing = MagicMock()
        existing.keys.return_value = ["id", "name"]
        db.execute.return_value.fetchone.return_value = existing
        with patch.object(service, "_update_record", new_callable=AsyncMock) as mock_upd:
            result = await service._import_table_data(db, "supported_villages", [{"id": 1, "name": "v2"}], "overwrite", 1)
            assert result["success"] == 1
            mock_upd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_manual_conflict(self, service):
        db = MagicMock()
        existing = MockRow(id=1, name="v1")
        db.execute.return_value.fetchone.return_value = existing
        result = await service._import_table_data(db, "supported_villages", [{"id": 1, "name": "v2"}], "manual", 1)
        assert result["success"] == 1
        assert len(result["conflicts"]) == 1
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_insert_new(self, service):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        with patch.object(service, "_insert_record", new_callable=AsyncMock) as mock_ins:
            result = await service._import_table_data(db, "supported_villages", [{"id": 99, "name": "new"}], "skip", 1)
            assert result["success"] == 1
            mock_ins.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_no_id(self, service):
        db = MagicMock()
        with patch.object(service, "_insert_record", new_callable=AsyncMock) as mock_ins:
            result = await service._import_table_data(db, "supported_villages", [{"name": "no_id"}], "skip", 1)
            assert result["success"] == 1
            mock_ins.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_record_exception(self, service):
        db = MagicMock()
        db.execute.side_effect = Exception("db error")
        result = await service._import_table_data(db, "supported_villages", [{"id": 1}], "skip", 1)
        assert result["failed"] == 1

    # ===================== static methods =====================
    def test_sanitize_column_name_valid(self, service):
        assert service._sanitize_column_name("valid_name") == "valid_name"

    def test_sanitize_column_name_invalid(self, service):
        with pytest.raises(ValueError, match="非法的列名"):
            service._sanitize_column_name("bad-col!")

    def test_validate_table_name_valid(self, service):
        assert service._validate_table_name("users") == "users"

    def test_validate_table_name_invalid_format(self, service):
        with pytest.raises(ValueError, match="非法的表名"):
            service._validate_table_name("bad table name!")

    def test_validate_table_name_not_allowed(self, service):
        with pytest.raises(ValueError, match="表名不在允许列表中"):
            service._validate_table_name("valid_name_but_not_allowed")

    # ===================== _insert_record =====================
    @pytest.mark.asyncio
    async def test_insert_record(self, service):
        db = MagicMock()
        with patch.object(service, "_validate_table_name", return_value="supported_villages"):
            with patch.object(service, "_sanitize_column_name", side_effect=lambda x: x):
                await service._insert_record(db, "supported_villages", {"id": 1, "name": "test"})
                db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_record_invalid_column(self, service):
        db = MagicMock()
        with patch.object(service, "_sanitize_column_name", side_effect=ValueError("bad")):
            with pytest.raises(ValueError):
                await service._insert_record(db, "t", {"bad-col!": "val"})

    # ===================== _update_record =====================
    @pytest.mark.asyncio
    async def test_update_record(self, service):
        db = MagicMock()
        with patch.object(service, "_validate_table_name", return_value="supported_villages"):
            with patch.object(service, "_sanitize_column_name", side_effect=lambda x: x):
                await service._update_record(db, "supported_villages", {"id": 1, "name": "updated"})
                db.execute.assert_called_once()

    # ===================== get_conflicts =====================
    @pytest.mark.asyncio
    async def test_get_conflicts(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            from datetime import datetime, timezone
            conflict = MagicMock()
            conflict.id = 1
            conflict.table_name = "t"
            conflict.record_id = "1"
            conflict.conflict_type = "duplicate"
            conflict.local_data = {}
            conflict.import_data = {}
            conflict.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            q = MagicMock()
            f = MagicMock()
            db.query.return_value = q
            q.filter.return_value = f
            f.all.return_value = [conflict]
            result = await service.get_conflicts(1)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_conflicts_empty(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            q = MagicMock()
            f = MagicMock()
            db.query.return_value = q
            q.filter.return_value = f
            f.all.return_value = []
            result = await service.get_conflicts(1)
            assert result == []

    # ===================== resolve_conflict =====================
    @pytest.mark.asyncio
    async def test_resolve_keep_local(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            c = MagicMock()
            c.resolved = False
            db.query.return_value.filter.return_value.first.return_value = c
            result = await service.resolve_conflict(1, "keep_local")
            assert result["success"] is True
            assert c.resolution == "keep_local"
            db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_use_import(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            c = MagicMock()
            c.table_name = "t"
            c.import_data = {"id": 1}
            c.resolved = False
            db.query.return_value.filter.return_value.first.return_value = c
            with patch.object(service, "_update_record", new_callable=AsyncMock) as m:
                result = await service.resolve_conflict(1, "use_import")
                m.assert_awaited_once()
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_resolve_merge(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            c = MagicMock()
            c.table_name = "t"
            c.resolved = False
            db.query.return_value.filter.return_value.first.return_value = c
            with patch.object(service, "_update_record", new_callable=AsyncMock):
                result = await service.resolve_conflict(1, "merge", merged_data={"id": 1})
                assert c.merged_data == {"id": 1}

    @pytest.mark.asyncio
    async def test_resolve_merge_no_data(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            c = MagicMock()
            c.resolved = False
            db.query.return_value.filter.return_value.first.return_value = c
            from app.core.error_handler import BusinessLogicError
            with pytest.raises(BusinessLogicError, match="合并数据不能为空"):
                await service.resolve_conflict(1, "merge")

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            db.query.return_value.filter.return_value.first.return_value = None
            from app.core.error_handler import BusinessLogicError
            with pytest.raises(BusinessLogicError, match="冲突记录不存在"):
                await service.resolve_conflict(999, "keep_local")

    # ===================== export_encrypted =====================
    @pytest.mark.asyncio
    async def test_export_encrypted_no_password(self, service):
        from app.core.error_handler import BusinessLogicError
        with pytest.raises(BusinessLogicError, match="密码不能为空"):
            await service.export_encrypted(password=None)

    @pytest.mark.asyncio
    async def test_export_encrypted_short_password(self, service):
        from app.core.error_handler import BusinessLogicError
        with pytest.raises(BusinessLogicError, match="密码长度至少为8位"):
            await service.export_encrypted(password="1234567")

    @pytest.mark.asyncio
    async def test_export_encrypted_full(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as me:
                me.return_value = [{"id": 1}]
                with patch("app.services.data_sync_service.create_encrypted_package"):
                    with patch("app.services.data_sync_service._hashlib.sha256") as mh:
                        h = MagicMock()
                        h.hexdigest.return_value = "abc"
                        mh.return_value = h
                        with patch.object(Path, "read_bytes", return_value=b"d"):
                            with patch.object(Path, "stat") as ms:
                                ms.return_value.st_size = 512
                                r = await service.export_encrypted(export_type="full", password="password123")
                                assert r["success"] is True
                                assert r["file_hash"] == "abc"

    @pytest.mark.asyncio
    async def test_export_encrypted_selective(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as me:
                me.return_value = []
                with patch("app.services.data_sync_service.create_encrypted_package"):
                    with patch("app.services.data_sync_service._hashlib.sha256") as mh:
                        h = MagicMock()
                        h.hexdigest.return_value = "def"
                        mh.return_value = h
                        with patch.object(Path, "read_bytes", return_value=b"d"):
                            with patch.object(Path, "stat") as ms:
                                ms.return_value.st_size = 10
                                r = await service.export_encrypted(export_type="selective", tables=["supported_villages"], password="password123")
                                assert r["success"] is True

    @pytest.mark.asyncio
    async def test_export_encrypted_skip_unknown(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as me:
                with patch("app.services.data_sync_service.create_encrypted_package"):
                    with patch("app.services.data_sync_service._hashlib.sha256") as mh:
                        h = MagicMock()
                        h.hexdigest.return_value = "111"
                        mh.return_value = h
                        with patch.object(Path, "read_bytes", return_value=b"d"):
                            with patch.object(Path, "stat") as ms:
                                ms.return_value.st_size = 1
                                r = await service.export_encrypted(export_type="selective", tables=["unknown"], password="password123")
                                assert r["success"] is True
                                me.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_encrypted_export_error(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            db = MagicMock()
            mock_get_db.return_value = iter([db])
            with patch.object(service, "_export_table_data", new_callable=AsyncMock) as me:
                me.side_effect = Exception("fail")
                with patch("app.services.data_sync_service.create_encrypted_package"):
                    with patch("app.services.data_sync_service._hashlib.sha256") as mh:
                        h = MagicMock()
                        h.hexdigest.return_value = "222"
                        mh.return_value = h
                        with patch.object(Path, "read_bytes", return_value=b"d"):
                            with patch.object(Path, "stat") as ms:
                                ms.return_value.st_size = 1
                                r = await service.export_encrypted(export_type="full", password="password123")
                                assert r["success"] is True
                                service.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_export_encrypted_general_exception(self, service):
        with patch("app.services.data_sync_service.get_db") as mock_get_db:
            mock_get_db.side_effect = Exception("big")
            from app.core.error_handler import BusinessLogicError
            with pytest.raises(BusinessLogicError):
                await service.export_encrypted(password="password123")

    # ===================== import_encrypted =====================
    @pytest.mark.asyncio
    async def test_import_encrypted_file_not_exists(self, service):
        from app.core.error_handler import BusinessLogicError
        with pytest.raises(BusinessLogicError, match="数据包文件不存在"):
            await service.import_encrypted("/tmp/nonexistent.rrs", "pwd123")

    @pytest.mark.asyncio
    async def test_import_encrypted_value_error(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.extract_encrypted_package", side_effect=ValueError("bad")):
                from app.core.error_handler import BusinessLogicError
                with pytest.raises(BusinessLogicError, match="bad"):
                    await service.import_encrypted("/tmp/test.rrs", "pwd123")

    @pytest.mark.asyncio
    async def test_import_encrypted_success(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.extract_encrypted_package") as ext:
                ext.return_value = {"metadata": {"package_name": "enc"}, "data": {"supported_villages": [{"id": 1}]}}
                with patch("app.services.data_sync_service.get_db") as mock_get_db:
                    db = MagicMock()
                    mock_get_db.return_value = iter([db])
                    with patch.object(service, "_import_table_data_enhanced", new_callable=AsyncMock) as mi:
                        mi.return_value = {"total": 1, "success": 1, "failed": 0, "inserted": 1, "updated": 0, "skipped": 0, "conflicts": []}
                        r = await service.import_encrypted("/tmp/test.rrs", "pwd123", user_id=1, user_name="admin")
                        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_import_encrypted_skip_unknown(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.extract_encrypted_package") as ext:
                ext.return_value = {"metadata": {}, "data": {"unknown_table": [{"id": 1}]}}
                with patch("app.services.data_sync_service.get_db") as mock_get_db:
                    db = MagicMock()
                    mock_get_db.return_value = iter([db])
                    with patch.object(service, "_import_table_data_enhanced", new_callable=AsyncMock) as mi:
                        r = await service.import_encrypted("/tmp/test.rrs", "pwd123")
                        mi.assert_not_called()
                        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_import_encrypted_table_error(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.extract_encrypted_package") as ext:
                ext.return_value = {"metadata": {}, "data": {"supported_villages": [{"id": 1}]}}
                with patch("app.services.data_sync_service.get_db") as mock_get_db:
                    db = MagicMock()
                    mock_get_db.return_value = iter([db])
                    with patch.object(service, "_import_table_data_enhanced", new_callable=AsyncMock) as mi:
                        mi.side_effect = Exception("err")
                        r = await service.import_encrypted("/tmp/test.rrs", "pwd123")
                        assert len(r["errors"]) == 1

    @pytest.mark.asyncio
    async def test_import_encrypted_general_exception(self, service):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("app.services.data_sync_service.extract_encrypted_package", side_effect=Exception("big")):
                from app.core.error_handler import BusinessLogicError
                with pytest.raises(BusinessLogicError):
                    await service.import_encrypted("/tmp/test.rrs", "pwd123")

    # ===================== _import_table_data_enhanced =====================
    @pytest.mark.asyncio
    async def test_enhanced_skip(self, service):
        db = MagicMock()
        existing = MagicMock()
        existing.keys.return_value = ["id", "name"]
        db.execute.return_value.fetchone.return_value = existing
        r = await service._import_table_data_enhanced(db, "supported_villages", [{"id": 1}], "skip", 1)
        assert r["skipped"] == 1

    @pytest.mark.asyncio
    async def test_enhanced_overwrite(self, service):
        db = MagicMock()
        existing = MagicMock()
        existing.keys.return_value = ["id", "name"]
        db.execute.return_value.fetchone.return_value = existing
        with patch.object(service, "_update_record", new_callable=AsyncMock) as mu:
            r = await service._import_table_data_enhanced(db, "supported_villages", [{"id": 1}], "overwrite", 1)
            assert r["updated"] == 1
            mu.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enhanced_merge_update(self, service):
        db = MagicMock()
        existing = MagicMock()
        existing.keys.return_value = ["id", "name", "updated_at"]
        existing.__iter__ = MagicMock(return_value=iter([1, "old", "2024-01-01"]))
        db.execute.return_value.fetchone.return_value = existing
        with patch.object(service, "_should_update_record", return_value=True):
            with patch.object(service, "_update_record", new_callable=AsyncMock) as mu:
                r = await service._import_table_data_enhanced(db, "supported_villages", [{"id": 1, "updated_at": "new"}], "merge", 1)
                assert r["updated"] == 1
                mu.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enhanced_merge_skip(self, service):
        db = MagicMock()
        existing = MagicMock()
        existing.keys.return_value = ["id", "name", "updated_at"]
        existing.__iter__ = MagicMock(return_value=iter([1, "new", "2024-06-01"]))
        db.execute.return_value.fetchone.return_value = existing
        with patch.object(service, "_should_update_record", return_value=False):
            with patch.object(service, "_update_record", new_callable=AsyncMock) as mu:
                r = await service._import_table_data_enhanced(db, "supported_villages", [{"id": 1}], "merge", 1)
                assert r["skipped"] == 1
                mu.assert_not_called()

    @pytest.mark.asyncio
    async def test_enhanced_insert_new(self, service):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        with patch.object(service, "_insert_record", new_callable=AsyncMock):
            r = await service._import_table_data_enhanced(db, "supported_villages", [{"id": 99}], "merge", 1)
            assert r["inserted"] == 1

    @pytest.mark.asyncio
    async def test_enhanced_no_id(self, service):
        db = MagicMock()
        with patch.object(service, "_insert_record", new_callable=AsyncMock):
            r = await service._import_table_data_enhanced(db, "supported_villages", [{"name": "no_id"}], "merge", 1)
            assert r["inserted"] == 1

    @pytest.mark.asyncio
    async def test_enhanced_exception(self, service):
        db = MagicMock()
        db.execute.side_effect = Exception("db error")
        r = await service._import_table_data_enhanced(db, "supported_villages", [{"id": 1}], "merge", 1)
        assert r["failed"] == 1

    @pytest.mark.asyncio
    async def test_enhanced_empty(self, service):
        db = MagicMock()
        r = await service._import_table_data_enhanced(db, "supported_villages", [], "merge", 1)
        assert r["success"] == 0
        db.commit.assert_called_once()

    # ===================== _should_update_record =====================
    def test_should_update_no_updated_at(self, service):
        assert service._should_update_record({"id": 1}, {"id": 1}) is False

    def test_should_update_missing_in_existing(self, service):
        assert service._should_update_record({"id": 1}, {"id": 1, "updated_at": "2024-01-01"}) is False

    def test_should_update_missing_in_imported(self, service):
        assert service._should_update_record({"id": 1, "updated_at": "2024-01-01"}, {"id": 1}) is False

    def test_should_update_newer_str(self, service):
        from datetime import datetime, timezone
        existing_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = service._should_update_record(
            {"id": 1, "updated_at": existing_dt},
            {"id": 1, "updated_at": "2024-06-01T00:00:00+00:00"},
        )
        assert result is True

    def test_should_update_older_str(self, service):
        assert service._should_update_record({"id": 1, "updated_at": "2024-06-01"}, {"id": 1, "updated_at": "2024-01-01"}) is False

    def test_should_update_newer_dt(self, service):
        from datetime import datetime, timezone
        r = service._should_update_record(
            {"id": 1, "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc)},
            {"id": 1, "updated_at": datetime(2024, 6, 1, tzinfo=timezone.utc)},
        )
        assert r is True

    def test_should_update_parse_error(self, service):
        r = service._should_update_record({"id": 1, "updated_at": "bad"}, {"id": 1, "updated_at": "also-bad"})
        assert r is False

    # ===================== module-level instance =====================
    def test_data_sync_service_instance(self):
        with patch("app.utils.paths.get_app_data_dir") as mock_dir:
            mock_dir.return_value = Path("/tmp/test_instance")
            with patch("pathlib.Path.mkdir"):
                from app.services.data_sync_service import data_sync_service
                assert data_sync_service is not None
