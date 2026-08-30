"""增量数据包三端点(/incremental/detect-changes|export|import)接口测试

- detect-changes：真实内存库验证统计口径（added=基准后新建；deleted=基准后软删且
  基准前已存在；modified=其余变更；无物理删除墓碑，物理删除恒为 0）
- export：mock service 验证 record_counts 从 manifest 取（旧实现引用 schema 不存在的
  record_counts/total_records 字段会 AttributeError→500）、PackageType.update 与
  base_package_id 透传、非管理员 owner 范围
- import：真实 zip 验证预览统计（旧实现是空操作）；apply 仅管理员
"""
import json
import zipfile
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/data-packages"


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True, full_name="管理员")


def _regular():
    return SimpleNamespace(id=2, username="user2", role="user", is_superuser=False, full_name="普通用户")


@pytest.fixture
def mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def api(mem_db):
    """TestClient + 真实内存库 + 权限放行；返回 (client, db)"""
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    from app.api.v1.data.data.data_packages import get_permission_service

    app.dependency_overrides[get_db] = lambda: mem_db
    app.dependency_overrides[get_current_user] = lambda: _admin()
    app.dependency_overrides[get_permission_service] = lambda: MagicMock(
        can_access_organization=MagicMock(return_value=True)
    )
    client = TestClient(app, raise_server_exceptions=False)
    yield client, mem_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_permission_service, None)


def _seed_base_package(db, base_time: datetime):
    from app.models.data_package import DataPackage

    pkg = DataPackage(package_code="BASE1", org_id=1, created_at=base_time)
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


def _seed_villages(db, base_time: datetime):
    from app.models.supported_village import SupportedVillage

    old = SupportedVillage(
        village_name="基准前老村", organization_id=1,
        created_at=base_time - timedelta(days=10), updated_at=base_time - timedelta(days=10),
    )
    added = SupportedVillage(
        village_name="基准后新建", organization_id=1,
        created_at=base_time + timedelta(days=1), updated_at=base_time + timedelta(days=1),
    )
    deleted = SupportedVillage(
        village_name="基准后软删", organization_id=1, is_active=False,
        created_at=base_time - timedelta(days=5), updated_at=base_time + timedelta(days=2),
    )
    modified = SupportedVillage(
        village_name="基准后修改", organization_id=1,
        created_at=base_time - timedelta(days=3), updated_at=base_time + timedelta(days=3),
    )
    db.add_all([old, added, deleted, modified])
    db.commit()


