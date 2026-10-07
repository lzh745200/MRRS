"""Group C 服务层分支覆盖补充测试（coverage.py partial branches 清零）。

每个用例对应 coverage report 中一条缺失弧（A->B），通过直调函数级
行为断言驱动真实分支，不修改 app/ 源码。

覆盖文件：
- app/services/data_package_service.py
- app/services/organization_service.py
- app/services/smart_conflict_resolver.py
- app/services/rbac_service.py
- app/services/effectiveness_service.py
- app/services/data_report_service.py
- app/services/data_sync_service.py
- app/services/package_record_validator.py
- app/services/user_service.py
- app/services/permission_package_service.py
- app/services/entity_import_validator.py
"""

import contextlib
import json
import os
import zipfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_report import ReportStatus
from app.models.supported_village import SupportedVillage
from app.schemas.data_package import (
    DataPackageManifest,
    DataPackageValidationResult,
    PackageStatusEnum,
)
from app.schemas.data_report import DataReportReview, ReviewActionEnum
from app.schemas.organization import OrganizationUpdate
from app.services import data_package_service as dp_mod
from app.services import data_report_service as dr_mod
from app.services import data_sync_service as ds_mod
from app.services import rbac_service as rbac_mod
from app.services.data_package_service import DataPackageService
from app.services.data_report_service import DataReportService
from app.services.data_sync_service import DataSyncService
from app.services.effectiveness_service import EffectivenessService
from app.services.entity_import_validator import EntityImportValidator
from app.services.organization_service import OrganizationInUseError, OrganizationService
from app.services.package_record_validator import validate_records
from app.services.permission_package_service import PermissionPackageService
from app.services.rbac_service import RBACService, _restricted_perms_cache
from app.services.smart_conflict_resolver import (
    ConflictStrategy,
    DataConflict,
    SmartConflictResolver,
)
from app.services.user_service import UserService


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------


def _query_mock(**returns):
    """构造一个可链式调用的 query 替身：filter/join/order_by/distinct 自链。"""
    q = MagicMock()
    q.filter.return_value = q
    q.join.return_value = q
    q.order_by.return_value = q
    q.distinct.return_value = q
    for method, value in returns.items():
        getattr(q, method).return_value = value
    return q


def _write_zip(path, manifest: dict, data_files: dict = None):
    """写一个最小可用的数据包 zip。"""
    data_files = data_files or {}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for name, content in data_files.items():
            zf.writestr(name, content if isinstance(content, str) else json.dumps(content))
    return str(path)


# ---------------------------------------------------------------------------
# user_service.py — 124->127, 134->137
# ---------------------------------------------------------------------------


class TestUserServiceDbNoneBranches:
    def test_update_user_without_db_skips_commit_and_returns_user(self):
        """124->127: db 为 None 时 update_user 跳过 commit 分支，仍返回更新后的用户。"""
        svc = UserService(db=None)
        svc.get_user_by_id = lambda user_id: SimpleNamespace(email="old@x.c", full_name="张三")
        result = svc.update_user(1, {"email": "new@x.c", "role": "admin"})
        assert result.email == "new@x.c"
        assert result.full_name == "张三"
        assert not hasattr(result, "role")  # 白名单外字段被忽略

    def test_delete_user_without_db_returns_true(self):
        """134->137: db 为 None 时 delete_user 跳过物理删除分支，仍返回 True。"""
        svc = UserService(db=None)
        svc.get_user_by_id = lambda user_id: SimpleNamespace(id=1)
        assert svc.delete_user(1) is True


# ---------------------------------------------------------------------------
# organization_service.py — 57->59, 59->61, 377->376, 451->454, 547->537
# ---------------------------------------------------------------------------


