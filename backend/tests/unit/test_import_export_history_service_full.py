"""Tests for app/services/import_export_history_service.py — 目标 100% 覆盖。

覆盖要点：
- create_history:
  * 成功（枚举 result / 字符串 result）
  * commit 异常 → rollback + re-raise
- record_export / record_import / record_validate / record_preview /
  record_confirm / record_delete：各便捷方法调用 create_history 并写入正确字段
- get_history_by_package: 多条记录按 created_at 倒序 + skip/limit 分页
- list_history (async): 无 user_id / 有 user_id / 空结果
- record (async): 创建记录并 commit+refresh
"""
import importlib

import pytest

# 异步 SQLAlchemy 依赖 greenlet；32 位 Python 无 wheel 无法安装时跳过而非报错
pytest.importorskip("greenlet")

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import _MODULE_MAP
from app.models.base import Base
from app.models.import_export_history import OperationResult
from app.services.import_export_history_service import ImportExportHistoryService


# ---------------------------------------------------------------------------
# 同步内存 DB fixture
# ---------------------------------------------------------------------------


def _import_all_models():
    for mod_path in set(_MODULE_MAP.values()):
        importlib.import_module(f"app.models{mod_path}")


def _build_sync_session():
    _import_all_models()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session(), engine


@pytest.fixture
def sync_db():
    db, engine = _build_sync_session()
    yield db
    db.close()
    engine.dispose()


async def _build_async_session():
    _import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    return Session(), engine


@pytest.fixture
async def async_db():
    db, engine = await _build_async_session()
    yield db
    await db.close()
    await engine.dispose()


# ---------------------------------------------------------------------------
# create_history
# ---------------------------------------------------------------------------


