"""短期项 2 回归：项目决算 total_remaining 重算（2026-11-01 审计）。

历史缺陷：决算结余只在「生成决算」时按当时的经费算一次；之后追加支出或只更新
单个字段（预算/支出）都不会重算，审批后错误金额被固化（不可改）。

覆盖：
- ``refresh_project_settlements``：重算非审批决算、跳过 APPROVED、非法 project_id 返回 0
- ``recalculate_settlement_totals``：预算按 approved > planned > amount 兜底、project_id 为空不动
- ``PUT /fund-lifecycle/settlement/{id}`` 只改 total_spent 时结余同步重算
- ``POST /fund-lifecycle/settlement/{id}/approve`` 固化前按当前经费重算
"""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.fund import Fund
from app.models.fund_lifecycle import FundSettlement, SettlementStatus
from app.models.project import Project
from app.services.fund_settlement_service import (
    recalculate_settlement_totals,
    refresh_project_settlements,
)

_BASE = "/api/v1/fund-lifecycle"


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
    admin.full_name = "Admin"

    async def _get_current_user():
        return admin

    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user

    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original


@pytest.fixture
def project(db_session):
    p = Project(
        name="决算重算测试项目",
        type="infrastructure",
        budget=Decimal("1000.00"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="in_progress",
        organization_id=1,
    )
    db_session.add(p)
    db_session.flush()
    return p


def _fund(project_id: int, *, approved, planned=0, amount=0, used=0) -> Fund:
    """构造最小经费行（name 可空，金额字段全部显式给值以便断言）。"""
    return Fund(
        project_id=project_id,
        name="决算重算测试经费",
        approved_amount=approved,
        planned_amount=planned,
        amount=amount,
        used_amount=used,
    )


def _settlement(project_id: int, *, no: str, status: str, budget=0, spent=0, remaining=0) -> FundSettlement:
    return FundSettlement(
        project_id=project_id,
        settlement_no=no,
        status=status,
        total_budget=Decimal(str(budget)),
        total_spent=Decimal(str(spent)),
        total_remaining=Decimal(str(remaining)),
    )


class TestRefreshProjectSettlements:
    def test_recalculates_draft_and_skips_approved(self, project, db_session):
        draft = _settlement(project.id, no="JS-R-DRAFT", status=SettlementStatus.DRAFT.value)
        approved = _settlement(project.id, no="JS-R-APPROVED", status=SettlementStatus.APPROVED.value,
                               budget=1, spent=1, remaining=0)
        db_session.add_all([draft, approved])
        db_session.add_all([
            _fund(project.id, approved=100, planned=90, amount=80, used=40),
            _fund(project.id, approved=None, planned=50, amount=30, used=10),
        ])
        db_session.flush()

        updated = refresh_project_settlements(db_session, project.id)

        assert updated == 1
        # refresh() 会丢弃未 flush 的改动：生产路径由 safe_commit 落库，这里显式 flush
        db_session.flush()
        db_session.refresh(draft)
        db_session.refresh(approved)
        assert draft.total_budget == Decimal("150.0000")
        assert draft.total_spent == Decimal("50.0000")
        assert draft.total_remaining == Decimal("100.0000")
        # 已审批决算=固化档案，不得被重算
        assert approved.total_budget == Decimal("1.0000")
        assert approved.total_spent == Decimal("1.0000")

    def test_invalid_project_id_is_noop(self, db_session):
        assert refresh_project_settlements(db_session, None) == 0
        assert refresh_project_settlements(db_session, "not-an-int") == 0
        assert refresh_project_settlements(db_session, 0) == 0

    def test_all_approved_returns_zero(self, project, db_session):
        """只有已审批决算时：查到记录但一条都不改（touched=0 分支）。"""
        db_session.add(_settlement(project.id, no="JS-R-ALL-APPROVED",
                                   status=SettlementStatus.APPROVED.value, budget=3, spent=1, remaining=2))
        db_session.flush()

        assert refresh_project_settlements(db_session, project.id) == 0


class TestRecalculateSettlementTotals:
    def test_budget_falls_back_to_planned_then_amount(self, project, db_session):
        settlement = _settlement(project.id, no="JS-R-FALLBACK", status=SettlementStatus.DRAFT.value)
        db_session.add(settlement)
        db_session.add_all([
            _fund(project.id, approved=None, planned=20, amount=10, used=5),
            _fund(project.id, approved=None, planned=0, amount=8, used=3),
        ])
        db_session.flush()

        recalculate_settlement_totals(db_session, settlement)

        assert settlement.total_budget == Decimal("28.0000")
        assert settlement.total_spent == Decimal("8.0000")
        assert settlement.total_remaining == Decimal("20.0000")

    def test_projectless_settlement_untouched(self, db_session):
        # project_id 列是 NOT NULL，这里不落库：只验证「空 project_id 时不做任何聚合」
        settlement = FundSettlement(
            project_id=None,
            settlement_no="JS-R-ORPHAN",
            status=SettlementStatus.DRAFT.value,
            total_budget=Decimal("7"),
            total_spent=Decimal("2"),
            total_remaining=Decimal("5"),
        )

        recalculate_settlement_totals(db_session, settlement)

        assert settlement.total_budget == Decimal("7")
        assert settlement.total_remaining == Decimal("5")


class TestSettlementApiRecompute:
    def test_update_single_field_recomputes_remaining(self, client, project, db_session):
        settlement = _settlement(project.id, no="JS-R-API-UPDATE", status=SettlementStatus.DRAFT.value,
                                 budget=100, spent=30, remaining=70)
        db_session.add(settlement)
        db_session.flush()

        resp = client.put(f"{_BASE}/settlement/{settlement.id}", json={"total_spent": 45})

        assert resp.status_code == 200, resp.text
        db_session.refresh(settlement)
        assert settlement.total_remaining == Decimal("55.0000")

    def test_update_without_total_spent_does_not_recompute(self, client, project, db_session):
        """预算与支出缺一时不重算结余（避免用 None 做减法）。"""
        settlement = _settlement(project.id, no="JS-R-API-UPDATE-NOSPENT",
                                 status=SettlementStatus.DRAFT.value,
                                 budget=100, spent=30, remaining=70)
        db_session.add(settlement)
        db_session.flush()
        settlement.total_spent = None
        db_session.flush()

        resp = client.put(f"{_BASE}/settlement/{settlement.id}", json={"total_budget": 120})

        assert resp.status_code == 200, resp.text
        db_session.refresh(settlement)
        assert settlement.total_budget == Decimal("120.0000")
        assert settlement.total_remaining == Decimal("70.0000")

    def test_approve_recomputes_before_freezing(self, client, project, db_session):
        settlement = _settlement(project.id, no="JS-R-API-APPROVE", status=SettlementStatus.DRAFT.value,
                                 budget=100, spent=30, remaining=70)
        db_session.add(settlement)
        db_session.add(_fund(project.id, approved=100, used=60))
        db_session.flush()

        resp = client.post(f"{_BASE}/settlement/{settlement.id}/approve", json={})

        assert resp.status_code == 200, resp.text
        db_session.refresh(settlement)
        assert settlement.status == SettlementStatus.APPROVED.value
        # 审批前按当前经费重算：结余 = 100 - 60，而不是旧的 70
        assert settlement.total_spent == Decimal("60.0000")
        assert settlement.total_remaining == Decimal("40.0000")
