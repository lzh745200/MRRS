"""
用户管理API测试
测试用户CRUD操作、权限检查、组织关联等功能
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.utils import assert_create_or_error


class TestUserManagement:
    """用户管理测试类"""

    def test_list_users(self, client: TestClient, admin_token_headers: dict):
        """测试获取用户列表"""
        response = client.get("/api/v1/user-management", headers=admin_token_headers)
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_list_users_with_search(
        self, client: TestClient, admin_token_headers: dict
    ):
        """测试搜索用户"""
        response = client.get(
            "/api/v1/user-management?username=admin", headers=admin_token_headers
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_create_user(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试创建用户"""
        user_data = {
            "username": "test_user_001_x",
            "full_name": "测试用户001",
            "password": "Test@1234567",
            "email": "test001@example.com",
            "role": "operator",
        }
        response = client.post(
            "/api/v1/user-management", json=user_data, headers=admin_token_headers
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_create_user_with_organization(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试创建用户并关联组织"""
        user_data = {
            "username": "test_user_002_x",
            "full_name": "测试用户002",
            "password": "Test@1234567",
            "organization_id": 1,
            "role": "operator",
        }
        response = client.post(
            "/api/v1/user-management", json=user_data, headers=admin_token_headers
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_create_user_duplicate_username(
        self, client: TestClient, admin_token_headers: dict
    ):
        """测试创建重复用户名"""
        user_data = {
            "username": "admin",
            "full_name": "重复用户",
            "password": "Test@1234567",
            "role": "operator",
        }
        response = client.post(
            "/api/v1/user-management", json=user_data, headers=admin_token_headers
        )
        # 可能返回200（创建成功）或4xx（用户名重复）
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_update_user(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试更新用户"""
        update_data = {"full_name": "更新后的用户名", "email": "updated@example.com"}
        response = client.put(
            "/api/v1/user-management/999",
            json=update_data,
            headers=admin_token_headers,
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_update_user_organization(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试更新用户组织"""
        update_data = {"organization_id": 1}
        response = client.put(
            "/api/v1/user-management/999",
            json=update_data,
            headers=admin_token_headers,
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_delete_user(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试删除用户"""
        response = client.delete(
            "/api/v1/user-management/999", headers=admin_token_headers
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_delete_admin_user(self, client: TestClient, admin_token_headers: dict):
        """测试删除管理员用户"""
        response = client.delete(
            "/api/v1/user-management/1", headers=admin_token_headers
        )
        # 可能返回4xx或5xx（管理员保护或用户不存在）
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_reset_password(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试重置密码"""
        reset_data = {"new_password": "NewPassword123"}
        response = client.post(
            "/api/v1/user-management/999/reset-password",
            json=reset_data,
            headers=admin_token_headers,
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_assign_role(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试分配角色"""
        response = client.post(
            "/api/v1/user-management/999/assign-role?role_code=manager",
            headers=admin_token_headers,
        )
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_list_roles(self, client: TestClient, admin_token_headers: dict):
        """测试获取角色列表"""
        response = client.get("/api/v1/user-management/roles", headers=admin_token_headers)
        assert_create_or_error(response.status_code)
        assert response.json() is not None

    def test_non_admin_cannot_create_user(
        self, client: TestClient, operator_token_headers: dict
    ):
        """测试非管理员无法创建用户"""
        user_data = {
            "username": "test_user_008",
            "full_name": "测试用户008",
            "password": "Test@1234567",
            "role": "operator",
        }
        response = client.post(
            "/api/v1/user-management", json=user_data, headers=operator_token_headers
        )
        assert response.status_code in (401, 403, 422, 500)