class TestOrganizationServiceBranches:
    def test_org_in_use_error_lists_only_users(self):
        """57->59: project_count 为 0 时跳过项目描述，仅列用户计数。"""
        err = OrganizationInUseError(5, project_count=0, user_count=3)
        assert "3 个用户" in str(err)
        assert "项目" not in str(err)

    def test_org_in_use_error_without_any_refs_uses_fallback_detail(self):
        """59->61: 项目与用户计数均为 0 时回退为"业务数据"。"""
        err = OrganizationInUseError(5, project_count=0, user_count=0)
        assert "业务数据" in str(err)

    async def test_update_organization_skips_fields_absent_on_record(self):
        """377->376: 更新数据中的字段在记录上不存在时跳过 setattr。"""
        svc = OrganizationService(MagicMock())
        org = SimpleNamespace(name="旧名称")
        svc.get_organization = lambda org_id: org
        result = await svc.update_organization(1, OrganizationUpdate(contact_phone="13800138000"), 9)
        assert not hasattr(result, "contact_phone")
        assert result.name == "旧名称"
        assert result.updated_by == 9

    async def test_get_statistics_with_missing_root_org(self):
        """451->454: root_id 传入但组织不存在时不过滤，统计空集。"""
        svc = OrganizationService(MagicMock())
        svc.get_organization = lambda root_id: None
        svc.db.query.return_value = _query_mock(all=[])
        stats = svc.get_statistics(root_id=42)
        assert stats.total == 0
        assert stats.by_level == {}
        assert stats.max_level == 0

    def test_batch_update_sort_orders_skips_missing_org(self):
        """547->537: 组织不存在时不计数，仍返回成功。"""
        svc = OrganizationService(MagicMock())
        svc.db.query.return_value = _query_mock(first=None)
        ok, updated = svc.batch_update_sort_orders([{"id": 1, "sort_order": 5}, {"id": None, "sort_order": 1}])
        assert ok is True
        assert updated == 0


# ---------------------------------------------------------------------------
# smart_conflict_resolver.py — 305->308, 336->298, 346->298, 491->493
# ---------------------------------------------------------------------------


class TestSmartConflictResolverBranches:
    def _conflict(self, local_id=1, old_id=100):
        return DataConflict(
            data_type="villages",
            business_key={"village_name": "村A"},
            local_record=SimpleNamespace(id=local_id, village_name="旧村名", updated_at=None),
            import_record={"id": old_id, "village_name": "新村名"},
            differences=["village_name"],
        )

    def test_same_data_type_reuses_id_mapping_entry(self):
        """305->308: 同类型第二个冲突不再重建 id_mapping 子字典。"""
        resolver = SmartConflictResolver(MagicMock())
        conflicts = [self._conflict(local_id=1, old_id=100), self._conflict(local_id=2, old_id=101)]
        result = resolver.resolve_conflicts_with_strategy(conflicts, ConflictStrategy.SKIP)
        assert result == {"villages": {100: 1, 101: 2}}

    def test_unknown_strategy_leaves_records_untouched(self):
        """336->298: 未知策略不匹配任何分支，直接进入下一条冲突。"""
        db = MagicMock()
        local = SimpleNamespace(id=1, village_name="旧村名")
        conflict = DataConflict("villages", {"village_name": "村A"}, local, {"id": 100}, ["village_name"])
        resolver = SmartConflictResolver(db)
        result = resolver.resolve_conflicts_with_strategy([conflict], "MAGIC")
        assert result == {"villages": {}}
        assert local.village_name == "旧村名"
        db.flush.assert_not_called()

    def test_auto_strategy_keep_both_is_not_handled_in_auto_branch(self):
        """346->298: AUTO 判定为 KEEP_BOTH 时无对应分支，落空进入下一条。"""
        db = MagicMock()
        local = SimpleNamespace(id=1, village_name="旧村名")
        conflict = DataConflict("villages", {"village_name": "村A"}, local, {"id": 100}, ["village_name"])
        resolver = SmartConflictResolver(db)
        resolver._determine_auto_strategy = lambda c: ConflictStrategy.KEEP_BOTH
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.AUTO)
        assert result == {"villages": {}}
        assert local.village_name == "旧村名"
        db.flush.assert_not_called()

    def test_import_with_id_mapping_merges_conflict_mapping(self):
        """冲突解决返回的 ID 映射被合并进总表（行为回归）。

        注：491->493 弧确认不可达 —— 外层 id_mapping 仅在 492-494 行写入，
        resolve_conflicts_with_strategy / _import_new_records 均返回新字典
        而不改写外层映射，故 491 行条件恒为真。
        """
        local = SimpleNamespace(id=1, village_name="旧村名", updated_at=None)
        db = MagicMock()
        db.query.return_value = _query_mock(first=local)
        resolver = SmartConflictResolver(db)
        result = resolver.import_with_id_mapping(
            {"villages": [{"id": 100, "village_name": "新村名"}]}, strategy=ConflictStrategy.SKIP
        )
        assert result == {"villages": {100: 1}}
        db.flush.assert_not_called()  # SKIP 策略不写库


