"""账号开通包 P4 限流：失败锁定 + 重试速率闸门（消费 ACCOUNT_PACKAGE_MAX_ATTEMPTS）。

覆盖三层：台账方法本身、API 接线（导出/预览/确认）、以及“闸门错误不再计数”的防自锁。
"""
from datetime import timedelta
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
from app.models.account_package import AccountPackageAttempt
from app.models.base import Base
from app.models.organization import Organization
from app.services.account_package_service import (
    AccountPackageBusinessError,
    AccountPackageService,
)
from app.services.machine_code_service import MachineCodeService
from app.utils.time_utils import utcnow


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _org(db, code="520000", name="州局", parent=None, level="1"):
    org = Organization(code=code, name=name, parent_id=getattr(parent, "id", None), level=level, is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    return org


@pytest.fixture
def limits(monkeypatch):
    """默认关闭速率闸门，便于单独验证锁定；速率用例自行打开。"""
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_LOCKOUT_MINUTES", 15)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ATTEMPT_INTERVAL_SECONDS", 0.0)


@pytest.fixture
def api_env(tmp_path, monkeypatch, limits):
    priv, pub = generate_keypair()
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", True)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", priv)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_PUBKEY", pub)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_KDF_ITERATIONS", 310_000)
    monkeypatch.setattr(AccountPackageService, "package_dir", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(MachineCodeService, "get_machine_code", staticmethod(lambda: "MC-API-123"))
    monkeypatch.setattr("app.api.v1.account_package._client_is_loopback", lambda request: True)
    return tmp_path


def _use_db(db, user=None):
    app.dependency_overrides[get_db] = lambda: db
    if user is None:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = lambda: user


# ---------- 台账方法 ----------

def test_subject_normalizes_and_scopes_are_separate(limits):
    assert AccountPackageService.attempt_subject("export", 7) == "export:7"
    assert AccountPackageService.attempt_subject("import", " mc-1 ") == "import:MC-1"
    svc = AccountPackageService(_db())
    svc.record_attempt_failure("export:7", "AP_X")
    svc.check_attempt_allowed("import:MC-1")  # 另一作用域不受影响


def test_unknown_subject_passes_without_creating_row(limits):
    db = _db()
    AccountPackageService(db).check_attempt_allowed("import:NEW")
    assert db.query(AccountPackageAttempt).count() == 0


def test_lockout_triggers_at_threshold_and_blocks(limits):
    db = _db()
    svc = AccountPackageService(db)
    for _ in range(3):
        svc.record_attempt_failure("import:MC-1", "AP_BAD_PASSWORD")
    row = db.query(AccountPackageAttempt).filter_by(subject_key="import:MC-1").one()
    assert row.fail_count == 3 and row.locked_until is not None
    assert row.last_error == "AP_BAD_PASSWORD"
    with pytest.raises(AccountPackageBusinessError) as exc:
        svc.check_attempt_allowed("import:MC-1")
    assert exc.value.code == "AP_ATTEMPTS_EXCEEDED" and exc.value.status == 429


def test_expired_lock_resets_window(limits):
    db = _db()
    svc = AccountPackageService(db)
    past = utcnow() - timedelta(minutes=30)
    for _ in range(3):
        svc.record_attempt_failure("import:MC-1", "AP_X", now=past)
    svc.check_attempt_allowed("import:MC-1")
    row = db.query(AccountPackageAttempt).filter_by(subject_key="import:MC-1").one()
    assert row.fail_count == 0 and row.locked_until is None and row.last_attempt_at is None


def test_success_clears_window(limits):
    db = _db()
    svc = AccountPackageService(db)
    svc.record_attempt_failure("import:MC-1", "AP_X")
    svc.record_attempt_success("import:MC-1")
    row = db.query(AccountPackageAttempt).filter_by(subject_key="import:MC-1").one()
    assert (row.fail_count, row.locked_until, row.last_error, row.last_attempt_at) == (0, None, None, None)
    svc.record_attempt_success("import:ABSENT")  # 无行时静默返回


def test_rate_gate_only_after_failure(monkeypatch, limits):
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ATTEMPT_INTERVAL_SECONDS", 60.0)
    db = _db()
    svc = AccountPackageService(db)
    svc.check_attempt_allowed("import:MC-1")  # 从未失败 → 放行
    svc.record_attempt_failure("import:MC-1", "AP_X")
    with pytest.raises(AccountPackageBusinessError) as exc:
        svc.check_attempt_allowed("import:MC-1")
    assert exc.value.code == "AP_RATE_LIMITED" and exc.value.status == 429
    svc.check_attempt_allowed("import:MC-1", now=utcnow() + timedelta(seconds=61))


def test_zero_max_attempts_disables_lockout(monkeypatch, limits):
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_MAX_ATTEMPTS", 0)
    db = _db()
    svc = AccountPackageService(db)
    for _ in range(10):
        svc.record_attempt_failure("import:MC-1", "AP_X")
    row = db.query(AccountPackageAttempt).filter_by(subject_key="import:MC-1").one()
    assert row.fail_count == 10 and row.locked_until is None
    svc.check_attempt_allowed("import:MC-1")


def test_long_error_code_is_truncated(limits):
    db = _db()
    AccountPackageService(db).record_attempt_failure("import:MC-1", "X" * 200)
    row = db.query(AccountPackageAttempt).filter_by(subject_key="import:MC-1").one()
    assert len(row.last_error) == 64


# ---------- API 接线 ----------

def _export_body(**over):
    body = {
        "organization_code": "520100", "organization_name": "市局", "parent_code": "520000",
        "admin_username": "u1", "admin_full_name": "用户",
        "target_machine_code": "MC-API-123", "package_password": "passw0rd-pass",
        "grants": {"projects": "view"},
    }
    body.update(over)
    return body


def test_export_failures_lock_the_issuer(client, api_env):
    db = _db(); root = _org(db)
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(db, admin)
    try:
        for _ in range(3):
            r = client.post("/api/v1/account-packages/export", json=_export_body())
            assert r.status_code == 404 and r.json()["detail"]["code"] == "AP_ORG_NOT_FOUND"
        locked = client.post("/api/v1/account-packages/export", json=_export_body())
        assert locked.status_code == 429
        assert locked.json()["detail"]["code"] == "AP_ATTEMPTS_EXCEEDED"
        row = db.query(AccountPackageAttempt).filter_by(subject_key="export:1").one()
        assert row.fail_count == 3  # 闸门拒绝本身不再计数
    finally:
        app.dependency_overrides.clear()


def test_export_success_resets_counter(client, api_env):
    db = _db(); root = _org(db)
    _org(db, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(db, admin)
    try:
        svc = AccountPackageService(db)
        svc.record_attempt_failure("export:1", "AP_ORG_NOT_FOUND")
        ok = client.post("/api/v1/account-packages/export", json=_export_body(admin_username="ok_user"))
        assert ok.status_code == 200, ok.text
        row = db.query(AccountPackageAttempt).filter_by(subject_key="export:1").one()
        assert row.fail_count == 0 and row.last_attempt_at is None
    finally:
        app.dependency_overrides.clear()


def test_import_wrong_password_locks_the_machine(client, api_env):
    source = _db(); root = _org(source)
    _org(source, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(source, admin)
    r = client.post("/api/v1/account-packages/export", json=_export_body(admin_username="imp_user"))
    assert r.status_code == 200, r.text
    raw = (api_env / f"account-package-{r.json()['data']['package_id']}.apkg").read_bytes()

    target = _db(); _org(target, "520000")
    _use_db(target)
    try:
        for _ in range(3):
            files = {"file": ("pkg.apkg", raw, "application/octet-stream")}
            bad = client.post("/api/v1/account-packages/preview", files=files, data={"password": "wrong-pass-123"})
            assert bad.status_code == 400, bad.text
        files = {"file": ("pkg.apkg", raw, "application/octet-stream")}
        blocked = client.post("/api/v1/account-packages/confirm", files=files, data={"password": "passw0rd-pass"})
        assert blocked.status_code == 429
        assert blocked.json()["detail"]["code"] == "AP_ATTEMPTS_EXCEEDED"
        row = target.query(AccountPackageAttempt).filter_by(subject_key="import:MC-API-123").one()
        assert row.fail_count == 3
        assert target.query(Organization).filter(Organization.code == "520100").first() is None
    finally:
        app.dependency_overrides.clear()


def test_import_rate_limit_returns_429(client, api_env, monkeypatch):
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ATTEMPT_INTERVAL_SECONDS", 60.0)
    target = _db(); _org(target, "520000")
    _use_db(target)
    try:
        files = {"file": ("pkg.apkg", b"not-a-package", "application/octet-stream")}
        first = client.post("/api/v1/account-packages/preview", files=files, data={"password": "passw0rd-pass"})
        assert first.status_code == 400, first.text
        files = {"file": ("pkg.apkg", b"not-a-package", "application/octet-stream")}
        second = client.post("/api/v1/account-packages/preview", files=files, data={"password": "passw0rd-pass"})
        assert second.status_code == 429
        assert second.json()["detail"]["code"] == "AP_RATE_LIMITED"
    finally:
        app.dependency_overrides.clear()


def test_confirm_failure_counts_and_success_clears(client, api_env):
    source = _db(); root = _org(source)
    _org(source, "520100", "市局", root, "2")
    admin = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True, organization_id=root.id)
    _use_db(source, admin)
    r = client.post("/api/v1/account-packages/export", json=_export_body(admin_username="cf_user"))
    assert r.status_code == 200, r.text
    raw = (api_env / f"account-package-{r.json()['data']['package_id']}.apkg").read_bytes()

    # 目标机已有同码组织 → confirm 冲突计一次失败
    target = _db(); parent = _org(target, "520000")
    _org(target, "520100", "已存在市局", parent, "2")
    _use_db(target)
    try:
        files = {"file": ("pkg.apkg", raw, "application/octet-stream")}
        conflict = client.post("/api/v1/account-packages/confirm", files=files, data={"password": "passw0rd-pass"})
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "AP_ORG_CONFLICT"
        row = target.query(AccountPackageAttempt).filter_by(subject_key="import:MC-API-123").one()
        assert row.fail_count == 1
    finally:
        app.dependency_overrides.clear()

    fresh = _db(); _org(fresh, "520000")
    AccountPackageService(fresh).record_attempt_failure("import:MC-API-123", "AP_ORG_CONFLICT")
    _use_db(fresh)
    try:
        files = {"file": ("pkg.apkg", raw, "application/octet-stream")}
        ok = client.post("/api/v1/account-packages/confirm", files=files, data={"password": "passw0rd-pass"})
        assert ok.status_code == 200, ok.text
        row = fresh.query(AccountPackageAttempt).filter_by(subject_key="import:MC-API-123").one()
        assert row.fail_count == 0 and row.locked_until is None
    finally:
        app.dependency_overrides.clear()


def test_prerequisite_rejection_does_not_count(client, api_env, monkeypatch):
    target = _db()
    from app.models.user import User
    target.add(User(username="seeded", hashed_password="x")); target.commit()
    _use_db(target)
    monkeypatch.setattr("app.api.v1.account_package.is_pristine_first_run", lambda d: False)
    try:
        files = {"file": ("pkg.apkg", b"x", "application/octet-stream")}
        denied = client.post("/api/v1/account-packages/preview", files=files, data={"password": "passw0rd-pass"})
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "AP_PREREQUISITE"
        assert target.query(AccountPackageAttempt).count() == 0
    finally:
        app.dependency_overrides.clear()
