"""2026-11-07 深度审计修复的单元测试。

覆盖本轮新增/改写的纯函数与守卫分支，避免全量覆盖率门禁因新分支回落：
- ``reports._safe_output_dir``（订阅输出目录限制）
- ``menus._assert_menu_config_target_allowed``（菜单配置跨组织防护）
- ``search._append_policy_results``（非管理员草稿/软删过滤）
- ``upload_helper._validate_upload_extension``（无扩展名/白名单）
- ``fund_lifecycle._assert_standalone_record_access``（独立记录跨组织防护）
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1 import menus as menus_module
from app.api.v1 import search as search_module
from app.api.v1.data.data import reports as reports_module
from app.api.v1.fund_lifecycle import _assert_standalone_record_access
from app.utils import upload_helper


def _user(role="admin", is_superuser=False, org=1, username="admin1", uid=2):
    return SimpleNamespace(
        id=uid,
        role=role,
        is_superuser=is_superuser,
        organization_id=org,
        username=username,
    )


# --------------------------------------------------------------------------
# reports._safe_output_dir
# --------------------------------------------------------------------------
class TestSafeOutputDir:
    def test_empty_returns_none(self):
        assert reports_module._safe_output_dir(None) is None
        assert reports_module._safe_output_dir("") is None

    def test_inside_uploads_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.utils.paths.get_runtime_uploads_path", lambda: str(tmp_path)
        )
        inside = tmp_path / "reports"
        inside.mkdir()
        assert reports_module._safe_output_dir(str(inside)) == str(inside.resolve())

    def test_outside_uploads_dir_rejected(self, tmp_path, monkeypatch):
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        monkeypatch.setattr(
            "app.utils.paths.get_runtime_uploads_path", lambda: str(uploads)
        )
        with pytest.raises(HTTPException) as exc_info:
            reports_module._safe_output_dir(str(tmp_path / "evil"))
        assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# menus._assert_menu_config_target_allowed
# --------------------------------------------------------------------------
class TestMenuConfigTargetGuard:
    def test_superuser_allowed(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "app.core.data_permission.assert_org_reachable",
            lambda *a, **k: calls.append((a, k)),
        )
        menus_module._assert_menu_config_target_allowed(
            None,
            _user(role="super_admin", is_superuser=True),
            SimpleNamespace(role="user", organization_id=99),
        )
        assert calls == []

    def test_target_super_admin_forbidden(self):
        with pytest.raises(HTTPException) as exc_info:
            menus_module._assert_menu_config_target_allowed(
                None,
                _user(role="admin"),
                SimpleNamespace(role="super_admin", is_superuser=True),
            )
        assert exc_info.value.status_code == 403

    def test_cross_org_delegates_to_assert_org_reachable(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "app.core.data_permission.assert_org_reachable",
            lambda db, user, org, action=None: calls.append((org, action)),
        )
        menus_module._assert_menu_config_target_allowed(
            None, _user(role="admin"), SimpleNamespace(role="user", organization_id=7)
        )
        assert calls == [(7, "修改菜单")]


# --------------------------------------------------------------------------
# search._append_policy_results
# --------------------------------------------------------------------------
class TestSearchPolicyVisibility:
    def test_regular_user_gets_visibility_filter(self):
        db = MagicMock()
        filtered = db.query.return_value.filter.return_value
        filtered.filter.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(id=1, title="政策一", issuing_authority=None)
        ]
        items = []
        search_module._append_policy_results(
            items, "政策", 5, db, current_user=_user(role="user")
        )
        assert len(items) == 1
        assert items[0].link == "/policies/1"
        assert filtered.filter.called

    def test_admin_does_not_get_visibility_filter(self):
        db = MagicMock()
        filtered = db.query.return_value.filter.return_value
        filtered.limit.return_value.all.return_value = []
        search_module._append_policy_results(
            [], "政策", 5, db, current_user=_user(role="admin")
        )
        filtered.filter.assert_not_called()

    def test_db_error_swallowed(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        items = []
        search_module._append_policy_results(items, "政策", 5, db, current_user=None)
        assert items == []


# --------------------------------------------------------------------------
# upload_helper._validate_upload_extension
# --------------------------------------------------------------------------
class TestUploadExtensionValidation:
    def test_missing_extension_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            upload_helper._validate_upload_extension("", {"pdf"}, 400)
        assert exc_info.value.status_code == 400
        assert "扩展名" in exc_info.value.detail

    def test_not_allowed_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            upload_helper._validate_upload_extension("exe", {"pdf"}, 415)
        assert exc_info.value.status_code == 415
        assert "不支持" in exc_info.value.detail

    def test_allowed_case_insensitive(self):
        assert upload_helper._validate_upload_extension("PDF", {".pdf"}, 400) is None


# --------------------------------------------------------------------------
# fund_lifecycle._assert_standalone_record_access
# --------------------------------------------------------------------------
class TestStandaloneRecordAccess:
    def test_creator_allowed(self):
        assert (
            _assert_standalone_record_access(
                SimpleNamespace(created_by="bob"),
                _user(role="user", username="bob"),
                db=None,
            )
            is None
        )

    def test_superuser_allowed(self):
        assert (
            _assert_standalone_record_access(
                SimpleNamespace(created_by="bob"),
                _user(role="super_admin", is_superuser=True),
                db=None,
            )
            is None
        )

    def test_department_admin_same_subtree_allowed(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            organization_id=3
        )
        monkeypatch.setattr(
            "app.core.data_permission._get_org_subtree",
            lambda db_, org: ([1, 3], []),
        )
        assert (
            _assert_standalone_record_access(
                SimpleNamespace(created_by="bob"), _user(role="admin", org=1), db=db
            )
            is None
        )

    def test_department_admin_cross_org_forbidden(self, monkeypatch):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            organization_id=9
        )
        monkeypatch.setattr(
            "app.core.data_permission._get_org_subtree", lambda db_, org: ([1], [])
        )
        with pytest.raises(HTTPException) as exc_info:
            _assert_standalone_record_access(
                SimpleNamespace(created_by="bob"), _user(role="admin", org=1), db=db
            )
        assert exc_info.value.status_code == 403

    def test_admin_without_db_fail_closed(self):
        with pytest.raises(HTTPException) as exc_info:
            _assert_standalone_record_access(
                SimpleNamespace(created_by="bob"), _user(role="admin", org=1), db=None
            )
        assert exc_info.value.status_code == 403

    def test_regular_user_other_record_forbidden(self):
        with pytest.raises(HTTPException) as exc_info:
            _assert_standalone_record_access(
                SimpleNamespace(created_by="bob"),
                _user(role="user", username="alice"),
                db=None,
            )
        assert exc_info.value.status_code == 403

# --------------------------------------------------------------------------
# batch_service._apply_batch_scope（2026-11-07 深审 P2：work_logs 等无组织列表）
# --------------------------------------------------------------------------
class TestBatchScope:
    def test_work_logs_without_user_identity_rejected(self):
        import asyncio

        from app.services.batch_service import BatchService

        svc = BatchService(db=MagicMock())
        result = asyncio.run(
            svc.batch_export("work_logs", [1], organization_id=7, is_superuser=False)
        )
        assert result["success"] is False
        assert "缺少用户身份" in result["error"]

    def test_work_logs_filters_by_user_id(self):
        import asyncio

        from app.services.batch_service import BatchService

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = []
        svc = BatchService(db=db)
        result = asyncio.run(
            svc.batch_export(
                "work_logs", [1], organization_id=7, is_superuser=False, user_id=5
            )
        )
        assert result["success"] is True
        db.query.return_value.filter.return_value.filter.assert_called_once()

    def test_table_without_org_or_user_column_rejected(self):
        from app.services.batch_service import BatchService, _apply_batch_scope

        query = MagicMock()
        model = SimpleNamespace(__tablename__="no_scope_table")
        _, error = _apply_batch_scope(
            query, model, organization_id=1, is_superuser=False, user_id=2
        )
        assert error is not None
        assert "缺少组织/用户归属列" in error
        assert BatchService  # 保持导入可被使用
