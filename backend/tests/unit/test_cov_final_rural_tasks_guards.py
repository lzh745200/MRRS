"""app.api.v1.rural_tasks 覆盖补全：审批红线守卫。

- line 242 —— 通用更新接口的 status 白名单：仅草稿/被驳回阶段可改状态，
  否则创建人可直接把任务置为 approved，绕过审批流程。
- line 329 —— 审批独立性：非管理员不得审批本人创建或提交的任务
  （自审自批会让审批形同虚设）。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.rural_tasks import approve_task, update_task
from app.models.rural_task import TaskStatus
from app.schemas.rural_task import RuralTaskUpdate, TaskApproveRequest


def _admin():
    return SimpleNamespace(
        id=1, username="admin", role="admin", is_superuser=True, is_active=True,
    )


def _non_admin(uid=9):
    return SimpleNamespace(
        id=uid, username="bob", role="user", is_superuser=False, is_active=True,
    )


def _task(**over):
    base = dict(id=5, code="TASK-2025-001", title="修路", status=TaskStatus.draft,
                created_by=9, submitted_by=None)
    base.update(over)
    return SimpleNamespace(**base)


class TestUpdateTaskStatusRedLine:
    """PUT /rural-tasks/{id} 的 status 白名单（line 242）。"""

    @pytest.mark.parametrize(
        "locked_status",
        [TaskStatus.pending_approval, TaskStatus.approved, TaskStatus.in_progress,
         TaskStatus.completed, TaskStatus.cancelled],
    )
    async def test_status_edit_on_submitted_task_is_400(self, locked_status):
        db = MagicMock(name="db")
        task = _task(status=locked_status)

        with patch("app.api.v1.rural_tasks._get_task_or_403", return_value=task):
            with pytest.raises(HTTPException) as excinfo:
                await update_task(
                    task_id=5, data=RuralTaskUpdate(status="approved"),
                    db=db, current_user=_admin(),
                )

        assert excinfo.value.status_code == 400
        assert "状态不能直接修改" in excinfo.value.detail
        # 必须在落库前拒绝
        assert task.status == locked_status
        db.commit.assert_not_called()

    async def test_draft_task_may_change_status(self):
        """对照组：草稿阶段允许改状态（守卫只锁"已提交"的任务）。"""
        db = MagicMock(name="db")
        task = MagicMock(name="task")
        task.id = 5
        task.status = TaskStatus.draft
        task.village = None
        task.rural_work = None
        task.to_dict.return_value = {"id": 5, "status": "in_progress"}

        with patch("app.api.v1.rural_tasks._get_task_or_403", return_value=task):
            resp = await update_task(
                task_id=5, data=RuralTaskUpdate(status="in_progress"),
                db=db, current_user=_admin(),
            )

        assert resp.code == 200
        assert task.status == "in_progress"
        assert task.updated_by == 1


class TestApproveTaskIndependenceRedLine:
    """POST /rural-tasks/{id}/approve 的审批独立性（line 329）。"""

    async def test_creator_cannot_approve_own_task(self):
        db = MagicMock(name="db")
        task = _task(status=TaskStatus.pending_approval, created_by=9, submitted_by=None)

        with patch("app.api.v1.rural_tasks._get_task_or_403", return_value=task):
            with pytest.raises(HTTPException) as excinfo:
                await approve_task(
                    task_id=5, body=TaskApproveRequest(approved=True),
                    db=db, current_user=_non_admin(9),
                )

        assert excinfo.value.status_code == 403
        assert "不得审批本人创建或提交的任务" in excinfo.value.detail
        assert task.status == TaskStatus.pending_approval
        db.commit.assert_not_called()

    async def test_submitter_cannot_approve_own_submission(self):
        """创建人是别人、提交人是自己 —— or 的右半边同样必须拦住。"""
        db = MagicMock(name="db")
        task = _task(status=TaskStatus.pending_approval, created_by=1, submitted_by=9)

        with patch("app.api.v1.rural_tasks._get_task_or_403", return_value=task):
            with pytest.raises(HTTPException) as excinfo:
                await approve_task(
                    task_id=5, body=TaskApproveRequest(approved=False),
                    db=db, current_user=_non_admin(9),
                )

        assert excinfo.value.status_code == 403
        db.commit.assert_not_called()

    async def test_unrelated_approver_is_allowed(self):
        """对照组：与创建/提交无关的审批人正常走通。"""
        db = MagicMock(name="db")
        task = MagicMock(name="task")
        task.id = 5
        task.code = "TASK-2025-001"
        task.status = TaskStatus.pending_approval
        task.created_by = 1
        task.submitted_by = 1
        approver = _non_admin(9)

        with patch("app.api.v1.rural_tasks._get_task_or_403", return_value=task):
            resp = await approve_task(
                task_id=5, body=TaskApproveRequest(approved=True, comment="同意"),
                db=db, current_user=approver,
            )

        assert resp.code == 200
        assert task.status == TaskStatus.approved
        assert task.approved_by == approver.id
        assert task.approval_comment == "同意"

    async def test_admin_may_approve_own_task(self):
        """唯一豁免：管理员（单机离线部署下需能自审），且仅在此角色下放行。"""
        db = MagicMock(name="db")
        task = MagicMock(name="task")
        task.id = 5
        task.code = "TASK-2025-001"
        task.status = TaskStatus.pending_approval
        task.created_by = 1
        task.submitted_by = 1

        with patch("app.api.v1.rural_tasks._get_task_or_403", return_value=task):
            resp = await approve_task(
                task_id=5, body=TaskApproveRequest(approved=True),
                db=db, current_user=_admin(),
            )

        assert resp.code == 200
        assert task.status == TaskStatus.approved
