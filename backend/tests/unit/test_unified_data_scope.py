"""
Tests for app/core/unified_data_scope.py — the consolidated data-scope module.

Covers both pathways:
* Part 1 — role-based DataScope: get_data_scope / apply_scope_to_query /
  check_record_access / filter_by_data_scope / require_data_permission
* Part 2 — org-tree–based OrgScopeFilter / _get_org_subtree / get_org_scope
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


# ── get_data_scope (role-based) ─────────────────────────────────────

class TestGetDataScopeRoleBased:
    def test_none_user_returns_own(self):
        from app.core.unified_data_scope import DataScope, get_data_scope
        assert get_data_scope(None) == DataScope.OWN

    def test_is_superuser_returns_all(self):
        from app.core.unified_data_scope import DataScope, get_data_scope
        user = MagicMock()
        user.is_superuser = True
        user.role = "user"
        assert get_data_scope(user) == DataScope.ALL

    def test_super_admin_role_returns_all(self):
        from app.core.unified_data_scope import DataScope, get_data_scope
        user = MagicMock()
        user.is_superuser = False
        user.role = "super_admin"
        assert get_data_scope(user) == DataScope.ALL

    @pytest.mark.parametrize("role", ["admin", "manager", "approval_leader"])
    def test_privileged_roles_return_own_dept(self, role):
        from app.core.unified_data_scope import DataScope, get_data_scope
        user = MagicMock()
        user.is_superuser = False
        user.role = role
        assert get_data_scope(user) == DataScope.OWN_DEPT

    def test_plain_user_returns_own(self):
        from app.core.unified_data_scope import DataScope, get_data_scope
        user = MagicMock()
        user.is_superuser = False
        user.role = "user"
        assert get_data_scope(user) == DataScope.OWN

    def test_user_without_attrs_defaults_to_own(self):
        from app.core.unified_data_scope import DataScope, get_data_scope
        assert get_data_scope(object()) == DataScope.OWN


# ── apply_scope_to_query ─────────────────────────────────────────────

class TestApplyScopeToQuery:
    def test_all_scope_returns_query_unmodified(self):
        from app.core.unified_data_scope import apply_scope_to_query
        user = MagicMock(is_superuser=True, role="super_admin")
        q = MagicMock()
        result = apply_scope_to_query(q, MagicMock(), user)
        assert result is q
        q.filter.assert_not_called()

    def test_own_dept_filters_by_dept_field(self):
        from app.core.unified_data_scope import apply_scope_to_query
        user = MagicMock(is_superuser=False, role="admin")
        user.organization_id = 5
        q = MagicMock()
        result = apply_scope_to_query(q, MagicMock(), user)
        q.filter.assert_called_once()
        assert result == q.filter.return_value

    def test_own_dept_without_org_falls_back_to_own(self):
        from app.core.unified_data_scope import apply_scope_to_query
        user = MagicMock(is_superuser=False, role="admin")
        user.organization_id = None
        user.id = 7
        model = MagicMock()
        q = MagicMock()
        result = apply_scope_to_query(q, model, user)
        # falls back to OWN scope → filters on owner field (created_by)
        q.filter.assert_called_once_with(model.created_by == 7)
        assert result == q.filter.return_value

    def test_own_scope_filters_by_owner_field(self):
        from app.core.unified_data_scope import apply_scope_to_query
        user = MagicMock(is_superuser=False, role="user")
        user.id = 42
        model = MagicMock()
        q = MagicMock()
        result = apply_scope_to_query(q, model, user)
        q.filter.assert_called_once_with(model.created_by == 42)
        assert result == q.filter.return_value

    def test_unknown_scope_returns_query_unmodified(self, monkeypatch):
        import app.core.unified_data_scope as uds
        monkeypatch.setattr(uds, "get_data_scope", lambda u: "not-a-scope")
        q = MagicMock()
        result = uds.apply_scope_to_query(q, MagicMock(), MagicMock())
        assert result is q
        q.filter.assert_not_called()


# ── check_record_access ──────────────────────────────────────────────

class TestCheckRecordAccess:
    def test_all_scope_grants_access(self):
        from app.core.unified_data_scope import check_record_access
        user = MagicMock(is_superuser=True, role="super_admin")
        assert check_record_access(MagicMock(), user) is True

    def test_own_dept_matching_org_grants_access(self):
        from app.core.unified_data_scope import check_record_access
        user = MagicMock(is_superuser=False, role="admin")
        user.organization_id = 5
        record = MagicMock()
        record.organization_id = 5
        assert check_record_access(record, user) is True

    def test_own_dept_mismatched_org_denies_access(self):
        from app.core.unified_data_scope import check_record_access
        user = MagicMock(is_superuser=False, role="admin")
        user.organization_id = 5
        record = MagicMock()
        record.organization_id = 6
        assert check_record_access(record, user) is False

    def test_own_scope_matching_owner_grants_access(self):
        from app.core.unified_data_scope import check_record_access
        user = MagicMock(is_superuser=False, role="user")
        user.id = 42
        record = MagicMock()
        record.created_by = 42
        assert check_record_access(record, user) is True

    def test_own_scope_mismatched_owner_denies_access(self):
        from app.core.unified_data_scope import check_record_access
        user = MagicMock(is_superuser=False, role="user")
        user.id = 42
        record = MagicMock()
        record.created_by = 99
        assert check_record_access(record, user) is False

    def test_unknown_scope_denies_access(self, monkeypatch):
        import app.core.unified_data_scope as uds
        monkeypatch.setattr(uds, "get_data_scope", lambda u: "not-a-scope")
        assert uds.check_record_access(MagicMock(), MagicMock()) is False


# ── filter_by_data_scope ─────────────────────────────────────────────

class TestFilterByDataScope:
    def test_admin_sees_all_records(self):
        with patch("app.core.unified_data_scope.is_admin", return_value=True):
            from app.core.unified_data_scope import filter_by_data_scope
            q = MagicMock()
            result = filter_by_data_scope(q, MagicMock(), MagicMock())
            assert result is q
            q.filter.assert_not_called()

    def test_non_admin_query_is_scoped(self):
        with patch("app.core.unified_data_scope.is_admin", return_value=False):
            from app.core.unified_data_scope import filter_by_data_scope
            user = MagicMock(is_superuser=False, role="user")
            user.id = 3
            q = MagicMock()
            result = filter_by_data_scope(q, MagicMock(), user)
            q.filter.assert_called_once()
            assert result == q.filter.return_value


# ── require_data_permission ──────────────────────────────────────────

class TestRequireDataPermission:
    def test_admin_auto_passes(self):
        with patch("app.core.unified_data_scope.is_admin", return_value=True):
            from app.core.unified_data_scope import require_data_permission
            assert require_data_permission(MagicMock()) is True

    def test_no_db_session_denies_access(self):
        with patch("app.core.unified_data_scope.is_admin", return_value=False):
            with patch("app.core.unified_data_scope.logger") as mock_log:
                from app.core.unified_data_scope import require_data_permission
                with pytest.raises(HTTPException) as exc_info:
                    require_data_permission(MagicMock(), db=None)
                assert exc_info.value.status_code == 403
                assert exc_info.value.detail == "无权执行此操作"
                mock_log.warning.assert_called_once()

    def test_owner_passes(self):
        with patch("app.core.unified_data_scope.is_admin", return_value=False):
            from app.core.unified_data_scope import require_data_permission
            user = MagicMock()
            user.id = 42
            assert require_data_permission(user, created_by=42, db=MagicMock()) is True

    def test_non_owner_denied(self):
        with patch("app.core.unified_data_scope.is_admin", return_value=False):
            from app.core.unified_data_scope import require_data_permission
            user = MagicMock()
            user.id = 42
            with pytest.raises(HTTPException) as exc_info:
                require_data_permission(user, created_by=99, db=MagicMock(), error_message="禁止")
            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "禁止"


# ── OrgScopeFilter ───────────────────────────────────────────────────

class TestOrgScopeFilter:
    def test_has_full_access(self):
        from app.core.unified_data_scope import OrgScopeFilter
        assert OrgScopeFilter(is_admin=True).has_full_access() is True
        assert OrgScopeFilter(is_admin=False).has_full_access() is False

    def test_admin_returns_query_unmodified(self):
        from app.core.unified_data_scope import OrgScopeFilter
        ds = OrgScopeFilter(is_admin=True)
        q = MagicMock()
        assert ds.filter_by_org_ids(q) is q

    def test_self_only_filters_by_created_by(self):
        from app.core.unified_data_scope import OrgScopeFilter
        ds = OrgScopeFilter(is_admin=False, self_only=True, user_id=42)
        q = MagicMock()
        col = MagicMock()
        result = ds.filter_by_org_ids(q, col, created_by_column=col)
        q.filter.assert_called_once()
        assert result == q.filter.return_value

    def test_self_only_without_user_id_denies_all(self):
        from app.core.unified_data_scope import OrgScopeFilter
        ds = OrgScopeFilter(is_admin=False, self_only=True, user_id=None)
        q = MagicMock()
        result = ds.filter_by_org_ids(q, MagicMock(), created_by_column=MagicMock())
        q.filter.assert_called_once_with(False)
        assert result == q.filter.return_value

    def test_empty_org_ids_denies_all(self):
        from app.core.unified_data_scope import OrgScopeFilter
        ds = OrgScopeFilter(is_admin=False, org_ids=[])
        q = MagicMock()
        result = ds.filter_by_org_ids(q, MagicMock())
        q.filter.assert_called_once_with(False)
        assert result == q.filter.return_value

    def test_org_ids_filter_with_or_conditions(self):
        from sqlalchemy import column
        from app.core.unified_data_scope import OrgScopeFilter
        ds = OrgScopeFilter(is_admin=False, org_ids=[1, 2])
        q = MagicMock()
        result = ds.filter_by_org_ids(q, column("organization_id"), column("dept_id"))
        q.filter.assert_called_once()
        assert result == q.filter.return_value

    def test_org_ids_without_columns_denies_all(self):
        from app.core.unified_data_scope import OrgScopeFilter
        ds = OrgScopeFilter(is_admin=False, org_ids=[1, 2])
        q = MagicMock()
        result = ds.filter_by_org_ids(q)
        q.filter.assert_called_once_with(False)
        assert result == q.filter.return_value


# ── _get_org_subtree ─────────────────────────────────────────────────

class TestGetOrgSubtree:
    def test_max_depth_exceeded_truncates(self):
        with patch("app.core.unified_data_scope.logger") as mock_log:
            from app.core.unified_data_scope import _get_org_subtree
            ids, names = _get_org_subtree(MagicMock(), 1, _depth=11)
            assert ids == []
            assert names == []
            mock_log.warning.assert_called_once()

    def test_cycle_detected_returns_empty(self):
        with patch("app.core.unified_data_scope.logger") as mock_log:
            from app.core.unified_data_scope import _get_org_subtree
            ids, names = _get_org_subtree(MagicMock(), 1, _visited={1})
            assert ids == []
            assert names == []
            mock_log.warning.assert_called_once()

    def test_org_not_found_returns_empty(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        from app.core.unified_data_scope import _get_org_subtree
        ids, names = _get_org_subtree(mock_db, 999)
        assert ids == []
        assert names == []

    def test_tree_with_children(self):
        mock_db = MagicMock()
        parent = MagicMock()
        parent.id = 1
        parent.name = "Parent"
        child = MagicMock()
        child.id = 2
        child.name = "Child"
        mock_db.query.return_value.filter.return_value.first.side_effect = [parent, child]
        mock_db.query.return_value.filter.return_value.all.side_effect = [[child], []]
        from app.core.unified_data_scope import _get_org_subtree
        ids, names = _get_org_subtree(mock_db, 1)
        assert ids == [1, 2]
        assert names == ["Parent", "Child"]


# ── get_org_scope dependency ─────────────────────────────────────────

class TestGetOrgScope:
    async def test_admin_role_full_access(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "admin"
        user.data_scope = "org"
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is True
        assert ds.has_full_access() is True

    async def test_data_scope_all_full_access(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "all"
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is True

    async def test_self_scope(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "self"
        user.id = 42
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is False
        assert ds.self_only is True
        assert ds.user_id == 42
        assert ds.org_ids == []
        assert ds.org_names == []

    async def test_org_scope_no_org_id_with_department(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org"
        user.organization_id = None
        user.department = "某部"
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is False
        assert ds.org_names == ["某部"]
        assert ds.org_ids == []

    async def test_org_scope_no_org_id_no_dept_fail_closed(self):
        """scope=org 但无组织无部门 → fail-closed 仅本人（ADR-0002）"""
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org"
        user.organization_id = None
        user.department = None
        user.id = 11
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is False
        assert ds.self_only is True
        assert ds.user_id == 11

    async def test_org_scope_with_org_id(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org"
        user.organization_id = 5
        mock_db = MagicMock()
        org = MagicMock()
        org.name = "TestOrg"
        mock_db.query.return_value.filter.return_value.first.return_value = org
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=mock_db)
        assert ds.is_admin is False
        assert ds.org_names == ["TestOrg"]
        assert ds.org_ids == [5]

    async def test_org_scope_org_not_found(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org"
        user.organization_id = 5
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=mock_db)
        assert ds.is_admin is False
        assert ds.org_names == []
        assert ds.org_ids == [5]

    async def test_org_children_no_org_id_with_department(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org_children"
        user.organization_id = None
        user.department = "某部"
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is False
        assert ds.org_names == ["某部"]
        assert ds.org_ids == []

    async def test_org_children_no_org_id_no_dept_fail_closed(self):
        """无组织无部门 fail-closed（ADR-0002）：回退仅本人，绝不放行全量"""
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org_children"
        user.organization_id = None
        user.department = None
        user.id = 7
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            ds = await get_org_scope(current_user=user, db=None)
        assert ds.is_admin is False
        assert ds.self_only is True
        assert ds.user_id == 7
        assert ds.org_ids == []

    async def test_org_children_with_subtree(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org_children"
        user.organization_id = 1
        mock_db = MagicMock()
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            with patch("app.core.unified_data_scope._get_org_subtree", return_value=([1, 2], ["Root", "Child"])):
                ds = await get_org_scope(current_user=user, db=mock_db)
        assert ds.is_admin is False
        assert ds.org_ids == [1, 2]
        assert ds.org_names == ["Root", "Child"]

    async def test_org_children_empty_names_with_department(self):
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org_children"
        user.organization_id = 1
        user.department = "DeptFallback"
        mock_db = MagicMock()
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            with patch("app.core.unified_data_scope._get_org_subtree", return_value=([1], [])):
                ds = await get_org_scope(current_user=user, db=mock_db)
        assert ds.is_admin is False
        assert ds.org_names == ["DeptFallback"]
        assert ds.org_ids == [1]

    async def test_org_children_empty_names_no_dept_fail_closed(self):
        """组织树为空且无部门 → fail-closed 仅本人（ADR-0002）"""
        from app.core.unified_data_scope import get_org_scope
        user = MagicMock()
        user.role = "user"
        user.data_scope = "org_children"
        user.organization_id = 1
        user.department = None
        user.id = 9
        mock_db = MagicMock()
        with patch("app.core.unified_data_scope.is_superuser", return_value=False):
            with patch("app.core.unified_data_scope._get_org_subtree", return_value=([1], [])):
                ds = await get_org_scope(current_user=user, db=mock_db)
        assert ds.is_admin is False
        assert ds.self_only is True
        assert ds.user_id == 9
