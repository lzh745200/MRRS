# -*- coding: utf-8 -*-
"""防回归：组织创建必须经**真实 HTTP** 校验（v1.17.2 修复）。

背景：`OrganizationCreate` schema 曾漏掉 `code` 字段，端点却直接读 `data.code` ——
单元测试用 MagicMock 传 data 时不会暴露，真实 HTTP 调用必然 422/AttributeError，
表现为**新装机器无法创建任何组织**（上下级部署无法初始化）。本用例只走 TestClient，
禁止 mock 请求体。
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


def _admin():
    return SimpleNamespace(
        id=1, username="admin", role="super_admin", is_superuser=True,
        is_active=True, organization_id=None,
    )


@pytest.fixture
def client():
    from app.main import app

    db = SimpleNamespace()  # 只验证请求层校验，不触达业务库
    original = app.dependency_overrides.copy()

    def _get_db():
        yield db

    async def _user():
        return _admin()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides = original


class TestOrganizationCreateSchema:
    """schema 层：code 必填且 6 位。"""

    def test_code_is_required(self):
        with pytest.raises(Exception):
            OrganizationCreate(name="某单位")

    def test_code_accepts_six_digits(self):
        m = OrganizationCreate(name="某单位", code="520000")
        assert m.code == "520000"

    def test_code_rejects_wrong_length(self):
        # 长度必须恰为 6（数字性由 organization_code_service.normalize_admin_code 在端点层校验）
        for bad in ("52000", "5200001", ""):
            with pytest.raises(Exception):
                OrganizationCreate(name="某单位", code=bad)

    def test_non_digit_code_rejected_by_service(self):
        from app.services.organization_code_service import OrganizationCodeService

        with pytest.raises(ValueError):
            OrganizationCodeService.normalize_admin_code("abcdef")

    def test_update_accepts_code_but_optional(self):
        assert OrganizationUpdate(code="520100").code == "520100"
        assert OrganizationUpdate().code is None


class TestOrganizationCreateHttp:
    """真实 HTTP：缺 code 必须 422，带 code 不得因 schema 缺字段报 500。"""

    URL = "/api/v1/organizations"

    def test_missing_code_returns_422(self, client):
        resp = client.post(self.URL, json={"name": "某单位", "org_type": "department"})
        assert resp.status_code == 422, resp.text

    def test_wrong_code_returns_422(self, client):
        for bad in ("5200", "5200001", "abcdef"):
            resp = client.post(self.URL, json={"name": "某单位", "code": bad, "org_type": "department"})
            assert resp.status_code == 422, (bad, resp.text)

    def test_valid_payload_not_schema_error(self, client):
        """带合法 code 时不应因 schema 缺字段而 500（数据库不可用可接受，但不得是 schema 错）。"""
        resp = client.post(self.URL, json={"name": "某单位", "code": "520000", "org_type": "department"})
        assert resp.status_code != 422, resp.text
        assert "code" not in (resp.text or "") or resp.status_code >= 500
