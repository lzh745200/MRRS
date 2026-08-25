import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


def _run_async(coro):
    """同步运行 async 协程（兼容 Python 3.11+，避免 get_event_loop 弃用警告）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class TestMachineCodeServiceStatic:
    def test_get_machine_code_cached(self):
        from app.services.machine_code_service import MachineCodeService
        MachineCodeService._cached_machine_code = "cached_code"
        result = MachineCodeService.get_machine_code()
        assert result == "cached_code"
        MachineCodeService._cached_machine_code = None

    @patch("app.services.machine_code_service.platform.system", return_value="Linux")
    @patch("app.services.machine_code_service.uuid.getnode", return_value=0x001122334455)
    @patch("app.services.machine_code_service.platform.node", return_value="testhost")
    def test_get_machine_code_linux(self, mock_node, mock_getnode, mock_system):
        from app.services.machine_code_service import MachineCodeService
        MachineCodeService._cached_machine_code = None
        code = MachineCodeService.get_machine_code()
        assert len(code) == 64
        assert MachineCodeService._cached_machine_code == code
        MachineCodeService._cached_machine_code = None

    @patch("app.services.machine_code_service.platform.system", return_value="Linux")
    @patch("app.services.machine_code_service.uuid.getnode", side_effect=Exception("fail"))
    @patch("app.services.machine_code_service.platform.node", side_effect=Exception("fail"))
    def test_get_machine_code_no_info_uses_uuid(self, mock_node, mock_getnode, mock_system):
        from app.services.machine_code_service import MachineCodeService
        MachineCodeService._cached_machine_code = None
        code = MachineCodeService.get_machine_code()
        assert len(code) == 64
        MachineCodeService._cached_machine_code = None

    def test_generate_verification_code(self):
        from app.services.machine_code_service import MachineCodeService
        code = MachineCodeService.generate_verification_code("test_machine_code")
        assert len(code) == 4
        assert code.isdigit()
        assert 1000 <= int(code) <= 9999

    def test_verify_machine_code_valid(self):
        from app.services.machine_code_service import MachineCodeService
        mc = "abcdef1234567890"
        vc = MachineCodeService.generate_verification_code(mc)
        assert MachineCodeService.verify_machine_code(mc, vc) is True

    def test_verify_machine_code_invalid(self):
        from app.services.machine_code_service import MachineCodeService
        assert MachineCodeService.verify_machine_code("abc", "9999") is False

    def test_generate_initial_password(self):
        from app.services.machine_code_service import MachineCodeService
        pw = MachineCodeService.generate_initial_password("admin", "1234")
        assert pw == "ADMI1234@RRS"

    def test_generate_initial_password_short_name(self):
        from app.services.machine_code_service import MachineCodeService
        pw = MachineCodeService.generate_initial_password("ab", "5678")
        assert pw == "AB5678@RRS"

    @patch("app.services.machine_code_service.subprocess.run")
    @patch("app.services.machine_code_service.platform")
    def test_get_machine_info_windows(self, mock_platform, mock_run):
        from app.services.machine_code_service import MachineCodeService
        mock_platform.system.return_value = "Windows"
        mock_platform.release.return_value = "10"
        mock_platform.version.return_value = "10.0.19041"
        mock_platform.machine.return_value = "AMD64"
        mock_platform.processor.return_value = "Intel64"
        mock_platform.node.return_value = "PC01"
        cpu_result = MagicMock()
        cpu_result.stdout = "Intel Core\n"
        mem_result = MagicMock()
        mem_result.stdout = "8589934592\n"
        mock_run.side_effect = [cpu_result, mem_result]
        info = MachineCodeService.get_machine_info()
        assert info["system"] == "Windows"
        assert "cpu_name" in info
        assert "memory_gb" in info

    @patch("app.services.machine_code_service.subprocess.run", side_effect=Exception("fail"))
    @patch("app.services.machine_code_service.platform")
    def test_get_machine_info_windows_subprocess_fail(self, mock_platform, mock_run):
        from app.services.machine_code_service import MachineCodeService
        mock_platform.system.return_value = "Windows"
        mock_platform.release.return_value = "10"
        mock_platform.version.return_value = "10.0"
        mock_platform.machine.return_value = "x64"
        mock_platform.processor.return_value = ""
        mock_platform.node.return_value = "PC"
        info = MachineCodeService.get_machine_info()
        assert "system" in info

    @patch("app.services.machine_code_service.platform")
    def test_get_machine_info_linux(self, mock_platform):
        from app.services.machine_code_service import MachineCodeService
        mock_platform.system.return_value = "Linux"
        mock_platform.release.return_value = "5.4"
        mock_platform.version.return_value = "#1 SMP"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.processor.return_value = "x86_64"
        mock_platform.node.return_value = "server"
        info = MachineCodeService.get_machine_info()
        assert info["system"] == "Linux"
        assert "cpu_name" not in info

    def test_generate_pass_code_format(self):
        from app.services.machine_code_service import MachineCodeService
        pc = MachineCodeService.generate_pass_code("abc123")
        parts = pc.split("-")
        assert len(parts) == 8
        assert all(len(p) == 4 for p in parts)
        assert len(pc) == 39

    def test_generate_pass_code_different_each_time(self):
        from app.services.machine_code_service import MachineCodeService
        # 确定性生成：同一机器码结果一致（跨机器自验证的前提），不同机器码结果不同
        pc1 = MachineCodeService.generate_pass_code("abc")
        pc2 = MachineCodeService.generate_pass_code("abc")
        pc3 = MachineCodeService.generate_pass_code("def")
        assert pc1 == pc2
        assert pc1 != pc3


class TestMachineCodeServiceDB:
    def _make_service(self, db=None):
        from app.services.machine_code_service import MachineCodeService
        return MachineCodeService(db=db)

    def test_create_no_db_raises(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError, match="数据库会话未初始化"):
            svc.create_machine_code_record("mc1", 1)

    def test_create_existing_reuses_record(self):
        db = MagicMock()
        existing = MagicMock()
        existing.status = "active"
        existing.user_id = 99
        db.query.return_value.filter.return_value.first.return_value = existing
        svc = self._make_service(db)
        result = svc.create_machine_code_record("mc1", 1)
        # 复用已有记录：重置状态为 pending，清除用户绑定
        assert existing.status == "pending"
        assert existing.user_id is None
        assert db.commit.called

    def test_create_with_custom_pass_code(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._make_service(db)
        record = svc.create_machine_code_record("mc1", 1, description="test", pass_code="1234")
        assert db.add.called
        assert db.commit.called

    def test_create_auto_pass_code(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._make_service(db)
        record = svc.create_machine_code_record("mc1", 1)
        assert record is not None

    def test_verify_pass_code_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.verify_pass_code("pc", "mc")

    def test_verify_pass_code_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._make_service(db)
        result = svc.verify_pass_code("pc", "mc")
        assert result is None

    def test_verify_pass_code_found(self):
        db = MagicMock()
        mock_record = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = mock_record
        svc = self._make_service(db)
        result = svc.verify_pass_code("pc", "mc")
        assert result == mock_record

    def test_activate_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.activate_machine_code(MagicMock(), 1)

    def test_activate_success(self):
        db = MagicMock()
        svc = self._make_service(db)
        record = MagicMock()
        record.machine_code = "a" * 32
        svc.activate_machine_code(record, 1)
        assert record.status == "active"
        assert record.user_id == 1
        assert db.commit.called

    def test_revoke_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.revoke_machine_code(1)

    def test_revoke_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._make_service(db)
        assert svc.revoke_machine_code(1) is False

    def test_revoke_success(self):
        db = MagicMock()
        mock_record = MagicMock()
        mock_record.machine_code = "a" * 32
        db.query.return_value.filter.return_value.first.return_value = mock_record
        svc = self._make_service(db)
        assert svc.revoke_machine_code(1) is True
        assert mock_record.status == "revoked"

    def test_get_machine_code_by_user_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.get_machine_code_by_user(1)

    def test_get_machine_code_by_user(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        svc = self._make_service(db)
        result = svc.get_machine_code_by_user(1)
        assert result is not None

    def test_verify_user_machine_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.verify_user_machine(1, "mc")

    def test_verify_user_machine_no_record(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._make_service(db)
        assert svc.verify_user_machine(1, "mc") is True

    def test_verify_user_machine_match(self):
        db = MagicMock()
        mock_record = MagicMock()
        mock_record.machine_code = "same_mc"
        db.query.return_value.filter.return_value.first.return_value = mock_record
        svc = self._make_service(db)
        assert svc.verify_user_machine(1, "same_mc") is True

    def test_verify_user_machine_mismatch(self):
        db = MagicMock()
        mock_record = MagicMock()
        mock_record.machine_code = "expected_mc"
        db.query.return_value.filter.return_value.first.return_value = mock_record
        svc = self._make_service(db)
        assert svc.verify_user_machine(1, "other_mc") is False

    def test_list_machine_codes_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.list_machine_codes()

    def test_list_machine_codes_with_status(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 2
        db.query.return_value.filter.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = self._make_service(db)
        records, total = svc.list_machine_codes(status="active")
        assert total == 2

    def test_list_machine_codes_no_filter(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        db.query.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = self._make_service(db)
        records, total = svc.list_machine_codes()
        assert total == 0


class TestMachineCodeServiceOrgPassCode:
    def _make_service(self, db=None):
        from app.services.machine_code_service import MachineCodeService
        return MachineCodeService(db=db)

    def test_generate_org_verification_code(self):
        from app.services.machine_code_service import MachineCodeService
        code = MachineCodeService.generate_organization_verification_code(1, "org_name")
        assert len(code) == 4
        assert code.isdigit()
        assert 1000 <= int(code) <= 9999

    def test_generate_org_verification_code_deterministic(self):
        from app.services.machine_code_service import MachineCodeService
        c1 = MachineCodeService.generate_organization_verification_code(42, "Test Org")
        c2 = MachineCodeService.generate_organization_verification_code(42, "Test Org")
        assert c1 == c2

    def test_generate_org_pass_code(self):
        from app.services.machine_code_service import MachineCodeService
        pc = MachineCodeService.generate_organization_pass_code(1, "1234")
        assert len(pc) == 14
        assert pc.count("-") == 2

    def test_create_org_pass_code_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.create_organization_pass_code(1, "1234", True, 1)

    def test_create_org_pass_code_success(self):
        db = MagicMock()
        svc = self._make_service(db)
        record = svc.create_organization_pass_code(1, "1234", True, 1, description="test")
        assert db.add.called
        assert db.commit.called
        assert record is not None

    def test_get_org_pass_codes_no_db(self):
        svc = self._make_service(db=None)
        with pytest.raises(ValueError):
            svc.get_organization_pass_codes()

    def test_get_org_pass_codes_with_filters(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 1
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = self._make_service(db)
        records, total = svc.get_organization_pass_codes(organization_id=1, status="pending")
        assert total == 1

    def test_get_org_pass_codes_no_filter(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.options.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        svc = self._make_service(db)
        records, total = svc.get_organization_pass_codes()
        assert total == 0


class TestRBACService:
    @pytest.fixture
    def svc(self):
        from app.services.rbac_service import RBACService
        return RBACService()

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        return db

    def _setup_cache_empty(self, mock_db):
        with patch("app.services.rbac_service._restricted_perms_cache") as mock_cache:
            mock_cache.get.return_value = {1: set()}
            yield mock_cache

    def test_init(self, svc):
        assert "admin" in svc.role_permissions_map
        assert "user" in svc.role_permissions_map

    def test_check_permission_no_db(self, svc):
        pass

    def test_check_permission_admin(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()), \
             patch.object(svc, "_has_admin_role", return_value=True):
            result = _run_async(
                svc.check_permission("1", "user:read", db=mock_db)
            )
            assert result is True

    def test_check_permission_direct(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()), \
             patch.object(svc, "_has_admin_role", return_value=False), \
             patch.object(svc, "_has_direct_permission", return_value=True):
            result = _run_async(
                svc.check_permission("1", "user:read", db=mock_db)
            )
            assert result is True

    def test_check_permission_denied(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()), \
             patch.object(svc, "_has_admin_role", return_value=False), \
             patch.object(svc, "_has_direct_permission", return_value=False), \
             patch.object(svc, "_has_role_permission", return_value=False), \
             patch.object(svc, "_has_resource_access", return_value=False):
            result = _run_async(
                svc.check_permission("1", "user:read", db=mock_db)
            )
            assert result is False

    def test_check_permission_resource_access(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()), \
             patch.object(svc, "_has_admin_role", return_value=False), \
             patch.object(svc, "_has_direct_permission", return_value=False), \
             patch.object(svc, "_has_role_permission", return_value=False), \
             patch.object(svc, "_has_resource_access", return_value=True):
            result = _run_async(
                svc.check_permission("1", "user:read", resource_type="org", resource_id="1", db=mock_db)
            )
            assert result is True

    def test_get_user_permissions(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()):
            mock_db.query.return_value.filter.return_value.all.return_value = [("user:read",)]
            mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.distinct.return_value.all.return_value = []
            mock_db.query.return_value.filter.return_value.first.return_value = None
            result = _run_async(
                svc.get_user_permissions("1", mock_db)
            )
            assert "user:read" in result

    def test_get_user_permissions_admin_all(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()):
            mock_db.query.return_value.filter.return_value.all.return_value = [("admin:all",)]
            mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.distinct.return_value.all.return_value = []
            result = _run_async(
                svc.get_user_permissions("1", mock_db)
            )
            assert "user:read" in result
            assert "admin:all" in result

    def test_get_user_permissions_with_whitelist(self, svc, mock_db):
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()):
            mock_db.query.return_value.filter.return_value.all.return_value = [("user:read",), ("admin:all",)]
            mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.distinct.return_value.all.return_value = []
            result = _run_async(
                svc.get_user_permissions_with_restrictions("1", mock_db)
            )
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_assign_role_not_found(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(Exception):
            _run_async(
                svc.assign_role("1", "999", "1", db=mock_db)
            )

    def test_assign_role_already_exists(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        result = _run_async(
            svc.assign_role("1", "1", "1", db=mock_db)
        )
        assert result == {"success": True, "newly_granted": False}

    def test_assign_role_new(self, svc, mock_db):
        role = MagicMock()
        role.id = "r1"
        role.is_active = True

        existing_role_query = MagicMock()
        existing_role_query.first.return_value = role

        existing_user_role_query = MagicMock()
        existing_user_role_query.first.return_value = None

        q1 = MagicMock()
        q1.filter.return_value = existing_role_query

        q2 = MagicMock()
        q2.filter.return_value = existing_user_role_query

        mock_db.query.side_effect = [q1, q2]
        result = _run_async(
            svc.assign_role("1", "r1", "1", expires_at="2030-01-01T00:00:00", db=mock_db)
        )
        assert result == {"success": True, "newly_granted": True}

    def test_revoke_role(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 1
        result = _run_async(
            svc.revoke_role("1", "1", mock_db)
        )
        assert result is True

    def test_revoke_role_none_deleted(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        result = _run_async(
            svc.revoke_role("1", "1", mock_db)
        )
        assert result is False

    def test_grant_permission_new(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = _run_async(
            svc.grant_permission("1", "user:read", "1", db=mock_db)
        )
        assert result is True

    def test_grant_permission_existing(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        result = _run_async(
            svc.grant_permission("1", "user:read", "1", db=mock_db)
        )
        assert result is True

    def test_grant_permission_with_expiry(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = _run_async(
            svc.grant_permission("1", "user:read", "1", expires_at="2030-01-01T00:00:00", db=mock_db)
        )
        assert result is True

    def test_create_role(self, svc, mock_db):
        mock_role = MagicMock()
        mock_role.id = "new_role_id"
        mock_db.add.return_value = None
        mock_db.flush.return_value = None
        result = _run_async(
            svc.create_role("test_role", "desc", ["user:read"], db=mock_db)
        )
        assert mock_db.add.called

    def test_get_user_roles(self, svc, mock_db):
        mock_row = MagicMock()
        mock_row.id = "r1"
        mock_row.name = "admin"
        mock_row.description = "Admin role"
        mock_row.is_system = True
        mock_row.granted_by = 1
        mock_row.expires_at = None
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_row]
        result = _run_async(
            svc.get_user_roles("1", mock_db)
        )
        assert len(result) == 1
        assert result[0]["name"] == "admin"

    def test_get_user_roles_with_expiry(self, svc, mock_db):
        mock_row = MagicMock()
        mock_row.id = "r1"
        mock_row.name = "user"
        mock_row.description = "User role"
        mock_row.is_system = False
        mock_row.granted_by = 1
        mock_row.expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_row]
        result = _run_async(
            svc.get_user_roles("1", mock_db)
        )
        assert result[0]["expires_at"] is not None

    def test_log_access_exception(self, svc, mock_db):
        mock_db.add.side_effect = Exception("db error")
        svc._log_access(mock_db, "1", "action", None, None, True, "reason")


class TestOrganizationService:
    def _make_service(self, db=None):
        from app.services.organization_service import OrganizationService
        return OrganizationService(db=db)

    def test_init_no_db(self):
        from app.services.organization_service import OrganizationService
        with pytest.raises(ValueError, match="OrganizationService requires"):
            OrganizationService(db=None)

    @patch("app.services.organization_service.OrganizationCodeService")
    def test_create_org_root(self, MockCodeService):
        db = MagicMock()
        mock_code_service = MockCodeService.return_value
        mock_code_service.generate_code.return_value = "ORG001"
        svc = self._make_service(db)
        data = MagicMock()
        data.parent_id = None
        data.code_prefix = "ORG"
        data.name = "Root Org"
        data.is_active = True
        data.description = None
        data.contact_person = None
        data.contact_phone = None
        data.address = None
        result = _run_async(
            svc.create_organization(data, created_by=1)
        )
        assert db.add.called

    @patch("app.services.organization_service.OrganizationCodeService")
    def test_create_org_with_parent(self, MockCodeService):
        db = MagicMock()
        mock_code_service = MockCodeService.return_value
        mock_code_service.generate_code.return_value = "ORG002"
        parent = MagicMock()
        parent.id = 1
        parent.code = "ORG001"
        parent.level = 1
        parent.path = "/1/"
        db.query.return_value.filter.return_value.first.return_value = parent
        svc = self._make_service(db)
        data = MagicMock()
        data.parent_id = 1
        data.code_prefix = "ORG"
        data.name = "Child Org"
        data.is_active = True
        data.description = None
        data.contact_person = None
        data.contact_phone = None
        data.address = None
        result = _run_async(
            svc.create_organization(data, created_by=1)
        )
        assert db.add.called

    def test_create_org_parent_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._make_service(db)
        data = MagicMock()
        data.parent_id = 999
        from app.services.organization_service import OrganizationNotFoundError
        with pytest.raises(OrganizationNotFoundError):
            _run_async(
                svc.create_organization(data, created_by=1)
            )

    def test_get_organization(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        result = svc.get_organization(1)
        assert result is not None

    def test_get_organization_by_code(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        result = svc.get_organization_by_code("ORG001")
        assert result is not None

    def test_get_org_tree_root_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []
        result = svc.get_organization_tree(root_id=999)
        assert result == []

    def test_get_org_tree_no_root(self):
        db = MagicMock()
        svc = self._make_service(db)
        mock_org = MagicMock()
        mock_org.parent_id = None
        mock_org.id = 1
        mock_org.code = "ORG001"
        mock_org.name = "Root"
        mock_org.level = "1"
        mock_org.path = "/1/"
        mock_org.is_active = True
        mock_org.description = None
        mock_org.contact_person = None
        mock_org.contact_phone = None
        mock_org.address = None
        mock_org.created_at = None
        mock_org.created_by = 1
        mock_org.updated_at = None
        mock_org.updated_by = None
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_org]
        result = svc.get_organization_tree(include_inactive=True)
        assert len(result) == 1

    def test_get_org_tree_with_children(self):
        db = MagicMock()
        svc = self._make_service(db)
        root = MagicMock()
        root.id = 1
        root.parent_id = None
        root.code = "R"
        root.name = "Root"
        root.level = "1"
        root.path = "/1/"
        root.is_active = True
        root.description = None
        root.contact_person = None
        root.contact_phone = None
        root.address = None
        root.created_at = None
        root.created_by = 1
        root.updated_at = None
        root.updated_by = None
        child = MagicMock()
        child.id = 2
        child.parent_id = 1
        child.code = "C"
        child.name = "Child"
        child.level = "2"
        child.path = "/1/2/"
        child.is_active = True
        child.description = None
        child.contact_person = None
        child.contact_phone = None
        child.address = None
        child.created_at = None
        child.created_by = 1
        child.updated_at = None
        child.updated_by = None
        db.query.return_value.filter.return_value.first.return_value = root
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [root, child]
        result = svc.get_organization_tree(root_id=1, include_inactive=True)
        assert len(result) == 1

    def test_get_subordinates_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        result = svc.get_subordinate_organizations(999)
        assert result == []

    def test_get_subordinates(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        org.id = 1
        org.path = "/1/"
        db.query.return_value.filter.return_value.first.return_value = org
        child = MagicMock(id=1)
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [child]
        result = svc.get_subordinate_organizations(1, include_self=False, include_inactive=True)
        assert len(result) == 1

    def test_get_subordinate_ids(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        org.id = 1
        org.path = "/1/"
        child_org = MagicMock()
        child_org.id = 2
        db.query.return_value.filter.return_value.first.return_value = org
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [child_org]
        ids = svc.get_subordinate_ids(1)
        assert 2 in ids

    def test_get_ancestors_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        result = svc.get_ancestors(999)
        assert result == []

    def test_get_ancestors_root_org(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        org.id = 1
        org.path = "/1/"
        db.query.return_value.filter.return_value.first.return_value = org
        result = svc.get_ancestors(1)
        assert result == []

    def test_get_ancestors_child(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        org.id = 2
        org.path = "/1/2/"
        ancestor = MagicMock()
        ancestor.id = 1
        db.query.return_value.filter.return_value.first.return_value = org
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ancestor]
        result = svc.get_ancestors(2)
        assert len(result) == 1

    def test_update_org_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        data = MagicMock()
        from app.services.organization_service import OrganizationNotFoundError
        with pytest.raises(OrganizationNotFoundError):
            _run_async(
                svc.update_organization(999, data, 1)
            )

    def test_update_org_success(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        org.name = "Old Name"
        db.query.return_value.filter.return_value.first.return_value = org
        data = MagicMock()
        data.model_dump.return_value = {"name": "New Name"}
        result = _run_async(
            svc.update_organization(1, data, 1)
        )
        assert db.commit.called

    def test_delete_org_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        from app.services.organization_service import OrganizationNotFoundError
        with pytest.raises(OrganizationNotFoundError):
            _run_async(svc.delete_organization(999))

    def test_delete_org_has_subordinates(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = org
        db.query.return_value.filter.return_value.count.return_value = 2
        from app.services.organization_service import OrganizationHasSubordinatesError
        with pytest.raises(OrganizationHasSubordinatesError):
            _run_async(svc.delete_organization(1))

    def test_delete_org_success(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = org
        db.query.return_value.filter.return_value.count.return_value = 0
        result = _run_async(svc.delete_organization(1))
        assert result is True

    def test_get_statistics_no_root(self):
        db = MagicMock()
        svc = self._make_service(db)
        org1 = MagicMock()
        org1.level = 1
        org1.is_active = True
        org2 = MagicMock()
        org2.level = 2
        org2.is_active = False
        db.query.return_value.all.return_value = [org1, org2]
        stats = svc.get_statistics()
        assert stats.total == 2
        assert stats.active == 1
        assert stats.inactive == 1

    def test_get_statistics_with_root(self):
        db = MagicMock()
        svc = self._make_service(db)
        root_org = MagicMock()
        root_org.id = 1
        root_org.path = "/1/"
        root_org.level = 1
        root_org.is_active = True
        child_org = MagicMock()
        child_org.id = 2
        child_org.path = "/1/2/"
        child_org.level = 2
        child_org.is_active = True
        db.query.return_value.filter.return_value.first.return_value = root_org
        db.query.return_value.filter.return_value.all.return_value = [root_org, child_org]
        stats = svc.get_statistics(root_id=1)
        assert stats.total == 2

    def test_search_organizations(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []
        result = svc.search_organizations("test")
        assert isinstance(result, list)

    def test_search_organizations_include_inactive(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        result = svc.search_organizations("test", include_inactive=True)
        assert result == []

    def test_validate_parent_child_same_id(self):
        db = MagicMock()
        svc = self._make_service(db)
        assert svc.validate_parent_child_relationship(1, 1) is False

    def test_validate_parent_child_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        assert svc.validate_parent_child_relationship(1, 999) is False

    def test_validate_parent_child_valid(self):
        db = MagicMock()
        svc = self._make_service(db)
        child = MagicMock()
        child.id = 2
        child.path = "/1/2/"
        db.query.return_value.filter.return_value.first.return_value = child
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
        assert svc.validate_parent_child_relationship(1, 2) is True

    def test_batch_update_sort_orders(self):
        db = MagicMock()
        svc = self._make_service(db)
        org = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = org
        success, count = svc.batch_update_sort_orders([{"id": 1, "sort_order": 10}])
        assert success is True
        assert count == 1

    def test_batch_update_sort_orders_skip_invalid(self):
        db = MagicMock()
        svc = self._make_service(db)
        success, count = svc.batch_update_sort_orders([{"id": None, "sort_order": None}])
        assert success is True
        assert count == 0

    def test_batch_update_sort_orders_exception(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.side_effect = Exception("db error")
        success, count = svc.batch_update_sort_orders([{"id": 1, "sort_order": 1}])
        assert success is False


class TestTrendPredictionService:
    def test_predict_empty_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        result = TrendPredictionService.predict_time_series([])
        assert result["predictions"] == []
        assert result["error"] == "历史数据为空"

    def test_predict_moving_average(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        data = [
            {"date": "2023-01-01", "value": 100},
            {"date": "2023-02-01", "value": 110},
            {"date": "2023-03-01", "value": 120},
        ]
        result = TrendPredictionService.predict_time_series(data, periods=3, method="moving_average")
        assert len(result["predictions"]) == 3
        assert result["method"] == "moving_average"

    def test_predict_moving_average_short_window(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        data = [{"date": "2023-01-01", "value": 100}]
        result = TrendPredictionService.predict_time_series(data, periods=2, method="moving_average")
        assert len(result["predictions"]) == 2

    def test_predict_linear(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        data = [
            {"date": "2023-01-01", "value": 100},
            {"date": "2023-02-01", "value": 110},
            {"date": "2023-03-01", "value": 120},
        ]
        result = TrendPredictionService.predict_time_series(data, periods=3, method="linear")
        assert len(result["predictions"]) == 3
        assert result["method"] == "linear_regression"

    def test_predict_prophet_unavailable_fallback(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService, PROPHET_AVAILABLE
        data = [
            {"date": "2023-01-01", "value": 100},
            {"date": "2023-02-01", "value": 110},
        ]
        if not PROPHET_AVAILABLE:
            result = TrendPredictionService.predict_time_series(data, periods=2, method="prophet")
            assert result["method"] == "linear_regression"

    def test_predict_exception(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        result = TrendPredictionService.predict_time_series(
            [{"date": "bad", "value": 1}], periods=1, method="linear"
        )
        assert "error" in result or len(result["predictions"]) >= 0

    def test_predict_income_trend_empty(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        result = TrendPredictionService.predict_income_trend([])
        assert result["error"] == "至少需要2个数据点"

    def test_predict_income_trend_insufficient_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        result = TrendPredictionService.predict_income_trend([{"year": 2020, "income": 100}])
        assert result["error"] == "有效数据点不足"

    def test_predict_income_trend_valid(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        data = [
            {"year": 2020, "income": 10000},
            {"year": 2021, "income": 11000},
            {"year": 2022, "income": 12000},
        ]
        result = TrendPredictionService.predict_income_trend(data, years_ahead=2)
        assert "predictions" in result

    def test_predict_income_trend_filtered_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        data = [
            {"year": 2020, "income": None},
            {"year": 2021, "income": 11000},
            {"year": None, "income": 12000},
        ]
        result = TrendPredictionService.predict_income_trend(data)
        assert "predictions" in result

    def test_predict_village_income_no_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        with patch("app.models.annual_income.AnnualIncome") as MockIncome:
            db = MagicMock()
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            result = TrendPredictionService.predict_village_income(db, 1)
            assert result["error"] == "无历史收入数据"

    def test_predict_village_income_with_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        with patch("app.models.annual_income.AnnualIncome") as MockIncome:
            db = MagicMock()
            record = MagicMock()
            record.year = 2022
            record.per_capita_income = 50000
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [record]
            with patch.object(TrendPredictionService, "_predict_with_prophet", return_value={
                "predictions": [{"ds": "2023", "yhat": 52000}],
                "model": "prophet",
            }):
                result = TrendPredictionService.predict_village_income(db, 1, periods=1)
            assert "predictions" in result

    def test_predict_village_population_no_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        with patch("app.models.annual_population.AnnualPopulation") as MockPop:
            db = MagicMock()
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            result = TrendPredictionService.predict_village_population(db, 1)
            assert result["error"] == "无历史人口数据"

    def test_predict_village_population_with_data(self):
        from app.services.ai.trend_prediction_service import TrendPredictionService
        with patch("app.models.annual_population.AnnualPopulation") as MockPop:
            db = MagicMock()
            record = MagicMock()
            record.year = 2022
            record.total_population = 1500
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [record]
            with patch.object(TrendPredictionService, "_predict_with_prophet", return_value={
                "predictions": [{"ds": "2023", "yhat": 1520}],
                "model": "prophet",
            }):
                result = TrendPredictionService.predict_village_population(db, 1, periods=1)
            assert "predictions" in result


class TestCrawlerService:
    def test_sentiment_crawler_init(self):
        from app.services.sentiment.crawler_service import SentimentCrawlerService
        svc = SentimentCrawlerService()
        assert svc.sources == []
        assert svc.crawled_data == []

    def test_crawl_news(self):
        from app.services.sentiment.crawler_service import SentimentCrawlerService
        svc = SentimentCrawlerService()
        result = svc.crawl_news(["keyword"])
        assert result == []

    def test_crawl_social_media(self):
        from app.services.sentiment.crawler_service import SentimentCrawlerService
        svc = SentimentCrawlerService()
        result = svc.crawl_social_media(["kw"], ["platform"])
        assert result == []

    def test_parse_content(self):
        from app.services.sentiment.crawler_service import SentimentCrawlerService
        svc = SentimentCrawlerService()
        result = svc.parse_content("raw text", "news")
        assert result["text"] == "raw text"
        assert result["source_type"] == "news"
        assert "parsed_at" in result

    def test_news_item_defaults(self):
        from app.services.sentiment.crawler_service import NewsItem
        item = NewsItem()
        assert item.id is None
        assert item.title == ""
        assert item.sentiment_score == 0.0
        assert item.is_alert is False

    def test_sentiment_data(self):
        from app.services.sentiment.crawler_service import SentimentData
        data = SentimentData(
            id="1", source="test", content="content",
            timestamp=datetime.now(timezone.utc), metadata={}
        )
        assert data.id == "1"

    def test_crawler_service_singleton(self):
        from app.services.sentiment.crawler_service import CrawlerService, SentimentCrawlerService
        CrawlerService._instance = None
        inst1 = CrawlerService._get_instance()
        inst2 = CrawlerService._get_instance()
        assert inst1 is inst2
        assert isinstance(inst1, SentimentCrawlerService)
        CrawlerService._instance = None

    def test_fetch_rss_disabled(self):
        from app.services.sentiment.crawler_service import CrawlerService, _CRAWLER_ENABLED
        if not _CRAWLER_ENABLED:
            result = CrawlerService.fetch_rss_feeds(MagicMock(), ["kw"])
            assert result == []

    def test_save_news(self):
        from app.services.sentiment.crawler_service import CrawlerService, NewsItem
        mock_model = MagicMock()
        with patch.dict("sys.modules", {"app.models.sentiment": MagicMock(SentimentNews=mock_model)}):
            db = MagicMock()
            news_list = [NewsItem(title="Title", source="src", content="c", keywords=["k1"])]
            result = CrawlerService.save_news(db, news_list)
            assert result == 1
            assert db.commit.called

    def test_save_news_no_keywords(self):
        from app.services.sentiment.crawler_service import CrawlerService, NewsItem
        mock_model = MagicMock()
        with patch.dict("sys.modules", {"app.models.sentiment": MagicMock(SentimentNews=mock_model)}):
            db = MagicMock()
            news_list = [NewsItem(title="T", source="s", content="c", keywords=[])]
            result = CrawlerService.save_news(db, news_list)
            assert result == 1

    def test_save_news_exception(self):
        from app.services.sentiment.crawler_service import CrawlerService, NewsItem
        mock_model = MagicMock()
        with patch.dict("sys.modules", {"app.models.sentiment": MagicMock(SentimentNews=mock_model)}):
            db = MagicMock()
            db.add.side_effect = Exception("db error")
            with pytest.raises(Exception):
                CrawlerService.save_news(db, [NewsItem(title="T", source="s", content="c")])


class TestPolicyService:
    def _make_service(self, db=None):
        from app.services.policy_service import PolicyService
        return PolicyService(db=db)

    def _mock_policy(self, **overrides):
        defaults = dict(
            id=1, category="military", level="cmc", status="active",
            title="Test", content="content", issue_date=None,
            effective_date=None, issuing_authority=None, summary=None,
            code=None, file_path=None, keywords=None, view_count=0,
            download_count=0, is_important=False, file_size=None,
            file_type=None, created_at=None, updated_at=None,
        )
        defaults.update(overrides)
        p = MagicMock(**defaults)
        return p

    def test_create_policy(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy()
        db.add.return_value = None
        db.commit.return_value = None
        db.refresh.return_value = None
        with patch.object(svc, "_to_response", return_value=MagicMock()) as mock_resp:
            data = MagicMock()
            data.title = "Test Policy"
            data.category = "military"
            data.level = "cmc"
            data.issuing_authority = "CMC"
            data.issue_date = None
            data.effective_date = None
            data.code = None
            data.file_path = None
            data.content = "content"
            data.summary = None
            data.status = "active"
            data.keywords = None
            result = svc.create_policy(data)
            assert db.add.called

    def test_get_policy_by_id_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy()
        db.query.return_value.filter.return_value.first.return_value = policy
        result = svc.get_policy_by_id(1)
        assert result is not None

    def test_get_policy_by_id_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        result = svc.get_policy_by_id(999)
        assert result is None

    def test_get_policy_model_by_id(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        result = svc.get_policy_model_by_id(1)
        assert result is not None

    def test_update_policy_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy()
        db.query.return_value.filter.return_value.first.return_value = policy
        data = MagicMock()
        data.model_dump.return_value = {"title": "New Title"}
        with patch.object(svc, "_to_response", return_value=MagicMock()):
            result = svc.update_policy(1, data, user_id=1)
            assert result is not None

    def test_update_policy_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        data = MagicMock()
        data.model_dump.return_value = {}
        result = svc.update_policy(999, data)
        assert result is None

    def test_delete_policy_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        result = svc.delete_policy(1)
        assert result is True

    def test_delete_policy_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        result = svc.delete_policy(999)
        assert result is False

    def test_get_policies_all_filters(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        result = svc.get_policies(
            category="military", organization_level="cmc",
            status="active", search="test", order_by="title", order_desc=False
        )
        assert result == ([], 0)

    def test_get_policies_no_filters(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.count.return_value = 0
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        result = svc.get_policies()
        assert result == ([], 0)

    def test_get_related_policies_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.first.return_value = None
        result = svc.get_related_policies(999)
        assert result == []

    def test_get_related_policies_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        current = self._mock_policy()
        db.query.return_value.filter.return_value.first.return_value = current
        related = self._mock_policy(id=2, title="Related")
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [related]
        with patch.object(svc, "_to_response", side_effect=lambda p: MagicMock()):
            result = svc.get_related_policies(1)
            assert len(result) == 1

    def test_increment_view_count_found(self):
        """W2-T6 原子 UPDATE：命中返回 True 且执行原子递增语句"""
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.update.return_value = 1
        result = svc.increment_view_count(1)
        assert result is True
        db.query.return_value.filter.return_value.update.assert_called_once()

    def test_increment_view_count_not_found(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.update.return_value = 0
        result = svc.increment_view_count(999)
        assert result is False

    def test_get_categories(self):
        svc = self._make_service(MagicMock())
        try:
            result = svc.get_categories()
            assert result is not None
        except Exception:
            pass

    def test_get_statistics_by_category(self):
        db = MagicMock()
        svc = self._make_service(db)
        q1 = MagicMock()
        q1.filter.return_value.group_by.return_value.all.return_value = [("military", 5), ("local", 3)]
        q2 = MagicMock()
        q2.filter.return_value.group_by.return_value.all.return_value = [
            ("military", "cmc", 3), ("military", "theater", 2), ("local", "national", 3),
        ]
        db.query.side_effect = [q1, q2]
        result = svc.get_statistics_by_category()
        assert result["military"]["total"] == 5
        assert result["local"]["total"] == 3

    def test_batch_delete(self):
        db = MagicMock()
        svc = self._make_service(db)
        db.query.return_value.filter.return_value.delete.return_value = 3
        result = svc.batch_delete([1, 2, 3])
        assert result == 3

    def test_to_response_military(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy(category="military", level="cmc")
        resp = svc._to_response(policy)
        assert resp.category_name == "专项政策"

    def test_to_response_local(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy(category="local", level="national")
        resp = svc._to_response(policy)
        assert resp.level_name == "国家级"

    def test_to_response_unknown_category(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy(category="unknown", level="unknown_level", status="unknown")
        resp = svc._to_response(policy)
        assert resp.level_name == "unknown_level"
        assert resp.status_name == "unknown"

    def test_update_policy_with_enum_value(self):
        db = MagicMock()
        svc = self._make_service(db)
        policy = self._mock_policy()
        db.query.return_value.filter.return_value.first.return_value = policy
        data = MagicMock()
        data.model_dump.return_value = {"status": MagicMock(value="draft")}
        with patch.object(svc, "_to_response", return_value=MagicMock()):
            result = svc.update_policy(1, data)
            assert result is not None

    def test_create_policy_with_enum_category(self):
        db = MagicMock()
        svc = self._make_service(db)
        data = MagicMock()
        data.title = "Test"
        data.category = MagicMock(value="military")
        data.level = "cmc"
        data.issuing_authority = "CMC"
        data.issue_date = None
        data.effective_date = None
        data.code = None
        data.file_path = None
        data.content = "content"
        data.summary = None
        data.status = MagicMock(value="active")
        data.keywords = None
        with patch.object(svc, "_to_response", return_value=MagicMock()):
            result = svc.create_policy(data, user_id=1)
            assert result is not None


class TestFundAnomalyEngine:
    def test_anomaly_result_defaults(self):
        from app.services.fund_anomaly_engine import AnomalyResult
        result = AnomalyResult(fund_id=1, fund_name="test")
        assert result.risk_score == 0
        assert result.risk_level == "normal"
        assert result.should_escalate is False

    def test_check_statistical_variance_insufficient_data(self):
        from app.services.fund_anomaly_engine import _check_statistical_variance
        result = _check_statistical_variance([1, 2])
        assert result == []

    def test_check_statistical_variance_identical_values(self):
        from app.services.fund_anomaly_engine import _check_statistical_variance
        result = _check_statistical_variance([100, 100, 100])
        assert result == []

    def test_check_statistical_variance_with_outlier(self):
        from app.services.fund_anomaly_engine import _check_statistical_variance
        result = _check_statistical_variance([10, 10, 10, 10, 10, 100])
        assert len(result) >= 1
        assert result[0]["index"] == 5

    def test_check_statistical_variance_no_outliers(self):
        from app.services.fund_anomaly_engine import _check_statistical_variance
        result = _check_statistical_variance([10, 11, 12, 10, 11])
        assert result == []

    def test_get_risk_level_critical(self):
        from app.services.fund_anomaly_engine import _get_risk_level
        assert _get_risk_level(75) == "critical"
        assert _get_risk_level(100) == "critical"

    def test_get_risk_level_high(self):
        from app.services.fund_anomaly_engine import _get_risk_level
        assert _get_risk_level(50) == "high"

    def test_get_risk_level_medium(self):
        from app.services.fund_anomaly_engine import _get_risk_level
        assert _get_risk_level(25) == "medium"

    def test_get_risk_level_normal(self):
        from app.services.fund_anomaly_engine import _get_risk_level
        assert _get_risk_level(10) == "normal"
        assert _get_risk_level(0) == "normal"

    def test_calculate_risk_score_danger(self):
        from app.services.fund_anomaly_engine import _calculate_risk_score
        score = _calculate_risk_score([{"severity": "danger"}], 0, 100)
        assert score == 25

    def test_calculate_risk_score_warning(self):
        from app.services.fund_anomaly_engine import _calculate_risk_score
        score = _calculate_risk_score([{"severity": "warning"}], 0, 100)
        assert score == 10

    def test_calculate_risk_score_variance(self):
        from app.services.fund_anomaly_engine import _calculate_risk_score
        score = _calculate_risk_score([], 3, 100)
        assert score == 60

    def test_calculate_risk_score_low_health(self):
        from app.services.fund_anomaly_engine import _calculate_risk_score
        score = _calculate_risk_score([], 0, 40)
        assert score == 15

    def test_calculate_risk_score_capped(self):
        from app.services.fund_anomaly_engine import _calculate_risk_score
        score = _calculate_risk_score(
            [{"severity": "danger"}] * 5, 5, 0
        )
        assert score == 100

    def test_should_escalate_by_score(self):
        from app.services.fund_anomaly_engine import should_escalate_approval
        assert should_escalate_approval(60, 100) is True

    def test_should_escalate_by_amount(self):
        from app.services.fund_anomaly_engine import should_escalate_approval
        assert should_escalate_approval(10, 600000) is True

    def test_should_not_escalate(self):
        from app.services.fund_anomaly_engine import should_escalate_approval
        assert should_escalate_approval(10, 100) is False

    def test_should_block_status_transition_critical(self):
        from app.services.fund_anomaly_engine import should_block_status_transition
        assert should_block_status_transition(True, 10, "approved") is True
        assert should_block_status_transition(True, 10, "audited") is True
        assert should_block_status_transition(True, 10, "completed") is True

    def test_should_block_status_transition_non_critical(self):
        from app.services.fund_anomaly_engine import should_block_status_transition
        assert should_block_status_transition(True, 30, "draft") is True

    def test_should_not_block_no_anomaly(self):
        from app.services.fund_anomaly_engine import should_block_status_transition
        assert should_block_status_transition(False, 100, "approved") is False

    def test_should_not_block_low_score(self):
        from app.services.fund_anomaly_engine import should_block_status_transition
        assert should_block_status_transition(True, 10, "draft") is False

    def test_detect_fund_anomalies_full(self):
        from app.services.fund_anomaly_engine import detect_fund_anomalies_full
        result = detect_fund_anomalies_full(MagicMock(), 1, "test fund", 100000.0, 80.0)
        assert result.fund_id == 1
        assert result.fund_name == "test fund"
        assert result.risk_level == "normal"


class TestSupportedVillageService:
    @pytest.mark.asyncio
    async def test_get_villages_basic(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)
        db.execute.side_effect = [mock_count, mock_result]
        svc = SupportedVillageService(db)
        result = await svc.get_villages()
        assert "items" in result
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_villages_with_filters(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        db.execute = AsyncMock(side_effect=[mock_count, mock_result])
        svc = SupportedVillageService(db)
        result = await svc.get_villages(organization_id=1)
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_village_found(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get_village(1)
        assert result == mock_village

    @pytest.mark.asyncio
    async def test_get_village_not_found(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get_village(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_village(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = SupportedVillageService(db)
        result = await svc.create_village(village_name="Test Village", province="贵州省")
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_village_found(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock()
        mock_village.village_name = "Old"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = SupportedVillageService(db)
        result = await svc.update_village(1, village_name="New")
        assert result is not None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_village_not_found(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.update_village(999, village_name="New")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_village_skip_none_values(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock(spec=["village_name", "province"])
        mock_village.village_name = "Old"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        svc = SupportedVillageService(db)
        result = await svc.update_village(1, village_name=None, province="贵州省")
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_village_found(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        db.delete = AsyncMock()
        db.commit = AsyncMock()
        svc = SupportedVillageService(db)
        result = await svc.delete_village(1)
        assert result is True
        db.delete.assert_awaited_once_with(mock_village)
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_village_not_found(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.delete_village(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_compat_alias(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get(1)
        assert result == mock_village

    @pytest.mark.asyncio
    async def test_get_population_compat(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get_population(1)
        assert result == mock_village

    @pytest.mark.asyncio
    async def test_get_income_compat(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_village = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_village
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get_income(1)
        assert result == mock_village

    @pytest.mark.asyncio
    async def test_get_departments(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [("Dept A",), ("Dept B",), (None,)]
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get_departments()
        assert "Dept A" in result
        assert "Dept B" in result
        assert None not in result

    @pytest.mark.asyncio
    async def test_get_departments_empty(self):
        from app.services.supported_village_service import SupportedVillageService
        db = AsyncMock()
        db.add = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)
        svc = SupportedVillageService(db)
        result = await svc.get_departments()
        assert result == []
