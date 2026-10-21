"""R34-2（P1-2）：数据包 PII 密钥指纹校验。

背景：多机离线同步时 PII 列以**密文**出包（见 data_package_service._export_data_type
的 W18-D8 注释），跨机要求相同 ENCRYPTION_KEY。但两台机器按默认方式安装时各自随机
生成密钥，导入后 `decrypt_pii` 解密失败会**原样返回密文**（pii_crypto 第 117 行），
用户看到 `enc.v1:...` 乱码却以为"同步成功"。本文件锁定：
- 导出在 manifest 写入密钥指纹；
- 导入校验指纹，不一致则 fail-closed 拒绝并给出可操作提示；
- 旧包（无字段）与本机指纹不可用时不误拦（向后兼容）。
"""

import json
import zipfile

import pytest


def _write_zip(path, members, compresslevel=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", compresslevel) as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)
    return str(path)


def _manifest(data_types=("schools",), record_counts=None, key_fingerprint=None):
    payload = {
        "version": "1.0",
        "data_types": list(data_types),
        "record_counts": record_counts or {t: 1 for t in data_types},
    }
    if key_fingerprint is not None:
        payload["key_fingerprint"] = key_fingerprint
    return json.dumps(payload)


def _pkg(tmp_path, name, key_fingerprint=None):
    return _write_zip(tmp_path / name, {
        "manifest.json": _manifest(key_fingerprint=key_fingerprint),
        "data/schools.json": json.dumps([{"name": "正常学校"}]),
    })


async def _validate(path):
    from app.services.data_package_service import DataPackageService

    service = DataPackageService.__new__(DataPackageService)
    return await DataPackageService.validate_package(service, path)


class TestLocalFingerprintHelper:
    def test_returns_fingerprint(self, monkeypatch):
        """正常情况返回本机指纹（非空）。"""
        from app.core import pii_crypto
        from app.services import data_package_service as svc

        monkeypatch.setattr(pii_crypto, "key_fingerprint", lambda: "abcd1234ef567890")
        assert svc._local_pii_key_fingerprint() == "abcd1234ef567890"

    def test_returns_empty_when_key_unavailable(self, monkeypatch):
        """密钥不可用时不阻断导出，退化为空串（导出侧不带指纹）。"""
        from app.core import pii_crypto
        from app.services import data_package_service as svc

        def _boom():
            raise RuntimeError("no key")

        monkeypatch.setattr(pii_crypto, "key_fingerprint", _boom)
        assert svc._local_pii_key_fingerprint() == ""


class TestKeyFingerprintValidation:
    async def test_legacy_package_without_fingerprint_passes(self, tmp_path):
        """旧包无该字段 → 跳过校验（向后兼容，不能拒绝历史包）。"""
        result = await _validate(_pkg(tmp_path, "legacy.zip"))
        assert result.is_valid is True

    async def test_matching_fingerprint_passes(self, tmp_path, monkeypatch):
        from app.services import data_package_service as svc

        monkeypatch.setattr(svc, "_local_pii_key_fingerprint", lambda: "same-fp")
        result = await _validate(_pkg(tmp_path, "same.zip", key_fingerprint="same-fp"))
        assert result.is_valid is True

    async def test_mismatched_fingerprint_rejected(self, tmp_path, monkeypatch):
        """核心场景：源机与本机密钥不同 → 拒绝并给出可操作提示。"""
        from app.services import data_package_service as svc

        monkeypatch.setattr(svc, "_local_pii_key_fingerprint", lambda: "local-fp")
        result = await _validate(_pkg(tmp_path, "diff.zip", key_fingerprint="remote-fp"))

        assert result.is_valid is False
        err = next(e for e in result.errors if e.field == "key_fingerprint")
        assert "不同 PII 密钥" in err.message
        assert "remote-fp" in err.message and "local-fp" in err.message
        assert "PII 密钥" in err.message  # 指向修复入口

    async def test_local_fingerprint_unavailable_does_not_block(self, tmp_path, monkeypatch):
        """本机指纹读不到时（密钥初始化异常）宁可放行，不误拦合法包。"""
        from app.services import data_package_service as svc

        monkeypatch.setattr(svc, "_local_pii_key_fingerprint", lambda: "")
        result = await _validate(_pkg(tmp_path, "nofp.zip", key_fingerprint="remote-fp"))
        assert result.is_valid is True


class TestManifestField:
    def test_schema_has_field(self):
        from app.schemas.data_package import DataPackageManifest

        m = DataPackageManifest(key_fingerprint="abc")
        assert m.key_fingerprint == "abc"

    def test_schema_field_defaults_none(self):
        from app.schemas.data_package import DataPackageManifest

        assert DataPackageManifest().key_fingerprint is None