class TestDetectChanges:
    def test_query_params_and_summary_shape(self, api):
        """前端以查询串传参（axios paramsSerializer indexes:null → 重复键无括号）"""
        client, db = api
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        _seed_base_package(db, base_time)
        _seed_villages(db, base_time)

        resp = client.post(
            f"{BASE}/incremental/detect-changes",
            params={"base_package_id": 1, "org_id": 1, "data_types": ["villages", "projects"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        summary = data["summary"]
        assert summary["by_type"]["villages"]["added"] == 1
        assert summary["by_type"]["villages"]["deleted"] == 1
        assert summary["by_type"]["villages"]["modified"] == 1
        assert summary["by_type"]["villages"]["total"] == 3
        assert summary["total_added"] == 1
        assert summary["total_modified"] == 1
        assert summary["total_deleted"] == 1
        # projects 无数据 → 全 0 且结构完整（前端表格直接渲染 by_type）
        assert summary["by_type"]["projects"] == {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        assert data["base_package_id"] == 1

    def test_missing_base_package_id_422(self, api):
        client, _ = api
        resp = client.post(f"{BASE}/incremental/detect-changes", params={"org_id": 1})
        assert resp.status_code == 422

    def test_org_forbidden_403(self, api):
        from app.core.security import get_current_user
        from app.main import app

        from app.api.v1.data.data.data_packages import get_permission_service

        client, db = api
        _seed_base_package(db, datetime(2024, 1, 1))
        app.dependency_overrides[get_current_user] = lambda: _regular()
        app.dependency_overrides[get_permission_service] = lambda: MagicMock(
            can_access_organization=MagicMock(return_value=False)
        )
        try:
            resp = client.post(
                f"{BASE}/incremental/detect-changes",
                params={"base_package_id": 1, "org_id": 1, "data_types": ["villages"]},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides[get_current_user] = lambda: _admin()
            app.dependency_overrides[get_permission_service] = lambda: MagicMock(
                can_access_organization=MagicMock(return_value=True)
            )

    def test_base_package_not_found_404(self, api):
        client, _ = api
        resp = client.post(
            f"{BASE}/incremental/detect-changes",
            params={"base_package_id": 999, "org_id": 1, "data_types": ["villages"]},
        )
        assert resp.status_code == 404


def _mock_export_service(record_counts=None):
    svc = MagicMock()
    svc.db = MagicMock()
    svc.get_package = MagicMock(return_value=SimpleNamespace(created_at=None))
    svc.export_package = AsyncMock(return_value=SimpleNamespace(
        package_id=9, package_code="EXP9", file_path="/tmp/EXP9.zip",
        file_name="EXP9.zip", file_size=123,
        manifest=SimpleNamespace(record_counts=record_counts or {"villages": 3}),
    ))
    return svc


def _install_mock_service(svc, user=None):
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    from app.api.v1.data.data.data_packages import get_package_service, get_permission_service

    app.dependency_overrides[get_package_service] = lambda: svc
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user or _admin()
    app.dependency_overrides[get_permission_service] = lambda: MagicMock(
        can_access_organization=MagicMock(return_value=True)
    )
    return app


class TestIncrementalExport:
    def test_returns_manifest_counts_and_passthrough(self):
        from app.main import app

        svc = _mock_export_service()
        _install_mock_service(svc)
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.post(
                f"{BASE}/incremental/export",
                json={
                    "org_id": 1, "data_types": ["villages"],
                    "base_package_id": 1, "description": "增量包",
                },
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()["data"]
            assert data["package_id"] == 9
            assert data["record_counts"] == {"villages": 3}
            assert data["total_records"] == 3
            assert data["download_url"] == "/api/v1/data-packages/9/download"
            assert data["filename"] == "EXP9.zip"

            _, kwargs = svc.export_package.call_args
            from app.models.data_package import PackageType

            assert kwargs["package_type"] is PackageType.update
            assert kwargs["incremental"] is True
            assert kwargs["base_package_id"] == 1
            assert kwargs["owner_id"] is None  # 管理员导出全组织
            assert kwargs["since_time"] is not None
        finally:
            app.dependency_overrides.clear()

    def test_non_admin_owner_scope(self):
        from app.main import app

        svc = _mock_export_service()
        _install_mock_service(svc, user=_regular())
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.post(
                f"{BASE}/incremental/export",
                json={"org_id": 1, "data_types": ["villages"], "base_package_id": 1},
            )
            assert resp.status_code == 200, resp.text
            _, kwargs = svc.export_package.call_args
            assert kwargs["owner_id"] == 2  # 非管理员仅导出本人录入
        finally:
            app.dependency_overrides.clear()

    def test_base_package_not_found_404(self):
        from app.main import app

        svc = _mock_export_service()
        svc.get_package = MagicMock(return_value=None)  # 基准包不存在
        _install_mock_service(svc)
        client = TestClient(app, raise_server_exceptions=False)
        try:
            resp = client.post(
                f"{BASE}/incremental/export",
                json={"org_id": 1, "data_types": ["villages"], "base_package_id": 42},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


def _make_incremental_zip(tmp_path, records):
    """构造 manifest+data 标准结构的增量包 zip"""
    path = tmp_path / "INC1.zip"
    manifest = {
        "version": "1.1", "package_type": "update", "org_code": "ORG001",
        "data_types": ["villages"], "record_counts": {"villages": len(records)},
        "incremental": True,
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr("data/villages.json", json.dumps(records, ensure_ascii=False))
    return str(path)


def _seed_package_with_file(db, file_path: str):
    from app.models.data_package import DataPackage

    pkg = DataPackage(
        package_code="INC1", org_id=1, file_path=file_path, file_name="INC1.zip",
        status="validated", type="update",
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


class TestIncrementalImport:
    def test_preview_stats(self, api, tmp_path):
        client, db = api
        from app.models.supported_village import SupportedVillage

        db.add(SupportedVillage(id=1, village_name="本地已有村", organization_id=1))
        db.commit()
        zip_path = _make_incremental_zip(tmp_path, [
            {"id": 1, "village_name": "本地已有村"},
            {"id": 999, "village_name": "包内新增村"},
        ])
        pkg = _seed_package_with_file(db, zip_path)

        resp = client.post(
            f"{BASE}/incremental/import",
            json={"package_id": pkg.id, "apply_changes": False},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["success"] is True
        assert data["preview_only"] is True
        assert data["stats"]["villages"]["added"] == 1
        assert data["stats"]["villages"]["modified"] == 1
        assert data["summary"]["total_added"] == 1
        assert data["summary"]["total_modified"] == 1

    def test_package_missing_file_404(self, api):
        client, db = api
        from app.models.data_package import DataPackage

        pkg = DataPackage(package_code="NOFILE", org_id=1, file_path=None)
        db.add(pkg)
        db.commit()
        db.refresh(pkg)
        resp = client.post(
            f"{BASE}/incremental/import",
            json={"package_id": pkg.id, "apply_changes": False},
        )
        assert resp.status_code == 404

    def test_apply_requires_admin_403(self, api, tmp_path):
        from app.core.security import get_current_user
        from app.main import app

        client, db = api
        zip_path = _make_incremental_zip(tmp_path, [{"id": 1, "village_name": "村"}])
        pkg = _seed_package_with_file(db, zip_path)
        app.dependency_overrides[get_current_user] = lambda: _regular()
        try:
            resp = client.post(
                f"{BASE}/incremental/import",
                json={"package_id": pkg.id, "apply_changes": True},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides[get_current_user] = lambda: _admin()

    def test_apply_success_uses_confirm(self, api, tmp_path):
        """apply 路径：注册包 + confirm_import(overwrite) + 审计，成功返回结构"""
        client, db = api
        zip_path = _make_incremental_zip(tmp_path, [{"id": 1, "village_name": "村"}])
        pkg = _seed_package_with_file(db, zip_path)

        from app.api.v1.data.data.data_packages import (
            get_history_service,
            get_package_service,
        )
        from app.main import app

        svc = MagicMock()
        svc.db = db
        svc.get_package = MagicMock(return_value=pkg)
        svc.import_package = AsyncMock(return_value=SimpleNamespace(package_id=77))
        svc.confirm_import = AsyncMock(return_value=SimpleNamespace(
            success=True, package_id=77,
            imported_counts={"villages": 2}, skipped_counts={}, error_counts={}, errors=[],
        ))
        hist = MagicMock()
        app.dependency_overrides[get_package_service] = lambda: svc
        app.dependency_overrides[get_history_service] = lambda: hist
        try:
            resp = client.post(
                f"{BASE}/incremental/import",
                json={"package_id": pkg.id, "apply_changes": True},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()["data"]
            assert data["success"] is True
            assert data["preview_only"] is False
            assert data["package_id"] == 77
            svc.confirm_import.assert_awaited_once()
            _, kwargs = svc.confirm_import.call_args
            assert kwargs["overwrite_existing"] is True
            hist.record_import.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_package_service, None)
            app.dependency_overrides.pop(get_history_service, None)

    def test_apply_confirm_failure_returns_soft_error(self, api, tmp_path):
        """confirm 失败 → 200 + success=false（数据已回滚），前端按 message 提示"""
        client, db = api
        zip_path = _make_incremental_zip(tmp_path, [{"id": 1, "village_name": "村"}])
        pkg = _seed_package_with_file(db, zip_path)

        from app.api.v1.data.data.data_packages import get_package_service
        from app.main import app

        svc = MagicMock()
        svc.db = db
        svc.get_package = MagicMock(return_value=pkg)
        svc.import_package = AsyncMock(return_value=SimpleNamespace(package_id=78))
        svc.confirm_import = AsyncMock(return_value=SimpleNamespace(
            success=False, package_id=78, imported_counts={}, skipped_counts={},
            error_counts={}, errors=[],
        ))
        app.dependency_overrides[get_package_service] = lambda: svc
        try:
            resp = client.post(
                f"{BASE}/incremental/import",
                json={"package_id": pkg.id, "apply_changes": True},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["success"] is False
        finally:
            app.dependency_overrides.pop(get_package_service, None)
