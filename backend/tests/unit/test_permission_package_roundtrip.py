"""权限配置包跨机回环与契约回归测试 (T08)

核心场景：A 机导出 → B 机导入。两机同名用户的数字 ID 不同、
角色自增 ID 也不同 —— 修复前按裸 ID 匹配会全部静默丢失。

覆盖：
1. 双库回环：username/role_name 映射使权限在异 ID 环境正确还原
2. 内容校验和：篡改数据段后预览拒绝导入
3. /import 契约：响应必须携带 saved_file_name/file_name（登录页两步导入依赖）
4. 旧版兼容：无 content_checksum 的包仅告警，可正常导入
"""
import json
import os
import zipfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import Mock

from app.models import Base
from app.models.rbac import RbacRole, RolePermission, UserPermission, UserRole
from app.models.user import User
from app.services.permission_package_service import PermissionPackageService


def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine), engine


def _seed_machine(Session, user_pk_id: int):
    """在一台"机器"上播种：自定义角色 + 用户 + 关联。user_pk_id 模拟不同机器的自增差异。"""
    db = Session()
    alice = User(
        id=user_pk_id,
        username="alice",
        full_name="Alice",
        hashed_password="x",
        role="user",
        is_active=True,
    )
    db.add(alice)
    db.flush()
    role = RbacRole(
        name="village_officer", description="村官", is_system=False,
        is_active=True, priority=50,
    )
    db.add(role)
    db.flush()
    db.add(RolePermission(role_id=role.id, permission="villages.read"))
    db.add(UserRole(user_id=alice.id, role_id=role.id))
    db.add(UserPermission(user_id=alice.id, permission="reports.export"))
    db.commit()
    ids = {"user_id": alice.id, "role_id": role.id}
    db.close()
    return ids


@pytest.fixture
def two_machines():
    session_a, eng_a = _make_db()
    session_b, eng_b = _make_db()
    # 同名用户/角色在两台机器上数字 ID 故意不同（跨机真实场景）
    ids_a = _seed_machine(session_a, user_pk_id=5)
    ids_b = _seed_machine(session_b, user_pk_id=42)
    yield session_a, session_b, ids_a, ids_b
    eng_a.dispose()
    eng_b.dispose()


class TestCrossMachineRoundtrip:
    def test_user_bindings_survive_different_ids(self, two_machines):
        session_a, session_b, ids_a, ids_b = two_machines
        svc_a = PermissionPackageService(session_a())
        exported = svc_a.export_package(description="回环测试")
        assert exported["success"] is True
        zip_path = exported["file_path"]

        db_b = session_b()
        svc_b = PermissionPackageService(db_b)
        preview = svc_b.import_package(zip_path)
        assert preview["success"] is True, preview.get("errors")

        confirmed = svc_b.confirm_import(zip_path, overwrite_existing=True)
        assert confirmed["success"] is True, confirmed.get("errors")
        # 用户-角色与直接权限都必须按 username 成功匹配（而不是静默跳过）
        assert confirmed["user_roles_assigned"] == 1, confirmed
        assert confirmed["user_permissions_assigned"] == 1, confirmed
        assert confirmed["user_roles_skipped"] == 0
        assert confirmed["user_permissions_skipped"] == 0

        # 落库校验：B 机 alice(42) 绑定了 B 机的 village_officer 角色
        alice_b = db_b.query(User).filter(User.username == "alice").first()
        role_b = (
            db_b.query(RbacRole).filter(RbacRole.name == "village_officer").first()
        )
        ur = (
            db_b.query(UserRole)
            .filter(UserRole.user_id == alice_b.id, UserRole.role_id == role_b.id)
            .all()
        )
        assert len(ur) == 1
        up = (
            db_b.query(UserPermission)
            .filter(UserPermission.user_id == alice_b.id)
            .all()
        )
        assert [p.permission for p in up] == ["reports.export"]
        db_b.close()

        try:
            os.unlink(zip_path)
        except OSError:
            pass


class TestContentChecksum:
    def test_tampered_package_rejected_in_preview(self, two_machines, tmp_path):
        session_a, session_b, _, _ = two_machines
        svc_a = PermissionPackageService(session_a())
        exported = svc_a.export_package()
        src = exported["file_path"]

        # 解包 → 篡改角色数据 → 重打包
        tampered = str(tmp_path / "tampered.zip")
        with zipfile.ZipFile(src, "r") as zin, zipfile.ZipFile(
            tampered, "w", zipfile.ZIP_DEFLATED
        ) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "data/roles.json":
                    roles = json.loads(data.decode("utf-8"))
                    roles[0]["priority"] = 9999  # 篡改
                    data = json.dumps(roles).encode("utf-8")
                zout.writestr(item, data)

        svc_b = PermissionPackageService(session_b())
        preview = svc_b.import_package(tampered)
        assert preview["success"] is False
        assert any("校验和" in e for e in preview.get("errors", []))

        try:
            os.unlink(src)
        except OSError:
            pass

    def test_legacy_package_without_checksum_warns_but_passes(self, tmp_path):
        # 构造无 content_checksum 的旧版包
        legacy = str(tmp_path / "legacy.zip")
        manifest = {"version": "1.0", "export_time": "2026-01-01T00:00:00+00:00",
                    "user_count": 1, "role_count": 1}
        with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("data/roles.json", json.dumps([
                {"id": 1, "name": "admin", "description": None, "is_system": True,
                 "is_active": True, "priority": 10, "permissions": []},
            ]))
            zf.writestr("data/user_roles.json", "[]")
            zf.writestr("data/user_permissions.json", "[]")
            zf.writestr("data/user_menus.json", "[]")
            zf.writestr("data/user_legacy.json", json.dumps([
                {"username": "ghost", "role": "user", "permissions": "",
                 "data_scope": "org", "is_superuser": False, "organization_id": None},
            ]))
            zf.writestr("data/organizations.json", "[]")

        session_b, eng_b = _make_db()
        try:
            svc_b = PermissionPackageService(session_b())
            preview = svc_b.import_package(legacy)
            assert preview["success"] is True
            assert any("内容校验和" in w for w in preview["preview"]["warnings"])
        finally:
            eng_b.dispose()


class TestImportApiContract:
    def test_import_response_carries_saved_file_name(self, client):
        """登录页两步导入依赖 saved_file_name/file_name 字段（旧缺陷回归）。"""
        if client is None:
            pytest.skip("client fixture unavailable")
        admin = Mock(id=1, username="admin", role="super_admin", is_superuser=True,
                     is_active=True, permissions_list=["*"], organization_id=1)
        from app.api.v1 import permission_package as pp_module

        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[pp_module._optional_current_user] = lambda: admin

        # 构造一个最小合法 ZIP 直接上传
        import io

        buf = io.BytesIO()
        manifest = {"version": "1.0"}
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("data/roles.json", "[]")
            zf.writestr("data/user_legacy.json", "[]")
        buf.seek(0)

        resp = client.post(
            "/api/v1/permission-packages/import",
            files={"file": ("pkg_contract.zip", buf, "application/zip")},
        )
        client.app.dependency_overrides = original
        if resp.status_code in (401, 403):
            pytest.skip(f"认证环境不可用: {resp.status_code}")
        assert resp.status_code == 200, resp.text[:300]
        body = resp.json().get("data") or resp.json()
        assert body.get("saved_file_name"), "必须返回 saved_file_name"
        assert body.get("file_name"), "必须返回 file_name 兼容字段"
