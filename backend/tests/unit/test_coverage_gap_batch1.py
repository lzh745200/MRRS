import hashlib
import io
import json
import os
import struct
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.permission_package_service import PermissionPackageService
from app.services.query_analyzer_service import QueryAnalyzer
from app.services.rural_work_service import RuralWorkService, _iso, _safe_enum_value
from app.services.organization_code_service import OrganizationCodeService
from app.services.encrypted_package import (
    create_encrypted_package,
    extract_encrypted_package,
    _derive_key,
    MAGIC,
    VERSION,
)


UPLOAD_PATCH = "app.utils.paths.get_uploads_path"


def _query_side_effect_models(empty_roles=True, role_query_result=None):
    """Return a db.query side_effect for PermissionPackageService."""
    def side_effect(*args):
        model = args[0] if args else None
        model = args[0] if args else None
        q = MagicMock()
        name = getattr(model, "__name__", "")
        if name == "RbacRole":
            if empty_roles:
                q.order_by.return_value.all.return_value = []
                q.filter.return_value.all.return_value = []
            else:
                q.order_by.return_value.all.return_value = role_query_result or []
                q.filter.return_value.all.return_value = []
        elif name in ("RolePermission", "UserRole", "UserPermission"):
            q.all.return_value = []
            q.filter.return_value.all.return_value = []
        elif name == "User":
            q.filter.return_value.all.return_value = []
            q.all.return_value = []
        else:
            q.all.return_value = []
        return q
    return side_effect


# ---------------------------------------------------------------------------
# 1. PermissionPackageService — Export
# ---------------------------------------------------------------------------


class TestPermissionPackageServiceExport:

    def _make(self):
        db = MagicMock()
        return PermissionPackageService(db), db

    def test_export_package_basic(self):
        svc, db = self._make()
        db.query.side_effect = _query_side_effect_models()
        with patch(UPLOAD_PATCH) as mock_path:
            mock_path.return_value = tempfile.mkdtemp()
            result = svc.export_package()
            assert result["success"] is True
            assert result["role_count"] == 0
            assert result["user_count"] == 0
            assert os.path.exists(result["file_path"])

    def test_export_package_with_roles_and_users(self):
        svc, db = self._make()

        role = MagicMock()
        role.id = "r1"
        role.name = "admin"
        role.description = "desc"
        role.is_system = True
        role.is_active = True
        role.priority = 1

        rp = MagicMock()
        rp.permission = "read"

        ur = MagicMock()
        ur.user_id = 1
        ur.role_id = "r1"
        ur.expires_at = None

        up = MagicMock()
        up.user_id = 1
        up.permission = "write"
        up.expires_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        user = MagicMock()
        user.username = "alice"
        user.is_active = True
        user.allowed_menus = '["menu1","menu2"]'
        user.role = "admin"
        user.permissions = "read,write"
        user.data_scope = "all"
        user.is_superuser = True
        user.organization_id = 1

        def side_effect(*args):
            model = args[0] if args else None
            model = args[0] if args else None
            q = MagicMock()
            name = getattr(model, "__name__", "")
            if name == "RbacRole":
                q.order_by.return_value.all.return_value = [role]
                q.filter.return_value.all.return_value = [rp]
            elif name == "RolePermission":
                q.filter.return_value.all.return_value = [rp]
            elif name == "UserRole":
                q.all.return_value = [ur]
            elif name == "UserPermission":
                q.all.return_value = [up]
            elif name == "User":
                q.filter.return_value.all.return_value = [user]
            else:
                q.all.return_value = []
                q.filter.return_value.all.return_value = []
                q.order_by.return_value.all.return_value = []
            return q

        db.query.side_effect = side_effect

        with patch(UPLOAD_PATCH) as mock_path:
            mock_path.return_value = tempfile.mkdtemp()
            result = svc.export_package(password="test", description="test desc")
            assert result["success"] is True
            assert result["role_count"] == 1
            assert result["user_count"] == 1

    def test_export_user_menus_invalid_json(self):
        svc, db = self._make()

        user = MagicMock()
        user.username = "bob"
        user.is_active = True
        user.allowed_menus = "not-json{{{"
        user.role = None
        user.permissions = None
        user.data_scope = None
        user.is_superuser = None
        user.organization_id = None

        def side_effect(*args):
            model = args[0] if args else None
            model = args[0] if args else None
            q = MagicMock()
            if getattr(model, "__name__", "") == "User":
                q.filter.return_value.all.return_value = [user]
            else:
                q.order_by.return_value.all.return_value = []
                q.all.return_value = []
            return q

        db.query.side_effect = side_effect

        with patch(UPLOAD_PATCH) as mock_path:
            mock_path.return_value = tempfile.mkdtemp()
            result = svc.export_package()
            assert result["success"] is True

    def test_export_user_menus_non_string(self):
        svc, db = self._make()

        user = MagicMock()
        user.username = "carol"
        user.is_active = True
        user.allowed_menus = ["a", "b"]
        user.role = "operator"
        user.permissions = ""
        user.data_scope = "org"
        user.is_superuser = False
        user.organization_id = 1

        def side_effect(*args):
            model = args[0] if args else None
            model = args[0] if args else None
            q = MagicMock()
            if getattr(model, "__name__", "") == "User":
                q.filter.return_value.all.return_value = [user]
            else:
                q.order_by.return_value.all.return_value = []
                q.all.return_value = []
            return q

        db.query.side_effect = side_effect

        with patch(UPLOAD_PATCH) as mock_path:
            mock_path.return_value = tempfile.mkdtemp()
            result = svc.export_package()
            assert result["success"] is True

    def test_export_user_menus_none(self):
        svc, db = self._make()

        user = MagicMock()
        user.username = "dan"
        user.is_active = True
        user.allowed_menus = None
        user.role = "operator"
        user.permissions = ""
        user.data_scope = "org"
        user.is_superuser = False
        user.organization_id = None

        def side_effect(*args):
            model = args[0] if args else None
            model = args[0] if args else None
            q = MagicMock()
            if getattr(model, "__name__", "") == "User":
                q.filter.return_value.all.return_value = [user]
            else:
                q.order_by.return_value.all.return_value = []
                q.all.return_value = []
            return q

        db.query.side_effect = side_effect

        with patch(UPLOAD_PATCH) as mock_path:
            mock_path.return_value = tempfile.mkdtemp()
            result = svc.export_package()
            assert result["success"] is True

    def test_export_with_organizations_and_machine_bind(self):
        """覆盖 org_id→code 映射（列查询 line 110）+ 机器码绑定成功分支（237-250）。"""
        svc, db = self._make()

        org_row = MagicMock()   # 列查询 (Organization.id, Organization.code) 返回行
        org_row.id = 1
        org_row.code = "ORG-1"

        user = MagicMock()
        user.username = "alice"
        user.is_active = True
        user.allowed_menus = None
        user.role = "admin"
        user.permissions = ""
        user.data_scope = "org"
        user.is_superuser = False
        user.organization_id = 1

        def side_effect(*args):
            model = args[0] if args else None
            q = MagicMock()
            name = getattr(model, "__name__", "")
            cls_name = getattr(getattr(model, "class_", None), "__name__", "")
            if name == "User":                      # 模型查询 User(is_active)
                q.filter.return_value.all.return_value = [user]
            elif name == "" and cls_name == "Organization":
                q.all.return_value = [org_row]      # 列查询 → org_id_to_code
            elif name == "":                        # 其它列查询（User/RbacRole）
                q.all.return_value = []
            else:
                q.order_by.return_value.all.return_value = []
                q.all.return_value = []
                q.filter.return_value.all.return_value = []
            return q

        db.query.side_effect = side_effect

        with patch(UPLOAD_PATCH) as mock_path, \
             patch("app.core.database.SessionLocal") as mock_sl, \
             patch("app.services.machine_code_service.MachineCodeService") as mock_mcs:
            mock_path.return_value = tempfile.mkdtemp()
            mock_sl.return_value = MagicMock()
            mock_mcs.return_value.get_machine_code.return_value = "MC-TEST-123"
            result = svc.export_package(bind_machine_code=True)

        assert result["success"] is True
        with zipfile.ZipFile(result["file_path"]) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["machine_codes"] == ["MC-TEST-123"]

    def test_export_machine_code_fetch_failure_degrades(self):
        """机器码获取失败时降级：不绑定 machine_codes（覆盖 except 分支 247-248）。"""
        svc, db = self._make()
        db.query.side_effect = _query_side_effect_models()
        with patch(UPLOAD_PATCH) as mock_path, \
             patch("app.core.database.SessionLocal") as mock_sl, \
             patch("app.services.machine_code_service.MachineCodeService") as mock_mcs:
            mock_path.return_value = tempfile.mkdtemp()
            mock_sl.return_value = MagicMock()
            mock_mcs.return_value.get_machine_code.side_effect = RuntimeError("no mc")
            result = svc.export_package(bind_machine_code=True)
        assert result["success"] is True
        with zipfile.ZipFile(result["file_path"]) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert "machine_codes" not in manifest


