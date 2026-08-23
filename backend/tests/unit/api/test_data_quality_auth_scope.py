"""W1-T3 安全回归：/data-quality/validate-rules 认证与数据隔离。

工单 .scratch/w1-security-redline/003
历史缺陷：端点无认证依赖且查询无组织过滤，匿名可枚举全库记录。
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.data_permission import get_data_scope
from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.main import app


def _mk_user(uid=1, username="op", role="user", org_id=10, is_superuser=False):
    u = Mock()
    u.id = uid
    u.username = username
    u.role = role
    u.organization_id = org_id
    u.is_superuser = is_superuser
    u.is_active = True
    return u


@pytest.fixture
def scoped_client(client):
    """在 conftest 内存库 client 之上注入指定用户。"""
    holder = {}

    def _install(user):
        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_active_user] = lambda: user
        holder["original"] = original_overrides
        return client

    yield _install

    if "original" in holder:
        app.dependency_overrides = holder["original"]


class TestValidateRulesAuth:
    def test_anonymous_rejected(self, client):
        """未认证调用必须 401（历史缺陷：匿名可枚举全库）。"""
        resp = client.post(
            "/api/v1/data-quality/validate-rules",
            json={"entity_type": "village",
                  "rules": [{"field": "name", "operator": "eq", "value": "x"}]},
        )
        assert resp.status_code == 401


class TestValidateRulesDataScope:
    def _seed_village(self, db_session, name, org_id):
        from datetime import date

        from app.models.supported_village import SupportedVillage

        v = SupportedVillage(
            village_name=name,
            province="贵州",
            organization_id=org_id,
            created_by=99,
        )
        # 兜底：模型若要求必填年度字段，则补默认
        if hasattr(SupportedVillage, "support_start_year"):
            v.support_start_year = v.support_start_year or 2024
        db_session.add(v)
        db_session.commit()
        db_session.refresh(v)
        return v

    def test_admin_sees_only_own_org(self, client, scoped_client):
        """OWN_DEPT 语义：admin 角色仅见本组织记录，跨组织记录不可见。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        from app.models.supported_village import SupportedVillage

        try:
            db.add(SupportedVillage(village_name="本组织村", organization_id=10))
            db.add(SupportedVillage(village_name="他组织村", organization_id=20))
            db.commit()

            original_overrides = app.dependency_overrides.copy()
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_active_user] = lambda: _mk_user(
                role="admin", org_id=10
            )
            try:
                resp = client.post(
                    "/api/v1/data-quality/validate-rules",
                    json={"entity_type": "village",
                          "rules": [{"field": "village_name", "operator": "not_empty"}]},
                )
            finally:
                app.dependency_overrides = original_overrides

            assert resp.status_code == 200, resp.text
            data = resp.json()["data"]
            # 仅本组织 1 条可见；跨组织记录不参与统计也不出现在 failed 列表
            assert data["total"] == 1, f"组织隔离失效: {data}"
            labels = [f["label"] for f in data["failed"]]
            assert all("他组织" not in lb for lb in labels)
        finally:
            db.close()

    def test_super_admin_sees_all(self, client):
        """super_admin（ALL 域）仍可跨组织统计——权限语义回归保护。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from app.models import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        from app.models.supported_village import SupportedVillage

        try:
            db.add(SupportedVillage(village_name="甲村", organization_id=10))
            db.add(SupportedVillage(village_name="乙村", organization_id=20))
            db.commit()

            original_overrides = app.dependency_overrides.copy()
            app.dependency_overrides[get_db] = lambda: db
            app.dependency_overrides[get_current_active_user] = lambda: _mk_user(
                role="super_admin", org_id=10, is_superuser=True
            )
            try:
                resp = client.post(
                    "/api/v1/data-quality/validate-rules",
                    json={"entity_type": "village",
                          "rules": [{"field": "village_name", "operator": "not_empty"}]},
                )
            finally:
                app.dependency_overrides = original_overrides

            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["total"] == 2
        finally:
            db.close()


class TestScopeSemanticsGuard:
    """确认 normalize 后角色→域映射未被破坏（防回归锚点）。"""

    def test_admin_is_own_dept(self):
        u = _mk_user(role="admin")
        assert get_data_scope(u).name == "OWN_DEPT"

    def test_plain_user_is_own(self):
        u = _mk_user(role="user")
        assert get_data_scope(u).name == "OWN"

