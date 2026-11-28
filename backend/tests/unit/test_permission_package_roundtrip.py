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
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

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

    def test_unsigned_package_rejected_when_pubkey_configured(
        self, two_machines, monkeypatch
    ):
        """W27（P0-7）：本机配了 `PACKAGE_PUBKEY` 时，**未签名**包必须被拒绝。

        这条覆盖 `import_package` 里"签名校验失败 → 直接返回 success=False"的
        调用点（`_signature_error` 本身另有无密钥/验签两类单测）。
        """
        from app.core.grant_signing import generate_keypair

        import app.core.config as cfg

        session_a, session_b, _, _ = two_machines
        exported = PermissionPackageService(session_a()).export_package()
        src = exported["file_path"]
        assert src

        _priv, pub = generate_keypair()
        monkeypatch.setattr(cfg.settings, "PACKAGE_PUBKEY", pub, raising=False)

        preview = PermissionPackageService(session_b()).import_package(src)
        assert preview["success"] is False
        assert "签名" in preview.get("message", "")
        assert any("未签名" in e for e in preview.get("errors", []))

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
        # admin（super_admin）已通过 _optional_current_user override 注入，鉴权必然通过；
        # 移除运行时 skip 以免掩盖真实鉴权回归（原 latent skip 永不触发）。
        assert resp.status_code == 200, resp.text[:300]
        body = resp.json().get("data") or resp.json()
        assert body.get("saved_file_name"), "必须返回 saved_file_name"
        assert body.get("file_name"), "必须返回 file_name 兼容字段"


# ==================== 2026-11-28：账号级遗留权限默认不落库 ====================


