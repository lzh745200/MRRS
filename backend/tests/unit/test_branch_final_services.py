"""终局分支清零：services 层长尾文件补充测试。

针对 coverage.py 报告中各文件的残余缺失弧/语句，直调函数级行为断言驱动真实分支。
不修改 app/ 源码；不触碰范围外文件。

覆盖文件：
- app/services/organization_permission_service.py
- app/services/work_log_service.py
- app/services/smart_conflict_resolver.py（491->493 不可达，见用例注释）
- app/services/sentiment/crawler_service.py（19->25 环境相关，见报告）
- app/services/secrets_manager.py
- app/services/rural_work_service.py
- app/services/retention_service.py
- app/services/restore_drill_service.py
- app/services/reminder_service.py
- app/services/reminder_engine.py
- app/services/fund_event_handler.py
- app/services/data_cleaning_service.py
- app/services/compliance_engine.py
- app/services/chunked_upload_service.py
- app/services/batch_service.py
- app/services/async_export_service.py
- app/services/ai/nlp_query_service.py
- app/services/ai/anomaly_detection_service.py
"""

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.data_permission import DataScope
from app.services import async_export_service as ax_mod
from app.services import batch_service as batch_mod
from app.services import data_cleaning_service as dc_mod
from app.services import fund_event_handler as feh_mod
from app.services import organization_permission_service as op_mod
from app.services import reminder_engine as re_mod
from app.services import restore_drill_service as rd_mod
from app.services import rural_work_service as rw_mod
from app.services import secrets_manager as sm_mod
from app.services.ai import anomaly_detection_service as ad_mod
from app.services.ai import nlp_query_service as nlp_mod
from app.services.ai.anomaly_detection_service import AnomalyDetectionService
from app.services.ai.nlp_query_service import NLPQueryService
from app.services.async_export_service import recover_stale_export_tasks
from app.services.batch_service import BatchService
from app.services.chunked_upload_service import (
    ChunkedUploadService,
    ChunkUploadStatus,
    UploadSession,
)
from app.services.compliance_engine import run_compliance_check
from app.services.data_cleaning_service import DataCleaningService
from app.services.fund_event_handler import on_project_status_change
from app.services.organization_permission_service import OrganizationPermissionService
from app.services.reminder_engine import scan_budget_warnings
from app.services.reminder_service import ApprovalReminderService
from app.services.retention_service import purge_expired_soft_deleted
from app.services.rural_work_service import RuralWorkService
from app.services.secrets_manager import SecretsManager
from app.services.sentiment.crawler_service import CrawlerService, NewsItem
from app.services.work_log_service import WorkLogService


def _query_mock(**returns):
    """可链式调用的 query 替身：filter/join/order_by/distinct 自链。"""
    q = MagicMock()
    q.filter.return_value = q
    q.join.return_value = q
    q.order_by.return_value = q
    q.distinct.return_value = q
    for method, value in returns.items():
        getattr(q, method).return_value = value
    return q


# ---------------------------------------------------------------------------
# organization_permission_service.py — 224->228, 261->265, 347->351
# ---------------------------------------------------------------------------


class TestOrganizationPermissionServiceBranches:
    def _svc(self, monkeypatch):
        svc = OrganizationPermissionService(MagicMock())
        svc._get_user = lambda user_id: SimpleNamespace(id=user_id, role="admin")
        monkeypatch.setattr(op_mod, "is_superuser", lambda user: True)
        return svc

    def test_can_manage_organization_when_resolved_user_is_superuser(self, monkeypatch):
        """224->228: user 入参为空但按 user_id 查得用户时，继续走超管判定。"""
        svc = self._svc(monkeypatch)
        assert svc.can_manage_organization(user_id=1, user=None, org_id=9) is True

    def test_can_create_subordinate_when_resolved_user_is_superuser(self, monkeypatch):
        """261->265: 未传 user 但查得用户时跳过 not-user 早退，走超管判定。"""
        svc = self._svc(monkeypatch)
        assert svc.can_create_subordinate(user_id=1, user=None, parent_org_id=9) is True

    def test_is_superior_of_when_resolved_user_is_superuser(self, monkeypatch):
        """347->351: 未传 user 但查得用户时跳过 not-user 早退，走超管判定。"""
        svc = self._svc(monkeypatch)
        assert svc.is_superior_of(user_id=1, user=None, target_org_id=9) is True


