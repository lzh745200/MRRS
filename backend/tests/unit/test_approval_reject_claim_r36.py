# -*- coding: utf-8 -*-
"""M30 原子抢占的失败分支（`approval_workflow_service.reject_task`）。

背景：CI 覆盖率曾在 `app/services/approval_workflow_service.py:582` 出现
`1 statement missed / 1 partial branch`（`if claimed != 1: return None`）——
这条"并发/重放导致 rowcount != 1"的防御分支只靠其它用例的副作用偶然覆盖，
一旦用例顺序变化就掉，属**不确定性门禁**。

本用例用替身把 `update()` 的 rowcount 钉成 0，确定性覆盖该分支。
"""
from unittest.mock import MagicMock

from app.models.approval import ApprovalStatus
from app.services.approval_workflow_service import ApprovalWorkflowService


def test_reject_task_returns_none_when_claim_loses(monkeypatch):
    """rowcount != 1（已被并发/重放处理）→ 返回 None，且不写审批记录。"""
    db = MagicMock(name="db")
    svc = ApprovalWorkflowService.__new__(ApprovalWorkflowService)
    svc.db = db

    task = MagicMock(name="task")
    task.status = ApprovalStatus.PENDING.value
    task.current_approver_id = 7
    task.current_level = 1
    monkeypatch.setattr(svc, "get_task", lambda _task_id: task)

    # 原子抢占失败：status + current_level 双条件更新命中 0 行
    db.query.return_value.filter.return_value.update.return_value = 0

    assert svc.reject_task(1, 7, "并发已处理") is None
    db.add.assert_not_called()