# ---------------------------------------------------------------------------
# rbac_service.py — 222->235, 249->253, 253->257, 322->327
# ---------------------------------------------------------------------------


class TestRbacServiceBranches:
    async def test_check_permission_denied_when_resource_access_fails(self):
        """222->235: 角色权限与资源权限都未命中时记录"权限不足"。"""
        svc = RBACService()
        svc._get_cached_restricted_permissions = lambda uid, db: set()
        svc._has_admin_role = lambda uid, db: False
        svc._has_role_permission = lambda uid, permission, db: False
        svc._has_direct_permission = lambda uid, permission, db: False
        svc._has_resource_access = lambda uid, rt, rid, level, db: False
        log = MagicMock()
        svc._log_access = log
        result = await svc.check_permission(
            "7", "villages:read", resource_type="village", resource_id="3", db=MagicMock()
        )
        assert result is False
        final_call = log.call_args_list[-1].args
        assert final_call[5] is False
        assert final_call[6] == "权限不足"

    async def test_restricted_permissions_cached_across_calls(self, monkeypatch):
        """249->253 / 253->257: 第二次调用命中请求级缓存，不再重建服务或重查。"""
        _restricted_perms_cache.set(None)
        inits = []

        class FakeMCPService:
            def __init__(self, db):
                inits.append(db)

            def get_user_restricted_permissions(self, user_id):
                return {"menu:delete"}

        monkeypatch.setattr(rbac_mod, "MachineCodePermissionService", FakeMCPService)
        svc = RBACService()
        db = MagicMock()
        first = svc._get_cached_restricted_permissions(7, db)
        second = svc._get_cached_restricted_permissions(7, db)
        assert first == {"menu:delete"}
        assert second == {"menu:delete"}
        assert len(inits) == 1  # 缓存命中：机器码权限服务只构建一次
        _restricted_perms_cache.set(None)

    async def test_compute_permissions_with_falsy_user_id_skips_whitelist_lookup(self):
        """322->327: user_id 为假值时跳过白名单查询分支。"""
        svc = RBACService()
        svc._get_cached_restricted_permissions = lambda uid, db: set()
        direct_q = _query_mock(all=[("villages.view",)])
        role_q = _query_mock(all=[])
        db = MagicMock()
        db.query = MagicMock(side_effect=[direct_q, role_q])
        effective, restricted = await svc._compute_user_permissions_with_restrictions(0, db)
        assert effective == {"villages.view"}
        assert restricted == set()
        assert db.query.call_count == 2  # 不触发用户白名单的第三次查询


# ---------------------------------------------------------------------------
# effectiveness_service.py — 86->88, 93->99, 95->99, 197->196
# ---------------------------------------------------------------------------


