"""v1.12.9 覆盖率补口：app/api/v1/approval.py 变更对比 IDOR 归属校验（W15 深审 #2）。

覆盖行（当前代码行号）：
- 1019-1021 任务不存在 → 404；
- 1023-1029 非管理员仅可查看「自己提交」或「分配给自己的」任务，否则 403
  （修复前任意登录用户可按自增 id 遍历他人 change_data/original_data）；
- 1031-1036 放行路径返回 diff / diff 缺失 404。

另附同文件既有未覆盖行（列表端点与序列化辅助），保证本文件的覆盖口径自洽。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.approval as approval_api


def _actor(uid=1, role="user", is_superuser=False):
    return SimpleNamespace(id=uid, username=f"u{uid}", role=role, is_superuser=is_superuser)


def _service(task=None, diff=None):
    svc = MagicMock()
    svc.get_task.return_value = task
    svc.get_task_diff.return_value = diff
    return svc


class TestGetTaskDiffOwnership:
    def test_missing_task_404(self):
        svc = _service(task=None)
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                approval_api.get_task_diff(1, db=MagicMock(), current_user=_actor())
        assert ei.value.status_code == 404
        svc.get_task_diff.assert_not_called()

    def test_plain_user_cannot_read_others_task(self):
        task = SimpleNamespace(submitter_id=2, current_approver_id=3)
        svc = _service(task=task, diff={"change": 1})
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                approval_api.get_task_diff(9, db=MagicMock(), current_user=_actor(uid=1))
        assert ei.value.status_code == 403
        assert "无权查看" in ei.value.detail
        svc.get_task_diff.assert_not_called()

    def test_submitter_can_read_own_task(self):
        task = SimpleNamespace(submitter_id=1, current_approver_id=3)
        svc = _service(task=task, diff={"change": 1})
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            result = approval_api.get_task_diff(9, db=MagicMock(), current_user=_actor(uid=1))
        assert result["data"] == {"change": 1}

    def test_current_approver_can_read_task(self):
        task = SimpleNamespace(submitter_id=2, current_approver_id=1)
        svc = _service(task=task, diff={"change": 2})
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            result = approval_api.get_task_diff(9, db=MagicMock(), current_user=_actor(uid=1))
        assert result["data"] == {"change": 2}

    def test_admin_can_read_any_task(self):
        task = SimpleNamespace(submitter_id=2, current_approver_id=3)
        svc = _service(task=task, diff={"change": 3})
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            result = approval_api.get_task_diff(9, db=MagicMock(), current_user=_actor(uid=1, role="admin"))
        assert result["data"] == {"change": 3}

    def test_task_without_owner_fields_denied_for_plain_user(self):
        """历史任务 submitter/approver 均为 NULL：非管理员一律拒绝（fail-closed）。"""
        task = SimpleNamespace(submitter_id=None, current_approver_id=None)
        svc = _service(task=task, diff={"change": 4})
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                approval_api.get_task_diff(9, db=MagicMock(), current_user=_actor(uid=1))
        assert ei.value.status_code == 403

    def test_missing_diff_404(self):
        task = SimpleNamespace(submitter_id=1, current_approver_id=None)
        svc = _service(task=task, diff=None)
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                approval_api.get_task_diff(9, db=MagicMock(), current_user=_actor(uid=1))
        assert ei.value.status_code == 404


class TestApprovalSerializationAndLists:
    """同文件既有缺口：分页回退 / 实体链接 / 驳回原因必填 / 列表 envelope / 序列化。"""

    def test_pagination_falls_back_for_non_int(self):
        assert approval_api._pagination("0", None) == (1, 20)
        assert approval_api._pagination(0, 10) == (1, 10)

    def test_entity_link_unknown_entity_returns_none(self):
        task = SimpleNamespace(entity_id=1, entity_type="unknown")
        assert approval_api._entity_link(task) is None

    def test_entity_link_known_entity(self):
        assert approval_api._entity_link(
            SimpleNamespace(entity_id=5, entity_type="fund")
        ) == "/funds/5"
        assert approval_api._entity_link(
            SimpleNamespace(entity_id=5, entity_type="rural_work")
        ) == "/rural-works/list"

    def test_reject_requires_opinion(self):
        with pytest.raises(HTTPException) as ei:
            approval_api.reject_task(
                1,
                approval_api.ApprovalActionRequest(opinion="   "),
                db=MagicMock(),
                current_user=_actor(),
            )
        assert ei.value.status_code == 400
        assert "驳回必须填写原因" in ei.value.detail

    def test_task_to_dict_includes_last_record_opinion(self):
        record = SimpleNamespace(opinion="不同意")
        task = SimpleNamespace(
            id=1, title="t", entity_type="fund", entity_id=2, status="pending",
            current_level=1, priority=1, submitter_id=1, submitter=None,
            current_approver_id=None, current_approver=None,
            records=[record], change_data={"a": 1},
            created_at=None, completed_at=None,
        )
        data = approval_api._task_to_dict(task)
        assert data["opinion"] == "不同意"
        assert data["change_data"] == {"a": 1}

    def test_get_my_tasks_scopes_to_current_user(self):
        svc = MagicMock()
        svc.get_tasks_with_count.return_value = {"items": [], "total": 0}
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            result = approval_api.get_my_tasks(
                status=None, date_from=None, date_to=None, skip=0, limit=100,
                db=MagicMock(), current_user=_actor(uid=1),
            )
        assert result["data"]["total"] == 0
        assert svc.get_tasks_with_count.call_args.kwargs["submitter_id"] == 1

    def test_get_task_history_admin_sees_all(self):
        svc = MagicMock()
        svc.get_tasks_with_count.return_value = {"items": [], "total": 0}
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            approval_api.get_task_history(
                entity_type=None, status=None, completed=None, skip=0, limit=100,
                db=MagicMock(), current_user=_actor(role="admin"),
            )
        assert svc.get_tasks_with_count.call_args.kwargs["submitter_id"] is None

    def test_get_task_history_plain_user_scoped(self):
        svc = MagicMock()
        svc.get_tasks_with_count.return_value = {"items": [], "total": 0}
        with patch.object(approval_api, "ApprovalWorkflowService", return_value=svc):
            approval_api.get_task_history(
                entity_type=None, status=None, completed=None, skip=0, limit=100,
                db=MagicMock(), current_user=_actor(uid=42),
            )
        assert svc.get_tasks_with_count.call_args.kwargs["submitter_id"] == 42