# ---------------------------------------------------------------------------
# 2. PermissionPackageService — Import Preview
# ---------------------------------------------------------------------------


class TestPermissionPackageServiceImport:

    def _make(self):
        db = MagicMock()
        return PermissionPackageService(db), db

    def _make_zip(self, tmpdir, files=None):
        files = files or {
            "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
            "data/roles.json": [{"id": "r1", "name": "test", "permissions": ["read"]}],
            "data/user_roles.json": [],
            "data/user_permissions.json": [],
            "data/user_menus.json": [],
            "data/user_legacy.json": [
                {"username": "alice", "role": "admin", "permissions": "",
                 "data_scope": "org", "is_superuser": False},
            ],
        }
        path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(path, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, json.dumps(content, ensure_ascii=False))
        return path

    def test_import_file_not_exists(self):
        svc, _ = self._make()
        result = svc.import_package("/nonexistent/path.zip")
        assert result["success"] is False
        assert "文件不存在" in result["errors"][0]

    def test_import_not_zipfile(self):
        svc, _ = self._make()
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"not a zip")
            path = f.name
        try:
            result = svc.import_package(path)
            assert result["success"] is False
        finally:
            os.unlink(path)

    def test_import_missing_required_file(self):
        svc, _ = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.zip")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("manifest.json", "{}")
            result = svc.import_package(path)
            assert result["success"] is False
            assert "包结构不完整" in result["message"]

    def test_import_version_mismatch(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {"version": "9.9", "export_time": "2025-01-01"},
                "data/roles.json": [],
                "data/user_legacy.json": [],
            }
            path = self._make_zip(tmpdir, files)
            db.query.return_value.filter.return_value.all.return_value = []
            result = svc.import_package(path)
            assert result["success"] is True
            assert any("不匹配" in w for w in result["preview"]["warnings"])

    def test_import_with_missing_users(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_zip(tmpdir)
            db.query.return_value.filter.return_value.all.return_value = []
            result = svc.import_package(path)
            assert result["success"] is True
            assert any("不存在" in w for w in result["preview"]["warnings"])

    def test_import_invalid_json(self):
        """manifest.json 非法 → 固定用户态文案，不泄露 JSON 解码器细节（安全红线）。

        JSONDecodeError 文本含出错位置与文档片段，可反推包内结构，禁止出站。
        """
        svc, _ = self._make()
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = f.name
        try:
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("manifest.json", "{invalid json")
                zf.writestr("data/roles.json", "[]")
                zf.writestr("data/user_legacy.json", "[]")
            result = svc.import_package(path)
            assert result["success"] is False
            assert result["message"] == "文件内容格式错误"
            # 不泄露解码器细节（安全红线）
            assert "column" not in result["message"]
            assert "char" not in result["errors"][0]
        finally:
            os.unlink(path)

    def test_import_general_exception(self):
        """通用异常分支：内存解密重构后走 io.BytesIO(working) 流。

        mock 目标与新流对齐：真实临时文件保证 open() 读到非空字节（跳过
        “文件不存在”早退）；looks_encrypted=False 跳过解密；is_zipfile=True
        跳过“非 ZIP”早退；zipfile.ZipFile(BytesIO) 抛异常→通用分支。
        安全要求：回传固定用户态文案，不泄露内部异常文本 'boom'。
        """
        svc, _ = self._make()
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"non-empty-dummy-bytes")
            path = f.name
        try:
            with patch("app.utils.package_crypto.looks_encrypted", return_value=False), \
                 patch("zipfile.is_zipfile", return_value=True), \
                 patch("zipfile.ZipFile") as mock_zf:
                mock_zf.side_effect = Exception("boom")
                result = svc.import_package(path)
            assert result["success"] is False
            assert result["message"] == "文件解析错误"
            # 不泄露内部异常文本（安全红线）
            assert "boom" not in result["message"]
            assert "boom" not in result["errors"][0]
        finally:
            os.unlink(path)

    def _make_encrypted_zip(self, password, files=None):
        """构建真实加密权限包（走 package_crypto.encrypt_bytes）。"""
        from app.utils.package_crypto import encrypt_bytes
        files = files or {
            "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
            "data/roles.json": [],
            "data/user_legacy.json": [],
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, json.dumps(content, ensure_ascii=False))
        token = encrypt_bytes(buf.getvalue(), password)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(token)
            return f.name

    def test_import_encrypted_without_password(self):
        """加密包未提供密码 → 拒绝（覆盖 340-345）。"""
        svc, _ = self._make()
        path = self._make_encrypted_zip("secret")
        try:
            result = svc.import_package(path)
            assert result["success"] is False
            assert result["message"] == "该权限包已加密"
        finally:
            os.unlink(path)

    def test_import_encrypted_wrong_password(self):
        """加密包密码错误 → 拒绝且不泄露异常文本（覆盖 346/349-350）。"""
        svc, _ = self._make()
        path = self._make_encrypted_zip("secret")
        try:
            result = svc.import_package(path, password="wrong")
            assert result["success"] is False
            assert result["message"] == "密码错误"
        finally:
            os.unlink(path)

    def test_import_encrypted_success_returns_decrypted_bytes(self):
        """M3：加密包内存解密成功，明文经 _decrypted_bytes 交回，磁盘仍为密文。"""
        svc, db = self._make()
        db.query.return_value.filter.return_value.all.return_value = []
        path = self._make_encrypted_zip("secret")
        try:
            result = svc.import_package(path, password="secret")
            assert result["success"] is True
            assert "_decrypted_bytes" in result
            assert result["_decrypted_bytes"][:2] == b"PK"
            # M3 安全红线：明文未落盘，磁盘文件仍是密文
            from app.utils.package_crypto import looks_encrypted
            with open(path, "rb") as f:
                assert looks_encrypted(f.read()) is True
        finally:
            os.unlink(path)

    def test_import_machine_code_mismatch(self):
        """机器码绑定校验失败 → 拒绝导入（覆盖 379-385）。"""
        svc, _ = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {
                    "version": "1.0", "export_time": "2025-01-01",
                    "machine_codes": ["OTHER-MACHINE"],
                },
                "data/roles.json": [],
                "data/user_legacy.json": [],
            }
            path = self._make_zip(tmpdir, files)
            result = svc.import_package(path, current_machine_code="LOCAL-MACHINE")
            assert result["success"] is False
            assert result["message"] == "机器码校验失败"


