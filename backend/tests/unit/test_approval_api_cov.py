"""app.api.v1.approval 覆盖率攻坚测试

覆盖缺口（基线 miss）：
- 70：_notify_submitter 提交人为空（submitter_id=None）→ 早退不写消息
- 103：approval_overview 非管理员 _scoped 过滤分支
- 140：overview 非管理员 my_pending=0 → 改按 submitter_id 统计
- 495-500：retry-apply 非管理员 403 / 无需重试 404
- 501-512：retry-apply 成功路径（写工作日志）
- 808-809：/tasks/pending count_pending_tasks 抛异常 → total 回退为当页长度
- 861-882：/tasks/batch 非管理员 allowed/denied 分流（含全 denied 不调服务）
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _user(admin=False):
    return SimpleNamespace(
        id=7, username="alice", role="admin" if admin else "user", is_superuser=admin
    )


def _db(scalar_side_effect=None, all_return=None):
    db = MagicMock(name="db")
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    if scalar_side_effect is not None:
        q.scalar.side_effect = scalar_side_effect
    if all_return is not None:
        q.all.return_value = all_return
    db.query.return_value = q
    return db, q


@pytest.fixture
def build_client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    def _make(db, user):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        tc = TestClient(app, raise_server_exceptions=False)
        return tc

    yield _make
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


class TestNotifySubmitter:
    def test_approve_without_submitter_skips_message(self, build_client):
        # 覆盖 approval.py:70 —— submitter_id=None 早退，不写站内消息
        db, _ = _db()
        task = SimpleNamespace(
            id=1, title="T", entity_type="fund", status="approved",
            current_level=2, submitter_id=None,
        )
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            svc.return_value.approve_task.return_value = task
            resp = build_client(db, _user()).post(
                "/api/v1/approval/tasks/1/approve", json={"opinion": "ok"}
            )
        assert resp.status_code == 200
        db.add.assert_not_called()


class TestApprovalOverview:
    def test_non_admin_scoped_and_submitter_pending_fallback(self, build_client):
        # 覆盖 approval.py:103（非管理员 _scoped 过滤）与 140（my_pending=0 改按 submitter 统计）
        # scalar 依次消费：total, pending, approved, rejected, my_pending(=0 触发回退), my_pending_submitter
        db, q = _db(scalar_side_effect=[10, 3, 5, 2, 0, 4])
        resp = build_client(db, _user(admin=False)).get("/api/v1/approval")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_count"] == 10
        assert data["pending_count"] == 3
        assert data["my_pending"] == 4
        assert q.filter.called  # 非管理员走 _scoped 过滤

    def test_non_admin_my_pending_nonzero_no_fallback(self, build_client):
        # 139 行条件为假：my_pending != 0 时不触发 submitter 回退查询
        db, q = _db(scalar_side_effect=[9, 2, 4, 1, 6])
        resp = build_client(db, _user(admin=False)).get("/api/v1/approval")
        assert resp.status_code == 200
        assert resp.json()["data"]["my_pending"] == 6
        assert q.scalar.call_count == 5


class TestWorkflowsList:
    def test_non_admin_sees_only_own_workflows(self, build_client):
        # 覆盖 approval.py:276 —— 非管理员 workflows 列表按 created_by 过滤
        mine = SimpleNamespace(
            created_by=7, id=1, name="W1", entity_type="fund",
            description="d", is_active=True, level_count=2,
        )
        others = SimpleNamespace(
            created_by=99, id=2, name="W2", entity_type="school",
            description="d", is_active=True, level_count=1,
        )
        db, _ = _db()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            svc.return_value.list_workflows.return_value = [mine, others]
            resp = build_client(db, _user(admin=False)).get("/api/v1/approval/workflows")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
        svc.return_value.list_workflows.assert_called_once_with(
            entity_type=None, is_active=None, skip=0, limit=100
        )


class TestRetryApply:
    def test_non_admin_forbidden_403(self, build_client):
        db, _ = _db()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            resp = build_client(db, _user(admin=False)).post(
                "/api/v1/approval/tasks/1/retry-apply"
            )
        assert resp.status_code == 403
        svc.return_value.retry_apply_entity_change.assert_not_called()

    def test_task_not_retryable_404(self, build_client):
        db, _ = _db()
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            svc.return_value.retry_apply_entity_change.return_value = None
            resp = build_client(db, _user(admin=True)).post(
                "/api/v1/approval/tasks/9/retry-apply"
            )
        assert resp.status_code == 404
        assert "无需重试" in resp.json()["detail"]

    def test_retry_success_writes_work_log(self, build_client):
        db, _ = _db()
        task = SimpleNamespace(id=5, title="经费变更", entity_type="fund", status="apply_failed")
        with (
            patch("app.api.v1.approval.ApprovalWorkflowService") as svc,
            patch("app.api.v1.approval.write_work_log") as wl,
        ):
            svc.return_value.retry_apply_entity_change.return_value = task
            resp = build_client(db, _user(admin=True)).post(
                "/api/v1/approval/tasks/5/retry-apply"
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["task_id"] == 5
        assert body["data"]["status"] == "apply_failed"
        wl.assert_called_once()
        assert wl.call_args.args[2] == "retry_apply"


class TestPendingCountFallback:
    def test_count_pending_raises_falls_back_to_page_len(self, build_client):
        # 覆盖 approval.py:808-809 —— count_pending_tasks 异常 → total=len(tasks)
        task = SimpleNamespace(
            id=1, title="T", entity_type="fund", entity_id=2, current_level=1,
            priority=1, status="pending", submitter_id=7,
            created_at=datetime(2026, 1, 1), change_data={"amount": 100},
        )
        db, _ = _db(all_return=[(7, "alice")])
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            svc.return_value.get_pending_tasks.return_value = [task]
            svc.return_value.count_pending_tasks.side_effect = TypeError("boom")
            resp = build_client(db, _user(admin=True)).get("/api/v1/approval/tasks/pending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1  # 回退为当页长度
        assert body["data"][0]["submitter_name"] == "alice"
        assert body["data"][0]["change_data"] == {"amount": 100}


class TestBatchApproveNonAdmin:
    def test_mixed_allowed_and_denied(self, build_client):
        # 覆盖 approval.py:861-882 —— 非管理员：allowed 走服务、denied 记失败
        db, _ = _db(all_return=[(1,), (3,)])
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            svc.return_value.batch_approve.return_value = {
                "success": [{"id": 1, "status": "approved"}], "failed": [],
            }
            resp = build_client(db, _user(admin=False)).post(
                "/api/v1/approval/tasks/batch",
                json={"task_ids": [1, 2, 3], "opinion": "批量通过"},
            )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert [s["id"] for s in results["success"]] == [1]
        assert {"id": 2, "reason": "无权限审批此任务"} in results["failed"]
        svc.return_value.batch_approve.assert_called_once_with([1, 3], 7, "批量通过")

    def test_all_denied_skips_service(self, build_client):
        # 覆盖 876-880 —— allowed 为空时不调用 batch_approve，全部记失败
        db, _ = _db(all_return=[])
        with patch("app.api.v1.approval.ApprovalWorkflowService") as svc:
            resp = build_client(db, _user(admin=False)).post(
                "/api/v1/approval/tasks/batch", json={"task_ids": [9], "opinion": None}
            )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert results["success"] == []
        assert results["failed"] == [{"id": 9, "reason": "无权限审批此任务"}]
        svc.return_value.batch_approve.assert_not_called()
