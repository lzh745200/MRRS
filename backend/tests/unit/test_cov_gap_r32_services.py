"""R32 覆盖率攻坚 —— app/services 语句 / 分支缺口补全。

覆盖：
- ai/nlp_query_service.py: 209->223（模板 SQL 无数据域占位符 → 不做额外子查询）
- analytics_service.py: 61（_village_id_scope_clause 子表维度数据域子句）、
  702（compare_years 目标村越权 / 不存在 → fail-closed 返回空结果）
- approval_workflow_service.py: 572（原子抢占 rowcount!=1 → 视为已被并发处理，返回 None）
- notification_preference_service.py: 117（并发首次写入撞唯一键后仍查不到行 → 原样抛出）
- permission_package_service.py: 860（角色名记忆化缓存命中）
- rbac_service.py: 636（create_role 缺 db 会话 → ValueError）
- smart_conflict_resolver.py: 191->200（单列业务键全为空 → 跳过预取）、
  198（预取命中写入缓存）
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError


# ══════════════════════════════════════════════════════════════════
#  app/services/ai/nlp_query_service.py
# ══════════════════════════════════════════════════════════════════


class TestNlpExecuteQueryWithoutScopePlaceholder:
    def test_sql_without_scope_placeholder_skips_subquery(self, monkeypatch):
        """模板 SQL 不含 {scope}/{village_scope} → 跳过数据域子查询（209->223）。"""
        from app.services.ai.nlp_query_service import NLPQueryService

        monkeypatch.setattr(
            NLPQueryService,
            "parse_query",
            staticmethod(
                lambda q: {
                    "template": "custom_tpl",
                    "sql": "SELECT 1 AS one",
                    "params": {},
                    "description": "自定义",
                }
            ),
        )

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []

        res = NLPQueryService.execute_query(db, "任意查询")
        assert res["success"] is True
        assert res["sql"] == "SELECT 1 AS one"
        assert res["data"] == []
        db.execute.assert_called_once()


# ══════════════════════════════════════════════════════════════════
#  app/services/analytics_service.py
# ══════════════════════════════════════════════════════════════════


def _super_admin():
    return SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True)


class TestAnalyticsServiceGaps:
    def test_village_id_scope_clause_delegates(self, real_db_session):
        """子表维度数据域子句（61）：委托帮扶村维度子句。"""
        from app.services.analytics_service import AnalyticsService

        clause = AnalyticsService._village_id_scope_clause(real_db_session, _super_admin(), "sv_id")
        assert isinstance(clause, str)
        assert clause.startswith("sv_id IN (")
        assert "SELECT" in clause

    def test_compare_years_inaccessible_village_returns_empty(self, real_db_session):
        """目标村不存在 / 越权 → fail-closed 空结果（702）。"""
        from app.services.analytics_service import AnalyticsService

        out = AnalyticsService(real_db_session).compare_years(
            999999, [2024], metrics=["income"], current_user=_super_admin()
        )
        assert out["village_id"] == 999999
        assert out["data"] == []
        assert out["years"] == [2024]


# ══════════════════════════════════════════════════════════════════
#  app/services/approval_workflow_service.py
# ══════════════════════════════════════════════════════════════════


class TestRejectTaskAtomicClaim:
    def test_claim_lost_returns_none(self):
        """原子抢占 rowcount != 1（已被并发 / 重放处理）→ 返回 None（571-572）。"""
        from app.models.approval import ApprovalStatus, ApprovalTask
        from app.services.approval_workflow_service import ApprovalWorkflowService

        task = ApprovalTask(
            id=1,
            status=ApprovalStatus.PENDING.value,
            current_level=1,
            current_approver_id=None,
        )

        db = MagicMock()
        # get_task 链：query(...).options(...).filter(...).first()
        db.query.return_value.options.return_value.filter.return_value.first.return_value = task
        # 抢占 update 返回 0（未命中任何行）
        db.query.return_value.filter.return_value.update.return_value = 0

        svc = ApprovalWorkflowService(db)
        assert svc.reject_task(1, approver_id=9, opinion="x") is None


class TestApprovalWorkflowMisc:
    def test_update_workflow_skips_none_fields(self, monkeypatch):
        """全部字段为 None → 不写任何属性（163->165），仅提交刷新。"""
        from app.services import approval_workflow_service as aws

        wf = SimpleNamespace(name="old", description="d", is_active=True)
        db = MagicMock()
        db.query.return_value.options.return_value.filter.return_value.first.return_value = wf
        monkeypatch.setattr(aws, "safe_commit", lambda *a, **k: None)

        svc = aws.ApprovalWorkflowService(db)
        out = svc.update_workflow(1, name=None, description=None, is_active=None)

        assert out is wf
        assert (wf.name, wf.description, wf.is_active) == ("old", "d", True)

    def test_count_pending_tasks_without_include_all(self):
        """include_all=False → 追加审批人/提交人过滤（361-367）。"""
        from app.services.approval_workflow_service import ApprovalWorkflowService

        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 3

        assert ApprovalWorkflowService(db).count_pending_tasks(7, include_all=False) == 3

    def test_submit_entity_change_approval_swallows_exception(self, monkeypatch):
        """通用入口内部异常 → 记日志并返回 None，不阻断业务（937-944）。"""
        from app.services import approval_workflow_service as aws

        monkeypatch.setattr(
            aws, "ApprovalWorkflowService", MagicMock(side_effect=RuntimeError("boom"))
        )
        out = aws.submit_entity_change_approval(
            MagicMock(), entity_type="fund", entity_id=1, submitter_id=2
        )
        assert out is None


# ══════════════════════════════════════════════════════════════════
#  app/services/notification_preference_service.py
# ══════════════════════════════════════════════════════════════════


class TestNotificationPreferenceConcurrentInsert:
    def test_integrity_error_without_row_reraises(self, monkeypatch):
        """并发首次写入撞唯一键，回滚后仍查不到行 → 原样抛出（110-117）。"""
        import app.services.notification_preference_service as nps

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        def _boom(*args, **kwargs):
            raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

        monkeypatch.setattr(nps, "safe_commit", _boom)

        svc = nps.NotificationPreferenceService(db)
        with pytest.raises(IntegrityError):
            svc.update_preference(42, email_task=False)

        db.rollback.assert_called_once()


# ══════════════════════════════════════════════════════════════════
#  app/services/permission_package_service.py
# ══════════════════════════════════════════════════════════════════


class TestPermissionPackageRoleNameCache:
    def test_role_name_memoization_hit(self):
        """同一 role_name 第二次解析直接命中记忆化缓存（859-860），不再查库。"""
        from app.services.permission_package_service import PermissionPackageService

        role = SimpleNamespace(id=99)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = role

        svc = PermissionPackageService(db)
        ur = {"role_name": "审计员"}

        assert svc._resolve_role_id(ur, {}) == 99
        assert svc._resolve_role_id(ur, {}) == 99  # 缓存命中
        assert db.query.call_count == 1

    def test_import_organizations_rebuilds_parent_paths(self, real_db_session):
        """组织导入：源 id 建映射（722）、按父链回填 path（736-741）、路径记忆化（732）。"""
        from app.models.organization import Organization
        from app.services.permission_package_service import PermissionPackageService

        svc = PermissionPackageService(real_db_session)
        stats = {"organizations_created": 0, "organizations_updated": 0}
        errors = []

        svc._import_organizations(
            [
                {"id": 11, "name": "根组织", "code": "R32ROOT", "parent_id": None},
                {"id": 12, "name": "子组织", "code": "R32CHILD", "parent_id": 11},
            ],
            stats,
            errors,
        )

        assert errors == []
        assert stats["organizations_created"] == 2
        root = real_db_session.query(Organization).filter_by(code="R32ROOT").one()
        child = real_db_session.query(Organization).filter_by(code="R32CHILD").one()
        assert child.parent_id == root.id
        assert child.path == f"{root.path}{child.id}/"
        # level 列是字符串型（历史兼容 "level_N" 与深度数字两种形态），SQLite 回读为 str
        assert str(child.level) == "2"


# ══════════════════════════════════════════════════════════════════
#  app/services/rbac_service.py
# ══════════════════════════════════════════════════════════════════


class TestRbacCreateRoleRequiresDb:
    async def test_missing_db_raises_value_error(self):
        """create_role 未显式传 db → ValueError（635-636），不再 NoneType.add 崩。"""
        from app.services.rbac_service import RBACService

        with pytest.raises(ValueError, match="db"):
            await RBACService().create_role("测试角色", "描述", [], db=None)


# ══════════════════════════════════════════════════════════════════
#  app/services/smart_conflict_resolver.py
# ══════════════════════════════════════════════════════════════════


class TestConflictResolverPrefetch:
    def test_all_none_business_key_skips_prefetch(self):
        """单列业务键全为 None → candidate_values 为空 → 跳过预取（191->200），视为新记录。"""
        from app.services.smart_conflict_resolver import SmartConflictResolver

        db = MagicMock()
        svc = SmartConflictResolver(db)

        result = svc.detect_conflicts_by_business_key([{"code": None}], "projects")

        assert result.new_records == [{"code": None}]
        assert result.conflict_records == []
        db.query.assert_not_called()

    def test_prefetch_hit_uses_cached_row(self, monkeypatch):
        """预取命中 → 写入 prefetched 缓存（198）并按本地记录判冲突。"""
        from app.services.smart_conflict_resolver import SmartConflictResolver

        row = MagicMock()
        row.code = "C1"

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [row]

        svc = SmartConflictResolver(db)
        monkeypatch.setattr(svc, "_find_differences", lambda local, imp: [])

        result = svc.detect_conflicts_by_business_key([{"code": "C1"}], "projects")

        assert result.no_conflict_records == [{"code": "C1"}]
        assert result.new_records == []
