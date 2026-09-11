# -*- coding: utf-8 -*-
"""安全加固越权测试: 普通用户访问敏感端点必须 403"""
import asyncio
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.core.permission_utils import require_admin, is_admin
from tests.unit._sec_helpers import _read


class _RoleUser:
    def __init__(self, role, uid=1):
        self.role = role
        self.id = uid
        self.username = f"user_{uid}"
        self.name = "测试用户"
        self.is_superuser = False


def _run_admin(user):
    try:
        require_admin(user, error_message="仅管理员可操作")
        return True
    except HTTPException as e:
        assert e.status_code == 403
        return False


class TestRequireAdmin:
    def test_admin_allowed(self):
        assert _run_admin(_RoleUser("admin"))

    def test_super_admin_allowed(self):
        assert _run_admin(_RoleUser("super_admin"))

    def test_normal_user_blocked(self):
        assert not _run_admin(_RoleUser("user"))

    def test_viewer_blocked(self):
        assert not _run_admin(_RoleUser("viewer"))

    def test_none_blocked(self):
        # require_admin(None) 装饰器模式直接调用不适用 —— 用 is_admin 兜底
        assert not is_admin(None)
        assert not _run_admin(_RoleUser("role_unknown"))

    def test_decorator_mode(self):
        @require_admin
        async def endpoint(current_user=None):
            return "ok"

        async def check():
            assert await endpoint(current_user=_RoleUser("admin")) == "ok"
            with pytest.raises(HTTPException):
                await endpoint(current_user=_RoleUser("user"))

        asyncio.run(check())

    def test_direct_call_returns_none(self):
        assert require_admin(_RoleUser("admin"), error_message="x") is None


class TestIsAdmin:
    def test_roles(self):
        assert is_admin(_RoleUser("admin"))
        assert is_admin(_RoleUser("super_admin"))
        assert not is_admin(_RoleUser("user"))
        assert not is_admin(_RoleUser("viewer"))
        assert not is_admin(None)


class TestSensitiveTableGuard:
    def test_sensitive_tables_defined(self):
        from app.services.data_sync_service import _SENSITIVE_TABLES, DataSyncService

        assert "users" in _SENSITIVE_TABLES
        assert "machine_codes" in _SENSITIVE_TABLES
        assert "audit_logs" in _SENSITIVE_TABLES
        svc = DataSyncService()
        for t in _SENSITIVE_TABLES:
            assert t not in svc.syncable_tables

    def test_syncable_tables_are_business_only(self):
        from app.services.data_sync_service import DataSyncService

        svc = DataSyncService()
        for t in svc.syncable_tables:
            assert t not in ("users", "machine_codes", "audit_logs")


class TestFilesSecurity:
    def test_svg_removed_from_allowed(self):
        from app.api.v1.files import _ALLOWED_EXTS

        all_exts = set()
        for exts in _ALLOWED_EXTS.values():
            all_exts |= exts
        assert "svg" not in all_exts

    def test_magic_check_rejects_fake_png(self):
        from app.api.v1.files import upload_file

        with pytest.raises(HTTPException) as ei:
            f = MagicMock()
            f.filename = "x.png"

            # 忠实模拟 UploadFile.read(size)：分块返回，读到 EOF 返回空。
            # （R26 起上传改为 8MB 分块流式落盘，read 会带 size 参数且需在
            #   数据耗尽后返回 b""，否则会一直读到超限。）
            _chunks = [b"<script>alert(1)</script>", b""]

            async def fake_read(size=-1):
                return _chunks.pop(0) if _chunks else b""

            f.read = fake_read

            async def call():
                await upload_file(file=f, category=None, current_user=_RoleUser("admin"))

            asyncio.run(call())
        assert ei.value.status_code == 400


class TestBackupDownloadGuard:
    def test_download_requires_admin_source(self):
        src = _read("backend/app/api/v1/system/backup.py")
        idx = src.find('@router.get("/download/{filename}"')
        assert idx > 0
        assert "require_admin" in src[idx : idx + 900]


class TestDataSyncGuard:
    def test_all_write_endpoints_have_require_admin(self):
        src = _read("backend/app/api/v1/data_sync.py")
        for ep in (
            '@router.post("/export")',
            '@router.post("/export-encrypted")',
            '@router.post("/import")',
            '@router.post("/import-encrypted")',
            '@router.post("/resolve-conflict")',
        ):
            idx = src.find(ep)
            assert idx > 0, f"端点缺失 {ep}"
            assert "require_admin" in src[idx : idx + 1600], f"端点缺少权限校验 {ep}"


class TestApprovalGuard:
    def test_auto_approve_requires_admin(self):
        src = _read("backend/app/api/v1/approval.py")
        for ep in ('/submit-auto', '/tasks/auto-approve', '/tasks/auto-approve-all'):
            idx = src.find(ep)
            assert idx > 0, f"端点缺失 {ep}"
            assert "require_admin" in src[idx : idx + 1800], f"端点缺少权限校验 {ep}"


class TestSystemHealthGuard:
    def test_maintenance_endpoints_require_admin(self):
        src = _read("backend/app/api/v1/system_health.py")
        for ep in ("/integrity-check", "/wal-checkpoint", "/vacuum"):
            idx = src.find(ep)
            assert idx > 0, f"端点缺失 {ep}"
            assert "require_admin" in src[idx : idx + 1400], f"端点缺少权限校验 {ep}"


class TestPermissionPackageGuard:
    def test_path_traversal_blocked(self):
        src = _read("backend/app/api/v1/permission_package.py")
        idx = src.find('@router.get("/download/')
        assert idx > 0
        chunk = src[idx : idx + 1800]
        assert "os.path.basename" in chunk
        assert "realpath" in chunk


class TestErrorReportGuard:
    def test_owner_check_present(self):
        src = _read("backend/app/api/v1/system/error_report.py")
        idx = src.find('@router.put("/{report_id}"')
        assert idx > 0
        chunk = src[idx : idx + 1200]
        assert "无权修改" in chunk or "is_owner" in chunk


class TestDashboardActivityGuard:
    def test_owner_check_present(self):
        src = _read("backend/app/api/v1/data/data/dashboard.py")
        for ep in ('@router.put("/recent-activities/{activity_id}")', '@router.delete("/recent-activities/{activity_id}")'):
            idx = src.find(ep)
            assert idx > 0
            chunk = src[idx : idx + 1500]
            assert "无权" in chunk or "is_admin" in chunk


class TestUserExportGuard:
    def test_users_export_requires_admin(self):
        src = _read("backend/app/api/v1/import_export/export.py")
        idx = src.find('@router.get("/users")')
        assert idx > 0
        assert "require_admin" in src[idx : idx + 600]


class TestConfigPackageExportGuard:
    def test_export_requires_admin(self):
        src = _read("backend/app/api/v1/system/config_package.py")
        idx = src.find('@router.post("/export"')
        assert idx > 0
        assert "require_admin" in src[idx : idx + 900]


class TestDataSyncSinceSql:
    def test_since_query_is_fstring(self):
        src = _read("backend/app/services/data_sync_service.py")
        idx = src.find("WHERE updated_at > :since OR created_at > :since")
        assert idx > 0
        prefix = src[max(0, idx - 200) : idx]
        assert "text(f" in prefix


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
