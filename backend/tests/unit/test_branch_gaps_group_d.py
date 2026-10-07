# -*- coding: utf-8 -*-
"""分支覆盖缺口补充测试（Group D）。

目标：清零以下模块在 coverage.py 分支模式下的 partial branches（A->B 缺失弧）：
- app/api/v1/auth/auth.py, rbac.py, two_factor.py
- app/api/v1/import_export/import_data.py
- app/api/v1/permission_package.py, sentiment.py, validation.py, system/backup.py
- app/core/config.py, logging_config.py, permission_utils.py, transaction.py
- app/main.py, app/middleware/csrf_middleware.py, app/models/base.py
- app/services/ai/recommendation_service.py, backup_scheduler.py, backup_service.py
- app/services/cache_service.py, data_tier_service.py, db_maintenance.py
- app/services/excel_importer_service.py, machine_code_service.py
- app/services/offline_map_service.py, report_export_service.py
- app/services/zero_trust/device_fingerprint.py
- app/utils/audit_logger.py, app/utils/excel_report_style.py

仅直调函数级用例；不修改 app/ 源码。
"""

import asyncio
import hmac
import hashlib
import importlib
import io
import logging
import logging.handlers
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from openpyxl import Workbook
from starlette.datastructures import Headers

from app.api.v1.auth import auth as auth_module
from app.api.v1.auth.auth import (
    LoginRequest,
    TwoFactorLoginVerifyRequest,
    _revoke_request_tokens,
    login,
    two_factor_verify_login,
)
from app.api.v1.auth.rbac import RoleUpdate, update_role
from app.api.v1.auth.two_factor import DisableTwoFactorRequest, _verify_second_factor
from app.api.v1.import_export.import_data import (
    _build_entity_validation_summary,
    _parse_excel_rows,
    _setup_preview_entity,
)
from app.api.v1.permission_package import (
    PermissionPackageConfirmRequest,
    _safe_unlink,
    confirm_import_permission_package,
)
from app.api.v1.sentiment import get_news_list
from app.api.v1.system.backup import BackupScheduleUpdate, delete_backup, update_backup_schedule
from app.api.v1.validation import (
    FIELD_LABELS,
    QueryCheckRequest,
    QueryCondition,
    RuleType,
    ValidationRule,
    query_check,
    validate_data,
)
from app.core.config import Settings
from app.core.logging_config import SafeTimedRotatingFileHandler
from app.core.permission_utils import (
    get_org_with_fallback,
    require_admin,
    require_organization,
    require_permission,
)
from app.core.transaction import _apply_tx_settings, _find_db_session
from app.middleware.csrf_middleware import CSRFMiddleware, sign_csrf_token
from app.models.base import _bump_sync_version_on_bulk_update, _bump_sync_version_on_update, is_datetime_type
from app.services.ai.recommendation_service import RecommendationService
from app.services.backup_scheduler import _auto_package_with_db, chunk_cleanup_job
from app.services.backup_service import BackupIncompleteError, BackupService
from app.services.cache_service import CacheService, cache_result
from app.services.data_tier_service import DataTierService
from app.services.db_maintenance import _run_wal_checkpoint
from app.services.excel_importer_service import (
    ExcelImporterService,
    ImportMode,
    ImportResult,
)
from app.services.machine_code_service import MachineCodeService
from app.services.offline_map_service import OfflineMapService
from app.services.report_export_service import ReportExportService
from app.services.zero_trust.device_fingerprint import (
    DeviceFingerprint,
    DeviceFingerprintService,
)
from app.utils.audit_logger import AuditLogger
from app.utils.excel_report_style import autofit_widths, build_report_sheet


def _make_user(**kwargs):
    """构造一个属性齐全的登录用户对象（与既有 auth 测试口径一致）。"""
    user = SimpleNamespace(
        id=1,
        username="testuser",
        email="t@example.com",
        full_name="Test User",
        role="user",
        is_active=True,
        is_superuser=False,
        organization_id=None,
        organization_name="",
        permissions_list=[],
        allowed_menus=None,
        allowed_menus_list=None,
        failed_login_count=0,
        locked_until=None,
        must_change_password=False,
        password_changed_at=None,
        last_login=None,
        token_version_safe=1,
        hashed_password="hashed",
    )
    for k, v in kwargs.items():
        setattr(user, k, v)
    return user


def _patch_login_pipeline(user):
    """login/two_factor_verify_login 共用的打补丁上下文。"""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch("app.api.v1.auth.auth.check_rate_limit", new_callable=AsyncMock, return_value=True))
    stack.enter_context(patch("app.api.v1.auth.auth.get_client_ip", return_value="127.0.0.1"))
    stack.enter_context(patch("app.api.v1.auth.auth.AuditLogger"))
    token_manager = stack.enter_context(patch("app.api.v1.auth.auth.token_manager"))
    token_manager.decode_token.return_value = {"two_factor_pending": True, "sub": user.username}
    token_manager.create_token_pair.return_value = {"access_token": "at1", "refresh_token": "rt1"}
    if user is not None:
        svc = MagicMock()
        svc.get_user_by_username.return_value = user
        stack.enter_context(patch("app.api.v1.auth.auth.UserService", return_value=svc))
    return stack


