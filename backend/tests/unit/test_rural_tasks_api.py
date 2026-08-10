"""
Comprehensive tests for app/api/v1/rural_tasks.py — all 10 endpoints, full branch coverage.

Covers:
  GET  /rural-tasks              — paginated list with filters
  GET  /rural-tasks/statistics   — aggregated stats
  GET  /rural-tasks/{task_id}    — get single (includes 404)
  POST /rural-tasks              — create (includes work-not-found 404)
  PUT  /rural-tasks/{task_id}    — update (includes 404)
  DELETE /rural-tasks/{task_id}  — delete (includes 404)
  POST /rural-tasks/{task_id}/submit  — submit for approval (includes 400)
  POST /rural-tasks/{task_id}/approve — approve/reject (includes 400)
  POST /rural-tasks/batch-delete — bulk delete (includes empty list)
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.rural_task import TaskCategory, TaskPriority, TaskStatus


# ---------------------------------------------------------------------------
# Disable camel-to-snake middleware so mock to_dict() keys pass through as-is
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch(
        "app.middleware.camel_to_snake._convert_keys",
        side_effect=lambda obj, converter: (obj, False),
    ):
        yield


# ============================================================================
# Mock-object factories
# ============================================================================

def _make_mock_task(
    id_=1,
    title="测试任务",
    code="TASK-2025-001",
    rural_work_id=1,
    status=TaskStatus.draft,
    category=TaskCategory.other,
    priority=TaskPriority.medium,
    year=2025,
    quarter=None,
    description="描述",
    target="目标",
    result=None,
    budget=100.0,
    actual_cost=50.0,
    progress=0,
    responsible_unit="帮扶单位",
    responsible_person="张三",
    contact_phone="13800138000",
    planned_start=None,
    planned_end=None,
    actual_start=None,
    actual_end=None,
    submitted_by=None,
    submitted_at=None,
    approved_by=None,
    approved_at=None,
    approval_comment=None,
    village_id=None,
    village_name="测试村",
    rural_work_name="测试乡村工作",
    created_by=1,
    created_at=None,
    updated_at=None,
    attachments=None,
):
    """Build a MagicMock that quacks like a RuralTask ORM instance."""
    t = MagicMock()
    t.id = id_
    t.title = title
    t.code = code
    t.rural_work_id = rural_work_id
    t.status = status
    t.category = category
    t.priority = priority
    t.year = year
    t.quarter = quarter
    t.description = description
    t.target = target
    t.result = result
    t.budget = budget
    t.actual_cost = actual_cost
    t.progress = progress
    t.responsible_unit = responsible_unit
    t.responsible_person = responsible_person
    t.contact_phone = contact_phone
    t.planned_start = planned_start
    t.planned_end = planned_end
    t.actual_start = actual_start
    t.actual_end = actual_end
    t.submitted_by = submitted_by
    t.submitted_at = submitted_at
    t.approved_by = approved_by
    t.approved_at = approved_at
    t.approval_comment = approval_comment
    t.village_id = village_id
    t.created_by = created_by
    t.created_at = created_at
    t.updated_at = updated_at
    t.attachments = attachments

    # Relationships
    mock_village = MagicMock()
    mock_village.name = village_name
    t.village = mock_village

    mock_work = MagicMock()
    mock_work.name = rural_work_name
    t.rural_work = mock_work

    # to_dict() returns a snake_case dict (matching Base.to_dict / _base_to_dict)
    def _to_dict():
        return {
            "id": t.id,
            "title": t.title,
            "code": t.code,
            "rural_work_id": t.rural_work_id,
            "status": t.status.value if isinstance(t.status, TaskStatus) else t.status,
            "category": t.category.value if isinstance(t.category, TaskCategory) else t.category,
            "priority": t.priority.value if isinstance(t.priority, TaskPriority) else t.priority,
            "year": t.year,
            "quarter": t.quarter,
            "description": t.description,
            "target": t.target,
            "result": t.result,
            "budget": t.budget,
            "actual_cost": t.actual_cost,
            "progress": t.progress,
            "responsible_unit": t.responsible_unit,
            "responsible_person": t.responsible_person,
            "contact_phone": t.contact_phone,
            "planned_start": t.planned_start,
            "planned_end": t.planned_end,
            "actual_start": t.actual_start,
            "actual_end": t.actual_end,
            "submitted_by": t.submitted_by,
            "submitted_at": t.submitted_at,
            "approved_by": t.approved_by,
            "approved_at": t.approved_at,
            "approval_comment": t.approval_comment,
            "village_id": t.village_id,
            "created_by": t.created_by,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }

    t.to_dict = _to_dict
    return t


def _make_mock_work(id_=1, name="测试乡村工作"):
    """Build a MagicMock that quacks like a RuralWork ORM instance."""
    w = MagicMock()
    w.id = id_
    w.name = name
    return w


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Simulated DB session with chainable query mock.

    Every query() returns the same ``q`` mock, and every chain method
    (filter, order_by, offset, limit, …) returns ``q`` so all paths
    converge on a single configurable object.
    """
    db = MagicMock()
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.first.return_value = None
    q.distinct.return_value = q
    q.delete.return_value = 0
    db.query.return_value = q
    db.add.return_value = None
    db.flush.return_value = None
    db.refresh.return_value = None
    db.commit.return_value = None
    db.rollback.return_value = None
    db.delete.return_value = None
    return db


