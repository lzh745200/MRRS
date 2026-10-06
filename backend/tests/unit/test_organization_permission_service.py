import pytest
from unittest.mock import MagicMock


class TestPermissionDeniedError:
    def test_creation(self):
        from app.services.organization_permission_service import PermissionDeniedError
        exc = PermissionDeniedError(1, 2, "read")
        assert exc.user_id == 1
        assert exc.org_id == 2
        assert exc.action == "read"
        assert "无权" in str(exc)


class TestAccessAttemptLog:
    def test_defaults(self):
        from app.services.organization_permission_service import AccessAttemptLog
        log = AccessAttemptLog(user_id=1, org_id=2, action="access", allowed=True)
        assert log.user_id == 1
        assert log.org_id == 2
        assert log.allowed is True
        assert log.timestamp is not None


class TestGetUser:
    def test_user_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = "user_obj"
        svc = OrganizationPermissionService(mock_db)
        result = svc._get_user(1)
        assert result == "user_obj"

    def test_user_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = OrganizationPermissionService(mock_db)
        assert svc._get_user(999) is None


class TestGetUserOrganizationId:
    def test_user_obj_provided(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.organization_id = 5
        assert svc.get_user_organization_id(user=user) == 5

    def test_user_obj_no_org_id(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        del user.organization_id
        assert svc.get_user_organization_id(user=user) is None

    def test_user_id_provided_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.organization_id = 10
        mock_db.query.return_value.filter.return_value.first.return_value = user
        assert svc.get_user_organization_id(user_id=1) == 10

    def test_user_id_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert svc.get_user_organization_id(user_id=999) is None

    def test_both_none(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        assert svc.get_user_organization_id() is None


class TestGetAccessibleOrganizations:
    def test_user_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = OrganizationPermissionService(mock_db)
        assert svc.get_accessible_organizations(999) == []

    def test_user_no_org_not_superuser(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        user = MagicMock()
        user.organization_id = None
        user.is_superuser = False
        user.role = "user"
        mock_db.query.return_value.filter.return_value.first.return_value = user
        svc = OrganizationPermissionService(mock_db)
        assert svc.get_accessible_organizations(1) == []

    def test_superuser_no_org_all_orgs(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        user = MagicMock()
        user.organization_id = None
        user.is_superuser = True
        user.role = "super_admin"

        call_count = [0]

        def query_side_effect(model):
            call_count[0] += 1
            if call_count[0] == 2:
                q = MagicMock()
                q.filter.return_value.all.return_value = [(1,), (2,), (3,)]
                return q
            q = MagicMock()
            q.filter.return_value.first.return_value = user
            return q
        mock_db.query.side_effect = query_side_effect
        svc = OrganizationPermissionService(mock_db)
        result = svc.get_accessible_organizations(1)
        assert result == [1, 2, 3]

    def test_superuser_include_inactive(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        user = MagicMock()
        user.organization_id = None
        user.is_superuser = True
        user.role = "super_admin"

        call_count = [0]

        def query_side_effect(model):
            call_count[0] += 1
            if call_count[0] == 2:
                q = MagicMock()
                q.all.return_value = [(1,)]
                return q
            q = MagicMock()
            q.filter.return_value.first.return_value = user
            return q
        mock_db.query.side_effect = query_side_effect
        svc = OrganizationPermissionService(mock_db)
        result = svc.get_accessible_organizations(1, include_inactive=True)
        assert result == [1]

    def test_user_with_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        user = MagicMock()
        user.organization_id = 5
        mock_db.query.return_value.filter.return_value.first.return_value = user
        svc = OrganizationPermissionService(mock_db)
        mock_org_svc = MagicMock()
        svc.org_service = mock_org_svc
        mock_org_svc.get_subordinate_ids.return_value = [5, 6, 7]
        result = svc.get_accessible_organizations(1)
        assert result == [5, 6, 7]


class TestGetAccessibleOrganizationSet:
    def test_returns_set(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organizations = MagicMock(return_value=[1, 2, 3])
        result = svc.get_accessible_organization_set(1)
        assert result == {1, 2, 3}


class TestCanAccessOrganization:
    def test_allowed(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organization_set = MagicMock(return_value={1, 2, 3})
        assert svc.can_access_organization(1, 2) is True

    def test_denied_logged(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organization_set = MagicMock(return_value={1})
        svc._log_access_attempt = MagicMock()
        assert svc.can_access_organization(1, 99, log_attempt=True, ip_address="10.0.0.1") is False
        svc._log_access_attempt.assert_called_once()

    def test_denied_no_log(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organization_set = MagicMock(return_value={1})
        svc._log_access_attempt = MagicMock()
        assert svc.can_access_organization(1, 99, log_attempt=False) is False
        svc._log_access_attempt.assert_not_called()


class TestRequireOrganizationAccess:
    def test_allowed(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.can_access_organization = MagicMock(return_value=True)
        # allowed 路径：正确透传 (user_id, org_id) 做权限判断且不抛错（返回 None）
        svc.require_organization_access(1, 2)
        svc.can_access_organization.assert_called_once_with(1, 2, ip_address=None)

    def test_denied_raises(self):
        from app.services.organization_permission_service import PermissionDeniedError, OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.can_access_organization = MagicMock(return_value=False)
        svc._log_access_attempt = MagicMock()
        with pytest.raises(PermissionDeniedError):
            svc.require_organization_access(1, 99, action="edit", ip_address="10.0.0.1")
        svc._log_access_attempt.assert_called_once()


class TestCanManageOrganization:
    def test_user_none(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        assert svc.can_manage_organization() is False

    def test_user_id_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = OrganizationPermissionService(mock_db)
        assert svc.can_manage_organization(user_id=999) is False

    def test_superuser(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = True
        user.role = "super_admin"
        assert svc.can_manage_organization(user=user, org_id=1) is True

    def test_no_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        user.role = "user"
        user.organization_id = None
        svc.get_user_organization_id = MagicMock(return_value=None)
        assert svc.can_manage_organization(user=user, org_id=1) is False

    def test_same_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        svc.get_user_organization_id = MagicMock(return_value=5)
        assert svc.can_manage_organization(user=user, org_id=5) is False

    def test_subordinate_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        svc.get_user_organization_id = MagicMock(return_value=5)
        svc.org_service.get_subordinate_ids = MagicMock(return_value=[6, 7])
        assert svc.can_manage_organization(user=user, org_id=6) is True
        assert svc.can_manage_organization(user=user, org_id=8) is False


class TestCanCreateSubordinate:
    def test_no_user_params(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        assert svc.can_create_subordinate() is False

    def test_user_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = OrganizationPermissionService(mock_db)
        assert svc.can_create_subordinate(user_id=999) is False

    def test_superuser(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = True
        user.role = "super_admin"
        assert svc.can_create_subordinate(user=user, parent_org_id=1) is True

    def test_no_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        user.id = 1
        svc.get_user_organization_id = MagicMock(return_value=None)
        assert svc.can_create_subordinate(user=user, parent_org_id=1) is False

    def test_accessible_org_success(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        user.id = 1
        svc.get_user_organization_id = MagicMock(return_value=5)
        svc.get_accessible_organization_set = MagicMock(return_value={1, 2, 3, 5})
        assert svc.can_create_subordinate(user=user, parent_org_id=2) is True

    def test_not_accessible(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        user.id = 1
        svc.get_user_organization_id = MagicMock(return_value=5)
        svc.get_accessible_organization_set = MagicMock(return_value={5})
        assert svc.can_create_subordinate(user=user, parent_org_id=10) is False


class TestGetDataScopeFilter:
    def test_with_accessible_orgs(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organizations = MagicMock(return_value=[1, 2, 3])
        mock_column = MagicMock()
        result = svc.get_data_scope_filter(1, mock_column)
        assert result is not None

    def test_no_accessible_orgs(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organizations = MagicMock(return_value=[])
        mock_column = MagicMock()
        result = svc.get_data_scope_filter(1, mock_column)
        assert result is not None


class TestFilterOrganizationsByAccess:
    def test_filters(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_accessible_organization_set = MagicMock(return_value={1, 3, 5})
        result = svc.filter_organizations_by_access(1, [1, 2, 3, 4, 5])
        assert result == [1, 3, 5]


class TestGetSuperiorOrganizations:
    def test_no_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_user_organization_id = MagicMock(return_value=None)
        assert svc.get_superior_organizations(1) == []

    def test_with_ancestors(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_user_organization_id = MagicMock(return_value=5)
        mock_org1 = MagicMock()
        mock_org1.id = 1
        mock_org2 = MagicMock()
        mock_org2.id = 2
        svc.org_service.get_ancestors = MagicMock(return_value=[mock_org1, mock_org2])
        result = svc.get_superior_organizations(1)
        assert result == [1, 2]


class TestIsSuperiorOf:
    def test_no_params(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        assert svc.is_superior_of() is False

    def test_user_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = OrganizationPermissionService(mock_db)
        assert svc.is_superior_of(user_id=999, target_org_id=1) is False

    def test_superuser(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = True
        assert svc.is_superior_of(user=user, target_org_id=1) is True

    def test_no_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        svc.get_user_organization_id = MagicMock(return_value=None)
        assert svc.is_superior_of(user=user, target_org_id=1) is False

    def test_target_org_not_found(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        svc.get_user_organization_id = MagicMock(return_value=5)
        svc.org_service.get_organization = MagicMock(return_value=None)
        assert svc.is_superior_of(user=user, target_org_id=999) is False

    def test_is_ancestor(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        svc.get_user_organization_id = MagicMock(return_value=2)
        target_org = MagicMock()
        svc.org_service.get_organization = MagicMock(return_value=target_org)
        mock_anc1 = MagicMock()
        mock_anc1.id = 1
        mock_anc2 = MagicMock()
        mock_anc2.id = 2
        svc.org_service.get_ancestors = MagicMock(return_value=[mock_anc1, mock_anc2])
        assert svc.is_superior_of(user=user, target_org_id=10) is True

    def test_not_ancestor(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        user = MagicMock()
        user.is_superuser = False
        svc.get_user_organization_id = MagicMock(return_value=5)
        target_org = MagicMock()
        svc.org_service.get_organization = MagicMock(return_value=target_org)
        svc.org_service.get_ancestors = MagicMock(return_value=[MagicMock(id=1), MagicMock(id=2)])
        assert svc.is_superior_of(user=user, target_org_id=10) is False


class TestIsSubordinateOf:
    def test_no_org(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_user_organization_id = MagicMock(return_value=None)
        assert svc.is_subordinate_of(1, 10) is False

    def test_is_subordinate(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_user_organization_id = MagicMock(return_value=3)
        svc.org_service.get_subordinate_ids = MagicMock(return_value=[1, 2, 3])
        assert svc.is_subordinate_of(1, 10) is True

    def test_not_subordinate(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc.get_user_organization_id = MagicMock(return_value=10)
        svc.org_service.get_subordinate_ids = MagicMock(return_value=[1, 2])
        assert svc.is_subordinate_of(1, 5) is False


class TestLogAccessAttempt:
    def test_log_allowed(self, caplog):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", True, "10.0.0.1", "details")
        assert len(svc._access_logs) == 1
        assert svc._access_logs[0].allowed is True

    def test_log_denied(self, caplog):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", False, "10.0.0.1", "blocked")
        assert svc._access_logs[0].allowed is False


class TestGetAccessLogs:
    def test_no_filters(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", True)
        svc._log_access_attempt(2, 2, "access", False)
        svc._log_access_attempt(1, 3, "access", True)
        logs = svc.get_access_logs()
        assert len(logs) == 3

    def test_filter_by_user_id(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", True)
        svc._log_access_attempt(2, 2, "access", False)
        logs = svc.get_access_logs(user_id=1)
        assert len(logs) == 1

    def test_filter_by_org_id(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", True)
        svc._log_access_attempt(1, 3, "access", False)
        logs = svc.get_access_logs(org_id=2)
        assert len(logs) == 1

    def test_filter_by_allowed(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", True)
        svc._log_access_attempt(1, 3, "access", False)
        logs = svc.get_access_logs(allowed=True)
        assert len(logs) == 1

    def test_get_denied(self):
        from app.services.organization_permission_service import OrganizationPermissionService
        mock_db = MagicMock()
        svc = OrganizationPermissionService(mock_db)
        svc._log_access_attempt(1, 2, "access", True)
        svc._log_access_attempt(1, 3, "access", False)
        logs = svc.get_denied_access_logs()
        assert len(logs) == 1
