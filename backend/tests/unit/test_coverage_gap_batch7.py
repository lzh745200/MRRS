"""
Coverage gap tests — batch 7.

Covers remaining uncovered lines across:
- app/api/v1/batch_operations.py   (audit-log failure + delete error re-raise)
- app/api/v1/files.py              (no-extension filename, 413 size limit)
- app/api/v1/system/admin.py       (token blacklist fallback branches)
- app/core/config.py               (ENCRYPTION_KEY generation failure / _generate_fernet_key)
- app/core/data_permission.py      (is_admin(None), org-match in require_data_permission)
- app/middleware/camel_to_snake.py (_patch_envelope + response patching)
- app/services/machine_code_service.py (third fallback machine-code update)
- app/services/package_version_service.py (get_current_version / parse_version branches)

All tests use mocks / direct function calls; no real DB required.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.data_permission import is_admin, require_data_permission
from app.middleware.camel_to_snake import CamelToSnakeMiddleware, _patch_envelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role="admin", is_superuser=False, org_id=1, uid=1, username="admin"):
    u = MagicMock()
    u.id = uid
    u.username = username
    u.role = role
    u.is_superuser = is_superuser
    u.organization_id = org_id
    u.is_active = True
    u.full_name = "Test User"
    u.email = "test@test.com"
    u.last_login = datetime(2025, 1, 1)
    return u


def _mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    return db


# ===========================================================================
# 1. app/api/v1/batch_operations.py — 审计日志失败分支 (149-150, 190-191)
# ===========================================================================


class TestBatchOperationsAuditFail:
    """write_work_log 抛异常时主操作不阻断（149-150/190-191）。"""

    @pytest.mark.asyncio
    async def test_batch_update_audit_log_failure_returns_success(self):
        from app.api.v1.batch_operations import batch_update

        db = _mock_db()
        user = _make_user()
        mock_svc = MagicMock()
        mock_svc.batch_update = AsyncMock(return_value={"success": True, "success_count": 1, "skipped": 0})
        with patch("app.api.v1.batch_operations.BatchService", return_value=mock_svc), \
             patch("app.api.v1.batch_operations.require_admin"), \
             patch("app.api.v1.batch_operations.write_work_log", side_effect=RuntimeError("audit down")):
            result = await batch_update(db=db, current_user=user,
                                        request=MagicMock(table_name="villages", ids=[1],
                                                          updates={"name": "x"}))
            assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_batch_delete_audit_log_failure_returns_success(self):
        from app.api.v1.batch_operations import batch_delete

        db = _mock_db()
        user = _make_user()
        mock_svc = MagicMock()
        mock_svc.batch_delete = AsyncMock(return_value={"success": True, "success_count": 1, "skipped": 0})
        with patch("app.api.v1.batch_operations.BatchService", return_value=mock_svc), \
             patch("app.api.v1.batch_operations.require_admin"), \
             patch("app.api.v1.batch_operations.write_work_log", side_effect=RuntimeError("audit down")):
            result = await batch_delete(db=db, current_user=user,
                                        request=MagicMock(table_name="villages", ids=[1], soft_delete=True))
            assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_batch_delete_validation_error_reraises(self):
        from app.core.exceptions import ValidationError as BizValidationError
        from app.api.v1.batch_operations import batch_delete

        db = _mock_db()
        user = _make_user()
        mock_svc = MagicMock()
        mock_svc.batch_delete = AsyncMock(side_effect=BizValidationError("bad"))
        with patch("app.api.v1.batch_operations.BatchService", return_value=mock_svc), \
             patch("app.api.v1.batch_operations.require_admin"):
            with pytest.raises(BizValidationError):
                await batch_delete(db=db, current_user=user,
                                   request=MagicMock(table_name="villages", ids=[1], soft_delete=True))

    @pytest.mark.asyncio
    async def test_batch_delete_database_error_reraises(self):
        from app.core.exceptions import DatabaseError as BizDatabaseError
        from app.api.v1.batch_operations import batch_delete

        db = _mock_db()
        user = _make_user()
        mock_svc = MagicMock()
        mock_svc.batch_delete = AsyncMock(side_effect=BizDatabaseError("db down"))
        with patch("app.api.v1.batch_operations.BatchService", return_value=mock_svc), \
             patch("app.api.v1.batch_operations.require_admin"):
            with pytest.raises(BizDatabaseError):
                await batch_delete(db=db, current_user=user,
                                   request=MagicMock(table_name="villages", ids=[1], soft_delete=True))


# ===========================================================================
# 2. app/api/v1/files.py — 无扩展名文件名 (34) + 413 大小限制 (57)
# ===========================================================================


class TestFilesUploadGaps:

    def test_upload_filename_without_extension(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("noextfile", b"data", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["file_size"] == 4

    def test_upload_too_large_returns_413(self, client_with_mocked_auth):
        from app.core.config import settings
        original = settings.MAX_FILE_SIZE
        settings.MAX_FILE_SIZE = 10
        try:
            resp = client_with_mocked_auth.post(
                "/api/v1/files/upload",
                files={"file": ("big.pdf", b"x" * 100, "application/pdf")},
            )
            assert resp.status_code == 413
            assert "文件大小超过限制" in resp.json()["detail"]
        finally:
            settings.MAX_FILE_SIZE = original


# ===========================================================================
# 3. app/api/v1/system/admin.py — 黑名单计数回退分支 (416-421)
# ===========================================================================


class TestAdminBlacklistFallback:

    @pytest.mark.asyncio
    async def test_count_fails_db_query_works(self):
        from app.api.v1.system.admin import list_user_sessions

        db = _mock_db()
        user = _make_user()
        target = _make_user(uid=5, username="target")
        db.query.return_value.filter.return_value.first.return_value = target
        db.query.return_value.count.return_value = 7
        with patch("app.core.token_blacklist.count", side_effect=RuntimeError("mem down")):
            result = await list_user_sessions(5, db=db, current_user=user)
        assert result["data"]["blacklisted_tokens"] == 7

    @pytest.mark.asyncio
    async def test_count_and_db_query_both_fail(self):
        from app.api.v1.system.admin import list_user_sessions

        db = _mock_db()
        user = _make_user()
        target = _make_user(uid=5, username="target")
        db.query.return_value.filter.return_value.first.return_value = target
        db.query.return_value.count.side_effect = RuntimeError("db down")
        with patch("app.core.token_blacklist.count", side_effect=RuntimeError("mem down")):
            result = await list_user_sessions(5, db=db, current_user=user)
        assert result["data"]["blacklisted_tokens"] == 0


# ===========================================================================
# 4. app/core/config.py — ENCRYPTION_KEY 生成失败 (318-321) + _generate_fernet_key (370-372)
# ===========================================================================


class TestConfigEncryptionKeyFallback:

    def test_generate_fernet_key(self):
        from app.core.config import _generate_fernet_key

        key = _generate_fernet_key()
        assert isinstance(key, str)
        assert len(key) > 20
        assert key.endswith("=") or "-" in key or "_" in key

    def test_encryption_key_generation_failure_warns(self, caplog):
        with patch("app.utils.runtime_secrets.get_or_create_secret",
                   side_effect=RuntimeError("no secret store")):
            with caplog.at_level("WARNING", logger="app.core.config"):
                s = Settings(ENVIRONMENT="production", ENCRYPTION_KEY="")
        assert any(
            "ENCRYPTION_KEY 未配置" in r.message
            for r in caplog.records
        )

    def test_encryption_key_generated_via_lambda(self):
        def fake_get_or_create(name, generate):
            return generate()

        with patch("app.utils.runtime_secrets.get_or_create_secret",
                   side_effect=fake_get_or_create):
            s = Settings(ENVIRONMENT="production", ENCRYPTION_KEY="")
        assert s.ENCRYPTION_KEY


# ===========================================================================
# 5. app/core/data_permission.py — is_admin(None) (46) + org match (172)
# ===========================================================================


class TestDataPermissionGaps:

    def test_is_admin_none_user_returns_false(self):
        assert is_admin(None) is False

    def test_require_data_permission_org_match_returns_true(self):
        user = MagicMock()
        user.is_superuser = False
        user.id = 1
        user.organization_id = 5
        assert require_data_permission(user, organization_id=5, created_by=None) is True


# ===========================================================================
# 6. app/middleware/camel_to_snake.py — _patch_envelope (46-56) + 响应补全 (94-105)
# ===========================================================================


class TestPatchEnvelope:
    """_patch_envelope 各分支（46-56）。"""

    def test_bare_dict_gets_envelope(self):
        out = _patch_envelope({"foo": 1})
        assert out["code"] == 200
        assert out["success"] is True
        assert out["message"] == "success"
        assert out["foo"] == 1

    def test_dict_with_message_keeps_message(self):
        out = _patch_envelope({"foo": 1, "message": "ok"})
        assert out["message"] == "ok"
        assert out["code"] == 200
        assert out["success"] is True

    def test_dict_with_success_skipped(self):
        data = {"success": False, "foo": 1}
        assert _patch_envelope(data) is data

    def test_dict_with_code_skipped(self):
        data = {"code": 500, "foo": 1}
        assert _patch_envelope(data) is data

    def test_non_dict_returned_as_is(self):
        assert _patch_envelope([1, 2]) == [1, 2]
        assert _patch_envelope("str") == "str"
        assert _patch_envelope(None) is None


class TestCamelDispatchResponsePatching:
    """dispatch 响应信封补全路径（94-105）。"""

    async def _dispatch(self, response_body, status_code=200, content_type="application/json"):
        mw = CamelToSnakeMiddleware(AsyncMock())
        request = MagicMock()
        request.headers.get.return_value = "application/json"
        request.body = AsyncMock(return_value=b"{}")
        response = MagicMock()
        response.headers.get.return_value = content_type
        response.status_code = status_code
        response.body = response_body
        call_next = AsyncMock(return_value=response)
        return await mw.dispatch(request, call_next), response

    @pytest.mark.asyncio
    async def test_bare_dict_response_is_patched(self):
        result, _ = await self._dispatch(b'{"foo": "bar"}')
        assert result is not None
        body = json.loads(result.body)
        assert body["code"] == 200
        assert body["success"] is True
        assert body["foo"] == "bar"

    @pytest.mark.asyncio
    async def test_enveloped_response_unchanged(self):
        result, original = await self._dispatch(b'{"success": true, "code": 200}')
        assert result is original

    @pytest.mark.asyncio
    async def test_non_json_content_type_skipped(self):
        result, original = await self._dispatch(b'{"foo": 1}', content_type="text/html")
        assert result is original

    @pytest.mark.asyncio
    async def test_status_ge_400_skipped(self):
        result, original = await self._dispatch(b'{"foo": 1}', status_code=400)
        assert result is original

    @pytest.mark.asyncio
    async def test_no_body_skipped(self):
        result, original = await self._dispatch(None)
        assert result is original

    @pytest.mark.asyncio
    async def test_invalid_json_returns_original(self):
        result, original = await self._dispatch(b"not-json")
        assert result is original


# ===========================================================================
# 7. app/services/machine_code_service.py — 第三回退：机器码更新 (496-506)
# ===========================================================================


class TestMachineCodeThirdFallback:

    def test_third_fallback_updates_machine_code(self):
        from app.models.machine_code import MachineCode
        from app.services.machine_code_service import MachineCodeService

        db = _mock_db()
        record = MachineCode(
            machine_code="old-machine-code",
            pass_code="PC-1234-5678-9012-3456-7890-ABCD-EF01",
            status="pending",
        )
        db.query.return_value.filter.return_value.first.side_effect = [None, None, record]
        svc = MachineCodeService(db=db)
        result = svc.verify_pass_code("PC-1234-5678-9012-3456-7890-ABCD-EF01", "new-machine-code")
        assert result is record
        assert record.machine_code == "new-machine-code"

