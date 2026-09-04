"""services/utils/models 覆盖率尾部缺口补充测试（任务 #21）。

针对各模块剩余的防御/边缘分支补齐覆盖：
- models: permission_pack.menu_keys_list、export_task.is_downloadable(naive tz)
- utils: db_error_handler 磁盘满载 OperationalError
- services: resource_limiter.check_rate_limit、organization_code_service(prefix)、
  system_config_service 全局函数、package_record_validator 解析/校验分支、
  report_export_service 金额格式化/查询失败/渲染/PDF 字体、machine_code_service
  空归一化通行码、user_permission_service 未绑定组织管理员、excel_importer
  示例行跳过/归属字段、user_cascade_delete 留痕表置空失败、data_sync 幽灵表告警/
  敏感表拦截、approval_workflow 角色节点/回写失败/重试缺任务、recommendation 收入值异常
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import Integer
from sqlalchemy.exc import OperationalError

from app.models.approval import ApprovalStatus
from app.models.export_task import ExportStatus, ExportTask
from app.models.permission_pack import PermissionPack
from app.services.ai.recommendation_service import RecommendationService
from app.services.approval_workflow_service import ApprovalWorkflowService
from app.services.excel_importer_service import ExcelImporterService
from app.services.machine_code_service import MachineCodeService
from app.services.organization_code_service import OrganizationCodeService
from app.services.package_record_validator import (
    _parse_date_string,
    _validate_numeric,
    validate_records,
)
from app.services.report_export_service import ReportExportService, _fmt_amount
from app.services.resource_limiter import check_rate_limit
from app.services.user_cascade_delete_service import UserCascadeDeleteService
from app.services.user_permission_service import UserPermissionService
from app.utils.db_error_handler import _handle_db_exception
import app.services.system_config_service as scs
from app.services.data_sync_service import DataSyncService


# ── models ────────────────────────────────────────────────────────────────
class TestPermissionPackMenuKeys:
    def test_menu_keys_list_variants(self):
        p = PermissionPack(name="pack")
        p.menu_keys = None
        assert p.menu_keys_list == []          # 38-39 falsy
        p.menu_keys = ""
        assert p.menu_keys_list == []          # 38-39 空串
        p.menu_keys = '["a", "b"]'
        assert p.menu_keys_list == ["a", "b"]  # 40-41 合法 JSON
        p.menu_keys = "not-json"
        assert p.menu_keys_list == []          # 42-43 非法 JSON


class TestExportTaskDownloadable:
    def test_naive_expires_gets_utc(self):
        t = ExportTask(status=ExportStatus.COMPLETED.value)
        # naive（无时区）未来时间 → 116-117 补 UTC；118 未过期 → 120 True
        t.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        assert t.is_downloadable is True

    def test_not_completed(self):
        t = ExportTask(status=ExportStatus.PENDING.value)
        assert t.is_downloadable is False


# ── utils ─────────────────────────────────────────────────────────────────
class TestDbErrorHandlerDisk:
    def test_operational_disk_full_503(self):
        exc = OperationalError(
            "INSERT INTO t VALUES (1)", None,
            sqlite3.OperationalError("database or disk is full"),
        )
        with pytest.raises(HTTPException) as ei:
            _handle_db_exception("create_thing", None, exc)
        assert ei.value.status_code == 503
        assert "磁盘空间不足" in ei.value.detail  # 行 54


# ── services: 简单直接 ─────────────────────────────────────────────────────
class TestResourceLimiterFunc:
    def test_check_rate_limit_allows(self):
        # 唯一 key，避免与其它测试共享配额状态
        assert check_rate_limit("tail_gap_key_unique_xyz", 5, 60) is True  # 166-167


class TestOrganizationCodePrefix:
    def test_generate_code_with_prefix(self):
        svc = OrganizationCodeService()
        code = svc.generate_code(org_name="测试单位", prefix="ORG")
        assert code.startswith("ORG-")  # 34-35


class TestGlobalConfigFuncs:
    def test_uses_global_service_when_set(self):
        fake = MagicMock()
        fake.get.return_value = "VAL"
        with patch.object(scs, "_global_config_service", fake):
            assert scs.get_config("k") == "VAL"      # 35-36
            scs.set_config("k", "v2", "desc")         # 46-48
            fake.set.assert_called_once_with("k", "v2", "desc")
            scs.delete_config("k")                    # 58-60
            fake.delete.assert_called_once_with("k")


class TestPackageRecordValidator:
    def test_parse_date_empty(self):
        assert _parse_date_string("   ") is None            # 138-139

    def test_parse_date_compact_invalid(self):
        assert _parse_date_string("20241345") is None       # 143 ValueError → 144-145

    def test_parse_date_loose_invalid(self):
        assert _parse_date_string("2024-13-45") is None     # 149 ValueError → 150-151

    def test_numeric_bool_rejected(self):
        v, e, c = _validate_numeric("amount", True, Integer())
        assert v is None and e and c is False               # 178-179

    def test_numeric_bad_string(self):
        v, e, c = _validate_numeric("amount", "abc", Integer())
        assert v is None and e                              # 187-188

    def test_numeric_other_type(self):
        v, e, c = _validate_numeric("amount", [1, 2], Integer())
        assert v is None and e                              # 190-191

    def test_numeric_float_not_integer(self):
        v, e, c = _validate_numeric("count", 3.5, Integer())
        assert v is None and "整数" in e                     # 198-199

    def test_numeric_float_to_int(self):
        v, e, c = _validate_numeric("count", 3.0, Integer())
        assert v == 3 and c is True                         # 200-201

    def test_validate_records_date_non_string(self):
        res = validate_records("projects", [{"name": "项目X", "start_date": 12345}])
        # start_date 为非字符串/非日期类型 → 279-281 记原因并拒绝
        assert res["rejected"]
        assert any("日期格式无法识别" in r for item in res["rejected"] for r in item["reasons"])


class TestReportExportEdge:
    def test_fmt_amount_errors(self):
        assert _fmt_amount("abc") == "0.00"   # ValueError → 42-43
        assert _fmt_amount(None) == "0.00"    # TypeError → 42-43

    def test_fund_detail_query_failure(self):
        svc = ReportExportService()
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        data = svc.generate_fund_detail_report_data(db, 2024)
        assert data["sections"][0]["table"] is None  # 140-146

    def test_project_progress_query_failure(self):
        svc = ReportExportService()
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        data = svc.generate_project_progress_report_data(db, 2024)
        assert data["sections"][0]["table"] is None  # 202-208

    def test_iter_render_items_empty_table(self):
        data = {"sections": [{"title": "t", "paragraphs": [], "table": {"rows": []}}]}
        items = list(ReportExportService._iter_render_items(data))
        assert ("paragraph", "暂无数据。") in items  # 316

    def test_export_pdf_registers_font_when_absent(self):
        svc = ReportExportService()
        from reportlab.pdfbase import pdfmetrics
        data = {"title": "T", "sections": [{"title": "s", "paragraphs": ["p"], "table": None}]}
        with patch.object(pdfmetrics, "getRegisteredFontNames", return_value=[]):
            out = svc.export_pdf("summary", data)  # 380-381 注册字体
        assert out.startswith(b"%PDF")


class TestMachineCodeVerify:
    def test_empty_after_normalize_returns_none(self, real_db_session):
        svc = MachineCodeService(real_db_session)
        # 全连字符 → strip 后 "---"，normalized 为空 → 453-458 warning + None
        assert svc.verify_pass_code("---", "machine_code_xyz") is None


class TestUserPermissionDataScope:
    def test_admin_without_org_returns_true(self):
        svc = UserPermissionService(MagicMock())
        fake_user = SimpleNamespace(role="admin", organization_id=None)
        with patch.object(svc, "_get_user", return_value=fake_user):
            assert svc.check_user_data_scope(1) is True  # 463-464


class TestExcelImporterEdge:
    def test_is_skippable_row_example_text(self):
        # 199-203：某单元格含 "示例行" 关键词
        assert ExcelImporterService._is_skippable_row(["数据", "这是示例行"], []) is True

    def test_create_village_sets_ownership(self, real_db_session):
        user = SimpleNamespace(id=7, organization_id=3)
        svc = ExcelImporterService(real_db_session, current_user=user)
        v = svc._create_village({"village_name": "新村"})
        assert v.organization_id == 3   # 552
        assert v.created_by == 7        # 553


# ── services: 需 mock 编排 ─────────────────────────────────────────────────
class TestUserCascadePreserveFailure:
    def test_preserve_audit_table_update_failure_rolls_back(self):
        db = MagicMock()
        user = MagicMock()
        user.id = 1
        db.query.return_value.filter.return_value.first.return_value = user
        m_master = MagicMock()
        m_master.fetchall.return_value = [("approval_records",)]
        m_fk = MagicMock()
        # (id, seq, table, from, to, on_update, on_delete, match)
        m_fk.fetchall.return_value = [
            (0, 0, "users", "created_by", "id", "NO ACTION", "SET NULL", "NONE")
        ]
        m_info = MagicMock()
        # (cid, name, type, notnull, dflt, pk)
        m_info.fetchall.return_value = [
            (0, "id", "INTEGER", 1, None, 1),
            (1, "created_by", "INTEGER", 0, None, 0),
        ]
        db.execute.side_effect = [m_master, m_fk, m_info, RuntimeError("no such column")]
        svc = UserCascadeDeleteService(db)
        result = svc.delete_user_cascade(1)
        assert result["success"] is True
        db.rollback.assert_called()  # 122-124


class TestDataSyncEdge:
    def test_ghost_table_warns_and_ignored(self):
        with patch("app.services.data_sync_service._SYNC_TABLE_LABELS",
                   {"ghost_table_xyz": "幽灵表", "supported_villages": "帮扶村"}):
            svc = DataSyncService()
        assert "ghost_table_xyz" not in svc.syncable_tables  # 109-113
        assert "supported_villages" in svc.syncable_tables

    async def test_import_package_blocks_sensitive_table(self, tmp_path):
        svc = DataSyncService()
        # 人为配置错误：敏感表进入可同步集，验证硬禁止逻辑
        svc.syncable_tables = {"users": "用户"}
        pkg = tmp_path / "pkg.zip"
        pkg.write_bytes(b"x")  # 仅需 exists()
        mock_db = MagicMock()
        with patch.object(
            svc, "_load_import_package",
            new=AsyncMock(return_value={
                "export_info": {"package_name": "p"},
                "data": {"users": [{"id": 1}]},
            }),
        ), patch.object(svc, "_get_db_context") as ctx:
            ctx.return_value.__enter__.return_value = mock_db
            result = await svc.import_package(str(pkg))
        assert result["success"] is True
        assert any("禁止导入敏感表: users" in e for e in result["errors"])  # 360-362


class TestApprovalWorkflowEdge:
    def _svc(self):
        return ApprovalWorkflowService(MagicMock())

    def test_approve_role_node_resolved(self):
        svc = self._svc()
        task = MagicMock()
        task.status = ApprovalStatus.PENDING.value
        task.current_approver_id = None
        task.current_level = 0
        node = MagicMock()
        node.level = 1
        node.approver_type = "role"
        node.approver_id = 5
        task.workflow.nodes = [node]
        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "_resolve_role_approver_id", return_value=99) as rr:
            svc.approve_task(1, 7)
        rr.assert_called_once_with(5)          # 490-491
        assert task.current_approver_id == 99

    def test_approve_final_level_apply_failed(self):
        svc = self._svc()
        task = MagicMock()
        task.status = ApprovalStatus.PENDING.value
        task.current_approver_id = None
        task.current_level = 1
        task.workflow.nodes = [MagicMock(level=1)]  # next_level=2 > len=1 → 终态
        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "apply_entity_change", return_value=False):
            svc.approve_task(1, 7)
        assert task.status == ApprovalStatus.APPROVED.value + svc.APPLY_FAILED_SUFFIX  # 498-500

    def test_reject_apply_failed(self):
        svc = self._svc()
        task = MagicMock()
        task.id = 1
        task.status = ApprovalStatus.PENDING.value
        task.current_approver_id = None
        task.current_level = 1
        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "apply_entity_change", return_value=False):
            svc.reject_task(1, 7)
        assert task.status == ApprovalStatus.REJECTED.value + svc.APPLY_FAILED_SUFFIX  # 534-535

    def test_retry_no_task_returns_none(self):
        svc = self._svc()
        with patch.object(svc, "get_task", return_value=None):
            assert svc.retry_apply_entity_change(999) is None  # 547-548


class TestRecommendationIncomeValueError:
    def test_income_value_bad_string_returns_zero(self):
        class MockVillage:
            id = 1
            village_name = "村"

        class MockPop:
            supported_village_id = 1
            population = 5000

        class MockInc:
            supported_village_id = 1
            year = 2025
            per_capita_income_2025 = "非数值"  # float() → ValueError → 227-228

        call = [0]
        db = MagicMock()

        def mq(*args):
            call[0] += 1
            q = MagicMock()
            if call[0] == 1:
                q.filter.return_value.all.return_value = [MockVillage()]
            elif call[0] == 2:
                q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call[0] == 3:
                q.join.return_value.all.return_value = [MockPop()]
            elif call[0] == 4:
                q.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
            elif call[0] == 5:
                q.join.return_value.all.return_value = [MockInc()]
            return q

        db.query.side_effect = mq
        admin = SimpleNamespace(role="super_admin", is_superuser=True, organization_id=None)
        result = RecommendationService.recommend_fund_allocation(db, 1000000, [1], user=admin)
        assert result["allocations"][0]["per_capita_income"] == 0.0
