"""定向覆盖率测试：organization 成员端点 + fund_health 同步评分 + effectiveness 指标计算。

覆盖 coverage.json 中三个文件缺失的分支：
- app/api/v1/organization.py: 881-927（添加/移除组织成员端点）
- app/services/fund_health_service.py: 同步评分辅助函数 + 批量健康度
- app/services/effectiveness_service.py: _compute_indicators + 排名更新循环

本文件自包含 mock，不依赖真实数据库；不改源码与既有测试。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.organization import Organization
from app.models.user import User

# ===========================================================================
#  organization.py — 成员管理端点（缺失行 881-927）
# ===========================================================================


@pytest.fixture
def member_db():
    """路由式 mock db：Organization / User 查询分开返回。"""
    db = MagicMock()
    org_q = MagicMock()
    org_q.filter.return_value = org_q
    org_q.first.return_value = None
    user_q = MagicMock()
    user_q.filter.return_value = user_q
    user_q.first.return_value = None

    def _query(model):
        if model is Organization:
            return org_q
        if model is User:
            return user_q
        return MagicMock()

    db.query.side_effect = _query
    db.org_q = org_q
    db.user_q = user_q
    return db


@pytest.fixture
def admin_user():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.is_active = True
    return u


@pytest.fixture
def regular_user():
    u = MagicMock()
    u.id = 2
    u.username = "operator"
    u.role = "operator"
    u.is_superuser = False
    u.is_active = True
    return u


@pytest.fixture
def client_admin(member_db, admin_user):
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: member_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


@pytest.fixture
def client_regular(member_db, regular_user):
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: member_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _org(id_=1):
    return SimpleNamespace(id=id_, name="测试组织")


def _user(id_, active=True):
    return SimpleNamespace(id=id_, is_active=active)


class TestAddOrganizationMembers:
    def test_add_members_success_mixed_ids(self, client_admin, member_db):
        member_db.org_q.first.return_value = _org(1)
        member_db.user_q.first.side_effect = [
            _user(1, True),
            _user(2, True),
            _user(3, False),
        ]
        resp = client_admin.post(
            "/api/v1/organizations/1/members",
            json={"user_ids": [1, "2", "abc", 3]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["added"] == 2
        member_db.commit.assert_called()

    def test_add_members_org_not_found(self, client_admin, member_db):
        member_db.org_q.first.return_value = None
        resp = client_admin.post(
            "/api/v1/organizations/999/members", json={"user_ids": [1]}
        )
        assert resp.status_code == 404
        assert "组织不存在" in resp.text

    def test_add_members_no_user_ids(self, client_admin, member_db):
        member_db.org_q.first.return_value = _org(1)
        resp = client_admin.post(
            "/api/v1/organizations/1/members", json={"user_ids": []}
        )
        assert resp.status_code == 400
        assert "请选择要添加的成员" in resp.text

    def test_add_members_permission_denied(self, client_regular):
        resp = client_regular.post(
            "/api/v1/organizations/1/members", json={"user_ids": [1]}
        )
        assert resp.status_code == 403


class TestRemoveOrganizationMember:
    def test_remove_member_success(self, client_admin, member_db):
        member_db.org_q.first.return_value = _org(1)
        member_db.user_q.first.return_value = _user(7, True)
        resp = client_admin.delete("/api/v1/organizations/1/members/7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["removed"] == 7
        assert member_db.user_q.first.return_value.organization_id is None
        member_db.commit.assert_called()

    def test_remove_member_org_not_found(self, client_admin, member_db):
        member_db.org_q.first.return_value = None
        resp = client_admin.delete("/api/v1/organizations/999/members/7")
        assert resp.status_code == 404
        assert "组织不存在" in resp.text

    def test_remove_member_user_not_found(self, client_admin, member_db):
        member_db.org_q.first.return_value = _org(1)
        member_db.user_q.first.return_value = None
        resp = client_admin.delete("/api/v1/organizations/1/members/999")
        assert resp.status_code == 404
        assert "用户不存在" in resp.text

    def test_remove_member_permission_denied(self, client_regular):
        resp = client_regular.delete("/api/v1/organizations/1/members/7")
        assert resp.status_code == 403


# ===========================================================================
#  fund_health_service.py — 同步评分函数（缺失行见 coverage.json）
# ===========================================================================

from app.services.fund_health_service import (  # noqa: E402
    _score_budget_usage,
    _score_phase_completion,
    _score_payment_timeliness,
    _score_voucher_completeness,
    _score_contract_fulfillment,
    calculate_projects_health_sync,
)


def _fund(approved=None, planned=None, amount=None, used=0):
    return SimpleNamespace(
        approved_amount=approved,
        planned_amount=planned,
        amount=amount,
        used_amount=used,
    )


class TestScoreBudgetUsage:
    def test_over_budget(self):
        assert _score_budget_usage(_fund(approved=100, used=120)) == 40.0

    def test_near_budget(self):
        assert _score_budget_usage(_fund(approved=100, used=95)) == 70.0

    def test_normal(self):
        assert _score_budget_usage(_fund(approved=100, used=50)) == 100.0

    def test_zero_budget_fallback(self):
        assert _score_budget_usage(_fund(approved=None, planned=None, amount=None, used=10)) == 100.0

    def test_non_numeric_budget_raises(self):
        assert _score_budget_usage(_fund(approved="abc", used=10)) == 100.0

    def test_planned_amount_budget(self):
        assert _score_budget_usage(_fund(approved=None, planned=200, used=100)) == 100.0


class TestScorePhaseCompletion:
    def test_with_phases(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.count.side_effect = [4, 2]
        db.query.return_value = q
        assert _score_phase_completion(db, 1) == 50.0


class TestScorePaymentTimeliness:
    def test_mixed_approval(self):
        f1 = SimpleNamespace(approval_date="2025-01-01", allocation_date="2025-02-01")
        f2 = SimpleNamespace(approval_date="2025-01-01", allocation_date=None)
        f3 = SimpleNamespace(approval_date=None, allocation_date=None)
        assert _score_payment_timeliness([f1, f2, f3]) == 50.0

    def test_funds_without_approval_date(self):
        f1 = SimpleNamespace(approval_date=None, allocation_date="2025-02-01")
        f2 = SimpleNamespace(approval_date=None, allocation_date=None)
        assert _score_payment_timeliness([f1, f2]) == 80.0


class TestScoreVoucherCompleteness:
    def test_mixed_voucher(self):
        f1 = SimpleNamespace(usage_description="用途说明", remaining_amount=None)
        f2 = SimpleNamespace(usage_description=None, remaining_amount=5.0)
        f3 = SimpleNamespace(usage_description="", remaining_amount=None)
        assert _score_voucher_completeness([f1, f2, f3]) == round(2 / 3 * 100, 1)


class TestScoreContractFulfillment:
    def test_query_raises_returns_neutral(self):
        db = MagicMock()
        db.query.side_effect = Exception("boom")
        assert _score_contract_fulfillment(db, 1) == 90.0

    def test_has_contracts(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.count.return_value = 3
        db.query.return_value = q
        assert _score_contract_fulfillment(db, 1) == 90.0


class TestCalculateProjectsHealthSync:
    def test_batch(self):
        db = MagicMock()
        with patch(
            "app.services.fund_health_service.calculate_project_health_sync",
            side_effect=lambda d, pid: {"project_id": pid},
        ) as m:
            result = calculate_projects_health_sync(db, [1, 2, 3])
        assert result == [{"project_id": 1}, {"project_id": 2}, {"project_id": 3}]
        assert m.call_count == 3


# ===========================================================================
#  effectiveness_service.py — _compute_indicators + 排名循环
# ===========================================================================

from app.services.effectiveness_service import EffectivenessService  # noqa: E402


class TestEffectivenessEvaluateVillage:
    def test_compute_indicators_and_rank_update(self):
        village = SimpleNamespace(id=1, village_name="测试村")
        income_obj = SimpleNamespace(per_capita_income_2025=10000)
        prev_obj = SimpleNamespace(per_capita_income_2024=8000)
        row1 = SimpleNamespace(rank=None)
        row2 = SimpleNamespace(rank=1)

        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.side_effect = [village, None, prev_obj]
        q.all.side_effect = [[income_obj], [row1, row2]]
        q.scalar.side_effect = [2, 3]
        db.query.return_value = q

        result = EffectivenessService.evaluate_village(db, 1, 2025, 99)

        assert result["village_name"] == "测试村"
        assert result["economic_score"] == 100.0
        assert result["social_score"] == 48.0
        assert result["ecological_score"] == 70.0
        assert result["indicators"]["per_capita_income"] == 10000.0
        assert result["indicators"]["income_growth_rate"] == 25.0
        assert result["indicators"]["infrastructure_count"] == 2
        assert result["indicators"]["industry_count"] == 3
        assert result["indicators"]["data_complete"] is True
        # 排名循环：row1.rank None→1，row2.rank 1→2
        assert row1.rank == 1
        assert row2.rank == 2
        db.commit.assert_called_once()
