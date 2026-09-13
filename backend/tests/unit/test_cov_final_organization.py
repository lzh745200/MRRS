"""app.api.v1.organization 覆盖补全 —
- create_organization: is_active 缺省补 True 分支 (line 530，schema 默认会带该字段，直接调用构造)
- update_organization: parent_id 设为自身的 400 分支 (line 588)
- get_organization_detail: 上级组织路径遍历循环 (lines 892-897)
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mocks():
    db = MagicMock(name="db")
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = []
    q.first.return_value = None
    db.query.return_value = q

    user = MagicMock(name="user")
    user.id = 1
    user.role = "admin"
    user.is_superuser = True
    user.username = "admin"
    return db, q, user


@pytest.fixture
def client(mocks):
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    db, _, user = mocks
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    tc = TestClient(app, raise_server_exceptions=False)
    yield tc
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


class TestCreateOrganization:
    async def test_is_active_defaulted_when_absent(self):
        """model_dump 结果不含 is_active → 补 True (line 530)

        OrganizationCreate schema 总是携带 is_active，HTTP 层不可达，直接调用构造。
        """
        from app.api.v1.organization import create_organization

        data = MagicMock(name="data")
        data.code = None
        data.model_dump.return_value = {"name": "新组织", "sort_order": 3}

        db = MagicMock(name="db")
        user = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=False)

        with patch("app.api.v1.organization.safe_commit"):
            with patch("app.api.v1.organization.write_work_log"):
                with patch("app.api.v1.organization.cache_manager") as cm:
                    cm.delete = AsyncMock()
                    resp = await create_organization(data, user, db)

        # R7-F1：信封返回（code/data/message；data 内为 ORM 组织对象）
        assert resp["code"] == 200
        created = resp["data"]
        assert created.name == "新组织"
        assert created.is_active is True
        db.add.assert_called_once()


class TestUpdateOrganization:
    def test_parent_id_equal_self_rejected(self, client, mocks):
        _, q, _ = mocks
        q.first.return_value = MagicMock(name="org", id=5)
        resp = client.put("/api/v1/organizations/5", json={"parent_id": 5})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "不能将组织自身设为上级组织"


class TestOrganizationDetail:
    def test_ancestor_path_walked(self, client, mocks):
        """org.parent_id 非空 → while 循环向上遍历上级组织 (lines 892-897)"""
        _, q, _ = mocks
        org = MagicMock(name="org")
        org.id = 5
        org.name = "本组织"
        org.code = "ORG1"
        org.org_type = None
        org.level = None
        org.parent_id = 2
        org.is_active = True
        org.sort_order = 1
        org.description = None
        org.contact_person = None
        org.contact_phone = None
        org.contact_email = None
        org.address = None
        org.created_at = None
        org.updated_at = None

        parent = MagicMock(name="parent")
        parent.id = 2
        parent.name = "上级组织"
        parent.parent_id = None

        # first() 依次对应: 详情查询 org、祖先遍历 parent
        q.first.side_effect = [org, parent]
        q.scalar.return_value = 2
        q.all.return_value = []

        resp = client.get("/api/v1/organizations/5/detail")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ancestors"] == [{"id": 2, "name": "上级组织"}]
        assert data["parent_name"] == "上级组织"

    def test_ancestor_record_missing_breaks_walk(self, client, mocks):
        """祖先组织在库中已被删除 → parent 查询为 None → break (line 895)"""
        _, q, _ = mocks
        org = MagicMock(name="org")
        org.id = 5
        org.name = "本组织"
        org.code = "ORG1"
        org.org_type = None
        org.level = None
        org.parent_id = 99
        org.is_active = True
        org.sort_order = 1
        org.description = None
        org.contact_person = None
        org.contact_phone = None
        org.contact_email = None
        org.address = None
        org.created_at = None
        org.updated_at = None

        # first() 依次对应: 详情查询 org、祖先遍历 → None (已被删除)
        q.first.side_effect = [org, None]
        q.scalar.return_value = 0
        q.all.return_value = []

        resp = client.get("/api/v1/organizations/5/detail")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ancestors"] == []
        assert data["parent_name"] is None