# ---------------------------------------------------------------------------
# 3. PermissionPackageService — Confirm Import
# ---------------------------------------------------------------------------


class TestPermissionPackageServiceConfirm:

    def _make(self):
        db = MagicMock()
        return PermissionPackageService(db), db

    def _make_zip(self, tmpdir, files=None):
        files = files or {
            "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
            "data/roles.json": [
                {"id": "r1", "name": "newrole", "description": "d",
                 "is_system": False, "is_active": True, "priority": 100,
                 "permissions": ["read"]},
            ],
            "data/user_roles.json": [],
            "data/user_permissions.json": [],
            "data/user_menus.json": [],
            "data/user_legacy.json": [],
        }
        path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(path, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, json.dumps(content, ensure_ascii=False))
        return path

    def test_confirm_invalid_file(self):
        svc, _ = self._make()
        result = svc.confirm_import("/nonexistent.zip")
        assert result["success"] is False

    def test_confirm_creates_roles(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_zip(tmpdir)

            def side_effect(*args):
                model = args[0] if args else None
                model = args[0] if args else None
                q = MagicMock()
                name = getattr(model, "__name__", "")
                if name == "RbacRole":
                    q.filter.return_value.all.return_value = []
                    q.filter.return_value.first.return_value = None
                elif name == "User":
                    q.all.return_value = []
                    q.filter.return_value.first.return_value = None
                else:
                    q.all.return_value = []
                return q

            db.query.side_effect = side_effect
            result = svc.confirm_import(path)
            assert result["success"] is True
            assert result["roles_created"] >= 1

    def test_confirm_updates_existing_role(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_zip(tmpdir)
            existing_role = MagicMock()
            existing_role.name = "newrole"
            existing_role.description = "old"
            existing_role.is_active = True
            existing_role.priority = 100

            def side_effect(*args):
                model = args[0] if args else None
                model = args[0] if args else None
                q = MagicMock()
                name = getattr(model, "__name__", "")
                if name == "RbacRole":
                    q.filter.return_value.first.return_value = existing_role
                    q.filter.return_value.all.return_value = []
                elif name == "User":
                    q.all.return_value = []
                    q.filter.return_value.first.return_value = None
                else:
                    q.all.return_value = []
                    q.filter.return_value.first.return_value = None
                return q

            db.query.side_effect = side_effect
            result = svc.confirm_import(path)
            assert result["success"] is True
            assert result["roles_updated"] >= 1

    def test_confirm_with_user_roles_and_permissions(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
                "data/roles.json": [{"id": "r1", "name": "testrole", "permissions": ["read"]}],
                "data/user_roles.json": [{"role_id": "r1", "user_id": 1, "expires_at": None}],
                "data/user_permissions.json": [{"user_id": 1, "permission": "write", "expires_at": None}],
                "data/user_menus.json": [{"username": "alice", "allowed_menus": ["m1"]}],
                "data/user_legacy.json": [
                    {"username": "alice", "role": "admin", "permissions": "r",
                     "data_scope": "all", "is_superuser": False},
                ],
            }
            path = self._make_zip(tmpdir, files)

            existing_user = MagicMock()
            existing_user.id = 1
            existing_user.username = "alice"

            def side_effect(*args):
                model = args[0] if args else None
                model = args[0] if args else None
                q = MagicMock()
                name = getattr(model, "__name__", "")
                if name == "User":
                    q.all.return_value = [existing_user]
                    q.filter.return_value.first.return_value = existing_user
                elif name == "RbacRole":
                    q.filter.return_value.all.return_value = []
                    q.filter.return_value.first.return_value = None
                else:
                    q.all.return_value = []
                return q

            db.query.side_effect = side_effect
            result = svc.confirm_import(path)
            assert result["success"] is True
            assert result["user_roles_assigned"] >= 1
            assert result["user_permissions_assigned"] >= 1
            assert result["user_menus_updated"] >= 1
            assert result["user_legacy_updated"] >= 1

    def test_confirm_user_roles_with_expires_at(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
                "data/roles.json": [{"id": "r1", "name": "testrole", "permissions": []}],
                "data/user_roles.json": [{"role_id": "r1", "user_id": 1, "expires_at": "2026-01-01T00:00:00"}],
                "data/user_permissions.json": [{"user_id": 1, "permission": "p", "expires_at": "2026-01-01T00:00:00"}],
                "data/user_menus.json": [],
                "data/user_legacy.json": [],
            }
            path = self._make_zip(tmpdir, files)

            existing_user = MagicMock()
            existing_user.id = 1

            def side_effect(*args):
                model = args[0] if args else None
                model = args[0] if args else None
                q = MagicMock()
                name = getattr(model, "__name__", "")
                if name == "User":
                    q.all.return_value = [existing_user]
                    q.filter.return_value.first.return_value = existing_user
                elif name == "RbacRole":
                    q.filter.return_value.all.return_value = []
                    q.filter.return_value.first.return_value = None
                else:
                    q.all.return_value = []
                return q

            db.query.side_effect = side_effect
            result = svc.confirm_import(path)
            assert result["success"] is True

    def test_confirm_user_not_found_skipped(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
                "data/roles.json": [],
                "data/user_roles.json": [{"role_id": "r1", "user_id": 999}],
                "data/user_permissions.json": [{"user_id": 999, "permission": "p"}],
                "data/user_menus.json": [{"username": "ghost", "allowed_menus": []}],
                "data/user_legacy.json": [
                    {"username": "ghost", "role": "admin", "permissions": "",
                     "data_scope": "org", "is_superuser": False},
                ],
            }
            path = self._make_zip(tmpdir, files)

            def side_effect(*args):
                q = MagicMock()
                q.all.return_value = []
                q.filter.return_value.all.return_value = []
                q.filter.return_value.first.return_value = None
                return q

            db.query.side_effect = side_effect
            result = svc.confirm_import(path)
            assert result["success"] is True

    def test_confirm_general_exception_rollback(self):
        """通用异常分支：回滚 + 固定用户态文案，不泄露内部异常文本（安全红线）。

        异常原文经 API 层 result.get("message") 直达 HTTPException detail，
        会暴露 SQLAlchemy 错误/表名/服务器路径，故禁止出站。
        """
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_zip(tmpdir)
            db.query.side_effect = Exception("db error")
            result = svc.confirm_import(path)
            assert result["success"] is False
            assert result["message"] == "导入失败，请稍后重试或联系管理员"
            # 不泄露内部异常文本（安全红线）
            assert "db error" not in result["message"]
            assert "db error" not in result["errors"][0]
            db.rollback.assert_called_once()

    def test_confirm_role_import_error(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_zip(tmpdir)

            def side_effect(*args):
                model = args[0] if args else None
                model = args[0] if args else None
                q = MagicMock()
                name = getattr(model, "__name__", "")
                if name == "RbacRole":
                    q.filter.return_value.first.return_value = None
                    q.filter.return_value.all.return_value = []
                elif name == "User":
                    q.all.return_value = []
                    q.filter.return_value.first.return_value = None
                else:
                    q.all.return_value = []
                return q

            db.query.side_effect = side_effect
            db.add.side_effect = Exception("add failed")
            result = svc.confirm_import(path)
            assert result["success"] is True

    def test_confirm_import_without_optional_files(self):
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {"version": "1.0", "export_time": "2025-01-01"},
                "data/roles.json": [],
                "data/user_legacy.json": [],
            }
            path = self._make_zip(tmpdir, files)

            def side_effect(*args):
                q = MagicMock()
                q.all.return_value = []
                q.filter.return_value.all.return_value = []
                q.filter.return_value.first.return_value = None
                return q

            db.query.side_effect = side_effect
            result = svc.confirm_import(path, overwrite_existing=False)
            assert result["success"] is True

    def test_confirm_rejects_tampered_checksum(self):
        """S4：确认阶段复验内容校验和，篡改包拒绝落库且不触发破坏性清空。"""
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "manifest.json": {
                    "version": "1.0", "export_time": "2025-01-01",
                    "content_checksum": "sha256:" + "0" * 64,
                },
                "data/roles.json": [{"id": "r1", "name": "newrole", "permissions": ["read"]}],
                "data/user_legacy.json": [],
            }
            path = self._make_zip(tmpdir, files)
            result = svc.confirm_import(path)
            assert result["success"] is False
            assert result["integrity_failed"] is True
            # 破坏性清空 (_clear_existing_data → db.execute) 绝不能在校验失败后运行
            db.execute.assert_not_called()

    def test_confirm_without_manifest_skips_checksum(self):
        """无 manifest.json 的包：_verify_content_checksum 直接放行（覆盖 969）。"""
        svc, db = self._make()
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "data/roles.json": [],
                "data/user_legacy.json": [],
            }
            path = self._make_zip(tmpdir, files)
            db.query.side_effect = _query_side_effect_models()
            result = svc.confirm_import(path, overwrite_existing=False)
            assert result["success"] is True