class TestAuthLoginBranches:
    """auth.py 305->309（密码未过期分支）。"""

    def test_login_password_not_expired(self, client):
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        user = _make_user(password_changed_at=recent, must_change_password=False)
        with _patch_login_pipeline(user):
            with patch("app.api.v1.auth.auth.verify_password", return_value=True):
                with patch("app.services.machine_code_service.MachineCodeService") as mc:
                    inst = mc.return_value
                    inst.get_machine_code.return_value = "mcode"
                    inst.verify_user_machine.return_value = True
                    resp = client.post(
                        "/api/v1/auth/login",
                        json={"username": "testuser", "password": "testpass"},
                    )
        assert resp.status_code == 200
        body = resp.json()
        # 未过期 → 不强制改密、提示登录成功
        assert body["must_change_password"] is False
        assert body["message"] == "登录成功"

    def test_two_factor_login_recent_aware_password_ts(self, client):
        """two_factor_verify_login 474->476（tz-aware）与 476->480（未过期）。"""
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        user = _make_user(password_changed_at=recent, must_change_password=False)
        with _patch_login_pipeline(user):
            with patch(
                "app.services.two_factor_service.TwoFactorService.verify_login",
                return_value=True,
            ):
                resp = client.post(
                    "/api/v1/auth/two-factor/verify-login",
                    json={"temp_token": "tok", "code": "123456"},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["must_change_password"] is False
        assert body["message"] == "登录成功"

    async def test_revoke_request_tokens_without_refresh(self):
        """auth.py 618->exit：body 为 dict 但无有效 refresh_token。"""
        request = MagicMock()
        request.json = AsyncMock(return_value={"refresh_token": None})
        with patch("app.api.v1.auth.auth.token_manager") as tm:
            await _revoke_request_tokens(request, None)
            tm.revoke_token.assert_not_called()


class TestRbacUpdateRoleBranches:
    """rbac.py 221->223 / 223->225 / 225->229 / 229->236（全 None 更新）。"""

    async def test_update_role_with_all_none_fields(self):
        role = SimpleNamespace(id="r1", name="RoleA", description="d", is_active=True)
        sess = MagicMock()
        sess.query.return_value.filter.return_value.first.return_value = role
        with patch("app.api.v1.auth.rbac.TransactionManager") as tm:
            tm.transaction.return_value.__enter__.return_value = sess
            resp = await update_role(
                role_id="r1",
                role_data=RoleUpdate(name=None, description=None, is_active=None, permissions=None),
                db=None,
                current_user=None,
            )
        # 字段全 None → 角色原样保留
        assert role.name == "RoleA"
        assert role.is_active is True
        sess.flush.assert_called_once()
        assert resp is not None


class TestTwoFactorSecondFactor:
    """two_factor.py 91->98（无 hashed_password）/ 93->98（密码校验不过）。"""

    def test_password_without_hash_fails(self):
        user = SimpleNamespace(id=1, hashed_password=None)
        ok = _verify_second_factor(MagicMock(), user, DisableTwoFactorRequest(code="", password="pw"))
        assert ok is False

    def test_wrong_password_fails(self):
        user = SimpleNamespace(id=1, hashed_password="$2b$hash")
        with patch("app.api.v1.auth.two_factor.verify_password", return_value=False):
            ok = _verify_second_factor(MagicMock(), user, DisableTwoFactorRequest(code="", password="bad"))
        assert ok is False


class TestImportDataBranches:
    """import_data.py / excel_importer_service.py 分支。"""

    def test_parse_excel_rows_skips_unmapped_columns(self):
        """339->338（列未映射）与 341->326（整行无映射字段 → 丢弃）。

        header_parser 仅映射第 6 列（超出实际行宽），所有数据行均无命中列。
        """
        wb = Workbook()
        ws = wb.active
        ws.append(["h0", "h1"])
        ws.append(["a", "b"])
        ws.append(["c", "d"])
        buf = BytesIO()
        wb.save(buf)
        rows = _parse_excel_rows(buf.getvalue(), lambda headers: {5: "name"}, ("示例",))
        assert rows == []

    def test_summary_skips_error_without_field(self):
        """367->364：field_name 为空的错误不计入 errors_by_field。"""
        from app.services.entity_import_validator import (
            EntityImportValidator,
            ValidationError,
            ValidationErrorCode,
        )

        err_no_field = ValidationError(
            row_number=1,
            field_name="",
            error_code=ValidationErrorCode.DUPLICATE_DATA,
            message="dup",
            value="x",
        )
        err_with_field = ValidationError(
            row_number=2,
            field_name="name",
            error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
            message="req",
            value=None,
        )
        result = SimpleNamespace(
            is_valid=False,
            total_rows=2,
            valid_rows=1,
            errors=[err_no_field, err_with_field],
            warnings=[],
        )
        summary = _build_entity_validation_summary(result, EntityImportValidator("fund"))
        assert summary["errors_by_type"] == {"IMPORT_005": 1, "IMPORT_003": 1}
        assert summary["errors_by_field"] == {"资金名称": 1}

    def test_setup_preview_entity_unknown_type_hits_name_error(self):
        """471->473：实体类型不在 project/fund/school 分支 → EntityModel 未绑定。

        注：这是潜在缺陷（未知类型应提前校验拦截），此处仅覆盖分支。
        """
        from app.services.entity_import_validator import EntityImportValidator

        assert EntityImportValidator("unknown_entity").config == {}
        with pytest.raises(NameError):
            _setup_preview_entity("unknown_entity", MagicMock())

    def test_import_data_unknown_entity_falls_through_dispatch(self):
        """excel_importer_service.py 338->342：未知实体类型跳过全部分发分支。"""
        db = MagicMock()
        svc = ExcelImporterService(db, current_user=None)
        svc.parse_excel = Mock(return_value=([], []))
        out = svc.import_data(
            file_content=b"",
            file_name="x.xlsx",
            file_size=10,
            user_id=1,
            mode=ImportMode.INCREMENTAL,
            entity_type="unknown_entity",
        )
        assert out.total_rows == 0
        assert out.errors == []

    def test_create_village_keeps_provided_bool_field(self):
        """excel_importer_service.py 549->548：布尔字段已提供时不覆盖默认值。"""
        svc = ExcelImporterService(MagicMock(), current_user=None)
        village = svc._create_village({"village_name": "测试村", "is_provincial_demo": True})
        assert village.is_provincial_demo is True
        assert village.is_border_area is False

    def test_import_funds_row_without_name(self):
        """excel_importer_service.py 693->663：无名称资金行不加重复集合。"""
        db = MagicMock()
        q_fund, q_project = MagicMock(), MagicMock()
        q_project.all.return_value = []
        db.query.side_effect = [q_fund, q_project]
        svc = ExcelImporterService(db, current_user=None)
        result = ImportResult(success=False)
        out = svc._import_funds([{"name": ""}], result, MagicMock(), ImportMode.FULL)
        assert out.success_rows == 1
        assert out.errors == []

    def test_import_schools_row_without_name(self):
        """excel_importer_service.py 763->733：无名称学校行。"""
        db = MagicMock()
        q_school = MagicMock()
        db.query.side_effect = [q_school]
        svc = ExcelImporterService(db, current_user=None)
        result = ImportResult(success=False)
        out = svc._import_schools([{"name": ""}], result, MagicMock(), ImportMode.FULL)
        assert out.success_rows == 1
        assert out.errors == []


class TestPermissionPackageBranches:
    """permission_package.py 45->exit 与 319->324。"""

    def test_safe_unlink_missing_path_noop(self):
        _safe_unlink("")  # path 为假 → 直接返回
        _safe_unlink(str(Path(tempfile.gettempdir()) / "definitely_missing_pkg_file.bin"))

    def test_confirm_import_cleans_missing_file(self):
        """319->324：服务处理期间文件已被删除 → 跳过清理。"""
        from app.api.v1.permission_package import _resolve_package_upload_path

        file_path = _resolve_package_upload_path("pkg_branch_gap.json")
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_bytes(b"{}")
        svc = MagicMock()
        # 模拟服务消费掉上传文件
        svc.confirm_import.side_effect = lambda p, **kw: (os.path.exists(p) and os.unlink(p)) or {"success": True}
        admin = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
        try:
            with patch("app.api.v1.permission_package.PermissionPackageService", return_value=svc):
                with patch("app.api.v1.permission_package.write_work_log"):
                    resp = confirm_import_permission_package(
                        file_name=os.path.basename(file_path),
                        body=PermissionPackageConfirmRequest(),
                        current_user=admin,
                        db=MagicMock(),
                        request=MagicMock(),
                    )
            assert resp.body is not None
            assert not os.path.exists(str(file_path))
        finally:
            if os.path.exists(str(file_path)):
                os.unlink(str(file_path))


class TestSentimentBranches:
    """sentiment.py 102->105 / 105->108（两个可选过滤都缺省）。"""

    async def test_news_list_without_optional_filters(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.offset.return_value = q
        q.all.return_value = []
        resp = await get_news_list(
            sentiment_label=None,
            is_alert=None,
            days=7,
            limit=50,
            offset=0,
            current_user=SimpleNamespace(id=1),
            db=db,
        )
        assert resp["data"]["items"] == []


class TestSystemBackupBranches:
    """system/backup.py 534->536 与 570->569。"""

    async def test_update_schedule_without_keep_count(self):
        cfg = {"auto_backup": "true", "backup_schedule_cron": "0 3 * * *"}
        with patch("app.api.v1.system.backup.set_config") as sc:
            with patch("app.api.v1.system.backup.get_config", side_effect=lambda k, d=None: cfg.get(k, d)):
                with patch("app.api.v1.system.backup.get_int_config", return_value=7):
                    resp = await update_backup_schedule(
                        body=BackupScheduleUpdate(enabled=True, keep_count=None, schedule="0 3 * * *"),
                        db=None,
                        current_user=SimpleNamespace(role="admin", is_superuser=True),
                    )
        # keep_count None → 不写保留天数配置
        written_keys = [c.args[0] for c in sc.call_args_list]
        assert "backup_retention_days" not in written_keys
        assert resp["data"]["keepCount"] == 7

    async def test_delete_backup_no_match_in_records(self):
        """570->569：遍历记录不匹配 → 404。"""
        svc = MagicMock()
        svc.list_backups.return_value = [SimpleNamespace(file_name="other.zip", backup_id="b2")]
        with patch("app.api.v1.system.backup.get_backup_service", return_value=svc):
            with pytest.raises(Exception) as ei:
                await delete_backup(
                    filename="missing.zip",
                    request=MagicMock(),
                    db=MagicMock(),
                    operator="op",
                )
        assert getattr(ei.value, "status_code", None) == 404


class TestValidationBranches:
    """validation.py 233->235 与 489->491。"""

    async def test_validate_data_custom_error_message(self):
        rule = ValidationRule(
            module="school",
            field="name",
            rule_type=RuleType.required,
            params=None,
            error_message="名称必填",
            priority=1,
            is_active=True,
        )
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = [rule]
        resp = await validate_data(module="school", data={"name": None}, current_user=None, db=db)
        assert resp["data"]["valid"] is False
        assert resp["data"]["errors"][0]["message"] == "名称必填"
        assert resp["data"]["errors"][0]["field_label"] == FIELD_LABELS["name"]

    async def test_query_check_model_without_is_active(self):
        """489->491：模型无 is_active 列 → 不追加软删过滤。"""
        from sqlalchemy import Column, Integer, MetaData, String
        from sqlalchemy.orm import declarative_base

        Base2 = declarative_base(metadata=MetaData())

        class DummyNoActive(Base2):
            __tablename__ = "dummy_no_active_branch"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        db = MagicMock()
        q = MagicMock()
        q.limit.return_value = q
        q.all.return_value = [SimpleNamespace(id=1, name="alice")]
        db.query.return_value = q
        with patch.dict("app.api.v1.validation._QUERY_CHECK_MODELS", {"dummy": DummyNoActive}):
            with patch("app.core.data_permission.apply_scope_filter", side_effect=lambda query, *a, **k: query):
                resp = await query_check(
                    data=QueryCheckRequest(
                        module="dummy",
                        conditions=[QueryCondition(field="name", operator="contains", value="ali")],
                        logic="and",
                        limit=10,
                    ),
                    current_user=None,
                    db=db,
                )
        assert resp["data"]["matched"] == 1
        assert resp["data"]["total"] == 1
        q.filter.assert_not_called()


class TestConfigBranches:
    """config.py 320->307 / 396->401 / 403->408。"""

    def test_load_encrypted_secrets_unknown_key(self, tmp_path, monkeypatch):
        """320->307：解密出的键不属于已知四个密钥 → 跳过赋值继续循环。"""
        secrets_file = tmp_path / "secrets.json"
        key_file = tmp_path / "master.key"
        key_file.write_text("master-key-123")
        secrets_file.write_text('{"SECRET_KEY": "enc1", "OTHER_KEY": "enc2"}')

        cfg = Settings()
        monkeypatch.setattr(cfg, "SECRETS_FILE_PATH", str(secrets_file))
        monkeypatch.setattr(cfg, "MASTER_KEY_PATH", str(key_file))
        original_secret = cfg.SECRET_KEY

        fake_encryptor = MagicMock()
        fake_encryptor.decrypt_data.return_value = b"plain-value"
        fake_cls = MagicMock()
        fake_cls.from_key_string.return_value = fake_encryptor
        monkeypatch.setattr("app.utils.encryption.DataPackageEncryption", fake_cls)

        cfg._load_encrypted_secrets()

        assert cfg.SECRET_KEY == "plain-value"
        assert cfg.SECRET_KEY != original_secret
        # OTHER_KEY 不在已知分支中 → 不写入实例
        assert not hasattr(cfg, "OTHER_KEY")

    def test_settings_dynamic_paths_with_absolute_values(self, tmp_path, monkeypatch):
        """396->401（DATABASE_URL 已配置且非相对 sqlite）与 403->408（LOG_DIR 非相对路径）。"""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "abs.db").replace("\\", "/"))
        monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
        monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
        monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))

        cfg = Settings()
        assert cfg.DATABASE_URL.startswith("sqlite:///")
        assert "./" not in cfg.DATABASE_URL.split(":///")[1][:2]
        assert str(cfg.LOG_DIR) == str(tmp_path / "logs")