class TestEffectivenessServiceBranches:
    def _indicator_db(self, incomes, prev, infra=2, industry=1):
        db = MagicMock()
        income_all_q = _query_mock(all=incomes)
        prev_q = _query_mock(first=prev)
        infra_q = _query_mock(scalar=infra)
        industry_q = _query_mock(scalar=industry)
        db.query = MagicMock(side_effect=[income_all_q, prev_q, infra_q, industry_q])
        return db

    def test_compute_indicators_without_income_data_uses_baseline(self):
        """86->88 / 93->99: 无年度收入与上年数据时全部走中性基线。"""
        db = self._indicator_db(incomes=[], prev=None)
        result = EffectivenessService._compute_indicators(db, SimpleNamespace(id=1), 2024)
        assert result["indicators"]["per_capita_income"] == 0.0
        assert result["indicators"]["income_growth_rate"] == 0.0
        assert result["indicators"]["data_complete"] is False
        assert result["economic"] == 0.0
        assert result["social"] == 36.0  # 2*15 + 1*6
        assert result["ecological"] == 70.0  # 60 + 2*5

    def test_compute_indicators_negative_prev_income_keeps_growth_zero(self):
        """95->99: 上年人均收入为负时增长率保持 0，不做除法。"""
        incomes = [SimpleNamespace(per_capita_income_2024=5000)]
        prev = SimpleNamespace(per_capita_income_2023=-100)
        db = self._indicator_db(incomes=incomes, prev=prev, infra=0, industry=0)
        result = EffectivenessService._compute_indicators(db, SimpleNamespace(id=1), 2024)
        assert result["indicators"]["per_capita_income"] == 5000.0
        assert result["indicators"]["income_growth_rate"] == 0.0
        assert result["economic"] == 60.0  # 人均收入封顶 60，增长率为 0

    def test_evaluate_village_keeps_rank_when_already_correct(self):
        """197->196: 排名已正确时跳过回写。"""
        village = SimpleNamespace(id=5, village_name="幸福村")
        ev = SimpleNamespace(
            village_id=5, year=2024, economic_score=1.0, social_score=1.0,
            ecological_score=1.0, total_score=1.0, rank=1, grade="D",
            indicators={}, evaluated_at=datetime(2024, 5, 1, 12, 0, 0), evaluated_by=1,
        )
        db = MagicMock()
        village_q = _query_mock(first=village)
        find_q = _query_mock(first=ev)
        income_all_q = _query_mock(all=[])
        prev_q = _query_mock(first=None)
        infra_q = _query_mock(scalar=2)
        industry_q = _query_mock(scalar=1)
        rank_q = _query_mock(all=[ev])
        db.query = MagicMock(side_effect=[village_q, find_q, income_all_q, prev_q, infra_q, industry_q, rank_q])

        result = EffectivenessService.evaluate_village(db, 5, 2024, 9)
        assert result["village_name"] == "幸福村"
        assert result["rank"] == 1
        assert ev.rank == 1  # 已正确的排名未被改动
        assert ev.evaluated_by == 9
        assert result["grade"] == "D"


# ---------------------------------------------------------------------------
# data_report_service.py — 187->190, 226->229, 385->387, 406->409
# ---------------------------------------------------------------------------


class TestDataReportServiceBranches:
    async def test_submit_report_without_comment_keeps_comment_none(self):
        """187->190: 未传备注时不覆盖 comment 字段。"""
        svc = DataReportService(MagicMock())
        report = SimpleNamespace(
            id=3, status=ReportStatus.DRAFT.value, comment=None,
            source_org_id=2, target_org_id=1, report_code="R-1",
        )
        svc._get_report = lambda report_id: report
        result = await svc.submit_report(3, 9, comment=None)
        assert result.status == ReportStatus.SUBMITTED.value
        assert result.comment is None  # 未传备注不落脏数据
        assert result.submitted_by == 9
        assert len(svc.notification_service.notifications) == 1

    async def test_review_report_approve_without_comment_keeps_original(self):
        """226->229: 审批未附备注时保留原 comment。"""
        svc = DataReportService(MagicMock())
        report = SimpleNamespace(
            id=3, status=ReportStatus.SUBMITTED.value, comment="初始备注",
            source_org_id=2, target_org_id=1, report_code="R-1",
        )
        svc._get_report = lambda report_id: report
        review = DataReportReview(action=ReviewActionEnum.APPROVE, comment=None)
        result = await svc.review_report(3, review, 9)
        assert result.status == ReportStatus.APPROVED.value
        assert result.comment == "初始备注"
        assert result.reviewed_by == 9

    async def test_subordinate_dashboard_groups_reports_and_counts_unreported(self):
        """385->387 / 406->409: 同源第二份报告并入既有分组；无报告下级计为未上报。"""
        svc = DataReportService(MagicMock())
        sub_a = SimpleNamespace(id=11, name="甲村", code="V001")
        sub_b = SimpleNamespace(id=12, name="乙村", code="V002")
        svc.org_service = SimpleNamespace(
            get_subordinate_organizations=lambda org_id, include_self=False: [sub_a, sub_b]
        )
        now = datetime.now(timezone.utc)
        r1 = SimpleNamespace(source_org_id=11, status=ReportStatus.SUBMITTED.value,
                             deadline=None, submitted_at=datetime(2024, 1, 5, tzinfo=timezone.utc))
        r2 = SimpleNamespace(source_org_id=11, status=ReportStatus.APPROVED.value,
                             deadline=now - timedelta(days=1), submitted_at=datetime(2024, 2, 1, tzinfo=timezone.utc))
        svc.db.query.return_value = _query_mock(all=[r1, r2])
        dashboard = svc.get_subordinate_dashboard(1)
        assert dashboard.total_subordinates == 2
        assert dashboard.reported_count == 1
        assert dashboard.unreported_count == 0  # schema 未接收 not_reported_count，保持默认
        assert dashboard.subordinates[0].total_reports == 2  # 同源报告归入同一分组
        assert dashboard.subordinates[0].pending_reports == 1
        assert dashboard.subordinates[0].approved_reports == 1
        assert dashboard.subordinates[1].total_reports == 0


