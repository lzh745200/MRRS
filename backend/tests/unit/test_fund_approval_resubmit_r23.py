"""R23 回归锁定：「驳回 → 重新提交 → 审批通过」的经费回写闭环。

R23 探针实测缺陷（真实 HTTP + 真实 DB）：

    fund=23 task=17 initial fund=(23, 'pending')
    reject      -> 200, task=rejected, fund=rejected   ✓
    resubmit    -> 200, task=pending,  fund=rejected   ✗ 经费没跟着回到待审批
    auto-approve-> 200, task=approved, fund=rejected   ✗✗ 审批过了，经费仍「已驳回」
    status history: [('pending','rejected',...)]          没有 approved 行

根因两处：① `ApprovalWorkflowService.resubmit_approval` 只改任务不改实体；
② `_apply_fund_approval_result` 要求 `fund.status == "pending"` 才回写，于是
驳回后的最终通过被静默忽略 —— 用户在待审批里点了通过，经费板块永远停在已驳回。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.api.v1.funds import (
    _FUND_APPROVAL_TARGETS,
    _apply_fund_approval_result,
)
from app.models.fund import Fund
from app.models.fund_history import FundStatusHistory
from app.services.approval_workflow_service import ApprovalWorkflowService


def _mk_task(status, entity_id, task_id=1, approver_id=None):
    return SimpleNamespace(
        id=task_id,
        status=status,
        entity_type="fund",
        entity_id=entity_id,
        submitter_id=1,
        current_level=1,
        current_approver_id=approver_id,
        current_approver=None,
        completed_at=None,
    )


@pytest.fixture()
def db_session(real_db_session):
    """真实内存 SQLite（conftest 的 `db_session` 是 MagicMock，会把回写断言变成空跑）。"""
    return real_db_session


@pytest.fixture()
def fund(db_session):
    f = Fund(name="R23 闭环经费", amount=10.0, status="pending")
    db_session.add(f)
    db_session.flush()
    return f


def _status(db, fund_id):
    db.expire_all()
    return db.query(Fund).filter(Fund.id == fund_id).first().status


class TestFundApprovalWriteBack:
    def test_approve_from_pending(self, db_session, fund):
        _apply_fund_approval_result(db_session, _mk_task("approved", fund.id))
        db_session.flush()
        assert _status(db_session, fund.id) == "approved"

    def test_approve_from_rejected(self, db_session, fund):
        """驳回后重新提交再通过 —— 修复前这里被静默忽略。"""
        fund.status = "rejected"
        db_session.flush()
        _apply_fund_approval_result(db_session, _mk_task("approved", fund.id))
        db_session.flush()
        assert _status(db_session, fund.id) == "approved"

    def test_reject_from_pending(self, db_session, fund):
        _apply_fund_approval_result(db_session, _mk_task("rejected", fund.id))
        db_session.flush()
        assert _status(db_session, fund.id) == "rejected"

    def test_resubmit_puts_fund_back_to_pending(self, db_session, fund):
        fund.status = "rejected"
        db_session.flush()
        _apply_fund_approval_result(db_session, _mk_task("pending", fund.id))
        db_session.flush()
        assert _status(db_session, fund.id) == "pending"

    def test_noop_when_target_equals_current(self, db_session, fund):
        fund.status = "approved"
        db_session.flush()
        before = db_session.query(FundStatusHistory).count()
        _apply_fund_approval_result(db_session, _mk_task("approved", fund.id))
        db_session.flush()
        assert db_session.query(FundStatusHistory).count() == before, "幂等重复回写不得再记历史"

    def test_noop_for_unrelated_status(self, db_session, fund):
        """已分配/使用中的经费不因审批任务终态而被改写。"""
        fund.status = "allocated"
        db_session.flush()
        _apply_fund_approval_result(db_session, _mk_task("approved", fund.id))
        db_session.flush()
        assert _status(db_session, fund.id) == "allocated"

    def test_noop_for_unknown_task_status(self, db_session, fund):
        _apply_fund_approval_result(db_session, _mk_task("withdrawn", fund.id))
        db_session.flush()
        assert _status(db_session, fund.id) == "pending"

    def test_missing_fund_is_noop(self, db_session):
        _apply_fund_approval_result(db_session, _mk_task("approved", 999999))
        db_session.flush()

    def test_history_row_written_with_remark(self, db_session, fund):
        _apply_fund_approval_result(db_session, _mk_task("approved", fund.id, task_id=77))
        db_session.flush()
        row = db_session.query(FundStatusHistory).filter(FundStatusHistory.fund_id == fund.id).first()
        assert row.from_status == "pending"
        assert row.to_status == "approved"
        assert "77" in row.remark and "通过" in row.remark

    def test_resubmit_history_remark(self, db_session, fund):
        fund.status = "rejected"
        db_session.flush()
        _apply_fund_approval_result(db_session, _mk_task("pending", fund.id, task_id=78))
        db_session.flush()
        row = (
            db_session.query(FundStatusHistory)
            .filter(FundStatusHistory.fund_id == fund.id, FundStatusHistory.to_status == "pending")
            .first()
        )
        assert row is not None and "重新提交" in row.remark

    def test_approve_records_approver_name(self, db_session, fund):
        approver = SimpleNamespace(id=5, full_name="张审核", username="zhang")
        task = _mk_task("approved", fund.id, approver_id=5)
        task.current_approver = approver
        _apply_fund_approval_result(db_session, task)
        db_session.flush()
        db_session.expire_all()
        assert db_session.query(Fund).filter(Fund.id == fund.id).first().approved_by == "张审核"

    def test_target_map_covers_rejected_roundtrip(self):
        assert _FUND_APPROVAL_TARGETS[("rejected", "pending")] == "rejected"
        assert _FUND_APPROVAL_TARGETS[("pending", "rejected")] == "pending"
        assert _FUND_APPROVAL_TARGETS[("approved", "rejected")] == "approved"
        assert ("approved", "allocated") not in _FUND_APPROVAL_TARGETS


class TestResubmitTriggersEntityWriteBack:
    def test_resubmit_calls_apply_entity_change(self, db_session):
        svc = ApprovalWorkflowService(db_session)
        task = _mk_task("rejected", 1)
        task.workflow = SimpleNamespace(nodes=[])

        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "apply_entity_change") as m_apply, \
             patch.object(db_session, "refresh"), \
             patch("app.services.approval_workflow_service.safe_commit"):
            svc.resubmit_approval(task.id, task.submitter_id)

        m_apply.assert_called_once_with(task)

    def test_resubmit_refused_for_pending_task_does_not_write_back(self, db_session):
        svc = ApprovalWorkflowService(db_session)
        task = _mk_task("pending", 1)
        with patch.object(svc, "get_task", return_value=task), \
             patch.object(svc, "apply_entity_change") as m_apply:
            assert svc.resubmit_approval(task.id, task.submitter_id) is None
        m_apply.assert_not_called()
