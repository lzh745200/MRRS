"""
Comprehensive pytest tests for funds.py API routes.
Covers all 25+ endpoints with Mock DB, edge cases, and error paths.
Uses FastAPI TestClient with dependency overrides for get_db and get_current_user.

KEY DESIGN DECISION: Fund instances use a plain object (FundMock) instead of
unittest.mock.Mock, because _safe_val() checks hasattr(val, "isoformat") which
is always True for Mock objects (Mock auto-creates attributes). This would
cause infinite recursion during JSON serialization.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient


# ============================================================================
# Plain-object helpers (NOT Mock) to avoid hasattr(…, "isoformat") traps
# ============================================================================

class FundMock:
    """Plain object mimicking a Fund ORM instance. Only attributes set in
    __init__ are accessible — missing ones raise AttributeError, so _safe_val
    does not mistake arbitrary values for datetime/date."""
    def __init__(self, fund_id=1, **overrides):
        defaults = dict(
            id=fund_id,
            date=date(2025, 6, 15),
            type="project",
            fund_type="project",
            fund_source="military",
            amount=Decimal("500.00"),
            planned_amount=Decimal("500.00"),
            approved_amount=Decimal("500.00"),
            allocated_amount=Decimal("200.00"),
            used_amount=Decimal("100.00"),
            remaining_amount=Decimal("400.00"),
            code="F001",
            name="测试经费",
            project_id=1,
            project_name="测试项目",
            village_id=1,
            school_id=None,
            purpose="测试用途",
            source="专项拨款",
            operator="张三",
            receiver=None,
            usage_description="使用说明",
            status="pending",
            applicant="李四",
            application_date=datetime(2025, 6, 10, tzinfo=timezone.utc),
            approved_by=None,
            approval_date=None,
            allocation_date=None,
            allocation_method=None,
            start_date=None,
            end_date=None,
            audit_date=None,
            audit_result=None,
            audit_opinion=None,
            remarks="备注",
            lifecycle_phase=1,
            budget_locked=False,
            deviation_rate=Decimal("0.00"),
            health_score=100,
            has_anomaly=False,
            settlement_status=None,
            budget_version=1,
            budget_status="draft",
            organization_id=1,
            created_by=1,
            year=2025,
            year_month="2025-06",
            year_quarter="2025-Q2",
            # Extra columns that Fund.__table__.columns might reference
            is_deleted=False,
            deleted_at=None,
            sync_version=1,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
            version=1,
        )
        defaults.update(overrides)
        for k, v in defaults.items():
            object.__setattr__(self, k, v)

        # Attach relationships
        object.__setattr__(self, "project", None)
        object.__setattr__(self, "village", None)
        object.__setattr__(self, "organization", None)


class SimpleObj:
    """Generic plain-object holder (used for DB row results, attachments, etc.)"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db():
    """Returns a MagicMock that mimics a SQLAlchemy Session."""
    db = MagicMock()
    db.commit.return_value = None
    db.add.return_value = None
    db.delete.return_value = None
    db.refresh.return_value = None
    db.flush.return_value = None
    return db


@pytest.fixture
def admin_user():
    """Admin user fixture — has full permissions (is_superuser=True)."""
    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1
    user.email = "admin@test.com"
    user.full_name = "管理员"
    return user


@pytest.fixture
def regular_user():
    """Regular non-admin user fixture."""
    user = Mock()
    user.id = 2
    user.username = "villager"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = []
    user.organization_id = 2
    user.email = "villager@test.com"
    user.full_name = "村民"
    return user


@pytest.fixture
def manager_user():
    """Manager user — has admin role but not superuser."""
    user = Mock()
    user.id = 3
    user.username = "manager"
    user.role = "manager"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = []
    user.organization_id = 1
    user.email = "manager@test.com"
    user.full_name = "经理"
    return user


# ----------- execute-result helper factories -----------

def _exec_with_scalar_one_or_none(value):
    """db.execute(…) -> result.scalar_one_or_none() == value"""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _exec_with_scalars_unique_all(items):
    """db.execute(…) -> result.scalars().unique().all() == items"""
    s = MagicMock()
    s.all.return_value = items
    u = MagicMock()
    u.all.return_value = items
    s.unique.return_value = u
    r = MagicMock()
    r.scalars.return_value = s
    return r


def _exec_with_all(rows):
    """db.execute(…) -> result.all() == rows (for aggregate queries)"""
    r = MagicMock()
    r.all.return_value = rows
    return r


# ----------- client factories -----------


def _build_client(user, mock_db):
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    def _get_db():
        yield mock_db

    async def _get_current_user():
        return user

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    client = TestClient(app, raise_server_exceptions=False)
    return client, app, _original_overrides


@pytest.fixture
def client(admin_user, mock_db):
    """TestClient with admin privileges. apply_scope_filter is patched as no-op."""
    with patch("app.api.v1.funds.apply_scope_filter",
               side_effect=lambda stmt, *a, **kw: stmt):
        c, app, orig = _build_client(admin_user, mock_db)
        yield c
        app.dependency_overrides = orig


@pytest.fixture
def client_regular(regular_user, mock_db):
    """TestClient with regular user privileges."""
    with patch("app.api.v1.funds.apply_scope_filter",
               side_effect=lambda stmt, *a, **kw: stmt):
        c, app, orig = _build_client(regular_user, mock_db)
        yield c
        app.dependency_overrides = orig


@pytest.fixture
def client_manager(manager_user, mock_db):
    """TestClient with manager role."""
    with patch("app.api.v1.funds.apply_scope_filter",
               side_effect=lambda stmt, *a, **kw: stmt):
        c, app, orig = _build_client(manager_user, mock_db)
        yield c
        app.dependency_overrides = orig


# ============================================================================
# 1. list_funds — GET /api/v1/funds
# ============================================================================