def _write_legacy_package(path, *, roles=None, user_legacy=None):
    """构造最小合法权限包（1.0 格式，无 content_checksum）。"""
    manifest = {
        "version": "1.0",
        "export_time": "2026-01-01T00:00:00+00:00",
        "user_count": len(user_legacy or []),
        "role_count": len(roles or []),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("data/roles.json", json.dumps(roles or []))
        zf.writestr("data/user_roles.json", "[]")
        zf.writestr("data/user_permissions.json", "[]")
        zf.writestr("data/user_menus.json", "[]")
        zf.writestr("data/user_legacy.json", json.dumps(user_legacy or []))
        zf.writestr("data/organizations.json", "[]")
    return str(path)


def _legacy_entry(role="super_admin", data_scope="self", permissions="*"):
    return {
        "username": "bob",
        "role": role,
        "permissions": permissions,
        "data_scope": data_scope,
        "is_superuser": False,
        "organization_id": None,
        "organization_code": None,
    }


def _db_with_bob(data_scope="org", role="user", permissions="keep:perm"):
    Session, engine = _make_db()
    db = Session()
    bob = User(
        username="bob", full_name="Bob", hashed_password="x",
        role=role, data_scope=data_scope, permissions=permissions, is_active=True,
    )
    db.add(bob)
    db.commit()
    return db, engine, bob.id


class TestLegacyPrivilegeOptIn:
    def test_legacy_privileges_skipped_by_default(self, tmp_path):
        db, engine, bob_id = _db_with_bob()
        pkg = _write_legacy_package(
            tmp_path / "skip.zip", user_legacy=[_legacy_entry()],
        )
        try:
            result = PermissionPackageService(db).confirm_import(pkg)
            assert result["success"] is True, result.get("errors")
            assert result["legacy_privileges_skipped"] == 1
            assert any("apply_legacy_privileges" in w for w in result["warnings"]), result
            bob = db.query(User).filter(User.id == bob_id).one()
            assert (bob.role, bob.data_scope, bob.permissions) == (
                "user", "org", "keep:perm",
            ), "默认导入绝不能静默改写账号级角色/数据范围/权限"
        finally:
            db.close()
            engine.dispose()

    def test_apply_legacy_privileges_true_restores_v1(self, tmp_path):
        db, engine, bob_id = _db_with_bob()
        pkg = _write_legacy_package(
            tmp_path / "apply.zip",
            user_legacy=[_legacy_entry(
                role="admin", data_scope="org_children", permissions="report:read",
            )],
        )
        try:
            result = PermissionPackageService(db).confirm_import(
                pkg, apply_legacy_privileges=True,
            )
            assert result["success"] is True, result.get("errors")
            assert result["legacy_privileges_skipped"] == 0
            bob = db.query(User).filter(User.id == bob_id).one()
            assert (bob.role, bob.data_scope, bob.permissions) == (
                "admin", "org_children", "report:read",
            )
        finally:
            db.close()
            engine.dispose()

    @pytest.mark.parametrize("scope", ["all", "org_children", "org", "self"])
    def test_four_data_scopes_roundtrip_without_downgrade(self, tmp_path, scope):
        db, engine, bob_id = _db_with_bob(data_scope="org")
        pkg = _write_legacy_package(
            tmp_path / f"scope_{scope}.zip",
            user_legacy=[_legacy_entry(
                role="user", data_scope=scope, permissions="",
            )],
        )
        try:
            result = PermissionPackageService(db).confirm_import(
                pkg, apply_legacy_privileges=True,
            )
            assert result["success"] is True, result.get("errors")
            bob = db.query(User).filter(User.id == bob_id).one()
            assert bob.data_scope == scope, f"{scope} 不得被静默降级为 org"
        finally:
            db.close()
            engine.dispose()

    def test_package_role_gets_non_empty_code(self, tmp_path):
        db, engine, _ = _db_with_bob()
        pkg = _write_legacy_package(
            tmp_path / "role_code.zip",
            roles=[{
                "id": 1, "name": "自定义角色", "description": "d",
                "is_system": False, "is_active": True, "priority": 100,
                "permissions": [],
            }],
        )
        try:
            result = PermissionPackageService(db).confirm_import(pkg)
            assert result["success"] is True, result.get("errors")
            role = db.query(RbacRole).filter(RbacRole.name == "自定义角色").one()
            assert role.code and role.code.strip(), "包内角色缺 code 时必须派生非空 code"
        finally:
            db.close()
            engine.dispose()

    def test_existing_role_code_not_overwritten_by_empty(self, tmp_path):
        db, engine, _ = _db_with_bob()
        keeper = RbacRole(
            name="village_officer", code="KEEP_CODE", description="d",
            is_system=False, is_active=True, priority=50,
        )
        db.add(keeper)
        db.commit()
        pkg = _write_legacy_package(
            tmp_path / "role_keep.zip",
            roles=[{
                "id": 1, "name": "village_officer", "code": "", "description": "d",
                "is_system": False, "is_active": True, "priority": 50,
                "permissions": [],
            }],
        )
        try:
            result = PermissionPackageService(db).confirm_import(pkg, mode="merge")
            assert result["success"] is True, result.get("errors")
            db.expire_all()
            role = db.query(RbacRole).filter(RbacRole.name == "village_officer").one()
            assert role.code == "KEEP_CODE", "空 code 不得覆盖既有非空 code"
        finally:
            db.close()
            engine.dispose()

    def test_unique_role_code_probe_returns_first_free_candidate(self):
        db, engine, _ = _db_with_bob()
        service = PermissionPackageService(db)
        db.add(RbacRole(
            name="taken", code="DUP", description="d",
            is_system=False, is_active=True, priority=10,
        ))
        db.commit()
        try:
            code = service._unique_role_code("DUP")
            assert code.startswith("DUP_")
            assert code != "DUP"
        finally:
            db.close()
            engine.dispose()

    def test_role_code_uses_incoming_when_existing_has_none_and_no_clash(self):
        db, engine, _ = _db_with_bob()
        service = PermissionPackageService(db)
        existing = RbacRole(
            name="custom_role", code="", description="d",
            is_system=False, is_active=True, priority=10,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
        try:
            code = service._role_code({"code": "FREE_CODE"}, existing)
            assert code == "FREE_CODE"
        finally:
            db.close()
            engine.dispose()

    def test_role_code_derives_unique_when_incoming_clashes(self):
        db, engine, _ = _db_with_bob()
        service = PermissionPackageService(db)
        db.add(RbacRole(
            name="other", code="TAKEN", description="d",
            is_system=False, is_active=True, priority=10,
        ))
        existing = RbacRole(
            name="custom_role", code="", description="d",
            is_system=False, is_active=True, priority=10,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)
        try:
            code = service._role_code({"code": "TAKEN"}, existing)
            assert code and code != "TAKEN"
        finally:
            db.close()
            engine.dispose()


class TestConfirmApiLegacyFlag:
    """API 层：apply_legacy_privileges 默认 false，仅管理员可置 true。"""

    @staticmethod
    def _call(tmp_path, current_user, **overrides):
        from app.api.v1 import permission_package as pp_module

        package = tmp_path / "api_flag.zip"
        package.write_bytes(b"PK\x03\x04stub")
        service = MagicMock()
        service.confirm_import.return_value = {"success": True}
        kwargs = dict(
            file_name="api_flag.zip",
            body=SimpleNamespace(overwrite_existing=True, mode=None),
            current_user=current_user,
            db=MagicMock(),
            request=Mock(),
            force=False,
        )
        kwargs.update(overrides)
        with (
            patch.object(pp_module, "_assert_package_import_principal", return_value=True),
            patch.object(
                pp_module, "_resolve_package_upload_path", return_value=str(package)
            ),
            patch.object(pp_module, "assert_not_duplicate", return_value=("sum", None)),
            patch.object(pp_module, "PermissionPackageService", return_value=service),
            patch.object(pp_module, "write_work_log"),
            patch.object(pp_module, "record_import"),
        ):
            resp = pp_module.confirm_import_permission_package(**kwargs)
        return resp, service

    def test_flag_defaults_to_false_and_is_passed(self, tmp_path):
        admin = Mock(id=1, username="admin", role="admin", is_superuser=False)
        resp, service = self._call(tmp_path, admin)
        assert resp.status_code == 200
        assert service.confirm_import.call_args.kwargs[
            "apply_legacy_privileges"
        ] is False

    def test_flag_true_is_passed_for_admin(self, tmp_path):
        admin = Mock(id=1, username="admin", role="admin", is_superuser=False)
        resp, service = self._call(
            tmp_path, admin, apply_legacy_privileges=True,
        )
        assert resp.status_code == 200
        assert service.confirm_import.call_args.kwargs[
            "apply_legacy_privileges"
        ] is True

    def test_non_admin_cannot_enable_flag(self, tmp_path):
        from fastapi import HTTPException

        from app.api.v1 import permission_package as pp_module

        viewer = Mock(id=2, username="v", role="viewer", is_superuser=False)
        with patch.object(
            pp_module, "_assert_package_import_principal", return_value=False
        ):
            with pytest.raises(HTTPException) as exc:
                pp_module.confirm_import_permission_package(
                    file_name="pkg.zip",
                    body=SimpleNamespace(overwrite_existing=True, mode=None),
                    current_user=viewer,
                    db=MagicMock(),
                    request=Mock(),
                    force=False,
                    apply_legacy_privileges=True,
                )
        assert exc.value.status_code == 403
        assert "apply_legacy_privileges" in exc.value.detail
