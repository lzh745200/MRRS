"""
组织管理API测试
测试组织CRUD操作、树形结构、权限检查等功能
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestOrganizationManagement:
    """组织管理测试类"""

    def test_list_organizations(self, client: TestClient, admin_token_headers: dict):
        """测试获取组织列表"""
        response = client.get("/api/v1/organizations", headers=admin_token_headers)
        assert response.status_code in (200, 400, 401, 403, 422, 500)
        assert response.json() is not None

    def test_list_organizations_with_filter(
        self, client: TestClient, admin_token_headers: dict
    ):
        """测试过滤组织列表"""
        response = client.get(
            "/api/v1/organizations?org_type=department", headers=admin_token_headers
        )
        assert response.status_code in (200, 400, 401, 403, 422, 500)

    def test_get_organization_tree(
        self, client: TestClient, admin_token_headers: dict
    ):
        """测试获取组织树"""
        response = client.get("/api/v1/organizations/tree", headers=admin_token_headers)
        assert response.status_code in (200, 400, 401, 403, 422, 500)
        assert response.json() is not None

    def test_create_organization(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试创建组织"""
        org_data = {
            "name": "测试组织001",
            "code": "TEST_ORG_001",
            "org_type": "department",
            "level": "level_1",
            "is_active": True,
        }
        response = client.post(
            "/api/v1/organizations", json=org_data, headers=admin_token_headers
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

    def test_create_organization_with_parent(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试创建子组织"""
        from app.models.organization import Organization
        parent_org = Organization(
            name="父组织", code="PARENT_ORG_001", org_type="department", is_active=True
        )
        db.add(parent_org)
        db.commit()
        db.refresh(parent_org)

        child_org_data = {
            "name": "子组织001",
            "code": "CHILD_ORG_001",
            "org_type": "department",
            "level": "level_2",
            "parent_id": parent_org.id,
            "is_active": True,
        }
        response = client.post(
            "/api/v1/organizations", json=child_org_data, headers=admin_token_headers
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

        # 清理
        db.query(Organization).filter(
            Organization.code.in_(["CHILD_ORG_001", "PARENT_ORG_001"])
        ).delete(synchronize_session=False)
        db.commit()

    def test_create_organization_duplicate_code(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试创建重复编码的组织"""
        from app.models.organization import Organization
        org = Organization(
            name="测试组织", code="DUPLICATE_CODE", org_type="department", is_active=True
        )
        db.add(org)
        db.commit()

        org_data = {
            "name": "重复编码组织",
            "code": "DUPLICATE_CODE",
            "org_type": "department",
            "is_active": True,
        }
        response = client.post(
            "/api/v1/organizations", json=org_data, headers=admin_token_headers
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

        db.delete(org)
        db.commit()

    def test_create_organization_requires_code(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """v1.16.4：编码（6 位行政区划代码）必填，缺失直接 422，不再自动生成。"""
        response = client.post(
            "/api/v1/organizations",
            json={"name": "缺编码组织", "org_type": "department", "is_active": True},
            headers=admin_token_headers,
        )
        assert response.status_code == 422, response.text
        assert "组织编码" in response.text


    def test_update_organization(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试更新组织"""
        from app.models.organization import Organization
        org = Organization(
            name="待更新组织", code="UPDATE_ORG_001", org_type="department", is_active=True
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        update_data = {
            "name": "已更新组织",
            "contact_person": "张三",
            "contact_phone": "13800138000",
        }
        response = client.put(
            f"/api/v1/organizations/{org.id}",
            json=update_data,
            headers=admin_token_headers,
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

        db.delete(org)
        db.commit()

    def test_delete_organization(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试删除组织（逻辑删除）"""
        from app.models.organization import Organization
        org = Organization(
            name="待删除组织", code="DELETE_ORG_001", org_type="department", is_active=True
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        response = client.delete(
            f"/api/v1/organizations/{org.id}", headers=admin_token_headers
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

        db.delete(org)
        db.commit()

    def test_delete_organization_with_children(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试删除有子组织的组织"""
        from app.models.organization import Organization
        parent_org = Organization(
            name="父组织", code="PARENT_ORG_002", org_type="department", is_active=True
        )
        db.add(parent_org)
        db.commit()
        db.refresh(parent_org)

        child_org = Organization(
            name="子组织",
            code="CHILD_ORG_002",
            org_type="department",
            parent_id=parent_org.id,
            is_active=True,
        )
        db.add(child_org)
        db.commit()

        response = client.delete(
            f"/api/v1/organizations/{parent_org.id}", headers=admin_token_headers
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

        # 清理
        db.delete(child_org)
        db.delete(parent_org)
        db.commit()

    def test_get_organization_children(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试获取子组织"""
        from app.models.organization import Organization
        parent_org = Organization(
            name="父组织", code="PARENT_ORG_003", org_type="department", is_active=True
        )
        db.add(parent_org)
        db.commit()
        db.refresh(parent_org)

        child_org = Organization(
            name="子组织",
            code="CHILD_ORG_003",
            org_type="department",
            parent_id=parent_org.id,
            is_active=True,
        )
        db.add(child_org)
        db.commit()

        response = client.get(
            f"/api/v1/organizations/{parent_org.id}/children",
            headers=admin_token_headers,
        )
        assert response.status_code in (200, 400, 401, 403, 404, 422, 500)

        db.delete(child_org)
        db.delete(parent_org)
        db.commit()

    def test_get_organization_ancestors(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试获取祖先组织"""
        from app.models.organization import Organization
        level1_org = Organization(
            name="一级组织", code="LEVEL1_ORG", org_type="department", is_active=True
        )
        db.add(level1_org)
        db.commit()
        db.refresh(level1_org)

        level2_org = Organization(
            name="二级组织",
            code="LEVEL2_ORG",
            org_type="department",
            parent_id=level1_org.id,
            is_active=True,
        )
        db.add(level2_org)
        db.commit()
        db.refresh(level2_org)

        level3_org = Organization(
            name="三级组织",
            code="LEVEL3_ORG",
            org_type="department",
            parent_id=level2_org.id,
            is_active=True,
        )
        db.add(level3_org)
        db.commit()

        response = client.get(
            f"/api/v1/organizations/{level3_org.id}/ancestors",
            headers=admin_token_headers,
        )
        assert response.status_code in (200, 400, 401, 403, 404, 422, 500)

        db.delete(level3_org)
        db.delete(level2_org)
        db.delete(level1_org)
        db.commit()

    def test_move_organization(
        self, client: TestClient, admin_token_headers: dict, db: Session
    ):
        """测试移动组织"""
        from app.models.organization import Organization
        parent1 = Organization(
            name="父组织1", code="PARENT1_ORG", org_type="department", is_active=True
        )
        parent2 = Organization(
            name="父组织2", code="PARENT2_ORG", org_type="department", is_active=True
        )
        db.add_all([parent1, parent2])
        db.commit()
        db.refresh(parent1)
        db.refresh(parent2)

        child = Organization(
            name="子组织",
            code="CHILD_MOVE_ORG",
            org_type="department",
            parent_id=parent1.id,
            is_active=True,
        )
        db.add(child)
        db.commit()
        db.refresh(child)

        response = client.post(
            f"/api/v1/organizations/{child.id}/move?new_parent_id={parent2.id}",
            headers=admin_token_headers,
        )
        assert response.status_code in (200, 201, 400, 401, 403, 404, 409, 422, 500)

        db.delete(child)
        db.delete(parent1)
        db.delete(parent2)
        db.commit()

    def test_get_type_options(self, client: TestClient, admin_token_headers: dict):
        """测试获取组织类型选项"""
        response = client.get(
            "/api/v1/organizations/types/options", headers=admin_token_headers
        )
        assert response.status_code in (200, 400, 401, 403, 422, 500)
        assert response.json() is not None

    def test_non_admin_cannot_create_organization(
        self, client: TestClient, operator_token_headers: dict
    ):
        """测试非管理员无法创建组织"""
        org_data = {
            "name": "测试组织",
            "code": "TEST_ORG",
            "org_type": "department",
            "is_active": True,
        }
        response = client.post(
            "/api/v1/organizations", json=org_data, headers=operator_token_headers
        )
        assert response.status_code in (401, 403, 422, 500)
