"""Comprehensive tests for fund_lifecycle.py — all 44+ endpoints, full branch coverage."""

from datetime import date
from unittest.mock import Mock
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.fund_lifecycle import (
    BudgetBaseline,
    BudgetVersion,
    ContractStatus,
    FundAnomaly,
    FundContract,
    FundContractPayment,
    FundSettlement,
    FundTransferVoucher,
    PhaseStatus,
    SettlementStatus,
    VoucherStatus,
)
from app.models.fund import Fund
from app.models.fund_budget import FundTransaction
from app.models.fund_allocation_order import FundAllocationOrder, AllocationOrderItem
from app.models.approval import ApprovalWorkflow
from app.models.project import Project


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    from app.main import app

    def _get_db():
        yield db_session

    admin = Mock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.is_active = True
    admin.permissions_list = ["*"]
    admin.organization_id = 1
    admin.email = "admin@test.com"
    admin.full_name = "管理员"

    async def _get_current_user():
        return admin

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user

    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides = _original_overrides


@pytest.fixture
def project(db_session):
    p = Project(
        id=1,
        name="测试项目",
        type="infrastructure",
        description="测试描述",
        objectives="测试目标",
        budget=Decimal("1000.00"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        leader="张三",
        responsible_unit="某单位",
        status="in_progress",
        progress=50.0,
        organization_id=1,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def fund(db_session, project):
    f = Fund(
        id=1,
        project_id=project.id,
        name="测试经费",
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
        lifecycle_phase=1,
        budget_locked=False,
        deviation_rate=Decimal("0"),
        has_anomaly=False,
        budget_version=1,
        status="approved",
        operator="张三",
        organization_id=1,
    )
    db_session.add(f)
    db_session.flush()
    return f


def _init_phases(db, project_id):
    from app.models.fund_lifecycle import ProjectFundPhase
    phases = []
    for i in range(1, 8):
        p = ProjectFundPhase(project_id=project_id, phase=i, status=PhaseStatus.NOT_STARTED.value)
        db.add(p)
        phases.append(p)
    db.flush()
    return phases


@pytest.fixture
def phases(db_session, project):
    return _init_phases(db_session, project.id)


def _viewer_user():
    u = Mock()
    u.id = 3
    u.username = "viewer"
    u.role = "viewer"
    u.is_superuser = False
    u.is_active = True
    u.permissions_list = ["view"]
    u.organization_id = 1
    u.email = "viewer@test.com"
    u.full_name = "查看者"
    return u


# =====================================================================
#  Phase Management (3.1)
# =====================================================================


class TestGetPhases:
    def test_success(self, client, project, phases):
        resp = client.get(f"/api/v1/fund-lifecycle/phases/{project.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["project_id"] == project.id
        assert len(data["data"]["phases"]) == 7
        assert data["data"]["current_phase"] == 1

    def test_auto_init(self, client, project, db_session):
        resp = client.get(f"/api/v1/fund-lifecycle/phases/{project.id}")
        assert resp.status_code == 200
        assert len(resp.json()["data"]["phases"]) == 7

    def test_not_found(self, client):
        resp = client.get("/api/v1/fund-lifecycle/phases/999")
        assert resp.status_code == 404
        assert "项目不存在" in resp.text

    def test_current_in_progress(self, client, project, db_session):
        _init_phases(db_session, project.id)
        from app.models.fund_lifecycle import ProjectFundPhase
        p = db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id, ProjectFundPhase.phase == 2
        ).first()
        p.status = PhaseStatus.IN_PROGRESS.value
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/phases/{project.id}")
        assert resp.json()["data"]["current_phase"] == 2

    def test_current_via_completed(self, client, project, db_session):
        _init_phases(db_session, project.id)
        from app.models.fund_lifecycle import ProjectFundPhase
        p1 = db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id, ProjectFundPhase.phase == 1
        ).first()
        p1.status = PhaseStatus.COMPLETED.value
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/phases/{project.id}")
        assert resp.json()["data"]["current_phase"] == 2


class TestAdvancePhase:
    def test_no_data(self, client, project, phases):
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_from_not_started_with_remarks(self, client, project, phases):
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance", json={"remarks": "开始"})
        assert resp.status_code == 200

    def test_to_next_phase(self, client, project, phases, fund, db_session):
        from app.models.fund_lifecycle import ProjectFundPhase
        p1 = db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id, ProjectFundPhase.phase == 1
        ).first()
        p1.status = PhaseStatus.IN_PROGRESS.value
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance", json={"remarks": "完成"})
        assert resp.status_code == 200
        assert "已推进到阶段 2" in resp.text

    def test_advance_updates_fund_phase(self, client, project, phases, fund, db_session):
        from app.models.fund_lifecycle import ProjectFundPhase
        p1 = db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id, ProjectFundPhase.phase == 1
        ).first()
        p1.status = PhaseStatus.IN_PROGRESS.value
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance")
        assert resp.status_code == 200
        db_session.refresh(fund)
        assert fund.lifecycle_phase == 2

    def test_all_done(self, client, project, phases, db_session):
        from app.models.fund_lifecycle import ProjectFundPhase
        for p in db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id
        ).all():
            p.status = PhaseStatus.COMPLETED.value
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance")
        assert resp.status_code == 400
        assert "所有阶段已完成" in resp.text

    def test_blocked_by_danger(self, client, project, phases, fund, db_session):
        anomaly = FundAnomaly(
            project_id=project.id, fund_id=fund.id,
            anomaly_type="overspend", severity="danger",
            description="严重超支", resolved=False,
        )
        db_session.add(anomaly)
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance")
        assert resp.status_code == 400
        assert "严重异常" in resp.text

    def test_auto_init_phases(self, client, project, db_session):
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance")
        assert resp.status_code == 200

    def test_forbidden_viewer(self, client, project, phases, db_session):
        from app.main import app
        u = _viewer_user()
        async def _auth(): return u
        _original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_user] = _auth
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/advance")
        assert resp.status_code == 403
        app.dependency_overrides.pop(get_current_user, None)


class TestRollbackPhase:
    def test_success(self, client, project, phases, fund, db_session):
        from app.models.fund_lifecycle import ProjectFundPhase
        p2 = db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id, ProjectFundPhase.phase == 2
        ).first()
        p2.status = PhaseStatus.IN_PROGRESS.value
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/rollback")
        assert resp.status_code == 200
        assert "已退回到阶段 1" in resp.text
        db_session.refresh(fund)
        assert fund.lifecycle_phase == 1

    def test_no_phases(self, client, project):
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/rollback")
        assert resp.status_code == 400
        assert "阶段记录不存在" in resp.text

    def test_already_first(self, client, project, phases):
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/rollback")
        assert resp.status_code == 400
        assert "已在第一阶段" in resp.text

    def test_with_remarks(self, client, project, phases, db_session):
        from app.models.fund_lifecycle import ProjectFundPhase
        p2 = db_session.query(ProjectFundPhase).filter(
            ProjectFundPhase.project_id == project.id, ProjectFundPhase.phase == 2
        ).first()
        p2.status = PhaseStatus.IN_PROGRESS.value
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/phases/{project.id}/rollback", json={"remarks": "退回修正"})
        assert resp.status_code == 200


