"""app.api.v1.projects 覆盖率攻坚测试（补充 test_projects_api.py 未覆盖分支）

覆盖点：
- Pydantic 校验器：ProjectCreate/ProjectUpdate/TaskCreate 日期格式非法
- _batch_get_fund_health_fields：project_id 无法转 int 跳过
- export_projects：openpyxl 数据行写入
- create_project：Diff 留痕异常、detail_parts 负责单位、缓存失效异常
- _convert_update_fields 预算转换、_apply_project_changes 未知字段
- _log_project_update_audit Diff 异常、_invalidate_project_cache 异常
- delete_project：Diff 留痕异常 + 缓存失效异常
- update_project_task：due_date 转换、HTTPException 透传
- download_project_template：模板下载
- _detect_import_headers / _extract_row_data / _build_import_project 编码冲突重建
- _process_import_rows：空行/示例行/无名行/失败行
- import_projects：提交失败 500
- upload_project_files：文件大小预检超限 400
- delete_project_file：无权限 403
- download/preview：文件不存在 404、预览 MIME 回退
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.projects as pj
from app.api.v1.projects import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate
from app.core.exceptions import NotFoundException


# ==================== 公共设施 ====================


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "limit", "offset"):
        getattr(q, attr).return_value = q
    q.options.return_value = q  # _get_project_or_404 走 .options(selectinload(...)).first() 链
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


def _db(*queries):
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


def _user(**kw):
    defaults = dict(
        id=1, username="admin", role="admin", is_superuser=True,
        organization_id=1, permissions_list=["*"], full_name="管理员",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ==================== Pydantic 校验器 ====================


class TestSchemaValidators:
    def test_project_create_bad_date(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            ProjectCreate(name="X", start_date="not-a-date")

    def test_project_update_bad_date(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            ProjectUpdate(end_date="2026/01/01")

    def test_task_create_bad_due_date(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            TaskCreate(name="t", due_date="bad")

    def test_task_create_good_due_date(self):
        t = TaskCreate(name="t", due_date="2026-01-01")
        assert t.due_date == "2026-01-01"


# ==================== _batch_get_fund_health_fields ====================


class TestBatchFundHealth:
    def test_invalid_project_id_skipped(self):
        good = SimpleNamespace(
            project_id=1, amount=100.0, approved_amount=90.0,
            used_amount=50.0, deviation_rate=5.0, health_score=85,
        )
        bad = SimpleNamespace(project_id="not-an-int")
        db = _db(_q(all=[good, bad]))
        result = pj._batch_get_fund_health_fields(db, [1])
        assert 1 in result


# ==================== export_projects 数据行 ====================


class TestExportProjects:
    async def test_export_with_rows(self):
        p = SimpleNamespace(
            code="PRJ-1", name="项目一", type="infrastructure", status="in_progress",
            budget=Decimal("10.5"), invested_amount=None, progress=50,
            responsible_person=None, responsible_unit="某单位",
            start_date=date(2026, 1, 1), end_date=None,
        )
        db = _db(_q(all=[p]))
        resp = await pj.export_projects(
            keyword=None, project_type=None, export_status=None,
            current_user=_user(), db=db,
        )
        assert "spreadsheetml" in resp.media_type


# ==================== create_project 分支 ====================


class TestCreateProject:
    async def test_diff_exception_and_cache_invalidate_exception(self):
        db = _db(_q(first=None))  # 编码唯一性检查 → 无重复
        data = ProjectCreate(
            name="新项目", type="infrastructure", responsible_unit="某单位",
            budget=10.0, start_date="2026-01-01", end_date="2026-06-01",
        )
        with (
            patch.object(pj, "AuditLogService") as m_als,
            patch.object(pj, "AuditEnhancementService") as m_aes,
            patch.object(pj, "write_work_log"),
            patch.object(pj, "safe_commit"),
            patch.object(pj, "get_client_ip", return_value="127.0.0.1"),
            patch(
                "app.api.v1.data.data.dashboard.invalidate_dashboard_cache",
                side_effect=RuntimeError("cache boom"),
            ),
        ):
            m_als.return_value.log = AsyncMock()
            m_aes.record_changes.side_effect = RuntimeError("diff boom")
            result = await pj.create_project(data, MagicMock(), _user(), db)
        # create_project 返回 success_response 信封: data.name
        assert result["data"]["name"] == "新项目"


# ==================== 更新辅助函数 ====================


class TestUpdateHelpers:
    def test_convert_budget_to_decimal(self):
        out = pj._convert_update_fields({"budget": 100.5, "start_date": "2026-01-01"})
        assert out["budget"] == Decimal("100.5")
        assert out["start_date"] == date(2026, 1, 1)

    def test_convert_invested_amount_to_decimal(self):
        # 覆盖 projects.py:934 —— invested_amount 金额量化
        out = pj._convert_update_fields({"invested_amount": 250.75})
        assert out["invested_amount"] == Decimal("250.75")

    def test_apply_changes_unknown_field_skipped(self):
        project = SimpleNamespace(name="旧名")
        changed = pj._apply_project_changes(project, {"unknown_field": 1, "name": "新名"})
        assert changed == ["name"]
        assert project.name == "新名"
        assert not hasattr(project, "unknown_field")

    def test_invalidate_cache_exception_degrades(self):
        with patch(
            "app.api.v1.data.data.dashboard.invalidate_dashboard_cache",
            side_effect=RuntimeError("boom"),
        ):
            pj._invalidate_project_cache()  # 不抛异常

    async def test_log_update_audit_diff_exception(self):
        with (
            patch.object(pj, "AuditLogService") as m_als,
            patch.object(pj, "AuditEnhancementService") as m_aes,
            patch.object(pj, "write_work_log"),
            patch.object(pj, "get_client_ip", return_value="127.0.0.1"),
        ):
            m_als.return_value.log = AsyncMock()
            m_aes.record_changes.side_effect = RuntimeError("diff boom")
            await pj._log_project_update_audit(
                MagicMock(), MagicMock(), SimpleNamespace(id=1, name="项目"),
                1, ["name"], {}, _user(),
            )


# ==================== delete_project 分支 ====================


class TestDeleteProject:
    async def test_diff_and_cache_exceptions(self):
        project = SimpleNamespace(
            id=1, name="项目", status="approved", created_by=1, is_active=True,
        )
        db = _db(_q(first=project))
        with (
            patch.object(pj, "AuditLogService") as m_als,
            patch.object(pj, "AuditEnhancementService") as m_aes,
            patch.object(pj, "write_work_log"),
            patch.object(pj, "safe_commit"),
            patch.object(pj, "get_client_ip", return_value="127.0.0.1"),
            patch.object(pj, "_project_to_diff_dict", return_value={}),
            patch(
                "app.api.v1.data.data.dashboard.invalidate_dashboard_cache",
                side_effect=RuntimeError("cache boom"),
            ),
        ):
            m_als.return_value.log = AsyncMock()
            m_aes.record_changes.side_effect = RuntimeError("diff boom")
            result = await pj.delete_project(1, MagicMock(), _user(), db)
        # delete_project 返回 success_response 信封: 断言 message 与 code
        assert result["message"] == "删除成功"
        assert result["code"] == 200
        assert project.status == "cancelled"


# ==================== update_project_task 分支 ====================


class TestUpdateProjectTask:
    async def test_due_date_conversion(self):
        project = SimpleNamespace(id=1, created_by=1)
        task = SimpleNamespace(
            id=5, project_id=1, name="旧", description=None, status="pending",
            priority=0, assignee=None, due_date=None, created_at=None, updated_at=None,
        )
        db = _db(_q(first=project), _q(first=task))
        data = TaskUpdate(due_date="2026-03-01")
        with patch.object(pj, "safe_commit"), patch.object(pj, "check_record_access"):
            result = await pj.update_project_task(1, 5, data, _user(), db)
        # 统一 envelope：任务数据在 data 键内
        assert result["data"]["due_date"] == "2026-03-01"

    async def test_http_exception_passthrough(self):
        project = SimpleNamespace(id=1, created_by=1)
        task = SimpleNamespace(
            id=5, project_id=1, name="旧", description=None, status="pending",
            priority=0, assignee=None, due_date=None, created_at=None, updated_at=None,
        )
        db = _db(_q(first=project), _q(first=task))
        with (
            patch.object(pj, "safe_commit", side_effect=HTTPException(status_code=400)),
            patch.object(pj, "check_record_access"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pj.update_project_task(1, 5, TaskUpdate(name="新"), _user(), db)
        assert exc_info.value.status_code == 400


# ==================== 导入模板下载 ====================


class TestDownloadTemplate:
    async def test_template_download(self):
        with patch("app.services.excel_template_service.ExcelTemplateService") as m_svc:
            m_svc.return_value.generate_project_template.return_value = b"PK\x03\x04"
            resp = await pj.download_project_template(current_user=_user())
        assert "spreadsheetml" in resp.media_type


# ==================== 导入解析辅助 ====================


class TestImportHelpers:
    def test_detect_headers(self):
        ws = SimpleNamespace(
            iter_rows=lambda **kw: iter([("项目名称", "项目类型", "预算金额")])
        )
        ri, matched = pj._detect_import_headers(ws)
        assert ri == 1
        assert matched == {0: "name", 1: "type", 2: "budget"}

    def test_extract_row_data_strips_strings(self):
        data = pj._extract_row_data(("  项目甲  ", None), {0: "name", 1: "type"})
        assert data == {"name": "项目甲"}

    def test_build_import_project_regenerates_duplicate_code(self):
        db = _db(_q(first=SimpleNamespace(id=99)))  # 编码已存在
        project = pj._build_import_project(db, {"name": "新项目", "code": "DUP"}, _user())
        assert project.code != "DUP"
        assert project.code.startswith("PRJ-")

    def test_process_import_rows_all_skip_branches(self):
        rows = [
            (None, None),               # 空行 → continue
            ("XX村饮水安全工程",),       # 示例行 → continue
            ("", "x"),                   # 无名称（其他列有值）→ continue
            ("坏行",),                   # 构建失败 → failed
            ("好项目",),                 # 成功
        ]
        ws = SimpleNamespace(iter_rows=lambda **kw: iter(rows))
        with patch.object(
            pj, "_build_import_project",
            side_effect=[RuntimeError("build boom"), SimpleNamespace()],
        ):
            created, failed, errors = pj._process_import_rows(
                MagicMock(), ws, 1, {0: "name"}, _user()
            )
        assert created == 1
        assert failed == 1
        assert errors[0]["row"] == 5
        assert errors[0]["name"] == "坏行"


# ==================== import_projects 提交失败 ====================


class TestImportProjects:
    async def test_commit_failure_500(self):
        with (
            patch.object(pj, "_check_import_rate_limit", new_callable=AsyncMock),
            patch.object(pj, "_parse_import_excel", new_callable=AsyncMock, return_value=MagicMock()),
            patch.object(pj, "_detect_import_headers", return_value=(2, {0: "name"})),
            patch.object(pj, "_process_import_rows", return_value=(1, 0, [])),
            patch.object(pj, "safe_commit", side_effect=RuntimeError("db err")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pj.import_projects(MagicMock(), "incremental", None, _user(), MagicMock())
        assert exc_info.value.status_code == 500
        assert "数据提交失败" in exc_info.value.detail


# ==================== 文件上传/删除/下载/预览 ====================


class TestFileEndpoints:
    async def test_upload_oversize_precheck_400(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.MAX_FILE_SIZE", 10)
        big_file = SimpleNamespace(size=11, filename="big.zip")
        with (
            patch.object(pj, "_get_project_or_404", return_value=SimpleNamespace(id=1)),
            patch.object(pj, "_can_modify_project", return_value=True),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pj.upload_project_files(1, "research", [big_file], _user(), MagicMock())
        assert exc_info.value.status_code == 400
        assert "限制" in exc_info.value.detail

    async def test_delete_file_forbidden_403(self):
        with (
            patch.object(pj, "_get_project_or_404", return_value=SimpleNamespace(id=1)),
            patch.object(pj, "_can_modify_project", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pj.delete_project_file(1, 9, _user(role="user", is_superuser=False), MagicMock())
        assert exc_info.value.status_code == 403

    async def test_download_file_not_found(self):
        db = _db(_q(first=None))
        with (
            patch.object(pj, "_get_project_or_404", return_value=SimpleNamespace(id=1)),
            pytest.raises(NotFoundException),
        ):
            await pj.download_project_file(1, 9, _user(), db)

    async def test_preview_file_not_found(self):
        db = _db(_q(first=None))
        with (
            patch.object(pj, "_get_project_or_404", return_value=SimpleNamespace(id=1)),
            pytest.raises(NotFoundException),
        ):
            await pj.preview_project_file(1, 9, _user(), db)

    async def test_preview_mime_fallback(self, tmp_path):
        f = tmp_path / "blob"
        f.write_bytes(b"\x00\x01")
        pf = SimpleNamespace(id=9, project_id=1, filepath=str(f), filename="file.unknownext")
        db = _db(_q(first=pf))
        with patch.object(pj, "_get_project_or_404", return_value=SimpleNamespace(id=1)):
            resp = await pj.preview_project_file(1, 9, _user(), db)
        assert resp.media_type == "application/octet-stream"

    def test_detect_headers_none_when_no_match(self):
        """无任何匹配表头 → (None, {})（1634 行）"""
        ws = SimpleNamespace(iter_rows=lambda **kw: iter([("foo", "bar", "baz")]))
        ri, matched = pj._detect_import_headers(ws)
        assert ri is None
        assert matched == {}


class TestImportNoHeader:
    async def test_no_valid_header_400(self):
        """未找到有效表头 → 400（1753 行）"""
        with (
            patch.object(pj, "_check_import_rate_limit", new_callable=AsyncMock),
            patch.object(pj, "_parse_import_excel", new_callable=AsyncMock, return_value=MagicMock()),
            patch.object(pj, "_detect_import_headers", return_value=(None, {})),
            pytest.raises(HTTPException) as exc_info,
        ):
            await pj.import_projects(MagicMock(), "incremental", None, _user(), MagicMock())
        assert exc_info.value.status_code == 400
        assert "未找到有效表头" in exc_info.value.detail