class TestLoggingConfigBranches:
    """logging_config.py 31->35 与 52->exit。"""

    def test_do_rollover_with_closed_stream(self, tmp_path):
        """31->35：stream 为 None 时跳过关闭直接轮转。"""
        base = tmp_path / "app.log"
        base.write_text("x", encoding="utf-8")
        handler = SafeTimedRotatingFileHandler(str(base), when="S", backupCount=1, delay=True)
        try:
            assert handler.stream is None
            handler.doRollover()  # 不应抛异常
            assert not base.exists()  # 原文件已被重命名
        finally:
            if handler.stream:
                handler.stream.close()
                handler.stream = None

    def test_do_rollover_gives_up_after_retries_keeps_stream(self, tmp_path, monkeypatch):
        """52->exit：5 次重试仍失败但流已被重新打开 → 不再重复打开。"""
        base = tmp_path / "app.log"
        base.write_text("x", encoding="utf-8")
        monkeypatch.setattr(time, "sleep", lambda s: None)

        attempts = {"n": 0}

        def fake_super_do_rollover(self):
            attempts["n"] += 1
            if attempts["n"] < 5:
                raise PermissionError(32, "file locked")
            # 最后一次"失败"但流被外层重新打开（模拟并发恢复）
            self.stream = io.StringIO()

        monkeypatch.setattr(logging.handlers.TimedRotatingFileHandler, "doRollover", fake_super_do_rollover)
        handler = SafeTimedRotatingFileHandler(str(base), when="S", backupCount=1, delay=True)
        try:
            handler.doRollover()
            assert attempts["n"] == 5
            assert handler.stream is not None  # 保持原流，不再 _open()
        finally:
            handler.stream = None


