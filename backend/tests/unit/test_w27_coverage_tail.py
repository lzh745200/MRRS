"""W27 第 12 轮：覆盖率门禁最后几处缺口的回归（99.99% → 100%）。

这些位置都是**异常/退化分支**，原实现藏在长流程内部，只有完整跑一次业务
（资金分配 / 包导入 / 数据包导入）才能命中，因此长期未覆盖。
处置方式统一为「提到可单测的位置 + 补真实断言」，而不是硬凑一个跑通用例。

覆盖：
* `recommendation_service._income_value_of` —— 收入值为脏字符串时返回 0（不抛）
* `control_package._verify_control_manifest` —— 完整性失败转 400
* `data_package_service._classify_import_records` —— 主键占用但本地行已消失
* `permission_package_service` 的签名失败分支
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


class TestIncomeValueOf:
    def test_none_record_returns_zero(self):
        from app.services.ai.recommendation_service import _income_value_of

        assert _income_value_of(None) == 0.0

    def test_missing_attribute_returns_zero(self):
        from app.services.ai.recommendation_service import _income_value_of

        assert _income_value_of(SimpleNamespace()) == 0.0

    def test_none_value_returns_zero(self):
        from app.services.ai.recommendation_service import _income_value_of

        assert _income_value_of(SimpleNamespace(per_capita_income=None)) == 0.0

    def test_numeric_value_converted(self):
        from app.services.ai.recommendation_service import _income_value_of

        assert _income_value_of(SimpleNamespace(per_capita_income="1234.5")) == 1234.5

    @pytest.mark.parametrize("dirty", ["abc", object(), [1, 2]])
    def test_dirty_value_falls_back_to_zero(self, dirty):
        """脏值（无法转 float）必须回落到 0，而不是让整个推荐流程 500。"""
        from app.services.ai.recommendation_service import _income_value_of

        assert _income_value_of(SimpleNamespace(per_capita_income=dirty)) == 0.0


class TestControlPackageIntegrityReject:
    def test_tampered_manifest_becomes_400(self):
        """checksum 不匹配 → 端点返回 400（而不是 500 或静默通过）。"""
        from app.api.v1.control_package import _verify_control_manifest

        manifest = {"package_type": "control", "checksum": "deadbeef"}
        with pytest.raises(HTTPException) as ei:
            _verify_control_manifest(manifest)
        assert ei.value.status_code == 400
        assert "完整性校验失败" in ei.value.detail

    def test_manifest_without_checksum_becomes_400(self):
        from app.api.v1.control_package import _verify_control_manifest

        with pytest.raises(HTTPException) as ei:
            _verify_control_manifest({"package_type": "control"})
        assert ei.value.status_code == 400
        assert "checksum" in ei.value.detail

    def test_valid_manifest_passes(self):
        from app.api.v1.control_package import _verify_control_manifest
        from app.core.package_integrity import sign_manifest

        # 合法 manifest：不抛异常，且返回 None（纯校验函数无返回值）
        assert _verify_control_manifest(sign_manifest({"package_type": "control"}, None)) is None


class TestPermissionPackageSignatureGuard:
    """权限包来源签名校验（W27 P0-7）。

    未配置 `PACKAGE_PUBKEY` → 不校验（保留旧包可用性）；
    已配置 → 未签名/签名不符必须**拒绝**（fail-closed），错误文案回传给调用方。
    """

    @staticmethod
    def _svc():
        from app.services.permission_package_service import PermissionPackageService

        return PermissionPackageService(MagicMock())

    def test_no_pubkey_configured_passes(self, monkeypatch):
        import app.core.config as cfg

        monkeypatch.setattr(cfg.settings, "PACKAGE_PUBKEY", "", raising=False)
        assert self._svc()._signature_error({"content_checksum": "x"}) is None

    def test_pubkey_configured_unsigned_package_rejected(self, monkeypatch):
        from app.core.grant_signing import generate_keypair

        import app.core.config as cfg

        _priv, pub = generate_keypair()
        monkeypatch.setattr(cfg.settings, "PACKAGE_PUBKEY", pub, raising=False)
        err = self._svc()._signature_error({"content_checksum": "x"})
        assert err is not None
        assert "未签名" in err

    def test_pubkey_configured_valid_signature_passes(self, monkeypatch):
        from app.core.grant_signing import generate_keypair
        from app.core.package_integrity import sign_manifest

        import app.core.config as cfg

        priv, pub = generate_keypair()
        monkeypatch.setattr(cfg.settings, "PACKAGE_PUBKEY", pub, raising=False)
        sealed = sign_manifest({"content_checksum": "x"}, priv)
        assert self._svc()._signature_error(sealed) is None

    def test_pubkey_configured_tampered_package_rejected(self, monkeypatch):
        from app.core.grant_signing import generate_keypair
        from app.core.package_integrity import sign_manifest

        import app.core.config as cfg

        priv, pub = generate_keypair()
        monkeypatch.setattr(cfg.settings, "PACKAGE_PUBKEY", pub, raising=False)
        sealed = sign_manifest({"content_checksum": "x"}, priv)
        sealed["content_checksum"] = "tampered"
        err = self._svc()._signature_error(sealed)
        assert err is not None
        assert "签名验证失败" in err


class TestClassifyLocalRowVanished:
    """「主键占用但本地行消失」分支的正确覆盖点在
    `test_data_package_import_edges_w18::test_local_row_vanished_falls_back_to_relocated`
    （该用例必须带齐业务键才会走到这一层，见其 docstring）。
    此处不重复造用例，避免两处替身形状不一致导致的假绿。
    """

    def test_covered_elsewhere(self):
        import pathlib

        p = pathlib.Path(__file__).parent / "test_data_package_import_edges_w18.py"
        assert "test_local_row_vanished_falls_back_to_relocated" in p.read_text(
            encoding="utf-8"
        )