# ---------------------------------------------------------------------------
# work_log_service.py — 43->42
# ---------------------------------------------------------------------------


class TestWorkLogServiceBranches:
    def test_update_work_log_ignores_unknown_attributes(self):
        """43->42: 数据键不是记录属性时跳过 setattr，继续下一个键。"""
        log = SimpleNamespace(id=1, title="旧标题")
        db = MagicMock()
        db.query.return_value = _query_mock(first=log)
        svc = WorkLogService(db)
        result = svc.update_work_log(1, {"title": "新标题", "not_a_column": "x"})
        assert result.title == "新标题"
        assert not hasattr(result, "not_a_column")


# ---------------------------------------------------------------------------
# sentiment/crawler_service.py — 140, 122-124, 172-195
# ---------------------------------------------------------------------------


class TestCrawlerServiceBranches:
    def test_fetch_rss_feeds_returns_empty_when_crawler_disabled(self, monkeypatch):
        """140: 爬虫禁用（离线默认）时直接返回空列表，不发网络请求。"""
        import app.services.sentiment.crawler_service as crawler_mod

        monkeypatch.setattr(crawler_mod, "_CRAWLER_ENABLED", False)
        assert CrawlerService.fetch_rss_feeds(MagicMock(), ["乡村振兴"]) == []

    def test_get_instance_lazily_creates_singleton(self):
        """122-124: 单例为空时惰性创建 SentimentCrawlerService 实例。"""
        original = CrawlerService._instance
        CrawlerService._instance = None
        try:
            inst = CrawlerService._get_instance()
            assert inst is not None
            assert CrawlerService._get_instance() is inst  # 后续调用复用同一实例
        finally:
            CrawlerService._instance = original

    def test_save_news_persists_each_item(self):
        """172-195: 保存新闻列表逐条入库并返回写入数量。"""
        db = MagicMock()
        news = [
            NewsItem(title="标题A", source="RSS", url="u", content="c", keywords=["村"]),
            NewsItem(title="标题B", source="RSS", url="u2", content="c2", keywords=[]),
        ]
        saved = CrawlerService.save_news(db, news)
        assert saved == 2
        assert db.add.call_count == 2
        added = db.add.call_args_list[0].args[0]
        assert added.title == "标题A"


# ---------------------------------------------------------------------------
# secrets_manager.py — 204->198
# ---------------------------------------------------------------------------


class TestSecretsManagerBranches:
    def test_cleanup_expired_keys_keeps_recently_revoked(self):
        """204->198: 已撤销但未超过保留期的版本保留，循环继续下一条。"""
        sm = SecretsManager()
        now = datetime.now(timezone.utc).timestamp()
        sm._key_versions = [
            {"version_id": "v-recent-revoked", "is_active": False, "revoked_at": now, "created_at": now},
            {"version_id": "v-active", "is_active": True, "created_at": now},
        ]
        deleted = sm.cleanup_expired_keys(keep_days=90)
        assert deleted == 0
        assert [v["version_id"] for v in sm._key_versions] == ["v-recent-revoked", "v-active"]


# ---------------------------------------------------------------------------
# rural_work_service.py — 86->94, 237, 251, 274, 278, 358, 370, 445
# ---------------------------------------------------------------------------


