"""v1.12.9 覆盖率补口：app/api/v1/auth/users.py 超级管理员账号守卫（W15 深审 #9~#12）。

覆盖行（当前代码行号）：
- 125-131 `_is_super_admin_account`：None / is_superuser 标记 / role=super_admin 三态判定；
- 150-155 `_assert_can_manage_super_admin`：非超管既不能改超管账号（target），
  也不能把任何账号提升为 super_admin（target_role）；
- 166-167 `_require_admin_user`：带缓存装饰器的静态选项端点用路由级依赖；
- 646 PUT /users/{id}：携带 role 字段时必经 target_role 提权守卫。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.auth.users as us
from app.core.data_permission import DataScope


def _u(**kw):
    defaults = dict(id=1, username="admin", role="admin", is_superuser=False, organization_id=1)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit", "options"):
        getattr(q, attr).return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    q.count.return_value = kw.get("count", 0)
    return q


class TestIsSuperAdminAccount:
    def test_none_is_not_super_admin(self):
        assert us._is_super_admin_account(None) is False

    def test_is_superuser_flag_wins(self):
        assert us._is_super_admin_account(_u(role="user", is_superuser=True)) is True

    def test_role_super_admin_detected(self):
        assert us._is_super_admin_account(_u(role="super_admin", is_superuser=False)) is True

    def test_plain_admin_is_not_super_admin(self):
        assert us._is_super_admin_account(_u(role="admin", is_superuser=False)) is False


class TestAssertCanManageSuperAdmin:
    def test_superuser_passes_for_any_target(self):
        us._assert_can_manage_super_admin(
            _u(is_superuser=True), target=_u(role="super_admin"), target_role="super_admin"
        )

    def test_plain_admin_cannot_touch_super_admin_account(self):
        with pytest.raises(HTTPException) as ei:
            us._assert_can_manage_super_admin(_u(role="admin"), target=_u(role="super_admin"))
        assert ei.value.status_code == 403
        assert "超级管理员" in ei.value.detail

    def test_plain_admin_cannot_promote_to_super_admin(self):
        with pytest.raises(HTTPException) as ei:
            us._assert_can_manage_super_admin(_u(role="admin"), target_role="super_admin")
        assert ei.value.status_code == 403

    def test_plain_admin_can_manage_normal_account(self):
        us._assert_can_manage_super_admin(_u(role="admin"), target=_u(role="user"), target_role="user")


class TestRequireAdminUserDependency:
    """供 @cache_result 静态选项端点使用的路由级管理员依赖（缓存命中也要判权）。"""

    def test_admin_passes_and_returns_user(self):
        admin = _u(role="admin")
        assert us._require_admin_user(current_user=admin) is admin

    def test_non_admin_rejected(self):
        with pytest.raises(HTTPException) as ei:
            us._require_admin_user(current_user=_u(role="user"))
        assert ei.value.status_code == 403

    def test_missing_role_rejected(self):
        with pytest.raises(HTTPException) as ei:
            us._require_admin_user(current_user=SimpleNamespace(role=None, is_superuser=False))
        assert ei.value.status_code == 403


class TestUpdateUserSuperAdminGuard:
    """PUT /users/{id}：改角色必须过提权守卫（W15 深审 #11/#12）。"""

    async def test_role_change_hits_target_role_guard_and_succeeds(self):
        target = _u(id=5, username="bob", role="user", is_superuser=False, organization_id=1)
        db = MagicMock()
        db.query.return_value = _q(first=target)
        admin = _u(id=1, username="root", role="super_admin", is_superuser=True)

        with patch.object(us, "safe_commit") as m_commit:
            result = await us.update_user(5, us.UserUpdateBody(role="user"), admin, db)

        assert result["code"] == 200
        assert result["updated_fields"] == ["role"]
        m_commit.assert_called_once_with(db)

    async def test_promote_to_super_admin_rejected(self):
        target = _u(id=5, username="bob", role="user", is_superuser=False, organization_id=1)
        db = MagicMock()
        db.query.return_value = _q(first=target)
        admin = _u(id=1, username="dept_admin", role="admin", is_superuser=False)

        with pytest.raises(HTTPException) as ei:
            await us.update_user(5, us.UserUpdateBody(role="super_admin"), admin, db)

        assert ei.value.status_code == 403
        assert target.role == "user"  # 目标账号未被改写


class TestListUsersScopeFiltering:
    """GET /users 数据范围收口（ADR-0002 fail-closed）。

    OWN（无组织）→ 仅本人；OWN_DEPT（有组织）→ 本组织及下级组织。
    历史缺陷：无组织时条件为假 → 过滤被整体跳过 → 跨组织枚举全部用户。
    """

    async def test_own_scope_filters_to_current_user(self):
        admin = _u(id=9, role="admin", is_superuser=False, organization_id=None)
        q = _q()
        db = MagicMock()
        db.query.return_value = q

        with patch("app.api.v1.auth.users.get_data_scope", return_value=DataScope.OWN):
            result = await us.list_users(current_user=admin, db=db)

        assert result["data"]["total"] == 0
        assert q.filter.call_count == 1  # 仅追加 User.id == current_user.id

    async def test_own_dept_scope_includes_child_orgs(self):
        admin = _u(id=9, role="admin", is_superuser=False, organization_id=7)
        user_query = _q()
        org_query = MagicMock()
        org_query.filter.return_value = org_query
        org_query.all.return_value = [(8,), (9,)]
        db = MagicMock()
        db.query.side_effect = [user_query, org_query]

        with patch("app.api.v1.auth.users.get_data_scope", return_value=DataScope.OWN_DEPT):
            result = await us.list_users(current_user=admin, db=db)

        assert result["data"]["total"] == 0
        org_query.all.assert_called_once()


class TestAdminMustHaveOrganization:
    """产品决策 2026-09-14：禁止创建/改成无组织管理员（创建/更新两道守卫）。"""

    async def test_create_orgless_admin_rejected(self):
        db = MagicMock()
        db.query.return_value = _q(first=None)
        body = us.UserCreateBody(
            username="new_admin", password="Str0ng!Passw0rd", role="admin"
        )
        root = _u(id=1, username="root", role="super_admin", is_superuser=True)

        with pytest.raises(HTTPException) as ei:
            await us.create_user(body, root, db)

        assert ei.value.status_code == 400
        assert "组织" in ei.value.detail

    async def test_update_admin_to_orgless_rejected(self):
        target = _u(id=5, username="bob", role="admin", is_superuser=False, organization_id=1)
        db = MagicMock()
        db.query.return_value = _q(first=target)
        root = _u(id=1, username="root", role="super_admin", is_superuser=True)

        with pytest.raises(HTTPException) as ei:
            await us.update_user(5, us.UserUpdateBody(organization_id=None), root, db)

        assert ei.value.status_code == 400
        assert "组织" in ei.value.detail


class TestStaffListKeyword:
    async def test_keyword_is_trimmed_and_applied(self):
        q = _q()
        db = MagicMock()
        db.query.return_value = q
        current = _u(id=3, role="user", is_superuser=False, organization_id=1)

        with patch("app.api.v1.auth.users.get_data_scope", return_value=DataScope.ALL):
            result = await us.get_staff_list(
                page=1, page_size=20, keyword="  bob  ", current_user=current, db=db
            )

        assert result["data"]["total"] == 0
        assert q.filter.call_count == 2  # is_active 过滤 + 关键词过滤