class TestPermissionUtilsBranches:
    """permission_utils.py 108->107 / 265->264 / 320->319 / 211->218。"""

    async def test_require_admin_skips_non_user_positional_arg(self):
        dec = require_admin()

        @dec
        async def endpoint(x):
            return "ok"

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as ei:
            await endpoint("plain-string")
        assert ei.value.status_code == 401

    async def test_require_organization_skips_non_user_positional_arg(self):
        dec = require_organization()

        @dec
        async def endpoint(x):
            return "ok"

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as ei:
            await endpoint(12345)
        assert ei.value.status_code == 401

    async def test_require_permission_skips_non_user_positional_arg(self):
        dec = require_permission("project:read")

        @dec
        async def endpoint(x):
            return "ok"

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as ei:
            await endpoint(object())
        assert ei.value.status_code == 401

    def test_get_org_with_fallback_uses_callback_when_no_user(self):
        """211->218：无用户对象 → 回调取第一个组织。"""
        org_id = get_org_with_fallback(
            current_user=None,
            requested_org_id=None,
            get_first_org_callback=lambda: 42,
        )
        assert org_id == 42


class TestTransactionBranches:
    """transaction.py 305->307 与 351->350。"""

    def test_apply_tx_settings_without_isolation(self, monkeypatch):
        monkeypatch.setattr("app.core.transaction.IS_SQLITE", False)
        sess = MagicMock()
        _apply_tx_settings(sess, isolation=None, readonly=True)
        # 仅设置只读，不设置隔离级别
        assert sess.execute.call_count == 1
        assert "READ ONLY" in str(sess.execute.call_args.args[0])

    def test_find_db_session_skips_non_session_args(self):
        real = MagicMock(spec=__import__("sqlalchemy.orm", fromlist=["Session"]).Session)
        found = _find_db_session(("not-a-session", 42, real), {})
        assert found is real