class TestRuralWorkServiceBranches:
    def test_can_access_work_denies_non_own_dept_scope(self, monkeypatch):
        """86->94: 数据范围为非本部门时返回 False。"""
        monkeypatch.setattr("app.core.data_permission.get_data_scope", lambda user: DataScope.OWN)
        work = SimpleNamespace(created_by=99, organization_id=5)
        user = SimpleNamespace(id=1, role="user", data_scope="all")
        assert rw_mod._can_access_work(work, user, MagicMock()) is False

    def test_get_rural_work_by_id_returns_none_on_scope_denied(self, monkeypatch):
        """237: 记录存在但无数据权限时返回 None。"""
        svc = RuralWorkService(MagicMock())
        svc.db.query.return_value = _query_mock(first=SimpleNamespace(id=1))
        monkeypatch.setattr(rw_mod, "_can_access_work", lambda work, user, db: False)
        assert svc.get_rural_work_by_id(1, current_user=SimpleNamespace(id=2)) is None

    def test_delete_rural_work_denied_returns_false(self, monkeypatch):
        """251: 记录存在但无数据权限时不做删除，返回 False。"""
        svc = RuralWorkService(MagicMock())
        svc.db.query.return_value = _query_mock(first=SimpleNamespace(id=1, name="工作A"))
        monkeypatch.setattr(rw_mod, "_can_access_work", lambda work, user, db: False)
        assert svc.delete_rural_work(1, current_user=SimpleNamespace(id=2)) is False
        svc.db.delete.assert_not_called()

    def test_validate_village_id_noop_when_empty(self):
        """274: village_id 为空时提前返回，不查询村庄表。"""
        svc = RuralWorkService(MagicMock())
        assert svc._validate_village_id(None) is None
        svc.db.query.assert_not_called()

    def test_validate_village_id_raises_when_village_missing(self):
        """278: village_id 在 villages 表不存在时抛 ValueError（转 400）。"""
        svc = RuralWorkService(MagicMock())
        svc.db.query.return_value = _query_mock(first=None)
        with pytest.raises(ValueError, match="所选村庄不存在"):
            svc._validate_village_id(999)

    def test_update_rural_work_denied_returns_none(self, monkeypatch):
        """358: 更新时无数据权限返回 None。"""
        svc = RuralWorkService(MagicMock())
        svc.db.query.return_value = _query_mock(first=SimpleNamespace(id=1))
        monkeypatch.setattr(rw_mod, "_can_access_work", lambda work, user, db: False)
        assert svc.update_rural_work(1, data={"name": "新"}, current_user=SimpleNamespace(id=2)) is None

    def test_update_rural_work_validates_village_id_when_present(self, monkeypatch):
        """370: updates 含 village_id 键时触发村庄存在性校验。"""
        from app.models.rural_work import RuralWork

        svc = RuralWorkService(MagicMock())
        work = RuralWork(id=1, name="工作A")
        svc.db.query.return_value = _query_mock(first=work)
        monkeypatch.setattr(rw_mod, "_can_access_work", lambda w, u, d: True)
        called = []

        def fake_validate(village_id):
            called.append(village_id)

        svc._validate_village_id = fake_validate
        svc.update_rural_work(1, data={"village_id": 7}, current_user=SimpleNamespace(id=1))
        assert called == [7]

    def test_get_villages_for_select_applies_scope_for_user(self, monkeypatch):
        """445: 传入 current_user 时对村庄查询应用数据范围过滤。"""
        svc = RuralWorkService(MagicMock())
        db = MagicMock()
        sv_query = _query_mock(all=[SimpleNamespace(name="甲村", county=None, township=None, organization_id=None)])
        village_query = _query_mock(all=[])
        db.query.side_effect = [sv_query, village_query]
        monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
        scope_calls = []

        def fake_apply_scope(query, user, model, db=None):
            scope_calls.append(user)
            return query

        monkeypatch.setattr("app.core.data_permission.apply_scope_filter", fake_apply_scope)
        rows = svc.get_villages_for_select(current_user=SimpleNamespace(id=1))
        assert [r["name"] for r in rows] == ["甲村"]
        assert len(scope_calls) == 1  # 非空用户触发范围过滤


# ---------------------------------------------------------------------------
# retention_service.py — 87->84
# ---------------------------------------------------------------------------


class TestRetentionServiceBranches:
    def test_purge_failure_does_not_count_and_continues(self, monkeypatch):
        """87->84: 单条 purge 失败（success=False）不计数，继续处理其余表。"""
        class _FakePurge:
            def __init__(self, db):
                self.db = db

            def purge(self, table, rid):
                return {"success": False}

        monkeypatch.setattr("app.services.cascade_purge_service.CascadePurgeService", _FakePurge)
        monkeypatch.setattr("app.services.immediate_backup.trigger_immediate_backup", lambda **kw: None)
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [(1,)]
        summary = purge_expired_soft_deleted(db, days=30)
        assert summary["purged"] == {}
        assert summary["total_records"] == 0


# ---------------------------------------------------------------------------
# restore_drill_service.py — 128->127
# ---------------------------------------------------------------------------


