"""R24 回归锁定：组织创建/更新的非法枚举值必须 422，而不是 500。

安装包验收实测：`POST /organizations` 带 `level="1"` 返回
`{"code":500,"message":"服务器内部错误"}` —— `OrganizationLevel("1")` 抛 ValueError
直接冒泡。前端下拉只给合法值，但接口是公开契约，非法输入属用户可纠正错误。
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base


@pytest.fixture
def client(real_db_session):
    from app.main import app

    def _get_db():
        yield real_db_session

    admin = Mock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "super_admin"
    admin.is_superuser = True
    admin.is_active = True

    async def _get_current_user():
        return admin

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


class TestInvalidOrgEnums:
    def test_invalid_level_returns_422(self, client):
        resp = client.post("/api/v1/organizations", json={"name": "R24 单位", "level": "1"})
        assert resp.status_code == 422
        assert "无效的组织层级" in resp.text
        assert "level_1" in resp.text

    def test_invalid_org_type_returns_422(self, client):
        resp = client.post("/api/v1/organizations", json={"name": "R24 单位", "org_type": "military"})
        assert resp.status_code == 422
        assert "无效的组织类型" in resp.text
        assert "department" in resp.text

    def test_valid_enums_accepted(self, client):
        resp = client.post(
            "/api/v1/organizations",
            json={"name": "R24 合法单位", "level": "level_1", "org_type": "department"},
        )
        assert resp.status_code in (200, 201), resp.text

    def test_update_invalid_level_returns_422(self, client, real_db_session):
        created = client.post(
            "/api/v1/organizations", json={"name": "R24 待更新单位", "level": "level_1"}
        )
        assert created.status_code in (200, 201)
        oid = created.json()["id"]

        resp = client.put(f"/api/v1/organizations/{oid}", json={"level": "9"})
        assert resp.status_code == 422
        assert "无效的组织层级" in resp.text