class TestListFunds:
    def test_list_funds_offset_pagination_empty(self, client, mock_db):
        """List returns empty result."""
        mock_db.execute.return_value = _exec_with_scalars_unique_all([])
        # The first execute call is the count query (select(func.count())...)
        # The second execute call is the items query.
        # We need BOTH to return compatible results.  Use side_effect.
        count_r = MagicMock()
        count_r.scalar_one.return_value = 0
        items_r = _exec_with_scalars_unique_all([])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 0
        assert data["pagination"] == "offset"
        assert data["data"]["items"] == []

    def test_list_funds_offset_pagination_with_items(self, client, mock_db):
        """List with offset pagination returns fund items."""
        fund1 = FundMock(1, name="项目经费A", fund_type="project", fund_source="military",
                         project_name=None, village_name=None)
        fund1.project = None
        fund1.village = None

        count_r = MagicMock()
        count_r.scalar_one.return_value = 1
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 1
        assert data["data"]["page"] == 1
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["name"] == "项目经费A"

    def test_list_funds_keyset_pagination(self, client, mock_db):
        """List with keyset pagination."""
        fund1 = FundMock(5, name="经费K")
        fund1.project = None
        fund1.village = None
        keyset_result = {
            "items": [fund1], "total": 1, "page_size": 20,
            "next_cursor": "abc123", "has_more": False,
        }
        with patch("app.api.v1.funds.keyset_paginate", return_value=keyset_result):
            resp = client.get("/api/v1/funds?pagination=keyset")
            assert resp.status_code == 200
            data = resp.json()
            assert data["pagination"] == "keyset"
            assert data["next_cursor"] == "abc123"

    def test_list_funds_with_status_filter(self, client, mock_db):
        """List filtered by status."""
        fund1 = FundMock(1, status="approved")
        fund1.project = None
        fund1.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 1
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?status=approved")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_list_funds_with_keyword_filter(self, client, mock_db):
        """List with keyword search."""
        fund1 = FundMock(1, name="匹配项目")
        fund1.project = None
        fund1.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 1
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?keyword=匹配")
        assert resp.status_code == 200

    def test_list_funds_with_fund_type_filter(self, client, mock_db):
        """List filtered by fund_type."""
        fund1 = FundMock(1, fund_type="education")
        fund1.project = None
        fund1.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 1
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?fund_type=education")
        assert resp.status_code == 200

    def test_list_funds_with_fund_source_filter(self, client, mock_db):
        """List filtered by fund_source."""
        fund1 = FundMock(1, fund_source="government")
        fund1.project = None
        fund1.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 1
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?fund_source=government")
        assert resp.status_code == 200

    def test_list_funds_with_project_id_filter(self, client, mock_db):
        """List filtered by project_id."""
        fund1 = FundMock(1, project_id=5)
        fund1.project = None
        fund1.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 1
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?project_id=5")
        assert resp.status_code == 200

    def test_list_funds_with_page_and_page_size(self, client, mock_db):
        """List with custom page parameters."""
        fund1 = FundMock(1)
        fund1.project = None
        fund1.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 50
        items_r = _exec_with_scalars_unique_all([fund1])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?page=2&page_size=10")
        assert resp.status_code == 200


# ============================================================================
# 3. get_fund — GET /api/v1/funds/{fund_id}
# ============================================================================


class TestGetFund:
    def test_get_fund_success(self, client, mock_db):
        """Get a single fund by ID."""
        fund1 = FundMock(42)
        fund1.project = None
        fund1.village = None
        fund1.organization = None
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund1)

        resp = client.get("/api/v1/funds/42")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["id"] == 42
        assert data["data"]["name"] == "测试经费"

    def test_get_fund_not_found(self, client, mock_db):
        """Non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.get("/api/v1/funds/999")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_get_fund_with_association_names(self, client, mock_db):
        """Fund detail includes project_name and village_name from associations."""
        fund1 = FundMock(1)
        fund1.project = SimpleObj(name="项目A")
        fund1.village = SimpleObj(village_name="村庄B")
        fund1.organization = SimpleObj(name="组织C")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund1)

        resp = client.get("/api/v1/funds/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["project_name"] == "项目A"
        assert data["village_name"] == "村庄B"


# ============================================================================
# 4. create_fund — POST /api/v1/funds
# ============================================================================


class TestCreateFund:
    def test_create_fund_admin_success(self, client, mock_db):
        """Admin creates a fund successfully."""
        created = Mock()
        created.id = 100
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            resp = client.post("/api/v1/funds", json={
                "name": "新经费", "amount": 10000,
                "fund_type": "project", "purpose": "新建项目",
            })
            assert resp.status_code == 201
            assert resp.json()["data"]["id"] == 100

    def test_create_fund_regular_user_allowed(self, client_regular, mock_db):
        """普通用户（user）也可直接创建经费记录（产品要求：经费全流程对普通用户开放）。"""
        created = Mock()
        created.id = 100
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            resp = client_regular.post("/api/v1/funds", json={
                "name": "新经费", "amount": 1000,
            })
            assert resp.status_code == 201
            assert resp.json()["data"]["id"] == 100

    def test_create_fund_with_all_fields(self, client, mock_db):
        """Create with all optional fields populated."""
        created = Mock()
        created.id = 101
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            payload = {
                "name": "综合经费", "amount": 50000, "planned_amount": 50000,
                "approved_amount": 50000, "allocated_amount": 20000,
                "used_amount": 10000, "remaining_amount": 40000,
                "code": "F-CUSTOM-001", "type": "project",
                "fund_type": "infrastructure", "fund_source": "military",
                "project_id": 10, "project_name": "基础设施",
                "village_id": 5, "school_id": 2,
                "purpose": "基础设施建设", "source": "专项",
                "operator": "王五", "receiver": "赵六",
                "usage_description": "建设村道", "status": "pending",
                "applicant": "张三", "remarks": "紧急",
                "date": "2025-07-01", "start_date": "2025-07-15",
                "end_date": "2025-12-31",
            }
            resp = client.post("/api/v1/funds", json=payload)
            assert resp.status_code == 201
            assert resp.json()["message"] == "创建成功"

    def test_create_fund_default_values(self, client, mock_db):
        """Create with minimal fields uses defaults."""
        created = Mock()
        created.id = 102
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            resp = client.post("/api/v1/funds", json={})
            assert resp.status_code == 201


# ============================================================================
# 5. apply_fund — POST /api/v1/funds/apply
# ============================================================================


class TestApplyFund:
    def test_apply_fund_admin_success(self, client, mock_db):
        """Admin user can also apply for funds."""
        created = Mock()
        created.id = 200
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            resp = client.post("/api/v1/funds/apply", json={
                "name": "我的申请", "amount": 3000, "purpose": "教育帮扶",
            })
            assert resp.status_code == 201
            data = resp.json()
            assert data["message"] == "申请已提交，等待审批"
            assert data["data"]["id"] == 200

    def test_apply_fund_regular_user(self, client_regular, mock_db):
        """Regular user can apply for funds (no admin required)."""
        created = Mock()
        created.id = 201
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            resp = client_regular.post("/api/v1/funds/apply", json={
                "name": "村民申请", "amount": 1000, "fund_type": "education",
            })
            assert resp.status_code == 201
            assert "申请已提交" in resp.json()["message"]


# ============================================================================
# 6. update_fund — PUT /api/v1/funds/{fund_id}
# ============================================================================


class TestUpdateFund:
    def test_update_fund_success(self, client, mock_db):
        """Admin updates a pending fund."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.put("/api/v1/funds/1", json={"name": "更新后的名称", "amount": 8000})
        assert resp.status_code == 200
        assert resp.json()["message"] == "更新成功"

    def test_update_fund_not_found(self, client, mock_db):
        """Update non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.put("/api/v1/funds/999", json={"name": "不存在"})
        assert resp.status_code == 404

    def test_update_fund_regular_user_allowed(self, client_regular, mock_db):
        """普通用户（user）可更新经费（pending 状态）。"""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client_regular.put("/api/v1/funds/1", json={"name": "尝试修改"})
        assert resp.status_code == 200

    def test_update_fund_immutable_status_rejected(self, client, mock_db):
        """Fund in approved+ status cannot be modified."""
        for blocked in ["approved", "allocated", "in_use", "completed", "audited"]:
            fund = FundMock(1, status=blocked)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.put("/api/v1/funds/1", json={"name": "try"})
            assert resp.status_code == 400, f"Status {blocked} should be blocked"
            assert "不允许修改" in resp.json()["detail"]

    def test_update_fund_mutable_status_allowed(self, client, mock_db):
        """Fund in pending/planned/rejected can be updated."""
        for allowed in ["pending", "planned", "rejected"]:
            fund = FundMock(1, status=allowed)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.put("/api/v1/funds/1", json={"remarks": "update"})
            assert resp.status_code == 200, f"Status {allowed} should be allowed"

    def test_update_fund_null_fields(self, client, mock_db):
        """Explicit null clears optional fields."""
        fund = FundMock(1, status="pending", remarks="old", school_id=5)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.put("/api/v1/funds/1", json={"remarks": None, "school_id": None})
        assert resp.status_code == 200

    def test_update_fund_extra_field_rejected(self, client, mock_db):
        """FundUpdate has extra='forbid' so unknown fields are rejected."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.put("/api/v1/funds/1", json={"name": "ok", "nonexistent_field": "bad"})
        assert resp.status_code == 422


