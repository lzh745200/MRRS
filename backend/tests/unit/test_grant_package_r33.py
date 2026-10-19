# -*- coding: utf-8 -*-
"""R33：授权包签名（Ed25519）与构建/解析/应用。

覆盖点：
- 签名往返、篡改即失败、密钥格式非法；
- 规范化字节排除 `signature` 字段（否则签完再填签名会自相矛盾）；
- 包结构校验的每一条拒绝分支（格式/版本/必填/级别/org_code/version）；
- 应用时的六道校验：验签、未签名、无公钥、单位不匹配、单位不存在、拒绝降级；
- 成功应用后：矩阵被**替换**（不是叠加）、版本号递增、元信息落库、缓存失效。
"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import grant_signing as gs
from app.core.grant_signing import (
    GrantSigningError,
    canonical_bytes,
    generate_keypair,
    sign_payload,
    verify_payload,
)
from app.models.base import Base
from app.models.org_grant import OrgGrant
from app.models.organization import Organization
from app.services import effective_grant_service as egs
from app.services.grant_package_service import (
    PACKAGE_FORMAT,
    PACKAGE_FORMAT_VERSION,
    GrantPackageError,
    apply_package,
    build_package,
    export_package_bytes,
    parse_package,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Organization.__table__, OrgGrant.__table__])
    session = sessionmaker(bind=engine)()
    egs.clear_cache()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        egs.clear_cache()


@pytest.fixture
def keys():
    return generate_keypair()


def _org(db, code="C001", name="某某县民政局", version=0):
    org = Organization(name=name, code=code, grant_version=version)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


class TestSigning:
    def test_roundtrip(self, keys):
        private_hex, public_hex = keys
        payload = {"a": 1, "b": "中文"}
        sig = sign_payload(payload, private_hex)
        assert verify_payload(payload, sig, public_hex) is True

    def test_tampered_payload_fails(self, keys):
        private_hex, public_hex = keys
        sig = sign_payload({"a": 1}, private_hex)
        assert verify_payload({"a": 2}, sig, public_hex) is False

    def test_signature_field_excluded_from_canonical_bytes(self):
        base = {"a": 1}
        with_sig = {"a": 1, "signature": "deadbeef"}
        assert canonical_bytes(base) == canonical_bytes(with_sig)

    def test_canonical_bytes_are_key_order_independent(self):
        assert canonical_bytes({"a": 1, "b": 2}) == canonical_bytes({"b": 2, "a": 1})

    def test_empty_private_key_rejected(self):
        with pytest.raises(GrantSigningError):
            sign_payload({"a": 1}, "")

    def test_bad_private_key_format(self):
        with pytest.raises(GrantSigningError):
            sign_payload({"a": 1}, "zzzz")

    def test_bad_public_key_returns_false(self, keys):
        private_hex, _ = keys
        sig = sign_payload({"a": 1}, private_hex)
        assert verify_payload({"a": 1}, sig, "not-hex") is False

    def test_empty_signature_or_key_returns_false(self, keys):
        _, public_hex = keys
        assert verify_payload({"a": 1}, "", public_hex) is False
        assert verify_payload({"a": 1}, "ab", "") is False

    def test_generate_keypair_shape(self):
        private_hex, public_hex = generate_keypair()
        assert len(private_hex) == 64 and len(public_hex) == 64
        assert private_hex != public_hex

    def test_error_class_is_value_error(self):
        assert issubclass(GrantSigningError, ValueError)


class TestBuildPackage:
    def test_minimal_unsigned(self):
        pkg = build_package(org_code="C001", grants={"projects": "edit"}, version=1)
        assert pkg["format"] == PACKAGE_FORMAT
        assert pkg["format_version"] == PACKAGE_FORMAT_VERSION
        assert pkg["grants"] == {"projects": "edit"}
        assert "signature" not in pkg
        assert pkg["issued_at"]

    def test_signed_with_optional_fields(self, keys):
        private_hex, _ = keys
        pkg = build_package(
            org_code="C001",
            grants={"funds": "view"},
            version=2,
            org_name="某某县",
            parent_codes=["S001"],
            issued_at="2026-10-19T00:00:00+00:00",
            private_key=private_hex,
        )
        assert pkg["signature"]
        assert pkg["org_name"] == "某某县"
        assert pkg["parent_codes"] == ["S001"]
        assert pkg["issued_at"] == "2026-10-19T00:00:00+00:00"

    def test_empty_org_code_rejected(self):
        with pytest.raises(GrantPackageError):
            build_package(org_code="", grants={}, version=1)

    def test_bad_version_rejected(self):
        for bad in (0, -1, True, "1"):
            with pytest.raises(GrantPackageError):
                build_package(org_code="C001", grants={}, version=bad)

    def test_grants_must_be_dict(self):
        with pytest.raises(GrantPackageError):
            build_package(org_code="C001", grants=[], version=1)

    def test_empty_module_key_rejected(self):
        with pytest.raises(GrantPackageError):
            build_package(org_code="C001", grants={"": "edit"}, version=1)

    def test_invalid_level_rejected(self):
        with pytest.raises(GrantPackageError):
            build_package(org_code="C001", grants={"projects": "own"}, version=1)


class TestParseAndExport:
    def test_export_then_parse_roundtrip(self):
        pkg = build_package(org_code="C001", grants={"projects": "edit"}, version=1)
        raw = export_package_bytes(pkg)
        assert isinstance(raw, bytes)
        assert parse_package(raw)["org_code"] == "C001"

    def test_parse_accepts_dict_and_str(self):
        pkg = build_package(org_code="C001", grants={}, version=1)
        assert parse_package(pkg)["version"] == 1
        assert parse_package(json.dumps(pkg))["version"] == 1

    def test_invalid_json(self):
        with pytest.raises(GrantPackageError):
            parse_package(b"{not json")

    def test_non_utf8_bytes(self):
        with pytest.raises(GrantPackageError):
            parse_package(b"\xff\xfe\x00")

    def test_root_must_be_object(self):
        with pytest.raises(GrantPackageError):
            parse_package("[1,2,3]")

    def test_missing_field(self):
        pkg = build_package(org_code="C001", grants={}, version=1)
        pkg.pop("org_code")
        with pytest.raises(GrantPackageError):
            parse_package(pkg)

    def test_wrong_format(self):
        pkg = build_package(org_code="C001", grants={}, version=1)
        pkg["format"] = "something-else"
        with pytest.raises(GrantPackageError):
            parse_package(pkg)

    def test_unsupported_format_version(self):
        pkg = build_package(org_code="C001", grants={}, version=1)
        pkg["format_version"] = 99
        with pytest.raises(GrantPackageError):
            parse_package(pkg)

    def test_bad_org_code_type(self):
        pkg = build_package(org_code="C001", grants={}, version=1)
        pkg["org_code"] = 123
        with pytest.raises(GrantPackageError):
            parse_package(pkg)

    def test_bad_version_type(self):
        pkg = build_package(org_code="C001", grants={}, version=1)
        pkg["version"] = 0
        with pytest.raises(GrantPackageError):
            parse_package(pkg)


class TestApplyPackage:
    def _pkg(self, keys, version=1, grants=None, org_code="C001"):
        private_hex, public_hex = keys
        pkg = build_package(
            org_code=org_code,
            grants=grants if grants is not None else {"projects": "edit"},
            version=version,
            private_key=private_hex,
        )
        return pkg, public_hex

    def test_signed_apply_writes_matrix(self, db, keys):
        org = _org(db)
        pkg, public_hex = self._pkg(keys)
        result = apply_package(db, pkg, public_key=public_hex)
        assert result == {"org_code": "C001", "version": 1, "modules": 1, "signed": True}

        db.refresh(org)
        assert org.grant_version == 1
        assert org.grant_source == "import"
        assert org.grant_signature
        assert org.grant_applied_at is not None
        rows = db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).all()
        assert [(r.module_key, r.level) for r in rows] == [("projects", "edit")]

    def test_apply_replaces_not_merges(self, db, keys):
        org = _org(db)
        pkg1, public_hex = self._pkg(keys, version=1, grants={"projects": "edit", "funds": "view"})
        apply_package(db, pkg1, public_key=public_hex)
        pkg2, _ = self._pkg(keys, version=2, grants={"projects": "view"})
        apply_package(db, pkg2, public_key=public_hex)
        rows = db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).all()
        assert [(r.module_key, r.level) for r in rows] == [("projects", "view")]

    def test_downgrade_rejected(self, db, keys):
        _org(db, version=5)
        pkg, public_hex = self._pkg(keys, version=5)
        with pytest.raises(GrantPackageError) as exc:
            apply_package(db, pkg, public_key=public_hex)
        assert "降级" in str(exc.value)

    def test_org_code_mismatch(self, db, keys):
        _org(db)
        pkg, public_hex = self._pkg(keys)
        with pytest.raises(GrantPackageError) as exc:
            apply_package(db, pkg, public_key=public_hex, expected_org_code="C999")
        assert "不一致" in str(exc.value)

    def test_org_not_found(self, db, keys):
        pkg, public_hex = self._pkg(keys)
        with pytest.raises(GrantPackageError) as exc:
            apply_package(db, pkg, public_key=public_hex)
        assert "不存在" in str(exc.value)

    def test_unsigned_rejected_by_default(self, db):
        _org(db)
        pkg = build_package(org_code="C001", grants={"projects": "edit"}, version=1)
        with pytest.raises(GrantPackageError) as exc:
            apply_package(db, pkg)
        assert "未签名" in str(exc.value)

    def test_unsigned_allowed_when_explicit(self, db):
        _org(db)
        pkg = build_package(org_code="C001", grants={"projects": "edit"}, version=1)
        result = apply_package(db, pkg, allow_unsigned=True)
        assert result["signed"] is False

    def test_signed_but_no_public_key(self, db, keys):
        _org(db)
        pkg, _ = self._pkg(keys)
        with pytest.raises(GrantPackageError) as exc:
            apply_package(db, pkg)
        assert "公钥" in str(exc.value)

    def test_bad_signature_rejected(self, db, keys):
        _org(db)
        pkg, public_hex = self._pkg(keys)
        pkg["grants"]["projects"] = "none"  # 篡改授权
        with pytest.raises(GrantPackageError) as exc:
            apply_package(db, pkg, public_key=public_hex)
        assert "签名" in str(exc.value)

    def test_apply_clears_cache(self, db, keys, monkeypatch):
        _org(db)
        called = SimpleNamespace(value=0)

        def _spy():
            called.value += 1

        monkeypatch.setattr(egs, "clear_cache", _spy)
        pkg, public_hex = self._pkg(keys)
        apply_package(db, pkg, public_key=public_hex)
        assert called.value == 1
