from unittest.mock import Mock, patch
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.database import get_db
from app.core.security import get_current_user


def _make_user(**kwargs):
    user = Mock()
    user.id = kwargs.get("id", 1)
    user.username = kwargs.get("username", "admin")
    user.email = kwargs.get("email", "admin@example.com")
    user.full_name = kwargs.get("full_name", "Admin User")
    user.hashed_password = kwargs.get("hashed_password", "hashed_pwd")
    user.role = kwargs.get("role", "admin")
    user.is_active = kwargs.get("is_active", True)
    user.is_superuser = kwargs.get("is_superuser", True)
    user.organization_id = kwargs.get("organization_id", 1)
    user.organization_name = kwargs.get("organization_name", "Org1")
    user.department = kwargs.get("department", "Dept")
    user.phone = kwargs.get("phone", "")
    user.last_login = kwargs.get("last_login", datetime.now(timezone.utc))
    user.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    user.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
    return user


def _setup_admin_user(client):
    user = _make_user(id=1, username="admin", role="admin", is_superuser=True)

    async def mock_gcu():
        return user
    client.app.dependency_overrides[get_current_user] = mock_gcu
    return user


def _setup_regular_user(client):
    user = _make_user(id=2, username="operator", role="operator", is_superuser=False)

    async def mock_gcu():
        return user
    client.app.dependency_overrides[get_current_user] = mock_gcu
    return user


def _make_mock_db():
    mock_db = Mock()
    mock_query = Mock()
    mock_db.query.return_value = mock_query
    return mock_db, mock_query


def _override_db(client, mock_db):
    def _gen():
        try:
            yield mock_db
        finally:
            pass
    client.app.dependency_overrides[get_db] = _gen


class TestGeneratePassword:
    prefix = "/api/v1/user-management"

    @patch("app.api.v1.auth.user_management.generate_password", return_value="AutoGenPass1")
    def test_generate_password_default(self, mock_gen, client):
        _setup_admin_user(client)
        response = client.get(f"{self.prefix}/generate-password")
        assert response.status_code == 200
        assert response.json()["data"]["password"] == "AutoGenPass1"

    @patch("app.api.v1.auth.user_management.generate_password", return_value="Short1")
    def test_generate_password_custom_length(self, mock_gen, client):
        _setup_admin_user(client)
        response = client.get(f"{self.prefix}/generate-password?length=8")
        assert response.status_code == 200
        mock_gen.assert_called_with(8)


class TestListRoles:
    prefix = "/api/v1/user-management"

    def test_list_roles_success(self, client):
        _setup_admin_user(client)
        mock_db, mock_query = _make_mock_db()
        mock_query.group_by.return_value.all.return_value = [
            ("super_admin", 1),
            ("admin", 2),
        ]
        _override_db(client, mock_db)

        with patch("app.api.v1.auth.user_management.func.count") as mock_count:
            mock_count.return_value = "count_col"

            response = client.get(f"{self.prefix}/roles")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total"] == 4


