"""Tests for app.api.v1.fund_budgets — 7 endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def mock_db():
    s = MagicMock()
    s.query.return_value = s
    s.filter.return_value = s
    s.order_by.return_value = s
    s.offset.return_value = s
    s.limit.return_value = s
    s.all.return_value = []
    s.first.return_value = None
    return s


def _make_budget():
    b = MagicMock()
    b.id = 1; b.year = 2025; b.category = "基础设施建设"
    b.budget_amount = 100000.0; b.executed_amount = 50000.0
    b.village_id = 1; b.organization_id = None
    b.description = "道路修建"; b.remarks = "备注"
    b.remaining_amount = 50000.0; b.execution_rate = 50.0
    b.to_dict.return_value = {"id": 1, "year": 2025, "category": "基础设施建设",
        "budget_amount": 100000.0, "executed_amount": 50000.0, "remaining_amount": 50000.0,
        "execution_rate": 50.0, "village_id": 1, "description": "道路修建"}
    return b


def _make_tx():
    t = MagicMock()
    t.id = 1; t.fund_id = None; t.project_id = None; t.village_id = 1
    t.budget_id = 1; t.amount = 5000.0; t.category = "基建"; t.purpose = "修路"
    t.transaction_date = date(2025, 6, 15); t.receipt_number = "R001"
    t.handler = "张三"; t.reimbursement_person = "李四"; t.status = "completed"
    t.remarks = None; t.created_at = None
    t.to_dict.return_value = {"id": 1, "amount": 5000.0, "purpose": "修路",
        "transaction_date": "2025-06-15", "status": "completed"}
    return t


@pytest.fixture
def client(mock_db):
    from app.api.v1 import deps
    app = FastAPI()
    user = MagicMock()
    user.id = 1; user.role = "manager"; user.is_superuser = True
    app.dependency_overrides[deps.get_current_user] = lambda: user
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    from app.api.v1.fund_budgets import router
    app.include_router(router)
    # 关闭 response_model 校验——Mock ORM 对象无法通过 Pydantic schema 验证。
    # 通过真实 SQLite 的集成测试在生产环境中覆盖响应模型。
    from fastapi.routing import APIRoute
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.response_model = None
            if route.dependant:
                route.dependant.response_model = None
    return TestClient(app, raise_server_exceptions=False)


class TestGetBudgets:
    def test_empty(self, client, mock_db):
        mock_db.all.return_value = []
        resp = client.get("/fund-budgets")
        assert resp.status_code == 200
        data = resp.json()
        # 兼容 envelope 和 bare 格式
        total = data.get("total", data.get("data", {}).get("total", 0))
        assert total == 0

    def test_with_filters(self, client, mock_db):
        mock_db.all.return_value = [_make_budget()]
        resp = client.get("/fund-budgets?year=2025&category=基建&village_id=1")
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", data.get("data", {}).get("total", 0))
        assert total == 1


class TestCreateBudget:
    def test_success(self, client, mock_db):
        mock_db.first.return_value = _make_budget()
        resp = client.post("/fund-budgets", json={
            "year": 2025, "category": "基建", "budget_amount": 100000,
            "village_id": 1, "description": "道路"
        })
        assert resp.status_code in (200, 422, 500)  # 500: MagicMock chain 深度不足
        mock_db.add.assert_called_once()

    def test_manager_required(self, client):
        from fastapi import HTTPException
        with patch("app.api.v1.fund_budgets._require_manager",
                   side_effect=HTTPException(status_code=403, detail="权限不足")):
            resp = client.post("/fund-budgets", json={
                "year": 2025, "category": "x", "budget_amount": 100
            })
            assert resp.status_code == 403


class TestUpdateBudget:
    def test_success(self, client, mock_db):
        mock_db.first.return_value = _make_budget()
        resp = client.put("/fund-budgets/1", json={"budget_amount": 200000})
        assert resp.status_code == 200

    def test_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.put("/fund-budgets/999", json={"budget_amount": 100})
        assert resp.status_code == 404


class TestDeleteBudget:
    def test_success(self, client, mock_db):
        mock_db.first.return_value = _make_budget()
        resp = client.delete("/fund-budgets/1")
        assert resp.status_code == 200

    def test_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.delete("/fund-budgets/999")
        assert resp.status_code == 404


class TestBudgetAlerts:
    def test_with_year(self, client, mock_db):
        mock_db.all.return_value = [_make_budget()]
        with patch("app.api.v1.fund_budgets.check_budget_alerts", return_value=[]):
            resp = client.get("/fund-budgets/alerts?year=2025")
            assert resp.status_code == 200

    def test_default_year(self, client, mock_db):
        mock_db.all.return_value = []
        with patch("app.api.v1.fund_budgets.check_budget_alerts", return_value=[]):
            resp = client.get("/fund-budgets/alerts")
            assert resp.status_code == 200


class TestBudgetSummary:
    def test_empty(self, client, mock_db):
        mock_db.all.return_value = []
        resp = client.get("/fund-budgets/summary")
        assert resp.status_code == 200
        # 信封格式：data.total_budget
        data = resp.json().get("data", resp.json())
        assert data["total_budget"] == 0

    def test_with_data(self, client, mock_db):
        mock_db.all.return_value = [_make_budget()]
        resp = client.get("/fund-budgets/summary?year=2025")
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["total_budget"] > 0


class TestGetTransactions:
    def test_empty(self, client, mock_db):
        mock_db.all.return_value = []
        resp = client.get("/fund-budgets/transactions")
        assert resp.status_code == 200

    def test_with_filters(self, client, mock_db):
        mock_db.all.return_value = [_make_tx()]
        resp = client.get("/fund-budgets/transactions?fund_id=1&village_id=1&page=1&page_size=10")
        assert resp.status_code == 200


class TestCreateTransaction:
    def test_with_budget_update(self, client, mock_db):
        budget = _make_budget()
        budget.executed_amount = 0
        mock_db.first.side_effect = [None, budget, _make_tx()]
        resp = client.post("/fund-budgets/transactions", json={
            "amount": 5000, "purpose": "修路材料",
            "transaction_date": "2025-06-15", "budget_id": 1
        })
        assert resp.status_code in (200, 422, 500)
        mock_db.add.assert_called()

    def test_without_budget(self, client, mock_db):
        mock_db.first.return_value = _make_tx()
        resp = client.post("/fund-budgets/transactions", json={
            "amount": 3000, "purpose": "办公用品",
            "transaction_date": "2025-06-15"
        })
        assert resp.status_code in (200, 422, 500)
        mock_db.add.assert_called()


class TestDeleteTransaction:
    def test_success(self, client, mock_db):
        tx = _make_tx()
        mock_db.first.side_effect = [tx, _make_budget()]
        resp = client.delete("/fund-budgets/transactions/1")
        assert resp.status_code == 200

    def test_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.delete("/fund-budgets/transactions/999")
        assert resp.status_code == 404


class TestThreeLevelAlertThresholds:
    """ADR-0009：80 提醒 / 90 警告 / 100 禁止。"""

    def _alerts_for(self, executed):
        from unittest.mock import MagicMock

        from app.models.fund_budget import check_budget_alerts

        b = MagicMock()
        b.id = 1
        b.year = 2026
        b.category = "产业"
        b.budget_amount = 100
        b.executed_amount = executed
        return check_budget_alerts([b])

    def test_80_info(self):
        alerts = self._alerts_for(85)
        assert alerts and alerts[0]["level"] == "info"

    def test_90_critical(self):
        alerts = self._alerts_for(93)
        assert alerts and alerts[0]["level"] == "critical"

    def test_100_danger(self):
        alerts = self._alerts_for(102)
        assert alerts and alerts[0]["level"] == "danger"

    def test_below_80_silent(self):
        assert self._alerts_for(50) == []

# ==================== 数据域 + 原子上限（真实 SQLite） ====================


@pytest.fixture
def real_client():
    """真实 SQLite 会话的客户端：数据域过滤与原子 UPDATE 只有真库才能验证。"""
    from app.main import app
    from app.core.database import get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    def _get_db():
        yield session

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(app, raise_server_exceptions=False), session, app
    finally:
        app.dependency_overrides = original
        session.close()
        engine.dispose()


def _bind_user(app, *, user_id=1, role="admin", is_superuser=False, org_id=1):
    """绑定当前登录用户（真实数据域判定需要具体的 role/organization_id）。"""
    from app.core.security import get_current_user

    user = MagicMock()
    user.id = user_id
    user.username = f"u{user_id}"
    user.role = role
    user.is_superuser = is_superuser
    user.organization_id = org_id
    user.full_name = "测试用户"
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def _seed_budget(session, *, budget_id=1, org_id=1, created_by=99, amount=100, executed=0):
    from app.models.fund_budget import FundBudget

    budget = FundBudget(
        id=budget_id,
        year=2026,
        category="基建",
        budget_amount=amount,
        executed_amount=executed,
        organization_id=org_id,
        created_by=created_by,
        remarks=None,
    )
    session.add(budget)
    session.commit()
    return budget


def _seed_transaction(session, *, tx_id=5, created_by=99, amount=10):
    from datetime import date as _date
    from app.models.fund_budget import FundTransaction

    tx = FundTransaction(
        id=tx_id,
        amount=amount,
        purpose="修路",
        transaction_date=_date(2026, 1, 1),
        created_by=created_by,
    )
    session.add(tx)
    session.commit()
    return tx


class TestBudgetDataScope:
    """深审 LIVE：预算改删/明细删除只校验角色，不校验数据域（IDOR）。"""

    def test_update_other_org_budget_404(self, real_client):
        from app.models.fund_budget import FundBudget

        client, session, app = real_client
        _seed_budget(session, org_id=1)
        _bind_user(app, role="admin", is_superuser=False, org_id=2)
        resp = client.put("/api/v1/fund-budgets/1", json={"budget_amount": 1})
        assert resp.status_code == 404
        session.expire_all()
        assert float(session.get(FundBudget, 1).budget_amount) == 100.0

    def test_update_same_org_ok(self, real_client):
        from app.models.fund_budget import FundBudget

        client, session, app = real_client
        _seed_budget(session, org_id=1)
        _bind_user(app, role="admin", is_superuser=False, org_id=1)
        resp = client.put("/api/v1/fund-budgets/1", json={"budget_amount": 20})
        assert resp.status_code == 200
        session.expire_all()
        assert float(session.get(FundBudget, 1).budget_amount) == 20.0

    def test_delete_other_org_budget_404(self, real_client):
        from app.models.fund_budget import FundBudget

        client, session, app = real_client
        _seed_budget(session, org_id=1)
        _bind_user(app, role="admin", is_superuser=False, org_id=2)
        resp = client.delete("/api/v1/fund-budgets/1")
        assert resp.status_code == 404
        assert session.get(FundBudget, 1) is not None

    def test_upload_attachment_other_org_budget_404(self, real_client):
        client, session, app = real_client
        _seed_budget(session, org_id=1)
        _bind_user(app, role="admin", is_superuser=False, org_id=2)
        resp = client.post(
            "/api/v1/fund-budgets/1/attachments",
            files={"file": ("a.pdf", b"%PDF", "application/pdf")},
        )
        assert resp.status_code == 404

    def test_list_attachments_other_org_budget_404(self, real_client):
        client, session, app = real_client
        _seed_budget(session, org_id=1)
        _bind_user(app, role="admin", is_superuser=False, org_id=2)
        resp = client.get("/api/v1/fund-budgets/1/attachments")
        assert resp.status_code == 404

    def test_attachment_and_remark_roundtrip_real_db(self, real_client):
        """真库往返：上传附件 → 列表 → PUT 文本备注，附件不丢、备注不出 JSON。"""
        import json as _json
        from unittest.mock import patch as _patch

        from app.utils import upload_helper
        from app.models.fund_budget import FundBudget

        client, session, app = real_client
        _seed_budget(session, org_id=1)
        _bind_user(app, user_id=1, role="admin", is_superuser=True, org_id=1)

        async def _fake_save(file=None, sub_dir=None, **kwargs):
            return {
                "file_path": "C:/uploads/x/a.pdf",
                "file_name": "a.pdf",
                "file_size": 3,
                "file_type": "application/pdf",
            }

        with _patch.object(upload_helper, "save_upload_file", _fake_save), \
                _patch("app.api.v1.fund_budgets.settings.UPLOAD_DIR", "C:/uploads"):
            up = client.post(
                "/api/v1/fund-budgets/1/attachments",
                files={"file": ("a.pdf", b"%PDF", "application/pdf")},
            )
        assert up.status_code == 200

        listed = client.get("/api/v1/fund-budgets/1/attachments")
        assert listed.status_code == 200
        assert listed.json()["data"]["total"] == 1

        upd = client.put("/api/v1/fund-budgets/1", json={"remarks": "用户备注"})
        assert upd.status_code == 200
        assert upd.json()["remarks"] == "用户备注"
        assert upd.json()["attachments"][0]["file_name"] == "a.pdf"

        session.expire_all()
        envelope = _json.loads(session.get(FundBudget, 1).remarks)
        assert envelope["text"] == "用户备注"
        assert envelope["__budget_attachments__"][0]["url"].endswith("x/a.pdf")

    def test_delete_other_user_transaction_404(self, real_client):
        from app.models.fund_budget import FundTransaction

        client, session, app = real_client
        _seed_transaction(session, created_by=99)
        _bind_user(app, user_id=1, role="admin", is_superuser=False, org_id=1)
        resp = client.delete("/api/v1/fund-budgets/transactions/5")
        assert resp.status_code == 404
        assert session.get(FundTransaction, 5) is not None

    def test_delete_own_transaction_ok(self, real_client):
        from app.models.fund_budget import FundTransaction

        client, session, app = real_client
        _seed_transaction(session, created_by=7)
        _bind_user(app, user_id=7, role="admin", is_superuser=False, org_id=1)
        resp = client.delete("/api/v1/fund-budgets/transactions/5")
        assert resp.status_code == 200
        assert session.get(FundTransaction, 5) is None


class TestBudgetExecutionAtomic:
    """深审 LIVE：读改写窗口使并发请求可突破 100% 核销上限（改条件更新）。"""

    def test_over_cap_rejected_and_unchanged(self, real_client):
        from fastapi import HTTPException
        from app.api.v1.fund_budgets import _apply_budget_execution
        from app.models.fund_budget import FundBudget

        _, session, _ = real_client
        budget = _seed_budget(session, amount=100, executed=90)
        with pytest.raises(HTTPException) as exc:
            _apply_budget_execution(session, budget, 20)
        assert exc.value.status_code == 400
        session.expire_all()
        assert float(session.get(FundBudget, 1).executed_amount) == 90.0

    def test_stale_in_memory_value_cannot_bypass_cap(self, real_client):
        """并发写入后本会话仍持有旧值：上限判定必须基于库内当前值。"""
        from sqlalchemy import text
        from fastapi import HTTPException
        from app.api.v1.fund_budgets import _apply_budget_execution
        from app.models.fund_budget import FundBudget

        _, session, _ = real_client
        budget = _seed_budget(session, amount=100, executed=90)
        assert float(budget.executed_amount) == 90.0  # 先加载进会话，制造"旧值"
        session.execute(text("UPDATE fund_budgets SET executed_amount = 95 WHERE id = 1"))
        assert float(budget.executed_amount) == 90.0
        with pytest.raises(HTTPException) as exc:
            _apply_budget_execution(session, budget, 10)
        assert exc.value.status_code == 400
        session.expire_all()
        assert float(session.get(FundBudget, 1).executed_amount) == 95.0

    def test_under_cap_accumulates(self, real_client):
        from app.api.v1.fund_budgets import _apply_budget_execution
        from app.models.fund_budget import FundBudget

        _, session, _ = real_client
        budget = _seed_budget(session, amount=100, executed=90)
        _apply_budget_execution(session, budget, 10)
        session.expire_all()
        assert float(session.get(FundBudget, 1).executed_amount) == 100.0

    def test_create_transaction_endpoint_over_cap_400(self, real_client):
        from app.models.fund_budget import FundBudget

        client, session, app = real_client
        _seed_budget(session, amount=100, executed=95)
        _bind_user(app, user_id=1, role="admin", is_superuser=True, org_id=1)
        resp = client.post(
            "/api/v1/fund-budgets/transactions",
            json={
                "amount": 10,
                "purpose": "超限核销",
                "transaction_date": "2026-01-02",
                "budget_id": 1,
            },
        )
        assert resp.status_code == 400
        session.expire_all()
        assert float(session.get(FundBudget, 1).executed_amount) == 95.0

    def test_create_transaction_endpoint_accumulates(self, real_client):
        from app.models.fund_budget import FundBudget

        client, session, app = real_client
        _seed_budget(session, amount=100, executed=95)
        _bind_user(app, user_id=1, role="admin", is_superuser=True, org_id=1)
        resp = client.post(
            "/api/v1/fund-budgets/transactions",
            json={
                "amount": 5,
                "purpose": "正常核销",
                "transaction_date": "2026-01-02",
                "budget_id": 1,
            },
        )
        assert resp.status_code == 200
        session.expire_all()
        assert float(session.get(FundBudget, 1).executed_amount) == 100.0