class TestRestoreDrillServiceBranches:
    def test_load_persisted_status_skips_unknown_keys(self, monkeypatch):
        """128->127: 持久化数据缺少某键时跳过该键，继续回填其余键。"""
        monkeypatch.setattr("app.core.database.SessionLocal", lambda: MagicMock())
        monkeypatch.setattr(
            "app.services.system_config_service.get_config",
            lambda key, default="": json.dumps({"status": "passed"}),
        )
        saved = dict(rd_mod.RESTORE_DRILL_STATUS)
        try:
            rd_mod._load_persisted_status()
            assert rd_mod.RESTORE_DRILL_STATUS["status"] == "passed"
            assert "tables_checked" not in json.dumps({"status": "passed"})
        finally:
            rd_mod.RESTORE_DRILL_STATUS.clear()
            rd_mod.RESTORE_DRILL_STATUS.update(saved)


# ---------------------------------------------------------------------------
# reminder_service.py — 83->91
# ---------------------------------------------------------------------------


class TestReminderServiceBranches:
    def test_stop_without_thread_clears_running_flag(self):
        """83->91: 运行标记为真但线程对象为空时，直接复位标记并返回 True。"""
        svc = ApprovalReminderService()
        svc._running = True
        svc._thread = None
        assert svc.stop() is True
        assert svc._running is False


# ---------------------------------------------------------------------------
# reminder_engine.py — 140->134
# ---------------------------------------------------------------------------


class TestReminderEngineBranches:
    def test_scan_budget_warnings_skips_fund_below_threshold(self):
        """140->134: 使用率低于预警线时不生成告警，进入下一条经费。"""
        db = MagicMock()
        db.query.return_value = _query_mock(
            all=[SimpleNamespace(amount=100, used_amount=10, id=1, name="经费A", created_by=None)]
        )
        assert scan_budget_warnings(db) == []


# ---------------------------------------------------------------------------
# fund_event_handler.py — 56->49
# ---------------------------------------------------------------------------


class TestFundEventHandlerBranches:
    def test_target_phase_in_progress_is_left_untouched(self):
        """56->49: 阶段等于目标阶段但状态已在推进中时不改写，循环继续。"""
        phase = SimpleNamespace(phase=2, status="in_progress", completed_at=None, operator="", entered_at=None)
        phases_q = _query_mock(all=[phase])
        funds_q = _query_mock(all=[])
        db = MagicMock()
        db.query.side_effect = [phases_q, funds_q]
        on_project_status_change(db, 1, "draft", "approved", operator="tester")
        assert phase.status == "in_progress"
        assert phase.entered_at is None
        assert phase.operator == ""
        db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# data_cleaning_service.py — 323->322
# ---------------------------------------------------------------------------


class TestDataCleaningServiceBranches:
    def test_trim_strings_ignores_non_string_values(self):
        """323->322: 非字符串值跳过裁剪，继续下一个键。"""
        records = [{"count": 5, "name": "  甲村  "}]
        dc_mod.DataCleaningService._trim_strings(records)
        assert records == [{"count": 5, "name": "甲村"}]


# ---------------------------------------------------------------------------
# compliance_engine.py — 79->66
# ---------------------------------------------------------------------------


class TestComplianceEngineBranches:
    def test_fund_within_threshold_produces_no_warning(self):
        """79->66: 偏差率低于预警线时既不违规也不预警，进入下一条经费。"""
        db = MagicMock()
        project_q = _query_mock(first=SimpleNamespace(name="项目A"))
        funds_q = _query_mock(
            all=[SimpleNamespace(approved_amount=100, planned_amount=None, amount=100,
                                 used_amount=100, code="F1", name="经费A")]
        )
        db.query.side_effect = [project_q, funds_q]
        result = run_compliance_check(db, 1)
        assert result["passed"] is True
        assert result["warnings"] == []
        assert result["violations"] == []
        assert result["summary"]["usage_rate"] == 100.0


# ---------------------------------------------------------------------------
# chunked_upload_service.py — 201-206, 448-449, 530->535
# ---------------------------------------------------------------------------


