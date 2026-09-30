"""OCR 深审第二轮：资源级授权级别必须由请求的权限派生（rbac_service.py:200）。

历史实现：check_permission 的资源权限回退恒传字面 "write" →
(a) 只读资源授权（access_level="read"）永远无法满足检查；
(b) 仅 write 级授权可满足同资源 delete/export/publish 等任意权限检查。
"""

from unittest.mock import MagicMock, patch

from app.services.rbac_service import (
    RBACService,
    _required_resource_access_level,
)


class TestRequiredResourceAccessLevelMapping:
    def test_read_action_requires_read_level(self):
        assert _required_resource_access_level("village:read") == "read"

    def test_delete_action_requires_delete_level(self):
        assert _required_resource_access_level("village:delete") == "delete"

    def test_other_actions_keep_write_level(self):
        assert _required_resource_access_level("village:write") == "write"
        assert _required_resource_access_level("village:export") == "write"
        assert _required_resource_access_level("admin:all") == "write"

    def test_missing_permission_defaults_to_write(self):
        assert _required_resource_access_level(None) == "write"
        assert _required_resource_access_level("") == "write"

    def test_action_is_case_insensitive_and_stripped(self):
        assert _required_resource_access_level("village: READ ") == "read"


class TestCheckPermissionPassesDerivedLevel:
    async def _run(self, permission: str):
        svc = RBACService()
        db = MagicMock()
        with patch.object(svc, "_get_cached_restricted_permissions", return_value=set()), \
             patch.object(svc, "_has_admin_role", return_value=False), \
             patch.object(svc, "_has_direct_permission", return_value=False), \
             patch.object(svc, "_has_role_permission", return_value=False), \
             patch.object(svc, "_has_resource_access", return_value=True) as spy:
            granted = await svc.check_permission(
                "1", permission, resource_type="village", resource_id="5", db=db
            )
        return granted, spy

    async def test_read_permission_checks_read_level(self):
        granted, spy = await self._run("village:read")
        assert granted is True
        assert spy.call_args.args[3] == "read", "只读授权必须按 read 级别匹配"

    async def test_delete_permission_checks_delete_level(self):
        granted, spy = await self._run("village:delete")
        assert granted is True
        assert spy.call_args.args[3] == "delete", "write 级授权不得满足 delete 检查"

    async def test_export_permission_checks_write_level(self):
        granted, spy = await self._run("village:export")
        assert granted is True
        assert spy.call_args.args[3] == "write"
