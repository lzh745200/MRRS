"""
Tests for approval.py — approval workflow management API (19 endpoints).
"""
from unittest.mock import MagicMock, patch
import pytest

BASE = "/api/v1/approval"

# Shared mock helpers


def make_mock_task(task_id=1, status="pending", current_level=1, title="Test", submitter_id=1, current_approver_id=1):
    t = MagicMock()
    t.id = task_id
    t.status = status
    t.current_level = current_level
    t.title = title
    t.submitter_id = submitter_id
    t.entity_type = "village"
    t.entity_id = 1
    t.priority = 0
    t.current_approver_id = current_approver_id
    t.created_at = MagicMock()
    t.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    t.completed_at = MagicMock()
    t.completed_at.isoformat.return_value = "2024-01-02T00:00:00"
    t.submitter = MagicMock()
    t.submitter.username = "admin"
    t.current_approver = MagicMock()
    t.current_approver.username = "approver"
    return t


def make_mock_workflow(wf_id=1, name="TestWF", entity_type="village", level_count=2):
    w = MagicMock()
    w.id = wf_id
    w.name = name
    w.entity_type = entity_type
    w.description = "test"
    w.is_active = True
    w.level_count = level_count
    n = MagicMock()
    n.id = 1
    n.level = 1
    n.name = "Node1"
    n.approver_type = "user"
    n.approver_id = 1
    n.timeout_hours = 24
    w.nodes = [n]
    return w


def make_mock_record(record_id=1):
    r = MagicMock()
    r.id = record_id
    r.task_id = 1
    r.action = "approve"
    r.opinion = "ok"
    r.level = 1
    r.approver = MagicMock()
    r.approver.username = "approver"
    r.task = make_mock_task()
    r.created_at = MagicMock()
    r.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    return r

# ── approval_overview ──────────────────────────────────────────────


