"""W1-T6 安全回归：通行码 HMAC 自验证 fail-closed（ADR-0004）。

历史缺陷：HMAC 密钥存在源码内置默认值且全仓库无部署配置，
任何人可离线计算合法通行码绕过整个授权体系。
"""

import hashlib
import hmac as hmac_mod
from unittest.mock import MagicMock, patch

import pytest

from app.services import machine_code_service as mcs


def _compute(pass_code: str, machine_code: str) -> str:
    digest = hmac_mod.new(
        mcs._PASS_CODE_SECRET, machine_code.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return digest[:32].upper()  # 与 generate_pass_code 截断策略一致


class TestHmacFailClosed:
    def test_default_secret_disables_self_validation(self, monkeypatch):
        """未显式配置 PASS_CODE_SECRET → 自验证路径必须拒绝（即使算式正确）。"""
        monkeypatch.delenv("PASS_CODE_SECRET", raising=False)
        mc = "MACHINECODE-123456"
        forged = _compute("x", mc)
        # 直接调用被测函数：默认密钥下无论输入如何都拒绝
        assert mcs.MachineCodeService.verify_pass_code_hmac(forged, mc) is False

    def test_explicit_secret_keeps_functionality(self, monkeypatch):
        """显式配置密钥后，正确 HMAC 通行码仍可通过（向后兼容）。"""
        secret = "unit-test-secret-key"
        monkeypatch.setenv("PASS_CODE_SECRET", secret)
        # 模块级常量在 import 时固化——通过 reload 生效
        import importlib

        importlib.reload(mcs)
        try:
            mc = "MACHINECODE-789012"
            digest = hmac_mod.new(
                secret.encode("utf-8"), mc.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            valid = mcs.MachineCodeService.generate_pass_code(mc)
            assert valid.lower() in (digest[:32].lower(), digest[:32].upper()) or (
                mcs.MachineCodeService.verify_pass_code_hmac(valid, mc) is True
            )
            assert mcs.MachineCodeService.verify_pass_code_hmac(valid, mc) is True
        finally:
            importlib.reload(mcs)

    def test_wrong_machine_still_rejected_with_explicit_secret(self, monkeypatch):
        monkeypatch.setenv("PASS_CODE_SECRET", "another-key")
        import importlib

        importlib.reload(mcs)
        try:
            assert mcs.MachineCodeService.verify_pass_code_hmac(
                "WRONGPASSCODE00000000000000000000AA", "MC-A"
            ) is False
        finally:
            importlib.reload(mcs)


class TestLevel3RebindAudit:
    def test_fallback_rebind_writes_audit_log(self, monkeypatch):
        """level-3 回退改绑机器码时必须写审计日志（可追溯要求）。"""
        record = MagicMock()
        record.machine_code = "OLDMC123"
        record.status = "pending"
        record.organization_id = None

        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.side_effect = [None, None, record]
        db.query.return_value = q

        svc = mcs.MachineCodeService(db)
        with patch("app.services.work_log_service.write_work_log") as wwl:
            result = svc.verify_pass_code("SOMEPASSCODE", "NEWMC456")

        assert result is record
        assert record.machine_code == "NEWMC456"
        assert wwl.called, "回退改绑机器码必须留痕"