# ---------------------------------------------------------------------------
# 4. PermissionPackageService — Checksum
# ---------------------------------------------------------------------------


class TestPermissionPackageServiceChecksum:

    def test_calculate_checksum(self):
        svc = PermissionPackageService(MagicMock())
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path = f.name
        try:
            cs = svc._calculate_checksum(path)
            assert cs.startswith("sha256:")
            expected = hashlib.sha256(b"hello world").hexdigest()
            assert cs == f"sha256:{expected}"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 4b. PermissionPackageService — 辅助方法分支
# ---------------------------------------------------------------------------


class TestPermissionPackageServiceHelpers:
    """覆盖 _resolve_*/_import_user_* 辅助方法分支（内存解密重构后遗漏路径）。"""

    def _make(self):
        db = MagicMock()
        return PermissionPackageService(db), db

    def test_resolve_user_by_id_fallback(self):
        """username 缺失时回退按 user_id 匹配（覆盖 768-769）。"""
        svc, db = self._make()
        user = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        assert svc._resolve_user_by_username_or_id(None, 5) is user

    def test_resolve_user_returns_none_when_no_key(self):
        """username 与 user_id 均缺失 → 无法匹配，返回 None（覆盖 770）。"""
        svc, db = self._make()
        assert svc._resolve_user_by_username_or_id(None, None) is None
        db.query.assert_not_called()

    def test_import_user_roles_skips_when_role_id_none(self):
        """角色无法解析（new_role_id=None）→ 跳过计数（覆盖 741-742）。"""
        svc, db = self._make()
        user = MagicMock()
        user.id = 1
        # first() 序列：1) 解析用户→user  2) 解析角色 exists→None
        db.query.return_value.filter.return_value.first.side_effect = [user, None]
        stats = svc._init_import_stats()
        errors = []
        ur_data = [{"username": "alice", "user_id": None, "role_id": None, "role_name": None}]
        stats, errors = svc._import_user_roles(ur_data, {}, stats, errors)
        assert stats["user_roles_skipped"] == 1
        assert errors == []

    def test_resolve_role_id_by_name(self):
        """role_id_map 未命中时按 role_name 匹配角色（覆盖 780-785）。"""
        svc, db = self._make()
        by_name = MagicMock()
        by_name.id = 55
        db.query.return_value.filter.return_value.first.return_value = by_name
        result = svc._resolve_role_id({"role_id": "old-x", "role_name": "editor"}, {})
        assert result == 55

    def test_import_user_menus_merge_union(self):
        """merge 模式菜单取并集，不丢目标机已有项（覆盖 830-841）。"""
        svc, db = self._make()
        user = MagicMock()
        user.allowed_menus = '["m1","m2"]'
        db.query.return_value.filter.return_value.first.return_value = user
        stats = svc._init_import_stats()
        errors = []
        menu_data = [{"username": "alice", "allowed_menus": ["m2", "m3"]}]
        stats, errors = svc._import_user_menus(menu_data, stats, errors, merge_mode=True)
        assert stats["user_menus_updated"] == 1
        assert json.loads(user.allowed_menus) == ["m1", "m2", "m3"]

    def test_import_user_menus_merge_invalid_existing_json(self):
        """merge 模式既有菜单非法 JSON → 视为空集（覆盖 838-839）。"""
        svc, db = self._make()
        user = MagicMock()
        user.allowed_menus = "not-json{{{"
        db.query.return_value.filter.return_value.first.return_value = user
        stats = svc._init_import_stats()
        errors = []
        menu_data = [{"username": "alice", "allowed_menus": ["m9"]}]
        stats, errors = svc._import_user_menus(menu_data, stats, errors, merge_mode=True)
        assert json.loads(user.allowed_menus) == ["m9"]

    def test_import_user_legacy_org_matched_by_code(self):
        """遗留字段：按组织编码匹配恢复归属（覆盖 880-884/892-893）。"""
        svc, db = self._make()
        user = MagicMock()
        user.organization_id = None
        org = MagicMock()
        org.id = 9
        # first() 序列：1) 用户→user  2) 组织(按 code)→org
        db.query.return_value.filter.return_value.first.side_effect = [user, org]
        stats = svc._init_import_stats()
        errors = []
        legacy = [{
            "username": "alice", "role": "admin", "permissions": "",
            "data_scope": "org", "is_superuser": False,
            "organization_id": 3, "organization_code": "ORG-3",
        }]
        stats, errors = svc._import_user_legacy(legacy, stats, errors, merge_mode=False)
        assert user.organization_id == 9

    def test_import_user_legacy_merge_keeps_org_when_unmatched(self):
        """merge 模式包内无匹配组织 → 保留目标机原归属（覆盖 894-895）。"""
        svc, db = self._make()
        user = MagicMock()
        user.organization_id = 7
        user.permissions = "existing"
        user.data_scope = "all"
        user.role = "admin"
        # first() 序列：1) 用户→user  2) 组织(按 code)→None  3) 组织(按 id)→None
        db.query.return_value.filter.return_value.first.side_effect = [user, None, None]
        stats = svc._init_import_stats()
        errors = []
        legacy = [{
            "username": "alice", "organization_id": 3, "organization_code": "ORG-3",
        }]
        stats, errors = svc._import_user_legacy(legacy, stats, errors, merge_mode=True)
        assert user.organization_id == 7