class TestListUsersManagement:
    prefix = "/api/v1/user-management"

    def test_non_admin_cannot_list(self, client):
        _setup_regular_user(client)
        response = client.get(f"{self.prefix}")
        assert response.status_code == 403

    def test_list_users_empty(self, client):
        _setup_admin_user(client)
        mock_db, mock_query = _make_mock_db()
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        _override_db(client, mock_db)

        response = client.get(f"{self.prefix}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

    def test_list_users_with_filters(self, client):
        _setup_admin_user(client)
        user = _make_user()
        mock_db, base_query = _make_mock_db()
        base_query.count.return_value = 1
        base_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [user]

        def filter_side(*args, **kwargs):
            return base_query
        base_query.filter = filter_side
        _override_db(client, mock_db)

        response = client.get(f"{self.prefix}?username=admin&name=Admin&status=active")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["username"] == "admin"

    def test_list_users_inactive_status(self, client):
        _setup_admin_user(client)
        user = _make_user(is_active=False)
        mock_db, base_query = _make_mock_db()
        base_query.count.return_value = 1
        base_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [user]
        base_query.filter = lambda *a, **kw: base_query
        _override_db(client, mock_db)

        response = client.get(f"{self.prefix}?status=inactive")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["status"] == "inactive"

    def test_list_users_no_last_login(self, client):
        _setup_admin_user(client)
        user = _make_user(last_login=None)
        mock_db, base_query = _make_mock_db()
        base_query.count.return_value = 1
        base_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [user]
        base_query.filter = lambda *a, **kw: base_query
        _override_db(client, mock_db)

        response = client.get(f"{self.prefix}")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["lastLogin"] == "-"

    def test_list_users_role_fallback(self, client):
        _setup_admin_user(client)
        user = _make_user(role=None, is_superuser=True)
        mock_db, base_query = _make_mock_db()
        base_query.count.return_value = 1
        base_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [user]
        base_query.filter = lambda *a, **kw: base_query
        _override_db(client, mock_db)

        response = client.get(f"{self.prefix}")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["role"] == "admin"


class TestCreateUserManagement:
    prefix = "/api/v1/user-management"

    def test_create_non_admin(self, client):
        _setup_regular_user(client)
        response = client.post(
            f"{self.prefix}",
            json={"username": "newuser", "full_name": "New User"},
        )
        assert response.status_code == 403

    def test_create_username_exists(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = _make_user()
        _override_db(client, mock_db)

        response = client.post(
            f"{self.prefix}",
            json={"username": "existing", "full_name": "Existing"},
        )
        assert response.status_code == 400
        assert "用户名已存在" in response.text

    def test_create_success_with_generated_password(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        with patch("app.api.v1.auth.user_management.generate_password", return_value="GenPwd1"):
            with patch("app.api.v1.auth.user_management.get_password_hash", return_value="hashed"):
                with patch("app.api.v1.auth.user_management.is_superuser", return_value=False):
                    response = client.post(
                        f"{self.prefix}",
                        json={"username": "newuser", "full_name": "New User", "role": "operator"},
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert data["data"]["username"] == "newuser"
                    assert data["data"]["password"] == "GenPwd1"

    def test_create_success_with_provided_password(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        with patch("app.api.v1.auth.user_management.get_password_hash", return_value="hashed"):
            with patch("app.api.v1.auth.user_management.is_superuser", return_value=False):
                response = client.post(
                    f"{self.prefix}",
                    json={"username": "newuser2", "password": "Str0ng!Pass1", "organization_id": 1},
                )
                assert response.status_code == 200

    def test_create_provided_password_fails_policy_400(self, client):
        # 覆盖 user_management.py:219 —— 管理员显式指定密码但不符合 PasswordPolicy
        # "abcdefghijkl1!" 满足 min_length=12 校验，但缺少大写字母 → 策略拒绝
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        response = client.post(
            f"{self.prefix}",
            json={"username": "newuser3", "password": "abcdefghijkl1!", "organization_id": 1},
        )
        assert response.status_code == 400
        assert "大写字母" in response.text

    def test_create_admin_role_sets_superuser(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        with patch("app.api.v1.auth.user_management.generate_password", return_value="GenPwd1"):
            with patch("app.api.v1.auth.user_management.get_password_hash", return_value="hashed"):
                with patch("app.api.v1.auth.user_management.is_superuser", return_value=True):
                    response = client.post(
                        f"{self.prefix}",
                        json={"username": "newadmin", "role": "admin", "is_active": False},
                    )
                    assert response.status_code == 200


class TestUpdateUserManagement:
    prefix = "/api/v1/user-management"

    def test_update_non_admin(self, client):
        _setup_regular_user(client)
        response = client.put(
            f"{self.prefix}/1",
            json={"full_name": "Updated"},
        )
        assert response.status_code == 403

    def test_update_not_found(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        response = client.put(
            f"{self.prefix}/999",
            json={"full_name": "Updated"},
        )
        assert response.status_code == 404

    def test_update_success(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target")
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        response = client.put(
            f"{self.prefix}/2",
            json={
                "full_name": "Updated Name",
                "email": "upd@test.com",
                "phone": "999",
                "department": "New Dept",
                "is_active": True,
                "role": "viewer",
                "organization_id": 2,
            },
        )
        assert response.status_code == 200
        assert user.full_name == "Updated Name"

    def test_update_with_status_field(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target", is_active=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        response = client.put(
            f"{self.prefix}/2",
            json={"status": "active"},
        )
        assert response.status_code == 200
        assert user.is_active is True

    def test_update_with_name_field(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target")
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        response = client.put(
            f"{self.prefix}/2",
            json={"name": "NameViaName"},
        )
        assert response.status_code == 200
        assert user.full_name == "NameViaName"

    def test_update_role_sets_superuser(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target", role="viewer", is_superuser=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        with patch("app.api.v1.auth.user_management.is_superuser", return_value=False):
            response = client.put(
                f"{self.prefix}/2",
                json={"role": "admin"},
            )
            assert response.status_code == 200
            assert user.is_superuser is True


class TestDeleteUserManagement:
    prefix = "/api/v1/user-management"

    def test_delete_non_admin(self, client):
        _setup_regular_user(client)
        response = client.delete(f"{self.prefix}/1")
        assert response.status_code == 403

    def test_delete_not_found(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        response = client.delete(f"{self.prefix}/999")
        assert response.status_code == 404

    def test_delete_super_admin_protected(self, client):
        _setup_admin_user(client)
        admin_user = _make_user(id=1, username="admin", is_superuser=True)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = admin_user
        _override_db(client, mock_db)

        response = client.delete(f"{self.prefix}/1")
        assert response.status_code == 400
        assert "系统管理员" in response.text

    def test_delete_self(self, client):
        _setup_admin_user(client)
        current_user = _make_user(id=1, username="admin", is_superuser=True)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = current_user
        _override_db(client, mock_db)

        response = client.delete(f"{self.prefix}/1")
        assert response.status_code == 400

    def test_delete_success(self, client):
        _setup_admin_user(client)
        target_user = _make_user(id=2, username="target", is_superuser=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = target_user
        _override_db(client, mock_db)

        with patch("app.services.user_cascade_delete_service.UserCascadeDeleteService") as mock_cascade:
            mock_svc_instance = Mock()
            mock_svc_instance.delete_user_cascade.return_value = {
                "success": True,
                "deleted_records": 5,
                "set_null_records": 2,
            }
            mock_cascade.return_value = mock_svc_instance

            response = client.delete(f"{self.prefix}/2")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["deleted_records"] == 5

    def test_delete_cascade_fails(self, client):
        _setup_admin_user(client)
        target_user = _make_user(id=3, username="target2", is_superuser=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = target_user
        _override_db(client, mock_db)

        with patch("app.services.user_cascade_delete_service.UserCascadeDeleteService") as mock_cascade:
            mock_svc_instance = Mock()
            mock_svc_instance.delete_user_cascade.return_value = {
                "success": False,
                "message": "User not found",
            }
            mock_cascade.return_value = mock_svc_instance

            response = client.delete(f"{self.prefix}/3")
            assert response.status_code == 404

    def test_delete_cascade_exception(self, client):
        _setup_admin_user(client)
        target_user = _make_user(id=4, username="target3", is_superuser=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = target_user
        _override_db(client, mock_db)

        with patch("app.services.user_cascade_delete_service.UserCascadeDeleteService") as mock_cascade:
            mock_svc_instance = Mock()
            mock_svc_instance.delete_user_cascade.side_effect = RuntimeError("DB crash")
            mock_cascade.return_value = mock_svc_instance

            response = client.delete(f"{self.prefix}/4")
            assert response.status_code == 500

    def test_delete_cascade_http_exception_passthrough(self, client):
        _setup_admin_user(client)
        target_user = _make_user(id=5, username="target4", is_superuser=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = target_user
        _override_db(client, mock_db)

        with patch("app.services.user_cascade_delete_service.UserCascadeDeleteService") as mock_cascade:
            mock_svc_instance = Mock()
            mock_svc_instance.delete_user_cascade.side_effect = HTTPException(400, "Bad")
            mock_cascade.return_value = mock_svc_instance

            response = client.delete(f"{self.prefix}/5")
            assert response.status_code == 400


class TestResetPasswordManagement:
    prefix = "/api/v1/user-management"

    def test_reset_non_admin(self, client):
        _setup_regular_user(client)
        response = client.post(
            f"{self.prefix}/1/reset-password",
            json={},
        )
        assert response.status_code == 403

    def test_reset_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        response = client.post(
            f"{self.prefix}/999/reset-password",
            json={},
        )
        assert response.status_code == 404

    def test_reset_password_invalid_custom(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target")
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        with patch("app.core.security.PasswordPolicy") as mock_policy:
            mock_policy.validate.return_value = (False, "弱密码")

            response = client.post(
                f"{self.prefix}/2/reset-password",
                json={"new_password": "weak"},
            )
            assert response.status_code == 400

    def test_reset_password_success_with_custom(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target")
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        with patch("app.core.security.PasswordPolicy") as mock_policy:
            mock_policy.validate.return_value = (True, "")
            with patch("app.api.v1.auth.user_management.get_password_hash", return_value="newhash"):
                response = client.post(
                    f"{self.prefix}/2/reset-password",
                    json={"new_password": "Str0ng!Pass"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["new_password"] == "Str0ng!Pass"
                assert data["data"]["username"] == "target"

    def test_reset_password_success_auto_generated(self, client):
        _setup_admin_user(client)
        user = _make_user(id=3, username="target2")
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        with patch("app.api.v1.auth.user_management.generate_password", return_value="AutoGen123"):
            with patch("app.api.v1.auth.user_management.get_password_hash", return_value="newhash"):
                response = client.post(
                    f"{self.prefix}/3/reset-password",
                    json={},
                )
                assert response.status_code == 200
                assert response.json()["data"]["new_password"] == "AutoGen123"


class TestAssignRole:
    prefix = "/api/v1/user-management"

    def test_assign_non_admin(self, client):
        _setup_regular_user(client)
        response = client.post(f"{self.prefix}/1/assign-role?role_code=admin")
        assert response.status_code == 403

    def test_assign_user_not_found(self, client):
        _setup_admin_user(client)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = None
        _override_db(client, mock_db)

        response = client.post(f"{self.prefix}/999/assign-role?role_code=admin")
        assert response.status_code == 404

    def test_assign_role_success(self, client):
        _setup_admin_user(client)
        user = _make_user(id=2, username="target", role="viewer", is_superuser=False)
        mock_db, base_query = _make_mock_db()
        base_query.filter.return_value.first.return_value = user
        _override_db(client, mock_db)

        response = client.post(f"{self.prefix}/2/assign-role?role_code=admin")
        assert response.status_code == 200
        assert user.role == "admin"
        assert user.is_superuser is True
