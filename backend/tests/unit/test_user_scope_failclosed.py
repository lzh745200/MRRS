"""安全回归：用户域数据范围 fail-closed + 管理员组织必填（2026-09-14）。

历史缺陷（均已在隔离库真实 HTTP 中复现）：
1. core.data_permission.get_data_scope 对**无组织**的部门级管理员返回 OWN_DEPT，
   而下游普遍写成 scope == OWN_DEPT and current_user.organization_id —— 条件为假即
   **整体跳过过滤**，导致无组织管理员可跨组织枚举全部用户：
   GET /users 看到 4/4 用户（含甲、乙两组织），GET /users/staff-list 同理。
2. 部门级管理员若无组织，其"部门"边界不存在，属配置性漏洞。

修复：
- get_data_scope 收口为单一事实源：无组织 admin → OWN（仅本人），并兼容历史 org_id 回退属性；
- /users 与 /users/staff-list 统一改用 get_data_scope 决策（不再各自内联判权）；
- 产品决策：**禁止创建无组织管理员**（创建/更新两道守卫）。

测试策略：**真实登录**取 token（不依赖 dependency_overrides 的对象身份——
全量套件中若发生模块重载，覆盖键会失配而静默失效）。

工单：.scratch/w7-defect-fixes/014-user-scope-failclosed.md
"""

import pytest

from app.core.data_permission import DataScope, get_data_scope
from app.core.security import get_password_hash

GOOD_PWD = "Probe@2026abc"  # 满足 PasswordPolicy（>=12 位 + 四类字符）


class _Actor:
    """轻量用户替身：仅用于单元级断言（不参与 HTTP 鉴权）。"""

    def __init__(self, role, org_id=None, is_superuser=False, org_id_attr=None):
        self.role = role
        self.is_superuser = is_superuser
        if org_id_attr is None:
            self.organization_id = org_id
        else:
            self.organization_id = None
            self.org_id = org_id_attr


@pytest.fixture(autouse=True)
def _clear_login_rate_limit():
    """登录限流是进程内计数：每例前后清空，避免跨用例累积触发 429。

    沿用 backend/tests/integration/conftest.py 的既有做法。
    """
    from app.core.security import _rate_limit_store

    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


@pytest.fixture
def seeded(client_with_db):
    """两个组织 + 各自成员 + 一个无组织管理员（is_superuser=False）+ 超级管理员。"""
    _client, db = client_with_db
    from app.models.organization import Organization
    from app.models.user import User

    org_a = Organization(name="范围测试甲")
    org_b = Organization(name="范围测试乙")
    db.add_all([org_a, org_b])
    db.commit()
    db.refresh(org_a)
    db.refresh(org_b)

    def _mk(username, role, org_id, is_superuser=False):
        u = User(
            username=username,
            hashed_password=get_password_hash(GOOD_PWD),
            role=role,
            is_superuser=is_superuser,
            organization_id=org_id,
            is_active=True,
            must_change_password=False,
        )
        db.add(u)
        return u

    rows = [
        _mk("scope_orgless_admin", "admin", None),
        _mk("scope_org_a_admin", "admin", org_a.id),
        _mk("scope_user_in_a", "user", org_a.id),
        _mk("scope_user_in_b", "user", org_b.id),
        _mk("scope_root", "super_admin", None, is_superuser=True),
    ]
    db.commit()
    for r in rows:
        db.refresh(r)
    return {"db": db, "org_a": org_a, "org_b": org_b,
            "users": {r.username: r for r in rows}}


def _login(client, username, password=GOOD_PWD):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text[:200]
    return (r.json().get("data") or {}).get("access_token")


def _auth(client, username, password=GOOD_PWD):
    return {"Authorization": "Bearer " + str(_login(client, username, password))}


class TestGetDataScopeFailClosed:
    """单一事实源：角色 → 数据域映射（含无组织降级与历史 org_id 回退）。"""

    def test_orgless_admin_downgraded_to_own(self):
        assert get_data_scope(_Actor("admin", org_id=None)) == DataScope.OWN

    def test_admin_with_org_is_own_dept(self):
        assert get_data_scope(_Actor("admin", org_id=7)) == DataScope.OWN_DEPT

    def test_admin_with_legacy_org_id_attr_is_own_dept(self):
        assert get_data_scope(_Actor("admin", org_id_attr=9)) == DataScope.OWN_DEPT

    def test_orgless_superuser_still_all(self):
        assert get_data_scope(_Actor("admin", org_id=None, is_superuser=True)) == DataScope.ALL


