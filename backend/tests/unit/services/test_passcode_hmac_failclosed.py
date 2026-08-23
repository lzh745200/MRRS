"""W1-T6 安全回归：通行码 HMAC 自验证 fail-closed（ADR-0004）。

历史缺陷：HMAC 密钥存在源码内置默认值且全仓库无部署配置，
任何人可离线计算合法通行码绕过整个授权体系。

注：直接 monkeypatch 模块属性（运行时读取），不做 importlib.reload——
reload 会替换类对象并污染其他测试文件（W1 验证期发现）。
"""

import hmac as hmac_mod
from unittest.mock import MagicMock, patch

from app.services import machine_code_service as mcs


class TestHmacFailClosed:
    def test_default_secret_disables_self_validation(self, monkeypatch):
        """未显式配置 PASS_CODE_SECRET → 自验证路径必须拒绝（即使算式正确）。"""
        monkeypatch.delenv("PASS_CODE_SECRET", raising=False)
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", False)
        mc = "MACHINECODE-123456"
        forged = mcs.MachineCodeService.generate_pass_code(mc)
        assert mcs.MachineCodeService.verify_pass_code_hmac(forged, mc) is False

    def test_explicit_secret_keeps_functionality(self, monkeypatch):
        """显式配置密钥后，正确 HMAC 通行码仍可通过（向后兼容）。"""
        secret = b"unit-test-secret-key"
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET", secret)
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", True)

        mc = "MACHINECODE-789012"
        valid = mcs.MachineCodeService.generate_pass_code(mc)
        assert mcs.MachineCodeService.verify_pass_code_hmac(valid, mc) is True

    def test_wrong_machine_still_rejected_with_explicit_secret(self, monkeypatch):
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET", b"another-key")
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", True)
        assert mcs.MachineCodeService.verify_pass_code_hmac(
            "WRONGPASSCODE00000000000000000000AA", "MC-A"
        ) is False


class TestLevel3RebindAudit:
    def test_fallback_rebind_writes_audit_log(self):
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