class TestMainBranches:
    """main.py 359->365 / 366->375 / 376->384（模块级挂载）与 717->735。"""

    def test_sqlite_col_spec_skips_non_scalar_default(self):
        """717->735：default.arg 非标量（bytes）→ 无 DEFAULT 子句。"""
        from app.main import _sqlite_col_spec

        col = SimpleNamespace(
            type="VARCHAR(50)",
            default=SimpleNamespace(arg=b"\x00raw"),
            server_default=None,
            nullable=True,
        )
        stype, clause = _sqlite_col_spec(col)
        assert stype == "TEXT"
        assert clause == ""

    def test_static_mounts_skipped_when_dirs_missing(self):
        """模块级：assets/images/static 目录缺失时跳过对应挂载。"""
        import app.main as main_mod

        orig_isdir = os.path.isdir

        def fake_isdir(p):
            if os.path.basename(str(p)) in ("assets", "images", "static"):
                return False
            return orig_isdir(p)

        try:
            with patch("os.path.isdir", side_effect=fake_isdir):
                importlib.reload(main_mod)
            mounted = {getattr(r, "path", "") for r in main_mod.app.routes}
            assert "/assets" not in mounted
            assert "/images" not in mounted
            assert "/static" not in mounted
        finally:
            importlib.reload(main_mod)  # 还原模块状态
        mounted_restored = {getattr(r, "path", "") for r in main_mod.app.routes}
        assert "/assets" in mounted_restored or "/uploads" in mounted_restored


class TestCsrfMiddlewareBranches:
    """csrf_middleware.py 97->100 与 308->306。"""

    def test_sign_csrf_token_accepts_bytes_token(self):
        sig = sign_csrf_token(b"1717000000.abcdef", "secret-k")
        expected = hmac.new(b"secret-k", b"1717000000.abcdef", hashlib.sha256).hexdigest()
        assert sig == expected

    def test_parse_cookies_skips_nameless_parts(self):
        headers = Headers(raw=[(b"cookie", b"a=1;;b=2 ; c=\"3\"")])
        cookies = CSRFMiddleware._parse_cookies(headers)
        assert cookies == {"a": "1", "b": "2", "c": "3"}


class TestModelsBaseBranches:
    """models/base.py 58->62 / 185->exit / 205->209。"""

    def test_is_datetime_type_with_plain_type(self):
        from sqlalchemy import Date, DateTime, String

        assert is_datetime_type(DateTime()) is True
        assert is_datetime_type(Date()) is True
        assert is_datetime_type(String(10)) is False

    def test_is_datetime_type_unwraps_at_most_five_levels(self):
        """58->62：超过 5 层 TypeDecorator 包装 → 循环自然耗尽后按最外层判断。"""
        from sqlalchemy.types import DateTime, TypeDecorator

        class DummyTD(TypeDecorator):
            impl = DateTime

        chain = [DummyTD() for _ in range(6)]
        for i in range(5):
            chain[i].impl = chain[i + 1]
        chain[-1].impl = DateTime()
        # 5 次解包后仍是 TypeDecorator → 不再继续，按候选类型本身判断
        assert is_datetime_type(chain[0]) is False

    def test_bump_sync_version_skips_none(self):
        """185->exit：sync_version 为 None（新对象）不递增。"""
        target = SimpleNamespace(sync_version=None)
        _bump_sync_version_on_update(None, None, target)
        assert target.sync_version is None

    def test_bulk_update_preserves_explicit_sync_version(self):
        """205->209：调用方显式设置 sync_version 时不覆盖。"""
        from sqlalchemy import Column, Integer, MetaData, Table
        from sqlalchemy.sql import update

        table = Table("t_bump_branch", MetaData(), Column("sync_version", Integer))
        stmt = update(table).values(sync_version=5)
        out_stmt, multiparams, params = _bump_sync_version_on_bulk_update(None, stmt, [], {}, {})
        assert out_stmt is stmt  # 未被替换

    def test_bulk_update_bumps_missing_sync_version(self):
        from sqlalchemy import Column, Integer, MetaData, Table
        from sqlalchemy.sql import update

        table = Table("t_bump_branch2", MetaData(), Column("sync_version", Integer))
        stmt = update(table).values(name="x")
        out_stmt, _, _ = _bump_sync_version_on_bulk_update(None, stmt, [], {}, {})
        assert out_stmt is not stmt  # 补上了 sync_version 自增


