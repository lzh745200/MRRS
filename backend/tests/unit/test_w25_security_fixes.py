"""W25（2026-10-20）安全收口回归测试。

覆盖本次修复引入的全部分支（后端覆盖率门禁要求 100%）：

1. ``get_org_scope`` 对部门级 admin 收口为「本组织及子树」（P0-1）
2. ``statistics._get_analysis_data_impl`` 的 active_projects 接入数据域（P0-2）
3. ``approve_task`` / ``reject_task`` 未分配审批人 fail-closed（P1-1）
4. ``_assert_can_grant_data_scope`` 提权收口（P1-4）
5. Excel 导入角色门禁 + full 模式限超管（P1-3）
6. ``ExcelImporterService._assert_org_reachable`` 跨组织写入守卫（P1-3）
"""

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.services.excel_importer_service import ExcelImporterService


def _user(**kw):
    defaults = dict(
        id=1,
        role="user",
        is_superuser=False,
        organization_id=None,
        data_scope=None,
        department=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ══════════════════════════════════════════════════════════════════
# 1. get_org_scope — 部门级 admin 收口（P0-1）
# ══════════════════════════════════════════════════════════════════


class TestGetOrgScopeStrict:
    @pytest.mark.asyncio
    async def test_dept_admin_gets_subtree_not_full_access(self):
        from app.core import data_permission as dp

        user = _user(role="admin", organization_id=7)
        db = MagicMock()
        with patch.object(dp, "is_superuser", return_value=False), patch.object(
            dp, "_get_org_subtree", return_value=([7, 8], ["本部", "下级"])
        ):
            scope = await get_org_scope(current_user=user, db=db)
        assert scope.is_admin is False
        assert scope.org_ids == [7, 8]

    @pytest.mark.asyncio
    async def test_dept_admin_without_org_is_self_only(self):
        from app.core import data_permission as dp

        user = _user(role="admin", organization_id=None)
        with patch.object(dp, "is_superuser", return_value=False):
            scope = await get_org_scope(current_user=user, db=MagicMock())
        assert scope.self_only is True
        assert scope.is_admin is False

    @pytest.mark.asyncio
    async def test_dept_admin_without_db_session_limited_to_own_org(self):
        from app.core import data_permission as dp

        user = _user(role="admin", organization_id=9)
        with patch.object(dp, "is_superuser", return_value=False):
            scope = await get_org_scope(current_user=user, db=None)
        assert scope.is_admin is False
        assert scope.org_ids == [9]

    @pytest.mark.asyncio
    async def test_dept_admin_empty_subtree_falls_back_to_own_org(self):
        from app.core import data_permission as dp

        user = _user(role="admin", organization_id=9)
        with patch.object(dp, "is_superuser", return_value=False), patch.object(
            dp, "_get_org_subtree", return_value=([], [])
        ):
            scope = await get_org_scope(current_user=user, db=MagicMock())
        assert scope.is_admin is False
        assert scope.org_ids == [9]

    @pytest.mark.asyncio
    async def test_super_admin_role_full_access(self):
        from app.core import data_permission as dp

        user = _user(role="super_admin")
        with patch.object(dp, "is_superuser", return_value=False):
            scope = await get_org_scope(current_user=user, db=None)
        assert scope.is_admin is True

    @pytest.mark.asyncio
    async def test_is_superuser_flag_full_access(self):
        from app.core import data_permission as dp

        user = _user(role="admin")
        with patch.object(dp, "is_superuser", return_value=True):
            scope = await get_org_scope(current_user=user, db=None)
        assert scope.is_admin is True

    @pytest.mark.asyncio
    async def test_explicit_all_data_scope_full_access(self):
        user = _user(role="user", data_scope="all")
        scope = await get_org_scope(current_user=user, db=None)
        assert scope.is_admin is True


# ══════════════════════════════════════════════════════════════════
# 2. statistics active_projects 数据域（P0-2）
# ══════════════════════════════════════════════════════════════════


class TestStatisticsActiveProjectsScoped:
    @pytest.mark.asyncio
    async def test_active_projects_goes_through_scope_filter(self):
        """Project 模型必须经 apply_scope_filter（原实现直查全库）。"""
        from app.api.v1.data.data import statistics as st

        db = MagicMock()
        # 所有 count/scalar 归零，避免真实查询
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.scalar.return_value = 0
        db.query.return_value.count.return_value = 0
        db.query.return_value.scalar.return_value = 0

        calls = []

        def _fake_apply(q, user, model, **kw):
            calls.append(model)
            return q

        with patch.object(st, "apply_scope_filter", _fake_apply, create=True), patch.object(
            st, "apply_scope_filter", _fake_apply, create=True
        ):
            # statistics 在函数内部 import，需 patch 源模块
            from app.core import data_permission as dp

            with patch.object(dp, "apply_scope_filter", _fake_apply):
                try:
                    await st._get_analysis_data_impl(db, _user(role="admin", organization_id=1))
                except Exception:
                    # 该函数后续依赖较多，只关心 Project 是否进入 scope 入口
                    pass

        from app.models.project import Project

        assert Project in calls, f"active_projects 未经数据域过滤；实际调用模型={calls}"


# ══════════════════════════════════════════════════════════════════
# 3. Excel 导入角色门禁（P1-3）
# ══════════════════════════════════════════════════════════════════


def _upload(content: bytes = b"x", filename: str = "a.xlsx") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


class TestImportRoleGate:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_import(self):
        from app.api.v1.import_export.import_data import _import_entities

        with patch(
            "app.api.v1.import_export.import_data.is_admin", return_value=False
        ):
            with pytest.raises(HTTPException) as ei:
                await _import_entities(
                    file=_upload(),
                    mode="incremental",
                    entity_type="supported_village",
                    current_user=_user(role="user"),
                    db=MagicMock(),
                )
        assert ei.value.status_code == 403
        assert "仅管理员" in ei.value.detail

    @pytest.mark.asyncio
    async def test_full_mode_requires_superuser(self):
        from app.api.v1.import_export.import_data import _import_entities

        with patch(
            "app.api.v1.import_export.import_data.is_admin", return_value=True
        ), patch(
            "app.api.v1.import_export.import_data.is_superuser", return_value=False
        ):
            with pytest.raises(HTTPException) as ei:
                await _import_entities(
                    file=_upload(),
                    mode="full",
                    entity_type="supported_village",
                    current_user=_user(role="admin", organization_id=1),
                    db=MagicMock(),
                )
        assert ei.value.status_code == 403
        assert "超级管理员" in ei.value.detail

    @pytest.mark.asyncio
    async def test_full_mode_superuser_passes_role_gate(self):
        """超管通过角色门禁：不抛 403（非法 xlsx 由导入器记为行错误并返回结果）。"""
        from app.api.v1.import_export.import_data import _import_entities

        with patch(
            "app.api.v1.import_export.import_data.is_admin", return_value=True
        ), patch(
            "app.api.v1.import_export.import_data.is_superuser", return_value=True
        ):
            result = await _import_entities(
                file=_upload(b"not-an-excel"),
                mode="full",
                entity_type="supported_village",
                current_user=_user(role="super_admin"),
                db=MagicMock(),
            )
        # 越过 403 门禁即算通过（解析失败的形态由导入器自身决定）
        assert result is not None


# ══════════════════════════════════════════════════════════════════
# 4. _assert_org_reachable（P1-3 跨组织写入）
# ══════════════════════════════════════════════════════════════════


class TestExcelImportOrgReachable:
    def _svc(self, user):
        return ExcelImporterService(db=MagicMock(), current_user=user)

    def test_no_current_user_passes(self):
        ExcelImporterService(db=MagicMock(), current_user=None)._assert_org_reachable(5)

    def test_none_target_passes(self):
        self._svc(_user(role="user", organization_id=1))._assert_org_reachable(None)

    def test_superuser_passes_any_org(self):
        self._svc(_user(role="super_admin", is_superuser=True))._assert_org_reachable(999)

    def test_same_org_passes(self):
        self._svc(_user(role="admin", organization_id=3))._assert_org_reachable(3)

    def test_subtree_org_passes(self):
        svc = self._svc(_user(role="admin", organization_id=3))
        with patch(
            "app.core.data_permission._get_org_subtree", return_value=([3, 4, 5], [])
        ):
            svc._assert_org_reachable(5)

    def test_foreign_org_rejected(self):
        svc = self._svc(_user(role="admin", organization_id=3))
        with patch(
            "app.core.data_permission._get_org_subtree", return_value=([3, 4], [])
        ):
            with pytest.raises(PermissionError):
                svc._assert_org_reachable(99)

    def test_user_without_org_rejected(self):
        with pytest.raises(PermissionError):
            self._svc(_user(role="user", organization_id=None))._assert_org_reachable(1)

    def test_non_numeric_target_rejected(self):
        with pytest.raises(PermissionError):
            self._svc(_user(role="admin", organization_id=1))._assert_org_reachable("abc")


# ══════════════════════════════════════════════════════════════════
# 5. data_scope="all" 提权收口（P1-4）
# ══════════════════════════════════════════════════════════════════


class TestGrantDataScopeGuard:
    def _f(self, user, scope):
        from app.api.v1.auth.users import _assert_can_grant_data_scope

        return _assert_can_grant_data_scope(user, scope)

    def test_non_all_scope_always_allowed(self):
        self._f(_user(role="admin"), "org")
        self._f(_user(role="admin"), "self")
        self._f(_user(role="admin"), None)

    def test_superuser_can_grant_all(self):
        self._f(_user(role="admin", is_superuser=True), "all")

    def test_super_admin_role_can_grant_all(self):
        self._f(_user(role="super_admin"), "all")

    def test_super_admin_role_branch_reachable_when_is_superuser_stubbed(self):
        """防御分支：is_superuser() 为 False 但 role 仍是 super_admin 时也放行。

        生产路径下 ``is_superuser()`` 自身就覆盖 role=="super_admin"，故该分支
        不可自然到达；此处打桩以锁定"即使 is_superuser 语义变化也不回退成 403"。
        """
        from app.api.v1.auth import users as users_mod

        with patch.object(users_mod, "is_superuser", return_value=False):
            users_mod._assert_can_grant_data_scope(_user(role="super_admin"), "all")

    def test_dept_admin_cannot_grant_all(self):
        with pytest.raises(HTTPException) as ei:
            self._f(_user(role="admin", is_superuser=False), "all")
        assert ei.value.status_code == 403

    def test_normal_user_cannot_grant_all(self):
        with pytest.raises(HTTPException) as ei:
            self._f(_user(role="user"), "all")
        assert ei.value.status_code == 403


# ══════════════════════════════════════════════════════════════════
# 6. 审批未分配任务 fail-closed（P1-1）——端点层 standalone 传参
# ══════════════════════════════════════════════════════════════════


class TestApprovalEndpointStandalone:
    def test_approve_endpoint_passes_standalone_for_admin(self):
        from app.api.v1 import approval as ap

        svc = MagicMock()
        svc.approve_task.return_value = MagicMock(
            id=1, status="approved", current_level=1, title="t", entity_type="fund"
        )
        with patch.object(ap, "ApprovalWorkflowService", return_value=svc), patch.object(
            ap, "is_admin", return_value=True
        ), patch.object(ap, "_notify_submitter"):
            ap.approve_task(
                1, ap.ApprovalActionRequest(opinion="ok"), db=MagicMock(),
                current_user=_user(role="admin"),
            )
        assert svc.approve_task.call_args.kwargs["standalone"] is True

    def test_approve_endpoint_passes_standalone_false_for_user(self):
        from app.api.v1 import approval as ap

        svc = MagicMock()
        svc.approve_task.return_value = MagicMock(
            id=1, status="approved", current_level=1, title="t", entity_type="fund"
        )
        with patch.object(ap, "ApprovalWorkflowService", return_value=svc), patch.object(
            ap, "is_admin", return_value=False
        ), patch.object(ap, "_notify_submitter"):
            ap.approve_task(
                1, ap.ApprovalActionRequest(opinion="ok"), db=MagicMock(),
                current_user=_user(role="user"),
            )
        assert svc.approve_task.call_args.kwargs["standalone"] is False

    def test_reject_endpoint_passes_standalone_for_admin(self):
        from app.api.v1 import approval as ap

        svc = MagicMock()
        svc.reject_task.return_value = MagicMock(
            id=1, status="rejected", current_level=1, title="t", entity_type="fund"
        )
        with patch.object(ap, "ApprovalWorkflowService", return_value=svc), patch.object(
            ap, "is_admin", return_value=True
        ), patch.object(ap, "_notify_submitter"):
            ap.reject_task(
                1, ap.ApprovalActionRequest(opinion="no"), db=MagicMock(),
                current_user=_user(role="admin"),
            )
        assert svc.reject_task.call_args.kwargs["standalone"] is True

    def test_reject_endpoint_passes_standalone_false_for_user(self):
        from app.api.v1 import approval as ap

        svc = MagicMock()
        svc.reject_task.return_value = MagicMock(
            id=1, status="rejected", current_level=1, title="t", entity_type="fund"
        )
        with patch.object(ap, "ApprovalWorkflowService", return_value=svc), patch.object(
            ap, "is_admin", return_value=False
        ), patch.object(ap, "_notify_submitter"):
            ap.reject_task(
                1, ap.ApprovalActionRequest(opinion="no"), db=MagicMock(),
                current_user=_user(role="user"),
            )
        assert svc.reject_task.call_args.kwargs["standalone"] is False


# ══════════════════════════════════════════════════════════════════
# 7. 审批提交校验实体归属（P1-2）
# ══════════════════════════════════════════════════════════════════


class TestApprovalSubmitEntityOwnership:
    def _call(self, entity_type, entity_id=1, visible=None):
        from app.api.v1 import approval as ap

        db = MagicMock()
        with patch(
            "app.core.data_permission.apply_scope_filter"
        ) as scope_mock:
            scope_mock.return_value.first.return_value = visible
            ap._assert_entity_submittable(db, _user(role="user"), entity_type, entity_id)
            return scope_mock

    def test_unknown_entity_type_is_skipped(self):
        """未登记的实体类型保持向后兼容（不查库、不抛错）。"""
        from app.api.v1 import approval as ap

        db = MagicMock()
        ap._assert_entity_submittable(db, _user(role="user"), "unknown_thing", 1)
        db.query.assert_not_called()

    def test_visible_entity_passes(self):
        marker = object()
        self._call("fund", visible=marker)

    def test_invisible_entity_raises_404(self):
        from app.api.v1 import approval as ap

        db = MagicMock()
        with patch("app.core.data_permission.apply_scope_filter") as scope_mock:
            scope_mock.return_value.first.return_value = None
            with pytest.raises(HTTPException) as ei:
                ap._assert_entity_submittable(db, _user(role="user"), "project", 9)
        assert ei.value.status_code == 404

    @pytest.mark.parametrize(
        "entity_type",
        ["fund", "funds", "project", "projects", "school", "schools",
         "supported_village", "village", "villages", "policy", "policies", "rural_work"],
    )
    def test_all_registered_entity_types_resolve(self, entity_type):
        """注册表中的每个类型都能解析到模型（防止模块路径写错）。"""
        import importlib

        from app.api.v1.approval import _APPROVAL_ENTITY_MODELS

        module_path, class_name = _APPROVAL_ENTITY_MODELS[entity_type]
        model = getattr(importlib.import_module(module_path), class_name)
        assert model is not None

    def test_submit_endpoint_checks_entity_before_service(self):
        from app.api.v1 import approval as ap

        svc = MagicMock()
        svc.submit_approval.return_value = None
        with patch.object(ap, "ApprovalWorkflowService", return_value=svc), patch.object(
            ap, "_assert_entity_submittable"
        ) as guard:
            with pytest.raises(HTTPException):
                ap.submit_approval(
                    ap.SubmitApprovalRequest(
                        entity_type="fund", entity_id=3, change_data={"a": 1}
                    ),
                    db=MagicMock(),
                    current_user=_user(role="user"),
                )
        guard.assert_called_once()