# =====================================================================
#  3.2 Initiate / Report Template
# =====================================================================


class TestInitiateProjectFund:
    def test_success(self, client, project):
        resp = client.post(f"/api/v1/fund-lifecycle/initiate/{project.id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "论证立项已启动"

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/initiate/999")
        assert resp.status_code == 404

    def test_auto_init_phases(self, client, project, db_session):
        resp = client.post(f"/api/v1/fund-lifecycle/initiate/{project.id}")
        assert resp.status_code == 200


class TestReportTemplate:
    def test_success(self, client, project, fund):
        resp = client.get(f"/api/v1/fund-lifecycle/report-template/{project.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["fund_summary"]["fund_count"] == 1

    def test_no_funds(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/report-template/{project.id}")
        assert resp.json()["data"]["fund_summary"]["fund_count"] == 0

    def test_not_found(self, client):
        resp = client.get("/api/v1/fund-lifecycle/report-template/999")
        assert resp.status_code == 404


# =====================================================================
#  3.3 Budget Lock / Compliance / Aggregation
# =====================================================================


class TestLockBudget:
    def test_success(self, client, project, fund, db_session):
        fund.approved_amount = Decimal("300.00")
        fund.type = "project"
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/budget-lock/{project.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["locked_count"] == 1
        baseline = db_session.query(BudgetBaseline).first()
        assert baseline is not None
        assert float(baseline.baseline_amount) == 300.0

    def test_no_funds(self, client, project):
        resp = client.post(f"/api/v1/fund-lifecycle/budget-lock/{project.id}")
        assert resp.status_code == 404

    def test_skip_locked(self, client, project, fund, db_session):
        fund.budget_locked = True
        fund.type = "project"
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/budget-lock/{project.id}")
        assert resp.json()["data"]["locked_count"] == 0

    def test_fallback_fields(self, client, project, fund, db_session):
        fund.approved_amount = None
        fund.planned_amount = Decimal("200.00")
        fund.fund_type = None
        fund.type = "education"
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/budget-lock/{project.id}")
        assert resp.status_code == 200
        baseline = db_session.query(BudgetBaseline).first()
        assert baseline.category == "education"
        assert float(baseline.baseline_amount) == 200.0


class TestComplianceCheck:
    def test_success(self, client, project):
        import sys
        mock_mod = Mock()
        mock_mod.run_compliance_check.return_value = {"status": "pass"}
        sys.modules['app.services.compliance_engine'] = mock_mod
        try:
            resp = client.get(f"/api/v1/fund-lifecycle/compliance-check/{project.id}")
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "pass"
        finally:
            sys.modules.pop('app.services.compliance_engine', None)

    def test_fail(self, client, project):
        import sys
        mock_mod = Mock()
        mock_mod.run_compliance_check.return_value = {"status": "fail", "issues": ["超支"]}
        sys.modules['app.services.compliance_engine'] = mock_mod
        try:
            resp = client.get(f"/api/v1/fund-lifecycle/compliance-check/{project.id}")
            assert resp.json()["data"]["status"] == "fail"
        finally:
            sys.modules.pop('app.services.compliance_engine', None)


class TestBudgetAggregation:
    def test_default(self, client, project, fund, db_session):
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation")
        assert resp.status_code == 200

    def test_by_type(self, client, project, fund, db_session):
        fund.type = "project"
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?group_by=type")
        assert resp.status_code == 200

    def test_by_village(self, client, project, fund, db_session):
        fund.village_id = 1
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?group_by=village")
        assert resp.status_code == 200

    def test_by_unit(self, client, project, fund, db_session):
        fund.fund_source = "military"
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?group_by=unit")
        assert resp.status_code == 200

    def test_by_organization(self, client, project, fund, db_session):
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?group_by=organization")
        assert resp.status_code == 200

    def test_year_filter(self, client, project, fund, db_session):
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?year=2025")
        assert resp.status_code == 200

    def test_org_filter_empty(self, client):
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?organization_id=999")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_org_filter_with_data(self, client, project, fund, db_session):
        project.organization_id = 1
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation?organization_id=1&group_by=type")
        assert resp.status_code == 200

    def test_execution_rate_zero(self, client, project, fund, db_session):
        fund.planned_amount = Decimal("0")
        fund.used_amount = Decimal("0")
        fund.date = date(2025, 6, 1)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/budget-aggregation")
        assert resp.status_code == 200


# =====================================================================
#  3.4 Quota Lock / Allocation Plan
# =====================================================================


class TestQuotaLock:
    def test_success(self, client, fund, db_session):
        fund.budget_locked = True
        fund.approved_amount = Decimal("500.00")
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/quota-lock/{fund.id}")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/quota-lock/999")
        assert resp.status_code == 404

    def test_not_locked(self, client, fund, db_session):
        fund.budget_locked = False
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/quota-lock/{fund.id}")
        assert resp.status_code == 400
        assert "锁定预算基线" in resp.text

    def test_exceeds_baseline(self, client, fund, db_session):
        fund.budget_locked = True
        fund.allocated_amount = Decimal("500.00")
        fund.approved_amount = Decimal("100.00")
        baseline = BudgetBaseline(
            fund_id=fund.id, project_id=fund.project_id,
            snapshot_year=2025, category="project",
            baseline_amount=Decimal("100.00"),
        )
        db_session.add(baseline)
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/quota-lock/{fund.id}")
        assert resp.status_code == 400
        assert "超过基线" in resp.text

    def test_no_baseline(self, client, fund, db_session):
        fund.budget_locked = True
        fund.allocated_amount = Decimal("300.00")
        fund.approved_amount = Decimal("300.00")
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/quota-lock/{fund.id}")
        assert resp.status_code == 200


class TestAllocationPlan:
    def test_success(self, client, project, fund, db_session):
        baseline = BudgetBaseline(
            fund_id=fund.id, project_id=project.id,
            snapshot_year=2025, category="project",
            baseline_amount=Decimal("500.00"),
        )
        db_session.add(baseline)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/allocation-plan/{project.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["baseline_amount"] == 500.0

    def test_no_baselines(self, client, project, fund):
        resp = client.get(f"/api/v1/fund-lifecycle/allocation-plan/{project.id}")
        assert resp.json()["data"]["items"][0]["baseline_amount"] is None

    def test_no_funds(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/allocation-plan/{project.id}")
        assert resp.json()["data"]["items"] == []


# =====================================================================
#  3.5 Transfer Vouchers
# =====================================================================


class TestListTransferVouchers:
    def test_empty(self, client):
        resp = client.get("/api/v1/fund-lifecycle/transfer-vouchers")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_with_filters(self, client, project, db_session):
        v = FundTransferVoucher(
            project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"), status="draft",
        )
        db_session.add(v)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/transfer-vouchers?project_id={project.id}&status=draft")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_filter_by_fund_id(self, client, project, fund, db_session):
        v = FundTransferVoucher(
            fund_id=fund.id, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
        )
        db_session.add(v)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/transfer-vouchers?fund_id={fund.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_pagination(self, client):
        resp = client.get("/api/v1/fund-lifecycle/transfer-vouchers?page=2&page_size=10")
        assert resp.status_code == 200


class TestCreateTransferVoucher:
    def test_success(self, client, project):
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers", json={
            "voucher_no": "V001", "direction": "military_to_local",
            "amount": 100.0, "project_id": project.id,
            "transfer_date": "2025-06-01",
            "payer_account": "PAYER", "payee_account": "PAYEE",
            "remarks": "test",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["voucher_no"] == "V001"

    def test_duplicate(self, client, project, db_session):
        v = FundTransferVoucher(
            voucher_no="V001", direction="military_to_local",
            amount=Decimal("50.00"), project_id=project.id,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers", json={
            "voucher_no": "V001", "direction": "military_to_local", "amount": 50.0,
        })
        assert resp.status_code == 400

    def test_insufficient_balance(self, client, fund, db_session):
        fund.approved_amount = Decimal("50.00")
        fund.used_amount = Decimal("0")
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers", json={
            "voucher_no": "V002", "direction": "military_to_local",
            "amount": 100.0, "fund_id": fund.id,
        })
        assert resp.status_code == 400
        assert "超过可用预算余额" in resp.text

    def test_balance_exact(self, client, fund, db_session):
        fund.approved_amount = Decimal("100.00")
        fund.used_amount = Decimal("0")
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers", json={
            "voucher_no": "V003", "direction": "military_to_local",
            "amount": 100.0, "fund_id": fund.id,
        })
        assert resp.status_code == 200

    def test_fund_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers", json={
            "voucher_no": "V004", "direction": "military_to_local",
            "amount": 100.0, "fund_id": 999,
        })
        assert resp.status_code == 200

    def test_balance_with_existing_transfers(self, client, fund, db_session):
        fund.approved_amount = Decimal("200.00")
        fund.used_amount = Decimal("0")
        v = FundTransferVoucher(
            fund_id=fund.id, voucher_no="V-EXIST", direction="military_to_local",
            amount=Decimal("150.00"), status="submitted",
        )
        db_session.add(v)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers", json={
            "voucher_no": "V005", "direction": "military_to_local",
            "amount": 60.0, "fund_id": fund.id,
        })
        assert resp.status_code == 400


