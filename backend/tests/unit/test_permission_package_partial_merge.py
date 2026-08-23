"""权限包选择性导出 + merge 合并导入测试 (T09)"""
import json
import os
import zipfile

from app.models.rbac import RbacRole, UserRole as UR, UserPermission as UP
from app.models.user import User
from app.services.permission_package_service import PermissionPackageService

from tests.unit.test_permission_package_roundtrip import two_machines  # noqa: F401


class TestPartialExportAndMerge:
    def test_partial_export_scopes_to_selected_role(self, two_machines):
        session_a, session_b, ids_a, ids_b = two_machines
        db_a = session_a()
        r2 = RbacRole(name="other_role", description="其他", is_system=False,
                      is_active=True, priority=60)
        db_a.add(r2)
        db_a.flush()
        alice_id = ids_a["user_id"]
        db_a.add(UR(user_id=alice_id, role_id=r2.id))
        db_a.commit()

        svc_a = PermissionPackageService(db_a)
        exported = svc_a.export_package(role_names=["village_officer"])
        assert exported["success"] is True

        with zipfile.ZipFile(exported["file_path"]) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            roles = json.loads(zf.read("data/roles.json").decode("utf-8"))
            user_roles = json.loads(zf.read("data/user_roles.json").decode("utf-8"))
            legacy = json.loads(zf.read("data/user_legacy.json").decode("utf-8"))
        assert manifest.get("scope") == "partial"
        assert [r["name"] for r in roles] == ["village_officer"]
        assert all(ur.get("role_name") == "village_officer" for ur in user_roles)
        assert [u["username"] for u in legacy] == ["alice"]
        db_a.close()

    def test_merge_mode_preserves_existing_bindings(self, two_machines):
        session_a, session_b, ids_a, ids_b = two_machines
        svc_a = PermissionPackageService(session_a())
        exported = svc_a.export_package()
        zip_path = exported["file_path"]

        db_b = session_b()
        keeper = RbacRole(name="keeper_role", description=None, is_system=False,
                          is_active=True, priority=70)
        db_b.add(keeper)
        db_b.flush()
        bob = User(username="bob", full_name="B", hashed_password="x",
                   role="user", is_active=True)
        db_b.add(bob)
        db_b.flush()
        db_b.add(UR(user_id=bob.id, role_id=keeper.id))
        db_b.add(UP(user_id=bob.id, permission="keeper.perm"))
        db_b.commit()

        svc_b = PermissionPackageService(db_b)
        preview = svc_b.import_package(zip_path)
        assert preview["success"] is True
        confirmed = svc_b.confirm_import(zip_path, mode="merge")
        assert confirmed["success"] is True, confirmed.get("errors")

        roles_after = {r.name for r in db_b.query(RbacRole).all()}
        assert "keeper_role" in roles_after, "merge 不应删除目标机既有角色"
        assert (bob.id, keeper.id) in {
            (ur.user_id, ur.role_id) for ur in db_b.query(UR).all()
        }, "merge 不应删除目标机既有绑定"
        assert any(up.permission == "reports.export" for up in db_b.query(UP).all()), \
            "包内权限应已合并写入"
        db_b.close()

        try:
            os.unlink(zip_path)
        except OSError:
            pass
