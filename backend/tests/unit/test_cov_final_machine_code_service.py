"""补齐 app.services.machine_code_service 覆盖率缺口。

目标行：
- 409-410：verify_pass_code 机器特定通行码 active(未绑定) → 重置 pending + 提交
- 434-438：verify_pass_code 组织通行码回退命中分支（含 active 未绑定重置与直接返回）
- 728-739：delete_organization_pass_code 全分支（记录不存在返回 False / 删除并返回 True）

db 使用 MagicMock 链式 mock；safe_commit 在模块命名空间打 patch。
"""

import platform
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.machine_code_service import MachineCodeService

_MOD = "app.services.machine_code_service"


def _svc_with_first(first_values):
    """构造 db.query().filter().first() 依次返回 first_values 的服务实例。"""
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.first.side_effect = first_values
    return MachineCodeService(db), db


class TestVerifyPassCode:
    def test_machine_code_active_unbound_reset_to_pending(self):
        # 第一次查询即命中：机器特定通行码，active 且未绑定用户 → 重置 pending（409-410）
        record = SimpleNamespace(status="active", user_id=None)
        svc, db = _svc_with_first([record])

        with patch(f"{_MOD}.safe_commit") as mock_commit:
            result = svc.verify_pass_code("P" * 40, "M" * 40)

        assert result is record
        assert record.status == "pending"
        mock_commit.assert_called_once_with(db)

    def test_org_pass_code_fallback_active_unbound_reset(self):
        # 机器特定未命中 → 组织通行码回退命中，active 未绑定 → 重置（434-436）并返回（437-438）
        record = SimpleNamespace(status="active", user_id=None)
        svc, db = _svc_with_first([None, record])

        with patch(f"{_MOD}.safe_commit") as mock_commit:
            result = svc.verify_pass_code("P" * 40, "M" * 40)

        assert result is record
        assert record.status == "pending"
        mock_commit.assert_called_once_with(db)

    def test_org_pass_code_fallback_pending_returned_as_is(self):
        # 回退命中 pending 记录：不触发重置，直接返回（434 条件为假分支）
        record = SimpleNamespace(status="pending", user_id=None)
        svc, db = _svc_with_first([None, record])

        with patch(f"{_MOD}.safe_commit") as mock_commit:
            result = svc.verify_pass_code("P" * 40, "M" * 40)

        assert result is record
        assert record.status == "pending"
        mock_commit.assert_not_called()

    def test_hmac_self_verify_cross_machine_creates_local_record(self, monkeypatch):
        # 目标机数据库无任何记录（first 均为 None），HMAC 自验证通过后
        # → 在本机创建绑定到当前机器的记录
        # W1-T6 fail-closed：需显式配置密钥后才允许自验证。
        # 注：直接 patch 模块级密钥常量（运行时读取），禁止 importlib.reload——
        # reload 会分裂类对象，导致其他文件对旧类的 patch 失效（全量序 flake 根因）。
        monkeypatch.setenv("PASS_CODE_SECRET", "unit-test-secret")

        from app.services import machine_code_service as mcs

        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET", b"unit-test-secret")
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", True)

        machine_code = "B" + "0" * 63
        pass_code = mcs.MachineCodeService.generate_pass_code(machine_code)

        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.first.side_effect = [None, None, None]  # 三次查询均返回未找到

        svc = mcs.MachineCodeService(db)

        with patch(f"{_MOD}.safe_commit") as mock_commit:
            result = svc.verify_pass_code(pass_code, machine_code)

        assert result is not None
        assert result.machine_code == machine_code
        assert result.status == "pending"
        db.add.assert_called_once()
        mock_commit.assert_called()

    def test_hmac_self_verify_rejects_wrong_machine(self):
        # 错误机器码 → HMAC 不匹配 → 返回 None（"通行码无效或已被使用"）
        # 归一化重试后查询轮次翻倍：原文3次 + 去连字符3次 = 6次 first()
        machine_b = "B" + "0" * 63
        pass_code = MachineCodeService.generate_pass_code(machine_b)

        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.first.side_effect = [None] * 6

        svc = MachineCodeService(db)
        result = svc.verify_pass_code(pass_code, "A" + "0" * 63)

        assert result is None

    def test_hmac_accepts_input_without_dashes(self, monkeypatch):
        # 用户输入去掉连字符的通行码 应 与一致机器码匹配
        # W1-T6 fail-closed：需显式配置密钥后才允许自验证。
        # 直接 patch 模块常量（运行时读取），不做 reload——防类对象分裂污染全量序。
        monkeypatch.setenv("PASS_CODE_SECRET", "unit-test-secret")

        from app.services import machine_code_service as mcs

        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET", b"unit-test-secret")
        monkeypatch.setattr(mcs, "_PASS_CODE_SECRET_EXPLICIT", True)

        machine_code = "C" + "0" * 63
        pass_code = mcs.MachineCodeService.generate_pass_code(machine_code)

        assert mcs.MachineCodeService.verify_pass_code_hmac(
            pass_code.replace("-", ""), machine_code
        ) is True

    def test_generate_pass_code_deterministic(self):
        # 确定性：同一机器码两次生成结果一致（跨机器可重算验证的前提）
        machine_code = "D" + "0" * 63
        pc1 = MachineCodeService.generate_pass_code(machine_code)
        pc2 = MachineCodeService.generate_pass_code(machine_code)

        assert pc1 == pc2
        assert len(pc1.replace("-", "")) == 32