# ============================================================================
# 7. delete_fund — DELETE /api/v1/funds/{fund_id}
# ============================================================================


class TestDeleteFund:
    def test_delete_fund_success(self, client, mock_db):
        """Admin deletes a pending fund."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.delete("/api/v1/funds/1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"

    def test_delete_fund_not_found(self, client, mock_db):
        """Delete non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.delete("/api/v1/funds/999")
        assert resp.status_code == 404

    def test_delete_fund_regular_user_allowed(self, client_regular, mock_db):
        """普通用户（user）可删除 pending 状态的经费。"""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client_regular.delete("/api/v1/funds/1")
        assert resp.status_code == 200

    def test_delete_fund_non_pending_rejected(self, client, mock_db):
        """Only pending funds can be deleted."""
        for non_pending in ["approved", "allocated", "in_use", "completed", "audited", "planned"]:
            fund = FundMock(1, status=non_pending)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.delete("/api/v1/funds/1")
            assert resp.status_code == 400, f"Status {non_pending} should block delete"
            assert "仅允许删除" in resp.json()["detail"]


# ============================================================================
# 8. Statistics endpoints
# ============================================================================


class TestFundStatisticsOverview:
    def test_statistics_overview(self, client, mock_db):
        """Overview returns aggregate counts."""
        row = SimpleObj(total_count=150, total_amount=Decimal("500000.00"),
                        pending_count=23, approved_count=100,
                        allocated_count=10, in_use_count=5, completed_count=2,
                        used_amount=Decimal("80000.00"), allocated_amount=Decimal("300000.00"))
        r = MagicMock()
        r.one.return_value = row
        mock_db.execute.return_value = r
        # 预算聚合（fund_budgets）mock：first() 返回 None（无预算记录）
        mock_db.query.return_value.first.return_value = None

        resp = client.get("/api/v1/funds/statistics/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_count"] == 150
        assert data["total_amount"] == 500000.0
        assert data["pending_count"] == 23
        assert data["approved_count"] == 100
        assert data["allocated_count"] == 10
        assert data["in_use_count"] == 5
        assert data["completed_count"] == 2
        assert data["used_amount"] == 80000.0
        assert data["allocated_amount"] == 300000.0
        assert data["budget_total"] == 0
        assert data["budget_executed"] == 0

    def test_statistics_overview_zero_data(self, client, mock_db):
        """Overview with zero data."""
        row = SimpleObj(total_count=0, total_amount=Decimal("0.00"),
                        pending_count=0, approved_count=0,
                        allocated_count=0, in_use_count=0, completed_count=0,
                        used_amount=Decimal("0.00"), allocated_amount=Decimal("0.00"))
        r = MagicMock()
        r.one.return_value = row
        mock_db.execute.return_value = r
        mock_db.query.return_value.first.return_value = None

        resp = client.get("/api/v1/funds/statistics/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_count"] == 0
        assert data["total_amount"] == 0.0