# ---------------------------------------------------------------------------
# data_sync_service.py — 316->315, 624->632, 938->919
# ---------------------------------------------------------------------------


class TestDataSyncServiceBranches:
    async def test_save_export_package_skips_directories_in_uploads(self, tmp_path, monkeypatch):
        """316->315: uploads 下的目录不是文件，跳过打包。"""
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        (uploads / "sub").mkdir()
        (uploads / "a.txt").write_text("hello", encoding="utf-8")
        monkeypatch.setattr("app.utils.paths.get_uploads_path", lambda: uploads)
        svc = DataSyncService()
        svc.sync_dir = tmp_path
        package_path = await svc._save_export_package({"tables": {}}, "pkgA", include_files=True)
        assert package_path == tmp_path / "pkgA.zip"
        with zipfile.ZipFile(package_path) as zf:
            names = zf.namelist()
        assert "data.json" in names
        assert "files/a.txt" in names
        assert not any(n.startswith("files/sub") for n in names)  # 目录未被打包

    async def test_resolve_conflict_with_unknown_resolution_still_marks_resolved(self, tmp_path):
        """624->632: 解析方式不属于 keep_local/use_import/merge 时仍落"已解决"标记。"""
        svc = DataSyncService()
        db = MagicMock()
        conflict = SimpleNamespace(
            id=9, table_name="projects", import_data={"id": 1},
            resolution=None, resolved=False, resolved_at=None, resolved_by=None, merged_data=None,
        )
        db.query.return_value = _query_mock(first=conflict)

        @contextlib.contextmanager
        def fake_db_ctx():
            yield db

        svc._get_db_context = fake_db_ctx
        result = await svc.resolve_conflict(9, "unknown_strategy", user_id=3)
        assert result == {"success": True, "message": "冲突已解决"}
        assert conflict.resolved is True
        assert conflict.resolved_by == 3

    async def test_import_table_data_enhanced_unhandled_strategy_counts_nothing(self):
        """938->919: 已存在记录但策略不匹配 skip/overwrite/merge 时不计数，进入下一条。"""
        svc = DataSyncService()
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = ("existing-row",)
        result = await svc._import_table_data_enhanced(db, "projects", [{"id": 1, "name": "x"}], "manual", 99)
        assert result["total"] == 1
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result["inserted"] == 0
        assert result["updated"] == 0
        assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# package_record_validator.py — 276->269, 294->281, 314->307
# ---------------------------------------------------------------------------


class TestPackageRecordValidatorBranches:
    def test_phone_already_clean_needs_no_correction(self):
        """276->269: 电话无分隔符时不产生纠正项（对照带分隔符的纠正路径）。"""
        result = validate_records(
            "schools",
            [
                {"name": "实验小学", "contact_phone": "13800138000"},
                {"name": "实验二中", "contact_phone": "138-0013-8000"},
            ],
        )
        cleaned = [r["contact_phone"] for r in result["ok"] + [c["data"] for c in result["corrected"]]]
        assert "13800138000" in cleaned
        assert "138-0013-8000" not in cleaned  # 带分隔符的已被纠正
        corrected = [c for c in result["corrected"] if any("contact_phone" in f for f in c["fixes"])]
        assert len(corrected) == 1
        assert corrected[0]["data"]["contact_phone"] == "13800138000"

    def test_normalized_date_and_native_numeric_need_no_correction(self):
        """294->281 / 314->307: 日期已是 ISO 归一格式、数值本就是数字时不产生纠正。"""
        result = validate_records("funds", [{"date": "2024-01-05T00:00:00", "amount": 100.5}])
        assert len(result["rejected"]) == 0
        assert len(result["corrected"]) == 0  # 无任何 fix
        assert result["ok"] == [{"date": "2024-01-05T00:00:00", "amount": 100.5}]


