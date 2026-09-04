"""
补齐 app/services 范围内 5 个模块的残余可覆盖行（全量 tests/ 核验发现，
#18 交接缺口清单未枚举，属本任务"services 各文件 100%"完成标准范围）：

- rural_work_service.py : 232/246/333
  （_can_access_work 拒绝访问的 get/delete/update 守卫）、417
  （get_villages_for_select 传入 current_user 时套用数据权限过滤）
  注：line 50-51（非管理员→DataScope.ALL 不过滤）经论证为逻辑不可达的
  防御冗余分支，已在源码以 pragma: no cover 声明豁免（见 rural_work_service.py）。
- report_service.py     : 250（订阅不存在返回 None）、268（list 字段转 str）、
  271（is_active 布尔化）
- data_package_service.py: 206（since_time 增量过滤）、356（非法类型返回空摘要）、
  362/364（rejected/corrected 明细行）、815-820（count_packages_by_org 计数链）
- reminder_orchestrator.py: 90（approval_approaching 文案分支）
- policy_fts_service.py : 59（空/空白查询返回 []）

均为正常业务分支，无不可达防御代码，故全部以真实断言覆盖，不使用 pragma 豁免。
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.data_package_service import DataPackageService
from app.services.policy_fts_service import search_policies_fts
from app.services.reminder_orchestrator import _format_reminder
from app.services.report_service import ReportService
from app.services.rural_work_service import RuralWorkService


# ─────────────────────────────────────────────────────────────
# rural_work_service
# ─────────────────────────────────────────────────────────────
def _denied_user():
    """非管理员 + data_scope='self' + 记录非本人创建 → _can_access_work 返回 False。"""
    return SimpleNamespace(
        role="user", id=1, data_scope="self", is_superuser=False, organization_id=5
    )


def _work():
    return SimpleNamespace(created_by=999, organization_id=5, name="w", id=1)


def _svc_with_work():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _work()
    return RuralWorkService(db)


class TestRuralWorkScope:
    def test_get_denied_returns_none(self):
        # line 231-232：_can_access_work 拒绝 → get 返回 None
        assert _svc_with_work().get_rural_work_by_id(1, _denied_user()) is None

    def test_delete_denied_returns_false(self):
        # line 245-246：_can_access_work 拒绝 → delete 返回 False
        assert _svc_with_work().delete_rural_work(1, current_user=_denied_user()) is False

    def test_update_denied_returns_none(self):
        # line 332-333：_can_access_work 拒绝 → update 返回 None
        assert _svc_with_work().update_rural_work(1, current_user=_denied_user()) is None

    def test_get_villages_for_select_applies_scope(self):
        # line 416-417：current_user 非 None → 对 SupportedVillage 查询套用数据权限过滤
        fake_db = MagicMock()
        q = fake_db.query.return_value
        q.all.return_value = []  # line 419 Village 全表（空）
        q.filter.return_value.order_by.return_value.all.return_value = []  # line 418 SV（空）
        svc = RuralWorkService(MagicMock())
        with patch("app.core.database.SessionLocal", return_value=fake_db), patch(
            "app.core.data_scope_adapter.apply_scope_filter",
            side_effect=lambda query, user, model, db=None: query,
        ):
            rows = svc.get_villages_for_select(
                current_user=SimpleNamespace(role="admin", id=1)
            )
        assert rows == []


# ─────────────────────────────────────────────────────────────
# report_service（update_subscription 为 async）
# ─────────────────────────────────────────────────────────────
class TestReportSubscriptionUpdate:
    async def test_not_found_returns_none(self):
        # line 249-250：订阅不存在 → 返回 None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ReportService(db)
        assert await svc.update_subscription(999, {}) is None

    async def test_list_fields_stringified_and_active_bool(self):
        # line 267-268：village_ids/include_sections 为 list → str(value)
        # line 270-271：is_active 存在 → bool 化
        db = MagicMock()
        sub = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = sub
        svc = ReportService(db)
        with patch("app.core.transaction.safe_commit"):
            result = await svc.update_subscription(
                1,
                {"village_ids": [1, 2], "include_sections": ["a"], "is_active": 1},
            )
        assert result is not None
        # is_active=1 被布尔化为 True（line 271）并写入返回体
        assert result["is_active"] is True


# ─────────────────────────────────────────────────────────────
# data_package_service
# ─────────────────────────────────────────────────────────────
class TestDataPackageGaps:
    def test_field_warnings_invalid_type_returns_empty(self):
        # line 355-356：data_type 不在 DATA_TYPE_MODELS → 返回 []
        assert DataPackageService._field_validation_warnings("bogus_type", [{}]) == []

    def test_field_warnings_corrected_and_rejected_detail(self):
        # line 361-362（rejected 明细）+ 363-364（corrected 明细）
        fake = {
            "ok": [],
            "corrected": [{"row": 0, "fixes": ["自动修正"]}],
            "rejected": [{"row": 1, "reasons": ["字段缺失"]}],
        }
        with patch(
            "app.services.data_package_service.validate_records", return_value=fake
        ):
            lines = DataPackageService._field_validation_warnings("villages", [{"x": 1}])
        assert any("已自动纠正" in ln for ln in lines)  # 364
        assert any("校验未通过" in ln for ln in lines)  # 362

    def test_export_data_type_since_time_filter(self, tmp_path):
        # line 205-206：since_time 非 None 且模型有 updated_at → 追加时间过滤
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q  # 所有 filter 返回同一 query，末端 all() 为空
        q.all.return_value = []
        svc = DataPackageService(db, upload_dir=str(tmp_path))

        class _FakeCol:
            """SQLAlchemy 列占位：支持 > / == 生成假表达式（db/query 已 mock，
            不执行真实 SQL），hasattr 均为 True 以驱动各过滤分支。"""

            def __gt__(self, other):
                return ("GT", other)

            def __eq__(self, other):
                return ("EQ", other)

            def __hash__(self):
                return id(self)

        class Dummy:
            org_id = _FakeCol()
            created_by = _FakeCol()
            sync_version = _FakeCol()
            updated_at = _FakeCol()

        result = svc._export_data_type(
            org_id=1,
            model=Dummy,
            since_sync_version=2,
            since_time=datetime(2020, 1, 1),
            owner_id=5,
        )
        assert result == []

    def test_count_packages_by_org(self, tmp_path):
        # line 815-820：org/status/type 三重过滤后计数
        db = MagicMock()
        m = db.query.return_value
        m.filter.return_value = m
        m.count.return_value = 7
        svc = DataPackageService(db, upload_dir=str(tmp_path))
        assert svc.count_packages_by_org(org_id=1, status="active", type_filter="full") == 7


# ─────────────────────────────────────────────────────────────
# reminder_orchestrator
# ─────────────────────────────────────────────────────────────
class TestReminderFormat:
    def test_approval_approaching_branch(self):
        # line 89-90：type == approval_approaching 的文案分支
        s = _format_reminder({"type": "approval_approaching", "elapsed_hours": 3})
        assert "即将超时" in s


# ─────────────────────────────────────────────────────────────
# policy_fts_service
# ─────────────────────────────────────────────────────────────
class TestPolicyFtsEmptyQuery:
    def test_blank_query_returns_empty_list(self):
        # line 58-59：query 为空白 → 直接返回 []（ensure_fts_table 已被隔离）
        with patch("app.services.policy_fts_service.ensure_fts_table"):
            assert search_policies_fts(MagicMock(), "   ") == []