class TestApprovalOverview:
    def test_requires_auth(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 401

    def test_overview(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert "pending_count" in data["data"]
        assert "approved_count" in data["data"]
        assert "rejected_count" in data["data"]
        assert "total_count" in data["data"]
        assert "my_pending" in data["data"]


# ── create_workflow ────────────────────────────────────────────────

class TestCreateWorkflow:
    def test_success(self, client_with_mocked_auth):
        wf = make_mock_workflow()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.create_workflow.return_value = wf
            MockSvc.return_value = mock_svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/workflows",
                json={"name": "TestWF", "entity_type": "village", "nodes": [{"name": "N1"}]},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["id"] == wf.id

    def test_value_error(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.create_workflow.side_effect = ValueError("nodes too many")
            MockSvc.return_value = mock_svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/workflows",
                json={"name": "BadWF", "entity_type": "village"},
            )
            assert resp.status_code == 400


# ── list_workflows ─────────────────────────────────────────────────

class TestListWorkflows:
    def test_success(self, client_with_mocked_auth):
        wf = make_mock_workflow()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.list_workflows.return_value = [wf]
            MockSvc.return_value = mock_svc
            resp = client_with_mocked_auth.get(f"{BASE}/workflows")
            assert resp.status_code == 200
            assert len(resp.json()["data"]) == 1

    def test_filter_params(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.list_workflows.return_value = []
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/workflows?entity_type=village&is_active=true")
            assert resp.status_code == 200
            svc.list_workflows.assert_called_with(entity_type="village", is_active=True, skip=0, limit=100)


# ── get_workflow ───────────────────────────────────────────────────

class TestGetWorkflow:
    def test_found(self, client_with_mocked_auth):
        wf = make_mock_workflow()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_workflow.return_value = wf
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/workflows/1")
            assert resp.status_code == 200
            assert resp.json()["data"]["id"] == 1

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_workflow.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/workflows/999")
            assert resp.status_code == 404


# ── update_workflow ────────────────────────────────────────────────

class TestUpdateWorkflow:
    def test_success(self, client_with_mocked_auth):
        wf = make_mock_workflow()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.update_workflow.return_value = wf
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.put(
                f"{BASE}/workflows/1",
                json={"name": "Updated", "is_active": False},
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "更新成功"

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.update_workflow.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.put(
                f"{BASE}/workflows/999", json={"name": "Nope"},
            )
            assert resp.status_code == 404

    def test_value_error(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.update_workflow.side_effect = ValueError("bad")
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.put(
                f"{BASE}/workflows/1", json={"name": "Bad"},
            )
            assert resp.status_code == 400


# ── delete_workflow ────────────────────────────────────────────────

class TestDeleteWorkflow:
    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.delete_workflow.return_value = True
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.delete(f"{BASE}/workflows/1")
            assert resp.status_code == 200
            assert resp.json()["message"] == "删除成功"

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.delete_workflow.return_value = False
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.delete(f"{BASE}/workflows/999")
            assert resp.status_code == 404


# ── submit_approval ────────────────────────────────────────────────

class TestSubmitApproval:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.submit_approval.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/submit",
                json={"entity_type": "village", "entity_id": 1, "change_data": {"name": "New"}},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["task_id"] == 1

    def test_no_workflow(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.submit_approval.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/submit",
                json={"entity_type": "village", "entity_id": 1, "change_data": {"name": "New"}},
            )
            assert resp.status_code == 400


# ── approve_task ──────────────────────────────────────────────────

class TestApproveTask:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task(status="approved")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.approve_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/approve", json={"opinion": "同意"})
            assert resp.status_code == 200
            assert resp.json()["message"] == "审批通过"

    def test_no_permission(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.approve_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/approve", json={})
            assert resp.status_code == 403


# ── reject_task ───────────────────────────────────────────────────

class TestRejectTask:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task(status="rejected")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.reject_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/reject", json={"opinion": "不同意"})
            assert resp.status_code == 200
            assert resp.json()["message"] == "已拒绝"

    def test_no_permission(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.reject_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/reject", json={})
            assert resp.status_code == 403


# ── transfer_task ─────────────────────────────────────────────────

class TestTransferTask:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task(current_approver_id=2)
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.transfer_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/tasks/1/transfer", json={"transfer_to_id": 2},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["current_approver_id"] == 2

    def test_failure(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.transfer_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/tasks/1/transfer", json={"transfer_to_id": 2},
            )
            assert resp.status_code == 400


# ── withdraw_task ─────────────────────────────────────────────────

class TestWithdrawTask:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task(status="withdrawn")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.withdraw_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/withdraw")
            assert resp.status_code == 200
            assert resp.json()["message"] == "撤回成功"

    def test_failure(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.withdraw_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/withdraw")
            assert resp.status_code == 400


# ── resubmit_task ─────────────────────────────────────────────────

class TestResubmitTask:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task(status="pending")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.resubmit_approval.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/resubmit")
            assert resp.status_code == 200
            assert resp.json()["message"] == "已重新提交"

    def test_failure(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.resubmit_approval.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/resubmit")
            assert resp.status_code == 400


# ── submit_and_auto_approve ───────────────────────────────────────

class TestSubmitAutoApprove:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task(status="approved")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.submit_and_auto_approve.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/submit-auto",
                json={"entity_type": "village", "entity_id": 1, "change_data": {"name": "New"}},
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "提交并自动审批通过"

    def test_failure(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.submit_and_auto_approve.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/submit-auto",
                json={"entity_type": "village", "entity_id": 1, "change_data": {"name": "New"}},
            )
            assert resp.status_code == 400


# ── auto_approve_single_task ─────────────────────────────────────

class TestAutoApproveSingle:
    def test_success(self, client_with_mocked_auth):
        task = make_mock_task()
        approved = make_mock_task(status="approved")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            svc.approve_task.return_value = approved
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/auto-approve", json={})
            assert resp.status_code == 200

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/999/auto-approve", json={})
            assert resp.status_code == 404

    def test_not_pending(self, client_with_mocked_auth):
        task = make_mock_task(status="approved")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/auto-approve", json={})
            assert resp.status_code == 400

    def test_approval_fails(self, client_with_mocked_auth):
        task = make_mock_task()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            svc.approve_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/auto-approve", json={})
            assert resp.status_code == 400


# ── auto_approve_all ─────────────────────────────────────────────

class TestAutoApproveAll:
    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.auto_approve_all_pending.return_value = {
                "total_pending": 5, "approved": 3, "failed": [],
            }
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/auto-approve-all", json={})
            assert resp.status_code == 200
            assert resp.json()["data"]["approved"] == 3


# ── get_all_tasks ─────────────────────────────────────────────────

class TestGetAllTasks:
    def test_admin_success(self, client_with_mocked_auth):
        task = make_mock_task()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_all_tasks_with_count.return_value = {"items": [task], "total": 1}
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/tasks/all")
            assert resp.status_code == 200
            assert resp.json()["total"] == 1

    def test_regular_user_forbidden(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.get(f"{BASE}/tasks/all")
        assert resp.status_code == 403

    def test_filter_params(self, client_with_mocked_auth):
        task = make_mock_task()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_all_tasks_with_count.return_value = {"items": [task], "total": 1}
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/tasks/all?status=pending&entity_type=village")
            assert resp.status_code == 200


# ── get_pending_tasks ─────────────────────────────────────────────

class TestGetPendingTasks:
    def test_with_pending(self, client_with_mocked_auth):
        task = make_mock_task()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_pending_tasks.return_value = [task]
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/tasks/pending")
            assert resp.status_code == 200
            assert resp.json()["total"] >= 1

    def test_fallback_to_all_pending(self, client_with_mocked_auth):
        from app.core.database import get_db
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.count.return_value = 0
        original = client_with_mocked_auth.app.dependency_overrides.get(get_db)
        client_with_mocked_auth.app.dependency_overrides[get_db] = lambda: mock_db
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_pending_tasks.return_value = []
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/tasks/pending")
            assert resp.status_code == 200
        if original:
            client_with_mocked_auth.app.dependency_overrides[get_db] = original
        else:
            del client_with_mocked_auth.app.dependency_overrides[get_db]


# ── batch_approve ─────────────────────────────────────────────────

class TestBatchApprove:
    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.batch_approve.return_value = {
                "success": [1, 2], "failed": [],
            }
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(
                f"{BASE}/tasks/batch",
                json={"task_ids": [1, 2]},
            )
            assert resp.status_code == 200
            assert "成功" in resp.json()["message"]


# ── get_task_diff ─────────────────────────────────────────────────

class TestGetTaskDiff:
    def test_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task_diff.return_value = {"changed": {"name": ["Old", "New"]}}
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/tasks/1/diff")
            assert resp.status_code == 200
            assert "changed" in resp.json()["data"]

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task_diff.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/tasks/999/diff")
            assert resp.status_code == 404


# ── remind_task ───────────────────────────────────────────────────

class TestRemindTask:
    def _setup_db_override(self, client, mock_db):
        from app.core.database import get_db
        original = client.app.dependency_overrides.get(get_db)
        client.app.dependency_overrides[get_db] = lambda: mock_db
        return original

    def _restore_db_override(self, client, original):
        from app.core.database import get_db
        if original:
            client.app.dependency_overrides[get_db] = original
        else:
            client.app.dependency_overrides.pop(get_db, None)

    def _make_mock_db(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.rollback = MagicMock()
        return mock_db

    def test_success(self, client_with_mocked_auth):
        task = make_mock_task()
        mock_db = self._make_mock_db()
        orig = self._setup_db_override(client_with_mocked_auth, mock_db)
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/remind")
            assert resp.status_code == 200
            assert resp.json()["message"] == "提醒已发送"
        self._restore_db_override(client_with_mocked_auth, orig)

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = None
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/999/remind")
            assert resp.status_code == 404

    def test_not_pending(self, client_with_mocked_auth):
        task = make_mock_task(status="approved")
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/remind")
            assert resp.status_code == 400

    def test_no_approver(self, client_with_mocked_auth):
        task = make_mock_task(current_approver_id=None)
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/remind")
            assert resp.status_code == 400

    def test_duplicate_reminder(self, client_with_mocked_auth):
        task = make_mock_task()
        mock_db = self._make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        orig = self._setup_db_override(client_with_mocked_auth, mock_db)
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/remind")
            assert resp.status_code == 409
        self._restore_db_override(client_with_mocked_auth, orig)

    def test_message_creation_error(self, client_with_mocked_auth):
        task = make_mock_task()
        mock_db = self._make_mock_db()
        mock_db.add.side_effect = RuntimeError("db error")
        orig = self._setup_db_override(client_with_mocked_auth, mock_db)
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_task.return_value = task
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.post(f"{BASE}/tasks/1/remind")
            assert resp.status_code == 500
        self._restore_db_override(client_with_mocked_auth, orig)


# ── get_approval_history ──────────────────────────────────────────

class TestGetApprovalHistory:
    def test_success(self, client_with_mocked_auth):
        record = make_mock_record()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_approval_history.return_value = [record]
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(f"{BASE}/history")
            assert resp.status_code == 200
            assert len(resp.json()["data"]) == 1

    def test_non_admin_auto_filters(self, client_with_regular_user_auth):
        record = make_mock_record()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_approval_history.return_value = [record]
            MockSvc.return_value = svc
            resp = client_with_regular_user_auth.get(f"{BASE}/history")
            assert resp.status_code == 200

    def test_with_filters(self, client_with_mocked_auth):
        record = make_mock_record()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as MockSvc:
            svc = MagicMock()
            svc.get_approval_history.return_value = [record]
            MockSvc.return_value = svc
            resp = client_with_mocked_auth.get(
                f"{BASE}/history?entity_type=village&status=approved"
            )
            assert resp.status_code == 200
