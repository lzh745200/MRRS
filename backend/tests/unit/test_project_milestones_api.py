"""Tests for app.api.v1.project_milestones — 9 endpoints.

本测试对齐生产 API 契约（见 app/api/v1/project_milestones.py）：
- POST /projects/{id}/milestones        → MilestoneResponse
- POST /projects/{id}/transition        → StatusTransitionResponse(valid, new_status, ...)
  字段名: new_status / reason（非 target_status / comment）
  校验失败时返回 200 + {valid: False, error}（非 HTTP 400）
- GET  /projects/{id}/transition-rules  → TransitionRulesResponse
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date, datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def mock_db():
    s = MagicMock()
    # 让链式查询调用全部返回同一个 mock，简化设置
    s.query.return_value = s
    s.filter.return_value = s
    s.join.return_value = s
    s.order_by.return_value = s
    s.offset.return_value = s
    s.limit.return_value = s
    s.all.return_value = []
    s.first.return_value = None
    return s


def _make_milestone():
    m = MagicMock()
    m.id = 1; m.project_id = 1; m.name = "基础施工"; m.description = "地基"
    m.planned_date = date(2025, 6, 1); m.actual_date = None
    m.responsible_person = "张三"; m.status = "pending"; m.sort_order = 1
    return m


def _make_project():
    p = MagicMock()
    p.id = 1; p.project_name = "道路工程"; p.name = "道路工程"
    p.status = "in_progress"
    return p


@pytest.fixture
def client(mock_db):
    from app.api.v1 import deps
    app = FastAPI()
    user = MagicMock()
    user.id = 1; user.username = "admin"
    app.dependency_overrides[deps.get_current_user] = lambda: user
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    from app.api.v1.project_milestones import router
    app.include_router(router)
    return TestClient(app)


def _patch_refresh(mock_db, **fields):
    """模拟真实 DB refresh：refresh 后给 ORM 实例回填字段（id、status 等）。

    生产环境 db.refresh(milestone) 会回填自增 id 和默认 status，
    mock 环境下需要显式设置以使响应序列化（MilestoneResponse 要求
    id:int、status:str 非空）通过。
    """

    def _refresh(instance, *args, **kwargs):
        for key, value in fields.items():
            setattr(instance, key, value)

    mock_db.refresh.side_effect = _refresh


class TestGetMilestones:
    def test_empty(self, client, mock_db):
        mock_db.all.return_value = []
        resp = client.get("/projects/1/milestones")
        assert resp.status_code == 200

    def test_with_data(self, client, mock_db):
        mock_db.all.return_value = [_make_milestone()]
        resp = client.get("/projects/1/milestones")
        assert resp.status_code == 200


class TestCreateMilestone:
    def test_success(self, client, mock_db):
        # 项目存在；refresh 回填新里程碑的 id 与 status，使响应序列化成功
        mock_db.first.return_value = _make_project()
        _patch_refresh(mock_db, id=1, status="pending")
        resp = client.post("/projects/1/milestones", json={
            "name": "新里程碑", "planned_date": "2025-12-31",
            "responsible_person": "李四", "sort_order": 2
        })
        assert resp.status_code == 200
        # 里程碑写入 + write_work_log 均会 db.add，断言至少调用
        mock_db.add.assert_called()

    def test_project_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.post("/projects/1/milestones", json={
            "name": "里程碑", "planned_date": "2025-12-31"
        })
        assert resp.status_code == 404


class TestUpdateMilestone:
    def test_success(self, client, mock_db):
        milestone = _make_milestone()
        mock_db.first.return_value = milestone
        _patch_refresh(mock_db, id=1, status="pending")
        resp = client.put("/projects/1/milestones/1", json={"name": "更新名称"})
        assert resp.status_code == 200

    def test_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.put("/projects/1/milestones/999", json={"name": "更新"})
        assert resp.status_code == 404


class TestDeleteMilestone:
    def test_success(self, client, mock_db):
        mock_db.first.return_value = _make_milestone()
        resp = client.delete("/projects/1/milestones/1")
        assert resp.status_code == 200

    def test_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.delete("/projects/1/milestones/999")
        assert resp.status_code == 404


class TestGetTransitionRules:
    def test_returns_rules(self, client, mock_db):
        mock_db.first.return_value = _make_project()
        resp = client.get("/projects/1/transition-rules")
        assert resp.status_code == 200

    def test_project_not_found(self, client, mock_db):
        mock_db.first.return_value = None
        resp = client.get("/projects/1/transition-rules")
        assert resp.status_code == 404


class TestTransitionStatus:
    def test_success(self, client, mock_db):
        # 项目存在 + 校验通过 → 记录变更日志并返回 valid=True
        mock_db.first.return_value = _make_project()
        with patch(
            "app.api.v1.project_milestones.validate_status_transition",
            return_value={"valid": True},
        ):
            resp = client.post("/projects/1/transition", json={
                "new_status": "completed", "reason": "完成"
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["new_status"] == "completed"
        mock_db.add.assert_called()  # 应添加变更日志

    def test_project_not_found(self, client, mock_db):
        # 项目不存在 → 404
        mock_db.first.return_value = None
        resp = client.post("/projects/1/transition", json={
            "new_status": "completed"
        })
        assert resp.status_code == 404

    def test_invalid_transition(self, client, mock_db):
        # 校验失败 → 返回 200 + {valid: False, error}（生产契约）
        mock_db.first.return_value = _make_project()
        with patch(
            "app.api.v1.project_milestones.validate_status_transition",
            return_value={"valid": False, "error": "无效转换", "missing_fields": []},
        ):
            resp = client.post("/projects/1/transition", json={
                "new_status": "invalid"
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert body["error"] == "无效转换"


class TestGetChangeLogs:
    def test_empty(self, client, mock_db):
        mock_db.first.return_value = _make_project()
        mock_db.all.return_value = []
        resp = client.get("/projects/1/change-logs")
        assert resp.status_code == 200

    def test_with_data(self, client, mock_db):
        mock_db.first.return_value = _make_project()
        log = MagicMock()
        log.id = 1; log.project_id = 1; log.field_name = "status"
        log.old_value = "pending"; log.new_value = "completed"
        log.change_type = "status"; log.reason = ""
        log.operator = "admin"; log.created_at = datetime(2025, 6, 1)
        mock_db.all.return_value = [log]
        resp = client.get("/projects/1/change-logs")
        assert resp.status_code == 200


class TestUpcomingMilestones:
    def test_empty(self, client, mock_db):
        mock_db.all.return_value = []
        resp = client.get("/projects/dashboard/upcoming-milestones")
        assert resp.status_code == 200

    def test_with_data(self, client, mock_db):
        mock_db.all.return_value = [_make_milestone()]
        resp = client.get("/projects/dashboard/upcoming-milestones?days=30")
        assert resp.status_code == 200


class TestOverdueMilestones:
    def test_empty(self, client, mock_db):
        mock_db.all.return_value = []
        resp = client.get("/projects/dashboard/overdue-milestones")
        assert resp.status_code == 200

    def test_with_data(self, client, mock_db):
        m = _make_milestone()
        m.planned_date = date(2020, 1, 1)  # Very overdue
        mock_db.all.return_value = [m]
        resp = client.get("/projects/dashboard/overdue-milestones")
        assert resp.status_code == 200
