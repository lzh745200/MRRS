"""组织模块跨组织越权守卫回归（2026-10-31 补口）。

缺陷背景：`children` / `ancestors` / `detail` 三个读端点原先对**所有登录用户**
无条件返回；`members` 增删与 `activate` / `deactivate` 只有角色级判定，没有
组织可达性校验。部门级管理员（role=admin，只挂某个部门）因此可以：

* 读取他组织的子单位/祖先链/联系人地址（组织架构外泄，可据此定位目标）；
* 向他组织投放成员、把他组织用户"拉进"自己组织、把他组织成员移出组织；
* 停用/激活他组织，直接改变对方业务可用性。

修复口径与 `GET /organizations/{id}`、`GET .../members` 完全一致：
统一走 `apply_scope_filter`（读）与 `_assert_org_write_scope`（写），
越权 403；成员关系不符 400（避免把「任意用户」的 organization_id 清空）。

为什么用真实 SQLite：这些守卫的正确性体现为"到底按哪些 org id 过滤"，
MagicMock 只能证明 filter 被调用过，正是历史假绿测试的来源。
"""
from unittest.mock import AsyncMock, patch

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


class TestOrganizationReadScope:
    """children / ancestors / detail 的组织读范围守卫。"""

    @pytest.mark.asyncio
    async def test_children_of_other_org_rejected(self, db):
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.get_children(sibling.id, admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_children_of_own_org_allowed(self, db):
        from app.api.v1 import organization as org_api
        from app.models.organization import Organization

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        grand = Organization(name="TEAM", code="T", parent_id=child.id, is_active=True)
        db.add(grand)
        db.commit()

        rows = await org_api.get_children(child.id, admin, db)
        assert [r.name for r in rows] == ["TEAM"]

    @pytest.mark.asyncio
    async def test_ancestors_of_other_org_rejected(self, db):
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.get_ancestors(sibling.id, admin, db)
        assert ei.value.status_code == 403

    @pytest.mark.asyncio
    async def test_ancestors_of_own_org_allowed(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        rows = await org_api.get_ancestors(child.id, admin, db)
        assert [r.name for r in rows] == ["ROOT"]

    @pytest.mark.asyncio
    async def test_detail_of_other_org_rejected(self, db):
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.get_organization_detail(sibling.id, admin, db)
        assert ei.value.status_code == 403
        assert "无权查看该组织详情" in ei.value.detail

    @pytest.mark.asyncio
    async def test_detail_of_own_org_allowed(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        result = await org_api.get_organization_detail(child.id, admin, db)
        assert result["code"] == 200
        assert result["data"]["name"] == "DEPT_A"

    @pytest.mark.asyncio
    async def test_super_admin_can_read_any_org(self, db):
        from app.api.v1 import organization as org_api

        _root, _child, sibling = _seed_orgs(db)
        root_admin = _user(db, "root", role="super_admin", org=None, is_superuser=True)
        db.commit()

        assert await org_api.get_children(sibling.id, root_admin, db) == []
        detail = await org_api.get_organization_detail(sibling.id, root_admin, db)
        assert detail["data"]["name"] == "DEPT_B"


class TestOrganizationMemberScope:
    """成员增删的组织可达性 + 成员关系校验。"""

    @pytest.mark.asyncio
    async def test_add_member_to_other_org_rejected(self, db):
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.add_organization_members(sibling.id, {"user_ids": [mine.id]}, admin, db)
        assert ei.value.status_code == 403
        db.refresh(mine)
        assert mine.organization_id == child.id

    @pytest.mark.asyncio
    async def test_add_member_within_own_org_allowed(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        db.commit()

        result = await org_api.add_organization_members(child.id, {"user_ids": [mine.id]}, admin, db)
        assert result["data"]["added"] == 1

    @pytest.mark.asyncio
    async def test_steal_user_from_other_org_rejected(self, db):
        """把「他组织用户」拉进自己组织同样属跨组织写入。"""
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other", role="user", org=sibling.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.add_organization_members(child.id, {"user_ids": [other.id]}, admin, db)
        assert ei.value.status_code == 403
        db.refresh(other)
        assert other.organization_id == sibling.id

    @pytest.mark.asyncio
    async def test_add_orgless_user_fail_closed_for_dept_admin(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        orphan = _user(db, "orphan", role="user", org=None)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.add_organization_members(child.id, {"user_ids": [orphan.id]}, admin, db)
        assert ei.value.status_code == 403
        db.refresh(orphan)
        assert orphan.organization_id is None

    @pytest.mark.asyncio
    async def test_remove_member_of_other_org_rejected(self, db):
        """成员关系校验：用自身组织 id + 他组织用户 id 不能清空对方组织归属。"""
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        other = _user(db, "other", role="user", org=sibling.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.remove_organization_member(child.id, other.id, admin, db)
        assert ei.value.status_code == 400
        assert "不属于此组织" in ei.value.detail
        db.refresh(other)
        assert other.organization_id == sibling.id

    @pytest.mark.asyncio
    async def test_remove_own_member_allowed(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        mine = _user(db, "mine", role="user", org=child.id)
        db.commit()

        result = await org_api.remove_organization_member(child.id, mine.id, admin, db)
        assert result["data"]["removed"] == mine.id
        db.refresh(mine)
        assert mine.organization_id is None


class TestOrganizationActivationScope:
    """激活/停用组织属写操作，必须落在调用者子树内。"""

    @pytest.mark.asyncio
    async def test_deactivate_other_org_rejected(self, db):
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with path_cache():
            with pytest.raises(HTTPException) as ei:
                await org_api.deactivate_organization(sibling.id, admin, db)
        assert ei.value.status_code == 403
        db.refresh(sibling)
        assert sibling.is_active is True

    @pytest.mark.asyncio
    async def test_activate_other_org_rejected(self, db):
        from app.api.v1 import organization as org_api

        _root, child, sibling = _seed_orgs(db)
        sibling.is_active = False
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with path_cache():
            with pytest.raises(HTTPException) as ei:
                await org_api.activate_organization(sibling.id, admin, db)
        assert ei.value.status_code == 403
        db.refresh(sibling)
        assert sibling.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_own_org_allowed(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with path_cache():
            result = await org_api.deactivate_organization(child.id, admin, db)
        assert result["code"] == 200
        db.refresh(child)
        assert child.is_active is False


class TestRootOrgCreateScope:
    """根组织创建只允许超管（部门级管理员无法在自身子树外新建组织树）。"""

    @pytest.mark.asyncio
    async def test_dept_admin_cannot_create_root_org(self, db):
        from app.api.v1 import organization as org_api

        _root, child, _sibling = _seed_orgs(db)
        admin = _user(db, "dept_admin", role="admin", org=child.id)
        db.commit()

        with pytest.raises(HTTPException) as ei:
            await org_api.create_organization(
                org_api.OrganizationCreate(name="GHOST_ROOT", code="520000"), admin, db
            )
        assert ei.value.status_code == 403
        assert "根组织" in ei.value.detail
        assert db.query(org_api.Organization).count() == 3  # 越权请求不得落库

    @pytest.mark.asyncio
    async def test_super_admin_can_create_root_org(self, db):
        from app.api.v1 import organization as org_api

        _root, _child, _sibling = _seed_orgs(db)
        root_admin = _user(db, "root", role="super_admin", org=None, is_superuser=True)
        db.commit()

        with path_cache():
            result = await org_api.create_organization(
                org_api.OrganizationCreate(name="NEW_ROOT", code="520000"), root_admin, db
            )
        assert result["code"] == 200
        assert result["data"].name == "NEW_ROOT"


class path_cache:
    """屏蔽 activate/deactivate 的真实缓存写（不关心缓存层，只看守卫语义）。"""

    def __enter__(self):
        self._patcher = patch("app.api.v1.organization.cache_manager.delete", new=AsyncMock())
        self._patcher.start()
        return self

    def __exit__(self, *exc):
        self._patcher.stop()
        return False