class TestRecommendationServiceBranches:
    """recommendation_service.py 102->88 与 255->261。"""

    def _patched_scoped_filter(self):
        return patch("app.services.data_scope_query.scoped_filter", side_effect=lambda query, *a, **k: query)

    def test_recommend_projects_caps_examples_at_three(self):
        """102->88：同类型第 4 个成功项目不再进 examples。"""
        village = SimpleNamespace(id=1, province="P", city="C")
        similar = [SimpleNamespace(id=2), SimpleNamespace(id=3)]
        projects = [
            SimpleNamespace(
                project_type="infra", name=f"p{i}", village_id=2, budget=100.0, progress=95
            )
            for i in range(4)
        ]
        vq, svq, pq = MagicMock(), MagicMock(), MagicMock()
        vq.filter.return_value.first.return_value = village
        svq.filter.return_value.limit.return_value.all.return_value = similar
        pq.filter.return_value.all.return_value = projects
        db = MagicMock()
        db.query.side_effect = [vq, svq, pq]

        with self._patched_scoped_filter():
            result = RecommendationService.recommend_projects(db, village_id=1, limit=5)

        assert isinstance(result, list) and len(result) >= 1
        assert result[0]["project_type"] == "infra"

    def test_fund_allocation_non_positive_total_score_skips_allocation(self):
        """255->261：total_score <= 0 → 不分配金额。

        注：负分场景（人口数为负的异常数据）会触发排序阶段 KeyError ——
        该分支当前实现存在潜在缺陷（未分配金额却参与排序），此处如实覆盖。
        """
        villages = [SimpleNamespace(id=1, village_name="A"), SimpleNamespace(id=2, village_name="B")]
        pop_rows = [
            SimpleNamespace(supported_village_id=1, population=-100000, year=2024),
            SimpleNamespace(supported_village_id=2, population=0, year=2024),
        ]
        q_villages, q_pop_meta, q_pop, q_inc_meta, q_inc = (MagicMock() for _ in range(5))
        q_villages.filter.return_value.all.return_value = villages
        q_pop.join.return_value.all.return_value = pop_rows
        q_inc.join.return_value.all.return_value = []
        db = MagicMock()
        db.query.side_effect = [q_villages, q_pop_meta, q_pop, q_inc_meta, q_inc]

        with self._patched_scoped_filter():
            with pytest.raises(KeyError):
                RecommendationService.recommend_fund_allocation(db, total_budget=1000.0, village_ids=[1, 2])


class TestBackupSchedulerBranches:
    """backup_scheduler.py 428->435 与 620->exit。"""

    async def test_auto_package_skips_when_interval_elapsed(self):
        """428->435：距上次打包超过间隔 → 继续执行（随后因无组织返回）。"""
        cfg = {"auto_package_enabled": "true", "auto_package_dir": "X:/pkg"}
        q_sys, q_org = MagicMock(), MagicMock()
        q_sys.filter.return_value.first.return_value = SimpleNamespace(value="2000-01-01T00:00:00")
        q_org.order_by.return_value.first.return_value = None
        db = MagicMock()
        db.query.side_effect = [q_sys, q_org]

        with patch("app.services.backup_scheduler.get_config", side_effect=lambda k, d=None: cfg.get(k, d)):
            with patch("app.services.backup_scheduler.get_int_config", return_value=1):
                with patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
                    result = await _auto_package_with_db(db)
        assert result is None
        assert db.query.call_count == 2

    def test_chunk_cleanup_job_without_expired_sessions(self):
        """620->exit：清理数为 0 时不记日志直接结束。"""
        svc = MagicMock()
        svc.cleanup_expired_sessions.return_value = 0
        with patch("app.services.chunked_upload_service.get_chunked_upload_service", return_value=svc):
            chunk_cleanup_job()
        svc.cleanup_expired_sessions.assert_called_once()


class TestBackupServiceBranches:
    """backup_service.py 347->352 / 698->714 / 720->722 / 727->729 / 1040-1041。"""

    def _make_service(self, tmp_path: Path) -> BackupService:
        svc = BackupService(db=None, backup_dir=str(tmp_path / "backups"))
        return svc

    def test_snapshot_failure_without_temp_file(self, tmp_path, monkeypatch):
        """347->352：快照临时文件未创建 → 跳过清理直接抛 BackupIncompleteError。"""
        db_file = tmp_path / "main.db"
        db_file.write_bytes(b"sqlite")
        svc = self._make_service(tmp_path)
        svc.database_path = str(db_file)

        def boom(*a, **kw):
            raise OSError("mkstemp failed")

        monkeypatch.setattr(tempfile, "mkstemp", boom)
        with pytest.raises(BackupIncompleteError) as ei:
            svc._create_consistency_snapshot()
        assert "一致性快照失败" in str(ei.value)

    def test_rollback_without_existing_live_files(self, tmp_path):
        """698->714（主库不存在跳过 unlink）与 720->722（uploads 目录不存在跳过 rmtree）。"""
        snap_db = tmp_path / "snap.db"
        snap_db.write_text("SNAPDB", encoding="utf-8")
        snap_up = tmp_path / "snap_up"
        snap_up.mkdir()
        (snap_up / "f.txt").write_text("UP", encoding="utf-8")

        svc = self._make_service(tmp_path)
        svc.database_path = str(tmp_path / "live_missing.db")  # 不存在
        svc.uploads_dir = str(tmp_path / "up_live_missing")  # 不存在

        svc._rollback_to_snapshots(str(snap_db), str(snap_up))

        assert Path(svc.database_path).read_text(encoding="utf-8") == "SNAPDB"
        assert (Path(svc.uploads_dir) / "f.txt").read_text(encoding="utf-8") == "UP"
        assert not snap_db.exists()  # 快照用后清理
        assert not snap_up.exists()

    def test_cleanup_temp_with_missing_paths(self, tmp_path):
        """727->729：临时目录不存在 → 跳过 rmtree。"""
        svc = self._make_service(tmp_path)
        svc._cleanup_temp(str(tmp_path / "no_such_dir"), None)

    def test_file_manifest_tolerates_stat_failure(self, tmp_path, monkeypatch):
        """1040-1041：os.stat 失败 → 记日志并跳过该文件。"""
        svc = self._make_service(tmp_path)
        # _validate_path 仅放行 uploads_dir 内的文件
        svc.uploads_dir = str(tmp_path / "up_live_manifest")
        files_dir = Path(svc.uploads_dir) / "sub"
        files_dir.mkdir(parents=True)
        (files_dir / "a.txt").write_text("data", encoding="utf-8")

        def boom(path, *a, **kw):
            raise OSError("stat failed")

        monkeypatch.setattr(os, "stat", boom)
        manifest = svc._get_file_manifest(str(files_dir))
        assert manifest == {}


