"""W2-T3 审批回写闭环回归测试。

覆盖：
1. apply 失败 → 任务标记 approved_apply_failed（不 commit 成功终态），可查询重试；
2. 重试成功 → 恢复 approved；
3. reject 路径同理（rejected_apply_failed）；
4. resubmit 对 role 型节点正确解析审批人。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.approval_workflow_service import ApprovalWorkflowService


@pytest.fixture()
def svc(db_session):
    return ApprovalWorkflowService(db_session)


def _mk_task(task_id=1, status="pending", entity_type="fund", entity_id=9):
    return SimpleNamespace(
        id=task_id,
        status=status,
        entity_type=entity_type,
        entity_id=entity_id,
        submitter_id=7,
        current_level=1,
        current_approver_id=None,
        completed_at=None,
        title="t",
    )


class TestApplyFailureClosure:
    def test_apply_failure_marks_task(self, svc):
        """handler 抛异常 → apply_entity_change 返回 False，任务可被标记失败态"""
        task = _mk_task()

        def _boom(db, t):
            raise RuntimeError("boom")

        with patch.object(ApprovalWorkflowService, "_ENTITY_APPLY_HANDLERS", {"fund": _boom}):
            ok = svc.apply_entity_change(task)
        assert ok is False

    def test_apply_success_returns_true(self, svc):
        task = _mk_task()
        calls = []
        with patch.object(
            ApprovalWorkflowService, "_ENTITY_APPLY_HANDLERS",
            {"fund": lambda db, t: calls.append(t)},
        ):
            ok = svc.apply_entity_change(task)
        assert ok is True
        assert calls == [task]

    def test_no_handler_returns_true(self, svc):
        task = _mk_task(entity_type="unknown_entity")
        with patch.object(ApprovalWorkflowService, "_ENTITY_APPLY_HANDLERS", {}):
            assert svc.apply_entity_change(task) is True


class TestRetryApply:
    def test_retry_restores_final_status(self, svc, db_session):
        """approved_apply_failed → 重试成功恢复 approved"""
        task = _mk_task(status=ApprovalStatusFailed.APPROVED_FAILED)
        fake_get = lambda _tid: task  # noqa: E731

        with patch.object(svc, "get_task", side_effect=fake_get), \
             patch.object(svc, "apply_entity_change", return_value=True) as m_apply, \
             patch("app.services.approval_workflow_service.safe_commit"):
            result = svc.retry_apply_entity_change(task.id)

        assert result is task
        assert task.status == "approved"
        m_apply.assert_called_once_with(task)

    def test_retry_keeps_failed_status_on_second_failure(self, svc):
        task = _mk_task(status=ApprovalStatusFailed.REJECTED_FAILED)
        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "apply_entity_change", return_value=False), \
             patch("app.services.approval_workflow_service.safe_commit"):
            result = svc.retry_apply_entity_change(task.id)
        assert result.status == ApprovalStatusFailed.REJECTED_FAILED

    def test_retry_rejects_normal_status(self, svc):
        task = _mk_task(status="approved")
        assert svc.retry_apply_entity_change(task.id) is None

    def test_retry_missing_task(self, svc):
        assert svc.retry_apply_entity_change(99999) is None


class ApprovalStatusFailed:
    APPROVED_FAILED = "approved_apply_failed"
    REJECTED_FAILED = "rejected_apply_failed"


class TestResubmitRoleResolution:
    def test_resubmit_resolves_role_node_approver(self, svc):
        """role 型首节点：resubmit 后 current_approver_id 应为解析出的具体用户而非角色标识"""
        role_node = SimpleNamespace(level=1, approver_type="role", approver_id="admin")
        task = _mk_task(status="rejected")
        task.workflow = SimpleNamespace(nodes=[role_node])

        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "_resolve_role_approver_id", return_value=42) as m_resolve, \
             patch("app.services.approval_workflow_service.safe_commit"):
            result = svc.resubmit_approval(task.id, task.submitter_id)

        assert result.current_approver_id == 42
        m_resolve.assert_called_once_with("admin")

    def test_resubmit_user_node_keeps_id(self, svc):
        user_node = SimpleNamespace(level=1, approver_type="user", approver_id=33)
        task = _mk_task(status="withdrawn")
        task.workflow = SimpleNamespace(nodes=[user_node])

        with patch.object(svc, "get_task", return_value=task), \
             patch("app.services.approval_workflow_service.safe_commit"):
            result = svc.resubmit_approval(task.id, task.submitter_id)

        assert result.current_approver_id == 33
