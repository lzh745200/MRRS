"""R27（2026-10-14）：组织管理写端点跨组织越权回归测试。

缺陷：app/api/v1/organization.py 的 create / update / delete / move /
batch-update-sort 五个写端点此前只有内联角色判定（admin/super_admin），
不校验目标组织是否在调用者组织子树内 —— role=admin 的部门级管理员
（organization_id=2）可以对其它分支的组织执行改名/软删除/移动/排序
（跨组织越权，例如删掉别的单位的组织节点）。

修复：五个写端点统一接入 core.data_permission.assert_org_reachable（与
org_module_policy / control_package 写端点同口径）。本文件按修复方案锁定：

- 部门级管理员（role=admin, is_superuser=False, organization_id=2）：
  对自身子树（2、3）操作 → 正常成功；对独立分支 B（8、9）操作 → 403
  且目标组织数据不变（尤其 delete 不得软删成功）；
- 超管行为零变化：跨分支操作仍可行（不回归）；
- move 的级联重算 path（OrganizationService.recompute_subtree_paths）
  能力不受守卫影响。

构造方式：真实 SQLite（内存 + StaticPool）+ TestClient + 依赖覆盖，
组织树 1(总公司)→2(部门A)→3(A子组)，另有独立分支 1→8(部门B)→9(B子组)。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

DEPT_PASSWORD = "dept-pass-123"
SUPER_PASSWORD = "super-pass-123"

# 守卫 403 文案前缀（assert_org_reachable 默认 detail："无权对该组织{action}"）
DENY_PREFIX = "无权对该组织"


# ---------------------------------------------------------------------------
#  数据准备
# ---------------------------------------------------------------------------

def _seed_tree(db):
    """组织树：1(总公司)→2(部门A)→3(A子组)；独立分支 1→8(部门B)→9(B子组)。"""
    from app.models.organization import Organization

    db.add_all(
        [
            # 2026-10-27：组织编码改为真实行政区划代码（权威表校验 + 父子同区划），
            # 占位码（原 R27-ROOT/R27-A/...）不再合法，见 tests/unit/test_admin_divisions_r47.py。
            Organization(id=1, name="总公司", code="520000", parent_id=None,
                         path="/1/", level=1, org_type="department", sort_order=1),
            Organization(id=2, name="部门A", code="520100", parent_id=1,
                         path="/1/2/", level=2, org_type="department", sort_order=2),
            Organization(id=3, name="A子组", code="520103", parent_id=2,
                         path="/1/2/3/", level=3, org_type="department", sort_order=3),
            Organization(id=8, name="部门B", code="520200", parent_id=1,
                         path="/1/8/", level=2, org_type="department", sort_order=8),
            Organization(id=9, name="B子组", code="520201", parent_id=8,
                         path="/1/8/9/", level=3, org_type="department", sort_order=9),
        ]
    )


def _seed_users(db):
    """部门级管理员挂在部门A（id=2），超管挂在总公司（id=1）。"""
    from app.core.security import hash_password
    from app.models.user import User

    db.add_all(
        [
            User(id=21, username="r27_dept_admin",
                 hashed_password=hash_password(DEPT_PASSWORD),
                 role="admin", is_superuser=False, is_active=True,
                 organization_id=2),
            User(id=22, username="r27_super",
                 hashed_password=hash_password(SUPER_PASSWORD),
                 role="super_admin", is_superuser=True, is_active=True,
                 organization_id=1),
        ]
    )


@pytest.fixture
def org_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    _seed_tree(session)
    _seed_users(session)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _make_client(org_db, user_id):
    """TestClient + 依赖覆盖（get_db / get_current_user 指向真实内存库与真实用户行）。"""
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app
    from app.models.user import User

    user = org_db.query(User).filter(User.id == user_id).first()
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: org_db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app, raise_server_exceptions=False)
    return client, original


@pytest.fixture
def dept_client(org_db):
    """role=admin、org=2 的部门级管理员（非超管）。"""
    client, original = _make_client(org_db, 21)
    yield client
    from app.main import app

    app.dependency_overrides = original


@pytest.fixture
def super_client(org_db):
    """is_superuser=True 的超级管理员。"""
    client, original = _make_client(org_db, 22)
    yield client
    from app.main import app

    app.dependency_overrides = original


def _org(db, org_id):
    """取最新落库状态的组织行（先 expire_all 绕开同会话身份映射缓存）。"""
    from app.models.organization import Organization

    db.expire_all()
    return db.query(Organization).filter(Organization.id == org_id).first()


# ---------------------------------------------------------------------------
#  部门级管理员 —— 跨分支写操作必须 403 且目标数据不变
# ---------------------------------------------------------------------------

class TestR27DeptAdminCrossBranchDenied:
    def test_update_cross_branch_403_target_untouched(self, dept_client, org_db):
        """对分支 B 的组织改名 → 403，组织 8 数据不变。"""
        resp = dept_client.put("/api/v1/organizations/8", json={"name": "越权改名"})
        assert resp.status_code == 403
        assert DENY_PREFIX + "修改组织" in resp.json()["detail"]
        assert _org(org_db, 8).name == "部门B"

    def test_delete_cross_branch_403_not_soft_deleted(self, dept_client, org_db):
        """删除分支 B 的组织 → 403，组织 9 不得被软删。"""
        resp = dept_client.delete(
            "/api/v1/organizations/9", headers={"X-Confirm-Password": DEPT_PASSWORD}
        )
        assert resp.status_code == 403
        assert DENY_PREFIX + "删除组织" in resp.json()["detail"]
        assert _org(org_db, 9).is_active is True

    def test_move_own_org_under_other_branch_403(self, dept_client, org_db):
        """把自己的子组织 3 挂到分支 B 名下 → 403，组织 3 归属不变。"""
        resp = dept_client.post("/api/v1/organizations/3/move", json={"new_parent_id": 8})
        assert resp.status_code == 403
        assert DENY_PREFIX + "移动组织" in resp.json()["detail"]
        moved = _org(org_db, 3)
        assert moved.parent_id == 2
        assert moved.path == "/1/2/3/"

    def test_move_other_branch_org_403(self, dept_client, org_db):
        """直接移动分支 B 的组织 8 → 403，组织 8 归属不变。"""
        resp = dept_client.post("/api/v1/organizations/8/move", json={"new_parent_id": 2})
        assert resp.status_code == 403
        moved = _org(org_db, 8)
        assert moved.parent_id == 1
        assert moved.path == "/1/8/"

    def test_batch_sort_cross_branch_403_no_change(self, dept_client, org_db):
        """批量排序混入分支 B 的组织 9 → 403，全部目标（含自己的 2）不变。"""
        resp = dept_client.post(
            "/api/v1/organizations/batch-update-sort",
            json={"items": [{"id": 2, "sort_order": 77}, {"id": 9, "sort_order": 99}]},
        )
        assert resp.status_code == 403
        assert DENY_PREFIX + "排序组织" in resp.json()["detail"]
        assert _org(org_db, 2).sort_order == 2
        assert _org(org_db, 9).sort_order == 9

    def test_create_under_other_branch_403_no_row(self, dept_client, org_db):
        """在分支 B 名下创建子组织 → 403，不落任何新行。"""
        from app.models.organization import Organization

        before = org_db.query(Organization).count()
        resp = dept_client.post(
            "/api/v1/organizations", json={"name": "越权新组织", "parent_id": 8, "code": "520100"}
        )
        assert resp.status_code == 403
        assert DENY_PREFIX + "创建组织" in resp.json()["detail"]
        org_db.expire_all()
        assert org_db.query(Organization).count() == before


# ---------------------------------------------------------------------------
#  部门级管理员 —— 自身子树内的管理路径必须照常可用（防误伤）
# ---------------------------------------------------------------------------

class TestR27DeptAdminOwnSubtreeAllowed:
    def test_update_own_subtree_ok(self, dept_client, org_db):
        resp = dept_client.put("/api/v1/organizations/3", json={"name": "A子组改名"})
        assert resp.status_code == 200
        assert _org(org_db, 3).name == "A子组改名"

    def test_update_own_org_ok(self, dept_client, org_db):
        """自身组织（子树根 2）也在可及范围内。"""
        resp = dept_client.put("/api/v1/organizations/2", json={"name": "部门A新名"})
        assert resp.status_code == 200
        assert _org(org_db, 2).name == "部门A新名"

    def test_delete_own_leaf_ok(self, dept_client, org_db):
        resp = dept_client.delete(
            "/api/v1/organizations/3", headers={"X-Confirm-Password": DEPT_PASSWORD}
        )
        assert resp.status_code == 200
        assert _org(org_db, 3).is_active is False

    def test_move_within_subtree_recomputes_path(self, dept_client, org_db):
        """子树内移动 → 200，且 v1.12.16 的级联重算 path 仍然生效
        （预置脏 path "/stale/3/"，移动后必须收敛为 /1/2/3/）。"""
        org3 = _org(org_db, 3)
        org3.path = "/stale/3/"
        org_db.commit()

        resp = dept_client.post("/api/v1/organizations/3/move", json={"new_parent_id": 2})
        assert resp.status_code == 200
        moved = _org(org_db, 3)
        assert moved.parent_id == 2
        assert moved.path == "/1/2/3/"

    def test_batch_sort_own_subtree_ok(self, dept_client, org_db):
        resp = dept_client.post(
            "/api/v1/organizations/batch-update-sort",
            json={"items": [{"id": 2, "sort_order": 5}, {"id": 3, "sort_order": 6}]},
        )
        assert resp.status_code == 200
        assert _org(org_db, 2).sort_order == 5
        assert _org(org_db, 3).sort_order == 6

    def test_create_under_own_subtree_ok(self, dept_client, org_db):
        resp = dept_client.post(
            "/api/v1/organizations", json={"name": "A新小组", "parent_id": 2, "code": "520102"}
        )
        assert resp.status_code == 200
        from app.models.organization import Organization

        org_db.expire_all()
        created = org_db.query(Organization).filter(Organization.name == "A新小组").first()
        assert created is not None
        assert created.parent_id == 2
        assert created.path == f"/1/2/{created.id}/"


# ---------------------------------------------------------------------------
#  超管 —— 跨分支操作零回归
# ---------------------------------------------------------------------------

class TestR27SuperuserUnchanged:
    def test_update_cross_branch_ok(self, super_client, org_db):
        resp = super_client.put("/api/v1/organizations/8", json={"name": "超管改名B"})
        assert resp.status_code == 200
        assert _org(org_db, 8).name == "超管改名B"

    def test_delete_cross_branch_ok(self, super_client, org_db):
        resp = super_client.delete(
            "/api/v1/organizations/9", headers={"X-Confirm-Password": SUPER_PASSWORD}
        )
        assert resp.status_code == 200
        assert _org(org_db, 9).is_active is False

    def test_move_across_branches_ok_with_path_recompute(self, super_client, org_db):
        """超管把 3 挂到 8 名下 → 200，path 级联重算为 /1/8/3/。"""
        resp = super_client.post("/api/v1/organizations/3/move", json={"new_parent_id": 8})
        assert resp.status_code == 200
        moved = _org(org_db, 3)
        assert moved.parent_id == 8
        assert moved.path == "/1/8/3/"

    def test_create_under_other_branch_ok(self, super_client, org_db):
        resp = super_client.post(
            "/api/v1/organizations", json={"name": "B新小组", "parent_id": 8, "code": "520203"}
        )
        assert resp.status_code == 200
        from app.models.organization import Organization

        org_db.expire_all()
        created = org_db.query(Organization).filter(Organization.name == "B新小组").first()
        assert created is not None
        assert created.path == f"/1/8/{created.id}/"

    def test_batch_sort_cross_branch_ok(self, super_client, org_db):
        resp = super_client.post(
            "/api/v1/organizations/batch-update-sort",
            json={"items": [{"id": 8, "sort_order": 1}, {"id": 9, "sort_order": 2}]},
        )
        assert resp.status_code == 200
        assert _org(org_db, 8).sort_order == 1
        assert _org(org_db, 9).sort_order == 2
