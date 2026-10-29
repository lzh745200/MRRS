# -*- coding: utf-8 -*-
"""全库审计修复（2026-10-29）新增分支的覆盖率补测。

本批修复给若干模块加了防御分支（禁用账号拒绝、审计序列化降级、审计写入失败、
发布路径正则豁免等）。全量覆盖率门禁要求 100%，这里为每个新分支各写一条用例，
避免为通过门禁而去掉防御（门禁的目的正是逼出这些分支的测试）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core import maintenance as mw
from app.core import security as sec
from app.utils import audit_logger as al


class TestRejectInactiveUser:
    """security._reject_inactive_user：禁用账号必须 403。"""

    def test_active_user_passes(self):
        sec._reject_inactive_user(MagicMock(is_active=True))

    def test_inactive_user_raises_403(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as ei:
            sec._reject_inactive_user(MagicMock(is_active=False))
        assert ei.value.status_code == 403
        assert "禁用" in ei.value.detail

    def test_object_without_is_active_passes(self):
        # 没有 is_active 属性的对象（历史/内部对象）不得被误拒
        class _Bare:
            pass

        sec._reject_inactive_user(_Bare())


class TestJsonSafeValue:
    """audit_logger._json_safe_value：details 必须可 JSON 序列化。"""

    def test_none_returns_none(self):
        assert al._json_safe_value(None) is None

    def test_plain_dict_passes_through(self):
        assert al._json_safe_value({"a": 1}) == {"a": 1}

    def test_datetime_converted_to_str(self):
        from datetime import datetime

        out = al._json_safe_value({"t": datetime(2026, 10, 29, 12, 0, 0)})
        assert isinstance(out["t"], str)
        assert "2026-10-29" in out["t"]

    def test_unserializable_falls_back_to_summary(self):
        # 自引用列表：json.dumps 抛 ValueError（循环引用）→ 降级为字符串摘要
        loop = []
        loop.append(loop)
        out = al._json_safe_value({"bad": loop})
        assert "_unserializable" in out


class TestAuditLogServiceFailurePaths:
    """security.AuditLogService.log：会话关闭失败也必须被吞掉。"""

    async def test_close_failure_is_swallowed(self):
        own = MagicMock()
        own.close.side_effect = RuntimeError("close failed")
        with patch("app.core.database.SessionLocal", return_value=own):
            # 不得抛出：审计是旁路，关闭失败同样不能影响业务
            await sec.AuditLogService.log(db=MagicMock(), user_id=1, action="login")
        own.close.assert_called_once()


class TestMaintenanceExemptPaths:
    """maintenance：豁免按锚定正则判定，任意后缀不得继承豁免。"""

    def test_shutdown_variants_exempt(self):
        # 只验证正则本身（不依赖 is_path_exempt 的公开名）
        cases = [
            "/api/v1/shutdown",
            "/api/v1/system/shutdown",
            "/shutdown",
        ]
        for path in cases:
            assert any(p.match(path.rstrip("/")) for p in mw.EXEMPT_PATH_PATTERNS), path

    def test_arbitrary_suffix_not_exempt(self):
        # 关键回归：新加一个以 /shutdown 结尾的写路由，不得自动继承豁免
        bad = ["/api/v1/report/shutdown", "/api/v1/admin/shutdown"]
        for path in bad:
            assert not any(p.match(path) for p in mw.EXEMPT_PATH_PATTERNS), path

    def test_backup_restore_variants_exempt(self):
        cases = [
            "/api/v1/backup/restore",
            "/api/v1/system/backup/restore",
            "/api/v1/system/backup/upload-restore",
        ]
        for path in cases:
            assert any(p.match(path) for p in mw.EXEMPT_PATH_PATTERNS), path

    def test_backup_restore_arbitrary_suffix_not_exempt(self):
        assert not any(p.match("/api/v1/foo/restore") for p in mw.EXEMPT_PATH_PATTERNS)

class TestOptionalCurrentUserEmptyToken:
    """permission_package._optional_current_user：header 有值但 token 为空。"""

    def test_bearer_with_empty_token_returns_none(self):
        import asyncio

        from app.api.v1.permission_package import _optional_current_user

        assert asyncio.run(
            _optional_current_user(
                request=MagicMock(), db=MagicMock(), authorization="Bearer "
            )
        ) is None


class TestRbacAuditFailureSwallowed:
    """rbac._audit_permission_change：审计写入失败不得阻断权限变更本身。"""

    def test_audit_exception_logged_not_raised(self):
        from app.api.v1.auth import rbac

        with patch("app.api.v1.auth.rbac.AuditLogger.log", side_effect=RuntimeError("boom")):
            # 不抛：审计是旁路，权限变更必须照常完成
            rbac._audit_permission_change("rbac_assign_role", MagicMock(username="u"), {"a": 1})


class TestSchoolCodeConflictMessage:
    """school._raise_if_code_taken：编码占用必须区分活跃 / 已软删除。"""

    def test_none_existing_returns(self):
        from app.api.v1.school import _raise_if_code_taken

        assert _raise_if_code_taken(None, "X001") is None

    def test_active_existing_conflict(self):
        from app.api.v1.school import _raise_if_code_taken
        from app.core.error_handler import AppError

        existing = MagicMock(is_active=True, name="在用学校")
        with pytest.raises(AppError) as ei:
            _raise_if_code_taken(existing, "X001")
        # AppError 的文案属性是 message（不是 detail）
        assert "已存在" in ei.value.message

    def test_soft_deleted_existing_gives_actionable_message(self):
        from app.api.v1.school import _raise_if_code_taken
        from app.core.error_handler import AppError

        existing = MagicMock(is_active=False, name="已删学校")
        with pytest.raises(AppError) as ei:
            _raise_if_code_taken(existing, "X001")
        message = ei.value.message
        assert "仍被已删除的学校" in message
        assert "已删学校" in message
        assert "请改用其他编码" in message