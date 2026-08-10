"""Comprehensive tests for organization.py — all endpoints, full branch coverage."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache_manager
from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.first.return_value = None
    db.query.return_value = q

    def _refresh(obj):
        if hasattr(obj, 'id') and (obj.id is None or isinstance(obj.id, MagicMock)):
            obj.id = 1
        if hasattr(obj, 'created_at') and obj.created_at is None:
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        if hasattr(obj, 'updated_at') and obj.updated_at is None:
            obj.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
    db.refresh.side_effect = _refresh

    return db


@pytest.fixture
def admin_user():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    u.email = "admin@test.com"
    u.is_active = True
    return u


@pytest.fixture
def regular_user():
    u = MagicMock()
    u.id = 2
    u.username = "user"
    u.role = "operator"
    u.is_superuser = False
    u.organization_id = 1
    u.is_active = True
    return u


@pytest.fixture
def client_admin(mock_db, admin_user):
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original_overrides


@pytest.fixture
def client_regular(mock_db, regular_user):
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original_overrides


def _make_mock_org(id_, name="测试组织", org_type="department", parent_id=None,
                   is_active=True, level="level_1", sort_order=0,
                   code=None, description=None, contact_person=None,
                   contact_phone=None, contact_email=None, address=None):
    org = MagicMock(spec=object)
    org.id = id_
    org.name = name
    org.code = code or f"ORG{id_:03d}"
    org.org_type = org_type
    org.level = level
    org.parent_id = parent_id
    org.is_active = is_active
    org.sort_order = sort_order
    org.description = description
    org.contact_person = contact_person
    org.contact_phone = contact_phone
    org.contact_email = contact_email
    org.address = address
    org.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    org.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
    return org


# ---------------------------------------------------------------------------
#  GET /organizations
# ---------------------------------------------------------------------------

class TestGetOrganizations:
    def test_default_list(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 2
        q.all.return_value = [_make_mock_org(1), _make_mock_org(2)]
        with patch.object(cache_manager, "get", AsyncMock(return_value=None)):
            resp = client_admin.get("/api/v1/organizations")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_with_filters(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_org(1)]
        resp = client_admin.get(
            "/api/v1/organizations?org_type=department&is_active=true&keyword=测试&page=1&page_size=10"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_list_with_parent_id_filter(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_org(2, parent_id=1)]
        resp = client_admin.get("/api/v1/organizations?parent_id=1")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_list_with_search(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_org(1)]
        resp = client_admin.get("/api/v1/organizations?search=测试")
        assert resp.status_code == 200

    def test_list_from_cache(self, client_admin, mock_db):
        cached = {"code": 200, "success": True, "message": "成功", "data": {"items": [], "total": 0, "page": 1, "page_size": 20}}
        with patch.object(cache_manager, "get", AsyncMock(return_value=cached)) as m:
            resp = client_admin.get("/api/v1/organizations")
            assert resp.status_code == 200
            assert resp.json()["data"]["total"] == 0
            m.assert_awaited_once_with("orgs:list")

    def test_list_writes_cache(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 0
        q.all.return_value = []
        with patch.object(cache_manager, "get", AsyncMock(return_value=None)):
            with patch.object(cache_manager, "set", AsyncMock()) as m:
                resp = client_admin.get("/api/v1/organizations")
                assert resp.status_code == 200
                m.assert_awaited_once()

    def test_list_exception(self, client_admin, mock_db):
        mock_db.query.side_effect = Exception("DB error")
        with patch.object(cache_manager, "get", AsyncMock(return_value=None)):
            resp = client_admin.get("/api/v1/organizations")
        assert resp.status_code == 500
        assert "获取组织列表失败" in resp.json()["detail"]


# ---------------------------------------------------------------------------
#  GET /organizations/tree
# ---------------------------------------------------------------------------

class TestGetOrganizationTree:
    def test_tree_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        parent = _make_mock_org(1, name="根组织", parent_id=None)
        child = _make_mock_org(2, name="子组织", parent_id=1)
        q.all.return_value = [parent, child]
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "根组织"
        assert len(data[0]["children"]) == 1

    def test_tree_with_org_type(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = []
        resp = client_admin.get("/api/v1/organizations/tree?org_type=support_unit")
        assert resp.status_code == 200

    def test_tree_level_number(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = [_make_mock_org(1, level="level_3")]
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.json()[0]["level"] == 3

    def test_tree_level_fallback(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = [_make_mock_org(1, level="invalid")]
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.json()[0]["level"] == 0

    def test_tree_level_parse_error(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = [_make_mock_org(1, level="level_abc")]
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.json()[0]["level"] == 0

    def test_tree_cycle_detected(self, client_admin, mock_db):
        a = _make_mock_org(1, name="A", parent_id=2)
        a2 = _make_mock_org(2, name="B", parent_id=1)
        mock_db.query.return_value.all.return_value = [a, a2]
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.status_code == 200

    def test_tree_orphan_parent(self, client_admin, mock_db):
        child = _make_mock_org(2, name="孤立子", parent_id=999)
        mock_db.query.return_value.all.return_value = [child]
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.status_code == 200
        # orphan should still appear as child-less node
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "孤立子"

    def test_tree_exception(self, client_admin, mock_db):
        mock_db.query.side_effect = Exception("Tree error")
        resp = client_admin.get("/api/v1/organizations/tree")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  GET /organizations/my-organization
# ---------------------------------------------------------------------------

class TestGetMyOrganization:
    def test_my_has_org(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_org(1)
        resp = client_admin.get("/api/v1/organizations/my-organization")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_my_fallback_to_first_active(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.side_effect = [None, _make_mock_org(1)]

        resp = client_admin.get("/api/v1/organizations/my-organization")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_my_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client_admin.get("/api/v1/organizations/my-organization")
        assert resp.status_code == 404

    def test_my_exception(self, client_admin, mock_db):
        mock_db.query.side_effect = Exception("Err")
        resp = client_admin.get("/api/v1/organizations/my-organization")
        assert resp.status_code == 500

    def test_my_alias(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_org(1)
        resp = client_admin.get("/api/v1/organizations/my")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1


# ---------------------------------------------------------------------------
#  GET /organizations/subordinates
# ---------------------------------------------------------------------------

class TestGetSubordinates:
    def test_include_self(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = [_make_mock_org(1)]
        resp = client_admin.get("/api/v1/organizations/subordinates?include_self=true")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_exclude_self(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = [_make_mock_org(2)]
        resp = client_admin.get("/api/v1/organizations/subordinates")
        assert resp.status_code == 200

    def test_subordinates_exception(self, client_admin, mock_db):
        mock_db.query.side_effect = Exception("Err")
        resp = client_admin.get("/api/v1/organizations/subordinates")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
#  GET /organizations/types/options
# ---------------------------------------------------------------------------

class TestGetTypeOptions:
    def test_options(self, client_admin):
        resp = client_admin.get("/api/v1/organizations/types/options")
        assert resp.status_code == 200
        assert len(resp.json()["types"]) == 2
        assert len(resp.json()["levels"]) == 4


# ---------------------------------------------------------------------------
#  GET /organizations/{org_id}
# ---------------------------------------------------------------------------

class TestGetOrganization:
    def test_get_success(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = _make_mock_org(1)
        resp = client_admin.get("/api/v1/organizations/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_get_not_found(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.get("/api/v1/organizations/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  POST /organizations
# ---------------------------------------------------------------------------

class TestCreateOrganization:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/organizations", json={"name": "新组织"})
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.post("/api/v1/organizations", json={
            "name": "新组织", "org_type": "department", "level": "level_2",
        })
        assert resp.status_code == 200
        # write_work_log 成功时会额外 add WorkLog
        assert mock_db.add.call_count >= 1
        # safe_commit + write_work_log 可能导致多次 commit
        assert mock_db.commit.call_count >= 1

    def test_duplicate_code(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = _make_mock_org(1)
        resp = client_admin.post("/api/v1/organizations", json={
            "name": "重复", "code": "DUP",
        })
        assert resp.status_code == 400

    def test_without_code_no_dup_check(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.post("/api/v1/organizations", json={"name": "无编码"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
#  PUT /organizations/{org_id}
# ---------------------------------------------------------------------------

class TestUpdateOrganization:
    def test_permission_denied(self, client_regular):
        resp = client_regular.put("/api/v1/organizations/1", json={"name": "x"})
        assert resp.status_code == 403

    def test_not_found(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.put("/api/v1/organizations/999", json={"name": "x"})
        assert resp.status_code == 404

    def test_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_org(1)
        resp = client_admin.put("/api/v1/organizations/1", json={"name": "新名称"})
        assert resp.status_code == 200

    def test_duplicate_code(self, client_admin, mock_db):
        q = mock_db.query.return_value
        existing = _make_mock_org(2)
        q.first.side_effect = [existing, _make_mock_org(1)]
        resp = client_admin.put("/api/v1/organizations/1", json={"code": "DUP", "name": "测试"})
        assert resp.status_code == 400

    def test_update_with_org_type_and_level(self, client_admin, mock_db):
        q = mock_db.query.return_value
        org = _make_mock_org(1)
        q.first.return_value = org
        resp = client_admin.put("/api/v1/organizations/1", json={
            "org_type": "support_unit", "level": "level_3",
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
#  DELETE /organizations/{org_id}
# ---------------------------------------------------------------------------

class TestDeleteOrganization:
    def _mock_user_password(self, mock_db, password_hash):
        """mock User 密码校验查询通过"""
        from app.models.user import User

        def _query(model):
            if model is User:
                q = MagicMock(name="user_q")
                q.filter.return_value.first.return_value = SimpleNamespace(
                    id=1, hashed_password=password_hash,
                )
                return q
            return mock_db.query.return_value

        mock_db.query.side_effect = _query

    def test_permission_denied(self, client_regular):
        resp = client_regular.delete("/api/v1/organizations/1")
        assert resp.status_code == 403

    def test_bad_confirm_password(self, client_admin, mock_db):
        # 密码不匹配 → 400 二次确认失败
        from app.core.security import hash_password

        self._mock_user_password(mock_db, hash_password("real-pass"))
        resp = client_admin.delete("/api/v1/organizations/1?confirm_password=wrong")
        assert resp.status_code == 400
        assert "二次确认" in resp.text

    def test_not_found(self, client_admin, mock_db):
        from app.core.security import hash_password

        self._mock_user_password(mock_db, hash_password("pass123"))
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.delete("/api/v1/organizations/999?confirm_password=pass123")
        assert resp.status_code == 404

    def test_has_children(self, client_admin, mock_db):
        from app.core.security import hash_password

        self._mock_user_password(mock_db, hash_password("pass123"))
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_org(1)
        children_q = MagicMock(name="children_q")
        children_q.filter.return_value = children_q
        children_q.count.return_value = 2
        mock_db.query.return_value = children_q
        resp = client_admin.delete("/api/v1/organizations/1?confirm_password=pass123")
        assert resp.status_code == 400

    def test_success(self, client_admin, mock_db):
        from app.core.security import hash_password

        self._mock_user_password(mock_db, hash_password("pass123"))
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_org(1)
        children_q = MagicMock(name="children_q")
        children_q.filter.return_value = children_q
        children_q.count.return_value = 0
        mock_db.query.return_value = children_q
        resp = client_admin.delete("/api/v1/organizations/1?confirm_password=pass123")
        assert resp.status_code == 200
        assert resp.json()["type"] == "soft_delete"


# ---------------------------------------------------------------------------
#  GET /organizations/{org_id}/children
# ---------------------------------------------------------------------------

class TestGetChildren:
    def test_success(self, client_admin, mock_db):
        mock_db.query.return_value.all.return_value = [_make_mock_org(2, parent_id=1)]
        resp = client_admin.get("/api/v1/organizations/1/children")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
#  GET /organizations/{org_id}/ancestors
# ---------------------------------------------------------------------------

class TestGetAncestors:
    def test_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        child = _make_mock_org(3, parent_id=2)
        p2 = _make_mock_org(2, parent_id=1)
        p1 = _make_mock_org(1, parent_id=None)
        q.first.side_effect = [child, p2, p1]

        resp = client_admin.get("/api/v1/organizations/3/ancestors")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_parent_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        child = _make_mock_org(3, parent_id=2)
        q.first.side_effect = [child, None]

        resp = client_admin.get("/api/v1/organizations/3/ancestors")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_not_found(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.get("/api/v1/organizations/999/ancestors")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
#  POST /organizations/{org_id}/move
# ---------------------------------------------------------------------------

class TestMoveOrganization:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/organizations/1/move", json={})
        assert resp.status_code == 403

    def test_org_not_found(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.post("/api/v1/organizations/999/move", json={})
        assert resp.status_code == 404

    def test_parent_not_found(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.first.side_effect = [_make_mock_org(1), None]
        resp = client_admin.post("/api/v1/organizations/1/move", json={"new_parent_id": 999})
        assert resp.status_code == 404

    def test_cycle_detected(self, client_admin, mock_db):
        q = mock_db.query.return_value
        org = _make_mock_org(1)
        parent = _make_mock_org(2, parent_id=1)
        q.first.side_effect = [org, parent, parent]

        resp = client_admin.post("/api/v1/organizations/1/move", json={"new_parent_id": 2})
        assert resp.status_code == 400

    def test_move_to_null(self, client_admin, mock_db):
        q = mock_db.query.return_value
        org = _make_mock_org(1)
        q.first.return_value = org
        resp = client_admin.post("/api/v1/organizations/1/move", json={"new_parent_id": None})
        assert resp.status_code == 200
        assert org.parent_id is None


# ---------------------------------------------------------------------------
#  POST /organizations/batch-update-sort
# ---------------------------------------------------------------------------

class TestBatchUpdateSort:
    def test_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/organizations/batch-update-sort", json={
            "items": [{"id": 1, "sort_order": 1}]
        })
        assert resp.status_code == 403

    def test_success(self, client_admin, mock_db):
        svc = MagicMock()
        svc.batch_update_sort_orders.return_value = (True, 3)
        with patch("app.api.v1.organization.OrganizationService", return_value=svc):
            resp = client_admin.post("/api/v1/organizations/batch-update-sort", json={
                "items": [{"id": 1, "sort_order": 1}, {"id": 2, "sort_order": 2}]
            })
            assert resp.status_code == 200
            assert resp.json()["data"]["updated_count"] == 3

    def test_service_fail(self, client_admin, mock_db):
        svc = MagicMock()
        svc.batch_update_sort_orders.return_value = (False, 0)
        with patch("app.api.v1.organization.OrganizationService", return_value=svc):
            resp = client_admin.post("/api/v1/organizations/batch-update-sort", json={
                "items": [{"id": 1, "sort_order": 1}]
            })
            assert resp.status_code == 500

    def test_service_raises(self, client_admin, mock_db):
        svc = MagicMock()
        svc.batch_update_sort_orders.side_effect = ValueError("Boom")
        with patch("app.api.v1.organization.OrganizationService", return_value=svc):
            resp = client_admin.post("/api/v1/organizations/batch-update-sort", json={
                "items": [{"id": 1, "sort_order": 1}]
            })
            assert resp.status_code == 500

    def test_http_exception_re_raised(self, client_admin, mock_db):
        from fastapi import HTTPException
        svc = MagicMock()
        svc.batch_update_sort_orders.side_effect = HTTPException(400, "custom")
        with patch("app.api.v1.organization.OrganizationService", return_value=svc):
            resp = client_admin.post("/api/v1/organizations/batch-update-sort", json={
                "items": [{"id": 1, "sort_order": 1}]
            })
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
#  POST /organizations/{org_id}/activate & /deactivate
# ---------------------------------------------------------------------------

class TestActivateDeactivate:
    def test_activate_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/organizations/1/activate")
        assert resp.status_code == 403

    def test_activate_not_found(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.post("/api/v1/organizations/999/activate")
        assert resp.status_code == 404

    def test_activate_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        org = _make_mock_org(1, is_active=False)
        q.first.return_value = org
        resp = client_admin.post("/api/v1/organizations/1/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True
        assert org.is_active is True

    def test_deactivate_permission_denied(self, client_regular):
        resp = client_regular.post("/api/v1/organizations/1/deactivate")
        assert resp.status_code == 403

    def test_deactivate_not_found(self, client_admin, mock_db):
        mock_db.query.return_value.first.return_value = None
        resp = client_admin.post("/api/v1/organizations/999/deactivate")
        assert resp.status_code == 404

    def test_deactivate_success(self, client_admin, mock_db):
        q = mock_db.query.return_value
        org = _make_mock_org(1, is_active=True)
        q.first.return_value = org
        resp = client_admin.post("/api/v1/organizations/1/deactivate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert org.is_active is False


# ---------------------------------------------------------------------------
#  /statistics/summary 与 /export/list（路由前移后可达，补全分支覆盖）
# ---------------------------------------------------------------------------


class TestStatisticsSummary:
    def test_summary_full(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.group_by.return_value = q
        # total=5, active=3, orgs_with_members=2, total_members=5
        q.scalar.side_effect = [5, 3, 2, 5]
        q.all.side_effect = [
            [("department", 3), (None, 2)],  # 类型分布（含 None → unknown）
            [("level_1", 4), (None, 1)],  # 层级分布（含 None → unknown）
        ]
        resp = client_admin.get("/api/v1/organizations/statistics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 5
        assert data["active"] == 3
        assert data["inactive"] == 2
        assert data["type_distribution"] == {"department": 3, "unknown": 2}
        assert data["level_distribution"] == {"level_1": 4, "unknown": 1}
        assert data["orgs_with_members"] == 2
        assert data["total_members"] == 5


class TestExportOrganizations:
    def test_forbidden_for_regular_user(self, client_regular):
        resp = client_regular.get("/api/v1/organizations/export/list")
        assert resp.status_code == 403

    def test_export_success_with_filters(self, client_admin, mock_db):
        q = mock_db.query.return_value
        org1 = _make_mock_org(1, org_type="department", is_active=True)
        org2 = _make_mock_org(2, org_type=None, is_active=False)
        org2.code = ""  # code or "" 兜底
        org2.level = None  # level 空值兜底
        org2.created_at = None  # created_at 空值兜底
        q.all.return_value = [org1, org2]
        q.scalar.side_effect = [2, 0]  # 成员数；0 走 or 0 分支
        resp = client_admin.get(
            "/api/v1/organizations/export/list?org_type=department&is_active=true"
        )
        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(resp.content) > 100  # 真实 Excel 字节流

    def test_export_success_no_filters(self, client_admin, mock_db):
        q = mock_db.query.return_value
        q.all.return_value = [_make_mock_org(1)]
        q.scalar.side_effect = [1]
        resp = client_admin.get("/api/v1/organizations/export/list")
        assert resp.status_code == 200

    def test_export_http_exception_passthrough(self, client_admin, mock_db, monkeypatch):
        """try 内抛出 HTTPException → except HTTPException: raise 原样透传"""
        from fastapi import HTTPException

        class RaisingService:
            def export_organizations(self, **kwargs):
                raise HTTPException(status_code=400, detail="导出参数错误")

        monkeypatch.setattr(
            "app.services.export_service.ExcelExportService", RaisingService
        )
        q = mock_db.query.return_value
        q.all.return_value = []
        resp = client_admin.get("/api/v1/organizations/export/list")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "导出参数错误"
