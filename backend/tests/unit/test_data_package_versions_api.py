"""Tests for data_packages.py 版本管理端点（/{package_id}/versions 系列，全覆盖各分支）."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

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


def _pkg(id_=1, data_types=None):
    p = MagicMock(name="package")
    p.id = id_
    p.data_types = data_types
    return p


def _version(id_=1, version="v1", changes=None, description=None, created_at=None):
    v = MagicMock(name="version_obj")
    v.id = id_
    v.package_id = 1
    v.version = version
    v.changes = changes
    v.description = description
    v.created_at = created_at
    return v


BASE = "/api/v1/data-packages/1/versions"


class TestListVersions:
    def test_not_found(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 404

    def test_list_covers_to_dict_branches(self, client, mocks):
        _, q, _ = mocks
        pkg = _pkg()
        v1 = _version(id_=1, version="v1", changes="bad{json", description=None, created_at=None)
        v2 = _version(
            id_=2,
            version="v2",
            changes=None,
            description="说明",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        q.first.return_value = pkg
        q.all.return_value = [v1, v2]
        resp = client.get(BASE)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        # 非法 JSON → {}；description 空 → ""；created_at 空 → None
        assert data["versions"][0] == {
            "id": 1,
            "version": "v1",
            "description": "",
            "changes": {},
            "created_at": None,
        }
        # changes=None → {}；created_at 有值 → isoformat
        assert data["versions"][1]["description"] == "说明"
        assert data["versions"][1]["changes"] == {}
        assert data["versions"][1]["created_at"] == "2025-01-01T00:00:00+00:00"


class TestCreateVersion:
    def test_package_not_found(self, client):
        resp = client.post(BASE, json={"version": "v1"})
        assert resp.status_code == 404

    def test_empty_version_rejected(self, client, mocks):
        _, q, _ = mocks
        q.first.return_value = _pkg()
        resp = client.post(BASE, json={"version": "   "})
        assert resp.status_code == 422

    def test_duplicate_version_rejected(self, client, mocks):
        _, q, _ = mocks
        q.first.side_effect = [_pkg(), _version()]
        resp = client.post(BASE, json={"version": "v1"})
        assert resp.status_code == 400

    def test_create_success_custom_data_types(self, client, mocks):
        db, q, _ = mocks
        q.first.side_effect = [_pkg(data_types=["villages"]), None]
        resp = client.post(BASE, json={"version": "v1.0", "description": "首版"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["version"] == "v1.0"
        # 变更结构按 data_types 生成（合法 JSON 的解析成功分支）
        assert data["changes"] == {"villages": {"added": [], "modified": [], "deleted": []}}
        assert db.add.called and db.commit.called

    def test_create_success_default_data_types(self, client, mocks):
        _, q, _ = mocks
        q.first.side_effect = [_pkg(data_types=None), None]
        resp = client.post(BASE, json={"version": "v2.0"})
        assert resp.status_code == 200
        changes = resp.json()["data"]["changes"]
        assert sorted(changes.keys()) == ["funds", "projects", "schools", "villages"]


class TestCompareVersions:
    def test_v1_not_found(self, client, mocks):
        _, q, _ = mocks
        q.first.side_effect = [None, _version()]
        resp = client.get(f"{BASE}/compare?version1=v1&version2=v2")
        assert resp.status_code == 404

    def test_v2_not_found(self, client, mocks):
        _, q, _ = mocks
        q.first.side_effect = [_pkg(), _version(), None]
        resp = client.get(f"{BASE}/compare?version1=v1&version2=v2")
        assert resp.status_code == 404

    def test_compare_diffs(self, client, mocks):
        _, q, _ = mocks
        v1 = _version(
            version="v1",
            changes=json.dumps({"villages": {"added": [1, 2], "modified": ["a"]}}),
        )
        v2 = _version(
            version="v2",
            changes=json.dumps({"villages": {"added": [2, 3], "modified": ["b"]}}),
        )
        q.first.side_effect = [_pkg(), v1, v2]
        resp = client.get(f"{BASE}/compare?version1=v1&version2=v2")
        assert resp.status_code == 200
        diff = resp.json()["data"]["comparison"]["differences"]
        assert diff["added_in_v2"] == {"villages": [3]}
        assert diff["removed_in_v2"] == {"villages": [1]}
        assert diff["modified"] == {"villages": ["b"]}

    def test_compare_handles_empty_and_invalid_changes(self, client, mocks):
        _, q, _ = mocks
        v1 = _version(version="v1", changes="not-json")  # 非法 JSON → {}
        v2 = _version(version="v2", changes=None)  # 空 → {}
        q.first.side_effect = [_pkg(), v1, v2]
        resp = client.get(f"{BASE}/compare?version1=v1&version2=v2")
        assert resp.status_code == 200
        diff = resp.json()["data"]["comparison"]["differences"]
        assert diff == {"added_in_v2": {}, "modified": {}, "removed_in_v2": {}}

    def test_compare_keys_from_single_side(self, client, mocks):
        """dtype 仅存在于一侧时 get 默认值与集合差集分支"""
        _, q, _ = mocks
        v1 = _version(version="v1", changes=json.dumps({"villages": {"added": [1]}}))
        v2 = _version(version="v2", changes=json.dumps({"projects": {"added": [3]}}))
        q.first.side_effect = [_pkg(), v1, v2]
        resp = client.get(f"{BASE}/compare?version1=v1&version2=v2")
        assert resp.status_code == 200
        diff = resp.json()["data"]["comparison"]["differences"]
        assert diff["added_in_v2"]["projects"] == [3]
        assert diff["removed_in_v2"]["villages"] == [1]


class TestGetVersion:
    def test_not_found(self, client):
        resp = client.get(f"{BASE}/999")
        assert resp.status_code == 404

    def test_found(self, client, mocks):
        _, q, _ = mocks
        q.first.return_value = _version(
            changes=json.dumps({"villages": {"added": [1], "modified": [], "deleted": []}}),
            description="d",
        )
        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["version"] == "v1"
        assert data["changes"]["villages"]["added"] == [1]


class TestDeleteVersion:
    def test_not_found(self, client):
        resp = client.delete(f"{BASE}/999")
        assert resp.status_code == 404

    def test_delete_success(self, client, mocks):
        db, q, _ = mocks
        v = _version()
        q.first.return_value = v
        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"
        db.delete.assert_called_once_with(v)
