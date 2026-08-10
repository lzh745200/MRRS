from unittest.mock import Mock, patch
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_db
from app.core.security import get_current_user


def _fake_require_admin(user):
    if not (getattr(user, "is_superuser", False) or getattr(user, "role", "") in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="需要管理员权限")


def _make_user(**kwargs):
    user = Mock()
    user.id = kwargs.get("id", 1)
    user.username = kwargs.get("username", "testuser")
    user.email = kwargs.get("email", "test@example.com")
    user.full_name = kwargs.get("full_name", "Test User")
    user.hashed_password = kwargs.get("hashed_password", "hashed_pwd")
    user.role = kwargs.get("role", "operator")
    user.is_active = kwargs.get("is_active", True)
    user.is_superuser = kwargs.get("is_superuser", False)
    user.organization_id = kwargs.get("organization_id", 1)
    user.organization_name = kwargs.get("organization_name", "TestOrg")
    user.permissions_list = kwargs.get("permissions_list", ["read"])
    user.allowed_menus = kwargs.get("allowed_menus", None)
    user.allowed_menus_list = kwargs.get("allowed_menus_list", [])
    user.failed_login_count = kwargs.get("failed_login_count", 0)
    user.locked_until = kwargs.get("locked_until", None)
    user.must_change_password = kwargs.get("must_change_password", False)
    user.password_changed_at = kwargs.get("password_changed_at", None)
    user.last_login = kwargs.get("last_login", datetime.now(timezone.utc))
    user.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    user.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
    user.phone = kwargs.get("phone", "13800138000")
    user.department = kwargs.get("department", "Dept A")
    user.position = kwargs.get("position", "Manager")
    user.avatar = kwargs.get("avatar", "")
    user.gender = kwargs.get("gender", "male")
    user.birthday = kwargs.get("birthday", "1990-01-01")
    user.address = kwargs.get("address", "Somewhere")
    user.remark = kwargs.get("remark", "Remark")
    user.data_scope = kwargs.get("data_scope", "org")
    user.machine_binding_required = kwargs.get("machine_binding_required", False)
    user.allowed_permissions = kwargs.get("allowed_permissions", "")
    user.token_version_safe = kwargs.get("token_version_safe", 1)
    user.organization = kwargs.get("organization", None)
    user.revoke_all_tokens = Mock()
    user.last_login = kwargs.get("last_login", datetime.now(timezone.utc))
    return user


def _setup_admin_user(client):
    user = _make_user(id=1, username="admin", role="admin", is_superuser=True)
    async def mock_gcu():
        return user
    client.app.dependency_overrides[get_current_user] = mock_gcu
    return user


def _setup_regular_user(client):
    user = _make_user(id=2, username="regular", role="user", is_superuser=False)
    async def mock_gcu():
        return user
    client.app.dependency_overrides[get_current_user] = mock_gcu
    return user


def _make_mock_db(user_list=None, user=None):
    mock_db = Mock()
    user_list = user_list or ([] if user is None else [user])
    mock_query = Mock()
    mock_query.count.return_value = len(user_list)
    mock_query.options.return_value.offset.return_value.limit.return_value.all.return_value = user_list
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = user_list
    mock_query.first.return_value = user
    mock_db.query.return_value = mock_query
    return mock_db


def _override_db(client, mock_db):
    def _gen():
        yield mock_db
    client.app.dependency_overrides[get_db] = _gen


def _clear_overrides(client, *deps):
    for d in deps:
        client.app.dependency_overrides.pop(d, None)


class TestGetCurrentUserProfile:
    prefix = "/api/v1/users"

    def test_me_success(self, client):
        admin = _setup_admin_user(client)
        mock_db = _make_mock_db(user=admin)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 200
            assert response.json()["data"]["roleName"] == "超级管理员"
        _clear_overrides(client, get_db, get_current_user)

    def test_me_not_found(self, client):
        admin = _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_me_role_display_operator(self, client):
        user = _make_user(id=2, username="opuser", role="operator", is_superuser=False)
        async def mock_gcu():
            return user
        client.app.dependency_overrides[get_current_user] = mock_gcu
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 200
            # 角色精简后 operator 并入普通用户（user），显示名同步为普通用户
            assert response.json()["data"]["roleName"] == "普通用户"
        _clear_overrides(client, get_db, get_current_user)

    def test_me_role_display_unknown(self, client):
        user = _make_user(id=3, username="stranger", role="unknown_role", is_superuser=False)
        async def mock_gcu():
            return user
        client.app.dependency_overrides[get_current_user] = mock_gcu
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/me")
            assert response.status_code == 200
            assert response.json()["data"]["roleName"] == "普通用户"
        _clear_overrides(client, get_db, get_current_user)


