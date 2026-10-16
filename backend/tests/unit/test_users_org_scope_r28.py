"""H4 regression: cross-org write guards on user management endpoints (military audit red line).

Background (docs/系统全面排查报告-2026-10-14.md H4): update / delete / permissions /
admin-reset-password / pending-list only had require_admin (role level) plus privilege
escalation guards, with no org-reachability check, so a department-level admin could
manage users of other organizations and /users/pending/list enumerated all pending
accounts. The fix routes through core.data_permission.assert_org_reachable, fails
closed for org-less targets, and scopes the pending list by data scope.

Why a real SQLite DB: the correctness of these guards shows up as "which org ids the
query really filters on", which MagicMock cannot prove (it can only prove that filter
was called). This is exactly how historical false-green tests were born."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _user(db, username, role="user", org=None, is_superuser=False):
    from app.models.user import User

    user = User(
        username=username,
        hashed_password="x",
        role=role,
        is_active=True,
        is_superuser=is_superuser,
        organization_id=org,
        email=None,
    )
    db.add(user)
    db.flush()
    return user


def _seed_orgs(db):
    from app.models.organization import Organization

    root = Organization(name="ROOT", code="ROOT", is_active=True)
    db.add(root)
    db.flush()
    child = Organization(name="DEPT_A", code="A", parent_id=root.id, is_active=True)
    db.add(child)
    db.flush()
    sibling = Organization(name="DEPT_B", code="B", parent_id=root.id, is_active=True)
    db.add(sibling)
    db.flush()
    db.commit()
    return root, child, sibling


class TestCrossOrgWriteGuards:
    @pytest.mark.asyncio
    async def test_update_user_in_other_org_rejected(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await us.update_user(other.id, us.UserUpdateBody(role="viewer"), admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_user_in_own_org_allowed(self, db):
        from app.api.v1.auth import users as us

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        db.commit()

        result = await us.update_user(mine.id, us.UserUpdateBody(role="viewer"), admin, db)
        assert result["code"] == 200
        db.refresh(mine)
        assert mine.role == "viewer"

    @pytest.mark.asyncio
    async def test_delete_user_in_other_org_rejected(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await us.delete_user(other.id, admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_reset_password_in_other_org_rejected(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        body = us.AdminResetPasswordBody(new_password="Str0ng!Passw0rd")
        with pytest.raises(HTTPException) as ei:
            await us.admin_reset_password(other.id, body, admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_permissions_in_other_org_rejected(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        body = us.UserPermissionsUpdate(role="viewer")
        with pytest.raises(HTTPException) as ei:
            await us.update_user_permissions(other.id, body, admin, db)
        assert ei.value.status_code == 403


class TestFailClosedForOrglessTarget:
    @pytest.mark.asyncio
    async def test_orgless_target_rejected_for_department_admin(self, db):
        from app.api.v1.auth import users as us

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        orphan = _user(db, "orphan", role="user", org=None)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await us.update_user(orphan.id, us.UserUpdateBody(role="viewer"), admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_orgless_target_allowed_for_super_admin(self, db):
        from app.api.v1.auth import users as us

        _root, _child, _sibling = _seed_orgs(db)
        admin = _user(db, "super_admin_user", role="admin", org=None, is_superuser=True)
        orphan = _user(db, "orphan", role="user", org=None)
        db.commit()

        result = await us.update_user(orphan.id, us.UserUpdateBody(role="viewer"), admin, db)
        assert result["code"] == 200


class TestSuperAdminBypass:
    @pytest.mark.asyncio
    async def test_super_admin_can_update_any_org(self, db):
        from app.api.v1.auth import users as us

        _root, _child, sibling = _seed_orgs(db)
        admin = _user(db, "super_admin_user", role="super_admin", org=None, is_superuser=True)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        result = await us.update_user(other.id, us.UserUpdateBody(role="viewer"), admin, db)
        assert result["code"] == 200


class TestPendingListScoping:
    @pytest.mark.asyncio
    async def test_department_admin_sees_only_own_subtree(self, db):
        from app.api.v1.auth import users as us

        root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine_pending", role="user", org=child.id)
        mine.is_active = False
        other = _user(db, "other_pending", role="user", org=sibling.id)
        other.is_active = False
        root_pending = _user(db, "root_pending", role="user", org=root.id)
        root_pending.is_active = False
        db.commit()

        result = await us.get_pending_users(admin, db)
        usernames = {item["username"] for item in result["data"]["items"]}
        assert usernames == {"mine_pending"}
        assert "other_pending" not in usernames
        assert "root_pending" not in usernames

    @pytest.mark.asyncio
    async def test_super_admin_sees_all_pending(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "super_admin_user", role="super_admin", org=None, is_superuser=True)
        a = _user(db, "pending_a", role="user", org=child.id)
        a.is_active = False
        b = _user(db, "pending_b", role="user", org=sibling.id)
        b.is_active = False
        db.commit()

        result = await us.get_pending_users(admin, db)
        usernames = {item["username"] for item in result["data"]["items"]}
        assert usernames == {"pending_a", "pending_b"}


class TestStaffListOrgSubtree:
    """R28：staff-list 与 /users、/pending 共用 _apply_user_data_scope（含子树）。

    历史缺陷：staff-list 内联 `organization_id == 本组织`（不含子树），而 /users
    列表含子树 —— 同一部门级管理员在任务分配（staff-list）里看不到下级组织成员，
    却在用户管理里能看到，两个页面口径矛盾。"""

    @pytest.mark.asyncio
    async def test_department_admin_sees_descendant_staff(self, db):
        from app.api.v1.auth import users as us
        from app.models.organization import Organization

        root, child, sibling = _seed_orgs(db)
        grand = Organization(name="TEAM", code="G", parent_id=child.id, is_active=True)
        db.add(grand)
        db.flush()

        admin = _user(db, "child_admin", role="admin", org=child.id)
        _user(db, "u_grand", role="user", org=grand.id)     # 子树的孙级
        _user(db, "u_sibling", role="user", org=sibling.id)  # 兄弟组织（跨域红线）
        _user(db, "u_root", role="user", org=root.id)        # 上级组织（子树向下）
        db.commit()

        result = await us.get_staff_list(
            page=1, page_size=50, keyword=None, current_user=admin, db=db
        )
        names = {item.username for item in result["data"]["items"]}
        assert "u_grand" in names           # 子树内（下级的下级）可见
        assert "u_sibling" not in names     # 跨组织红线：兄弟组织不可见
        assert "u_root" not in names        # 子树只向下
        assert "child_admin" in names

    @pytest.mark.asyncio
    async def test_subtree_is_downward_only(self, db):
        from app.api.v1.auth import users as us

        root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "child_admin", role="admin", org=child.id)
        _user(db, "u_root", role="user", org=root.id)
        db.commit()

        result = await us.get_staff_list(
            page=1, page_size=50, keyword=None, current_user=admin, db=db
        )
        names = {item.username for item in result["data"]["items"]}
        assert "child_admin" in names
        assert "u_root" not in names  # 上级组织成员不在下级的子树内


class TestPendingListSubtree:
    """R28：待审列表必须解析子树（旧实现漏传 db → 退化为仅本组织）。"""

    @pytest.mark.asyncio
    async def test_department_admin_sees_grandchild_pending(self, db):
        from app.api.v1.auth import users as us
        from app.models.organization import Organization

        root, child, sibling = _seed_orgs(db)
        grand = Organization(name="TEAM", code="G", parent_id=child.id, is_active=True)
        db.add(grand)
        db.flush()

        admin = _user(db, "child_admin", role="admin", org=child.id)
        pending_grand = _user(db, "pending_grand", role="user", org=grand.id)
        pending_grand.is_active = False
        pending_sibling = _user(db, "pending_sibling", role="user", org=sibling.id)
        pending_sibling.is_active = False
        db.commit()

        result = await us.get_pending_users(admin, db)
        usernames = {item["username"] for item in result["data"]["items"]}
        assert "pending_grand" in usernames   # 孙级组织（子树）必须可见
        assert "pending_sibling" not in usernames


class TestDanglingOrgFailClosed:
    """R28：管理员指向不存在（悬空）的组织 id → 子树解析为空，退化为
    in_([org_id])，只可能命中该 id 名下的记录（即管理员自己），绝不放大可见范围。"""

    @pytest.mark.asyncio
    async def test_dangling_org_sees_only_self(self, db):
        from app.api.v1.auth import users as us

        _root, _child, _sibling = _seed_orgs(db)
        normal = _user(db, "normal_user", role="user", org=_child.id)
        ghost_admin = _user(db, "ghost_admin", role="admin", org=99999)
        db.commit()

        staff = await us.get_staff_list(
            page=1, page_size=50, keyword=None, current_user=ghost_admin, db=db
        )
        # 子树为空 → in_([99999]) 只命中 ghost 自己；其它组织成员不可见
        assert [i.username for i in staff["data"]["items"]] == ["ghost_admin"]

        listing = await us.list_users(page=1, page_size=50, current_user=ghost_admin, db=db)
        usernames = {i["username"] for i in listing["data"]["items"]}
        assert usernames == {"ghost_admin"}
        assert normal.username not in usernames


class TestCreateUserOrgGuard:
    """H4 补口（2026-10-16 收尾）：创建用户时的组织可达性守卫。

    R27-H4 原始清单只覆盖 update / delete / permissions / admin-reset-password /
    pending-list 五个端点；收尾复核发现 create 无任何组织校验 —— 部门级 admin
    可向任意组织投放账号（含 admin 角色），构成对目标组织的持久渗透。
    与其余写端点同口径：非超管只能创建在自身组织子树内，否则 403。
    """

    @pytest.mark.asyncio
    async def test_create_in_other_org_rejected(self, db):
        from app.api.v1.auth import users as us
        from app.models.user import User

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        body = us.UserCreateBody(
            username="intruder",
            password="Str0ng!Passw0rd",
            organization_id=sibling.id,
            role="user",
        )
        with pytest.raises(HTTPException) as ei:
            await us.create_user(body, admin, db)
        assert ei.value.status_code == 403
        # 越权请求不得产生任何落库记录
        assert db.query(User).filter(User.username == "intruder").first() is None

    @pytest.mark.asyncio
    async def test_create_in_own_subtree_allowed(self, db):
        from app.api.v1.auth import users as us
        from app.models.organization import Organization

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        grand = Organization(name="TEAM", code="T", parent_id=child.id, is_active=True)
        db.add(grand)
        db.commit()

        body = us.UserCreateBody(
            username="newstaff",
            password="Str0ng!Passw0rd",
            organization_id=grand.id,
            role="user",
        )
        result = await us.create_user(body, admin, db)
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_orgless_admin_create_fails_closed(self, db):
        from app.api.v1.auth import users as us

        _root, _child, sibling = _seed_orgs(db)
        orgless_admin = _user(db, "orgless_admin", role="admin", org=None)
        db.commit()

        body = us.UserCreateBody(
            username="newstaff2",
            password="Str0ng!Passw0rd",
            organization_id=sibling.id,
            role="user",
        )
        with pytest.raises(HTTPException) as ei:
            await us.create_user(body, orgless_admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_super_admin_can_create_any_org(self, db):
        from app.api.v1.auth import users as us

        _root, _child, sibling = _seed_orgs(db)
        root_admin = _user(db, "super_admin_user", role="super_admin", org=None, is_superuser=True)
        db.commit()

        body = us.UserCreateBody(
            username="sky",
            password="Str0ng!Passw0rd",
            organization_id=sibling.id,
            role="user",
        )
        result = await us.create_user(body, root_admin, db)
        assert result["code"] == 200


class TestGetUserDetailOrgGuard:
    """H4 补口：用户详情读取的跨组织守卫（先 require_admin，再组织可达性）。"""

    @pytest.mark.asyncio
    async def test_detail_of_other_org_rejected(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await us.get_user(other.id, admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_detail_of_own_subtree_allowed(self, db):
        from app.api.v1.auth import users as us

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        db.commit()

        result = await us.get_user(mine.id, admin, db)
        assert result["data"]["username"] == "mine"

    @pytest.mark.asyncio
    async def test_self_detail_allowed_for_regular_user(self, db):
        from app.api.v1.auth import users as us

        _root, _child, _sibling = _seed_orgs(db)
        me = _user(db, "plain_user", role="user", org=None)
        db.commit()

        result = await us.get_user(me.id, me, db)
        assert result["data"]["username"] == "plain_user"

    @pytest.mark.asyncio
    async def test_super_admin_can_read_any(self, db):
        from app.api.v1.auth import users as us

        _root, _child, sibling = _seed_orgs(db)
        root_admin = _user(db, "super_admin_user", role="super_admin", org=None, is_superuser=True)
        other = _user(db, "other_user", role="user", org=sibling.id)
        db.commit()

        result = await us.get_user(other.id, root_admin, db)
        assert result["data"]["username"] == "other_user"


class TestUpdateUserMoveOrgGuard:
    """H4 补口：改组织（移动用户）时的目标组织可达性守卫。"""

    @pytest.mark.asyncio
    async def test_move_to_other_org_rejected(self, db):
        from app.api.v1.auth import users as us

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await us.update_user(mine.id, us.UserUpdateBody(organization_id=sibling.id), admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_move_within_own_subtree_allowed(self, db):
        from app.api.v1.auth import users as us
        from app.models.organization import Organization

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        grand = Organization(name="TEAM", code="T", parent_id=child.id, is_active=True)
        db.add(grand)
        db.commit()

        result = await us.update_user(mine.id, us.UserUpdateBody(organization_id=grand.id), admin, db)
        assert result["code"] == 200
        db.refresh(mine)
        assert mine.organization_id == grand.id
