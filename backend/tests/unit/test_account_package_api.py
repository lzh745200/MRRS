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
        "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass", "grants": {},
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