class TestCreateHistory:
    def test_success_with_enum_result(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.create_history(
            org_id=1, user_id=2, operation_type="export",
            result=OperationResult.SUCCESS, duration_ms=100, client_ip="127.0.0.1",
        )
        assert record.id is not None
        assert record.operation_type == "export"
        assert record.result == "success"
        assert record.duration_ms == 100
        assert record.ip_address == "127.0.0.1"

    def test_success_with_string_result(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.create_history(
            org_id=1, user_id=2, operation_type="import",
            result="failed", error_message="bad file",
        )
        assert record.result == "failed"
        assert record.error_message == "bad file"

    def test_extra_kwargs_ignored_but_logged(self, sync_db, caplog):
        """未声明的额外参数不再静默：仍不落库，但输出告警日志（可追踪）。"""
        svc = ImportExportHistoryService(sync_db)
        with caplog.at_level("WARNING", logger="app.services.import_export_history_service"):
            record = svc.create_history(
                org_id=1, user_id=2, custom_field="ignored",
            )
        assert record.id is not None
        assert any("custom_field" in rec.getMessage() for rec in caplog.records)

    def test_audit_metadata_is_persisted(self, sync_db):
        """显式声明的 6 个审计元数据列必须真正落库（历史缺陷：落进 **extra 被吞）。"""
        svc = ImportExportHistoryService(sync_db)
        record = svc.create_history(
            org_id=1, user_id=2, operation_type="export",
            file_name="audit.xlsx", file_size=2048, record_count=12,
            data_types=["village"], user_agent="pytest/1.0",
            details_json={"source": "unit-test"},
        )
        assert record.file_name == "audit.xlsx"
        assert record.file_size == 2048
        assert record.record_count == 12
        assert record.data_types == '["village"]'
        assert record.user_agent == "pytest/1.0"
        assert record.details_json == '{"source": "unit-test"}'

    def test_dump_json_passthrough_and_none(self, sync_db):
        """_dump_json: None/字符串原样透传，列表/字典序列化。"""
        svc = ImportExportHistoryService(sync_db)
        assert svc._dump_json(None) is None
        assert svc._dump_json("[1]") == "[1]"
        assert svc._dump_json(["a"]) == '["a"]'
        assert svc._dump_json({"k": "v"}) == '{"k": "v"}'

    def test_commit_failure_raises_and_rolls_back(self, sync_db):
        """commit 抛异常 → rollback + re-raise。"""
        svc = ImportExportHistoryService(sync_db)

        original_commit = sync_db.commit

        def raising_commit():
            raise RuntimeError("commit failed")

        sync_db.commit = raising_commit
        sync_db.rollback = lambda: None  # 避免事务状态问题
        try:
            with pytest.raises(RuntimeError, match="commit failed"):
                svc.create_history(org_id=1, user_id=2)
        finally:
            sync_db.commit = original_commit


# ---------------------------------------------------------------------------
# record_export / record_import
# ---------------------------------------------------------------------------


class TestRecordExportImport:
    def test_record_export(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_export(
            org_id=1, user_id=2, file_name="data.rrs", file_size=1024,
            record_count=10, data_types=["village", "fund"], duration_ms=50,
            ip_address="10.0.0.1", user_agent="curl/8",
        )
        assert record.operation_type == "export"
        # 审计元数据必须落库（不再落进 **extra 被静默丢弃）
        assert record.file_name == "data.rrs"
        assert record.file_size == 1024
        assert record.record_count == 10
        assert record.data_types == '["village", "fund"]'
        assert record.user_agent == "curl/8"
        assert record.duration_ms == 50
        assert record.ip_address == "10.0.0.1"
        assert record.result == "success"

    def test_record_export_without_optional_fields(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_export(org_id=1, user_id=2)
        assert record.operation_type == "export"
        assert record.duration_ms is None

    def test_record_import(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_import(
            org_id=1, user_id=2, file_name="in.rrs", data_types=["village"],
            result=OperationResult.FAILED, error_message="parse error",
        )
        assert record.operation_type == "import"
        assert record.result == "failed"
        assert record.error_message == "parse error"
        assert record.file_name == "in.rrs"
        assert record.data_types == '["village"]'

    def test_record_import_without_data_types(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_import(org_id=1, user_id=2)
        assert record.operation_type == "import"


# ---------------------------------------------------------------------------
# record_validate / record_preview
# ---------------------------------------------------------------------------


class TestRecordValidatePreview:
    def test_record_validate(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_validate(
            org_id=1, user_id=2, ip_address="10.0.0.2",
            result=OperationResult.PARTIAL, error_message="some warnings",
        )
        assert record.operation_type == "validate"
        assert record.result == "partial"
        assert record.ip_address == "10.0.0.2"

    def test_record_preview(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_preview(
            org_id=1, user_id=2, ip_address="10.0.0.3",
        )
        assert record.operation_type == "preview"
        assert record.ip_address == "10.0.0.3"


# ---------------------------------------------------------------------------
# record_confirm / record_delete
# ---------------------------------------------------------------------------


class TestRecordConfirmDelete:
    def test_record_confirm(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_confirm(
            org_id=1, user_id=2, record_count=5, data_types=["fund"],
            duration_ms=200, details={"source": "upload"}, ip_address="10.0.0.4",
        )
        assert record.operation_type == "confirm"
        # record_count / data_types / details_json 审计元数据必须落库
        assert record.record_count == 5
        assert record.data_types == '["fund"]'
        assert record.details_json == '{"source": "upload"}'
        assert record.duration_ms == 200
        assert record.ip_address == "10.0.0.4"
        assert record.result == "success"

    def test_record_confirm_without_details(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_confirm(org_id=1, user_id=2)
        assert record.operation_type == "confirm"

    def test_record_delete(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        record = svc.record_delete(
            org_id=1, user_id=2, reason="duplicate", ip_address="10.0.0.5",
        )
        assert record.operation_type == "delete"
        # reason → error_message（create_history 参数映射）
        assert record.error_message == "duplicate"
        assert record.ip_address == "10.0.0.5"


# ---------------------------------------------------------------------------
# get_history_by_package
# ---------------------------------------------------------------------------


class TestGetHistoryByPackage:
    def test_returns_records_ordered_desc_with_pagination(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        # 为 package_id=1 创建 3 条记录
        svc.create_history(package_id=1, org_id=1, user_id=1, operation_type="export")
        svc.create_history(package_id=1, org_id=1, user_id=1, operation_type="import")
        svc.create_history(package_id=1, org_id=1, user_id=1, operation_type="validate")
        # package_id=2 的记录不应返回
        svc.create_history(package_id=2, org_id=1, user_id=1, operation_type="export")

        records = svc.get_history_by_package(1)
        assert len(records) == 3
        # 全部属于 package_id=1
        assert all(r.package_id == 1 for r in records)

    def test_pagination_skip_limit(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        for _ in range(5):
            svc.create_history(package_id=1, org_id=1, user_id=1, operation_type="export")

        page = svc.get_history_by_package(1, skip=2, limit=2)
        assert len(page) == 2

    def test_empty_result(self, sync_db):
        svc = ImportExportHistoryService(sync_db)
        records = svc.get_history_by_package(999)
        assert records == []


# ---------------------------------------------------------------------------
# list_history (async)
# ---------------------------------------------------------------------------


class TestListHistory:
    async def test_without_user_id(self, async_db):
        svc = ImportExportHistoryService(async_db)
        # 用 async record 创建数据
        await svc.record(org_id=1, user_id=1, operation_type="export", result="success")
        await svc.record(org_id=1, user_id=2, operation_type="import", result="success")

        result = await svc.list_history(page=1, page_size=20)
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["page"] == 1
        assert result["page_size"] == 20

    async def test_with_user_id_filter(self, async_db):
        svc = ImportExportHistoryService(async_db)
        await svc.record(org_id=1, user_id=1, operation_type="export", result="success")
        await svc.record(org_id=1, user_id=2, operation_type="import", result="success")
        await svc.record(org_id=1, user_id=1, operation_type="validate", result="success")

        result = await svc.list_history(page=1, page_size=20, user_id=1)
        assert result["total"] == 2
        assert all(item.user_id == 1 for item in result["items"])

    async def test_empty_result(self, async_db):
        svc = ImportExportHistoryService(async_db)
        result = await svc.list_history(page=1, page_size=20)
        assert result["total"] == 0
        assert result["items"] == []


# ---------------------------------------------------------------------------
# record (async)
# ---------------------------------------------------------------------------


class TestRecordAsync:
    async def test_creates_and_commits(self, async_db):
        svc = ImportExportHistoryService(async_db)
        record = await svc.record(
            org_id=1, user_id=2, operation_type="export", result="success",
            file_name="x.rrs", file_size=10,
        )
        assert record.id is not None
        assert record.operation_type == "export"
        assert record.file_name == "x.rrs"
