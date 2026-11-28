"""账号开通包：外层签名 + 密文 + KDF 边界（P1-a 核心）。

不导入 bcrypt/passlib（本机 Windows + coverage 下 PyO3 二次导入会失败），
凭据哈希一律用字面量 bcrypt 形态字符串。
"""

from __future__ import annotations

import json
import struct
from datetime import datetime, timedelta, timezone

import pytest

from app.core.account_package import (
    KDF_DEFAULT_ITERATIONS,
    KDF_MAX_ITERATIONS,
    KDF_MIN_ITERATIONS,
    PACKAGE_MAGIC,
    AccountPackageBadKdf,
    AccountPackageBadSignature,
    AccountPackageError,
    AccountPackageExpired,
    AccountPackageUnsigned,
    build_manifest,
    generate_otp,
    inspect_package,
    open_package,
    seal_package,
)
from app.core.grant_signing import generate_keypair, sign_payload

FAKE_HASH = "$2b$12$" + "a" * 53
PASSWORD = "pkg-pass-1"


@pytest.fixture(scope="module")
def keypair():
    priv, pub = generate_keypair()
    return priv, pub


def _manifest(now=None, valid_days=7, package_id="pkg-1"):
    return build_manifest(
        package_id=package_id,
        organization_code="520000",
        target_machine_code="MC-1",
        created_at=now or datetime.now(timezone.utc),
        valid_days=valid_days,
        items=[
            {
                "username": "alice",
                "credential_hash": FAKE_HASH,
                "role": "user",
                "data_scope": "self",
                "full_name": "爱丽丝",
            }
        ],
    )


def _seal(keypair, manifest, iterations=KDF_MIN_ITERATIONS, password=PASSWORD):
    return seal_package(
        manifest,
        password=password,
        private_key_hex=keypair[0],
        iterations=iterations,
    )


def test_roundtrip_returns_manifest(keypair):
    manifest = _manifest()
    raw = _seal(keypair, manifest)

    opened = open_package(raw, password=PASSWORD, public_key_hex=keypair[1])

    assert opened["package_id"] == "pkg-1"
    assert opened["organization_code"] == "520000"
    assert opened["target_machine_code"] == "MC-1"
    assert opened["items"][0]["username"] == "alice"
    assert opened["items"][0]["credential_hash"] == FAKE_HASH


def test_inspect_works_without_password(keypair):
    raw = _seal(keypair, _manifest())
    head = inspect_package(raw)

    assert head["package_id"] == "pkg-1"
    assert head["item_count"] == 1
    assert head["signed"] is True
    assert head["cipher_len"] > 0
    assert "signature" not in head


def test_otp_is_128_bit():
    otp = generate_otp()
    assert len(otp) == 32
    assert all(c in "0123456789abcdef" for c in otp)
    assert generate_otp() != otp


def test_rejects_unsigned_package(keypair):
    with pytest.raises(AccountPackageUnsigned):
        seal_package(_manifest(), password=PASSWORD, private_key_hex="")


def _strip_embedded_signer(raw: bytes, private_hex: str) -> bytes:
    """模拟旧版账号包：header 不内嵌签发公钥，但仍由同一私钥签名。"""
    magic_len = len(PACKAGE_MAGIC)
    magic = raw[:magic_len]
    header_len = struct.unpack(">I", raw[magic_len : magic_len + 4])[0]
    body_start = magic_len + 4
    header = json.loads(raw[body_start : body_start + header_len])
    header.pop("signer_public_key", None)
    header["signature"] = sign_payload(header, private_hex)
    payload = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return magic + struct.pack(">I", len(payload)) + payload + raw[body_start + header_len :]


def test_rejects_when_public_key_missing(keypair):
    raw = _strip_embedded_signer(_seal(keypair, _manifest()), keypair[0])
    with pytest.raises(AccountPackageUnsigned):
        open_package(raw, password=PASSWORD, public_key_hex=None)


def test_embedded_signer_verifies_without_external_key(keypair):
    raw = _seal(keypair, _manifest())
    opened = open_package(raw, password=PASSWORD, public_key_hex=None)
    assert opened["package_id"] == "pkg-1"


def test_rejects_wrong_public_key_for_legacy_package(keypair):
    other_priv, other_pub = generate_keypair()
    raw = _strip_embedded_signer(_seal(keypair, _manifest()), keypair[0])
    with pytest.raises(AccountPackageBadSignature):
        open_package(raw, password=PASSWORD, public_key_hex=other_pub)


def test_rejects_wrong_password(keypair):
    raw = _seal(keypair, _manifest())
    with pytest.raises(AccountPackageError) as exc:
        open_package(raw, password="wrong", public_key_hex=keypair[1])
    assert exc.value.code == "ACCOUNT_PACKAGE_DECRYPT_FAILED"


def test_rejects_tampered_cipher(keypair):
    raw = bytearray(_seal(keypair, _manifest()))
    raw[-1] ^= 0xFF

    with pytest.raises(AccountPackageBadSignature):
        open_package(bytes(raw), password=PASSWORD, public_key_hex=keypair[1])


def test_rejects_tampered_header(keypair):
    raw = _seal(keypair, _manifest())
    header, cipher = _split(raw)
    header["expires_at"] = "2099-01-01T00:00:00+00:00"  # 延长有效期
    forged = _join(header, cipher)

    with pytest.raises(AccountPackageBadSignature):
        open_package(forged, password=PASSWORD, public_key_hex=keypair[1])


def test_rejects_expired(keypair):
    past = datetime.now(timezone.utc) - timedelta(days=30)
    raw = _seal(keypair, _manifest(now=past, valid_days=1))

    with pytest.raises(AccountPackageExpired):
        open_package(raw, password=PASSWORD, public_key_hex=keypair[1])


def test_rejects_low_iterations_on_seal(keypair):
    with pytest.raises(AccountPackageBadKdf):
        seal_package(
            _manifest(),
            password=PASSWORD,
            private_key_hex=keypair[0],
            iterations=100_000,
        )


def test_rejects_low_iterations_in_header(keypair):
    """包头迭代数低于下限时，必须在派生之前拒绝（防 DoS / 降强度）。"""
    raw = _seal(keypair, _manifest())
    header, cipher = _split(raw)
    header["kdf"]["iterations"] = 10_000
    # 重新签名，模拟"攻击者持有私钥但想降强度"的极端场景
    from app.core.grant_signing import sign_payload

    unsigned = {k: v for k, v in header.items() if k != "signature"}
    header["signature"] = sign_payload(unsigned, keypair[0])
    forged = _join(header, cipher)

    with pytest.raises(AccountPackageBadKdf):
        open_package(forged, password=PASSWORD, public_key_hex=keypair[1])


def test_rejects_bad_magic():
    with pytest.raises(AccountPackageError) as exc:
        open_package(b"NOTAPKG" + b"0" * 16, password=PASSWORD, public_key_hex="00")
    assert exc.value.code == "ACCOUNT_PACKAGE_BAD_MAGIC"


def test_rejects_truncated(keypair):
    raw = _seal(keypair, _manifest())
    with pytest.raises(AccountPackageError):
        open_package(raw[: len(PACKAGE_MAGIC) + 2], password=PASSWORD, public_key_hex=keypair[1])


def test_default_iterations_within_range():
    assert KDF_MIN_ITERATIONS <= KDF_DEFAULT_ITERATIONS <= KDF_MAX_ITERATIONS


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