# ---------------------------------------------------------------------------
# 5. QueryAnalyzer
# ---------------------------------------------------------------------------


class TestQueryAnalyzer:

    def test_log_slow_query_basic(self):
        qa = QueryAnalyzer()
        qa.log_slow_query("SELECT 1", 100.0, params={"a": 1}, explain_plan="SCAN")
        assert len(qa._slow_queries) == 1
        assert qa._slow_queries[0]["duration_ms"] == 100.0

    def test_log_slow_query_truncates_long_query(self):
        qa = QueryAnalyzer()
        long_q = "SELECT " + "a" * 600
        qa.log_slow_query(long_q, 50.0)
        assert len(qa._slow_queries[0]["query"]) == 500

    def test_log_slow_query_trims_list(self):
        qa = QueryAnalyzer()
        qa._max_slow_queries = 5
        for i in range(10):
            qa.log_slow_query(f"q{i}", float(i))
        assert len(qa._slow_queries) == 5

    def test_get_slow_queries_empty(self):
        qa = QueryAnalyzer()
        assert qa.get_slow_queries() == []

    def test_get_slow_queries_with_min_duration(self):
        qa = QueryAnalyzer()
        qa.log_slow_query("q1", 50.0)
        qa.log_slow_query("q2", 200.0)
        qa.log_slow_query("q3", 300.0)
        result = qa.get_slow_queries(min_duration_ms=100.0)
        assert len(result) == 2

    def test_get_slow_queries_limit(self):
        qa = QueryAnalyzer()
        for i in range(10):
            qa.log_slow_query(f"q{i}", float(i))
        assert len(qa.get_slow_queries(limit=3)) == 3

    def test_get_query_stats_empty(self):
        qa = QueryAnalyzer()
        stats = qa.get_query_stats()
        assert stats["total_slow_queries"] == 0

    def test_get_query_stats_with_data(self):
        qa = QueryAnalyzer()
        for v in [10.0, 20.0, 30.0]:
            qa.log_slow_query("q", v)
        stats = qa.get_query_stats()
        assert stats["total_slow_queries"] == 3
        assert stats["avg_duration_ms"] == 20.0
        assert stats["max_duration_ms"] == 30.0
        assert stats["min_duration_ms"] == 10.0
        assert "p50_duration_ms" in stats
        assert "p95_duration_ms" in stats
        assert "p99_duration_ms" in stats

    def test_calculate_percentile_empty(self):
        qa = QueryAnalyzer()
        assert qa._calculate_percentile([], 50) == 0.0

    def test_calculate_percentile_single(self):
        qa = QueryAnalyzer()
        assert qa._calculate_percentile([5.0], 50) == 5.0

    def test_calculate_percentile_index_clamp(self):
        qa = QueryAnalyzer()
        result = qa._calculate_percentile([1.0, 2.0, 3.0], 99)
        assert isinstance(result, float)

    def test_detect_n_plus_one_first_call(self):
        qa = QueryAnalyzer()
        qa.detect_n_plus_one("SELECT * FROM users WHERE id = 1", "ctx")
        cache_key = "ctx:" + qa._get_query_signature("SELECT * FROM users WHERE id = 1")
        assert cache_key in qa._n_plus_one_cache

    def test_detect_n_plus_one_repeated(self):
        qa = QueryAnalyzer()
        for _ in range(7):
            qa.detect_n_plus_one("SELECT * FROM users WHERE id = 1", "ctx")
        count_key = None
        for k in qa._n_plus_one_cache:
            if k.endswith("_count"):
                count_key = k
                break
        if count_key:
            assert qa._n_plus_one_cache[count_key] >= 1

    def test_detect_n_plus_one_expires_old(self):
        qa = QueryAnalyzer()
        qa._n_plus_one_cache["old_key"] = time.time() - 5.0
        qa._n_plus_one_cache["old_key_count"] = 3
        qa.detect_n_plus_one("SELECT 1", "ctx")
        assert "old_key" not in qa._n_plus_one_cache

    def test_get_query_signature(self):
        qa = QueryAnalyzer()
        sig = qa._get_query_signature("SELECT * FROM users WHERE id = 123 AND name = 'abc'")
        assert "?" in sig

    def test_clear_slow_queries(self):
        qa = QueryAnalyzer()
        qa.log_slow_query("q", 10.0)
        qa.clear_slow_queries()
        assert len(qa._slow_queries) == 0

    def test_analyze_query_plan_success(self):
        qa = QueryAnalyzer()
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(["(0,0,SCAN TABLE users)"]))
        db.execute.return_value = mock_result
        plan = qa.analyze_query_plan(db, "SELECT * FROM users")
        assert plan is not None
        assert "SCAN" in plan

    def test_analyze_query_plan_exception(self):
        qa = QueryAnalyzer()
        db = MagicMock()
        db.execute.side_effect = Exception("error")
        plan = qa.analyze_query_plan(db, "bad query")
        assert plan is None


