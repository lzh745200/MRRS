"""
机器码服务单元测试
覆盖: app/services/machine_code_service.py
"""
import pytest
from unittest.mock import patch
from unittest.mock import MagicMock
from app.services.machine_code_service import MachineCodeService


@pytest.fixture
def mcs():
    return MachineCodeService()


class TestGenerateVerificationCode:
    def test_returns_4_digit_string(self, mcs):
        result = MachineCodeService.generate_verification_code("ABC123")
        assert len(result) == 4
        assert result.isdigit()

    def test_deterministic_same_input(self, mcs):
        code1 = MachineCodeService.generate_verification_code("test-machine")
        code2 = MachineCodeService.generate_verification_code("test-machine")
        assert code1 == code2

    def test_different_inputs_different_codes(self, mcs):
        code1 = MachineCodeService.generate_verification_code("machine-A")
        code2 = MachineCodeService.generate_verification_code("machine-B")
        assert code1 != code2

    def test_code_in_range(self, mcs):
        """Verification code should be between 1000-9999."""
        for _ in range(10):
            code = MachineCodeService.generate_verification_code(
                f"test-{_}"
            )
            assert 1000 <= int(code) <= 9999

    def test_empty_string_works(self, mcs):
        """Empty machine_code should still generate a code."""
        code = MachineCodeService.generate_verification_code("")
        assert len(code) == 4


class TestVerifyMachineCode:
    def test_matching_codes_pass(self, mcs):
        machine_code = "ABC123DEF456"
        verification = MachineCodeService.generate_verification_code(machine_code)
        assert MachineCodeService.verify_machine_code(machine_code, verification) is True

    def test_wrong_code_fails(self, mcs):
        machine_code = "ABC123DEF456"
        assert MachineCodeService.verify_machine_code(machine_code, "0000") is False

    def test_empty_codes(self, mcs):
        verification = MachineCodeService.generate_verification_code("")
        assert MachineCodeService.verify_machine_code("", verification) is True


class TestGenerateInitialPassword:
    def test_password_format(self, mcs):
        pwd = MachineCodeService.generate_initial_password("admin", "1234")
        # username[:4].upper() = "ADMI"
        assert pwd == "ADMI1234@RRS"

    def test_short_username(self, mcs):
        pwd = MachineCodeService.generate_initial_password("ab", "5678")
        assert pwd == "AB5678@RRS"

    def test_long_username_truncated(self, mcs):
        pwd = MachineCodeService.generate_initial_password("administrator", "0000")
        assert pwd == "ADMI0000@RRS"

    def test_lowercase_uppercased(self, mcs):
        pwd = MachineCodeService.generate_initial_password("user", "9999")
        assert pwd == "USER9999@RRS"

    def test_ends_with_suffix(self, mcs):
        pwd = MachineCodeService.generate_initial_password("test", "1111")
        assert pwd.endswith("@RRS")

    def test_contains_verification_code(self, mcs):
        pwd = MachineCodeService.generate_initial_password("test", "4321")
        assert "4321" in pwd


class TestGetMachineInfo:
    def test_returns_dict_with_keys(self, mcs):
        info = MachineCodeService.get_machine_info()
        assert isinstance(info, dict)
        assert "system" in info
        assert "release" in info
        assert "machine" in info
        assert "node" in info

    def test_system_is_string(self, mcs):
        info = MachineCodeService.get_machine_info()
        assert isinstance(info["system"], str)
        assert len(info["system"]) > 0


class TestGetMachineCode:
    def test_returns_string(self, mcs):
        # patch 类属性，测试结束自动恢复（防跨测试缓存污染）
        with patch.object(MachineCodeService, "_cached_machine_code",
                          "deadbeefcafe12340011aabbccdd9988"):
            code = MachineCodeService.get_machine_code()
            assert isinstance(code, str)
            assert len(code) == 32

    def test_cached_second_call(self, mcs):
        with patch.object(MachineCodeService, "_cached_machine_code",
                          "aaaabbbbccccddddeeeeffff00001111"):
            code = MachineCodeService.get_machine_code()
            assert code == "aaaabbbbccccddddeeeeffff00001111"
            code2 = MachineCodeService.get_machine_code()
            assert code2 == code


class TestGeneratePassCode:
    def test_returns_formatted_string(self, mcs):
        code = MachineCodeService.generate_pass_code("test-machine")
        assert isinstance(code, str)
        # 32 hex chars + 7 hyphens = 39 chars
        assert len(code) == 39
        assert code.count("-") == 7

    def test_deterministic(self, mcs):
        """generate_pass_code 为确定性 HMAC(跨机器自验证前提):同输入一致,不同输入不同。"""
        c1 = MachineCodeService.generate_pass_code("same-input")
        c2 = MachineCodeService.generate_pass_code("same-input")
        c3 = MachineCodeService.generate_pass_code("other-input")
        assert c1 == c2  # 确定性
        assert c1 != c3  # 不同机器码不同通行码

    def test_hyphen_format(self, mcs):
        code = MachineCodeService.generate_pass_code("test")
        parts = code.split("-")
        assert len(parts) == 8
        for part in parts:
            assert len(part) == 4


class TestMachineCodeServiceInit:
    def test_init_with_db(self):
        from app.services.machine_code_service import MachineCodeService
        mock_db = MagicMock()
        svc = MachineCodeService(db=mock_db)
        assert svc.db is mock_db

    def test_init_without_db(self):
        from app.services.machine_code_service import MachineCodeService
        svc = MachineCodeService()
        assert svc.db is None


class TestGenerateOrganizationVerificationCode:
    def test_returns_code(self, mcs):
        code = MachineCodeService.generate_organization_verification_code(1, "Test Org")
        assert isinstance(code, str)
        assert len(code) >= 4

    def test_different_ids_different_codes(self, mcs):
        c1 = MachineCodeService.generate_organization_verification_code(1, "Same Org")
        c2 = MachineCodeService.generate_organization_verification_code(2, "Same Org")
        assert c1 != c2


class TestGenerateOrganizationPassCode:
    def test_returns_code(self, mcs):
        code = MachineCodeService.generate_organization_pass_code(1, "VERIFY123")
        assert isinstance(code, str)
        assert len(code) >= 6

    def test_different_inputs_different_codes(self, mcs):
        c1 = MachineCodeService.generate_organization_pass_code(1, "CODE-A")
        c2 = MachineCodeService.generate_organization_pass_code(2, "CODE-B")
        assert c1 != c2
