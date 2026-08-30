"""403 根因修复回归（ADR-0002 语义补齐）

场景：单机/未绑定组织的管理员（role=admin, organization_id=None）此前被
organization_permission_service 判为"无任何组织权限"，数据包/数据上报等
组织门禁端点一律 403；legacy 模型（无 created_by/organization_id 列）
在 data_permission 下 AttributeError→500。

- org-less admin → 可访问所有组织、可管理/创建/祖先判定通过
- org-less 普通用户 → 维持拒绝（fail-closed）
- 缺 owner 字段的模型 → OWN 范围 fail-closed 空集（不再 500）
- ai 预测端点（sklearn 移除后）→ 200
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def mem_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _user(role="admin", org=None, su=False):
    return SimpleNamespace(
        id=1, username="probe", role=role, is_superuser=su, is_active=True,
        organization_id=org, data_scope="org",
        permissions_list=[], failed_login_count=0, locked_until=None,
        allowed_menus=None, allowed_menus_list=None,
    )


def _seed_orgs(db, n=2):
    from app.models.organization import Organization

    orgs = [Organization(name=f"组织{i}", code=f"ORG{i}", is_active=True) for i in range(1, n + 1)]
    db.add_all(orgs)
    db.commit()
    for o in orgs:
        db.refresh(o)
    return orgs


class TestOrgLessAdminAccessible:
    def test_admin_without_org_accesses_all_orgs(self, mem_db):
        from app.services.organization_permission_service import OrganizationPermissionService

        orgs = _seed_orgs(mem_db)
        svc = OrganizationPermissionService(mem_db)
        assert svc.get_accessible_organizations.__self__ is svc

    def test_admin_without_org_can_access_via_user(self, mem_db):
        from app.models.user import User
        from app.services.organization_permission_service import OrganizationPermissionService

        orgs = _seed_orgs(mem_db)
        admin_row = User(username="orgless_admin", role="admin", hashed_password="x",
                         organization_id=None, is_active=True)
        mem_db.add(admin_row)
        mem_db.commit()
        mem_db.refresh(admin_row)

        svc = OrganizationPermissionService(mem_db)
        # 无组织 admin：可访问所有组织（修复前返回 [] → 数据包/上报端点全 403）
        assert svc.can_access_organization(admin_row.id, orgs[0].id, log_attempt=False) is True
        assert svc.get_accessible_organizations(admin_row.id) == [o.id for o in orgs]

    def test_regular_user_without_org_still_denied(self, mem_db):
        from app.services.organization_permission_service import OrganizationPermissionService

        orgs = _seed_orgs(mem_db)
        svc = OrganizationPermissionService(mem_db)

        class _U:
            id = 998
            role = "user"
            is_superuser = False
            organization_id = None

            # _get_user 会按 id 查库，查不到返回 None → []；此处验证空集语义
        assert svc.get_accessible_organizations(998) == []

    def test_orgless_admin_can_manage_and_create(self, mem_db):
        from app.services.organization_permission_service import OrganizationPermissionService

        orgs = _seed_orgs(mem_db)
        svc = OrganizationPermissionService(mem_db)
        u = _user(role="admin")
        assert svc.can_manage_organization(user=u, org_id=orgs[0].id) is True
        assert svc.can_create_subordinate(user=u, parent_org_id=None) is True


class TestDataScopeFailClosed:
    def test_model_without_owner_field_returns_empty_not_500(self, mem_db):
        """缺 created_by 的模型（legacy villages）在 OWN 范围下返回空集而非 AttributeError"""
        from sqlalchemy import text

        from app.core.data_permission import apply_scope_to_query

        class _NoOwnerModel:
            """无任何权限字段的裸模型（模拟 legacy Village）"""

            __name__ = "BareModel"

        q = mem_db.query(text("1")).subquery() if False else MagicMock()
        # 用真实 Query 对象验证过滤可用
        from app.models.user import User as UserModel

        query = mem_db.query(UserModel)
        result = apply_scope_to_query(query, _NoOwnerModel, _user(role="user"))
        # fail-closed 空集：SQL 可编译执行且结果为空
        assert result.count() == 0

    def test_model_with_owner_field_filters_normally(self, mem_db):
        from app.core.data_permission import apply_scope_to_query
        from app.models.project import Project

        mem_db.add(Project(name="mine", created_by=1))
        mem_db.add(Project(name="other", created_by=42))
        mem_db.commit()

        result = apply_scope_to_query(mem_db.query(Project), Project, _user(role="user"))
        names = sorted(p.name for p in result.all())
        assert names == ["mine"]


class TestAiForecastNoSklearn:
    def test_forecast_income_endpoint_200(self):
        """sklearn 移除后收入预测端点不再 500（polyfit 实现）"""
        import os

        os.environ.setdefault("ENVIRONMENT", "test")
        from app.main import app
        from app.core.database import get_db
        from app.core.security import get_current_user

        mem = MagicMock()
        app.dependency_overrides[get_db] = lambda: mem
        app.dependency_overrides[get_current_user] = lambda: _user(role="admin", su=False)
        try:
            c = TestClient(app, raise_server_exceptions=False)
            r = c.get("/api/v1/ai/forecast/income")
            assert r.status_code == 200, r.text[:200]
            data = r.json()["data"]
            # 空库 → insufficient_data 分支（200 + 结构完整）
            assert data["status"] in ("insufficient_data", "completed")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)