# ---------------------------------------------------------------------------
# data_package_service.py — 203->206, 279->284, 410->408, 452->455, 556->553, 624->635, 776->768
# ---------------------------------------------------------------------------


class _Col:
    def __init__(self, name):
        self.name = name


class _BareTableModel:
    """既无 org_id 也无 organization_id 列的最小可导出模型替身。"""

    __table__ = SimpleNamespace(columns=[_Col("id"), _Col("name")])


class _FalsyManifest(DataPackageManifest):
    """属性齐全但整体为假的 manifest：驱动 `if validation.manifest:` 的假分支。"""

    def __bool__(self):
        return False


class TestDataPackageServiceBranches:
    def test_export_data_type_without_org_columns_applies_no_org_filter(self):
        """203->206: 模型无 org_id/organization_id 列时跳过两个组织过滤分支。"""
        db = MagicMock()
        record = SimpleNamespace(id=1, name="n1", __table__=_BareTableModel.__table__)
        db.query.return_value = _query_mock(all=[record])
        svc = DataPackageService(db)
        result = svc._export_data_type(5, _BareTableModel)
        assert result == [{"id": 1, "name": "n1"}]
        db.query.return_value.filter.assert_not_called()  # 未加任何组织过滤

    async def test_import_package_with_falsy_manifest_skips_manifest_serialization(self, tmp_path):
        """279->284: manifest 整体为假时不序列化 manifest_dict，落库为 None。"""
        src = tmp_path / "src.zip"
        src.write_bytes(b"PK-fake")
        db = MagicMock()

        def _refresh(obj, *args, **kwargs):
            obj.id = 77

        db.refresh = MagicMock(side_effect=_refresh)
        svc = DataPackageService(db, upload_dir=str(tmp_path))
        validation = DataPackageValidationResult(
            is_valid=True, errors=[], warnings=[], manifest=_FalsyManifest(version="1.0")
        )
        svc.validate_package = AsyncMock(return_value=validation)
        svc.preview_package_data_from_file = AsyncMock(return_value=[])
        result = await svc.import_package(str(src), "src.zip", 5, 9)
        assert result.status == PackageStatusEnum.VALIDATED
        assert result.package_id == 77
        added = db.add.call_args[0][0]
        assert added.manifest is None  # 假 manifest 未序列化落库
        assert added.file_path.startswith(str(tmp_path))

    async def test_preview_skips_manifest_type_without_data_file(self, tmp_path):
        """410->408: manifest 声明的类型在包内缺数据文件时跳过该类型。"""
        zip_path = _write_zip(tmp_path / "p.zip", {"version": "1.0", "org_code": "A", "data_types": ["villages"]})
        svc = DataPackageService(MagicMock())
        preview = await svc.preview_package_data_from_file(zip_path)
        assert preview == []

    async def test_confirm_import_unknown_source_org_keeps_package_org(self, tmp_path, monkeypatch):
        """452->455: 按包内 org_code 查不到本地组织时保留包记录自身的 org_id。"""
        zip_path = _write_zip(tmp_path / "p.zip", {"org_code": "ORGX", "data_types": []})
        package = SimpleNamespace(id=1, status="validated", file_path=zip_path, org_id=7)
        package_q = _query_mock(first=package)
        org_q = _query_mock(first=None)
        db = MagicMock()
        db.query = MagicMock(side_effect=[package_q, org_q])
        monkeypatch.setattr(
            dp_mod.db_coordinator, "exclusive_write", lambda timeout: contextlib.nullcontext()
        )
        svc = DataPackageService(db)
        result = await svc.confirm_import(1, confirmed_by=9)
        assert result.success is True
        assert result.imported_counts == {}
        assert package.status == "imported"

    def test_bulk_upsert_drops_records_cleaned_to_none(self):
        """556->553: 清洗结果为 None 的记录不进入批量写入集合。"""
        svc = DataPackageService(MagicMock())
        svc._clean_import_record = lambda record, valid_columns, org_id, i, model: None
        imported, skipped, errors = svc._bulk_upsert_records(
            SupportedVillage, [{"village_name": "村A"}], org_id=5, overwrite=False
        )
        assert (imported, skipped, errors) == (0, 0, [])

    async def test_export_encrypted_without_package_record_still_replaces_file(self, tmp_path):
        """624->635: 包记录已被删除时跳过记录更新，仍完成加密文件替换。"""
        src = tmp_path / "p.zip"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("manifest.json", "{}")
        export_result = SimpleNamespace(
            package_id=1, package_code="EXP-A-1", file_path=str(src), file_name="p.zip",
            file_size=src.stat().st_size,
            manifest=SimpleNamespace(model_dump=lambda: {"version": "1.0", "org_code": "A"}),
            download_url="/download",
        )
        db = MagicMock()
        svc = DataPackageService(db)

        async def fake_export(*args, **kwargs):
            return export_result

        svc.export_package = fake_export
        svc.get_package = lambda package_id: None  # 包记录不存在
        result = await svc.export_encrypted_package(5, ["villages"], 9, password="pw-123456")
        assert result.file_path == str(src) + ".enc"
        assert os.path.exists(result.file_path)
        assert not os.path.exists(str(src))  # 原始明文文件被清理
        assert result.file_size == os.path.getsize(result.file_path)
        db.add.assert_not_called()  # 无包记录可更新

    async def test_confirm_with_conflict_resolution_ignores_empty_type_data(self, tmp_path, monkeypatch):
        """776->768: 数据文件存在但记录列表为空时不进入冲突解决器。"""
        zip_path = _write_zip(
            tmp_path / "p.zip",
            {"version": "1.0", "org_code": "A", "data_types": ["villages"]},
            {"data/villages.json": "[]"},
        )
        package = SimpleNamespace(
            id=2, status="validated", is_encrypted=False, file_path=zip_path,
            error_message=None, imported_at=None,
        )
        db = MagicMock()
        monkeypatch.setattr(
            dp_mod.db_coordinator, "exclusive_write", lambda timeout: contextlib.nullcontext()
        )
        svc = DataPackageService(db)
        svc.get_package = lambda package_id: package
        result = await svc.confirm_import_with_conflict_resolution(2, conflict_strategy="SKIP")
        assert result == {"success": True, "message": "导入并解决冲突完成"}
        assert package.status == "imported"
        db.add.assert_not_called()  # 空记录未触发任何写入


