"""账号开通包：应用内签发密钥 + 跨机信任（自动密钥，不再依赖环境变量）。"""

from __future__ import annotations

import json

import pytest

from app.core.account_package import (
    KDF_MIN_ITERATIONS,
    build_manifest,
    inspect_package,
    open_package,
    seal_package,
)
from app.core.account_package_keys import (
    AccountPackageKeyError,
    add_trusted_public_key,
    key_fingerprint,
    local_private_key,
    local_public_key,
    remove_trusted_public_key,
    trusted_public_keys,
    verification_public_keys,
)
from app.core.config import settings
from app.core.grant_signing import derive_public_key, generate_keypair


@pytest.fixture()
def secrets_file(tmp_path, monkeypatch):
    path = tmp_path / "runtime_secrets.json"
    monkeypatch.setenv("RUNTIME_SECRETS_FILE", str(path))
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", "")
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_PUBKEY", "")
    return path


def test_derive_public_key_matches_keypair() -> None:
    private_hex, public_hex = generate_keypair()
    assert derive_public_key(private_hex) == public_hex


def test_local_key_generated_once_and_persisted(secrets_file) -> None:
    assert local_private_key(create=False) == ""

    first = local_private_key(create=True)
    second = local_private_key(create=True)

    assert first == second
    assert len(first) == 64
    assert secrets_file.exists()
    stored = json.loads(secrets_file.read_text(encoding="utf-8"))
    assert stored["ACCOUNT_PACKAGE_SIGNING_KEY"] == first
    assert local_public_key(create=False) == derive_public_key(first)


def test_environment_private_key_takes_precedence(secrets_file, monkeypatch) -> None:
    env_private, env_public = generate_keypair()
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", env_private)

    assert local_private_key(create=True) == env_private
    assert local_public_key(create=False) == env_public
    assert not secrets_file.exists()


def test_invalid_environment_private_key_is_rejected(secrets_file, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", "not-a-valid-key")
    with pytest.raises(AccountPackageKeyError):
        local_private_key(create=True)


def test_trusted_keys_add_list_and_remove(secrets_file) -> None:
    _, public_a = generate_keypair()
    _, public_b = generate_keypair()

    fingerprint_a = add_trusted_public_key(public_a)
    add_trusted_public_key(public_b)

    assert fingerprint_a == key_fingerprint(public_a)
    assert public_a in trusted_public_keys()
    assert public_b in trusted_public_keys()
    assert public_a in verification_public_keys()

    assert remove_trusted_public_key(fingerprint_a) is True
    assert public_a not in trusted_public_keys()
    assert remove_trusted_public_key("0000-0000") is False


def test_trusted_keys_rejects_invalid_public_key(secrets_file) -> None:
    with pytest.raises(AccountPackageKeyError):
        add_trusted_public_key("xyz")


def test_local_public_key_is_implicitly_trusted(secrets_file) -> None:
    public_hex = local_public_key(create=True)
    assert public_hex in trusted_public_keys()


def test_seal_embeds_signer_public_key_and_opens_without_external_key() -> None:
    private_hex, public_hex = generate_keypair()
    manifest = build_manifest(
        package_id="9f3c2f5e-0000-4000-8000-000000000001",
        organization_code="520100",
        organization_name="市局",
        parent_code="520000",
        target_machine_code="MC-TEST-123",
        items=[{"username": "alice", "role": "admin", "data_scope": "org"}],
        grants={"projects": "edit"},
    )
    raw = seal_package(
        manifest,
        password="Passw0rd-123",
        private_key_hex=private_hex,
        iterations=KDF_MIN_ITERATIONS,
    )

    head = inspect_package(raw)
    assert head["signer_public_key"] == public_hex
    opened = open_package(raw, password="Passw0rd-123", public_key_hex=None)
    assert opened["package_id"] == manifest["package_id"]


def test_open_still_rejects_tampered_header_when_using_embedded_key() -> None:
    private_hex, _ = generate_keypair()
    manifest = build_manifest(
        package_id="9f3c2f5e-0000-4000-8000-000000000002",
        organization_code="520100",
        target_machine_code="MC-TEST-123",
        items=[{"username": "alice", "role": "admin", "data_scope": "org"}],
        grants={"projects": "edit"},
    )
    raw = bytearray(
        seal_package(manifest, password="Passw0rd-123", private_key_hex=private_hex,
                     iterations=KDF_MIN_ITERATIONS)
    )
    # 翻转密文区最后一个字节：包头签名仍有效，但 cipher_sha256 必须发现篡改。
    raw[-1] ^= 0xFF
    with pytest.raises(Exception):
        open_package(raw, password="Passw0rd-123", public_key_hex=None)
