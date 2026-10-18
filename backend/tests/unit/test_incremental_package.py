"""增量数据包(T3.1): schema + 过滤 + API 透传"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.schemas.data_package import DataPackageExportRequest


def test_schema_incremental_fields():
    req = DataPackageExportRequest(data_types=["villages"])
    assert req.incremental is False
    assert req.since_sync_version is None
    req2 = DataPackageExportRequest(data_types=["villages"], incremental=True, since_sync_version=42)
    assert req2.incremental is True
    assert req2.since_sync_version == 42


class _FakeColumn:
    def __init__(self, name):
        self.name = name


class _FakeTable:
    def __init__(self, *column_names):
        self.columns = [_FakeColumn(name) for name in column_names]


class _FakeModel:
    """W18-D8：_export_data_type 走 raw SQL，模型只需表名 + 列元数据。"""

    __tablename__ = "incremental_schools"
    __table__ = _FakeTable("id", "sync_version")
    sync_version = 1
    org_id = 1


def _svc_with_execute(rows=()):
    from app.services.data_package_service import DataPackageService

    db = MagicMock()
    db.execute.return_value.fetchall.return_value = list(rows)
    svc = DataPackageService(db)
    return svc, db


def test_export_data_type_incremental_filter():
    # 增量: org 过滤 + sync_version 过滤
    svc, db = _svc_with_execute()
    svc._export_data_type(1, _FakeModel(), since_sync_version=100)
    stmt, params = db.execute.call_args.args
    sql = str(stmt)
    assert "org_id = :org_id" in sql
    assert "sync_version > :since_sync" in sql
    assert params == {"org_id": 1, "since_sync": 100}

    # 全量: 仅 org 过滤（sync_version 只作为选列出现，不得出现在 WHERE 条件）
    svc._export_data_type(1, _FakeModel(), since_sync_version=None)
    stmt, params = db.execute.call_args.args
    sql = str(stmt)
    assert "sync_version > :since_sync" not in sql
    assert "org_id = :org_id" in sql
    assert params == {"org_id": 1}


def test_export_data_type_incremental_no_sync_column():
    class _NoSyncModel:
        __tablename__ = "incremental_no_sync"
        __table__ = _FakeTable("id")
        org_id = 1

    svc, db = _svc_with_execute()
    svc._export_data_type(1, _NoSyncModel(), since_sync_version=100)
    stmt, params = db.execute.call_args.args
    sql = str(stmt)
    assert "sync_version > :since_sync" not in sql
    assert "org_id = :org_id" in sql
    assert params == {"org_id": 1}


def test_export_api_passes_incremental():
    """API 端点透传 incremental/since_sync_version 到 service"""
    from app.main import app
    from fastapi.testclient import TestClient

    from app.api.v1.data.data.data_packages import get_package_service
    from app.core.database import get_db
    from app.core.security import get_current_user

    mock_svc = MagicMock()
    mock_svc.db = MagicMock()
    mock_svc.export_package = AsyncMock(return_value=SimpleNamespace(
        package_id=1, file_name="EXP001.zip", file_path="/tmp/EXP001.zip",
        file_size=100, total_records=3, manifest={}, checksum="abc",
        record_counts={}, data_types=["villages"], description="增量包",
        status="success", message="ok",
    ))
    mock_hist = MagicMock()
    mock_hist.log_export = AsyncMock()

    def _override(service):
        from app.api.v1.data.data.data_packages import get_history_service, get_permission_service
        app.dependency_overrides[get_package_service] = lambda: service
        app.dependency_overrides[get_history_service] = lambda: mock_hist
        app.dependency_overrides[get_permission_service] = lambda: MagicMock(
            can_access_organization=MagicMock(return_value=True),
        )
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, username="admin", role="admin",
        )

    _override(mock_svc)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.post(
            "/api/v1/data-packages/export",
            json={
                "data_types": ["villages"],
                "incremental": True,
                "since_sync_version": 77,
            },
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 200, resp.text
        _, kwargs = mock_svc.export_package.call_args
        assert kwargs["incremental"] is True
        assert kwargs["since_sync_version"] == 77
    finally:
        app.dependency_overrides.clear()


def test_export_api_full_without_incremental():
    from app.main import app
    from fastapi.testclient import TestClient

    from app.api.v1.data.data.data_packages import get_package_service
    from app.core.database import get_db
    from app.core.security import get_current_user

    mock_svc = MagicMock()
    mock_svc.db = MagicMock()
    mock_svc.export_package = AsyncMock(return_value=SimpleNamespace(
        package_id=2, file_name="EXP002.zip", file_path="/tmp/EXP002.zip",
        file_size=50, total_records=1, manifest={}, checksum="x",
        record_counts={}, data_types=["villages"], description="全量包",
        status="success", message="ok",
    ))

    from app.api.v1.data.data.data_packages import get_history_service, get_permission_service
    app.dependency_overrides[get_package_service] = lambda: mock_svc
    app.dependency_overrides[get_history_service] = lambda: MagicMock(log_export=AsyncMock())
    app.dependency_overrides[get_permission_service] = lambda: MagicMock(
        can_access_organization=MagicMock(return_value=True),
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="admin", role="admin",
    )
    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.post(
            "/api/v1/data-packages/export",
            json={"data_types": ["villages"]},
            headers={"Authorization": "Bearer tok"},
        )
        assert resp.status_code == 200, resp.text
        _, kwargs = mock_svc.export_package.call_args
        assert kwargs["incremental"] is False
        assert kwargs["since_sync_version"] is None
    finally:
        app.dependency_overrides.clear()