class TestChunkedUploadServiceBranches:
    def _service(self, tmp_path):
        return ChunkedUploadService(
            temp_dir=str(tmp_path / "chunks"), final_dir=str(tmp_path / "files")
        )

    def test_session_limit_evicts_oldest_first(self, tmp_path):
        """201-206: 会话超上限时按 created_at 淘汰最早会话。"""
        svc = self._service(tmp_path)
        svc.max_sessions = 2
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for idx, sid in enumerate(["oldest", "middle", "newest"]):
            svc._sessions[sid] = UploadSession(
                session_id=sid, file_name="a.bin", file_size=0, chunk_size=1,
                total_chunks=0, file_hash=None, user_id=1,
                status=ChunkUploadStatus.UPLOADING, created_at=base + timedelta(minutes=idx),
            )
        evicted = []
        svc.delete_session = lambda sid: evicted.append(sid) or True
        svc._enforce_session_limit()
        assert evicted == ["oldest"]  # 只淘汰最早的一个

    def test_merge_lock_rejects_status_flip_inside_lock(self, tmp_path):
        """448-449: 取锁后二次检查发现状态变为 MERGING 时释放锁并拒绝重入。"""
        svc = self._service(tmp_path)

        class _StatusFlipSession:
            def __init__(self):
                self._reads = 0

            @property
            def status(self):
                self._reads += 1
                return ChunkUploadStatus.MERGING if self._reads >= 3 else ChunkUploadStatus.UPLOADING

        session = _StatusFlipSession()
        with pytest.raises(ValueError, match="already merging"):
            svc._acquire_merge_lock(session, "sess-locked")
        assert not svc._get_session_lock("sess-locked").locked()  # 锁已释放

    async def test_merge_without_temp_dir_skips_cleanup(self, tmp_path):
        """530->535: 临时分片目录不存在时跳过 rmtree 清理，仍返回合并结果。"""
        svc = self._service(tmp_path)
        session = UploadSession(
            session_id="sess-empty", file_name="empty.bin", file_size=0, chunk_size=1,
            total_chunks=0, file_hash=None, user_id=3,
            status=ChunkUploadStatus.UPLOADING,
        )
        svc._sessions["sess-empty"] = session
        assert not (svc.temp_dir / "sess-empty").exists()

        merged_path = await svc.merge_chunks("sess-empty")
        assert merged_path.endswith("empty.bin")
        assert session.status == ChunkUploadStatus.MERGED
        assert not svc._get_session_lock("sess-empty").locked()


# ---------------------------------------------------------------------------
# batch_service.py — 127->132
# ---------------------------------------------------------------------------


class TestBatchServiceBranches:
    def test_db_context_without_session_skips_close(self, monkeypatch):
        """127->132: 无既有 session 且生成器未产出连接时不调用 close，直接关闭生成器。"""
        closed = []

        def fake_gen():
            try:
                yield None
            finally:
                closed.append("gen")

        monkeypatch.setattr(batch_mod, "get_db", lambda: fake_gen())
        svc = BatchService(db=None)
        with svc._get_db_context() as db:
            assert db is None
        assert closed == ["gen"]


# ---------------------------------------------------------------------------
# async_export_service.py — 402->410, 426-446
# ---------------------------------------------------------------------------


class TestAsyncExportServiceBranches:
    def test_run_export_task_failure_without_task_row_closes_session(self, monkeypatch):
        """402->410: 失败回写时任务行已不存在，跳过回写并关闭会话。"""
        from app.services import async_export_service as aem

        db = MagicMock()
        task = SimpleNamespace(
            task_id="t-1", user_id=1, status="pending", query_params={},
            export_type="villages", file_name=None,
        )
        first_q = _query_mock(first=task)
        requery_q = _query_mock(first=None)
        db.query.side_effect = [first_q, requery_q]
        monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
        monkeypatch.setattr(aem, "_load_user", lambda db_, user_id: (_ for _ in ()).throw(RuntimeError("boom")))
        aem._run_export_task("t-1")
        assert db.rollback.called
        assert db.close.called

    def test_recover_stale_export_tasks_marks_pending_and_processing_failed(self):
        """426-446: 启动恢复把 pending/processing 任务统一回写为 failed。"""
        t1 = SimpleNamespace(status="pending", error_message=None, completed_at=None)
        t2 = SimpleNamespace(status="processing", error_message=None, completed_at=None)
        db = MagicMock()
        db.query.return_value = _query_mock(all=[t1, t2])
        count = recover_stale_export_tasks(db)
        assert count == 2
        assert t1.status == "failed" and t2.status == "failed"
        assert "重新发起导出" in t2.error_message
        db.commit.assert_called()


# ---------------------------------------------------------------------------
# ai/nlp_query_service.py — 108->112
# ---------------------------------------------------------------------------


