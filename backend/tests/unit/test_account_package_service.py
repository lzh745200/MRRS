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
from app.models.org_grant import OrgGrant
from app.models.user import User
from app.services.account_package_service import (
    AccountPackageBusinessError,
    AccountPackageService,
    _normalize_menu_selection,
    _validated_accounts,
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
    assert out["authorization"]["page_count"] == 1
    assert out["authorization"]["edit_page_count"] == 1
    raw = (tmp_path / out["file_name"]).read_bytes()

    target = _db()
    _org(target, "520000")
    target_service = AccountPackageService(target)
    preview = target_service.preview(raw, password="passw0rd-pass", machine_code="MC-1")
    assert preview["organization_exists"] is False
    assert "credential_hash" not in preview["admin"]
    assert preview["authorization"]["page_count"] == 1
    assert preview["authorization"]["edit_page_count"] == 1
    assert preview["authorization"]["module_count"] == 1

    result = target_service.confirm(raw, password="passw0rd-pass", machine_code="mc-1")
    assert result["authorization"]["page_count"] == 1
    assert result["users"][0]["username"] == "gy_admin"
    created = target.query(User).filter(User.username == "gy_admin").first()
    assert created.must_change_password is True
    assert created.credential_expires_at is not None
    assert created.organization_id == result["organization_id"]
    assert created.allowed_permissions_list == []
    org = target.query(Organization).filter(Organization.code == "520100").first()
    assert org is not None
    assert org.grant_version == 1
    grants = target.query(OrgGrant).filter(OrgGrant.organization_id == org.id).all()
    assert {(grant.module_key, grant.level) for grant in grants} == {("projects", "edit")}

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
        grants={"projects": "view"},
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
    _org(db, "520100", "市局", root, "2")
    db.add(User(username="exists", hashed_password="x")); db.commit()
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(db).export_package(**{**base, "accounts": [{"username": "exists"}]})
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(db).export_package(**{**base, "accounts": [{"username": "u", "role": "god"}]})
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(db).export_package(**{**base, "accounts": [{"username": ""}]})
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).export_package(**{**base, "grants": {"x": "bad"}})
    assert exc.value.code == "AP_GRANT_INVALID"

    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).export_package(**{**base, "grants": {"unknown-page": "view"}})
    assert exc.value.code == "AP_GRANT_INVALID"

    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).export_package(**{**base, "grants": {}})
    assert exc.value.code == "AP_GRANT_EMPTY"

    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).export_package(**{**base, "grants": {"dashboard": "edit"}})
    assert exc.value.code == "AP_GRANT_INVALID"


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
    api._assert_import_principal(SimpleNamespace(), user, _db(), "", require_confirm=False)
    # 初始化机器匿名分支
    db = _db(); db.add(User(username="a", hashed_password="x")); db.commit()
    monkeypatch.setattr(api, "_client_is_loopback", lambda r: True)
    monkeypatch.setattr(api, "is_pristine_first_run", lambda d: False)
    with pytest.raises(Exception):
        api._assert_import_principal(SimpleNamespace(), None, db, "", require_confirm=False)


def _raw_package(env, package_id, *, parent_code="520000", org_name="市局", credential_hash=None):
    from app.core.account_package import build_manifest, seal_package

    priv = env[0]
    manifest = build_manifest(
        package_id=package_id, organization_code="520100", organization_name=org_name,
        parent_code=parent_code, target_machine_code="MC-API-123",
        items=[{"username": "xuser", "full_name": "X", "credential_hash": credential_hash or "$2b$12$" + "a" * 53,
                "role": "admin", "data_scope": "org"}],
    )
    return seal_package(manifest, password="passw0rd-pass", private_key_hex=priv, iterations=310_000)


