"""`.rrs` 可选来源签名测试。"""
import pytest

from app.core.grant_signing import generate_keypair
from app.services.encrypted_package import (
    create_encrypted_package,
    extract_encrypted_package,
)


def test_signed_package_roundtrip(tmp_path):
    private, public = generate_keypair()
    path = tmp_path / "data.rrs"
    create_encrypted_package({"a": 1}, str(path), "pass", signing_key=private)
    assert (tmp_path / "data.rrs.sig").exists()
    assert extract_encrypted_package(str(path), "pass", public_key=public) == {"a": 1}


def test_signed_package_rejects_tamper(tmp_path):
    private, public = generate_keypair()
    path = tmp_path / "data.rrs"
    create_encrypted_package({"a": 1}, str(path), "pass", signing_key=private)
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        extract_encrypted_package(str(path), "pass", public_key=public)


def test_pubkey_requires_signature_unless_allowed(tmp_path):
    path = tmp_path / "unsigned.rrs"
    create_encrypted_package({"a": 1}, str(path), "pass")
    _, public = generate_keypair()
    with pytest.raises(ValueError, match="缺少来源签名"):
        extract_encrypted_package(str(path), "pass", public_key=public, allow_unsigned=False)
    assert extract_encrypted_package(str(path), "pass", public_key=public, allow_unsigned=True) == {"a": 1}


def test_no_pubkey_warns_but_allows_unsigned(tmp_path):
    path = tmp_path / "unsigned2.rrs"
    create_encrypted_package({"a": 1}, str(path), "pass")
    assert extract_encrypted_package(str(path), "pass") == {"a": 1}


def test_wrong_public_key_rejects_signature(tmp_path):
    private, _public = generate_keypair()
    _, other_public = generate_keypair()
    path = tmp_path / "wrong-key.rrs"
    create_encrypted_package({"a": 1}, str(path), "pass", signing_key=private)
    with pytest.raises(ValueError, match="签名验证失败"):
        extract_encrypted_package(str(path), "pass", public_key=other_public)


def test_signed_package_without_pubkey_is_allowed(tmp_path):
    private, _public = generate_keypair()
    path = tmp_path / "signed-no-pub.rrs"
    create_encrypted_package({"a": 1}, str(path), "pass", signing_key=private)
    assert extract_encrypted_package(str(path), "pass") == {"a": 1}
