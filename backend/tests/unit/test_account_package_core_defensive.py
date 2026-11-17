"""账号开通包：防御性分支覆盖（包头/清单/参数的非法输入）。

与 test_account_package_core.py 同源，拆开是为了让"正常路径"与"攻击/损坏路径"读起来分开。
"""

from __future__ import annotations

import json
import struct

import pytest

from app.core.account_package import (
    KDF_ALGORITHM,
    KDF_MAX_ITERATIONS,
    KDF_MIN_ITERATIONS,
    PACKAGE_MAGIC,
    AccountPackageBadKdf,
    AccountPackageBadSignature,
    AccountPackageError,
    _decode_manifest,
    _extract_salt,
    _parse_iso,
    _split_package,
    _validate_kdf,
    build_manifest,
    open_package,
    seal_package,
)
from app.core.grant_signing import generate_keypair, sign_payload

FAKE_HASH = "$2b$12$" + "a" * 53
PASSWORD = "pkg-pass-1"


def _manifest():
    return build_manifest(
        package_id="pkg-1",
        organization_code="520000",
        target_machine_code="MC-1",
        items=[
            {
                "username": "alice",
                "credential_hash": FAKE_HASH,
                "role": "user",
                "data_scope": "self",
            }
        ],
    )


def _split(raw: bytes):
    offset = len(PACKAGE_MAGIC)
    (header_len,) = struct.unpack(">I", raw[offset : offset + 4])
    offset += 4
    header = json.loads(raw[offset : offset + header_len].decode("utf-8"))
    return header, raw[offset + header_len :]