@pytest.fixture
def admin_user():
    """Simulated authenticated admin user."""
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.organization_id = 1
    u.is_active = True
    u.full_name = "管理员"
    return u


@pytest.fixture
def client(mock_db, admin_user):
    """TestClient with get_db and get_current_user overridden."""
    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original_overrides


# ============================================================================
# GET /rural-tasks  —  paginated list
# ============================================================================

class TestListTasks:
    """Tests for GET /rural-tasks"""

    def test_default_pagination(self, client, mock_db):
        """Returns first page with default skip=0, limit=10."""
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_task(1)]
        resp = client.get("/api/v1/rural-tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["skip"] == 0
        assert data["limit"] == 10

    def test_empty_list(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 0
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_custom_pagination(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 50
        q.all.return_value = [_make_mock_task(i) for i in range(1, 6)]
        resp = client.get("/api/v1/rural-tasks?skip=10&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skip"] == 10
        assert data["limit"] == 5
        assert data["total"] == 50

    # -- filter parameters --------------------------------------------------

    def test_filter_rural_work_id(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 0
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks?rural_work_id=3")
        assert resp.status_code == 200

    def test_filter_status(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_task(1, status=TaskStatus.completed)]
        resp = client.get("/api/v1/rural-tasks?status=completed")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_category(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 0
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks?category=industry")
        assert resp.status_code == 200

    def test_filter_year(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 0
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks?year=2025")
        assert resp.status_code == 200

    def test_filter_village_id(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 0
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks?village_id=1")
        assert resp.status_code == 200

    def test_filter_search(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_task(1, title="道路硬化")]
        resp = client.get("/api/v1/rural-tasks?search=道路")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_order_by_asc(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 2
        q.all.return_value = [
            _make_mock_task(1, title="A"),
            _make_mock_task(2, title="B"),
        ]
        resp = client.get("/api/v1/rural-tasks?order_by=title&order_desc=false")
        assert resp.status_code == 200

    def test_items_include_village_and_work_names(self, client, mock_db):
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [_make_mock_task(1, village_name="红花村", rural_work_name="产业帮扶")]
        resp = client.get("/api/v1/rural-tasks")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["village_name"] == "红花村"
        assert item["rural_work_name"] == "产业帮扶"

    def test_items_null_relationships(self, client, mock_db):
        """When village/rural_work are None, names should be None."""
        t = _make_mock_task(1)
        t.village = None
        t.rural_work = None
        q = mock_db.query.return_value
        q.count.return_value = 1
        q.all.return_value = [t]
        resp = client.get("/api/v1/rural-tasks")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["village_name"] is None
        assert item["rural_work_name"] is None


# ============================================================================
# GET /rural-tasks/statistics  —  aggregated stats
# ============================================================================

class TestGetStatistics:
    """Tests for GET /rural-tasks/statistics"""

    def test_empty(self, client, mock_db):
        q = mock_db.query.return_value
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 0
        assert data["data"]["completion_rate"] == 0

    def test_mixed_statuses(self, client, mock_db):
        tasks = [
            _make_mock_task(1, status=TaskStatus.draft, category=TaskCategory.infrastructure, budget=10, actual_cost=5),
            _make_mock_task(2, status=TaskStatus.completed, category=TaskCategory.industry, budget=20, actual_cost=18),
            _make_mock_task(3, status=TaskStatus.completed, category=TaskCategory.infrastructure, budget=30, actual_cost=30),
            _make_mock_task(4, status=TaskStatus.in_progress, category=TaskCategory.education, budget=5, actual_cost=2),
            _make_mock_task(5, status=TaskStatus.pending_approval, category=TaskCategory.other, budget=0, actual_cost=0),
        ]
        q = mock_db.query.return_value
        q.all.return_value = tasks
        resp = client.get("/api/v1/rural-tasks/statistics")
        assert resp.status_code == 200
        s = resp.json()["data"]
        assert s["total"] == 5
        assert s["draft"] == 1
        assert s["completed"] == 2
        assert s["in_progress"] == 1
        assert s["pending_approval"] == 1
        assert s["rejected"] == 0
        assert s["total_budget"] == 65.0
        assert s["total_actual_cost"] == 55.0
        assert s["completion_rate"] == 40.0  # 2/5 * 100
        assert "infrastructure" in s["by_category"]
        assert s["by_category"]["infrastructure"] == 2
        assert s["by_category"]["industry"] == 1

    def test_with_year_filter(self, client, mock_db):
        q = mock_db.query.return_value
        q.all.return_value = [_make_mock_task(1, year=2024)]
        resp = client.get("/api/v1/rural-tasks/statistics?year=2024")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_with_rural_work_id_filter(self, client, mock_db):
        q = mock_db.query.return_value
        q.all.return_value = []
        resp = client.get("/api/v1/rural-tasks/statistics?rural_work_id=99")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_completion_rate_rounding(self, client, mock_db):
        """2/3 = 66.666... → round to 66.7"""
        tasks = [
            _make_mock_task(1, status=TaskStatus.completed, budget=0, actual_cost=0),
            _make_mock_task(2, status=TaskStatus.completed, budget=0, actual_cost=0),
            _make_mock_task(3, status=TaskStatus.draft, budget=0, actual_cost=0),
        ]
        q = mock_db.query.return_value
        q.all.return_value = tasks
        resp = client.get("/api/v1/rural-tasks/statistics")
        assert resp.json()["data"]["completion_rate"] == 66.7

    def test_rejected_counted(self, client, mock_db):
        tasks = [_make_mock_task(1, status=TaskStatus.rejected, budget=0, actual_cost=0)]
        q = mock_db.query.return_value
        q.all.return_value = tasks
        resp = client.get("/api/v1/rural-tasks/statistics")
        assert resp.json()["data"]["rejected"] == 1


# ============================================================================
# GET /rural-tasks/{task_id}  —  get single
# ============================================================================

class TestGetTask:
    """Tests for GET /rural-tasks/{task_id}"""

    def test_found(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(42, title="找到的任务")
        resp = client.get("/api/v1/rural-tasks/42")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["id"] == 42
        assert data["data"]["title"] == "找到的任务"

    def test_not_found(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client.get("/api/v1/rural-tasks/999")
        assert resp.status_code == 404
        assert "任务不存在" in resp.json()["detail"]


# ============================================================================
# POST /rural-tasks  —  create
# ============================================================================

class TestCreateTask:
    """Tests for POST /rural-tasks"""

    VALID_PAYLOAD = {
        "rural_work_id": 1,
        "title": "新建道路硬化任务",
        "category": "infrastructure",
        "priority": "high",
        "year": 2025,
        "quarter": 2,
        "description": "硬化村主干道",
        "target": "完成2公里道路",
        "budget": 50.0,
        "responsible_unit": "某部队",
        "responsible_person": "李四",
        "contact_phone": "13900139000",
        "village_id": 1,
    }

    def test_create_success_with_year(self, client, mock_db):
        """Create with explicit year → generates code TASK-2025-NNN."""
        q = mock_db.query.return_value
        # First .first() → check RuralWork exists; second .first() → _generate_code
        q.first.side_effect = [_make_mock_work(1), None]
        q.all.return_value = []
        q.count.return_value = 0

        resp = client.post("/api/v1/rural-tasks", json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["message"] == "创建成功"
        assert data["data"]["title"] == "新建道路硬化任务"
        assert data["data"]["status"] == "draft"
        assert data["data"]["code"] == "TASK-2025-001"

    def test_create_success_without_year(self, client, mock_db):
        """year omitted → uses datetime.now().year."""
        q = mock_db.query.return_value
        q.first.side_effect = [_make_mock_work(1), None]
        payload = {**self.VALID_PAYLOAD}
        del payload["year"]
        resp = client.post("/api/v1/rural-tasks", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        # Code prefix uses current year
        assert data["data"]["code"].startswith("TASK-")

    def test_create_work_not_found(self, client, mock_db):
        """RuralWork does not exist → 404."""
        q = mock_db.query.return_value
        q.first.return_value = None  # work not found
        resp = client.post("/api/v1/rural-tasks", json=self.VALID_PAYLOAD)
        assert resp.status_code == 404
        assert "关联的乡村工作不存在" in resp.json()["detail"]

    def test_create_generates_code_sequence(self, client, mock_db):
        """Last code TASK-2025-005 → new code TASK-2025-006."""
        prev = _make_mock_task(1, code="TASK-2025-005")
        # Restore .first.side_effect in case fixture teardown already cleared
        q = mock_db.query.return_value
        q.first.side_effect = [_make_mock_work(1), prev]
        resp = client.post("/api/v1/rural-tasks", json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["data"]["code"] == "TASK-2025-006"

    def test_create_code_with_non_numeric_suffix(self, client, mock_db):
        """Last code has non-numeric suffix → ValueError caught → num=1."""
        prev = _make_mock_task(1, code="TASK-2025-ABC")
        q = mock_db.query.return_value
        q.first.side_effect = [_make_mock_work(1), prev]
        resp = client.post("/api/v1/rural-tasks", json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["data"]["code"] == "TASK-2025-001"

    def test_create_code_with_none_code(self, client, mock_db):
        """Last task has code=None → num=1."""
        prev = _make_mock_task(1, code=None)
        q = mock_db.query.return_value
        q.first.side_effect = [_make_mock_work(1), prev]
        resp = client.post("/api/v1/rural-tasks", json=self.VALID_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["data"]["code"] == "TASK-2025-001"

    def test_create_defaults_budget_to_zero(self, client, mock_db):
        """budget omitted → defaults to 0.0."""
        q = mock_db.query.return_value
        q.first.side_effect = [_make_mock_work(1), None]
        payload = {
            "rural_work_id": 1,
            "title": "无预算任务",
        }
        resp = client.post("/api/v1/rural-tasks", json=payload)
        assert resp.status_code == 200
        assert resp.json()["data"]["budget"] == 0.0


# ============================================================================
# PUT /rural-tasks/{task_id}  —  update
# ============================================================================

class TestUpdateTask:
    """Tests for PUT /rural-tasks/{task_id}"""

    def test_update_success(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, title="原始标题")
        resp = client.put("/api/v1/rural-tasks/1", json={"title": "修改后的标题"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["message"] == "更新成功"
        assert data["data"]["title"] == "修改后的标题"

    def test_update_not_found(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client.put("/api/v1/rural-tasks/999", json={"title": "不存在"})
        assert resp.status_code == 404
        assert "任务不存在" in resp.json()["detail"]

    def test_update_multiple_fields(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, title="旧", description="旧描述", budget=10)
        resp = client.put(
            "/api/v1/rural-tasks/1",
            json={
                "title": "新标题",
                "description": "新描述",
                "budget": 200.0,
                "progress": 50,
                "status": "in_progress",
            },
        )
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["title"] == "新标题"
        assert d["description"] == "新描述"
        assert d["budget"] == 200.0
        assert d["progress"] == 50
        assert d["status"] == "in_progress"

    def test_update_ignores_unset(self, client, mock_db):
        """exclude_unset=True → only sent fields are written."""
        q = mock_db.query.return_value
        original = _make_mock_task(1, title="旧标题", description="旧描述")
        q.first.return_value = original
        resp = client.put("/api/v1/rural-tasks/1", json={"title": "新标题"})
        assert resp.status_code == 200
        # description should be unchanged
        assert resp.json()["data"]["description"] == "旧描述"


# ============================================================================
# DELETE /rural-tasks/{task_id}  —  delete
# ============================================================================

class TestDeleteTask:
    """Tests for DELETE /rural-tasks/{task_id}"""

    def test_delete_success(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1)
        resp = client.delete("/api/v1/rural-tasks/1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "删除成功"

    def test_delete_not_found(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client.delete("/api/v1/rural-tasks/999")
        assert resp.status_code == 404
        assert "任务不存在" in resp.json()["detail"]


# ============================================================================
# POST /rural-tasks/{task_id}/submit  —  submit for approval
# ============================================================================

class TestSubmitTask:
    """Tests for POST /rural-tasks/{task_id}/submit"""

    def test_submit_from_draft(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.draft)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 200
        assert resp.json()["message"] == "提交成功"

    def test_submit_from_rejected(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.rejected)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 200
        assert resp.json()["message"] == "提交成功"

    def test_submit_not_found(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client.post("/api/v1/rural-tasks/999/submit")
        assert resp.status_code == 404
        assert "任务不存在" in resp.json()["detail"]

    def test_submit_invalid_status_pending(self, client, mock_db):
        """Already pending → 400."""
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.pending_approval)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 400
        assert "仅草稿或被驳回" in resp.json()["detail"]

    def test_submit_invalid_status_approved(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.approved)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 400

    def test_submit_invalid_status_in_progress(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.in_progress)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 400

    def test_submit_invalid_status_completed(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.completed)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 400

    def test_submit_invalid_status_cancelled(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.cancelled)
        resp = client.post("/api/v1/rural-tasks/1/submit")
        assert resp.status_code == 400

    def test_submit_with_comment(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.draft)
        resp = client.post("/api/v1/rural-tasks/1/submit", json={"comment": "请审批"})
        assert resp.status_code == 200


# ============================================================================
# POST /rural-tasks/{task_id}/approve  —  approve / reject
# ============================================================================

class TestApproveTask:
    """Tests for POST /rural-tasks/{task_id}/approve"""

    def test_approve_success(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.pending_approval)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True, "comment": "同意"},
        )
        assert resp.status_code == 200
        assert "已批准" in resp.json()["message"]

    def test_reject_success(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.pending_approval)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": False, "comment": "需要修改"},
        )
        assert resp.status_code == 200
        assert "已驳回" in resp.json()["message"]

    def test_approve_not_found(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = None
        resp = client.post(
            "/api/v1/rural-tasks/999/approve",
            json={"approved": True},
        )
        assert resp.status_code == 404
        assert "任务不存在" in resp.json()["detail"]

    def test_approve_invalid_status_draft(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.draft)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 400
        assert "仅待审批" in resp.json()["detail"]

    def test_approve_invalid_status_approved(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.approved)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 400

    def test_approve_invalid_status_rejected(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.rejected)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 400

    def test_approve_invalid_status_in_progress(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.in_progress)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 400

    def test_approve_invalid_status_completed(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.completed)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 400

    def test_approve_invalid_status_cancelled(self, client, mock_db):
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.cancelled)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 400

    def test_approve_without_comment(self, client, mock_db):
        """comment is optional in TaskApproveRequest."""
        q = mock_db.query.return_value
        q.first.return_value = _make_mock_task(1, status=TaskStatus.pending_approval)
        resp = client.post(
            "/api/v1/rural-tasks/1/approve",
            json={"approved": True},
        )
        assert resp.status_code == 200

    def test_approve_missing_approved_field(self, client, mock_db):
        """approved is required — FastAPI validation should fail."""
        resp = client.post("/api/v1/rural-tasks/1/approve", json={})
        assert resp.status_code == 422  # Validation error


# ============================================================================
# POST /rural-tasks/batch-delete  —  bulk delete
# ============================================================================

class TestBatchDelete:
    """Tests for POST /rural-tasks/batch-delete"""

    def test_batch_delete_success(self, client, mock_db):
        q = mock_db.query.return_value
        q.delete.return_value = 3
        resp = client.post("/api/v1/rural-tasks/batch-delete", json=[1, 2, 3])
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["deleted"] == 3
        assert "成功删除3条" in data["message"]

    def test_batch_delete_single(self, client, mock_db):
        q = mock_db.query.return_value
        q.delete.return_value = 1
        resp = client.post("/api/v1/rural-tasks/batch-delete", json=[42])
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] == 1

    def test_batch_delete_empty_list(self, client, mock_db):
        """Empty list → deletes 0 records, returns success."""
        q = mock_db.query.return_value
        q.delete.return_value = 0
        resp = client.post("/api/v1/rural-tasks/batch-delete", json=[])
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["deleted"] == 0
        assert "成功删除0条" in data["message"]

    def test_batch_delete_nonexistent_ids(self, client, mock_db):
        """Nonexistent IDs → delete returns 0, still success."""
        q = mock_db.query.return_value
        q.delete.return_value = 0
        resp = client.post("/api/v1/rural-tasks/batch-delete", json=[9999, 9998])
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] == 0
