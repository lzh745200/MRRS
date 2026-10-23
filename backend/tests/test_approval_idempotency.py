"""审批幂等 / 状态机 / 事务边界 / 超时提醒 —— 真实行为回归。

## 为什么重写（W27 P1，W26 检测「19 个空壳测试」）
本文件原有 **10 个测试函数体全部是 `pass`**：不建数据、不调被测代码、不写任何断言。
它们会让测试计数与覆盖率"看起来有覆盖"，实际审批幂等这一**关键属性完全没有被验证** ——
而审批在 W27 恰被改造成「真门禁」（变更需审批通过才生效），这些属性更重要了。

现全部替换为对**真实实现**的断言：
* 幂等/状态机 → ``ApprovalWorkflowService``（含 W25 的 fail-closed 审批人语义、
  M30 的原子抢占 UPDATE）
* 超时/预警/提醒去重 → ``ApprovalReminderService``（48h 超时 / 36h 预警）
* 事务边界 → 审批人不匹配 / 已被处理时不得二次推进，且不得重复写审批记录
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models.approval import (
    ApprovalNode,
    ApprovalRecord,
    ApprovalStatus,
    ApprovalTask,
    ApprovalWorkflow,
)
from app.models.message import Message
from app.services.approval_workflow_service import ApprovalWorkflowService


# ── 造数据辅助 ──────────────────────────────────────────────────────


def _workflow(db, entity_type="policy", levels=(1,), approver=1):
    wf = ApprovalWorkflow(name=f"WF-{entity_type}", entity_type=entity_type, is_active=True)
    db.add(wf)
    db.flush()
    for lv in levels:
        db.add(ApprovalNode(
            workflow_id=wf.id, level=lv, name=f"L{lv}",
            approver_type="user", approver_id=approver,
        ))
    db.commit()
    return wf


def _task(db, wf, *, status=ApprovalStatus.PENDING.value, approver=1, level=1,
          entity_type=None, age_hours=0):
    task = ApprovalTask(
        workflow_id=wf.id,
        entity_type=entity_type or wf.entity_type,
        entity_id=1,
        submitter_id=2,
        current_level=level,
        current_approver_id=approver,
        status=status,
        title="测试审批",
    )
    db.add(task)
    db.commit()
    if age_hours:
        task.created_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        db.commit()
    return task


class TestApprovalIdempotency:
    """重复提交 / 重复审批的幂等性。"""

    def test_duplicate_submit_returns_existing_status(self, real_db_session):
        """同一实体重复提交：**不得产生第二条待审批任务**（幂等）。"""
        db = real_db_session
        wf = _workflow(db)
        svc = ApprovalWorkflowService(db)

        first = svc.submit_approval(entity_type="policy", entity_id=1, submitter_id=2)
        assert first is not None and first.status == ApprovalStatus.PENDING.value

        svc.submit_approval(entity_type="policy", entity_id=1, submitter_id=2)
        pending = (
            db.query(ApprovalTask)
            .filter(
                ApprovalTask.entity_type == "policy",
                ApprovalTask.entity_id == 1,
                ApprovalTask.status == ApprovalStatus.PENDING.value,
            )
            .all()
        )
        # 幂等契约：同一实体同一时刻只允许一条待审批任务
        assert len(pending) == 1, f"重复提交产生了 {len(pending)} 条待审批任务"
        assert pending[0].id == first.id
        assert wf.id == first.workflow_id

    def test_concurrent_approve_is_idempotent(self, real_db_session):
        """同一任务审批两次：第二次必须无效，且审批记录只有一条。"""
        db = real_db_session
        wf = _workflow(db)
        task = _task(db, wf)
        svc = ApprovalWorkflowService(db)

        applied = []
        ApprovalWorkflowService.register_entity_apply_handler(
            "policy", lambda _db, _task: applied.append(_task.id) or True
        )

        first = svc.approve_task(task.id, approver_id=1, standalone=True)
        assert first is not None
        db.refresh(task)
        assert task.status == ApprovalStatus.APPROVED.value

        second = svc.approve_task(task.id, approver_id=1, standalone=True)
        assert second is None, "已通过的任务不得被再次审批"

        records = db.query(ApprovalRecord).filter(ApprovalRecord.task_id == task.id).all()
        assert len(records) == 1, "重复审批写入了多条审批记录"
        assert len(applied) == 1, "重复审批触发了两次业务回写"

    def test_reject_and_resubmit_flow(self, real_db_session):
        """驳回后可重新提交：状态回到 pending，且允许新任务。"""
        db = real_db_session
        wf = _workflow(db)
        task = _task(db, wf)
        svc = ApprovalWorkflowService(db)

        rejected = svc.reject_task(task.id, approver_id=1, opinion="材料不全", standalone=True)
        assert rejected is not None
        db.refresh(task)
        assert task.status == ApprovalStatus.REJECTED.value
        assert task.completed_at is not None

        again = svc.submit_approval(entity_type="policy", entity_id=1, submitter_id=2)
        assert again is not None
        # 驳回后可重新进入待审批（旧任务保持 rejected，新任务 pending）
        pending = (
            db.query(ApprovalTask)
            .filter(
                ApprovalTask.entity_type == "policy",
                ApprovalTask.entity_id == 1,
                ApprovalTask.status == ApprovalStatus.PENDING.value,
            )
            .count()
        )
        assert pending == 1

    def test_withdraw_and_resubmit(self, real_db_session):
        """撤回后任务不再是 pending，可再次提交。"""
        db = real_db_session
        wf = _workflow(db)
        task = _task(db, wf)
        svc = ApprovalWorkflowService(db)

        withdrawn = svc.withdraw_task(task.id, submitter_id=2)
        assert withdrawn is not None
        db.refresh(task)
        assert task.status != ApprovalStatus.PENDING.value

        again = svc.submit_approval(entity_type="policy", entity_id=1, submitter_id=2)
        assert again is not None
        assert again.status == ApprovalStatus.PENDING.value

    def test_approval_status_transition_integrity(self, real_db_session):
        """只有 pending 任务可被通过/驳回；已终结任务一律拒绝。"""
        db = real_db_session
        wf = _workflow(db)
        svc = ApprovalWorkflowService(db)

        for terminal in (ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value):
            task = _task(db, wf, status=terminal)
            assert svc.approve_task(task.id, approver_id=1, standalone=True) is None
            assert svc.reject_task(task.id, approver_id=1, opinion="x", standalone=True) is None


class TestApprovalTimeout:
    """超时 / 预警 / 提醒去重（真实 ``ApprovalReminderService``）。"""

    @staticmethod
    def _reminder_svc():
        from app.services.reminder_service import ApprovalReminderService

        return ApprovalReminderService()

    def test_overdue_approval_detection(self, real_db_session, monkeypatch):
        """超过 48h 未处理 → 生成 approval_overtime 提醒。"""
        db = real_db_session
        wf = _workflow(db)
        _task(db, wf, age_hours=50)
        svc = self._reminder_svc()

        monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
        # 防止 finally 关掉共享会话
        monkeypatch.setattr(db, "close", lambda *a, **k: None, raising=False)
        svc._check_overdue_approvals()

        msgs = db.query(Message).filter(Message.message_type == "approval_overtime").all()
        assert len(msgs) == 1
        assert "48小时" in msgs[0].content

    def test_approaching_deadline_warning(self, real_db_session, monkeypatch):
        """36h~48h 之间 → 生成 approval_approaching 预警（不是超时）。"""
        db = real_db_session
        wf = _workflow(db)
        _task(db, wf, age_hours=40)
        svc = self._reminder_svc()

        monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
        monkeypatch.setattr(db, "close", lambda *a, **k: None, raising=False)
        svc._check_overdue_approvals()

        msgs = db.query(Message).filter(Message.message_type == "approval_approaching").all()
        assert len(msgs) == 1
        assert "36小时" in msgs[0].content
        assert db.query(Message).filter(Message.message_type == "approval_overtime").count() == 0

    def test_reminder_message_created_once(self, real_db_session, monkeypatch):
        """重复扫描不得重复建提醒（幂等键 type:id）。"""
        db = real_db_session
        wf = _workflow(db)
        _task(db, wf, age_hours=60)
        svc = self._reminder_svc()

        monkeypatch.setattr("app.core.database.SessionLocal", lambda: db)
        monkeypatch.setattr(db, "close", lambda *a, **k: None, raising=False)
        svc._check_overdue_approvals()
        svc._check_overdue_approvals()
        svc._check_overdue_approvals()

        assert db.query(Message).filter(Message.message_type == "approval_overtime").count() == 1


class TestApprovalTransactionBoundary:
    """事务边界：审批人不符/已被处理时不得推进。"""

    def test_approve_changes_in_single_transaction(self, real_db_session):
        """一次审批 = 一条审批记录 + 状态推进（同一提交内完成）。"""
        db = real_db_session
        wf = _workflow(db)
        task = _task(db, wf)
        svc = ApprovalWorkflowService(db)

        assert svc.approve_task(task.id, approver_id=1, standalone=True) is not None

        db.expire_all()
        fresh = db.query(ApprovalTask).filter(ApprovalTask.id == task.id).one()
        assert fresh.status == ApprovalStatus.APPROVED.value
        assert fresh.completed_at is not None
        recs = db.query(ApprovalRecord).filter(ApprovalRecord.task_id == task.id).all()
        assert len(recs) == 1
        assert recs[0].action in ("approve", "approved")

    def test_rollback_on_failure(self, real_db_session):
        """审批人不匹配（非 standalone）→ 整体不生效：状态不变、无审批记录。"""
        db = real_db_session
        wf = _workflow(db, approver=1)
        task = _task(db, wf, approver=1)
        svc = ApprovalWorkflowService(db)

        assert svc.approve_task(task.id, approver_id=999, standalone=False) is None

        db.expire_all()
        fresh = db.query(ApprovalTask).filter(ApprovalTask.id == task.id).one()
        assert fresh.status == ApprovalStatus.PENDING.value
        assert fresh.completed_at is None
        assert db.query(ApprovalRecord).filter(ApprovalRecord.task_id == task.id).count() == 0

    def test_unassigned_task_fails_closed_without_standalone(self, real_db_session):
        """W25 契约：未分配审批人的任务，非管理员一律不得通过。"""
        db = real_db_session
        wf = _workflow(db)
        task = _task(db, wf, approver=None)
        svc = ApprovalWorkflowService(db)

        assert svc.approve_task(task.id, approver_id=1, standalone=False) is None
        db.refresh(task)
        assert task.status == ApprovalStatus.PENDING.value