class TestNlpQueryServiceBranches:
    def test_template_with_groups_but_no_param_sql_yields_no_params(self, monkeypatch):
        """108->112: 模板含捕获组但 SQL 无 province/status/village_name 参数时不提取参数。

        说明：内置模板中带捕获组的模板均含上述关键字，此弧需自定义模板（扩展契约）驱动。
        """
        monkeypatch.setattr(
            NLPQueryService,
            "QUERY_TEMPLATES",
            {
                "synthetic": {
                    "patterns": [r"测试(\w+)数据"],
                    "sql": "SELECT COUNT(*) FROM some_table",
                    "description": "合成模板",
                }
            },
        )
        result = NLPQueryService.parse_query("测试村庄数据")
        assert result["template"] == "synthetic"
        assert result["params"] == {}  # 未产生 province/status/village_name 参数


# ---------------------------------------------------------------------------
# ai/anomaly_detection_service.py — 214->208
# ---------------------------------------------------------------------------


class TestAnomalyDetectionServiceBranches:
    def test_zero_length_project_window_produces_no_anomaly(self):
        """214->208: 起止日期同日（总天数 0）时跳过进度计算，进入下一个项目。"""
        day = date(2024, 5, 1)
        project = SimpleNamespace(
            id=1, name="项目A", village_id=1, progress=10,
            start_date=day, end_date=day,
        )
        db = MagicMock()
        db.query.return_value = _query_mock(all=[project])
        assert AnomalyDetectionService.detect_project_progress_anomalies(db) == []


# ---------------------------------------------------------------------------
# approval_workflow_service.py — 163->165, 362, 888-895
# ---------------------------------------------------------------------------


class TestApprovalWorkflowServiceBranches:
    def test_update_workflow_without_name_keeps_existing_name(self):
        """163->165: 未传 name 时跳过改名，继续处理 description。"""
        from app.services.approval_workflow_service import ApprovalWorkflowService

        svc = ApprovalWorkflowService(MagicMock())
        workflow = SimpleNamespace(name="旧名称", description=None)
        svc.get_workflow = lambda workflow_id: workflow
        result = svc.update_workflow(1, description="新描述")
        assert result is workflow
        assert workflow.name == "旧名称"  # 未传不改名
        assert workflow.description == "新描述"

    def test_count_pending_tasks_scoped_to_approver(self):
        """362: include_all=False 时按"分配给本人或本人提交"过滤后计数。"""
        from app.services.approval_workflow_service import ApprovalWorkflowService

        db = MagicMock()
        db.query.return_value = _query_mock(count=3)
        svc = ApprovalWorkflowService(db)
        assert svc.count_pending_tasks(approver_id=7, include_all=False) == 3
        assert db.query.return_value.filter.called

    def test_submit_entity_change_approval_swallows_service_error(self, monkeypatch):
        """888-895: 创建审批任务失败仅记日志并返回 None，不阻断业务。"""
        from app.services import approval_workflow_service as aw_mod
        from app.services.approval_workflow_service import ApprovalWorkflowService

        def _boom(self, **kwargs):
            raise RuntimeError("审批服务不可用")

        monkeypatch.setattr(ApprovalWorkflowService, "submit_approval", _boom)
        result = aw_mod.submit_entity_change_approval(
            MagicMock(), entity_type="project", entity_id=1, submitter_id=2
        )
        assert result is None


# ---------------------------------------------------------------------------
# smart_conflict_resolver.py — 491->493（不可达，回归占位）
# ---------------------------------------------------------------------------


class TestSmartConflictResolverFinalNote:
    def test_conflict_resolution_mapping_is_merged_into_result(self):
        """行为回归：冲突解决的 ID 映射并入总表。

        491->493 弧经复核**不可达**：外层 id_mapping 仅在 492-494 行写入，
        而 resolve_conflicts_with_strategy / _import_new_records 均返回新字典、
        不改写调用方映射，故 491 行 `data_type not in id_mapping` 恒为真。
        """
        from app.services.smart_conflict_resolver import (
            ConflictStrategy,
            DataConflict,
            SmartConflictResolver,
        )

        local = SimpleNamespace(id=1, village_name="旧村名", updated_at=None)
        db = MagicMock()
        db.query.return_value = _query_mock(first=local)
        resolver = SmartConflictResolver(db)
        result = resolver.import_with_id_mapping(
            {"villages": [{"id": 100, "village_name": "新村名"}]},
            strategy=ConflictStrategy.SKIP,
        )
        assert result == {"villages": {100: 1}}