# ---------------------------------------------------------------------------
# 6. RuralWorkService
# ---------------------------------------------------------------------------


class TestRuralWorkService:

    def _make(self):
        db = MagicMock()
        return RuralWorkService(db), db

    def test_get_rural_works_empty(self):
        svc, db = self._make()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        q.count.return_value = 0
        db.query.return_value = q
        items, total = svc.get_rural_works()
        assert items == []
        assert total == 0

    def test_get_rural_works_with_filters(self):
        svc, db = self._make()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.count.return_value = 0
        q.all.return_value = []
        db.query.return_value = q
        items, total = svc.get_rural_works(
            status="active", type="infrastructure", village_id=1,
            search="test", start_date="2025-01-01", end_date="2025-12-31",
            year=2025, order_by="name", order_desc=False
        )
        assert items == []

    def test_get_rural_works_invalid_dates(self):
        svc, db = self._make()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.count.return_value = 0
        q.all.return_value = []
        db.query.return_value = q
        items, total = svc.get_rural_works(start_date="not-a-date", end_date="bad")
        assert items == []

    def test_get_rural_works_with_rows(self):
        svc, db = self._make()
        row = MagicMock()
        row.id = 1
        row.code = "RW-001"
        row.name = "Test Work"
        row.type = MagicMock(value="infrastructure")
        row.status = MagicMock(value="in_progress")
        row.village_id = 10
        row.responsible_person = "Alice"
        row.contact_phone = "123"
        row.start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        row.end_date = datetime(2025, 6, 1, tzinfo=timezone.utc)
        row.description = "desc"
        row.target = "target"
        row.progress = 50
        row.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        row.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)

        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.count.return_value = 1
        q.all.return_value = [row]
        db.query.return_value = q
        items, total = svc.get_rural_works()
        assert total == 1
        assert items[0]["name"] == "Test Work"

    def test_get_rural_works_none_dates(self):
        svc, db = self._make()
        row = MagicMock()
        row.id = 1
        row.code = "RW-002"
        row.name = "No Dates"
        row.type = None
        row.status = None
        row.village_id = None
        row.responsible_person = None
        row.contact_phone = None
        row.start_date = None
        row.end_date = None
        row.description = None
        row.target = None
        row.progress = 0
        row.created_at = None
        row.updated_at = None

        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.count.return_value = 1
        q.all.return_value = [row]
        db.query.return_value = q
        items, _ = svc.get_rural_works()
        assert items[0]["start_date"] is None

    def test_get_by_id_found(self):
        svc, db = self._make()
        work = MagicMock()
        work.id = 1
        work.code = "RW-001"
        work.name = "Test"
        work.type = None
        work.status = None
        work.village_id = 1
        db.query.return_value.filter.return_value.first.return_value = work
        result = svc.get_rural_work_by_id(1)
        assert result is not None
        assert result["id"] == 1

    def test_get_by_id_not_found(self):
        svc, db = self._make()
        db.query.return_value.filter.return_value.first.return_value = None
        assert svc.get_rural_work_by_id(999) is None

    def test_delete_found(self):
        svc, db = self._make()
        work = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = work
        assert svc.delete_rural_work(1) is True
        db.delete.assert_called_once_with(work)
        db.commit.assert_called_once()

    def test_delete_not_found(self):
        svc, db = self._make()
        db.query.return_value.filter.return_value.first.return_value = None
        assert svc.delete_rural_work(999) is False

    def test_update_found(self):
        svc, db = self._make()
        work = MagicMock()
        work.id = 1
        work.code = "RW-001"
        work.name = "Test"
        work.type = None
        work.status = None
        work.village_id = 1
        db.query.return_value.filter.return_value.first.return_value = work
        svc.update_rural_work(1, name="Updated", nonexistent_field="x")
        assert work.name == "Updated"
        db.commit.assert_called_once()

    def test_update_not_found(self):
        svc, db = self._make()
        db.query.return_value.filter.return_value.first.return_value = None
        assert svc.update_rural_work(999) is None

    def test_generate_code(self):
        code = RuralWorkService._generate_code()
        assert code.startswith("RW-")
        assert len(code) == 11


