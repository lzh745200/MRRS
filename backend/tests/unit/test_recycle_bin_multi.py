"""通用回收站端点测试：项目 / 经费 / 学校 三资源 (Phase C)

覆盖：软删→恢复回环；软删→彻底删除(密码错/对)；非管理员 403；
活跃记录拒绝操作；级联清除验证（项目→其下经费一并物理删除）。
"""
import pytest

from app.models.fund import Fund
from app.models.project import Project
from app.models.school import School


def _admin():
    u = type("U", (), {})()
    u.id = 1
    u.username = "admin1"
    u.role = "admin"
    u.is_superuser = True
    u.is_active = True
    u.organization_id = 1
    u.permissions_list = ["*"]
    u.full_name = "管理员"
    from app.core.security import get_password_hash

    u.hashed_password = get_password_hash("admin123")
    return u


def _regular():
    u = type("U", (), {})()
    u.id = 2
    u.username = "user2"
    u.role = "user"
    u.is_superuser = False
    u.is_active = True
    u.organization_id = 2
    u.permissions_list = ["read"]
    return u


def _set_user(client, user):
    from app.core.security import get_current_user

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    return original


def _reset(client, original):
    client.app.dependency_overrides = original


RESOURCES = {
    "projects": ("测试项目", Project),
    "funds": ("测试经费", Fund),
    "schools": ("测试学校", School),
}
BASE = "/api/v1"


def _create(db, resource):
    if resource == "projects":
        rec = Project(name="回收站P", code="RB-P-1", budget=10)
    elif resource == "funds":
        rec = Fund(name="回收站F", amount=100, status="pending")
    else:
        rec = School(name="回收站S")
    db.add(rec)
    db.commit()
    return rec.id


def _soft_delete(db, resource, rid):
    model = RESOURCES[resource][1]
    rec = db.query(model).filter(model.id == rid).first()
    rec.is_active = False
    db.commit()


class TestRecycleBinLifecycle:
    @pytest.mark.parametrize("resource", list(RESOURCES))
    def test_restore_roundtrip(self, client, resource, ):
        """创建→软删→恢复→默认可见。"""
        admin = _admin()
        original = _set_user(client, admin)
        try:
            from app.core.database import get_db

            db_gen = client.app.dependency_overrides.get(get_db)
            db = next(db_gen()) if db_gen else None
            assert db is not None, "需要 get_db override 提供会话"
            rid = _create(db, resource)
            _soft_delete(db, resource, rid)

            resp = client.post(f"{BASE}/{resource}/{rid}/restore")
            assert resp.status_code == 200, resp.text[:200]

            model = RESOURCES[resource][1]
            rec = db.query(model).filter(model.id == rid).first()
            db.refresh(rec)
            assert rec.is_active is True
        finally:
            _reset(client, original)

    @pytest.mark.parametrize("resource", list(RESOURCES))
    def test_purge_requires_correct_password_and_cascades(self, client, resource):
        admin = _admin()
        original = _set_user(client, admin)
        try:
            from app.core.database import get_db

            db = next(client.app.dependency_overrides[get_db]())
            rid = _create(db, resource)

            # 项目挂一个经费子记录，验证级联
            child_id = None
            if resource == "projects":
                child = Fund(name="子经费", project_id=rid, amount=5, status="pending")
                db.add(child)
                db.commit()
                child_id = child.id

            _soft_delete(db, resource, rid)

            bad = client.post(
                f"{BASE}/{resource}/{rid}/purge",
                json={"confirm_password": "wrong"},
            )
            assert bad.status_code == 400

            ok = client.post(
                f"{BASE}/{resource}/{rid}/purge",
                json={"confirm_password": "admin123"},
            )
            assert ok.status_code == 200, ok.text[:300]
            body = ok.json().get("data") or {}
            assert body["deleted_records"] >= 1

            model = RESOURCES[resource][1]
            assert db.query(model).filter(model.id == rid).first() is None
            if child_id:
                assert (
                    db.query(Fund).filter(Fund.id == child_id).first() is None
                ), "项目的经费应被级联物理删除"
        finally:
            _reset(client, original)

    @pytest.mark.parametrize("resource", list(RESOURCES))
    def test_non_admin_forbidden(self, client, resource):
        admin = _admin()
        regular = _regular()

        original = _set_user(client, admin)
        try:
            from app.core.database import get_db

            db = next(client.app.dependency_overrides[get_db]())
            rid = _create(db, resource)
            _soft_delete(db, resource, rid)
        finally:
            _reset(client, original)

        original = _set_user(client, regular)
        try:
            for method, path in [
                ("post", f"{BASE}/{resource}/{rid}/restore"),
                ("post", f"{BASE}/{resource}/{rid}/purge"),
                ("get", f"{BASE}/{resource}/{rid}/purge/preview"),
            ]:
                kwargs = {"json": {"confirm_password": "x"}} if method == "post" else {}
                resp = getattr(client, method)(path, **kwargs)
                assert resp.status_code == 403, f"{path} 应 403"
        finally:
            _reset(client, original)

    @pytest.mark.parametrize("resource", list(RESOURCES))
    def test_active_record_rejected(self, client, resource):
        admin = _admin()
        original = _set_user(client, admin)
        try:
            from app.core.database import get_db

            db = next(client.app.dependency_overrides[get_db]())
            rid = _create(db, resource)
            resp = client.post(f"{BASE}/{resource}/{rid}/restore")
            assert resp.status_code == 400
            resp = client.post(
                f"{BASE}/{resource}/{rid}/purge",
                json={"confirm_password": "admin123"},
            )
            assert resp.status_code == 400
        finally:
            _reset(client, original)