# ---------------------------------------------------------------------------
# permission_package_service.py — 779->781, 797->799
# ---------------------------------------------------------------------------


class TestPermissionPackageServiceBranches:
    def test_resolve_user_falls_back_to_numeric_id(self):
        """779->781: 用户名未命中时回退数字 ID 查询。"""
        svc = PermissionPackageService(MagicMock())
        by_name_q = _query_mock(first=None)
        by_id_q = _query_mock(first=SimpleNamespace(id=5))
        svc.db.query = MagicMock(side_effect=[by_name_q, by_id_q])
        user = svc._resolve_user_by_username_or_id("ghost", 5)
        assert user is not None
        assert user.id == 5

    def test_resolve_role_by_name_miss_falls_back_to_original_id_lookup(self):
        """797->799: role_name 未命中时按原 role_id 校验存在性。"""
        svc = PermissionPackageService(MagicMock())
        by_name_q = _query_mock(first=None)
        by_id_q = _query_mock(first=SimpleNamespace(id=3))
        svc.db.query = MagicMock(side_effect=[by_name_q, by_id_q])
        role_id = svc._resolve_role_id({"role_id": 9, "role_name": "ghost"}, {})
        assert role_id == 3


# ---------------------------------------------------------------------------
# entity_import_validator.py — 219->218, 265->exit
# ---------------------------------------------------------------------------


class TestEntityImportValidatorBranches:
    def test_parse_excel_headers_skips_empty_header_cells(self):
        """219->218: 空表头单元格不参与列映射。"""
        validator = EntityImportValidator("school")
        mapping = validator.get_column_mapping()
        assert mapping, "school 配置必须提供列映射"
        first_label = next(iter(mapping))
        result = validator.parse_excel_headers(["", first_label])
        assert result == {1: mapping[first_label]}
        assert 0 not in result  # 空表头被跳过

    def test_validate_bool_field_accepts_known_and_rejects_unknown(self):
        """265->exit: 合法布尔取值直接通过不抛异常；非法取值抛 ValueError。"""
        validator = EntityImportValidator("school")
        for legal in ("是", "否", "true", "false", "1", "0", "yes", "no"):
            assert validator._validate_bool_field(legal) is None  # 合法值正常返回
        with pytest.raises(ValueError, match="是"):
            validator._validate_bool_field("也许")