class TestRuralWorkHelpers:

    def test_iso_none(self):
        assert _iso(None) is None

    def test_iso_value(self):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert _iso(dt) == dt.isoformat()

    def test_safe_enum_value_with_value(self):
        val = MagicMock()
        val.value = "enum_val"
        assert _safe_enum_value(val) == "enum_val"

    def test_safe_enum_value_without_value(self):
        assert _safe_enum_value("plain") == "plain"

    def test_safe_enum_value_none(self):
        assert _safe_enum_value(None) is None


# ---------------------------------------------------------------------------
# 7. UpdateLogService
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 8. OrganizationCodeService
# ---------------------------------------------------------------------------


class TestOrganizationCodeService:

    def test_generate_code(self):
        svc = OrganizationCodeService()
        code = svc.generate_code("TestOrg")
        assert len(code) >= 8
        assert code.isalnum()

    def test_generate_code_with_parent(self):
        svc = OrganizationCodeService()
        code = svc.generate_code("Child", parent_code="PARENT1")
        assert len(code) >= 8

    def test_generate_code_collision_resolution(self):
        svc = OrganizationCodeService()
        code = svc.generate_code("Org1")
        svc._codes[code] = {"info": "first"}
        code2 = svc.generate_code("Org1")
        assert code2 != code or len(code2) > len(code)

    def test_validate_code_valid(self):
        svc = OrganizationCodeService()
        assert svc.validate_code("ABCD1234") is True

    def test_validate_code_too_short(self):
        svc = OrganizationCodeService()
        assert svc.validate_code("AB") is False

    def test_validate_code_non_alnum(self):
        svc = OrganizationCodeService()
        assert svc.validate_code("ABCD-EFGH") is False

    def test_get_code_info_found(self):
        svc = OrganizationCodeService()
        svc._codes["X1"] = {"name": "test"}
        assert svc.get_code_info("X1") == {"name": "test"}

    def test_get_code_info_not_found(self):
        svc = OrganizationCodeService()
        assert svc.get_code_info("NONE") is None

    def test_register_code(self):
        svc = OrganizationCodeService()
        svc.register_code("C1", {"name": "org"})
        assert svc._codes["C1"] == {"name": "org"}

    def test_init_with_db(self):
        db = MagicMock()
        svc = OrganizationCodeService(db)
        assert svc.db is db