class TestDeleteOrganizationPassCode:
    def test_no_db_session_raises_value_error(self):
        # db 未初始化 → 729 行 raise ValueError
        svc = MachineCodeService(None)
        with pytest.raises(ValueError, match="数据库会话未初始化"):
            svc.delete_organization_pass_code(1)

    def test_not_found_returns_false(self):
        svc, db = _svc_with_first([None])

        assert svc.delete_organization_pass_code(123) is False
        db.delete.assert_not_called()

    def test_found_deletes_and_returns_true(self):
        record = SimpleNamespace(id=5)
        svc, db = _svc_with_first([record])

        with patch(f"{_MOD}.safe_commit") as mock_commit:
            assert svc.delete_organization_pass_code(5) is True

        db.delete.assert_called_once_with(record)
        mock_commit.assert_called_once_with(db)


class TestCollectWmicInfoParsing:
    def test_parses_and_filters_placeholder_values(self, monkeypatch):
        """wmic 采集的解析与占位过滤（machine_code_service.py 92-95 行）。

        真 Windows 环境由 get_machine_code() 间接走真实 wmic 覆盖；Linux CI 上
        整个 Windows 分支被 platform 守卫 + pragma 提前返回、92-94 永不执行 →
        fail_under=100 门禁恒缺 3 行（2026-09-05 PR Checks 实测）。此处 mock
        Popen/communicate，双平台确定性锁定解析语义：
        - ProcessorId（skip=None）：取最后一行非空值；
        - baseboard SerialNumber：值 == "To be filled by O.E.M." 占位 → 丢弃；
        - diskdrive SerialNumber：正常值保留。
        """
        monkeypatch.setattr(platform, "system", lambda: "Windows")

        fake_proc = MagicMock()
        fake_proc.communicate.side_effect = [
            ("ProcessorId\n BFEBFBFF000806EC\n", ""),
            ("SerialNumber\n To be filled by O.E.M.\n", ""),
            ("SerialNumber\n WD-WX11A80D1234\n", ""),
        ]
        with patch(
            f"{_MOD}.subprocess.Popen", return_value=fake_proc
        ) as mock_popen:
            info = MachineCodeService._collect_wmic_info()

        assert mock_popen.call_count == 3
        assert info == ["BFEBFBFF000806EC", "WD-WX11A80D1234"]

    def test_communicate_timeout_is_2s_and_blank_output_skipped(self, monkeypatch):
        """communicate 必须 2 秒超时；空输出行（val 为空）不得进入 info。"""
        monkeypatch.setattr(platform, "system", lambda: "Windows")

        fake_proc = MagicMock()
        fake_proc.communicate.side_effect = [
            # ProcessorId：纯空白输出 → strip 后 val 为空 → 跳过
            ("   \n", ""),
            # baseboard：占位值 → 上一用例已验丢弃，此处验空白跳过同样生效
            ("SerialNumber\n To be filled by O.E.M.\n", ""),
            # diskdrive：正常值
            ("SerialNumber\n DISK-SER\n", ""),
        ]
        with patch(
            f"{_MOD}.subprocess.Popen", return_value=fake_proc
        ) as mock_popen:
            info = MachineCodeService._collect_wmic_info()

        assert mock_popen.call_count == 3
        assert fake_proc.communicate.call_args_list[0].kwargs.get("timeout") == 2
        assert info == ["DISK-SER"]
