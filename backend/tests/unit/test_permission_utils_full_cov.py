"""app.core.permission_utils 全覆盖补充测试。

针对 47% 覆盖率缺口，补齐 is_admin / require_admin（直接调用 + 装饰器 +
无参工厂）/ get_org_with_fallback（新式 + 旧式全分支）/ require_organization /
require_permission / check_permission 的所有分支。

约定：asyncio_mode=auto，async 测试无需显式标记。
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import permission_utils as pu


# ─────────────────────────── is_superuser / is_admin ───────────────────────────


class TestIsSuperuser:
    def test_none_user(self):
        assert pu.is_superuser(None) is False

    def test_is_superuser_attr_true(self):
        assert pu.is_superuser(SimpleNamespace(is_superuser=True, role="user")) is True

    def test_role_super_admin(self):
        assert pu.is_superuser(SimpleNamespace(is_superuser=False, role="super_admin")) is True

    def test_role_not_super(self):
        assert pu.is_superuser(SimpleNamespace(is_superuser=False, role="admin")) is False

    def test_no_attrs(self):
        # 既无 is_superuser（或为 False）也无 role 属性 → 行 37 返回 False
        assert pu.is_superuser(SimpleNamespace(is_superuser=False)) is False


class TestIsAdmin:
    def test_none_user(self):
        assert pu.is_admin(None) is False

    def test_superuser_short_circuit(self):
        # is_superuser True → is_admin True（不检查 role）
        assert pu.is_admin(SimpleNamespace(is_superuser=True)) is True

    def test_role_admin(self):
        assert pu.is_admin(SimpleNamespace(is_superuser=False, role="admin")) is True

    def test_role_super_admin(self):
        assert pu.is_admin(SimpleNamespace(is_superuser=False, role="super_admin")) is True

    def test_role_manager_not_admin(self):
        # manager 不在 ADMIN_ROLES（仅 super_admin/admin）
        assert pu.is_admin(SimpleNamespace(is_superuser=False, role="manager")) is False

    def test_no_role_attr(self):
        # 非 superuser 且无 role 属性 → 行 58 返回 False
        assert pu.is_admin(SimpleNamespace(is_superuser=False)) is False


# ─────────────────────────── require_admin ───────────────────────────


class TestRequireAdminDirectCall:
    """直接调用模式：require_admin(user) —— 第一个参数是有 role 字符串的用户。"""

    def test_admin_passes_returns_none(self):
        admin = SimpleNamespace(role="admin", is_superuser=False)
        assert pu.require_admin(admin) is None

    def test_non_admin_raises_403(self):
        user = SimpleNamespace(role="user", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            pu.require_admin(user)
        assert exc.value.status_code == 403

    def test_custom_error_message(self):
        user = SimpleNamespace(role="user", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            pu.require_admin(user, error_message="仅管理员可执行")
        assert exc.value.detail == "仅管理员可执行"


class TestRequireAdminDecorator:
    """无参装饰器模式：@require_admin。"""

    async def test_allows_admin_kwarg(self):
        @pu.require_admin
        async def endpoint(current_user=None):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False)
        assert await endpoint(current_user=admin) == "ok"

    async def test_rejects_non_admin(self):
        @pu.require_admin
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(role="user", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            await endpoint(current_user=user)
        assert exc.value.status_code == 403

    async def test_missing_user_raises_401(self):
        @pu.require_admin
        async def endpoint():
            return "ok"

        with pytest.raises(HTTPException) as exc:
            await endpoint()
        assert exc.value.status_code == 401

    async def test_positional_user_detected(self):
        # current_user 未在 kwargs → 从 args 中查找带 role 的对象（行 95-98）
        @pu.require_admin
        async def endpoint(user):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False)
        assert await endpoint(admin) == "ok"


class TestRequireAdminFactory:
    """带参工厂模式：@require_admin(error_message=...)。"""

    async def test_custom_message_on_reject(self):
        @pu.require_admin(error_message="需要管理员")
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(role="user", is_superuser=False)
        with pytest.raises(HTTPException) as exc:
            await endpoint(current_user=user)
        assert exc.value.detail == "需要管理员"


# ─────────────────────────── get_user_org_id ───────────────────────────


class TestGetUserOrgId:
    def test_none_user(self):
        assert pu.get_user_org_id(None) is None

    def test_organization_id(self):
        assert pu.get_user_org_id(SimpleNamespace(organization_id=7)) == 7

    def test_org_id_fallback(self):
        assert pu.get_user_org_id(SimpleNamespace(organization_id=None, org_id=9)) == 9

    def test_neither(self):
        assert pu.get_user_org_id(SimpleNamespace(organization_id=None, org_id=None)) is None


# ─────────────────────────── get_org_with_fallback ───────────────────────────


class TestGetOrgWithFallbackNewStyle:
    def test_requested_org_id_wins(self):
        user = SimpleNamespace(organization_id=1)
        result = pu.get_org_with_fallback(current_user=user, requested_org_id=42)
        assert result == 42

    def test_current_user_organization_id(self):
        user = SimpleNamespace(organization_id=5)
        assert pu.get_org_with_fallback(current_user=user) == 5

    def test_current_user_org_id_attr(self):
        user = SimpleNamespace(organization_id=None, org_id=6)
        assert pu.get_org_with_fallback(current_user=user) == 6

    def test_callback_used(self):
        # 无 requested_org_id、用户无 org → 调用回调（行 196-197）
        user = SimpleNamespace()
        assert pu.get_org_with_fallback(
            current_user=user, get_first_org_callback=lambda: 99
        ) == 99

    def test_no_source_returns_none(self):
        assert pu.get_org_with_fallback(current_user=SimpleNamespace()) is None


class TestGetOrgWithFallbackOldStyle:
    def test_positional_user_none(self):
        # 旧式调用（无关键字参数）且 user=None → 行 202-203
        assert pu.get_org_with_fallback(None) is None

    def test_direct_organization_relationship(self):
        org = SimpleNamespace(id=3)
        user = SimpleNamespace(organization=org)
        assert pu.get_org_with_fallback(user) is org

    def test_organization_id_only_returns_none(self):
        # 有 organization_id 但无直接 relationship → 记录 debug 日志并返回 None
        user = SimpleNamespace(organization=None, organization_id=8)
        assert pu.get_org_with_fallback(user) is None

    def test_no_org_info_returns_none(self):
        assert pu.get_org_with_fallback(SimpleNamespace(organization=None)) is None


# ─────────────────────────── require_organization ───────────────────────────


class TestRequireOrganization:
    async def test_admin_skips_check(self):
        @pu.require_organization
        async def endpoint(organization_id=None, current_user=None):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False, organization_id=1)
        assert await endpoint(organization_id=999, current_user=admin) == "ok"

    async def test_non_admin_same_org_allowed(self):
        @pu.require_organization
        async def endpoint(organization_id=None, current_user=None):
            return "ok"

        user = SimpleNamespace(role="user", is_superuser=False, organization_id=2)
        assert await endpoint(organization_id=2, current_user=user) == "ok"

    async def test_non_admin_cross_org_denied(self):
        @pu.require_organization
        async def endpoint(organization_id=None, current_user=None):
            return "ok"

        user = SimpleNamespace(role="user", is_superuser=False, organization_id=2)
        with pytest.raises(HTTPException) as exc:
            await endpoint(organization_id=3, current_user=user)
        assert exc.value.status_code == 403

    async def test_missing_user_raises_401(self):
        @pu.require_organization
        async def endpoint():
            return "ok"

        with pytest.raises(HTTPException) as exc:
            await endpoint()
        assert exc.value.status_code == 401

    async def test_requested_org_none_allowed(self):
        # requested_org_id 为 None → 不做比较，放行（行 260 条件为 False）
        @pu.require_organization
        async def endpoint(organization_id=None, current_user=None):
            return "ok"

        user = SimpleNamespace(role="user", is_superuser=False, organization_id=2)
        assert await endpoint(organization_id=None, current_user=user) == "ok"

    async def test_positional_user_detected(self):
        @pu.require_organization
        async def endpoint(user):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False, organization_id=1)
        assert await endpoint(admin) == "ok"

    async def test_factory_mode_decorates(self):
        # func=None 且带关键字参数 → 返回 decorator（行 232-236），并实际应用
        @pu.require_organization(org_param="org_id")
        async def endpoint(org_id=None, current_user=None):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False, organization_id=1)
        assert await endpoint(org_id=1, current_user=admin) == "ok"


# ─────────────────────────── require_permission ───────────────────────────


class TestRequirePermission:
    async def test_admin_has_permission(self):
        @pu.require_permission("villages:write")
        async def endpoint(current_user=None):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False)
        assert await endpoint(current_user=admin) == "ok"

    async def test_user_with_exact_permission(self):
        # 修复后：require_permission 将 "villages:write" 拆分为
        # resource="villages"、action="write" 传入 check_permission，
        # 普通用户持有精确权限 "villages:write" 即可通过。
        # （原缺陷：整串作为 resource、action="" 拼出 "villages:write:"
        # 尾冒号，普通用户恒 403，仅 "*:*" 通配可过。）
        @pu.require_permission("villages:write")
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(
            role="user", is_superuser=False, permissions=["villages:write"]
        )
        assert await endpoint(current_user=user) == "ok"

    async def test_user_with_wildcard_permission(self):
        # 非管理员持有通配权限 "*:*" → 通过（通配逻辑不受修复影响）
        @pu.require_permission("villages:write")
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(
            role="user", is_superuser=False, permissions=["*:*"]
        )
        assert await endpoint(current_user=user) == "ok"

    async def test_user_with_wildcard_action_permission(self):
        # 非管理员持有 "villages:*" 通配 action → 对 write 操作放行
        @pu.require_permission("villages:write")
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(
            role="user", is_superuser=False, permissions=["villages:*"]
        )
        assert await endpoint(current_user=user) == "ok"

    async def test_user_with_json_string_permission(self):
        # permissions 为 JSON 字符串格式时同样应命中精确权限
        @pu.require_permission("villages:read")
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(
            role="user", is_superuser=False, permissions='["villages:read"]'
        )
        assert await endpoint(current_user=user) == "ok"

    async def test_user_missing_permission_denied(self):
        @pu.require_permission("villages:write")
        async def endpoint(current_user=None):
            return "ok"

        user = SimpleNamespace(role="user", is_superuser=False, permissions=["other:read"])
        with pytest.raises(HTTPException) as exc:
            await endpoint(current_user=user)
        assert exc.value.status_code == 403

    async def test_missing_user_raises_401(self):
        @pu.require_permission("villages:write")
        async def endpoint():
            return "ok"

        with pytest.raises(HTTPException) as exc:
            await endpoint()
        assert exc.value.status_code == 401

    async def test_positional_user_detected(self):
        @pu.require_permission("villages:read")
        async def endpoint(user):
            return "ok"

        admin = SimpleNamespace(role="admin", is_superuser=False)
        assert await endpoint(admin) == "ok"


# ─────────────────────────── check_permission ───────────────────────────


class TestCheckPermission:
    def test_none_user(self):
        assert pu.check_permission(None, "villages", "read") is False

    def test_admin_all_permissions(self):
        admin = SimpleNamespace(role="admin", is_superuser=False)
        assert pu.check_permission(admin, "anything", "write") is True

    def test_no_permissions_attr(self):
        user = SimpleNamespace(role="user", is_superuser=False)
        assert pu.check_permission(user, "villages", "read") is False

    def test_empty_permissions(self):
        user = SimpleNamespace(role="user", is_superuser=False, permissions=[])
        assert pu.check_permission(user, "villages", "read") is False

    def test_permissions_list_match(self):
        user = SimpleNamespace(
            role="user", is_superuser=False, permissions=["villages:read"]
        )
        assert pu.check_permission(user, "villages", "read") is True

    def test_permissions_json_string(self):
        user = SimpleNamespace(
            role="user", is_superuser=False, permissions='["villages:read", "funds:write"]'
        )
        assert pu.check_permission(user, "funds", "write") is True

    def test_permissions_comma_string(self):
        # 非 JSON 字符串 → 逗号分隔解析（行 342-344）
        user = SimpleNamespace(
            role="user", is_superuser=False, permissions="villages:read, funds:write"
        )
        assert pu.check_permission(user, "villages", "read") is True

    def test_wildcard_all(self):
        user = SimpleNamespace(role="user", is_superuser=False, permissions=["*:*"])
        assert pu.check_permission(user, "villages", "read") is True

    def test_wildcard_resource(self):
        user = SimpleNamespace(role="user", is_superuser=False, permissions=["*:read"])
        assert pu.check_permission(user, "villages", "read") is True

    def test_wildcard_action(self):
        user = SimpleNamespace(role="user", is_superuser=False, permissions=["villages:*"])
        assert pu.check_permission(user, "villages", "delete") is True

    def test_no_match(self):
        user = SimpleNamespace(role="user", is_superuser=False, permissions=["funds:read"])
        assert pu.check_permission(user, "villages", "write") is False
