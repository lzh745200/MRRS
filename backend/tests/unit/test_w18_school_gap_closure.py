"""W18 收口：app/api/v1/school.py 覆盖率缺口（statistics / 审批回写 / 附件 / 一校一档 PDF）。

补充既有 school 测试未命中的可覆盖分支（coverage 实测）：
  69-75       _apply_scholarship_approval_result 审批通过 → pending 资助记录置 approved
  670->676   下载附件时所属学校行已不存在 → 跳过数据权限校验
  698->704   删除附件时所属学校行已不存在 → 跳过数据权限校验
  759->764   include_deleted=True → 不加 is_active 过滤（管理员可见已软删）
  861->864   创建学校 type 为空 → 跳过枚举转换
  938->942   更新学校编码无冲突 → 不抛 409
  1195->1197 创建帮扶项目 phase 为空 → 跳过枚举转换
  1557-1578  一校一档 PDF：404（不存在/越权）/ 生成失败 500 / 成功下载

注意：本文件只补学校 API 自身的分支；统计端点与其余端点由既有 school 测试覆盖
（tests/unit/test_school_api*.py / test_school_cov.py / test_api_schools_full.py）。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.school as sch
from app.models.school import ScholarshipStatus, SupportStatus


def _user(**kw):
    defaults = dict(
        id=1, username="admin", role="admin", is_superuser=True, organization_id=1,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit"):
        getattr(q, attr).return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    q.count.return_value = kw.get("count", 0)
    return q


def _school(id_=1, name="某校"):
    school = MagicMock()
    school.id = id_
    school.name = name
    school.code = "OLD"
    school.district = "某县"
    school.support_status = SupportStatus.ACTIVE
    school.to_dict.return_value = {"id": id_, "name": name}
    return school


# ==================== 审批回写处理器 ====================


class TestScholarshipApprovalHandler:
    def test_approved_pending_student_updated(self):
        """审批通过 → pending 资助记录置 approved（69-75）。"""
        student = SimpleNamespace(status=ScholarshipStatus.PENDING)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = student

        sch._apply_scholarship_approval_result(
            db, SimpleNamespace(status="approved", entity_id=9)
        )
        assert student.status == ScholarshipStatus.APPROVED

    def test_approved_missing_student_noop(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert sch._apply_scholarship_approval_result(
            db, SimpleNamespace(status="approved", entity_id=9)
        ) is None


# ==================== 附件下载/删除：学校行已不存在 ====================


class TestAttachmentSchoolMissing:
    async def test_download_attachment_skips_permission_when_school_missing(self):
        att = SimpleNamespace(
            id=5, school_id=99, file_path="/tmp/w18-secret.pdf",
            file_name="w18-secret.pdf", file_type=None,
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [att, None]

        with patch.object(sch, "_validate_file_path", return_value="/tmp/w18-secret.pdf"), \
                patch.object(sch, "require_data_permission") as mock_perm:
            resp = await sch.download_attachment(5, _user(), db)

        mock_perm.assert_not_called()
        assert resp.media_type == "application/octet-stream"

    async def test_delete_attachment_skips_permission_when_school_missing(self):
        att = SimpleNamespace(id=5, school_id=99, file_path="/tmp/w18-secret.pdf")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [att, None]

        with patch.object(sch, "_validate_file_path", return_value="/tmp/w18-secret.pdf"), \
                patch.object(sch, "require_data_permission") as mock_perm, \
                patch.object(sch.os, "remove") as mock_remove, \
                patch.object(sch, "safe_commit"):
            result = await sch.delete_attachment(5, _user(), db)

        mock_perm.assert_not_called()
        mock_remove.assert_called_once_with("/tmp/w18-secret.pdf")
        db.delete.assert_called_once_with(att)
        assert result["code"] == 200


# ==================== 列表：include_deleted=True ====================


class TestListSchoolsIncludeDeleted:
    async def test_include_deleted_skips_active_filter(self):
        """include_deleted=True（管理员）→ 不加 is_active=True 过滤（759->764）。"""
        db = MagicMock()
        q = _q(count=0, all=[])
        db.query.return_value = q
        scope = MagicMock()
        scope.filter_by_org_ids = MagicMock(side_effect=lambda query, *a, **k: query)

        result = await sch.list_schools(
            page=1, page_size=20, keyword=None, name=None, type=None,
            support_status=None, supportStatus=None, include_deleted=True,
            current_user=_user(), data_scope=scope, db=db,
        )
        assert result["data"]["total"] == 0


# ==================== 创建/更新：枚举与编码唯一性分支 ====================


class TestCreateUpdateSchoolBranches:
    async def test_create_school_without_type_skips_enum_conversion(self):
        """type 为空（None）→ 跳过枚举转换（861->864）。"""
        db = MagicMock()
        db.refresh = MagicMock()
        # 编码唯一性查询：无同编码记录
        db.query.return_value.filter.return_value.first.return_value = None
        data = sch.SchoolCreate(name="无类型学校", code="W18-NOTYPE", type=None)

        with patch.object(sch, "safe_commit"), \
                patch.object(sch, "write_work_log"), \
                patch.object(sch, "_invalidate_school_list_cache", AsyncMock()), \
                patch("app.api.v1.data.data.dashboard.invalidate_dashboard_cache"):
            result = await sch.create_school(data, _user(), db)

        # W27：创建即时生效，不再返回伪审批任务
        assert "approval_task_id" not in result["data"]
        db.add.assert_called_once()

    async def test_update_school_code_no_conflict(self):
        """更新编码且全局唯一 → 不抛 409（938->942），正常写回。"""
        school = _school()
        db = MagicMock()
        db.query = MagicMock(side_effect=[_q(first=school), _q(first=None)])
        data = sch.SchoolUpdate(name="新校名", code="NEW-CODE")

        with patch.object(sch, "require_data_permission"), \
                patch.object(sch, "safe_commit"), \
                patch.object(sch, "write_work_log"), \
                patch.object(sch, "_invalidate_school_list_cache", AsyncMock()), \
                patch("app.api.v1.data.data.dashboard.invalidate_dashboard_cache"):
            result = await sch.update_school(1, data, _user(), db)

        # W27：管理员直通，不再返回伪审批任务
        assert "approval_task_id" not in result["data"]
        assert school.name == "新校名"


# ==================== 帮扶项目：phase 为空 ====================


class TestCreateProjectBranch:
    async def test_create_project_without_phase_skips_enum_conversion(self):
        """phase 为空 → 跳过 ProjectPhase 转换（1195->1197）。"""
        db = MagicMock()
        db.refresh = MagicMock()
        data = sch.SchoolProjectCreate(name="无阶段项目", phase=None)

        with patch.object(sch, "_get_school_and_check_permission"), \
                patch.object(sch, "safe_commit"), \
                patch.object(sch, "submit_entity_change_approval", return_value=9):
            result = await sch.create_project(1, data, _user(), db)

        assert result["data"]["approval_task_id"] == 9
        db.add.assert_called_once()


# ==================== 一校一档 PDF ====================


class TestExportSchoolDossier:
    def _db(self, school):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = school
        return db

    async def test_dossier_school_not_found_404(self):
        with pytest.raises(HTTPException) as exc:
            await sch.export_school_dossier(1, _user(), self._db(None))
        assert exc.value.status_code == 404

    async def test_dossier_access_denied_404(self):
        """记录存在但数据域不可见 → 统一 404（不暴露存在性差异）。"""
        school = SimpleNamespace(
            id=1, name="越权学校", created_by=99, organization_id=2,
        )
        with patch("app.core.data_permission.check_record_access", return_value=False), \
                pytest.raises(HTTPException) as exc:
            await sch.export_school_dossier(1, _user(), self._db(school))
        assert exc.value.status_code == 404

    async def test_dossier_render_failure_500(self):
        school = SimpleNamespace(
            id=1, name="某校", created_by=1, organization_id=1,
        )
        service = MagicMock()
        service.render_school_pdf.side_effect = RuntimeError("pdf boom")
        with patch("app.core.data_permission.check_record_access", return_value=True), \
                patch("app.services.dossier_service.DossierService", return_value=service), \
                pytest.raises(HTTPException) as exc:
            await sch.export_school_dossier(1, _user(), self._db(school))
        assert exc.value.status_code == 500
        assert "档案册生成失败" in exc.value.detail

    async def test_dossier_success_streams_pdf_and_audits(self):
        school = SimpleNamespace(
            id=1, name="某校", created_by=1, organization_id=1,
        )
        service = MagicMock()
        service.render_school_pdf.return_value = b"%PDF-1.4 w18"
        with patch("app.core.data_permission.check_record_access", return_value=True), \
                patch("app.services.dossier_service.DossierService", return_value=service), \
                patch("app.services.dossier_service.record_dossier_audit") as mock_audit:
            resp = await sch.export_school_dossier(1, _user(), self._db(school))

        assert resp.media_type == "application/pdf"
        assert "attachment" in resp.headers["content-disposition"]
        mock_audit.assert_called_once()
        assert service.render_school_pdf.call_args.args[0] is school