class TestGetTransferVoucher:
    def test_success(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"), status="draft",
        )
        db_session.add(v)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/transfer-vouchers/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["voucher_no"] == "V001"

    def test_not_found(self, client):
        resp = client.get("/api/v1/fund-lifecycle/transfer-vouchers/999")
        assert resp.status_code == 404


class TestUpdateTransferVoucher:
    def test_success(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"), status="draft",
        )
        db_session.add(v)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/transfer-vouchers/1", json={"amount": 200.0})
        assert resp.status_code == 200
        assert resp.json()["data"]["amount"] == 200.0

    def test_not_found(self, client):
        resp = client.put("/api/v1/fund-lifecycle/transfer-vouchers/999", json={"amount": 100.0})
        assert resp.status_code == 404

    def test_confirmed_blocked(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status=VoucherStatus.CONFIRMED.value,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/transfer-vouchers/1", json={"amount": 200.0})
        assert resp.status_code == 400
        assert "不可修改" in resp.text


class TestDeleteTransferVoucher:
    def test_success(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status=VoucherStatus.DRAFT.value,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.delete("/api/v1/fund-lifecycle/transfer-vouchers/1")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.delete("/api/v1/fund-lifecycle/transfer-vouchers/999")
        assert resp.status_code == 404

    def test_not_draft(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status=VoucherStatus.CONFIRMED.value,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.delete("/api/v1/fund-lifecycle/transfer-vouchers/1")
        assert resp.status_code == 400


class TestConfirmTransferVoucher:
    def test_from_draft(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status=VoucherStatus.DRAFT.value,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers/1/confirm")
        assert resp.status_code == 200
        assert resp.json()["message"] == "凭证已确认"

    def test_from_submitted(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status=VoucherStatus.SUBMITTED.value,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers/1/confirm")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers/999/confirm")
        assert resp.status_code == 404

    def test_invalid_status(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status=VoucherStatus.CONFIRMED.value,
        )
        db_session.add(v)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/transfer-vouchers/1/confirm")
        assert resp.status_code == 400


class TestUploadVoucherAttachment:
    def test_success(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status="draft", fund_id=1,
        )
        db_session.add(v)
        db_session.flush()
        # Send as multipart file upload
        import io
        file_content = io.BytesIO(b"%PDF-1.4 fake pdf content")
        resp = client.post(
            "/api/v1/fund-lifecycle/transfer-vouchers/1/attachments",
            files={"file": ("receipt.pdf", file_content, "application/pdf")},
            data={"category": "bank_receipt"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["file_name"] == "receipt.pdf"

    def test_not_found(self, client):
        import io
        file_content = io.BytesIO(b"fake")
        resp = client.post(
            "/api/v1/fund-lifecycle/transfer-vouchers/999/attachments",
            files={"file": ("t.pdf", file_content, "application/pdf")},
        )
        assert resp.status_code == 404

    def test_with_description(self, client, project, db_session):
        v = FundTransferVoucher(
            id=1, project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"), status="draft",
        )
        db_session.add(v)
        db_session.flush()
        import io
        file_content = io.BytesIO(b"fake image content")
        resp = client.post(
            "/api/v1/fund-lifecycle/transfer-vouchers/1/attachments",
            files={"file": ("scan.jpg", file_content, "image/jpeg")},
            data={"description": "银行回单"},
        )
        assert resp.status_code == 200


class TestTransferLedger:
    def test_success(self, client, project, db_session):
        v1 = FundTransferVoucher(
            project_id=project.id, voucher_no="V001",
            direction="military_to_local", amount=Decimal("100.00"),
            status="confirmed", transfer_date=date(2025, 6, 1),
        )
        v2 = FundTransferVoucher(
            project_id=project.id, voucher_no="V002",
            direction="local_to_military", amount=Decimal("50.00"),
            status="confirmed", transfer_date=date(2025, 6, 2),
        )
        db_session.add_all([v1, v2])
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/transfer-ledger/{project.id}")
        data = resp.json()["data"]
        assert data["total_military_to_local"] == 100.0
        assert data["total_local_to_military"] == 50.0
        assert data["net_transfer"] == 50.0
        assert data["voucher_count"] == 2
        assert data["confirmed_count"] == 2

    def test_empty(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/transfer-ledger/{project.id}")
        assert resp.json()["data"]["voucher_count"] == 0


# =====================================================================
#  3.6 Contracts
# =====================================================================


class TestListContracts:
    def test_empty(self, client):
        resp = client.get("/api/v1/fund-lifecycle/contracts")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_with_filters(self, client, project, db_session):
        c = FundContract(
            id=1, project_id=project.id, contract_no="C001",
            contract_name="测试合同", contract_amount=Decimal("100.00"),
            status=ContractStatus.DRAFT.value,
        )
        db_session.add(c)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/contracts?project_id={project.id}&status=draft")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1


class TestCreateContract:
    def test_success(self, client, project):
        resp = client.post("/api/v1/fund-lifecycle/contracts", json={
            "contract_no": "C001", "contract_name": "新建合同",
            "contract_amount": 100.0, "project_id": project.id,
            "sign_date": "2025-06-01", "party_a": "甲方", "party_b": "乙方",
            "deadline": "2025-12-31", "remarks": "备注",
        })
        assert resp.status_code == 200

    def test_duplicate(self, client, project, db_session):
        db_session.add(FundContract(contract_no="C001", contract_name="Dup", project_id=project.id))
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/contracts", json={
            "contract_no": "C001", "contract_name": "重复",
        })
        assert resp.status_code == 400


class TestGetContract:
    def test_success(self, client, project, db_session):
        c = FundContract(
            id=1, project_id=project.id, contract_no="C001",
            contract_name="测试合同", contract_amount=Decimal("100.00"),
        )
        db_session.add(c)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/contracts/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["contract_no"] == "C001"

    def test_with_payments(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001", contract_name="C")
        db_session.add(c)
        p = FundContractPayment(
            contract_id=1, payment_no="C001-P001",
            amount=Decimal("50.00"), payment_date=date(2025, 6, 1), status="approved",
        )
        db_session.add(p)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/contracts/1")
        assert len(resp.json()["data"]["payments"]) == 1

    def test_not_found(self, client):
        resp = client.get("/api/v1/fund-lifecycle/contracts/999")
        assert resp.status_code == 404


class TestUpdateContract:
    def test_success(self, client, project, db_session):
        c = FundContract(
            id=1, project_id=project.id, contract_no="C001",
            contract_name="旧名称", contract_amount=Decimal("100.00"),
        )
        db_session.add(c)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/contracts/1", json={"contract_name": "新名称"})
        assert resp.status_code == 200
        assert resp.json()["data"]["contract_name"] == "新名称"

    def test_not_found(self, client):
        resp = client.put("/api/v1/fund-lifecycle/contracts/999", json={"contract_name": "x"})
        assert resp.status_code == 404


class TestDeleteContract:
    def test_success(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="待删", status=ContractStatus.DRAFT.value)
        db_session.add(c)
        db_session.flush()
        resp = client.delete("/api/v1/fund-lifecycle/contracts/1")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.delete("/api/v1/fund-lifecycle/contracts/999")
        assert resp.status_code == 404

    def test_not_draft(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="活跃", status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        db_session.flush()
        resp = client.delete("/api/v1/fund-lifecycle/contracts/1")
        assert resp.status_code == 400

    def test_with_payments(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="待删", status=ContractStatus.DRAFT.value)
        db_session.add(c)
        p = FundContractPayment(id=1, contract_id=1, amount=Decimal("10.00"),
                                payment_date=date(2025, 1, 1))
        db_session.add(p)
        db_session.flush()
        resp = client.delete("/api/v1/fund-lifecycle/contracts/1")
        assert resp.status_code == 200


class TestCreateContractPayment:
    def test_approved(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="合同", contract_amount=Decimal("200.00"),
                         status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/contracts/1/payments", json={
            "amount": 30.0, "payment_date": "2025-06-01", "purpose": "首付款",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "approved"

    def test_requires_approval(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="大额合同", contract_amount=Decimal("1000.00"),
                         status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/contracts/1/payments", json={
            "amount": 100.0, "payment_date": "2025-06-01",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "pending"
        assert "超过阈值" in resp.text

    def test_with_workflow(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="大额合同", contract_amount=Decimal("1000.00"),
                         status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        wf = ApprovalWorkflow(entity_type="fund_payment", is_active=True, name="付款审批")
        db_session.add(wf)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/contracts/1/payments", json={
            "amount": 100.0, "payment_date": "2025-06-01",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["approval"]["status"] == "submitted"

    def test_no_workflow(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="大额合同", contract_amount=Decimal("1000.00"),
                         status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/contracts/1/payments", json={
            "amount": 100.0, "payment_date": "2025-06-01",
        })
        assert resp.json()["data"]["approval"]["status"] == "no_workflow"

    def test_payment_approval_exception(self, client, project, db_session):
        """Trigger except path in _create_payment_approval by making ApprovalTask init fail."""
        from unittest.mock import patch as _patch
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="大额合同", contract_amount=Decimal("1000.00"),
                         status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        wf = ApprovalWorkflow(entity_type="fund_payment", is_active=True, name="付款审批")
        db_session.add(wf)
        db_session.flush()
        with _patch('app.models.approval.ApprovalTask.__init__', side_effect=Exception("mock init fail")):
            resp = client.post("/api/v1/fund-lifecycle/contracts/1/payments", json={
                "amount": 100.0, "payment_date": "2025-06-01",
            })
        assert resp.status_code == 200
        assert resp.json()["data"]["approval"]["status"] == "error"

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/contracts/999/payments", json={
            "amount": 10.0, "payment_date": "2025-06-01",
        })
        assert resp.status_code == 404

    def test_with_all_fields(self, client, project, db_session):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="合同", contract_amount=Decimal("200.00"),
                         status=ContractStatus.ACTIVE.value)
        db_session.add(c)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/contracts/1/payments", json={
            "amount": 30.0, "payment_date": "2025-06-01",
            "operator": "李四", "voucher_no": "V001",
            "wbs_code": "WBS-001", "task_id": 1, "remarks": "test",
            "purpose": "尾款",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["operator"] == "李四"


# =====================================================================
#  Monitoring: Deviation / Fund Flow
# =====================================================================


class TestMonitoringDeviation:
    def test_success(self, client, project, fund, db_session):
        fund.used_amount = Decimal("50.00")
        fund.approved_amount = Decimal("100.00")
        fund.amount = Decimal("100.00")
        project.progress = 50.0
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/deviation/{project.id}")
        assert resp.status_code == 200
        assert len(resp.json()["data"]["deviations"]) == 1

    def test_alert_green(self, client, project, fund, db_session):
        fund.used_amount = Decimal("50.00")
        fund.approved_amount = Decimal("100.00")
        fund.amount = Decimal("100.00")
        project.progress = 50.0
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/deviation/{project.id}")
        assert resp.json()["data"]["deviations"][0]["alert_level"] == "green"

    def test_alert_yellow(self, client, project, fund, db_session):
        fund.used_amount = Decimal("60.00")
        fund.approved_amount = Decimal("100.00")
        fund.amount = Decimal("100.00")
        project.progress = 50.0
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/deviation/{project.id}")
        assert resp.json()["data"]["deviations"][0]["alert_level"] == "yellow"

    def test_alert_red(self, client, project, fund, db_session):
        fund.used_amount = Decimal("80.00")
        fund.approved_amount = Decimal("100.00")
        fund.amount = Decimal("100.00")
        project.progress = 50.0
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/deviation/{project.id}")
        assert resp.json()["data"]["deviations"][0]["alert_level"] == "red"

    def test_zero_approved(self, client, project, fund, db_session):
        fund.used_amount = Decimal("0")
        fund.approved_amount = Decimal("0")
        fund.amount = Decimal("0")
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/deviation/{project.id}")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.get("/api/v1/fund-lifecycle/monitoring/deviation/999")
        assert resp.status_code == 404

    def test_with_report(self, client, project, fund, db_session):
        import sys
        mock_mod = Mock()
        mock_mod.generate_deviation_report.return_value = {"report": "data"}
        sys.modules['app.services.fund_report_generator'] = mock_mod
        try:
            fund.approved_amount = Decimal("100.00")
            fund.amount = Decimal("100.00")
            db_session.flush()
            resp = client.get(f"/api/v1/fund-lifecycle/monitoring/deviation/{project.id}?generate_report=true")
            assert resp.status_code == 200
            assert "report" in resp.json()["data"]
        finally:
            sys.modules.pop('app.services.fund_report_generator', None)


class TestFundFlow:
    def test_success(self, client, project, fund, db_session):
        t = FundTransaction(
            fund_id=fund.id, amount=Decimal("50.00"), purpose="采购",
            transaction_date=date(2025, 6, 1), status="completed",
            project_id=project.id,
        )
        db_session.add(t)
        v = FundTransferVoucher(
            fund_id=fund.id, project_id=project.id,
            voucher_no="V001", direction="military_to_local",
            amount=Decimal("100.00"), status="confirmed",
        )
        db_session.add(v)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/fund-flow/{project.id}")
        data = resp.json()["data"]
        assert len(data["fund_flows"]) == 1
        assert len(data["fund_flows"][0]["transactions"]) == 1
        assert len(data["fund_flows"][0]["transfer_vouchers"]) == 1

    def test_no_funds(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/fund-flow/{project.id}")
        assert resp.json()["data"]["fund_flows"] == []


# =====================================================================
#  3.7 Anomalies
# =====================================================================


class TestListAnomalies:
    def test_empty(self, client):
        resp = client.get("/api/v1/fund-lifecycle/anomalies")
        assert resp.status_code == 200 and resp.json()["data"]["total"] == 0

    def test_all_filters(self, client, project, fund, db_session):
        a = FundAnomaly(project_id=project.id, fund_id=fund.id, anomaly_type="overspend",
                        severity="danger", description="x", resolved=False)
        db_session.add(a)
        db_session.flush()
        resp = client.get(
            f"/api/v1/fund-lifecycle/anomalies?project_id={project.id}&fund_id={fund.id}"
            f"&anomaly_type=overspend&severity=danger&resolved=false"
        )
        assert resp.json()["data"]["total"] == 1

    def test_resolved_true(self, client, project, db_session):
        a = FundAnomaly(project_id=project.id, anomaly_type="overspend",
                        severity="warning", description="x", resolved=True)
        db_session.add(a)
        db_session.flush()
        resp = client.get("/api/v1/fund-lifecycle/anomalies?resolved=true")
        assert resp.status_code == 200


class TestDetectAnomalies:
    def test_success(self, client, project):
        import sys
        mock_mod = Mock()
        mock_mod.detect_anomalies.return_value = [{"id": 1}]
        sys.modules['app.services.fund_anomaly_detector'] = mock_mod
        try:
            resp = client.post(f"/api/v1/fund-lifecycle/anomalies/detect/{project.id}")
            assert resp.status_code == 200
            assert resp.json()["data"]["new_count"] == 1
        finally:
            sys.modules.pop('app.services.fund_anomaly_detector', None)

    def test_empty(self, client, project):
        import sys
        mock_mod = Mock()
        mock_mod.detect_anomalies.return_value = []
        sys.modules['app.services.fund_anomaly_detector'] = mock_mod
        try:
            resp = client.post(f"/api/v1/fund-lifecycle/anomalies/detect/{project.id}")
            assert resp.json()["data"]["new_count"] == 0
        finally:
            sys.modules.pop('app.services.fund_anomaly_detector', None)


class TestResolveAnomaly:
    def test_success(self, client, project, fund, db_session):
        a = FundAnomaly(id=1, project_id=project.id, fund_id=fund.id,
                        anomaly_type="overspend", severity="danger",
                        description="超支", resolved=False)
        db_session.add(a)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "已处理"})
        assert resp.status_code == 200
        assert db_session.get(FundAnomaly, 1).resolved is True

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/anomalies/999/resolve", json={"resolution": "x"})
        assert resp.status_code == 404

    def test_already_resolved(self, client, project, db_session):
        a = FundAnomaly(id=1, project_id=project.id, anomaly_type="deviation",
                        severity="info", description="x", resolved=True)
        db_session.add(a)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "x"})
        assert resp.status_code == 400

    def test_clears_fund_flag(self, client, project, fund, db_session):
        fund.has_anomaly = True
        a = FundAnomaly(id=1, project_id=project.id, fund_id=fund.id,
                        anomaly_type="overspend", severity="danger", description="x", resolved=False)
        db_session.add(a)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "fixed"})
        assert resp.status_code == 200
        db_session.refresh(fund)
        assert fund.has_anomaly is False

    def test_other_anomalies_remain(self, client, project, fund, db_session):
        fund.has_anomaly = True
        a1 = FundAnomaly(id=1, project_id=project.id, fund_id=fund.id,
                         anomaly_type="overspend", severity="danger", description="x", resolved=False)
        a2 = FundAnomaly(id=2, project_id=project.id, fund_id=fund.id,
                         anomaly_type="idle", severity="warning", description="y", resolved=False)
        db_session.add_all([a1, a2])
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "fixed"})
        assert resp.status_code == 200
        db_session.refresh(fund)
        assert fund.has_anomaly is True

    def test_no_fund_id(self, client, project, db_session):
        a = FundAnomaly(id=1, project_id=project.id, fund_id=None,
                        anomaly_type="deviation", severity="info", description="x", resolved=False)
        db_session.add(a)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "done"})
        assert resp.status_code == 200

    def test_no_fund_record(self, client, project, db_session):
        a = FundAnomaly(id=1, project_id=project.id, fund_id=999,
                        anomaly_type="deviation", severity="info", description="x", resolved=False)
        db_session.add(a)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "done"})
        assert resp.status_code == 200


