"""R14 组织树元数据修复回归（真实 HTTP 探测 2026-09-13 发现）。

缺陷：POST /api/v1/organizations 走 Organization(**org_data) 直建，path/level
未落库（NULL）。组织级数据权限完全依赖 path 前缀匹配
（OrganizationPermissionService.can_access_organization → get_subordinate_ids →
Organization.path LIKE），因此**经 UI/接口新建的组织，其成员一律被判为
"无组织权限"**：数据包导出等组织门禁端点恒 403（安装包首启即复现）。

修复三件套：
1. 端点补 path/level（根 /{id}/、子 {父 path}{id}/，与 OrganizationService 同口径）；
2. get_subordinate_organizations 对 path 为 NULL 的历史数据退化"仅自身"；
3. repair_organization_paths() 启动自检回填（幂等）。
"""

from unittest.mock import MagicMock

import pytest

from app.models.organization import Organization


def _admin():
    admin = MagicMock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.organization_id = None
    return admin


async def _create_org(db, payload):
    """直调端点协程并返回**落库**的 ORM 行。

    直调而非 TestClient：全量套件下 app.dependency_overrides 会被其它测试
    替换/清理，HTTP 级断言会因外部状态 401（首轮全量跑实测）。
    端点用的是模块内的 OrganizationCreate（organization.py:72-88 局部模型，
    与 app.schemas.organization 同名基类字段不同——后者无 code 字段）。
    """
    from app.api.v1.organization import OrganizationCreate, create_organization

    await create_organization(
        data=OrganizationCreate(**payload), current_user=_admin(), db=db
    )
    return (
        db.query(Organization)
        .filter(Organization.name == payload["name"])
        .order_by(Organization.id.desc())
        .first()
    )


def _db():
    """与 client fixture 同一内存库的会话（conftest 已重定向 SessionLocal）。"""
    from app.core.database import SessionLocal

    return SessionLocal()


class TestCreateOrganizationTreeMetadata:
    async def test_root_org_gets_path_and_level(self, client):
        db = _db()
        try:
            org = await _create_org(db, {"name": "根组织R14"})
            assert org.path == f"/{org.id}/"
            assert str(org.level) == "1"
        finally:
            db.close()

    async def test_child_org_extends_parent_path(self, client):
        db = _db()
        try:
            parent = await _create_org(db, {"name": "父组织R14"})
            child = await _create_org(db, {"name": "子组织R14", "parent_id": parent.id})
            assert child.path == f"/{parent.id}/{child.id}/"
            assert str(child.level) == "2"
        finally:
            db.close()

    async def test_missing_parent_is_rejected(self, client):
        from fastapi import HTTPException

        db = _db()
        try:
            with pytest.raises(HTTPException) as exc:
                await _create_org(db, {"name": "孤儿组织R14", "parent_id": 999999})
            assert exc.value.status_code == 400
        finally:
            db.close()

    async def test_member_of_new_org_can_access_it(self, client):
        """回归本体：新建组织的成员必须通过组织级权限校验（原先恒 403）。"""
        from app.models.user import User
        from app.services.organization_permission_service import OrganizationPermissionService

        db = _db()
        try:
            org = await _create_org(db, {"name": "权限组织R14"})
            org_id = org.id
            user = User(username="r14_member", hashed_password="x", role="user",
                        organization_id=org_id, is_active=True)
            db.add(user)
            db.flush()

            svc = OrganizationPermissionService(db)
            assert svc.can_access_organization(user.id, org_id) is True
            assert org_id in svc.get_accessible_organization_set(user.id)
        finally:
            db.close()


class TestStartupOrgPathBackfill:
    """启动自检里的组织树回填（R14）：两条分支都要走通且只在缺失时写库。"""

    def test_backfills_and_logs_when_missing(self, client, caplog):
        from app.startup.monitors import _backfill_organization_paths

        db = _db()
        try:
            db.add(Organization(name="启动回填R14", code="BOOT_FIX_R14", path=None, level=None, is_active=True))
            db.commit()  # 启动回填走独立会话，必须已提交才可见
        finally:
            db.close()

        import logging

        with caplog.at_level(logging.WARNING):
            outcome = _backfill_organization_paths()
        assert outcome["repaired"] >= 1
        assert any("组织树元数据回填" in r.message for r in caplog.records)

    def test_silent_when_nothing_missing(self, client, caplog):
        from app.startup.monitors import _backfill_organization_paths

        import logging

        with caplog.at_level(logging.WARNING):
            outcome = _backfill_organization_paths()
        assert outcome["repaired"] == 0
        assert not any("组织树元数据回填" in r.message for r in caplog.records)


class TestSubordinateFallbackAndRepair:
    def test_subordinate_ids_fall_back_to_self_for_null_path(self, client):
        from app.services.organization_service import OrganizationService

        db = _db()
        try:
            legacy = Organization(name="历史组织R14", code="LEGACY_R14", level=None, path=None, is_active=True)
            db.add(legacy)
            db.flush()
            svc = OrganizationService(db)
            assert svc.get_subordinate_ids(legacy.id, include_self=True) == [legacy.id]
            assert svc.get_subordinate_ids(legacy.id, include_self=False) == []
        finally:
            db.close()

    def test_repair_backfills_paths_and_is_idempotent(self, client):
        from app.services.organization_service import OrganizationService

        db = _db()
        try:
            root = Organization(name="待修根R14", code="FIX_ROOT", path=None, level=None, is_active=True)
            db.add(root)
            db.flush()
            child = Organization(name="待修子R14", code="FIX_CHILD", parent_id=root.id,
                                 path=None, level=None, is_active=True)
            db.add(child)
            db.flush()

            svc = OrganizationService(db)
            first = svc.repair_organization_paths()
            assert first["repaired"] >= 2
            assert first["remaining"] == 0

            db.refresh(root)
            db.refresh(child)
            assert root.path == f"/{root.id}/"
            assert str(root.level) == "1"
            assert child.path == f"/{root.id}/{child.id}/"
            assert str(child.level) == "2"

            second = svc.repair_organization_paths()
            assert second["repaired"] == 0  # 幂等：无缺失不再写库
        finally:
            db.close()
