"""账号包 API 集成：超管导出/下载/列表、pristine 预览/确认。"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.core.grant_signing import generate_keypair
from app.core.security import get_current_user
from app.main import app
from app.models.base import Base
from app.models.organization import Organization
from app.services.account_package_service import AccountPackageService
from app.services.machine_code_service import MachineCodeService
from app.utils.audit_logger import AuditLogger


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    priv, pub = generate_keypair()
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", True)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", priv)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_PUBKEY", pub)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_KDF_ITERATIONS", 310_000)
    # P4：本文件验证错误码映射，不验证限流；关闭速率闸门避免连续失败请求被 429 打断。
    # 锁定/速率行为由 test_account_package_rate_limit.py 专门覆盖。
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ATTEMPT_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(AccountPackageService, "package_dir", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(MachineCodeService, "get_machine_code", staticmethod(lambda: "MC-API-123"))
    monkeypatch.setattr("app.api.v1.account_package._client_is_loopback", lambda request: True)
    return tmp_path


def _use_db(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user


def _org(db, code="520000", name="州局", parent=None, level="1"):
    org = Organization(code=code, name=name, parent_id=getattr(parent, "id", None), level=level, is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    return org


def test_export_download_list_revoke(client, api_env):
    source = _db()
    root = _org(source)
    _org(source, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(source, admin)
    try:
        body = {
            "organization_code": "520100", "organization_name": "市局", "parent_code": "520000",
            "admin_username": "api_admin", "admin_full_name": "管理员",
            "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
            "grants": {"projects": "edit"}, "valid_days": 7,
            "accounts": [{"username": "api_admin", "full_name": "管理员", "role": "admin", "data_scope": "org"}],
        }
        r = client.post("/api/v1/account-packages/export", json=body)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["accounts"][0]["one_time_password"]
        assert data["authorization"]["page_count"] == 1
        assert data["authorization"]["module_count"] == 1
        pid = data["package_id"]

        assert client.get(f"/api/v1/account-packages/{pid}/download").status_code == 200
        listed = client.get("/api/v1/account-packages")
        assert listed.status_code == 200 and listed.json()["data"]["total"] == 1
        revoked = client.post(f"/api/v1/account-packages/{pid}/revoke", json={"reason": "test"})
        assert revoked.status_code == 200
        assert revoked.json()["data"]["state"] == "revoked"
    finally:
        app.dependency_overrides.clear()


def test_pristine_preview_confirm(client, api_env):
    source = _db()
    root = _org(source)
    _org(source, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(source, admin)
    r = client.post("/api/v1/account-packages/export", json={
        "organization_code": "520100", "organization_name": "市局", "parent_code": "520000",
        "admin_username": "p_admin", "admin_full_name": "管理员",
        "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
        "grants": {"projects": "view"},
    })
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["package_id"]
    raw = (api_env / f"account-package-{pid}.apkg").read_bytes()

    target = _db()
    _org(target, "520000")
    app.dependency_overrides[get_db] = lambda: target
    app.dependency_overrides.pop(get_current_user, None)
    try:
        files = {"file": ("pkg.apkg", raw, "application/octet-stream")}
        preview = client.post("/api/v1/account-packages/preview", files=files, data={"password": "passw0rd-pass"})
        assert preview.status_code == 200, preview.text
        assert preview.json()["data"]["admin"]["username"] == "p_admin"
        confirm = client.post("/api/v1/account-packages/confirm", files=files, data={"password": "passw0rd-pass"})
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["data"]["users"][0]["username"] == "p_admin"
    finally:
        app.dependency_overrides.clear()


def test_export_error_paths_and_download_missing(client, api_env):
    source = _db(); root = _org(source)
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(source, admin)
    try:
        # 功能关闭
        settings.ACCOUNT_PACKAGE_ENABLED = False
        r = client.post("/api/v1/account-packages/export", json={
            "organization_code": "520100", "admin_username": "u", "admin_full_name": "u",
            "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
        })
        assert r.status_code == 403 and r.json()["detail"]["code"] == "AP_DISABLED"
        settings.ACCOUNT_PACKAGE_ENABLED = True
        # 弱口令
        r = client.post("/api/v1/account-packages/export", json={
            "organization_code": "520100", "admin_username": "u", "admin_full_name": "u",
            "target_machine_code": "MC-API-123", "package_password": "short",
        })
        assert r.status_code == 422
        # 组织不存在
        r = client.post("/api/v1/account-packages/export", json={
            "organization_code": "520100", "admin_username": "u", "admin_full_name": "u",
            "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
        })
        assert r.status_code == 404
        assert client.get("/api/v1/account-packages/not-a-uuid/download").status_code == 400
        assert client.get("/api/v1/account-packages/11111111-1111-1111-1111-111111111111/download").status_code == 404
        assert client.post("/api/v1/account-packages/11111111-1111-1111-1111-111111111111/revoke", json={}).status_code == 404
    finally:
        settings.ACCOUNT_PACKAGE_ENABLED = True
        app.dependency_overrides.clear()


def test_admin_list_and_preview_errors(client, api_env, monkeypatch):
    db = _db(); org = _org(db)
    admin = SimpleNamespace(id=2, username="admin", role="admin", is_superuser=False, organization_id=org.id)
    _use_db(db, admin)
    try:
        listed = client.get("/api/v1/account-packages")
        assert listed.status_code == 200
        assert client.get("/api/v1/account-packages/receipts").status_code == 200
    finally:
        app.dependency_overrides.clear()

    # 非回环匿名预览
    monkeypatch.setattr("app.api.v1.account_package._client_is_loopback", lambda request: False)
    files = {"file": ("pkg.apkg", b"bad", "application/octet-stream")}
    assert client.post("/api/v1/account-packages/preview", files=files, data={"password": "x"}).status_code == 403

    # 超过大小上限
    monkeypatch.setattr("app.api.v1.account_package._client_is_loopback", lambda request: True)
    monkeypatch.setattr("app.api.v1.account_package.MAX_PACKAGE_BYTES", 1)
    assert client.post("/api/v1/account-packages/preview", files=files, data={"password": "x"}).status_code == 413

def test_authorization_catalog_and_can_issue_routes(client, api_env):
    db = _db()
    root = _org(db)
    admin = SimpleNamespace(id=1, username="root", role="admin", is_superuser=True, organization_id=root.id)
    _use_db(db, admin)
    try:
        catalog = client.get("/api/v1/account-packages/authorization-catalog")
        assert catalog.status_code == 200, catalog.text
        data = catalog.json()["data"]
        assert len(data["pages"]) == 54
        assert len(data["modules"]) == 32
        assert data["catalog_version"]

        status = client.get("/api/v1/account-packages/can-issue")
        assert status.status_code == 200, status.text
        info = status.json()["data"]
        assert info["can_issue"] is True
        assert info["enabled"] is True
        assert info["signing_key_configured"] is True

        non_super = SimpleNamespace(id=3, username="admin2", role="admin", is_superuser=False, organization_id=root.id)
        app.dependency_overrides[get_current_user] = lambda: non_super
        blocked = client.get("/api/v1/account-packages/can-issue")
        assert blocked.status_code == 200, blocked.text
        assert blocked.json()["data"]["can_issue"] is False
        assert blocked.json()["data"]["reason_code"] == "AP_FORBIDDEN"
    finally:
        app.dependency_overrides.clear()


def test_export_audit_records_authorization_summary(client, api_env, monkeypatch):
    db = _db()
    root = _org(db)
    _org(db, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(db, admin)
    captured = []
    monkeypatch.setattr(AuditLogger, "log", staticmethod(lambda **kwargs: captured.append(kwargs)))
    try:
        body = {
            "organization_code": "520100", "organization_name": "市局", "parent_code": "520000",
            "admin_username": "audit_admin", "admin_full_name": "管理员",
            "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
            "grants": {"projects": "edit"},
        }
        response = client.post("/api/v1/account-packages/export", json=body)
        assert response.status_code == 200, response.text
    finally:
        app.dependency_overrides.clear()
    details = captured[-1]["details"]
    assert details["target_org"] == "520100"
    assert details["target_machine_code"] == "MC-API-123"
    assert details["account_count"] == 1
    assert details["page_count"] == 1
    assert details["edit_page_count"] == 1
    assert details["module_count"] == 1
    assert len(details["digest"]) == 64


def test_can_issue_reports_disabled_and_missing_key(client, api_env, monkeypatch):
    db = _db()
    root = _org(db)
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(db, admin)
    try:
        monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", False)
        disabled = client.get("/api/v1/account-packages/can-issue").json()["data"]
        assert disabled["can_issue"] is False
        assert disabled["reason_code"] == "AP_DISABLED"

        monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", True)
        monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", "")
        missing = client.get("/api/v1/account-packages/can-issue").json()["data"]
        assert missing["can_issue"] is False
        assert missing["reason_code"] == "AP_SIGNING_MISSING"
    finally:
        app.dependency_overrides.clear()

def test_export_authorization_error_maps_to_400(client, api_env):
    source = _db()
    root = _org(source)
    _org(source, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(source, admin)
    try:
        r = client.post("/api/v1/account-packages/export", json={
            "organization_code": "520100", "organization_name": "市局", "parent_code": "520000",
            "admin_username": "api_admin", "admin_full_name": "管理员",
            "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
            "grants": {"not-a-page": "view"},
        })
        assert r.status_code == 400, r.text
        assert r.json()["detail"]["code"] == "AP_GRANT_INVALID"
    finally:
        app.dependency_overrides.clear()
