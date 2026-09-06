"""通行码 HMAC 自验证语义（2026-09-06 产品决策更新，取代 W1-T6 fail-closed）。

W1-T6 历史：内置默认密钥曾被判"允许离线伪造授权"而 fail-closed——该决策
导致跨机器注册在所有安装实例上 100% 失败（Electron 不注入 PASS_CODE_SECRET，
管理员在 A 机生成的通行码在 B 机永远无效，2026-09-06 生产双机反馈）。
产品所有者确认接受取舍：离线跨机器注册为明确需求，自注册兜底为管理员
事后审计（用户管理可见/可停用，注册动作全量审计留痕）。

注：直接 monkeypatch 模块属性（运行时读取），不做 importlib.reload——
reload 会替换类对象并污染其他测试文件（W1 验证期发现）。
"""

import hmac as hmac_mod
from unittest.mock import MagicMock, patch

from app.services import machine_code_service as mcs


class TestHmacFailClosed:
    def test_default_secret_enables_self_validation(self, monkeypatch):
        """2026-09-06 起：未配置 PASS_CODE_SECRET → 内置常量密钥自验证可用。

        旧断言（fail-closed 拒绝）导致跨机器注册在所有安装实例上 100% 失败，
        已按产品决策翻转（见文件头）。
        """
        monkeypatch.delenv("PASS_CODE_SECRET", raising=False)
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", False)
        mc = "MACHINECODE-123456"
        code = mcs.MachineCodeService.generate_pass_code(mc)
        assert mcs.MachineCodeService.verify_pass_code_hmac(code, mc) is True

    def test_wrong_machine_rejected_with_default_secret(self, monkeypatch):
        """内置密钥下错误机器的通行码仍被拒（机器绑定语义保留）。"""
        monkeypatch.delenv("PASS_CODE_SECRET", raising=False)
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", False)
        code = mcs.MachineCodeService.generate_pass_code("MC-REAL")
        assert mcs.MachineCodeService.verify_pass_code_hmac(code, "MC-OTHER") is False

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