class TestUpdateCurrentUserProfile:
    prefix = "/api/v1/users"

    def test_update_profile_success(self, client):
        admin = _setup_admin_user(client)
        mock_db = _make_mock_db(user=admin)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/me/profile", json={"full_name": "Updated Name"})
            assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_update_profile_not_found(self, client):
        admin = _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/me/profile", json={"full_name": "Updated"})
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)


class TestListUsers:
    prefix = "/api/v1/users"

    def test_list_users_empty(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}?page=1&page_size=20")
            assert response.status_code == 200
            assert response.json()["data"]["total"] == 0
        _clear_overrides(client, get_db, get_current_user)

    def test_list_users_with_keyword(self, client):
        _setup_admin_user(client)
        user = _make_user(username="target")
        mock_db = _make_mock_db(user_list=[user])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}?keyword=target&page=1&page_size=20")
            assert response.status_code == 200
            assert response.json()["data"]["total"] == 1
        _clear_overrides(client, get_db, get_current_user)

    def test_list_users_with_is_active_filter(self, client):
        _setup_admin_user(client)
        user = _make_user(is_active=True)
        mock_db = _make_mock_db(user_list=[user])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}?is_active=true&page=1&page_size=20")
            assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_list_users_with_org_and_role_filter(self, client):
        _setup_admin_user(client)
        user = _make_user(organization_id=1, role="admin")
        mock_db = _make_mock_db(user_list=[user])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}?organization_id=1&role=admin")
            assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_list_users_with_machine_codes(self, client):
        _setup_admin_user(client)
        user = _make_user(id=1)
        mock_db = _make_mock_db(user_list=[user])
        _override_db(client, mock_db)

        mc_record = Mock()
        mc_record.user_id = 1
        mc_record.machine_code = "MC-001"
        mc_query = Mock()
        mc_query.filter.return_value = mc_query
        mc_query.all.return_value = [mc_record]
        user_query = mock_db.query.return_value

        def query_side_effect(model):
            # db.query(MachineCode) returns mc_query, db.query(User) returns user_query
            if hasattr(model, 'user_id') or getattr(model, '__tablename__', '') == 'machine_codes':
                return mc_query
            return user_query

        mock_db.query.side_effect = query_side_effect

        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}?page=1&page_size=20")
            assert response.status_code == 200
            assert response.json()["data"]["items"][0]["machine_code"] == "MC-001"
        _clear_overrides(client, get_db, get_current_user)


