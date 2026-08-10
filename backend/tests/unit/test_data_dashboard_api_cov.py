"""
dashboard.py 覆盖率攻坚测试（补充 test_data_dashboard_api.py 未覆盖部分）

目标分支：
- _query_village_stats：人口汇总行/空行分支、学校统计行空值回退
- _query_fund_stats：非全量访问的村ID过滤/无村回退、状态聚合循环
- _query_project_approval_stats：org_ids/org_names 文本回退/无条件兜底、审批查询异常、数据完整性计算
- get_dashboard_stats：有数据成功路径 + 缓存写入
- get_dashboard_summary：成功/缓存命中/统计异常降级
- _fetch_* 五路动态获取器（含异常分支）
- recent-activities CRUD（custom/系统动态隐藏、404、缓存清除）
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api.v1.data.data.dashboard as dash
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.unified_data_scope import get_org_scope
from app.models.supported_village import SupportedVillage


# ==================== 公共设施 ====================


def _scope(full_access=True, org_ids=None, org_names=None):
    """构造 OrgScopeFilter mock：filter_by_org_ids 透传查询"""
    scope = MagicMock()
    scope.has_full_access = MagicMock(return_value=full_access)
    scope.org_ids = org_ids if org_ids is not None else [1]
    scope.org_names = org_names if org_names is not None else []
    scope.filter_by_org_ids = MagicMock(side_effect=lambda q, *a, **k: q)
    return scope


def _q(**kw):
    """通用查询链 mock：scalar/first/all 可配，其余链式调用自返回"""
    q = MagicMock()
    for attr in ("filter", "order_by", "limit", "offset", "group_by", "select_from", "options", "subquery", "in_"):
        getattr(q, attr).return_value = q
    q.scalar.return_value = kw.get("scalar")
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


def _db_with_queries(queries):
    """db.query 按调用顺序依次返回给定查询链"""
    db = MagicMock()
    db.query = MagicMock(side_effect=list(queries))
    return db


def _pop_inner_select():
    """人口汇总中 supported_village_id.in_(db.query(...)) 的内层查询返回值

    内层 db.query 的返回值会传入真实 SQLAlchemy 列的 in_()，
    必须是真实 selectable，否则 in_() 强转报错。
    """
    return select(SupportedVillage.id).scalar_subquery()


@pytest.fixture
def admin_user():
    u = Mock()
    u.id = 1
    u.username = "admin"
    u.name = "管理员"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    return u


@pytest.fixture
def cov_client(admin_user):
    """注入 mock 数据范围（全量访问）的客户端，db 由各测试自定义"""
    from app.main import app

    original = app.dependency_overrides.copy()

    async def mu():
        return admin_user

    app.dependency_overrides[get_current_user] = mu
    app.dependency_overrides[get_org_scope] = lambda: _scope(True)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _override_db(client, db):
    client.app.dependency_overrides[get_db] = lambda: db


# ==================== _query_village_stats ====================


class TestQueryVillageStats:
    def test_with_population_row(self):
        db = _db_with_queries([
            _q(),                                    # village_query（透传过滤）
            _q(scalar=3),                            # total_villages
            _q(scalar=2026),                         # latest_year
            _q(first=(1000, 120)),                   # pop_row（外层查询先求值）
            _pop_inner_select(),                     # pop in_() 内层子查询
            _q(first=(5, 3, 500, 60)),               # school_row
        ])
        result = dash._query_village_stats(db, _scope(True))
        assert result["total_villages"] == 3
        assert result["total_population"] == 1000
        assert result["total_households"] == 120
        assert result["total_schools"] == 5
        assert result["schools_active"] == 3
        assert result["total_students"] == 500
        assert result["total_teachers"] == 60

    def test_no_population_when_zero_villages(self):
        """total_villages=0 时跳过人口汇总（pop_row 不查询）"""
        db = _db_with_queries([
            _q(),
            _q(scalar=0),                            # total_villages=0
            _q(scalar=2026),                         # latest_year
            _q(first=None),                          # school_row 为 None → 全部回退 0
        ])
        result = dash._query_village_stats(db, _scope(True))
        assert result["total_villages"] == 0
        assert result["total_population"] == 0
        assert result["total_schools"] == 0

    def test_no_latest_year_skips_population(self):
        db = _db_with_queries([
            _q(),
            _q(scalar=2),
            _q(scalar=None),                         # 无人口年份
            _q(first=(1, 1, 100, 10)),
        ])
        result = dash._query_village_stats(db, _scope(True))
        assert result["total_villages"] == 2
        assert result["total_population"] == 0


# ==================== _query_fund_stats ====================


class TestQueryFundStats:
    def test_full_access_aggregation(self):
        db = _db_with_queries([
            _q(all=[("approved", 100.0), ("pending", 30.0), ("planned", 20.0), ("other", 5.0)]),
        ])
        result = dash._query_fund_stats(db, _scope(True))
        assert result["total_funds"] == 155.0
        assert result["funds_allocated"] == 100.0
        assert result["funds_pending"] == 30.0
        assert result["funds_planned"] == 20.0

    def test_limited_access_with_villages(self):
        """非全量访问：有可访问村 → village_id IN 或 NULL 过滤"""
        db = _db_with_queries([
            _q(all=[("allocated", 50.0)]),           # fund 聚合查询（先发起）
            _q(all=[(1,), (2,)]),                    # accessible_village_ids
        ])
        result = dash._query_fund_stats(db, _scope(False))
        assert result["funds_allocated"] == 50.0
        assert result["total_funds"] == 50.0

    def test_limited_access_no_villages(self):
        """非全量访问：无可访问村 → 只统计未关联村经费"""
        db = _db_with_queries([
            _q(all=[("completed", 80.0)]),           # fund 聚合查询
            _q(all=[]),                              # 无可访问村
        ])
        result = dash._query_fund_stats(db, _scope(False))
        assert result["funds_allocated"] == 80.0  # completed ∈ allocated_statuses


# ==================== _query_project_approval_stats ====================


class TestQueryProjectApprovalStats:
    def _run(self, scope, approval_side_effect=None, villages=2, filled=10):
        queries = [
            _q(first=(10, 4)),                       # proj_row
            _q(scalar=approval_side_effect if approval_side_effect is not None else 3),
            _q(scalar=8),                            # total_users
            _q(scalar=villages),                     # total_villages_count
            _q(scalar=filled),                       # total_filled
        ]
        db = _db_with_queries(queries)
        return dash._query_project_approval_stats(db, scope)

    def test_full_access(self):
        result = self._run(_scope(True))
        assert result["total_projects"] == 10
        assert result["active_projects"] == 4
        assert result["pending_approvals"] == 3
        assert result["total_users"] == 8
        # completeness = min(10 / (2 * expected_years), 1)
        expected_years = max(datetime.now().year - 2021 + 1, 1)
        assert result["data_completeness"] == round(min(10 / (2 * expected_years), 1.0), 4)

    def test_limited_access_org_ids(self):
        """有 organization_id 且 org_ids 非空 → filter_by_org_ids 被调用"""
        scope = _scope(False, org_ids=[7])
        result = self._run(scope)
        assert result["total_projects"] == 10
        scope.filter_by_org_ids.assert_called()

    def test_limited_access_org_names_fallback(self):
        """org_ids 空 + org_names 非空 → 文本匹配回退"""
        scope = _scope(False, org_ids=[], org_names=["火箭军某部"])
        result = self._run(scope)
        assert result["total_projects"] == 10

    def test_limited_access_short_names_filter_false(self):
        """org_names 全部短于2字符 → conditions 空 → filter(False)"""
        scope = _scope(False, org_ids=[], org_names=["甲"])
        result = self._run(scope)
        assert result["total_projects"] == 10

    def test_approval_query_exception(self):
        """审批查询异常 → 警告并 pending_approvals=0"""
        bad_q = MagicMock()
        bad_q.filter.return_value = bad_q
        bad_q.scalar.side_effect = Exception("no table")
        db = _db_with_queries([
            _q(first=(10, 4)),
            bad_q,                                   # approval 查询抛异常
            _q(scalar=8),
            _q(scalar=0),                            # total_villages_count=0 → 跳过完整性
        ])
        result = dash._query_project_approval_stats(db, _scope(True))
        assert result["pending_approvals"] == 0
        assert result["data_completeness"] == 0.0

    def test_completeness_capped_at_one(self):
        result = self._run(_scope(True), villages=1, filled=99999)
        assert result["data_completeness"] == 1.0


# ==================== GET /dashboard/stats 有数据路径 ====================


class TestStatsWithData:
    def test_stats_success_and_cached(self, cov_client):
        db = _db_with_queries([
            # village_stats（含 pop in_() 内层子查询）
            _q(), _q(scalar=3), _q(scalar=2026), _q(first=(1000, 120)),
            _pop_inner_select(), _q(first=(5, 3, 500, 60)),
            # fund_stats
            _q(all=[("approved", 100.0)]),
            # project_approval_stats
            _q(first=(10, 4)), _q(scalar=3), _q(scalar=8), _q(scalar=2), _q(scalar=10),
        ])
        _override_db(cov_client, db)
        with patch.object(dash, "_cache", None):
            resp = cov_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_villages"] == 3
        assert data["total_funds"] == 100.0
        assert data["total_projects"] == 10

    def test_stats_writes_cache(self, cov_client):
        db = _db_with_queries([
            _q(), _q(scalar=3), _q(scalar=2026), _q(first=(1000, 120)),
            _pop_inner_select(), _q(first=(5, 3, 500, 60)),
            _q(all=[("approved", 100.0)]),
            _q(first=(10, 4)), _q(scalar=3), _q(scalar=8), _q(scalar=2), _q(scalar=10),
        ])
        _override_db(cov_client, db)
        with patch.object(dash, "_cache") as mc:
            mc.get.return_value = None
            resp = cov_client.get("/api/v1/dashboard/stats")
            assert resp.status_code == 200
            mc.set.assert_called_once()


# ==================== GET /dashboard/summary ====================


class TestDashboardSummary:
    def _activities_stub(self, items):
        return {"items": items}

    def test_summary_success(self, cov_client):
        db = _db_with_queries([
            _q(), _q(scalar=3), _q(scalar=2026), _q(first=(1000, 120)),
            _pop_inner_select(), _q(first=(5, 3, 500, 60)),
            _q(all=[("approved", 100.0)]),
            _q(first=(10, 4)), _q(scalar=3), _q(scalar=8), _q(scalar=2), _q(scalar=10),
        ])
        _override_db(cov_client, db)
        with patch.object(dash, "_cache", None), patch.object(
            dash, "get_recent_activities", return_value=self._activities_stub([{"id": "x"}])
        ) as m_act:
            async def fake_act(**kwargs):
                return {"items": [{"id": "x"}]}
            m_act.side_effect = fake_act
            resp = cov_client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_villages"] == 3
        assert data["recent_activities"] == [{"id": "x"}]

    def test_summary_cached(self, cov_client):
        with patch.object(dash, "_cache") as mc:
            mc.get.return_value = {"stats": {}, "recent_activities": []}
            resp = cov_client.get("/api/v1/dashboard/summary")
            assert resp.json() == {"stats": {}, "recent_activities": []}

    def test_summary_stats_exception_degrades(self, cov_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("db boom"))
        _override_db(cov_client, db)
        with patch.object(dash, "_cache", None), patch.object(dash, "get_recent_activities") as m_act:
            async def fake_act(**kwargs):
                return {"items": []}
            m_act.side_effect = fake_act
            resp = cov_client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 200
        assert resp.json()["stats"] == {}


# ==================== _fetch_* 动态获取器 ====================


def _sess_with(queries):
    """SessionLocal 工厂 mock：query 按序返回链，close 可调用"""
    sess = MagicMock()
    sess.query = MagicMock(side_effect=list(queries))
    sess.close = MagicMock()
    return sess


class TestFetchActivities:
    def test_fetch_hidden_activities(self):
        sess = _sess_with([_q(all=[("project_1",), ("fund_2",)])])
        with patch.object(dash, "SessionLocal", return_value=sess):
            hidden = dash._fetch_hidden_activities()
        assert hidden == {"project_1", "fund_2"}
        sess.close.assert_called_once()

    def test_fetch_hidden_activities_exception(self):
        sess = _sess_with([])
        sess.query = MagicMock(side_effect=Exception("no table"))
        with patch.object(dash, "SessionLocal", return_value=sess):
            hidden = dash._fetch_hidden_activities()
        assert hidden == set()
        sess.close.assert_called_once()

    def test_fetch_custom_activities(self):
        act = SimpleNamespace(
            id=1, type="project", action="创建了", target="项目A",
            user="张三", created_at=datetime(2026, 7, 24, 9, 0),
        )
        sess = _sess_with([_q(all=[act])])
        with patch.object(dash, "SessionLocal", return_value=sess):
            items = dash._fetch_custom_activities()
        assert len(items) == 1
        assert items[0]["id"] == "custom_1"
        assert items[0]["_custom"] is True
        assert items[0]["time"] == "07-24 09:00"

    def test_fetch_custom_activities_defaults_and_exception(self):
        act = SimpleNamespace(id=2, type=None, action=None, target=None, user=None, created_at=None)
        sess = _sess_with([_q(all=[act])])
        with patch.object(dash, "SessionLocal", return_value=sess):
            items = dash._fetch_custom_activities()
        assert items[0]["type"] == "project"
        assert items[0]["user"] == "系统"
        assert items[0]["time"] == ""
        sess2 = _sess_with([])
        sess2.query = MagicMock(side_effect=Exception("x"))
        with patch.object(dash, "SessionLocal", return_value=sess2):
            assert dash._fetch_custom_activities() == []

    def test_fetch_project_activities(self):
        created = datetime(2026, 7, 1, 8, 0)
        updated_same = created
        updated_later = datetime(2026, 7, 20, 8, 0)
        p1 = SimpleNamespace(id=1, name="项目甲", responsible_person="李四", updated_at=updated_same, created_at=created)
        p2 = SimpleNamespace(id=2, name=None, responsible_person=None, leader="王五", updated_at=updated_later, created_at=created)
        sess = _sess_with([_q(all=[p1, p2])])
        with patch.object(dash, "SessionLocal", return_value=sess):
            items = dash._fetch_project_activities()
        assert items[0]["action"] == "创建了"
        assert items[1]["action"] == "更新了"
        assert items[1]["target"] == ""
        assert items[1]["user"] == "王五"

    def test_fetch_project_activities_exception(self):
        sess = _sess_with([])
        sess.query = MagicMock(side_effect=Exception("x"))
        with patch.object(dash, "SessionLocal", return_value=sess):
            assert dash._fetch_project_activities() == []

    def test_fetch_fund_activities(self):
        f1 = SimpleNamespace(id=1, name="经费A", status="approved", applicant="赵六", updated_at=datetime(2026, 7, 2, 8, 0))
        f2 = SimpleNamespace(id=2, name=None, status="unknown_status", applicant=None, updated_at=None)
        sess = _sess_with([_q(all=[f1, f2])])
        with patch.object(dash, "SessionLocal", return_value=sess):
            items = dash._fetch_fund_activities()
        assert items[0]["action"] == "审批通过"
        assert items[1]["action"] == "更新了"  # 未知状态回退
        assert items[1]["user"] == "系统"
        assert items[1]["time"] == ""

    def test_fetch_fund_activities_exception(self):
        sess = _sess_with([])
        sess.query = MagicMock(side_effect=Exception("x"))
        with patch.object(dash, "SessionLocal", return_value=sess):
            assert dash._fetch_fund_activities() == []

    def test_fetch_approval_activities(self):
        a1 = SimpleNamespace(
            id=1, status="pending", title="审批甲", entity_type="fund", entity_id=3,
            submitter=SimpleNamespace(username="审批人"),
            updated_at=datetime(2026, 7, 3, 8, 0), created_at=datetime(2026, 7, 1, 8, 0),
        )
        a2 = SimpleNamespace(
            id=2, status="weird", title=None, entity_type="fund", entity_id=4,
            submitter=None, updated_at=None, created_at=None,
        )
        sess = _sess_with([_q(all=[a1, a2])])
        with patch.object(dash, "SessionLocal", return_value=sess):
            items = dash._fetch_approval_activities()
        assert items[0]["action"] == "待审批"
        assert items[0]["user"] == "审批人"
        assert items[1]["action"] == "weird"  # 未知状态原样
        assert items[1]["target"] == "fund#4"
        assert items[1]["user"] == "系统"
        assert items[1]["time"] == ""

    def test_fetch_approval_activities_exception(self):
        sess = _sess_with([])
        sess.query = MagicMock(side_effect=Exception("x"))
        with patch.object(dash, "SessionLocal", return_value=sess):
            assert dash._fetch_approval_activities() == []


# ==================== GET /dashboard/recent-activities ====================


class TestRecentActivitiesEndpoint:
    def test_aggregates_sorts_filters_hidden(self, cov_client):
        custom = [{"id": "custom_1", "time": "07-24 10:00", "type": "project"}]
        project = [{"id": "project_1", "time": "07-23 10:00", "type": "project"}]
        fund = [{"id": "fund_1", "time": "07-25 10:00", "type": "fund"}]
        approval = [{"id": "approval_1", "time": "07-22 10:00", "type": "approval"}]
        with patch.object(dash, "_cache", None), patch.object(
            dash, "_fetch_hidden_activities", return_value={"approval_1"}
        ), patch.object(dash, "_fetch_custom_activities", return_value=custom), patch.object(
            dash, "_fetch_project_activities", return_value=project
        ), patch.object(dash, "_fetch_fund_activities", return_value=fund), patch.object(
            dash, "_fetch_approval_activities", return_value=approval
        ):
            resp = cov_client.get("/api/v1/dashboard/recent-activities")
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = [i["id"] for i in items]
        assert "approval_1" not in ids  # 隐藏被过滤
        assert ids == ["fund_1", "custom_1", "project_1"]  # 按时间倒序

    def test_recent_cached(self, cov_client):
        with patch.object(dash, "_cache") as mc:
            mc.get.return_value = {"items": [{"id": "cached"}]}
            resp = cov_client.get("/api/v1/dashboard/recent-activities")
            assert resp.json() == {"items": [{"id": "cached"}]}

    def test_recent_slice_to_10(self, cov_client):
        many = [{"id": f"custom_{i}", "time": f"07-{10 + i:02d} 00:00"} for i in range(15)]
        with patch.object(dash, "_cache", None), patch.object(
            dash, "_fetch_hidden_activities", return_value=set()
        ), patch.object(dash, "_fetch_custom_activities", return_value=many), patch.object(
            dash, "_fetch_project_activities", return_value=[]
        ), patch.object(dash, "_fetch_fund_activities", return_value=[]), patch.object(
            dash, "_fetch_approval_activities", return_value=[]
        ):
            resp = cov_client.get("/api/v1/dashboard/recent-activities")
        assert len(resp.json()["items"]) == 10


# ==================== recent-activities CRUD ====================


class TestActivityCrud:
    def test_create_activity_success(self, cov_client, admin_user):
        db = MagicMock()

        def _refresh(obj):
            obj.id = 5
            obj.created_at = datetime(2026, 7, 24, 12, 0)

        db.refresh.side_effect = _refresh
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache") as mc:
            resp = cov_client.post(
                "/api/v1/dashboard/recent-activities",
                json={"type": "fund", "action": "拨付", "target": "经费X"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "custom_5"
        assert data["user"] == "管理员"
        assert data["time"] == "07-24 12:00"
        db.add.assert_called_once()
        mc.delete.assert_called_once_with("dashboard_recent_activities")

    def test_create_activity_user_fallback(self, cov_client):
        db = MagicMock()
        db.refresh.side_effect = lambda obj: setattr(obj, "id", 6)
        cov_client.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, name=None, username=None)
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache", None):
            resp = cov_client.post(
                "/api/v1/dashboard/recent-activities",
                json={"action": "操作", "target": "对象"},
            )
        assert resp.status_code == 200
        assert resp.json()["user"] == "系统"

    def test_create_activity_exception_500(self, cov_client):
        db = MagicMock()
        db.add.side_effect = Exception("db err")
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"):
            resp = cov_client.post(
                "/api/v1/dashboard/recent-activities",
                json={"action": "操作", "target": "对象"},
            )
        assert resp.status_code == 500
        assert "db err" in resp.json()["detail"]
        db.rollback.assert_called_once()

    def test_update_custom_activity(self, cov_client):
        activity = SimpleNamespace(id=3, type="project", action="旧", target="旧目标")
        q = _q(first=activity)
        db = _db_with_queries([q])
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache") as mc:
            resp = cov_client.put(
                "/api/v1/dashboard/recent-activities/custom_3",
                json={"action": "新", "target": "新目标"},
            )
        assert resp.status_code == 200
        assert activity.action == "新"
        assert activity.target == "新目标"
        assert activity.type == "project"  # 未提供则不变
        mc.delete.assert_called_once()

    def test_update_custom_activity_not_found(self, cov_client):
        db = _db_with_queries([_q(first=None)])
        _override_db(cov_client, db)
        resp = cov_client.put(
            "/api/v1/dashboard/recent-activities/custom_99",
            json={"action": "新"},
        )
        assert resp.status_code == 404

    def test_update_system_activity_rejected(self, cov_client):
        db = MagicMock()
        _override_db(cov_client, db)
        resp = cov_client.put(
            "/api/v1/dashboard/recent-activities/project_5",
            json={"action": "新"},
        )
        assert resp.status_code == 200
        assert "无法更新" in resp.json()["message"]

    def test_update_activity_exception_500(self, cov_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("boom"))
        _override_db(cov_client, db)
        resp = cov_client.put(
            "/api/v1/dashboard/recent-activities/custom_1",
            json={"action": "新"},
        )
        assert resp.status_code == 500
        db.rollback.assert_called_once()

    def test_delete_custom_activity(self, cov_client):
        activity = SimpleNamespace(id=7)
        db = _db_with_queries([_q(first=activity)])
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache") as mc:
            resp = cov_client.delete("/api/v1/dashboard/recent-activities/custom_7")
        assert resp.status_code == 200
        db.delete.assert_called_once_with(activity)
        mc.delete.assert_called_once()

    def test_delete_custom_activity_not_found_skips(self, cov_client):
        db = _db_with_queries([_q(first=None)])
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache", None):
            resp = cov_client.delete("/api/v1/dashboard/recent-activities/custom_88")
        assert resp.status_code == 200
        db.delete.assert_not_called()

    def test_delete_system_activity_hides(self, cov_client):
        db = _db_with_queries([_q(first=None)])  # 尚未隐藏
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache", None):
            resp = cov_client.delete("/api/v1/dashboard/recent-activities/project_9")
        assert resp.status_code == 200
        db.add.assert_called_once()  # 写入隐藏表

    def test_delete_system_activity_already_hidden(self, cov_client):
        db = _db_with_queries([_q(first=SimpleNamespace(id=1))])  # 已隐藏
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache", None):
            resp = cov_client.delete("/api/v1/dashboard/recent-activities/project_9")
        assert resp.status_code == 200
        db.add.assert_not_called()

    def test_delete_activity_exception_500(self, cov_client):
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("boom"))
        _override_db(cov_client, db)
        resp = cov_client.delete("/api/v1/dashboard/recent-activities/project_1")
        assert resp.status_code == 500
        db.rollback.assert_called_once()


# ==================== 缓存读写与兜底分支补盲 ====================


class TestCacheAndFallbackBranches:
    def test_stats_cache_hit(self, cov_client):
        """stats 缓存命中 → 直接返回缓存（覆盖 return cached）"""
        with patch.object(dash, "_cache") as mc:
            mc.get.return_value = {"total_villages": 9}
            resp = cov_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        assert resp.json() == {"total_villages": 9}

    def test_stats_no_data_returns_null(self, cov_client):
        """统计全为 0 → 返回 None，前端显示空状态（覆盖 has_data=False）"""
        db = _db_with_queries([
            _q(), _q(scalar=0), _q(scalar=None), _q(first=None),   # village 全 0（跳过人口）
            _q(all=[]),                                            # fund 全 0
            _q(first=(0, 0)), _q(scalar=0), _q(scalar=0), _q(scalar=0),  # project 全 0
        ])
        _override_db(cov_client, db)
        with patch.object(dash, "_cache", None):
            resp = cov_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_stats_exception_returns_null(self, cov_client):
        """统计查询异常 → 降级返回 None（覆盖 except 分支）"""
        db = MagicMock()
        db.query = MagicMock(side_effect=Exception("db boom"))
        _override_db(cov_client, db)
        with patch.object(dash, "_cache", None):
            resp = cov_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_cache_read_write_exception_still_computes(self, cov_client):
        """缓存读/写均异常 → 正常计算并返回（覆盖 _get_cached/_set_cached 异常分支）"""
        db = _db_with_queries([
            _q(), _q(scalar=1), _q(scalar=None), _q(first=(1, 1, 1, 1)),
            _q(all=[]),
            _q(first=(0, 0)), _q(scalar=0), _q(scalar=0), _q(scalar=0),
        ])
        _override_db(cov_client, db)
        with patch.object(dash, "_cache") as mc:
            mc.get.side_effect = Exception("cache down")
            mc.set.side_effect = Exception("cache down")
            resp = cov_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        assert resp.json()["total_villages"] == 1

    def test_invalidate_dashboard_cache(self):
        """invalidate_dashboard_cache 正常/异常/无缓存三分支"""
        with patch.object(dash, "_cache") as mc:
            dash.invalidate_dashboard_cache()
            mc.clear.assert_called_once()
        with patch.object(dash, "_cache") as mc:
            mc.clear.side_effect = Exception("x")
            dash.invalidate_dashboard_cache()  # 异常被吞掉，不向外抛
        with patch.object(dash, "_cache", None):
            dash.invalidate_dashboard_cache()  # 无缓存直接返回

    def test_org_names_with_department_attr(self, monkeypatch):
        """Project 具备 department 属性时文本回退拼接 department 条件（覆盖 238 行）"""

        class _FakeCol:
            def contains(self, name):
                return dash.Project.responsible_unit.contains(name)

        monkeypatch.setattr(dash.Project, "department", _FakeCol(), raising=False)
        scope = _scope(False, org_ids=[], org_names=["某部"])
        db = _db_with_queries([
            _q(first=(10, 4)), _q(scalar=3), _q(scalar=8), _q(scalar=0),
        ])
        result = dash._query_project_approval_stats(db, scope)
        assert result["total_projects"] == 10

    def test_create_cache_delete_exception_ignored(self, cov_client):
        """创建动态后清缓存异常 → 不影响创建（覆盖 525-526）"""
        db = MagicMock()
        db.refresh.side_effect = lambda obj: setattr(obj, "id", 8)
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache") as mc:
            mc.delete.side_effect = Exception("cache err")
            resp = cov_client.post(
                "/api/v1/dashboard/recent-activities",
                json={"action": "操作", "target": "对象"},
            )
        assert resp.status_code == 200

    def test_update_with_type_and_cache_delete_exception(self, cov_client):
        """更新带 type 字段（覆盖 557）且清缓存异常被吞（覆盖 567-568）"""
        activity = SimpleNamespace(id=3, type="project", action="旧", target="旧目标")
        db = _db_with_queries([_q(first=activity)])
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache") as mc:
            mc.delete.side_effect = Exception("cache err")
            resp = cov_client.put(
                "/api/v1/dashboard/recent-activities/custom_3",
                json={"type": "fund", "action": "新"},
            )
        assert resp.status_code == 200
        assert activity.type == "fund"
        assert activity.action == "新"

    def test_delete_cache_delete_exception_ignored(self, cov_client):
        """删除动态后清缓存异常 → 不影响删除（覆盖 609-610）"""
        db = _db_with_queries([_q(first=SimpleNamespace(id=7))])
        _override_db(cov_client, db)
        with patch.object(dash, "safe_commit"), patch.object(dash, "_cache") as mc:
            mc.delete.side_effect = Exception("cache err")
            resp = cov_client.delete("/api/v1/dashboard/recent-activities/custom_7")
        assert resp.status_code == 200