class TestFundStatisticsMultiDimension:
    def test_by_type(self, client, mock_db):
        """Group by type."""
        r1 = SimpleObj(group_key="project", count=10,
                       total_amount=Decimal("100000"),
                       total_allocated=Decimal("80000"),
                       total_used=Decimal("50000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=type")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"][0]["label"] == "项目经费"

    def test_by_source(self, client, mock_db):
        """Group by source."""
        r1 = SimpleObj(group_key="military", count=5,
                       total_amount=Decimal("200000"),
                       total_allocated=Decimal("150000"),
                       total_used=Decimal("100000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=source")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["label"] == "专项投资"

    def test_by_status(self, client, mock_db):
        """Group by status."""
        r1 = SimpleObj(group_key="pending", count=3,
                       total_amount=Decimal("30000"),
                       total_allocated=Decimal("0"),
                       total_used=Decimal("0"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=status")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["label"] == "待审批"

    def test_by_period_monthly(self, client, mock_db):
        """Group by period (monthly)."""
        r1 = SimpleObj(group_key="2025-06", count=4,
                       total_amount=Decimal("40000"),
                       total_allocated=Decimal("30000"),
                       total_used=Decimal("20000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=period")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["label"] == "2025-06"

    def test_by_period_quarterly(self, client, mock_db):
        """Group by period (quarterly)."""
        r1 = SimpleObj(group_key="2025-Q2", count=12,
                       total_amount=Decimal("120000"),
                       total_allocated=Decimal("90000"),
                       total_used=Decimal("60000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get(
            "/api/v1/funds/statistics/multi-dimension?group_by=period&period_type=quarterly"
        )
        assert resp.status_code == 200
        assert resp.json()["data"][0]["label"] == "2025-Q2"

    def test_by_period_yearly(self, client, mock_db):
        """Group by period (yearly)."""
        r1 = SimpleObj(group_key=2025, count=50,
                       total_amount=Decimal("500000"),
                       total_allocated=Decimal("400000"),
                       total_used=Decimal("350000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get(
            "/api/v1/funds/statistics/multi-dimension?group_by=period&period_type=yearly"
        )
        assert resp.status_code == 200
        assert resp.json()["data"][0]["label"] == "2025"

    def test_date_filter_valid(self, client, mock_db):
        """Valid date filter."""
        r1 = SimpleObj(group_key="project", count=1,
                       total_amount=Decimal("1000"),
                       total_allocated=Decimal("500"),
                       total_used=Decimal("200"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get(
            "/api/v1/funds/statistics/multi-dimension?group_by=type"
            "&start_date=2025-01-01&end_date=2025-12-31"
        )
        assert resp.status_code == 200

    def test_date_filter_invalid_format(self, client, mock_db):
        """Invalid date format returns 400."""
        resp = client.get(
            "/api/v1/funds/statistics/multi-dimension?group_by=type&start_date=not-a-date"
        )
        assert resp.status_code == 400
        assert "日期格式错误" in resp.json()["detail"]

    def test_invalid_group_by(self, client, mock_db):
        """Invalid group_by returns 400."""
        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=invalid")
        assert resp.status_code == 400
        assert "不支持的分组维度" in resp.json()["detail"]

    def test_utilization_rate_calculation(self, client, mock_db):
        """Utilization rate = used / amount * 100."""
        r1 = SimpleObj(group_key="project", count=1,
                       total_amount=Decimal("100000"),
                       total_allocated=Decimal("80000"),
                       total_used=Decimal("60000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=type")
        assert resp.status_code == 200
        item = resp.json()["data"][0]
        assert item["utilization_rate"] == 60.0

    def test_zero_amount_utilization_rate(self, client, mock_db):
        """Utilization rate 0 when amount is 0."""
        r1 = SimpleObj(group_key="project", count=0,
                       total_amount=Decimal("0"),
                       total_allocated=Decimal("0"),
                       total_used=Decimal("0"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=type")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["utilization_rate"] == 0

    def test_unknown_key_label(self, client, mock_db):
        """Group key not in label map falls back to raw key."""
        r1 = SimpleObj(group_key="unmapped_key", count=1,
                       total_amount=Decimal("100"),
                       total_allocated=Decimal("50"),
                       total_used=Decimal("20"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/statistics/multi-dimension?group_by=source")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["label"] == "unmapped_key"


class TestFundStatsByType:
    def test_stats_by_type(self, client, mock_db):
        """Supported village statistics by type."""
        r1 = SimpleObj(fund_type="project", count=10, amount=Decimal("100000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/supported-village/statistics/by-type")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["project"]["count"] == 10
        assert data["data"]["project"]["fund_type_label"] == "项目经费"

    def test_stats_by_type_with_year_range(self, client, mock_db):
        """Filter by year range."""
        mock_db.execute.return_value = _exec_with_all([])

        resp = client.get(
            "/api/v1/funds/supported-village/statistics/by-type"
            "?year_start=2020&year_end=2025"
        )
        assert resp.status_code == 200

    def test_stats_by_type_null_fund_type(self, client, mock_db):
        """Null fund_type maps to 'other' key."""
        r1 = SimpleObj(fund_type=None, count=2, amount=Decimal("2000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/supported-village/statistics/by-type")
        assert resp.status_code == 200
        assert "other" in resp.json()["data"]

    def test_stats_by_type_with_department(self, client, mock_db):
        """Department parameter is accepted."""
        mock_db.execute.return_value = _exec_with_all([])

        resp = client.get(
            "/api/v1/funds/supported-village/statistics/by-type?department=military"
        )
        assert resp.status_code == 200


class TestFundStatsYearly:
    def test_yearly_comparison(self, client, mock_db):
        """Yearly comparison with items."""
        r1 = SimpleObj(year=2025, count=20,
                       amount=Decimal("200000"), allocated=Decimal("150000"))
        mock_db.execute.return_value = _exec_with_all([r1])

        resp = client.get("/api/v1/funds/supported-village/statistics/yearly-comparison")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"][0]["year"] == 2025
        assert data["data"][0]["total_actual"] == 200000.0
        assert data["data"][0]["total_planned"] == 150000.0

    def test_yearly_comparison_with_filter(self, client, mock_db):
        """Yearly comparison with year range filter."""
        mock_db.execute.return_value = _exec_with_all([])

        resp = client.get(
            "/api/v1/funds/supported-village/statistics/yearly-comparison"
            "?year_start=2024&year_end=2026"
        )
        assert resp.status_code == 200


class TestFundStatsUtilization:
    def test_utilization_rate(self, client, mock_db):
        """Overall utilization rate."""
        row = SimpleObj(planned=Decimal("200000"), actual=Decimal("150000"))
        r = MagicMock()
        r.one.return_value = row
        mock_db.execute.return_value = r

        resp = client.get("/api/v1/funds/supported-village/statistics/utilization-rate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["overall_utilization_rate"] == 75.0
        assert data["data"]["total_actual_investment"] == 150000.0
        assert data["data"]["total_planned_investment"] == 200000.0

    def test_utilization_rate_zero_planned(self, client, mock_db):
        """Rate is 0 when planned is 0."""
        row = SimpleObj(planned=Decimal("0"), actual=Decimal("50000"))
        r = MagicMock()
        r.one.return_value = row
        mock_db.execute.return_value = r

        resp = client.get("/api/v1/funds/supported-village/statistics/utilization-rate")
        assert resp.status_code == 200
        assert resp.json()["data"]["overall_utilization_rate"] == 0


class TestFundStatsSummary:
    def test_summary(self, client, mock_db):
        """Fund statistics summary."""
        row = SimpleObj(total_count=100, total_amount=Decimal("1000000"),
                        total_allocated=Decimal("800000"),
                        total_used=Decimal("600000"))
        r = MagicMock()
        r.one.return_value = row
        mock_db.execute.return_value = r

        resp = client.get("/api/v1/funds/supported-village/statistics/summary")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_count"] == 100
        assert data["total_amount"] == 1000000.0

    def test_summary_with_year_range(self, client, mock_db):
        """Summary with year range."""
        row = SimpleObj(total_count=10, total_amount=Decimal("50000"),
                        total_allocated=Decimal("30000"),
                        total_used=Decimal("20000"))
        r = MagicMock()
        r.one.return_value = row
        mock_db.execute.return_value = r

        resp = client.get(
            "/api/v1/funds/supported-village/statistics/summary"
            "?year_start=2025&year_end=2025"
        )
        assert resp.status_code == 200


# ============================================================================
# 9. Workflow / state transition endpoints
# ============================================================================


def _setup_attachment_query(mock_db, attachments):
    """Configure mock_db.query(FundAttachment).filter(…).all() to return attachments."""
    inner = MagicMock()
    inner.all.return_value = attachments
    middle = MagicMock()
    middle.filter.return_value = inner  # db.query(FundAttachment).filter(…) → inner
    mock_db.query.return_value = middle


class TestApproveFund:
    def test_approve_fund_success(self, client, mock_db):
        """Approve pending fund with attachment."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="contract")
        ])

        resp = client.post("/api/v1/funds/1/approve")
        assert resp.status_code == 200
        assert resp.json()["message"] == "审批通过"

    def test_approve_fund_not_found(self, client, mock_db):
        """Approve non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.post("/api/v1/funds/999/approve")
        assert resp.status_code == 404

    def test_approve_fund_regular_user_allowed(self, client_regular, mock_db):
        """普通用户（user）可执行经费审批。"""
        fund = FundMock(1, status="pending")
        fund.attachments = []
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client_regular.post("/api/v1/funds/1/approve")
        assert resp.status_code == 200

    def test_approve_fund_illegal_transition(self, client, mock_db):
        """Cannot approve a fund in non-pending/planned states."""
        for bad in ["approved", "allocated", "in_use", "completed", "audited"]:
            fund = FundMock(1, status=bad)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.post("/api/v1/funds/1/approve")
            assert resp.status_code == 400, f"Status {bad} should block approve"
            assert "非法" in resp.json()["detail"]

    def test_approve_fund_no_attachment(self, client, mock_db):
        """Approve requires at least one attachment."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [])

        resp = client.post("/api/v1/funds/1/approve")
        assert resp.status_code == 400
        assert "附件" in resp.json()["detail"]

    def test_approve_planned_fund(self, client, mock_db):
        """Planned fund can also be approved."""
        fund = FundMock(1, status="planned")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="report")
        ])

        resp = client.post("/api/v1/funds/1/approve")
        assert resp.status_code == 200


class TestRejectFund:
    def test_reject_fund_success(self, client, mock_db):
        """Reject a pending fund（009 起驳回理由必填）."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/reject", json={"opinion": "材料不齐"})
        assert resp.status_code == 200
        assert resp.json()["message"] == "审批驳回"

    def test_reject_fund_requires_opinion(self, client, mock_db):
        """缺少驳回意见 → 400（009 驳回理由必填）。"""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/reject")
        assert resp.status_code == 400
        assert "原因" in resp.json()["detail"] or "意见" in resp.json()["detail"]

    def test_reject_fund_illegal_transition(self, client, mock_db):
        """Cannot reject non-pending/planned funds."""
        for bad in ["approved", "allocated", "in_use", "completed", "audited"]:
            fund = FundMock(1, status=bad)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.post("/api/v1/funds/1/reject")
            assert resp.status_code == 400, f"Status {bad} should block reject"


class TestAllocateFund:
    def test_allocate_fund_success(self, client, mock_db):
        """Allocate approved fund with required attachments."""
        fund = FundMock(1, status="approved")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="contract"),
            SimpleObj(id=2, fund_id=1, category="allocation_order"),
        ])

        resp = client.post("/api/v1/funds/1/allocate")
        assert resp.status_code == 200
        assert resp.json()["message"] == "经费已拨付"

    def test_allocate_fund_missing_allocation_order(self, client, mock_db):
        """Allocate requires both contract AND allocation_order."""
        fund = FundMock(1, status="approved")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="contract"),
        ])

        resp = client.post("/api/v1/funds/1/allocate")
        assert resp.status_code == 400
        assert "分配令" in resp.json()["detail"]

    def test_allocate_fund_illegal_transition(self, client, mock_db):
        """Cannot allocate non-approved funds."""
        for bad in ["pending", "planned", "in_use", "completed", "audited"]:
            fund = FundMock(1, status=bad)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.post("/api/v1/funds/1/allocate")
            assert resp.status_code == 400, f"Status {bad} should block allocate"

    def test_allocate_fund_with_milestone_completed(self, client, mock_db):
        """Allocate with milestone that is completed."""
        fund = FundMock(1, status="approved", project_id=10)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        milestone = SimpleObj(id=5, project_id=10, status="completed")

        # Build: milestone query result (returns milestone) + attachment query result (returns required attachments)
        ms_q = MagicMock()
        ms_q.filter.return_value.first.return_value = milestone

        att_q = MagicMock()
        att_q.filter.return_value.all.return_value = [
            SimpleObj(id=1, fund_id=1, category="contract"),
            SimpleObj(id=2, fund_id=1, category="allocation_order"),
        ]

        mock_db.query.side_effect = [ms_q, att_q]

        resp = client.post("/api/v1/funds/1/allocate?milestone_id=5")
        assert resp.status_code == 200

    def test_allocate_fund_no_project_for_milestone(self, client, mock_db):
        """Allocate with milestone but no project_id returns 400."""
        fund = FundMock(1, status="approved", project_id=None)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/allocate?milestone_id=5")
        assert resp.status_code == 400
        assert "未关联项目" in resp.json()["detail"]

    def test_allocate_fund_milestone_not_found(self, client, mock_db):
        """Milestone not found returns 404."""
        fund = FundMock(1, status="approved", project_id=10)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q

        resp = client.post("/api/v1/funds/1/allocate?milestone_id=99")
        assert resp.status_code == 404
        assert "里程碑" in resp.json()["detail"]

    def test_allocate_fund_milestone_not_completed(self, client, mock_db):
        """Milestone exists but not completed returns 400."""
        fund = FundMock(1, status="approved", project_id=10)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        milestone = SimpleObj(id=5, project_id=10, status="in_progress")
        q = MagicMock()
        q.filter.return_value.first.return_value = milestone
        mock_db.query.return_value = q

        resp = client.post("/api/v1/funds/1/allocate?milestone_id=5")
        assert resp.status_code == 400
        assert "未完成" in resp.json()["detail"]


class TestStartUseFund:
    def test_start_use_success(self, client, mock_db):
        """Start using an allocated fund."""
        fund = FundMock(1, status="allocated")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/start-use")
        assert resp.status_code == 200
        assert resp.json()["message"] == "经费已开始使用"

    def test_start_use_illegal_transition(self, client, mock_db):
        """Cannot start-use non-allocated funds."""
        for bad in ["pending", "planned", "approved", "in_use", "completed", "audited"]:
            fund = FundMock(1, status=bad)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.post("/api/v1/funds/1/start-use")
            assert resp.status_code == 400, f"Status {bad} should block start-use"


class TestCompleteFund:
    def test_complete_success(self, client, mock_db):
        """Complete an in-use fund."""
        fund = FundMock(1, status="in_use")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/complete")
        assert resp.status_code == 200
        assert resp.json()["message"] == "经费使用完成"

    def test_complete_illegal_transition(self, client, mock_db):
        """Cannot complete non-in-use funds."""
        for bad in ["pending", "planned", "approved", "allocated", "completed", "audited"]:
            fund = FundMock(1, status=bad)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.post("/api/v1/funds/1/complete")
            assert resp.status_code == 400, f"Status {bad} should block complete"


class TestAuditFund:
    def test_audit_success(self, client, mock_db):
        """Audit a completed fund."""
        fund = FundMock(1, status="completed")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/audit")
        assert resp.status_code == 200
        assert resp.json()["message"] == "经费审计完成"

    def test_audit_illegal_transition(self, client, mock_db):
        """Cannot audit non-completed funds."""
        for bad in ["pending", "planned", "approved", "allocated", "in_use", "audited"]:
            fund = FundMock(1, status=bad)
            mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

            resp = client.post("/api/v1/funds/1/audit")
            assert resp.status_code == 400, f"Status {bad} should block audit"


# ============================================================================
# 10. History endpoints
# ============================================================================


class TestFundHistoryStatus:
    def test_status_history_with_items(self, client, mock_db):
        """Get fund status change history."""
        fund = FundMock(1)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        hist1 = SimpleObj(
            id=1, fund_id=1, from_status="pending", to_status="approved",
            operator_id=1, operator_name="管理员",
            operation_time=datetime(2025, 6, 16, tzinfo=timezone.utc),
            remark="审批通过",
        )
        hist2 = SimpleObj(
            id=2, fund_id=1, from_status="approved", to_status="allocated",
            operator_id=1, operator_name="管理员",
            operation_time=datetime(2025, 6, 17, tzinfo=timezone.utc),
            remark="已拨付",
        )

        chain = MagicMock()
        chain.all.return_value = [hist1, hist2]
        inner = MagicMock()
        inner.limit.return_value = chain
        inner2 = MagicMock()
        inner2.order_by.return_value = inner
        inner3 = MagicMock()
        inner3.filter.return_value = inner2
        mock_db.query.return_value = inner3

        resp = client.get("/api/v1/funds/1/history/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["to_status"] == "approved"

    def test_status_history_not_found(self, client, mock_db):
        """Status history for non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.get("/api/v1/funds/999/history/status")
        assert resp.status_code == 404

    def test_status_history_empty(self, client, mock_db):
        """Empty status history returns empty list."""
        fund = FundMock(1)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        chain = MagicMock()
        chain.all.return_value = []
        inner = MagicMock()
        inner.limit.return_value = chain
        inner2 = MagicMock()
        inner2.order_by.return_value = inner
        inner3 = MagicMock()
        inner3.filter.return_value = inner2
        mock_db.query.return_value = inner3

        resp = client.get("/api/v1/funds/1/history/status")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestFundHistoryFields:
    def test_field_changes(self, client, mock_db):
        """Get fund field change history."""
        fund = FundMock(1)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        change = SimpleObj(id=1, fund_id=1, field_name="amount",
                           old_value="300.00", new_value="500.00",
                           changed_by=1, changed_by_name="管理员",
                           changed_at=datetime(2025, 6, 16, tzinfo=timezone.utc))

        chain = MagicMock()
        chain.all.return_value = [change]
        inner = MagicMock()
        inner.limit.return_value = chain
        inner2 = MagicMock()
        inner2.order_by.return_value = inner
        inner3 = MagicMock()
        inner3.filter.return_value = inner2
        mock_db.query.return_value = inner3

        resp = client.get("/api/v1/funds/1/history/fields")
        assert resp.status_code == 200
        data = resp.json()["data"]["items"]
        assert len(data) == 1
        assert data[0]["field_name"] == "amount"

    def test_field_changes_not_found(self, client, mock_db):
        """Field changes for non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.get("/api/v1/funds/999/history/fields")
        assert resp.status_code == 404


class TestFundHistoryOperations:
    def test_operation_logs(self, client, mock_db):
        """Get fund operation logs."""
        fund = FundMock(1)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        log = SimpleObj(id=1, fund_id=1, operation_type="approve",
                        operator_name="管理员",
                        operation_detail="通过审批",
                        created_at=datetime(2025, 6, 16, tzinfo=timezone.utc))

        chain = MagicMock()
        chain.all.return_value = [log]
        inner = MagicMock()
        inner.limit.return_value = chain
        inner2 = MagicMock()
        inner2.order_by.return_value = inner
        inner3 = MagicMock()
        inner3.filter.return_value = inner2
        mock_db.query.return_value = inner3

        resp = client.get("/api/v1/funds/1/history/operations")
        assert resp.status_code == 200
        data = resp.json()["data"]["items"]
        assert len(data) == 1
        assert data[0]["operation_type"] == "approve"

    def test_operation_logs_not_found(self, client, mock_db):
        """Operation logs for non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.get("/api/v1/funds/999/history/operations")
        assert resp.status_code == 404


# ============================================================================
# 11. Attachment endpoints
# ============================================================================


class TestListFundAttachments:
    def test_list_attachments(self, client, mock_db):
        """List attachments for a fund."""
        fund = FundMock(1)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        att1 = SimpleObj(
            id=1, fund_id=1, file_name="test.pdf", file_path="/tmp/test.pdf",
            file_size=1024, file_type="application/pdf", category="contract",
            description="测试附件", uploaded_by="管理员",
            created_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        att1.to_dict = lambda: {
            "id": 1, "fund_id": 1, "file_name": "test.pdf",
            "file_path": "/tmp/test.pdf", "file_size": 1024,
            "file_type": "application/pdf", "category": "contract",
            "description": "测试附件", "uploaded_by": "管理员",
            "created_at": "2025-06-15T00:00:00+00:00",
        }

        att2 = SimpleObj(
            id=2, fund_id=1, file_name="report.pdf", file_path="/tmp/report.pdf",
            file_size=2048, file_type="application/pdf", category="report",
            description="报告", uploaded_by="管理员",
            created_at=datetime(2025, 6, 16, tzinfo=timezone.utc),
        )
        att2.to_dict = lambda: {
            "id": 2, "fund_id": 1, "file_name": "report.pdf",
            "file_path": "/tmp/report.pdf", "file_size": 2048,
            "file_type": "application/pdf", "category": "report",
            "description": "报告", "uploaded_by": "管理员",
            "created_at": "2025-06-16T00:00:00+00:00",
        }

        chain = MagicMock()
        chain.all.return_value = [att1, att2]
        inner = MagicMock()
        inner.order_by.return_value = chain
        inner2 = MagicMock()
        inner2.filter.return_value = inner
        mock_db.query.return_value = inner2

        resp = client.get("/api/v1/funds/1/attachments")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_attachments_empty(self, client, mock_db):
        """Empty attachment list."""
        fund = FundMock(1)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        chain = MagicMock()
        chain.all.return_value = []
        inner = MagicMock()
        inner.order_by.return_value = chain
        inner2 = MagicMock()
        inner2.filter.return_value = inner
        mock_db.query.return_value = inner2

        resp = client.get("/api/v1/funds/1/attachments")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_list_attachments_fund_not_found(self, client, mock_db):
        """Attachments for non-existent fund returns 404."""
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(None)

        resp = client.get("/api/v1/funds/999/attachments")
        assert resp.status_code == 404


class TestDeleteFundAttachment:
    def test_delete_attachment_success(self, client, mock_db):
        """Delete an attachment successfully."""
        att = SimpleObj(id=1, fund_id=1, file_path="/tmp/test.pdf")

        q = MagicMock()
        q.filter.return_value.first.return_value = att
        mock_db.query.return_value = q

        with patch("os.path.exists", return_value=True), patch("os.remove"):
            resp = client.delete("/api/v1/funds/attachments/1")
            assert resp.status_code == 200
            assert resp.json()["message"] == "删除成功"

    def test_delete_attachment_not_found(self, client, mock_db):
        """Delete non-existent attachment returns 404."""
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q

        resp = client.delete("/api/v1/funds/attachments/999")
        assert resp.status_code == 404

    def test_delete_attachment_file_remove_error(self, client, mock_db):
        """Delete succeeds even if file removal fails (graceful)."""
        att = SimpleObj(id=1, fund_id=1, file_path="/nonexistent/file.pdf")

        q = MagicMock()
        q.filter.return_value.first.return_value = att
        mock_db.query.return_value = q

        with patch("os.path.exists", return_value=True), \
             patch("os.remove", side_effect=OSError("Permission denied")):
            resp = client.delete("/api/v1/funds/attachments/1")
            assert resp.status_code == 200


class TestDownloadFundAttachment:
    def test_download_not_found_db(self, client, mock_db):
        """Download non-existent attachment returns 404."""
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q

        resp = client.get("/api/v1/funds/attachments/999/download")
        assert resp.status_code == 404

    def test_download_file_missing_on_disk(self, client, mock_db):
        """Download when file is missing on disk returns 404."""
        att = SimpleObj(id=1, fund_id=1, file_path="/tmp/missing.pdf", file_name="missing.pdf",
                        file_type="application/pdf")
        q = MagicMock()
        q.filter.return_value.first.return_value = att
        mock_db.query.return_value = q

        with patch("os.path.exists", return_value=False):
            resp = client.get("/api/v1/funds/attachments/1/download")
            assert resp.status_code == 404
            assert "文件不存在" in resp.json()["detail"]


class TestPreviewFundAttachment:
    def test_preview_not_found_db(self, client, mock_db):
        """Preview non-existent attachment returns 404."""
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q

        resp = client.get("/api/v1/funds/attachments/999/preview")
        assert resp.status_code == 404

    def test_preview_file_missing_on_disk(self, client, mock_db):
        """Preview when file is missing on disk returns 404."""
        att = SimpleObj(id=1, fund_id=1, file_path="/tmp/missing.pdf", file_name="missing.pdf",
                        file_type="application/pdf")
        q = MagicMock()
        q.filter.return_value.first.return_value = att
        mock_db.query.return_value = q

        with patch("os.path.exists", return_value=False):
            resp = client.get("/api/v1/funds/attachments/1/preview")
            assert resp.status_code == 404
            assert "文件不存在" in resp.json()["detail"]


# ============================================================================
# 12. Edge cases
# ============================================================================


class TestSafeVal:
    """Test _safe_val through the get_fund endpoint (which returns fund dicts)."""

    def test_decimal_is_converted_to_float(self, client, mock_db):
        """Decimal values become floats in JSON."""
        fund = FundMock(1, amount=Decimal("1234.56"))
        fund.project = None
        fund.village = None
        fund.organization = None
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.get("/api/v1/funds/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["amount"] == 1234.56

    def test_datetime_is_serialized(self, client, mock_db):
        """Datetime values become ISO strings."""
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        fund = FundMock(1, application_date=dt,
                        approval_date=dt, allocation_date=dt)
        fund.project = None
        fund.village = None
        fund.organization = None
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.get("/api/v1/funds/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "application_date" in data
        assert data["application_date"] is not None

    def test_none_is_serialized(self, client, mock_db):
        """None values are preserved."""
        fund = FundMock(1, approved_by=None)
        fund.project = None
        fund.village = None
        fund.organization = None
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.get("/api/v1/funds/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["approved_by"] is None

    def test_date_type_is_isoformat(self, client, mock_db):
        """date objects (not datetime) are also ISO-formatted via hasattr(isoformat)."""
        fund = FundMock(1, date=date(2025, 8, 20))
        fund.project = None
        fund.village = None
        fund.organization = None
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.get("/api/v1/funds/1")
        assert resp.status_code == 200
        assert "2025-08-20" in resp.json()["data"]["date"]

    def test_fund_with_associations(self, client, mock_db):
        """Associated project and village names appear in the result."""
        fund = FundMock(1)
        fund.project = SimpleObj(name="项目X")
        fund.village = SimpleObj(village_name="村庄Y")
        fund.organization = SimpleObj(name="组织Z")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.get("/api/v1/funds/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["project_name"] == "项目X"
        assert data["village_name"] == "村庄Y"


class TestPaginationValidation:
    def test_page_size_minimum(self, client, mock_db):
        """page_size=1 is valid."""
        count_r = MagicMock()
        count_r.scalar_one.return_value = 0
        items_r = _exec_with_scalars_unique_all([])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?page_size=1")
        assert resp.status_code == 200

    def test_page_size_maximum(self, client, mock_db):
        """page_size=200 is valid."""
        count_r = MagicMock()
        count_r.scalar_one.return_value = 0
        items_r = _exec_with_scalars_unique_all([])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?page_size=200")
        assert resp.status_code == 200

    def test_page_zero_rejected(self, client, mock_db):
        """page=0 is rejected (minimum is 1)."""
        resp = client.get("/api/v1/funds?page=0")
        assert resp.status_code == 422

    def test_page_size_zero_rejected(self, client, mock_db):
        """page_size=0 is rejected."""
        resp = client.get("/api/v1/funds?page_size=0")
        assert resp.status_code == 422

    def test_page_size_over_max_rejected(self, client, mock_db):
        """page_size=201 is rejected (>200 max)."""
        resp = client.get("/api/v1/funds?page_size=201")
        assert resp.status_code == 422


class TestKeysetPagination:
    def test_keyset_without_cursor(self, client, mock_db):
        """Keyset pagination first page."""
        fund = FundMock(1)
        fund.project = None
        fund.village = None
        keyset = {"items": [fund], "total": 1, "page_size": 20,
                  "next_cursor": None, "has_more": False}
        with patch("app.api.v1.funds.keyset_paginate", return_value=keyset):
            resp = client.get("/api/v1/funds?pagination=keyset")
            assert resp.status_code == 200
            assert resp.json()["next_cursor"] is None

    def test_keyset_with_cursor(self, client, mock_db):
        """Keyset pagination with cursor."""
        fund = FundMock(50)
        fund.project = None
        fund.village = None
        keyset = {"items": [fund], "total": 100, "page_size": 20,
                  "next_cursor": "next_cursor_val", "has_more": True}
        with patch("app.api.v1.funds.keyset_paginate", return_value=keyset):
            resp = client.get("/api/v1/funds?pagination=keyset&cursor=abc123")
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_more"] is True
            assert data["next_cursor"] == "next_cursor_val"

    def test_offset_page_3(self, client, mock_db):
        """Offset pagination on page 3."""
        fund = FundMock(41)
        fund.project = None
        fund.village = None
        count_r = MagicMock()
        count_r.scalar_one.return_value = 45
        items_r = _exec_with_scalars_unique_all([fund])
        mock_db.execute.side_effect = [count_r, items_r]

        resp = client.get("/api/v1/funds?page=3&page_size=20")
        assert resp.status_code == 200
        assert resp.json()["data"]["page"] == 3


# ============================================================================
# 13. Manager role
# ============================================================================


class TestManagerRole:
    def test_manager_can_create_fund(self, client_manager, mock_db):
        """Manager (role='manager') can create funds."""
        created = Mock()
        created.id = 300
        with patch("app.services.fund_service.FundService") as MockService:
            mock_svc = MockService.return_value
            mock_svc.create_fund_for_user.return_value = created

            resp = client_manager.post("/api/v1/funds",
                                       json={"name": "经理创建", "amount": 2000})
            assert resp.status_code == 201

    def test_manager_can_delete_fund(self, client_manager, mock_db):
        """Manager can delete pending funds."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client_manager.delete("/api/v1/funds/1")
        assert resp.status_code == 200

    def test_manager_can_approve_fund(self, client_manager, mock_db):
        """Manager can approve pending funds."""
        fund = FundMock(1, status="pending")
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="report")
        ])

        resp = client_manager.post("/api/v1/funds/1/approve")
        assert resp.status_code == 200


# ============================================================================
# 14. Transition status sets correct fields
# ============================================================================


class TestTransitionStatus:
    def test_approve_sets_fields(self, client, mock_db):
        """Approve sets approved_by and approval_date."""
        fund = FundMock(1, status="pending", approved_by=None, approval_date=None)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="report")
        ])

        resp = client.post("/api/v1/funds/1/approve")
        assert resp.status_code == 200
        assert fund.status == "approved"
        assert fund.approved_by == "管理员"
        assert fund.approval_date is not None

    def test_reject_sets_approved_by(self, client, mock_db):
        """Reject sets approved_by field."""
        fund = FundMock(1, status="pending", approved_by=None)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/reject", json={"opinion": "不予通过"})
        assert resp.status_code == 200
        assert fund.status == "rejected"
        assert fund.approved_by == "管理员"

    def test_allocate_sets_allocation_date(self, client, mock_db):
        """Allocate sets allocation_date."""
        fund = FundMock(1, status="approved", allocation_date=None)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)
        _setup_attachment_query(mock_db, [
            SimpleObj(id=1, fund_id=1, category="contract"),
            SimpleObj(id=2, fund_id=1, category="allocation_order"),
        ])

        resp = client.post("/api/v1/funds/1/allocate")
        assert resp.status_code == 200
        assert fund.status == "allocated"
        assert fund.allocation_date is not None

    def test_complete_sets_end_date(self, client, mock_db):
        """Complete sets end_date."""
        fund = FundMock(1, status="in_use", end_date=None)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/complete")
        assert resp.status_code == 200
        assert fund.status == "completed"
        assert fund.end_date is not None

    def test_audit_sets_audit_date(self, client, mock_db):
        """Audit sets audit_date."""
        fund = FundMock(1, status="completed", audit_date=None)
        mock_db.execute.return_value = _exec_with_scalar_one_or_none(fund)

        resp = client.post("/api/v1/funds/1/audit")
        assert resp.status_code == 200
        assert fund.status == "audited"
        assert fund.audit_date is not None
