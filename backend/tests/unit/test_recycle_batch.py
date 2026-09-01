"""批量恢复/批量彻底删除端点测试 (Phase: 回收站批量操作)"""
import pytest

from app.models.fund import Fund
from app.models.project import Project


def _admin():
    u = type("U", (), {})()
    u.id = 1
    u.username = "a"
    u.role = "admin"
    u.is_superuser = True
    u.is_active = True
    u.organization_id = 1
    from app.core.security import get_password_hash
    u.hashed_password = get_password_hash("pw")
    return u


BASE = "/api/v1"


class TestBatchOperations:
    def test_batch_restore(self, client):
        admin = _admin()
        from app.core.security import get_current_user
        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_current_user] = lambda: admin

        try:
            from app.core.database import get_db
            db = next(client.app.dependency_overrides[get_db]())

            p1 = Project(name="BR1", code="BR-1", budget=1)
            p2 = Project(name="BR2", code="BR-2", budget=2)
            db.add_all([p1, p2])
            db.commit()
            for r in (p1, p2):
                r.is_active = False
                r.deleted_at = None
            db.commit()

            resp = client.post(
                f"{BASE}/projects/batch-restore",
                json={"ids": [p1.id, p2.id], "confirm_password": ""},
            )
            assert resp.status_code == 200, resp.text[:200]
            assert resp.json()["data"]["restored"] == 2
        finally:
            client.app.dependency_overrides = original

    def test_batch_purge(self, client):
        admin = _admin()
        from app.core.security import get_current_user
        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_current_user] = lambda: admin

        try:
            from app.core.database import get_db
            db = next(client.app.dependency_overrides[get_db]())

            f1 = Fund(name="BP1", amount=1)
            f2 = Fund(name="BP2", amount=2)
            db.add_all([f1, f2])
            db.commit()
            for r in (f1, f2):
                r.is_active = False
            db.commit()
            ids = [f1.id, f2.id]

            # 密码错误 → 400
            bad = client.post(
                f"{BASE}/funds/batch-purge",
                json={"ids": ids, "confirm_password": "wrong"},
            )
            assert bad.status_code == 400

            ok = client.post(
                f"{BASE}/funds/batch-purge",
                json={"ids": ids, "confirm_password": "pw"},
            )
            assert ok.status_code == 200
            assert ok.json()["data"]["purged"] == 2

            for rid in ids:
                assert db.query(Fund).filter(Fund.id == rid).first() is None
        finally:
            client.app.dependency_overrides = original

    def test_batch_purge_non_admin_403(self, client):
        regular = type("U", (), {})()
        regular.id = 99; regular.username = "u"; regular.role = "user"
        regular.is_superuser = False; regular.is_active = True
        regular.organization_id = 1

        from app.core.security import get_current_user
        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_current_user] = lambda: regular
        try:
            resp = client.post(
                f"{BASE}/projects/batch-purge",
                json={"ids": [1], "confirm_password": "x"},
            )
            assert resp.status_code == 403
        finally:
            client.app.dependency_overrides = original