def test_package_dir_real(monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setattr(
        "app.services.account_package_service.get_runtime_uploads_path",
        lambda sub: Path(tmp_path) / sub,
    )
    assert AccountPackageService.package_dir().name == "account_packages"


def test_more_confirm_conflicts(env):
    pid = "77777777-7777-7777-7777-777777777777"
    target = _db()
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(target).confirm(_raw_package(env, pid), password="passw0rd-pass", machine_code="OTHER")
    assert exc.value.code == "AP_MACHINE_MISMATCH"

    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(target).confirm(_raw_package(env, pid, parent_code="999999"), password="passw0rd-pass", machine_code="MC-API-123")
    assert exc.value.code == "AP_ORG_NOT_FOUND"

    parent = _org(target)
    _org(target, "520100", "市局", parent, "2")
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(target).confirm(_raw_package(env, pid), password="passw0rd-pass", machine_code="MC-API-123")
    assert exc.value.code == "AP_ORG_CONFLICT"

    # 旧版空授权包不得激活矩阵：不写 OrgGrant，grant_version 保持 0。
    legacy_target = _db()
    _org(legacy_target, "520000")
    legacy = AccountPackageService(legacy_target).confirm(
        _raw_package(env, "12121212-1212-1212-1212-121212121212"),
        password="passw0rd-pass",
        machine_code="MC-API-123",
    )
    legacy_org = legacy_target.query(Organization).filter(Organization.code == "520100").first()
    assert legacy["users"][0]["username"] == "xuser"
    assert legacy_org is not None
    assert legacy_org.grant_version == 0
    assert legacy_target.query(OrgGrant).count() == 0

    fresh = _db(); _org(fresh, "520000")
    raw = _raw_package(env, "88888888-8888-8888-8888-888888888888", parent_code="", org_name="")
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(fresh).preview(raw, password="passw0rd-pass", machine_code="MC-API-123")
    assert exc.value.code == "AP_ORG_NOT_FOUND"


def test_invalid_hash_and_commit_rollback(env, monkeypatch):
    target = _db(); _org(target, "520000")
    raw = _raw_package(env, "99999999-9999-9999-9999-999999999999", credential_hash="plaintext")
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(target).confirm(raw, password="passw0rd-pass", machine_code="MC-API-123")
    assert exc.value.code == "AP_USERNAME_TAKEN"

    target2 = _db(); _org(target2, "520000")
    raw2 = _raw_package(env, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    svc = AccountPackageService(target2)
    def boom():
        from sqlalchemy.exc import SQLAlchemyError
        raise SQLAlchemyError("unique")
    monkeypatch.setattr(target2, "commit", boom)
    with pytest.raises(AccountPackageBusinessError) as exc:
        svc.confirm(raw2, password="passw0rd-pass", machine_code="MC-API-123")
    assert exc.value.code == "AP_ALREADY_IMPORTED"


def test_export_without_issuer_org_and_confirm_without_parent(env):
    source = _db(); root = _org(source)
    _org(source, "520100", "市局", root, "2")
    out = AccountPackageService(source).export_package(
        package_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        organization_code="520100", organization_name="市局", parent_code="",
        admin_username="no_org", admin_full_name="无组织签发人",
        target_machine_code="MC-API-123", grants={"projects": "view"}, password="passw0rd-pass",
        issued_by=SimpleNamespace(id=1, organization_id=None),
    )
    raw = (__import__("pathlib").Path(AccountPackageService.package_dir()) / out["file_name"]).read_bytes()
    target = _db()
    result = AccountPackageService(target).confirm(raw, password="passw0rd-pass", machine_code="MC-API-123")
    assert result["users"][0]["username"] == "no_org"
    org = target.query(Organization).filter(Organization.code == "520100").first()
    assert org is not None and org.level == "1"


def test_offline_accounts_carry_password_menus_permissions(env):
    source = _db(); root = _org(source)
    _org(source, "520100", "市局", root, "2")
    out = AccountPackageService(source).export_package(
        package_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        organization_code="520100", organization_name="市局", parent_code="520000",
        admin_username="", admin_full_name="", target_machine_code="MC-API-123",
        grants={"projects": "view"}, password="passw0rd-pass",
        issued_by=SimpleNamespace(id=1, organization_id=root.id),
        accounts=[{
            "username": "restricted", "full_name": "受限用户", "role": "user",
            "data_scope": "self", "initial_password": "CustomPass123",
            "allowed_menus": ["projects"],
            "allowed_permissions": ["project:view", "fund:view"],
        }],
    )
    assert out["accounts"][0]["generated_password"] is False
    raw = (__import__("pathlib").Path(AccountPackageService.package_dir()) / out["file_name"]).read_bytes()
    target = _db(); _org(target, "520000")
    AccountPackageService(target).confirm(raw, password="passw0rd-pass", machine_code="MC-API-123")
    user = target.query(User).filter(User.username == "restricted").first()
    assert user.allowed_menus_list == ["projects"]
    # 设计约束：包内不再携带逐账号权限码，允许矩阵是唯一权限上限。
    assert not user.allowed_permissions_list

    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(source).export_package(
            package_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
            organization_code="520100", organization_name="市局", parent_code="520000",
            admin_username="", admin_full_name="", target_machine_code="MC-API-123",
            grants={"projects": "view"}, password="passw0rd-pass",
            issued_by=SimpleNamespace(id=1, organization_id=root.id),
            accounts=[{"username": "weak", "initial_password": "short"}],
        )


def test_offline_initial_password_requires_letters_and_digits(env):
    source = _db(); root = _org(source)
    _org(source, "520100", "市局", root, "2")
    with pytest.raises(AccountPackageBusinessError):
        AccountPackageService(source).export_package(
            package_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            organization_code="520100", organization_name="市局", parent_code="520000",
            admin_username="", admin_full_name="", target_machine_code="MC-API-123",
            grants={"projects": "view"}, password="passw0rd-pass",
            issued_by=SimpleNamespace(id=1, organization_id=root.id),
            accounts=[{"username": "digits", "initial_password": "123456789012"}],
        )

def test_export_account_validation_errors(env):
    source = _db(); root = _org(source)
    _org(source, "520100", "市局", root, "2")
    source.add(User(username="existing_user", hashed_password="x", role="user", data_scope="org"))
    source.commit()
    svc = AccountPackageService(source)
    issuer = SimpleNamespace(id=1, organization_id=root.id)

    def _export(accounts):
        return svc.export_package(
            package_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            organization_code="520100", organization_name="市局", parent_code="520000",
            admin_username="", admin_full_name="", target_machine_code="MC-API-123",
            grants={"projects": "view"}, password="passw0rd-pass", issued_by=issuer,
            accounts=accounts,
        )

    for accounts in (
        [{"username": ""}],
        [{"username": "dup"}, {"username": "dup"}],
        [{"username": "existing_user"}],
        [{"username": "bad_role", "role": "super_admin"}],
        [{"username": "bad_scope", "data_scope": "all"}],
        [{"username": "weak_short", "initial_password": "short"}],
        [{"username": "weak_digits", "initial_password": "123456789012"}],
        [{"username": "bad_menu", "allowed_menus": ["not-a-menu"]}],
    ):
        with pytest.raises(AccountPackageBusinessError):
            _export(accounts)


def test_normalize_menu_selection_and_validated_accounts_errors():
    with pytest.raises(AccountPackageBusinessError) as exc:
        _normalize_menu_selection(["not-a-menu"], {"projects": "view"})
    assert exc.value.code == "AP_MENU_NOT_ALLOWED"

    for manifest in (
        {"items": []},
        {"items": "bad"},
        {"items": [None]},
        {"items": [{"username": ""}]},
        {"items": [{"username": "u", "role": "super_admin"}]},
        {"items": [{"username": "u", "data_scope": "all"}]},
        {"items": [{"username": "u", "allowed_menus": ["not-a-menu"]}]},
    ):
        with pytest.raises(AccountPackageBusinessError):
            _validated_accounts(manifest, {"projects": "view"})


def test_cross_machine_import_requires_and_persists_signer_trust(tmp_path, monkeypatch):
    """跨机首次导入：包内公钥只验完整性，必须人工核对指纹后才落信任。"""
    from app.core import account_package_keys

    monkeypatch.setenv("RUNTIME_SECRETS_FILE", str(tmp_path / "target-runtime-secrets.json"))
    priv, _pub = generate_keypair()
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", True)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", priv)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_PUBKEY", "")
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_KDF_ITERATIONS", 310_000)
    monkeypatch.setattr(AccountPackageService, "package_dir", classmethod(lambda cls: tmp_path))

    source = _db()
    root = _org(source)
    _org(source, "520100", "贵阳", root, "2")
    out = AccountPackageService(source).export_package(
        package_id="77777777-7777-7777-7777-777777777777",
        organization_code="520100", organization_name="贵阳市局", parent_code="520000",
        admin_username="gy_cross", admin_full_name="跨机管理员",
        target_machine_code="MC-CROSS", grants={"projects": "view"},
        password="passw0rd-pass", issued_by=SimpleNamespace(id=1, organization_id=root.id),
    )
    fingerprint = out["signer_fingerprint"]
    assert fingerprint
    raw = (tmp_path / out["file_name"]).read_bytes()

    # 目标机：没有预置公钥、没有本机密钥，签发包来源应显示"未信任"。
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", "")
    target = _db()
    _org(target, "520000")
    service = AccountPackageService(target)
    preview = service.preview(raw, password="passw0rd-pass", machine_code="MC-CROSS")
    assert preview["signer_fingerprint"] == fingerprint
    assert preview["signer_trusted"] is False
    assert preview["trust_required"] is True

    with pytest.raises(AccountPackageBusinessError) as exc:
        service.confirm(raw, password="passw0rd-pass", machine_code="MC-CROSS")
    assert exc.value.code == "AP_SIGNING_UNTRUSTED"

    with pytest.raises(AccountPackageBusinessError) as exc:
        service.confirm(
            raw, password="passw0rd-pass", machine_code="MC-CROSS",
            confirmed_fingerprint="0000-0000-0000-0000-0000-0000-0000-0000",
        )
    assert exc.value.code == "AP_SIGNING_UNTRUSTED"

    result = service.confirm(
        raw, password="passw0rd-pass", machine_code="MC-CROSS",
        confirmed_fingerprint=fingerprint,
    )
    assert result["signer_trusted"] is True
    assert [item["fingerprint"] for item in account_package_keys.trusted_key_info()] == [fingerprint]

    # 信任已持久化：再次导入同一包应直接走到回执唯一校验，而不是再次要求指纹。
    with pytest.raises(AccountPackageBusinessError) as exc:
        service.confirm(raw, password="passw0rd-pass", machine_code="MC-CROSS")
    assert exc.value.code == "AP_ALREADY_IMPORTED"


def _strip_embedded_signer(raw: bytes, private_hex: str) -> bytes:
    """构造 v1.18.66 之前的旧包：包头没有 signer_public_key，仍由同一私钥签名。"""
    import json
    import struct

    from app.core.account_package import PACKAGE_MAGIC
    from app.core.grant_signing import sign_payload

    magic_len = len(PACKAGE_MAGIC)
    header_len = struct.unpack(">I", raw[magic_len:magic_len + 4])[0]
    header = json.loads(raw[magic_len + 4:magic_len + 4 + header_len])
    header.pop("signer_public_key", None)
    header["signature"] = sign_payload(header, private_hex)
    payload = json.dumps(header, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return PACKAGE_MAGIC + struct.pack(">I", len(payload)) + payload + raw[magic_len + 4 + header_len:]


def test_legacy_package_preview_uses_pretrusted_public_key(env, tmp_path):
    """旧包没有内嵌公钥时，只能靠本机预置公钥验签，预览应标记来源可信。"""
    priv, _pub = env
    source = _db()
    root = _org(source)
    _org(source, "520100", "贵阳", root, "2")
    out = AccountPackageService(source).export_package(
        package_id="88888888-8888-8888-8888-888888888888",
        organization_code="520100", organization_name="贵阳市局", parent_code="520000",
        admin_username="legacy_admin", admin_full_name="旧包管理员",
        target_machine_code="MC-LEGACY", grants={"projects": "view"},
        password="passw0rd-pass", issued_by=SimpleNamespace(id=1, organization_id=root.id),
    )
    raw = _strip_embedded_signer((tmp_path / out["file_name"]).read_bytes(), priv)

    target = _db()
    _org(target, "520000")
    preview = AccountPackageService(target).preview(raw, password="passw0rd-pass", machine_code="MC-LEGACY")
    assert preview["signer_fingerprint"] == ""
    assert preview["signer_trusted"] is True


def test_persist_signer_trust_failure_is_non_fatal(monkeypatch):
    from app.core import account_package_keys
    from app.services.account_package_service import _persist_signer_trust

    def _fail(_public_key):
        raise account_package_keys.AccountPackageKeyError("disk full")

    monkeypatch.setattr(account_package_keys, "add_trusted_public_key", _fail)
    assert _persist_signer_trust("ab" * 32, False) is False


@pytest.mark.parametrize("mode", ["raise", "empty"])
def test_export_reports_unavailable_signing_key(env, monkeypatch, mode):
    from app.core import account_package_keys

    def _boom(*_args, **_kwargs):
        raise account_package_keys.AccountPackageKeyError("secrets dir unwritable")

    monkeypatch.setattr(
        account_package_keys,
        "local_private_key",
        _boom if mode == "raise" else (lambda **_kwargs: ""),
    )
    db = _db()
    root = _org(db)
    _org(db, "520100", "贵阳", root, "2")
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).export_package(
            package_id="99999999-9999-9999-9999-999999999999",
            organization_code="520100", organization_name="贵阳市局", parent_code="520000",
            admin_username="nokey_admin", admin_full_name="无密钥管理员",
            target_machine_code="MC-NOKEY", grants={"projects": "view"},
            password="passw0rd-pass", issued_by=SimpleNamespace(id=1, organization_id=root.id),
        )
    assert exc.value.code == "AP_SIGNING_MISSING"
    assert exc.value.status == 403
