"""app/api/v1/fund_budgets.py 附件端点与 used_amount 映射分支覆盖

补齐：create/update 的 used_amount→executed_amount 映射、附件上传/列表、
_record_attachment 追加、_get_attachments 解析（含异常降级）。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.v1 import deps


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


def _make_user(role="manager"):
    u = MagicMock()
    u.id = 1
    u.role = role
    u.is_superuser = False
    u.username = "budget_admin"
    u.full_name = "预算管理员"
    return u


@pytest.fixture
def client(mock_db):
    app = FastAPI()
    user = _make_user()
    app.dependency_overrides[deps.get_current_user] = lambda: user
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    from app.api.v1.fund_budgets import router

    app.include_router(router)
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.response_model = None
            if route.dependant:
                route.dependant.response_model = None
    return TestClient(app, raise_server_exceptions=False)


def _set_db_first(mock_db, value):
    mock_db.first.return_value = value


def _make_existing_budget(remarks=None):
    b = MagicMock()
    b.id = 1
    b.year = 2025
    b.category = "基础设施"
    b.budget_amount = 100000.0
    b.executed_amount = 20000.0
    b.village_id = 1
    b.organization_id = None
    b.description = "d"
    b.remarks = remarks
    b.remaining_amount = 80000.0
    b.execution_rate = 20.0
    b.to_dict.return_value = {
        "id": 1,
        "year": 2025,
        "category": "基础设施",
        "budget_amount": 100000.0,
        "executed_amount": 20000.0,
        "village_id": 1,
        "organization_id": None,
        "description": "d",
        "remarks": remarks,
    }
    return b


class TestUsedAmountMapping:
    def test_create_with_used_amount_maps_to_executed(self, client, mock_db):
        """create：前端字段 used_amount → executed_amount"""
        mock_db.refresh.side_effect = lambda budget: setattr(budget, "id", 7)
        resp = client.post("/fund-budgets", json={
            "year": 2025,
            "category": "基建",
            "budget_amount": 100000,
            "used_amount": 30000,
            "village_id": 1,
        })
        assert resp.status_code == 200
        added = mock_db.add.call_args[0][0]
        assert added.executed_amount == 30000
        assert not hasattr(added, "used_amount")
        assert resp.json()["executed_amount"] == 30000

    def test_create_with_used_amount_none(self, client, mock_db):
        """create：used_amount=None 不覆盖 executed_amount"""
        mock_db.refresh.side_effect = lambda budget: (
            setattr(budget, "id", 8),
            setattr(budget, "executed_amount", getattr(budget, "executed_amount", None) or 0.0),
        )
        resp = client.post("/fund-budgets", json={
            "year": 2025,
            "category": "基建",
            "budget_amount": 100000,
            "used_amount": None,
        })
        assert resp.status_code == 200
        added = mock_db.add.call_args[0][0]
        # used_amount=None 时不写入 executed_amount（refresh 副作用后为 0.0 或保持 None）
        assert added.executed_amount in (None, 0.0)
        assert not hasattr(added, "used_amount")

    def test_update_with_used_amount_maps_to_executed(self, client, mock_db):
        """update：used_amount → executed_amount 映射"""
        budget = _make_existing_budget()
        _set_db_first(mock_db, budget)
        resp = client.put("/fund-budgets/1", json={"used_amount": 45000})
        assert resp.status_code == 200
        assert budget.executed_amount == 45000

    def test_update_with_used_amount_none_skips(self, client, mock_db):
        """update：used_amount=None 跳过映射，不报错"""
        budget = _make_existing_budget()
        _set_db_first(mock_db, budget)
        resp = client.put("/fund-budgets/1", json={"used_amount": None})
        assert resp.status_code == 200
        assert budget.executed_amount == 20000  # 保持不变


class TestBudgetAttachments:
    UPLOAD_INFO = {
        "file_path": "C:/uploads/fund-budgets/1/abc.pdf",
        "file_name": "批复文件.pdf",
        "file_size": 2048,
        "file_type": "application/pdf",
    }

    def test_upload_attachment_success(self, client, mock_db):
        _set_db_first(mock_db, _make_existing_budget(remarks=None))
        with patch("app.utils.upload_helper.save_upload_file", new=pytest_asyncio_wrap(self.UPLOAD_INFO)), \
             patch("app.api.v1.fund_budgets.settings.UPLOAD_DIR", "C:/uploads"):
            resp = client.post(
                "/fund-budgets/1/attachments",
                files={"file": ("批复文件.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["file_name"] == "批复文件.pdf"
        assert "/fund-budgets/1/" in data["url"]
        budget = mock_db.first.return_value
        import json as _json
        attachments = _json.loads(budget.remarks)
        assert attachments[-1]["file_name"] == "批复文件.pdf"
        assert attachments[-1]["uploaded_by"] == "预算管理员"

    def test_upload_attachment_budget_not_found(self, client, mock_db):
        resp = client.post(
            "/fund-budgets/999/attachments",
            files={"file": ("a.pdf", b"%PDF", "application/pdf")},
        )
        assert resp.status_code == 404

    def test_upload_attachment_allowed_for_user(self, mock_db):
        """普通用户（user）可上传经费附件（产品要求：经费全流程对普通用户开放）。"""
        app = FastAPI()
        app.dependency_overrides[deps.get_current_user] = lambda: _make_user(role="user")
        app.dependency_overrides[deps.get_db] = lambda: mock_db
        from app.api.v1.fund_budgets import router

        _set_db_first(mock_db, _make_existing_budget(remarks="[]"))

        app.include_router(router)
        c = TestClient(app, raise_server_exceptions=False)
        with patch("app.utils.upload_helper.save_upload_file", new=pytest_asyncio_wrap(self.UPLOAD_INFO)), \
                patch("app.api.v1.fund_budgets.settings.UPLOAD_DIR", "C:/uploads"):
            resp = c.post(
                "/fund-budgets/1/attachments",
                files={"file": ("a.pdf", b"%PDF", "application/pdf")},
            )
        assert resp.status_code == 200

    def test_list_attachments_with_records(self, client, mock_db):
        remarks = (
            '[{"url": "/uploads/a.pdf", "file_name": "a.pdf", '
            '"uploaded_by": "admin", "created_at": "2026-01-01"}]'
        )
        _set_db_first(mock_db, _make_existing_budget(remarks=remarks))
        resp = client.get("/fund-budgets/1/attachments")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["url"] == "/uploads/a.pdf"

    def test_list_attachments_budget_not_found(self, client, mock_db):
        resp = client.get("/fund-budgets/999/attachments")
        assert resp.status_code == 404

    def test_get_attachments_invalid_json_returns_empty(self):
        from app.api.v1.fund_budgets import _get_attachments

        budget = _make_existing_budget(remarks="{bad json")
        assert _get_attachments(budget) == []

    def test_get_attachments_non_list_returns_empty(self):
        from app.api.v1.fund_budgets import _get_attachments

        budget = _make_existing_budget(remarks='"just a string"')
        assert _get_attachments(budget) == []

    def test_get_attachments_no_remarks_returns_empty(self):
        from app.api.v1.fund_budgets import _get_attachments

        assert _get_attachments(_make_existing_budget(remarks=None)) == []

    def test_get_attachments_filters_non_url_entries(self):
        from app.api.v1.fund_budgets import _get_attachments

        budget = _make_existing_budget(
            remarks='[{"url": "/uploads/ok.pdf"}, {"name": "no-url"}]'
        )
        result = _get_attachments(budget)
        assert len(result) == 1
        assert result[0]["url"] == "/uploads/ok.pdf"


def pytest_asyncio_wrap(value):
    """构造 async 返回值（save_upload_file 是 async 函数）"""

    async def _fake(*args, **kwargs):
        return value

    return _fake