class TestUsersListScope:
    """GET /users：无组织管理员只应看到自己；有组织管理员只应看到本组织。"""

    def test_orgless_admin_sees_only_self(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.get("/api/v1/users", params={"page": 1, "page_size": 50},
                          headers=_auth(client, "scope_orgless_admin"))
        assert resp.status_code == 200, resp.text
        names = [i["username"] for i in resp.json()["data"]["items"]]
        assert names == ["scope_orgless_admin"], names

    def test_org_admin_sees_only_own_org(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.get("/api/v1/users", params={"page": 1, "page_size": 50},
                          headers=_auth(client, "scope_org_a_admin"))
        assert resp.status_code == 200, resp.text
        names = {i["username"] for i in resp.json()["data"]["items"]}
        assert "scope_user_in_b" not in names, names
        assert "scope_orgless_admin" not in names, names
        assert "scope_user_in_a" in names, names

    def test_superuser_sees_all(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.get("/api/v1/users", params={"page": 1, "page_size": 50},
                          headers=_auth(client, "scope_root"))
        assert resp.status_code == 200, resp.text
        names = {i["username"] for i in resp.json()["data"]["items"]}
        assert {"scope_user_in_a", "scope_user_in_b"} <= names, names


class TestStaffListScope:
    """GET /users/staff-list：同一收口 + 关键词检索（原 /user-management 列表能力迁移点）。"""

    def test_orgless_admin_sees_only_self(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.get("/api/v1/users/staff-list", params={"page": 1, "page_size": 50},
                          headers=_auth(client, "scope_orgless_admin"))
        assert resp.status_code == 200, resp.text
        names = [i["username"] for i in resp.json()["data"]["items"]]
        assert names == ["scope_orgless_admin"], names

    def test_keyword_filters(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.get("/api/v1/users/staff-list",
                          params={"page": 1, "page_size": 50, "keyword": "scope_user_in_b"},
                          headers=_auth(client, "scope_root"))
        assert resp.status_code == 200, resp.text
        names = [i["username"] for i in resp.json()["data"]["items"]]
        assert names == ["scope_user_in_b"], names

    def test_plain_user_sees_only_self(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.get("/api/v1/users/staff-list", params={"page": 1, "page_size": 50},
                          headers=_auth(client, "scope_user_in_a"))
        assert resp.status_code == 200, resp.text
        names = [i["username"] for i in resp.json()["data"]["items"]]
        assert names == ["scope_user_in_a"], names


class TestAdminRequiresOrganization:
    """产品决策：禁止创建/改成无组织管理员（部门级管理员必须有数据边界）。"""

    def test_create_orgless_admin_rejected(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.post("/api/v1/users",
                           json={"username": "new_orgless_admin", "password": GOOD_PWD, "role": "admin"},
                           headers=_auth(client, "scope_root"))
        assert resp.status_code == 400, resp.text
        assert "组织" in resp.json()["detail"]

    def test_create_orgless_super_admin_rejected(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.post("/api/v1/users",
                           json={"username": "new_orgless_su", "password": GOOD_PWD, "role": "super_admin"},
                           headers=_auth(client, "scope_root"))
        assert resp.status_code == 400, resp.text
        assert "组织" in resp.json()["detail"]

    def test_create_admin_with_org_ok(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.post("/api/v1/users",
                           json={"username": "new_admin_with_org", "password": GOOD_PWD,
                                 "role": "admin", "organization_id": seeded["org_a"].id},
                           headers=_auth(client, "scope_root"))
        assert resp.status_code in (200, 201), resp.text

    def test_create_orgless_plain_user_still_allowed(self, client_with_db, seeded):
        client, _db = client_with_db
        resp = client.post("/api/v1/users",
                           json={"username": "new_orgless_user", "password": GOOD_PWD, "role": "user"},
                           headers=_auth(client, "scope_root"))
        assert resp.status_code in (200, 201), resp.text

    def test_update_admin_to_orgless_rejected(self, client_with_db, seeded):
        client, _db = client_with_db
        target = seeded["users"]["scope_org_a_admin"]
        resp = client.put("/api/v1/users/" + str(target.id), json={"organization_id": None},
                          headers=_auth(client, "scope_root"))
        assert resp.status_code == 400, resp.text
        assert "组织" in resp.json()["detail"]
