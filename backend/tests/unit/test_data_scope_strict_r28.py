"""R28 / R27-H8 + M40 回归：数据范围口径收敛（军事审计红线 S2）。

背景（docs/系统全面排查报告-2026-10-14.md）
- H8：`apply_scope_filter` 对**任何**管理员直接 return query（全量放行），而
  `filter_by_data_scope`（导出链路）对部门级 admin 严格限定本组织 → 同一数据面
  两条口径：部门级 admin 在 funds/projects/villages 列表看到跨组织全量，导出却只有
  本组织。本文件锁定修复后的口径：
    * 默认严格 —— role=admin（is_superuser=False）收敛到"本组织及子树"；
    * 只有调用点显式 admin_full_access=True（组织树可见性模型：地图/大屏/统计/组织树）
      才放行全量；
    * super_admin / is_superuser / data_scope="all" 仍然全局（真正的全局管理员）。
- M40：`check_record_access` 的 OWN_DEPT 分支原先直接比较两侧组织字段，当**记录侧**
  组织列为 NULL、而用户侧组织来自 `org_id` 回退属性（或自定义 dept_field 缺失）时，
  `None == None` 为真 → **fail-open**：无组织记录对部门级 admin 反而可见。修复后
  显式判空拒绝，且用户侧统一走 `_get_user_org_id` 回退。

为什么用真实 SQLAlchemy Select 而不是 MagicMock：
权限过滤是"是否真的加上 WHERE 条件"的问题，MagicMock 只能证明"调用了 .filter()"，
不能证明条件落在 organization_id 上（历史假绿正是这么来的）。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, select
from sqlalchemy.orm import declarative_base

import app.core.data_permission as dp
from app.core.data_permission import apply_scope_filter, check_record_access

Base = declarative_base()


class ScopedModel(Base):
    __tablename__ = "scoped_model_r28"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer)
    created_by = Column(Integer)


class NoOrgModel(Base):
    __tablename__ = "no_org_model_r28"
    id = Column(Integer, primary_key=True)
    created_by = Column(Integer)


def _user(**kwargs):
    defaults = {"is_superuser": False, "data_scope": None}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _bound_params(stmt):
    """展开编译参数（IN 条件会是列表），返回扁平值集合，便于断言"10 在过滤条件里"。"""
    flat = []
    for value in stmt.compile().params.values():
        if isinstance(value, (list, tuple, set)):
            flat.extend(value)
        else:
            flat.append(value)
    return flat


DEPT_ADMIN = _user(id=1, role="admin", organization_id=10)
SUPER_ADMIN = _user(id=2, role="super_admin", organization_id=None)
FLAG_SUPERUSER = _user(id=3, role="viewer", is_superuser=True)
GLOBAL_SCOPE = _user(id=4, role="viewer", data_scope="all")
PLAIN_USER = _user(id=5, role="user", organization_id=10)


class TestDepartmentAdminIsScopedByDefault:
    """H8：部门级 admin 默认必须收敛到本组织及子树（与导出链路同口径）。"""

    def test_query_style_filters_by_org(self):
        q = MagicMock(name="query")
        result = apply_scope_filter(q, DEPT_ADMIN, ScopedModel)
        q.filter.assert_called_once()
        assert result is q.filter.return_value

    def test_select_style_where_clause_targets_organization_id(self):
        stmt = select(ScopedModel)
        with patch.object(dp, "_get_org_subtree", return_value=([10, 11], ["总部", "分部"])):
            result = apply_scope_filter(stmt, DEPT_ADMIN, ScopedModel, db=MagicMock())
        where_sql = str(result.whereclause)
        assert "organization_id" in where_sql
        assert "created_by" not in where_sql
        bound = _bound_params(result)
        assert 10 in bound and 11 in bound

    def test_subtree_expansion_uses_db(self):
        """本组织 + 全部下级（与 get_org_scope 的 org_children 语义一致）。"""
        stmt = select(ScopedModel)
        db = MagicMock(name="db")
        with patch.object(dp, "_get_org_subtree", return_value=([10, 11, 12], ["a", "b", "c"])) as sub:
            apply_scope_filter(stmt, DEPT_ADMIN, ScopedModel, db=db)
        sub.assert_called_once_with(db, 10)

    def test_without_db_limits_to_own_org(self):
        stmt = select(ScopedModel)
        result = apply_scope_filter(stmt, DEPT_ADMIN, ScopedModel)
        assert "organization_id" in str(result.whereclause)
        assert 10 in _bound_params(result)

    def test_explicit_full_access_grants_everything(self):
        q = MagicMock(name="query")
        assert apply_scope_filter(q, DEPT_ADMIN, ScopedModel, admin_full_access=True) is q
        q.filter.assert_not_called()

    def test_full_access_flag_does_not_widen_plain_user(self):
        """开关只对管理员生效，普通用户不会因为传了 True 就被放行。"""
        q = MagicMock(name="query")
        result = apply_scope_filter(q, PLAIN_USER, ScopedModel, admin_full_access=True)
        q.filter.assert_called_once()
        assert result is q.filter.return_value


class TestGlobalAdminsStayGlobal:
    """super_admin / is_superuser / data_scope=all 不受开关约束。"""

    @pytest.mark.parametrize("user", [SUPER_ADMIN, FLAG_SUPERUSER, GLOBAL_SCOPE])
    def test_global_admin_query_unchanged(self, user):
        q = MagicMock(name="query")
        assert apply_scope_filter(q, user, ScopedModel) is q
        q.filter.assert_not_called()

    @pytest.mark.parametrize("user", [SUPER_ADMIN, FLAG_SUPERUSER, GLOBAL_SCOPE])
    def test_global_admin_select_unchanged(self, user):
        stmt = select(ScopedModel)
        assert apply_scope_filter(stmt, user, ScopedModel) is stmt


class TestOrgIdsNoneFailsClosed:
    """H8 关键分支：可访问组织为 None（全局范围）时不得静默放行。"""

    def test_none_org_ids_without_flag_degrades_to_own_org(self):
        stmt = select(ScopedModel)
        with patch.object(dp, "get_accessible_org_ids", return_value=None):
            result = apply_scope_filter(stmt, DEPT_ADMIN, ScopedModel)
        where_sql = str(result.whereclause)
        assert "organization_id" in where_sql
        assert 10 in _bound_params(result)

    def test_none_org_ids_with_flag_returns_query(self):
        q = MagicMock(name="query")
        with patch.object(dp, "get_accessible_org_ids", return_value=None):
            assert apply_scope_filter(q, DEPT_ADMIN, ScopedModel, admin_full_access=True) is q
        q.filter.assert_not_called()

    def test_none_org_ids_and_no_organization_fails_closed_to_owner(self):
        """OWN_DEPT 范围 + 全局 org_ids + 无组织归属：只能看自己创建的记录（绝不看全量）。

        该组合在正常口径下不可达（无组织用户会被 get_data_scope 降级为 OWN），
        因此按"口径漂移"场景打补丁驱动：get_data_scope=OWN_DEPT 且用户无组织。
        """
        stmt = select(NoOrgModel)
        admin_without_org = _user(id=6, role="admin", organization_id=None)
        with patch.object(dp, "get_accessible_org_ids", return_value=None), \
                patch.object(dp, "get_data_scope", return_value=dp.DataScope.OWN_DEPT), \
                patch.object(dp, "logger") as mock_logger:
            result = apply_scope_filter(stmt, admin_without_org, NoOrgModel)
        where_sql = str(result.whereclause)
        assert "created_by" in where_sql
        assert 6 in _bound_params(result)
        mock_logger.warning.assert_called_once()


class TestGetScopeOrgIdsHelper:
    """_get_scope_org_ids：严格口径的可访问组织集合（永不返回 None）。"""

    def test_without_org_returns_empty(self):
        assert dp._get_scope_org_ids(_user(id=7, role="admin")) == []

    def test_without_db_returns_own_org_only(self):
        assert dp._get_scope_org_ids(DEPT_ADMIN) == [10]

    def test_with_db_expands_subtree(self):
        with patch.object(dp, "_get_org_subtree", return_value=([10, 11], ["a", "b"])):
            assert dp._get_scope_org_ids(DEPT_ADMIN, db=MagicMock()) == [10, 11]

    def test_empty_subtree_falls_back_to_own_org(self):
        with patch.object(dp, "_get_org_subtree", return_value=([], [])):
            assert dp._get_scope_org_ids(DEPT_ADMIN, db=MagicMock()) == [10]


class TestCheckRecordAccessFailClosed:
    """M40：OWN_DEPT 分支不得因组织字段为 None 而放行。"""

    def test_record_org_none_is_denied(self):
        """记录组织列为 NULL 时对部门级 admin 一律拒绝（原实现 None==None 放行）。"""
        user = _user(id=8, role="admin", organization_id=10)
        record = SimpleNamespace(organization_id=None, created_by=8)
        assert check_record_access(record, user) is False

    def test_user_org_via_org_id_fallback_and_record_none_is_denied(self):
        """用户组织来自 org_id 回退属性、记录组织为 NULL —— 历史 fail-open 场景。"""
        user = _user(id=8, role="admin", org_id=10)
        record = SimpleNamespace(organization_id=None, created_by=8)
        assert check_record_access(record, user) is False

    def test_custom_dept_field_none_on_both_sides_is_denied(self):
        """自定义 dept_field 在两侧都为 None —— 原实现 None==None 放行。"""
        user = _user(id=8, role="admin", organization_id=10, org_id=None)
        record = SimpleNamespace(org_id=None, created_by=8)
        assert check_record_access(record, user, dept_field="org_id") is False

    def test_same_org_still_allowed(self):
        user = _user(id=8, role="admin", organization_id=10)
        record = SimpleNamespace(organization_id=10, created_by=99)
        assert check_record_access(record, user) is True

    def test_user_org_via_org_id_fallback_same_org_allowed(self):
        """用户侧走 _get_user_org_id 回退（organization_id → org_id）后仍能正常放行。"""
        user = _user(id=8, role="admin", org_id=10)
        record = SimpleNamespace(organization_id=10, created_by=99)
        assert check_record_access(record, user) is True

    def test_different_org_denied(self):
        user = _user(id=8, role="admin", organization_id=10)
        record = SimpleNamespace(organization_id=11, created_by=99)
        assert check_record_access(record, user) is False

    def test_custom_dept_field_match(self):
        user = _user(id=8, role="admin", organization_id=10, dept_id=10)
        record = SimpleNamespace(dept_id=10, created_by=99)
        assert check_record_access(record, user, dept_field="dept_id") is True
        record_other = SimpleNamespace(dept_id=11, created_by=99)
        assert check_record_access(record_other, user, dept_field="dept_id") is False

    def test_admin_without_org_degrades_to_owner_scope(self):
        """无组织 admin 经 get_data_scope 降级为 OWN：只认自己创建的记录。"""
        user = _user(id=8, role="admin", organization_id=None)
        assert check_record_access(SimpleNamespace(organization_id=None, created_by=8), user) is True
        assert check_record_access(SimpleNamespace(organization_id=None, created_by=99), user) is False
