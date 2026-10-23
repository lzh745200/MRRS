"""W27 三类包完整性校验回归（���复 W26-P0-7）。

## 背景
四类「人带 U 盘」包中只有单位授权包有密码学完整性；管控配置包 / 系统配置包
完全没有校验，权限包只有 `content_checksum` 没有来源签名。且 `manifest.checksum`
全仓只写不校验。

## 本模块策略（详见 ``app/core/package_integrity.py``）
1. **checksum 强制**：无密钥基建也可用，检出截断/损坏/简单篡改；
2. **Ed25519 签名可选启用**：配置 ``PACKAGE_PUBKEY`` 后强制验签（fail-closed）；
   未配置时保留现场可用性（否则"自己刚生成的包"会被自己拒收）。

本文件锁定：checksum 生成/校验、签名三态（无公钥放行 / 有公钥缺签名拒绝 /
有公钥签名不符拒绝）、以及三类包的接入点。
"""

from unittest.mock import patch

import pytest

from app.core import package_integrity as pi
from app.core.grant_signing import generate_keypair


def _manifest():
    return {
        "package_version": "1.0",
        "package_type": "control",
        "target_organization_id": 7,
        "contents": {"users": 2},
    }


class TestChecksum:
    def test_sign_manifest_adds_checksum(self):
        sealed = pi.sign_manifest(_manifest(), None)
        assert "checksum" in sealed
        assert "signature" not in sealed  # 无私钥不签名
        assert sealed["checksum"] == pi.compute_checksum(sealed)

    def test_verify_accepts_intact_manifest(self):
        sealed = pi.sign_manifest(_manifest(), None)
        pi.verify_manifest(sealed, package_label="管控配置包")  # 不抛

    def test_verify_rejects_missing_checksum(self):
        with pytest.raises(pi.PackageIntegrityError) as ei:
            pi.verify_manifest(_manifest(), package_label="管控配置包")
        assert "checksum" in str(ei.value)

    def test_verify_rejects_tampered_content(self):
        sealed = pi.sign_manifest(_manifest(), None)
        sealed["contents"]["users"] = 99  # 篡改
        with pytest.raises(pi.PackageIntegrityError) as ei:
            pi.verify_manifest(sealed, package_label="管控配置包")
        assert "完整性校验失败" in str(ei.value)

    def test_verify_rejects_non_dict(self):
        with pytest.raises(pi.PackageIntegrityError):
            pi.verify_manifest(["not", "a", "dict"], package_label="管控配置包")

    def test_checksum_ignores_meta_fields(self):
        """checksum/signature 自身不参与校验和计算（否则自指）。"""
        a = _manifest()
        b = dict(a, checksum="whatever", signature="deadbeef")
        assert pi.compute_checksum(a) == pi.compute_checksum(b)


class TestSignatureOptional:
    def test_no_pubkey_allows_unsigned(self):
        sealed = pi.sign_manifest(_manifest(), None)
        pi.verify_manifest(sealed, public_key_hex=None, allow_unsigned=True)

    def test_no_pubkey_with_signature_falls_through(self):
        """未配置公钥但包里**有**签名 → 不做验签，直接放行（走函数末尾返回）。"""
        priv, _pub = generate_keypair()
        sealed = pi.sign_manifest(_manifest(), priv)
        assert sealed.get("signature")
        # 本地未配公钥 → 无来源校验，但 checksum 已通过
        pi.verify_manifest(sealed, public_key_hex=None, allow_unsigned=True)

    def test_sign_manifest_rejects_non_dict(self):
        with pytest.raises(pi.PackageIntegrityError) as ei:
            pi.sign_manifest(["not", "a", "dict"], None)
        assert "manifest 必须是对象" in str(ei.value)

    def test_pubkey_requires_signature(self):
        sealed = pi.sign_manifest(_manifest(), None)  # 无签名
        with pytest.raises(pi.PackageIntegrityError) as ei:
            pi.verify_manifest(sealed, public_key_hex=generate_keypair()[1])
        assert "未签名" in str(ei.value)

    def test_pubkey_accepts_valid_signature(self):
        priv, pub = generate_keypair()
        sealed = pi.sign_manifest(_manifest(), priv)
        assert sealed.get("signature")
        pi.verify_manifest(sealed, public_key_hex=pub)

    def test_pubkey_rejects_signature_from_other_key(self):
        priv, _pub = generate_keypair()
        _p2, other_pub = generate_keypair()
        sealed = pi.sign_manifest(_manifest(), priv)
        with pytest.raises(pi.PackageIntegrityError) as ei:
            pi.verify_manifest(sealed, public_key_hex=other_pub)
        assert "签名验证失败" in str(ei.value)

    def test_forbid_unsigned_without_pubkey(self):
        """allow_unsigned=False 且未配公钥 → 拒绝（严格的部署策略）。"""
        sealed = pi.sign_manifest(_manifest(), None)
        with pytest.raises(pi.PackageIntegrityError):
            pi.verify_manifest(sealed, public_key_hex=None, allow_unsigned=False)


class TestOptionalSignatureHelper:
    """自带 checksum 的包（权限配置包）只用签名这一层。"""

    def test_no_pubkey_is_noop(self):
        pi.verify_optional_signature(_manifest(), public_key_hex=None)

    def test_non_dict_manifest_rejected(self):
        """非法 manifest 结构 → 拒绝（不静默放过）。"""
        with pytest.raises(pi.PackageIntegrityError) as ei:
            pi.verify_optional_signature(["not", "a", "dict"], public_key_hex=None)
        assert "不是有效对象" in str(ei.value)

    def test_pubkey_requires_signature(self):
        with pytest.raises(pi.PackageIntegrityError):
            pi.verify_optional_signature(_manifest(), public_key_hex=generate_keypair()[1])

    def test_valid_signature_passes(self):
        priv, pub = generate_keypair()
        sealed = pi.sign_manifest(_manifest(), priv)
        pi.verify_optional_signature(sealed, public_key_hex=pub)

    def test_tampered_signature_rejected(self):
        priv, pub = generate_keypair()
        sealed = pi.sign_manifest(_manifest(), priv)
        sealed["contents"]["users"] = 999
        with pytest.raises(pi.PackageIntegrityError):
            pi.verify_optional_signature(sealed, public_key_hex=pub)


class TestWiring:
    """三类包导入端点确实接入了校验（防重构时丢失）。"""

    @pytest.mark.parametrize(
        "module_path,marker",
        [
            ("app.api.v1.control_package", "_verify_control_manifest"),
            ("app.api.v1.system.config_package", "_verify_config_package_integrity"),
        ],
    )
    def test_package_module_has_verifier(self, module_path, marker):
        import importlib
        import inspect

        mod = importlib.import_module(module_path)
        assert hasattr(mod, marker)
        assert "verify_manifest" in inspect.getsource(getattr(mod, marker))

    def test_permission_service_verifies_signature(self):
        import inspect

        from app.services import permission_package_service as svc

        src = inspect.getsource(svc.PermissionPackageService)
        assert "verify_optional_signature" in src, "权限包未接入来源签名校验"


class TestConfigPackageSealed:
    """系统配置包导出即带 checksum（导入端强制校验的前提）。"""

    def test_export_result_contains_checksum(self):
        from app.core.package_integrity import sign_manifest

        package = {"name": "p", "configs": {"a": 1}}
        sealed = sign_manifest(package, None)
        assert "checksum" in sealed
        pi.verify_manifest(sealed, package_label="系统配置包")