class TestGetPendingUsers:
    prefix = "/api/v1/users"

    def test_get_pending_users_success(self, client):
        _setup_admin_user(client)
        pending = _make_user(id=3, username="pending", is_active=False)
        mock_db = _make_mock_db(user_list=[pending])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/pending/list")
            assert response.status_code == 200
            assert response.json()["data"]["total"] == 1
        _clear_overrides(client, get_db, get_current_user)

    def test_get_pending_users_empty(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/pending/list")
            assert response.status_code == 200
            assert response.json()["data"]["total"] == 0
        _clear_overrides(client, get_db, get_current_user)


class TestGetStaffList:
    prefix = "/api/v1/users"

    def test_staff_list_success(self, client):
        admin = _setup_admin_user(client)
        user = _make_user(id=2, username="staff1")
        mock_db = _make_mock_db(user_list=[user])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.data_permission.filter_by_data_scope") as mock_fds:
                mock_fds.return_value = mock_db.query.return_value
                response = client.get(f"{self.prefix}/staff-list?page=1&page_size=20")
                assert response.status_code == 200
                assert response.json()["data"]["total"] == 1
        _clear_overrides(client, get_db, get_current_user)


class TestGetUser:
    prefix = "/api/v1/users"

    def test_get_self(self, client):
        user = _setup_regular_user(client)
        user.organization = Mock()
        user.organization.id = 1
        user.organization.name = "Org1"
        user.organization.code = "ORG1"
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/2")
            assert response.status_code == 200
            assert response.json()["organization"] == {"id": 1, "name": "Org1", "code": "ORG1"}
        _clear_overrides(client, get_db, get_current_user)

    def test_get_other_user_no_admin(self, client):
        regular = _setup_regular_user(client)
        other = _make_user(id=1, username="other")
        mock_db = _make_mock_db(user=other)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin", side_effect=_fake_require_admin):
            response = client.get(f"{self.prefix}/1")
            assert response.status_code == 403
        _clear_overrides(client, get_db, get_current_user)

    def test_get_user_admin_can_view_other(self, client):
        admin = _setup_admin_user(client)
        other = _make_user(id=5, username="other")
        other.organization = Mock()
        other.organization.id = 2
        other.organization.name = "Org2"
        other.organization.code = "ORG2"
        mock_db = _make_mock_db(user=other)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/5")
            assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_get_user_not_found(self, client):
        admin = _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/999")
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_get_user_no_org(self, client):
        admin = _setup_admin_user(client)
        other = _make_user(id=5, username="other", organization=None)
        mock_db = _make_mock_db(user=other)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/5")
            assert response.status_code == 200
            assert response.json()["organization"] is None
        _clear_overrides(client, get_db, get_current_user)


class TestCreateUser:
    prefix = "/api/v1/users"

    def test_username_exists(self, client):
        _setup_admin_user(client)
        existing = _make_user(username="existing")
        mock_db = _make_mock_db(user=existing, user_list=[existing])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.post(f"{self.prefix}", json={"username": "existing", "password": "Str0ng!Pass"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_email_exists(self, client):
        _setup_admin_user(client)
        mock_call = [0]
        def query_side(model):
            mock_call[0] += 1
            q = Mock()
            q.filter.return_value.first.side_effect = lambda: None if mock_call[0] <= 1 else _make_user()
            return q
        mock_db = Mock()
        mock_db.query = query_side
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.post(f"{self.prefix}", json={"username": "newuser", "password": "Str0ng!Pass", "email": "used@example.com"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_org_not_found(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.models.organization.Organization") as mock_org_cls:
                mock_org_cls.query.filter.return_value.first.return_value = None
                response = client.post(f"{self.prefix}", json={"username": "newuser", "password": "Str0ng!Pass", "organization_id": 999})
                assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_invalid_role(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.post(f"{self.prefix}", json={"username": "newuser", "password": "Str0ng!Pass", "role": "nonexistent_role"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_invalid_data_scope(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.post(f"{self.prefix}", json={"username": "newuser", "password": "Str0ng!Pass", "data_scope": "invalid_scope"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_create_user_success(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        user_query = mock_db.query.return_value
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.api.v1.auth.users.get_password_hash", return_value="hashed"):
                with patch("app.models.organization.Organization") as mock_org_cls:
                    org_query = Mock()
                    org_query.filter.return_value = org_query
                    org_query.first.return_value = Mock(id=1)
                    def query_side_effect(model):
                        if model is mock_org_cls:
                            return org_query
                        return user_query
                    mock_db.query.side_effect = query_side_effect
                    response = client.post(f"{self.prefix}", json={"username": "newuser", "password": "Str0ng!Pass", "full_name": "New", "organization_id": 1})
                    assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_create_user_with_old_permissions_format(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.api.v1.auth.users.get_password_hash", return_value="hashed"):
                response = client.post(f"{self.prefix}", json={"username": "newuser2", "password": "Str0ng!Pass", "permissions": "read,write", "is_active": False})
                assert response.status_code == 200
                assert "待审核" in response.json()["message"]
        _clear_overrides(client, get_db, get_current_user)

    def test_create_user_inactive_message(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user_list=[])
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.api.v1.auth.users.get_password_hash", return_value="hashed"):
                response = client.post(f"{self.prefix}", json={"username": "newuser3", "password": "Str0ng!Pass", "is_active": False})
                assert response.status_code == 200
                assert "待审核" in response.json()["message"]
        _clear_overrides(client, get_db, get_current_user)


class TestUpdateUser:
    prefix = "/api/v1/users"

    def test_update_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/999", json={"full_name": "Updated"})
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_update_user_cannot_remove_self_admin(self, client):
        self_user = _make_user(id=1, username="admin", role="admin", is_superuser=True)
        async def mock_gcu():
            return self_user
        client.app.dependency_overrides[get_current_user] = mock_gcu
        mock_db = _make_mock_db(user=self_user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/1", json={"role": "viewer"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_update_user_org_not_found(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        user_query = mock_db.query.return_value
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.models.organization.Organization") as mock_org_cls:
                org_query = Mock()
                org_query.filter.return_value = org_query
                org_query.first.return_value = None
                def query_side_effect(model):
                    if model is mock_org_cls:
                        return org_query
                    return user_query
                mock_db.query.side_effect = query_side_effect
                response = client.put(f"{self.prefix}/2", json={"organization_id": 999})
                assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_update_user_invalid_role(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/2", json={"role": "invalid_role"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_update_user_invalid_data_scope(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/2", json={"data_scope": "invalid_scope"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_update_user_success(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/2", json={"full_name": "Updated Name", "email": "new@example.com"})
            assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)


class TestDeleteUser:
    prefix = "/api/v1/users"

    def test_delete_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.delete(f"{self.prefix}/999")
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_delete_self(self, client):
        self_user = _make_user(id=1, username="admin", role="admin", is_superuser=True)
        async def mock_gcu():
            return self_user
        client.app.dependency_overrides[get_current_user] = mock_gcu
        mock_db = _make_mock_db(user=self_user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.delete(f"{self.prefix}/1")
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_delete_user_success(self, client):
        _setup_admin_user(client)
        target = _make_user(id=2, username="other")
        mock_db = _make_mock_db(user=target)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.delete(f"{self.prefix}/2")
            assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_delete_user_not_admin(self, client):
        _setup_regular_user(client)
        target = _make_user(id=2)
        mock_db = _make_mock_db(user=target)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin", side_effect=_fake_require_admin):
            response = client.delete(f"{self.prefix}/2")
            assert response.status_code == 403
        _clear_overrides(client, get_db, get_current_user)


class TestUpdateUserPermissions:
    prefix = "/api/v1/users"

    def test_permissions_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/999/permissions", json={"role": "admin"})
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_permissions_cannot_cancel_self_admin(self, client):
        self_user = _make_user(id=1, username="admin", role="admin", is_superuser=True)
        async def mock_gcu():
            return self_user
        client.app.dependency_overrides[get_current_user] = mock_gcu
        mock_db = _make_mock_db(user=self_user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/1/permissions", json={"role": "viewer"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_permissions_org_not_found(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        user_query = mock_db.query.return_value
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.models.organization.Organization") as mock_org_cls:
                org_query = Mock()
                org_query.filter.return_value = org_query
                org_query.first.return_value = None
                def query_side_effect(model):
                    if model is mock_org_cls:
                        return org_query
                    return user_query
                mock_db.query.side_effect = query_side_effect
                response = client.put(f"{self.prefix}/2/permissions", json={"organization_id": 999})
                assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_permissions_invalid_role(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/2/permissions", json={"role": "invalid_role"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_permissions_invalid_data_scope(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/2/permissions", json={"data_scope": "invalid_scope"})
            assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_permissions_success(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, role="viewer")
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/2/permissions", json={"role": "admin", "is_active": True})
            assert response.status_code == 200
            assert response.json()["role"] == "admin"
        _clear_overrides(client, get_db, get_current_user)


class TestRoleOptions:
    prefix = "/api/v1/users"

    def test_get_role_options(self, client):
        _setup_admin_user(client)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/roles/options")
            assert response.status_code == 200
            assert len(response.json()["roles"]) == 4
        _clear_overrides(client, get_current_user)


class TestDataScopeOptions:
    prefix = "/api/v1/users"

    def test_get_data_scope_options(self, client):
        _setup_admin_user(client)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/data-scopes/options")
            assert response.status_code == 200
            assert len(response.json()["data_scopes"]) == 4
        _clear_overrides(client, get_current_user)


class TestPermissionOptions:
    prefix = "/api/v1/users"

    def test_get_permission_options(self, client):
        _setup_admin_user(client)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.get(f"{self.prefix}/permissions/options")
            assert response.status_code == 200
        _clear_overrides(client, get_current_user)


class TestAdminResetPassword:
    prefix = "/api/v1/users"

    def test_reset_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.post(f"{self.prefix}/999/admin-reset-password", json={"new_password": "NewStr0ng!Pass"})
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_reset_password_invalid(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.PasswordPolicy") as mock_policy:
                mock_policy.validate.return_value = (False, "密码强度不足")
                response = client.post(f"{self.prefix}/2/admin-reset-password", json={"new_password": "weak"})
                assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_reset_password_success(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2)
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.PasswordPolicy") as mock_policy:
                mock_policy.validate.return_value = (True, "")
                with patch("app.api.v1.auth.users.get_password_hash", return_value="new_hash"):
                    response = client.post(f"{self.prefix}/2/admin-reset-password", json={"new_password": "NewStr0ng!Pass"})
                    assert response.status_code == 200
                    assert user.revoke_all_tokens.called
                    assert user.must_change_password is True
        _clear_overrides(client, get_db, get_current_user)


class TestChangePassword:
    prefix = "/api/v1/users"

    def test_change_password_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db = _make_mock_db(user=None)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/999/password", json={"old_password": "old", "new_password": "NewStr0ng!Pass"})
            assert response.status_code == 404
        _clear_overrides(client, get_db, get_current_user)

    def test_change_password_no_permission(self, client):
        _setup_regular_user(client)
        other = _make_user(id=1, username="admin", role="admin", is_superuser=True)
        mock_db = _make_mock_db(user=other)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            response = client.put(f"{self.prefix}/1/password", json={"old_password": "old", "new_password": "NewStr0ng!Pass"})
            assert response.status_code == 401
        _clear_overrides(client, get_db, get_current_user)

    def test_change_password_wrong_old_password(self, client):
        _setup_regular_user(client)
        user = _make_user(id=2, username="regular")
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.verify_password", return_value=False):
                response = client.put(f"{self.prefix}/2/password", json={"old_password": "wrong", "new_password": "NewStr0ng!Pass"})
                assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_change_password_policy_fail(self, client):
        _setup_regular_user(client)
        user = _make_user(id=2, username="regular")
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.verify_password", return_value=True):
                with patch("app.core.security.PasswordPolicy") as mock_policy:
                    mock_policy.validate.return_value = (False, "密码强度不足")
                    response = client.put(f"{self.prefix}/2/password", json={"old_password": "correct", "new_password": "weak"})
                    assert response.status_code == 400
        _clear_overrides(client, get_db, get_current_user)

    def test_change_password_success(self, client):
        _setup_regular_user(client)
        user = _make_user(id=2, username="regular")
        mock_db = _make_mock_db(user=user)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.verify_password", return_value=True):
                with patch("app.core.security.PasswordPolicy") as mock_policy:
                    mock_policy.validate.return_value = (True, "")
                    with patch("app.api.v1.auth.users.get_password_hash", return_value="new_hash"):
                        response = client.put(f"{self.prefix}/2/password", json={"old_password": "correct", "new_password": "NewStr0ng!Pass"})
                        assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)

    def test_change_password_superuser_can_change_others(self, client):
        _setup_admin_user(client)
        other = _make_user(id=5, username="other")
        mock_db = _make_mock_db(user=other)
        _override_db(client, mock_db)
        with patch("app.api.v1.auth.users.require_admin") as mock_req:
            mock_req.return_value = None
            with patch("app.core.security.verify_password", return_value=True):
                with patch("app.core.security.PasswordPolicy") as mock_policy:
                    mock_policy.validate.return_value = (True, "")
                    with patch("app.api.v1.auth.users.get_password_hash", return_value="new_hash"):
                        response = client.put(f"{self.prefix}/5/password", json={"old_password": "any", "new_password": "NewStr0ng!Pass"})
                        assert response.status_code == 200
        _clear_overrides(client, get_db, get_current_user)