class TestCacheServiceBranches:
    """cache_service.py 167->171 / 172->176 / 179->182 / 351->354。"""

    async def test_invalidate_counts_zero_when_delete_fails(self):
        svc = CacheService()
        svc.delete = AsyncMock(return_value=False)
        count = await svc.invalidate_related_cache("project", "5")
        assert count == 0
        assert svc.delete.await_count == 3

    async def test_cache_result_skips_set_for_none_result(self):
        """351->354：函数返回 None 时不写缓存。"""
        calls = {"n": 0}

        @cache_result(ttl=1)
        async def load_none():
            calls["n"] += 1
            return None

        assert await load_none() is None
        assert calls["n"] == 1


class TestDataTierServiceBranches:
    """data_tier_service.py 137->142 与 276->278。"""

    def test_archive_stats_without_cold_archive(self, tmp_path, monkeypatch):
        """137->142：冷存储目录不存在 → cold_archive_size 保持 0。"""
        hot = tmp_path / "hot.db"
        hot.write_bytes(b"db")
        warm = tmp_path / "warm.db"
        warm.write_bytes(b"db")
        svc = DataTierService()
        monkeypatch.setattr(svc.config, "HOT_DATA_PATH", str(hot))
        monkeypatch.setattr(svc.config, "WARM_DATA_PATH", str(warm))
        monkeypatch.setattr(svc.config, "COLD_ARCHIVE_PATH", str(tmp_path / "cold_missing"))

        stats = svc.get_archive_stats(db=None)
        assert stats["storage"]["cold_archive_size"] == 0
        assert stats["storage"]["hot_db_size"] == hot.stat().st_size

    def test_archive_records_write_failure_leaves_no_tmp(self, tmp_path, monkeypatch):
        """276->278：写临时归档失败且 tmp 未落盘 → 不尝试删除直接抛出。"""
        cold_dir = tmp_path / "cold"
        cold_dir.mkdir()
        svc = DataTierService()
        monkeypatch.setattr(svc.config, "COLD_ARCHIVE_PATH", str(cold_dir))
        monkeypatch.setattr(svc.config, "COMPRESSION_ENABLED", True)
        monkeypatch.setattr(svc, "_model_to_dict", lambda r: {"id": r.id}, raising=False)

        FakeModel = type(
            "FakeArchiveModel",
            (),
            {"__name__": "fakearchive", "created_at": datetime(2000, 1, 1)},
        )
        record = SimpleNamespace(id=7)
        q = MagicMock()
        q.count.return_value = 1
        q.all.return_value = [record]
        q.limit.return_value = q
        db = MagicMock()
        db.query.return_value.filter.return_value = q

        def gzip_boom(*a, **kw):
            raise OSError("gzip failed")

        monkeypatch.setattr("app.services.data_tier_service.gzip.open", gzip_boom)

        before_date = datetime.now(timezone.utc) - timedelta(days=3650)
        archived, msg = svc.archive_records(db, FakeModel, before_date=before_date)
        assert archived == 0
        assert "归档失败" in msg
        db.rollback.assert_called_once()
        assert list(cold_dir.iterdir()) == []  # 无残留 tmp 文件


class TestDbMaintenanceBranches:
    """db_maintenance.py 102->exit 与 108->102。"""

    def test_wal_checkpoint_loop_exits_on_stop_event(self, monkeypatch):
        monkeypatch.setattr("app.services.db_maintenance._do_wal_checkpoint", lambda: None)
        fake_event = SimpleNamespace(
            is_set=Mock(side_effect=[False, True]),
            wait=Mock(return_value=False),
        )
        monkeypatch.setattr("app.services.db_maintenance._wal_stop_event", fake_event)
        _run_wal_checkpoint()
        assert fake_event.is_set.call_count == 2
        assert fake_event.wait.call_count == 2


class TestMachineCodeServiceBranches:
    """machine_code_service.py 260->266 / 379->385 / 393->404。"""

    def test_machine_info_without_memory_output(self, monkeypatch):
        """260->266：wmic 返回空输出 → 不写 memory_gb。"""
        monkeypatch.setattr(
            "app.services.machine_code_service.subprocess.run",
            lambda *a, **kw: SimpleNamespace(stdout=""),
        )
        info = MachineCodeService.get_machine_info()
        assert "memory_gb" not in info
        assert "system" in info

    def test_self_verify_org_pass_code_finds_existing_org_and_record(self):
        """379->385（组织已存在）与 393->404（记录已存在）。"""
        db = MagicMock()
        org = SimpleNamespace(id=3)
        record = SimpleNamespace(id=9)
        q_org, q_rec = MagicMock(), MagicMock()
        q_org.filter.return_value.first.return_value = org
        q_rec.filter.return_value.first.return_value = record
        db.query.side_effect = [q_org, q_rec]

        svc = MachineCodeService(db=db)
        pass_code = MachineCodeService.generate_org_pass_code("单位A")
        out = svc.self_verify_org_pass_code(pass_code, "单位A")
        assert out is record
        assert db.add.call_count == 0  # find-or-create 均命中，无新建