def _join(header: dict, cipher: bytes) -> bytes:
    body = json.dumps(
        header, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return PACKAGE_MAGIC + struct.pack(">I", len(body)) + body + cipher


def test_build_manifest_rejects_empty_and_non_dict_items():
    with pytest.raises(AccountPackageError):
        build_manifest(
            package_id="p", organization_code="1", target_machine_code="m", items=[]
        )
    with pytest.raises(AccountPackageError):
        build_manifest(
            package_id="p",
            organization_code="1",
            target_machine_code="m",
            items=["oops"],  # type: ignore[list-item]
        )


def test_seal_requires_password():
    priv, _ = generate_keypair()
    with pytest.raises(AccountPackageError):
        seal_package(_manifest(), password="", private_key_hex=priv)


def test_validate_kdf_rejects_every_bad_shape():
    bad_inputs = [
        None,
        "x",
        {},
        {"algorithm": "scrypt", "iterations": 600_000},
        {"algorithm": KDF_ALGORITHM},
        {"algorithm": KDF_ALGORITHM, "iterations": True},
        {"algorithm": KDF_ALGORITHM, "iterations": "600000"},
        {"algorithm": KDF_ALGORITHM, "iterations": KDF_MAX_ITERATIONS + 1},
    ]
    for bad in bad_inputs:
        with pytest.raises(AccountPackageBadKdf):
            _validate_kdf(bad)

    assert (
        _validate_kdf({"algorithm": KDF_ALGORITHM, "iterations": KDF_MIN_ITERATIONS})
        == KDF_MIN_ITERATIONS
    )


def test_parse_iso_variants():
    with pytest.raises(AccountPackageError):
        _parse_iso(None, "expires_at")
    with pytest.raises(AccountPackageError):
        _parse_iso("not-a-date", "expires_at")

    naive = _parse_iso("2030-01-01T00:00:00", "expires_at")
    assert naive.tzinfo is not None


def test_split_package_defensive():
    with pytest.raises(AccountPackageError):
        _split_package("str")  # type: ignore[arg-type]
    with pytest.raises(AccountPackageError):
        _split_package(PACKAGE_MAGIC + struct.pack(">I", 0) + b"")
    with pytest.raises(AccountPackageError):
        _split_package(PACKAGE_MAGIC + struct.pack(">I", 3) + b"{}")
    with pytest.raises(AccountPackageError):
        _split_package(PACKAGE_MAGIC + struct.pack(">I", 1) + b"x")
    with pytest.raises(AccountPackageError):
        _split_package(PACKAGE_MAGIC + struct.pack(">I", 2) + b"[]")


def test_extract_salt_defensive():
    with pytest.raises(AccountPackageBadKdf):
        _extract_salt({})
    with pytest.raises(AccountPackageBadKdf):
        _extract_salt({"salt_hex": "zz"})
    with pytest.raises(AccountPackageBadKdf):
        _extract_salt({"salt_hex": "00"})


def test_decode_manifest_defensive():
    header = {"package_id": "p1"}

    with pytest.raises(AccountPackageError):
        _decode_manifest(b"not-json", header)
    with pytest.raises(AccountPackageError):
        _decode_manifest(json.dumps([1]).encode(), header)
    with pytest.raises(AccountPackageError):
        _decode_manifest(json.dumps({"format": "other"}).encode(), header)
    with pytest.raises(AccountPackageError):
        _decode_manifest(
            json.dumps({"format": "account-package", "items": []}).encode(), header
        )
    with pytest.raises(AccountPackageBadSignature):
        _decode_manifest(
            json.dumps(
                {"format": "account-package", "items": [{}], "package_id": "p2"}
            ).encode(),
            header,
        )

    ok = _decode_manifest(
        json.dumps(
            {"format": "account-package", "items": [{}], "package_id": "p1"}
        ).encode(),
        header,
    )
    assert ok["package_id"] == "p1"


def test_rejects_unsupported_version():
    priv, pub = generate_keypair()
    raw = seal_package(
        _manifest(), password=PASSWORD, private_key_hex=priv, iterations=KDF_MIN_ITERATIONS
    )
    header, cipher = _split(raw)
    header["version"] = 99

    with pytest.raises(AccountPackageError):
        open_package(_join(header, cipher), password=PASSWORD, public_key_hex=pub)


def test_rejects_manifest_hash_mismatch():
    priv, pub = generate_keypair()
    raw = seal_package(
        _manifest(), password=PASSWORD, private_key_hex=priv, iterations=KDF_MIN_ITERATIONS
    )
    header, cipher = _split(raw)
    header["manifest_sha256"] = "0" * 64
    unsigned = {k: v for k, v in header.items() if k != "signature"}
    header["signature"] = sign_payload(unsigned, priv)

    with pytest.raises(AccountPackageError):
        open_package(_join(header, cipher), password=PASSWORD, public_key_hex=pub)

def test_open_rejects_empty_password_and_unsigned_header():
    priv, pub = generate_keypair()
    raw = seal_package(
        _manifest(), password=PASSWORD, private_key_hex=priv, iterations=KDF_MIN_ITERATIONS
    )
    with pytest.raises(AccountPackageError):
        open_package(raw, password="", public_key_hex=pub)

    header, cipher = _split(raw)
    header.pop("signature")
    with pytest.raises(AccountPackageError) as exc:
        open_package(_join(header, cipher), password=PASSWORD, public_key_hex=pub)
    assert exc.value.code == "ACCOUNT_PACKAGE_UNSIGNED"


def test_rejects_oversized_package_and_header(monkeypatch):
    import app.core.account_package as ap

    monkeypatch.setattr(ap, "MAX_PACKAGE_BYTES", 2)
    with pytest.raises(AccountPackageError) as exc:
        ap._split_package(PACKAGE_MAGIC + b"xx")
    assert exc.value.code == "ACCOUNT_PACKAGE_TOO_LARGE"

    monkeypatch.setattr(ap, "MAX_PACKAGE_BYTES", 1024)
    monkeypatch.setattr(ap, "MAX_HEADER_BYTES", 2)
    with pytest.raises(AccountPackageError):
        ap._split_package(PACKAGE_MAGIC + struct.pack(">I", 3) + b"{}x")