# ---------------------------------------------------------------------------
# 11. EncryptedPackage
# ---------------------------------------------------------------------------


class TestEncryptedPackage:

    def test_derive_key(self):
        key = _derive_key("testpass", b"0" * 16)
        assert len(key) == 32

    def test_create_and_extract_roundtrip(self):
        data = {"key": "value", "numbers": [1, 2, 3]}
        with tempfile.NamedTemporaryFile(suffix=".rrs", delete=False) as f:
            path = f.name
        try:
            create_encrypted_package(data, path, "mypassword")
            assert os.path.exists(path)
            result = extract_encrypted_package(path, "mypassword")
            assert result == data
        finally:
            os.unlink(path)

    def test_extract_wrong_password(self):
        with tempfile.NamedTemporaryFile(suffix=".rrs", delete=False) as f:
            path = f.name
        try:
            create_encrypted_package({"a": 1}, path, "correct")
            with pytest.raises(ValueError, match="解密失败"):
                extract_encrypted_package(path, "wrong")
        finally:
            os.unlink(path)

    def test_extract_bad_magic(self):
        with tempfile.NamedTemporaryFile(suffix=".rrs", delete=False) as f:
            f.write(b"XXXX")
            path = f.name
        try:
            with pytest.raises(ValueError, match="无效的文件格式"):
                extract_encrypted_package(path, "pass")
        finally:
            os.unlink(path)

    def test_extract_bad_version(self):
        with tempfile.NamedTemporaryFile(suffix=".rrs", delete=False) as f:
            f.write(MAGIC + b"2.0" + b"\x00" * 16)
            path = f.name
        try:
            with pytest.raises(ValueError, match="不支持的版本"):
                extract_encrypted_package(path, "pass")
        finally:
            os.unlink(path)

    def test_extract_truncated_data(self):
        with tempfile.NamedTemporaryFile(suffix=".rrs", delete=False) as f:
            f.write(MAGIC + VERSION + b"\x00" * 16 + struct.pack(">I", 10) + b"\x00" * 5)
            path = f.name
        try:
            with pytest.raises(ValueError, match="数据包损坏"):
                extract_encrypted_package(path, "pass")
        finally:
            os.unlink(path)

    def test_extract_tampered_checksum(self):
        with tempfile.NamedTemporaryFile(suffix=".rrs", delete=False) as f:
            path = f.name
        try:
            create_encrypted_package({"a": 1}, path, "pass")
            with open(path, "rb") as f:
                data = bytearray(f.read())
            data[-1] ^= 0xFF
            with open(path, "wb") as f:
                f.write(data)
            with pytest.raises(ValueError, match="完整性校验失败"):
                extract_encrypted_package(path, "pass")
        finally:
            os.unlink(path)
