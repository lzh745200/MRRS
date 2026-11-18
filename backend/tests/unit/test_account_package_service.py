"""账号开通包 P1-b 服务闭环：导出 → 预览 → 确认 → 回执唯一。"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.account_package import AccountPackageError
from app.core.config import settings
from app.core.grant_signing import generate_keypair
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User
from app.services.account_package_service import (
    AccountPackageBusinessError,
    AccountPackageService,
)


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _org(db, code="520000", name="黔南", parent=None, level="1"):
    org = Organization(code=code, name=name, parent_id=getattr(parent, "id", None), level=level, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def env(tmp_path, monkeypatch):
    priv, pub = generate_keypair()
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", True)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", priv)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_PUBKEY", pub)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_KDF_ITERATIONS", 310_000)
    monkeypatch.setattr(AccountPackageService, "package_dir", classmethod(lambda cls: tmp_path))
    return priv, pub


def test_export_preview_confirm_and_receipt_unique(env, tmp_path):
    source = _db()
    issuer_org = _org(source, "520000")
    _org(source, "520100", "贵阳", issuer_org, "2")
    issuer = SimpleNamespace(id=1, username="root", organization_id=issuer_org.id)
    service = AccountPackageService(source)
    out = service.export_package(
        package_id="11111111-1111-1111-1111-111111111111",
        organization_code="520100",
        organization_name="贵阳市局",
        parent_code="520000",
        admin_username="gy_admin",
        admin_full_name="贵阳管理员",
        target_machine_code="mc-1",
        grants={"projects": "edit"},
        password="passw0rd-pass",
        issued_by=issuer,
    )
    assert out["one_time_password"]
    raw = (tmp_path / out["file_name"]).read_bytes()

    target = _db()
    _org(target, "520000")
    target_service = AccountPackageService(target)
    preview = target_service.preview(raw, password="passw0rd-pass", machine_code="MC-1")
    assert preview["organization_exists"] is False
    assert "credential_hash" not in preview["admin"]

    result = target_service.confirm(raw, password="passw0rd-pass", machine_code="mc-1")
    assert result["users"][0]["username"] == "gy_admin"
    created = target.query(User).filter(User.username == "gy_admin").first()
    assert created.must_change_password is True
    assert created.credential_expires_at is not None
    assert created.organization_id == result["organization_id"]
    assert target.query(Organization).filter(Organization.code == "520100").first() is not None

    with pytest.raises(AccountPackageBusinessError) as exc:
        target_service.confirm(raw, password="passw0rd-pass", machine_code="mc-1")
    assert exc.value.code == "AP_ALREADY_IMPORTED"


def test_preview_rejects_wrong_machine(env, tmp_path):
    source = _db()
    root = _org(source)
    _org(source, "520100", "贵阳", root, "2")
    service = AccountPackageService(source)
    out = service.export_package(
        package_id="22222222-2222-2222-2222-222222222222",
        organization_code="520100",
        organization_name="贵阳市局",
        parent_code="520000",
        admin_username="gy_admin2",
        admin_full_name="贵阳管理员",
        target_machine_code="MC-2",
        grants={},
        password="passw0rd-pass",
        issued_by=SimpleNamespace(id=1, organization_id=root.id),
    )
    raw = (tmp_path / out["file_name"]).read_bytes()
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(_db()).preview(raw, password="passw0rd-pass", machine_code="OTHER")
    assert exc.value.code == "AP_MACHINE_MISMATCH"


def test_export_closed_switch_and_weak_password(env):
    service = AccountPackageService(_db())
    issuer = SimpleNamespace(id=1, organization_id=None)
    with pytest.raises(AccountPackageBusinessError):
        service.export_package(
            package_id="33333333-3333-3333-3333-333333333333",
            organization_code="520100", organization_name="x", parent_code="",
            admin_username="u", admin_full_name="u", target_machine_code="m",
            grants={}, password="short", issued_by=issuer,
        )


def test_multi_account_package_creates_all_users(env, tmp_path):
    source = _db()
    root = _org(source)
    _org(source, "520100", "贵阳", root, "2")
    out = AccountPackageService(source).export_package(
        package_id="44444444-4444-4444-4444-444444444444",
        organization_code="520100", organization_name="贵阳市局", parent_code="520000",
        admin_username="", admin_full_name="", target_machine_code="MC-3",
        grants={"projects": "view"}, password="passw0rd-pass",
        issued_by=SimpleNamespace(id=1, organization_id=root.id),
        accounts=[
            {"username": "gy_admin", "full_name": "管理员", "role": "admin", "data_scope": "org"},
            {"username": "gy_user", "full_name": "用户", "role": "user", "data_scope": "self"},
        ],
    )
    assert len(out["accounts"]) == 2
    assert len({a["one_time_password"] for a in out["accounts"]}) == 2
    raw = (tmp_path / out["file_name"]).read_bytes()
    target = _db()
    _org(target, "520000")
    result = AccountPackageService(target).confirm(raw, password="passw0rd-pass", machine_code="mc-3")
    assert [u["username"] for u in result["users"]] == ["gy_admin", "gy_user"]
    assert target.query(User).filter(User.username == "gy_user").first().data_scope == "self"


def test_export_validation_branches(env):
    service = AccountPackageService(_db())
    issuer = SimpleNamespace(id=1, organization_id=None)
    base = dict(
        package_id="66666666-6666-6666-6666-666666666666",
        organization_code="520100", organization_name="x", parent_code="",
        admin_username="u", admin_full_name="u", target_machine_code="MC-API-123",
        grants={}, password="passw0rd-pass", issued_by=issuer,
    )
    settings.ACCOUNT_PACKAGE_SIGNING_KEY = ""
    with pytest.raises(AccountPackageBusinessError):
        service.export_package(**base)
    settings.ACCOUNT_PACKAGE_SIGNING_KEY = env[0]
    with pytest.raises(AccountPackageBusinessError):
        service.export_package(**{**base, "password": "letters-only-pass"})
    with pytest.raises(AccountPackageBusinessError):
        service.export_package(**{**base, "password": "123456789012"})
    db = _db(); root = _org(db)
    db.add(User(username="exists", hashed_password="x")); db.commit()
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(db).export_package(**{**base, "accounts": [{"username": "exists"}]})
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(db).export_package(**{**base, "accounts": [{"username": "u", "role": "god"}]})
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(db).export_package(**{**base, "accounts": [{"username": ""}]})


def test_confirm_conflicts_and_api_helpers(env, monkeypatch):
    from app.api.v1 import account_package as api

    assert api._fail(AccountPackageBusinessError("x", code="AP_X", status=400)).code == "AP_X"
    assert api._fail(AccountPackageError("bad", code="ACCOUNT_PACKAGE_BAD_SIGNATURE")).status == 403
    assert api._fail(RuntimeError("boom")).code == "AP_ROLLBACK"
    with pytest.raises(Exception):
        api._raise_http_error(AccountPackageBusinessError("x", code="AP_X", status=400))

    # 管理员已认证分支 + 二次确认分支
    user = SimpleNamespace(id=1, role="admin", is_superuser=False)
    monkeypatch.setattr(api, "require_admin", lambda u: None)
    monkeypatch.setattr("app.api.v1.deps.verify_confirm_password_value", lambda *a, **k: None)
    api._assert_import_principal(SimpleNamespace(), user, _db(), "pw", require_confirm=True)
    # 初始化机器匿名分支
    db = _db(); db.add(User(username="a", hashed_password="x")); db.commit()
    monkeypatch.setattr(api, "is_pristine_first_run", lambda d: False)
    with pytest.raises(Exception):
        api._assert_import_principal(SimpleNamespace(), None, db, "", require_confirm=False)