# =====================================================================
#  3.8 Settlement / Performance
# =====================================================================


class TestCreateSettlement:
    def test_success(self, client, project, fund, db_session):
        fund.approved_amount = Decimal("500.00")
        fund.used_amount = Decimal("300.00")
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/settlement/{project.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_budget"] == 500.0 and data["total_spent"] == 300.0

    def test_with_data(self, client, project, fund, db_session):
        fund.approved_amount = Decimal("100.00")
        fund.used_amount = Decimal("50.00")
        db_session.flush()
        resp = client.post(f"/api/v1/fund-lifecycle/settlement/{project.id}",
                           json={"fund_id": fund.id, "remarks": "测试决算"})
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/settlement/999")
        assert resp.status_code == 404

    def test_no_funds(self, client, project):
        resp = client.post(f"/api/v1/fund-lifecycle/settlement/{project.id}")
        assert resp.status_code == 200


class TestUpdateSettlement:
    def test_success(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_budget=Decimal("500.00"), total_spent=Decimal("300.00"),
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/settlement/1", json={
            "total_budget": 600.0, "total_spent": 400.0, "audit_opinion": "同意",
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_budget"] == 600.0 and data["total_remaining"] == 200.0

    def test_not_found(self, client):
        resp = client.put("/api/v1/fund-lifecycle/settlement/999", json={"total_budget": 100.0})
        assert resp.status_code == 404

    def test_approved_forbidden(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.APPROVED.value)
        db_session.add(s)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/settlement/1", json={"total_budget": 100.0})
        assert resp.status_code == 400

    def test_partial_update(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_budget=Decimal("500.00"), total_spent=Decimal("300.00"),
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/settlement/1", json={"audit_opinion": "通过"})
        assert resp.status_code == 200

    def test_recalc_remaining(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_budget=Decimal("500.00"), total_spent=Decimal("300.00"),
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        resp = client.put("/api/v1/fund-lifecycle/settlement/1", json={"total_budget": 200.0, "total_spent": 100.0})
        assert resp.json()["data"]["total_remaining"] == 100.0


class TestApproveSettlement:
    def test_success(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/settlement/1/approve")
        assert resp.status_code == 200
        db_session.refresh(s)
        assert s.status == SettlementStatus.APPROVED.value

    def test_with_data(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        client.post("/api/v1/fund-lifecycle/settlement/1/approve", json={
            "audit_opinion": "批准", "performance_score": 85, "performance_level": "B",
        })
        db_session.refresh(s)
        assert s.performance_score == 85 and s.performance_level == "B"

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/settlement/999/approve")
        assert resp.status_code == 404

    def test_auto_A(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        _ = client.post("/api/v1/fund-lifecycle/settlement/1/approve", json={"performance_score": 95})
        db_session.refresh(s)
        assert s.performance_level == "A"

    def test_auto_B(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        _ = client.post("/api/v1/fund-lifecycle/settlement/1/approve", json={"performance_score": 80})
        db_session.refresh(s)
        assert s.performance_level == "B"

    def test_auto_C(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        _ = client.post("/api/v1/fund-lifecycle/settlement/1/approve", json={"performance_score": 65})
        db_session.refresh(s)
        assert s.performance_level == "C"

    def test_auto_D(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        _ = client.post("/api/v1/fund-lifecycle/settlement/1/approve", json={"performance_score": 50})
        db_session.refresh(s)
        assert s.performance_level == "D"

    def test_updates_fund(self, client, project, fund, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.DRAFT.value)
        db_session.add(s)
        db_session.flush()
        _ = client.post("/api/v1/fund-lifecycle/settlement/1/approve")
        db_session.refresh(fund)
        assert fund.settlement_status == "approved"


class TestPerformance:
    def test_success(self, client, project, fund, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_budget=Decimal("500.00"), total_spent=Decimal("300.00"),
                           status=SettlementStatus.APPROVED.value,
                           performance_score=90, performance_level="A")
        db_session.add(s)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/performance/{project.id}")
        assert resp.json()["data"]["settlement"]["performance_score"] == 90

    def test_no_settlement(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/performance/{project.id}")
        assert resp.json()["data"]["settlement"] is None

    def test_execution_rate(self, client, project, fund, db_session):
        fund.approved_amount = Decimal("200.00")
        fund.amount = Decimal("200.00")
        fund.used_amount = Decimal("50.00")
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/performance/{project.id}")
        assert resp.json()["data"]["budget_summary"]["execution_rate"] == 25.0

    def test_zero_budget(self, client, project, fund, db_session):
        fund.approved_amount = Decimal("0")
        fund.amount = Decimal("0")
        fund.used_amount = Decimal("0")
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/performance/{project.id}")
        assert resp.json()["data"]["budget_summary"]["execution_rate"] == 0

    def test_anomaly_stats(self, client, project, db_session):
        db_session.add_all([
            FundAnomaly(project_id=project.id, anomaly_type="overspend",
                        severity="danger", description="x", resolved=True),
            FundAnomaly(project_id=project.id, anomaly_type="idle",
                        severity="warning", description="y", resolved=False),
        ])
        db_session.flush()
        anom = client.get(f"/api/v1/fund-lifecycle/performance/{project.id}").json()["data"]["anomaly_summary"]
        assert anom["total"] == 2 and anom["resolved"] == 1 and anom["unresolved"] == 1
        assert anom["resolution_rate"] == 50.0

    def test_no_anomalies(self, client, project):
        anom = client.get(f"/api/v1/fund-lifecycle/performance/{project.id}").json()["data"]["anomaly_summary"]
        assert anom["total"] == 0 and anom["resolution_rate"] == 100.0


# =====================================================================
#  3.9 Health Score
# =====================================================================


class TestHealth:
    def test_success(self, client, project):
        """健康度端点按项目聚合资金记录计算，返回 health_score + details"""
        resp = client.get(f"/api/v1/fund-lifecycle/health/{project.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100
        assert "details" in data
        assert "budget_execution" in data["details"]
        assert "score" in data["details"]["budget_execution"]

    def test_invalid_project_id_400(self, client):
        """project_id <= 0 → 400 提示选择具体项目（不再误导为项目不存在）"""
        resp = client.get("/api/v1/fund-lifecycle/health/0")
        assert resp.status_code == 400
        assert "项目ID" in resp.json()["detail"]

    def test_batch(self, client):
        resp = client.post("/api/v1/fund-lifecycle/health/batch", json={"project_ids": []})
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# =====================================================================
#  3.10 Allocation Orders
# =====================================================================


class TestListAllocationOrders:
    def test_empty(self, client):
        resp = client.get("/api/v1/fund-lifecycle/allocation-orders")
        assert resp.status_code == 200 and resp.json()["data"]["total"] == 0

    def test_with_filters(self, client, project, db_session):
        o = FundAllocationOrder(id=1, project_id=project.id, order_no="AO001",
                                total_amount=Decimal("100.00"), status="draft")
        db_session.add(o)
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/allocation-orders?project_id={project.id}&status=draft")
        assert resp.json()["data"]["total"] == 1


class TestCreateAllocationOrder:
    def test_success(self, client, project):
        resp = client.post("/api/v1/fund-lifecycle/allocation-orders", json={
            "order_no": "AO001", "total_amount": 100.0, "project_id": project.id,
            "source_document": "指标文001",
            "target_organization_id": 1, "target_organization_name": "某单位",
            "target_account": "123456", "issue_date": "2025-06-01", "remarks": "test",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["order_no"] == "AO001"

    def test_duplicate(self, client, db_session):
        db_session.add(FundAllocationOrder(order_no="AO001", total_amount=Decimal("50.00")))
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/allocation-orders", json={
            "order_no": "AO001", "total_amount": 100.0,
        })
        assert resp.status_code == 400


class TestIssueAllocationOrder:
    def test_success(self, client, db_session):
        o = FundAllocationOrder(id=1, order_no="AO001", total_amount=Decimal("100.00"), status="draft")
        db_session.add(o)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/allocation-orders/1/issue")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/allocation-orders/999/issue")
        assert resp.status_code == 404

    def test_not_draft(self, client, db_session):
        o = FundAllocationOrder(id=1, order_no="AO001", total_amount=Decimal("100.00"), status="issued")
        db_session.add(o)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/allocation-orders/1/issue")
        assert resp.status_code == 400


# =====================================================================
#  3.11 Quota Adjust
# =====================================================================


class TestQuotaAdjust:
    def test_success(self, client, fund):
        resp = client.put(f"/api/v1/fund-lifecycle/quota-adjust/{fund.id}", json={
            "new_amount": 600.0, "reason": "预算增加",
        })
        assert resp.status_code == 200
        assert "待审批" in resp.text

    def test_emergency_super_admin(self, client, fund, db_session):
        resp = client.put(f"/api/v1/fund-lifecycle/quota-adjust/{fund.id}", json={
            "new_amount": 700.0, "reason": "紧急调整", "is_emergency": True,
        })
        assert resp.status_code == 200
        assert "已生效" in resp.text
        db_session.refresh(fund)
        assert float(fund.approved_amount) == 700.0

    def test_emergency_forbidden(self, client, fund, db_session):
        from app.main import app
        u = Mock()
        u.id = 2
        u.username = "manager"
        u.role = "manager"
        u.is_superuser = False
        u.is_active = True
        u.permissions_list = ["read", "write"]
        u.organization_id = 1
        u.email = "m@t.com"
        u.full_name = "经理"
        async def _auth(): return u
        _original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_user] = _auth
        resp = client.put(f"/api/v1/fund-lifecycle/quota-adjust/{fund.id}", json={
            "new_amount": 700.0, "reason": "紧急", "is_emergency": True,
        })
        assert resp.status_code == 403
        app.dependency_overrides.pop(get_current_user, None)

    def test_not_found(self, client):
        resp = client.put("/api/v1/fund-lifecycle/quota-adjust/999", json={
            "new_amount": 100.0, "reason": "调整",
        })
        assert resp.status_code == 404

    def test_empty_reason(self, client, fund):
        resp = client.put(f"/api/v1/fund-lifecycle/quota-adjust/{fund.id}", json={
            "new_amount": 100.0, "reason": "   ",
        })
        assert resp.status_code == 422

    def test_reason_validator(self, client, fund):
        resp = client.put(f"/api/v1/fund-lifecycle/quota-adjust/{fund.id}", json={
            "new_amount": 100.0, "reason": " 有效原因 ",
        })
        assert resp.status_code == 200

    def test_creates_version(self, client, fund, db_session):
        _ = client.put(f"/api/v1/fund-lifecycle/quota-adjust/{fund.id}", json={
            "new_amount": 800.0, "reason": "版本测试",
        })
        bv = db_session.query(BudgetVersion).filter(BudgetVersion.fund_id == fund.id).first()
        assert bv is not None and bv.version == 2 and bv.status == "submitted"


# =====================================================================
#  3.12 Inspection Clues
# =====================================================================


class TestInspectionClues:
    def test_success(self, client, project, fund, db_session):
        db_session.add_all([
            FundAnomaly(project_id=project.id, fund_id=fund.id,
                        anomaly_type="overspend", severity="danger", description="严重超支", resolved=False),
            FundAnomaly(project_id=project.id, fund_id=fund.id,
                        anomaly_type="idle", severity="warning", description="闲置", resolved=True),
        ])
        db_session.flush()
        data = client.get(f"/api/v1/fund-lifecycle/inspection-clues/{project.id}").json()["data"]
        assert data["total_clues"] == 2 and data["unresolved_count"] == 1
        type_labels = [c["type_label"] for c in data["clues"]]
        assert "超支" in type_labels
        assert "资金闲置" in type_labels

    def test_no_anomalies(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/inspection-clues/{project.id}")
        assert resp.json()["data"]["total_clues"] == 0

    def test_unknown_type(self, client, project, fund, db_session):
        a = FundAnomaly(project_id=project.id, fund_id=fund.id,
                        anomaly_type="unknown", severity="info",
                        description="未知", resolved=False)
        db_session.add(a)
        db_session.flush()
        c = client.get(f"/api/v1/fund-lifecycle/inspection-clues/{project.id}").json()["data"]["clues"][0]
        assert c["suggestion"] == "建议进一步核查"

    def test_no_fund(self, client, project, db_session):
        a = FundAnomaly(project_id=project.id, fund_id=None,
                        anomaly_type="deviation", severity="warning",
                        description="偏差", resolved=False)
        db_session.add(a)
        db_session.flush()
        c = client.get(f"/api/v1/fund-lifecycle/inspection-clues/{project.id}").json()["data"]["clues"][0]
        assert c["involved_amount"] is None


# =====================================================================
#  3.13 Asset Verification
# =====================================================================


class TestVerifyAsset:
    def test_passed(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_spent=Decimal("100.00"), status=SettlementStatus.APPROVED.value)
        db_session.add(s)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/settlement/1/verify-asset", json={
            "asset_value": 98.0, "opinion": "一致",
        })
        assert resp.json()["success"] is True and "通过" in resp.text

    def test_failed(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_spent=Decimal("100.00"), status=SettlementStatus.APPROVED.value)
        db_session.add(s)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/settlement/1/verify-asset", json={"asset_value": 80.0})
        assert "未通过" in resp.text

    def test_not_found(self, client):
        resp = client.post("/api/v1/fund-lifecycle/settlement/999/verify-asset", json={"asset_value": 100.0})
        assert resp.status_code == 404

    def test_zero_spent(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           total_spent=Decimal("0"), status=SettlementStatus.APPROVED.value)
        db_session.add(s)
        db_session.flush()
        resp = client.post("/api/v1/fund-lifecycle/settlement/1/verify-asset", json={"asset_value": 0})
        assert resp.status_code == 200


# =====================================================================
#  3.14 Performance Report / Feasibility Report
# =====================================================================


class TestPerformanceReport:
    def test_success(self, client, project):
        import sys
        mock_mod = Mock()
        mock_mod.generate_performance_report.return_value = {"score": 90}
        sys.modules['app.services.performance_evaluator'] = mock_mod
        try:
            resp = client.get(f"/api/v1/fund-lifecycle/performance-report/{project.id}")
            assert resp.json()["data"]["score"] == 90
        finally:
            sys.modules.pop('app.services.performance_evaluator', None)


class TestFeasibilityReport:
    def test_success(self, client, project):
        import sys
        mock_mod = Mock()
        mock_mod.generate_feasibility_report.return_value = {"investment": 500.0}
        sys.modules['app.services.fund_report_generator'] = mock_mod
        try:
            resp = client.get(f"/api/v1/fund-lifecycle/feasibility-report/{project.id}")
            assert resp.json()["data"]["investment"] == 500.0
        finally:
            sys.modules.pop('app.services.fund_report_generator', None)


# =====================================================================
#  3.15 Fund Flow Tree
# =====================================================================


class TestFundFlowTree:
    def test_success(self, client, project, fund, db_session):
        o = FundAllocationOrder(id=1, fund_id=fund.id, project_id=project.id,
                                order_no="AO001", total_amount=Decimal("100.00"), status="issued")
        db_session.add(o)
        db_session.flush()
        item = AllocationOrderItem(order_id=1, organization_name="某单位",
                                   amount=Decimal("100.00"), status="transferred")
        db_session.add(item)
        t = FundTransaction(fund_id=fund.id, amount=Decimal("50.00"), purpose="采购",
                            transaction_date=date(2025, 6, 1), status="completed", project_id=project.id)
        db_session.add(t)
        db_session.flush()
        data = client.get(f"/api/v1/fund-lifecycle/monitoring/fund-flow-tree/{project.id}").json()
        assert data["success"] is True
        tree = data["data"]["fund_tree"]
        assert len(tree) == 1 and len(tree[0]["allocation_orders"]) == 1
        assert len(tree[0]["transactions"]) == 1

    def test_no_funds(self, client, project):
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/fund-flow-tree/{project.id}")
        assert resp.json() == []

    def test_with_code(self, client, project, fund, db_session):
        fund.code = "F001"
        db_session.flush()
        data = client.get(f"/api/v1/fund-lifecycle/monitoring/fund-flow-tree/{project.id}?fund_code=F001").json()
        assert len(data["data"]["fund_tree"]) == 1

    def test_code_no_match(self, client, project, fund, db_session):
        fund.code = "F001"
        db_session.flush()
        resp = client.get(f"/api/v1/fund-lifecycle/monitoring/fund-flow-tree/{project.id}?fund_code=NONEXIST")
        assert resp.json() == []


# =====================================================================
#  Auth / Permission Tests
# =====================================================================


class TestForbiddenForViewer:
    ENDPOINTS = [
        ("POST", "/api/v1/fund-lifecycle/phases/1/advance", {}),
        ("POST", "/api/v1/fund-lifecycle/phases/1/rollback", {}),
        ("POST", "/api/v1/fund-lifecycle/initiate/1", {}),
        ("POST", "/api/v1/fund-lifecycle/budget-lock/1", {}),
        ("POST", "/api/v1/fund-lifecycle/quota-lock/1", {}),
        ("POST", "/api/v1/fund-lifecycle/transfer-vouchers",
         {"voucher_no": "VX", "direction": "military_to_local", "amount": 10.0}),
        ("PUT", "/api/v1/fund-lifecycle/transfer-vouchers/1", {"amount": 10.0}),
        ("DELETE", "/api/v1/fund-lifecycle/transfer-vouchers/1", None),
        ("POST", "/api/v1/fund-lifecycle/transfer-vouchers/1/confirm", None),
        ("POST", "/api/v1/fund-lifecycle/transfer-vouchers/1/attachments",
         {"_multipart": True, "file_name": "t.pdf"}),
        ("POST", "/api/v1/fund-lifecycle/contracts", {"contract_no": "CX", "contract_name": "x"}),
        ("PUT", "/api/v1/fund-lifecycle/contracts/1", {"contract_name": "x"}),
        ("DELETE", "/api/v1/fund-lifecycle/contracts/1", None),
        ("POST", "/api/v1/fund-lifecycle/contracts/1/payments", {"amount": 10.0, "payment_date": "2025-06-01"}),
        ("POST", "/api/v1/fund-lifecycle/anomalies/detect/1", None),
        ("POST", "/api/v1/fund-lifecycle/anomalies/1/resolve", {"resolution": "x"}),
        ("POST", "/api/v1/fund-lifecycle/settlement/1", {}),
        ("PUT", "/api/v1/fund-lifecycle/settlement/1", {"test": True}),
        ("POST", "/api/v1/fund-lifecycle/settlement/1/approve", {}),
        ("POST", "/api/v1/fund-lifecycle/settlement/1/verify-asset", {"asset_value": 100.0}),
        ("PUT", "/api/v1/fund-lifecycle/quota-adjust/1", {"new_amount": 100.0, "reason": "x"}),
        ("POST", "/api/v1/fund-lifecycle/allocation-orders", {"order_no": "AOX", "total_amount": 10.0}),
        ("POST", "/api/v1/fund-lifecycle/allocation-orders/1/issue", None),
    ]

    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_viewer_gets_403(self, client, db_session, method, path, body):
        import io
        from app.main import app
        u = _viewer_user()
        async def _auth(): return u
        original = app.dependency_overrides.get(get_current_user)
        _original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_user] = _auth
        try:
            # Handle multipart file upload endpoints differently
            if body and isinstance(body, dict) and body.pop("_multipart", False):
                file_content = io.BytesIO(b"fake")
                resp = client.request(
                    method, path,
                    files={"file": (body.get("file_name", "t.pdf"), file_content, "application/pdf")},
                )
            else:
                resp = client.request(method, path, json=body)
            assert resp.status_code == 403, f"{method} {path} expected 403 got {resp.status_code}"
        finally:
            if original:
                app.dependency_overrides[get_current_user] = original
            else:
                app.dependency_overrides.pop(get_current_user, None)