class TestOfflineMapServiceBranches:
    """offline_map_service.py 106->105 与 151->153。"""

    async def test_coverage_ignores_non_directory_entries(self, tmp_path):
        """106->105：缓存目录中的普通文件不计入瓦片统计。"""
        cache_dir = tmp_path / "tiles"
        cache_dir.mkdir()
        (cache_dir / "README.txt").write_text("note", encoding="utf-8")
        svc = OfflineMapService(cache_dir=cache_dir)
        stats = await svc.get_coverage()
        assert stats["total_tiles"] == 0
        assert stats["zoom_levels"] == []

    def test_download_region_idempotent(self, tmp_path):
        """151->153：重复下载同一区域不重复登记。"""
        svc = OfflineMapService(cache_dir=tmp_path / "tiles2")
        assert svc.download_region("region-x") is True
        assert svc.download_region("region-x") is True
        assert svc._downloaded_regions == ["region-x"]


class TestReportExportServiceBranches:
    """report_export_service.py 411->410 / 473->475 / 497->499。"""

    def test_export_word_row_longer_than_headers(self):
        """411->410：数据行列数超过表头 → 多余单元格跳过。"""
        svc = ReportExportService()
        data = {
            "title": "分支覆盖",
            "sections": [
                {"title": "S1", "table": {"headers": ["A", "B"], "rows": [["1", "2", "extra"]]}},
            ],
        }
        out = svc.export_word("annual", data)
        assert isinstance(out, bytes) and len(out) > 0

    def test_add_text_run_without_size(self):
        """473->475：size 缺省 → 不设置字号。"""
        from docx import Document

        doc = Document()
        p = doc.add_paragraph()
        run = ReportExportService._add_text_run(p, "你好")
        assert run.text == "你好"
        assert run.font.size is None

    def test_add_field_run_without_size(self):
        """497->499：域 run 缺省字号。"""
        from docx import Document

        doc = Document()
        p = doc.add_paragraph()
        run = ReportExportService._add_field_run(p, "PAGE")
        assert run.font.size is None
        assert "fldChar" in run._r.xml


class TestDeviceFingerprintBranches:
    """device_fingerprint.py 180->184 / 266->272 / 268->272。"""

    def test_trust_score_with_untrusted_platform(self):
        """180->184：平台不在可信列表 → 无加分。"""
        svc = DeviceFingerprintService()

        def device_with(platform):
            return DeviceFingerprint(
                fingerprint_id="fp-x",
                user_agent="Mozilla/5.0 (Windows NT 10.0) normal-browser",
                ip_address="1.2.3.4",
                platform=platform,
            )

        untrusted = svc._calculate_trust_score(device_with("WeirdOS/9.9"))
        trusted = svc._calculate_trust_score(device_with("MacIntel"))
        assert 0.0 <= untrusted <= 1.0
        # 可信平台 +0.1，未命中可信列表不加分
        assert trusted == pytest.approx(untrusted + 0.1)

    def test_update_trust_score_unknown_action_and_successful_export(self):
        """266->272（未知动作）与 268->272（导出成功不扣分）。"""
        svc = DeviceFingerprintService()
        device = svc.create_device_record("fp-act", "ok-ua", "1.1.1.1")
        base = device.trust_score

        s1 = svc.update_trust_score("fp-act", "data_export", True)
        assert s1 == base  # 成功导出不调整

        s2 = svc.update_trust_score("fp-act", "page_view", True)
        assert s2 == base  # 未知动作不调整


class TestAuditLoggerBranches:
    """audit_logger.py 192->198 / 198->exit / 243->245 / 245->248。"""

    def test_persist_db_failure_with_no_session(self, monkeypatch):
        """192->198 与 198->exit：SessionLocal 创建失败且 db 为 None。"""
        def boom():
            raise RuntimeError("no db")

        monkeypatch.setattr("app.core.database.SessionLocal", boom)
        # 不应抛出异常（审计失败不影响主流程）
        AuditLogger._persist_to_db(
            {"action": "login", "username": "u", "user_id": None},
            __import__("app.models.audit", fromlist=["AuditAction"]).AuditAction.LOGIN,
        )

    def test_log_data_change_without_old_and_new_data(self, monkeypatch):
        """243->245 与 245->248：old_data/new_data 均为空。"""
        session = MagicMock()
        monkeypatch.setattr("app.core.database.SessionLocal", lambda: session)
        from app.models.audit import AuditAction

        AuditLogger.log_data_change(
            action=AuditAction.UPDATE,
            user_id=1,
            username="u",
            resource_type="project",
            old_data=None,
            new_data=None,
        )
        session.add.assert_called()  # 审计记录已入库


class TestExcelReportStyleBranches:
    """excel_report_style.py 248->247 / 333->336 / 337->340。"""

    def test_autofit_widths_with_short_rows(self):
        """248->247：数据行短于表头列数 → 该列只按表头估宽。"""
        widths = autofit_widths(None, ["列A", "列B"], [["只有一列"]])
        assert len(widths) == 2
        assert widths[0] >= widths[1]

    def test_build_report_sheet_reuse_ws_without_rename(self):
        """333->336（sheet_name 为空不重命名）与 337->340（显式列宽）。"""
        from openpyxl import Workbook as NewWorkbook

        wb = NewWorkbook()
        ws = wb.active
        out_ws, start, end = build_report_sheet(
            wb,
            "测试报表",
            ["A", "B"],
            [["1", "2"]],
            ws=ws,
            sheet_name=None,
            col_widths=[20.0, 20.0],
        )
        assert out_ws is ws
        assert end >= start
