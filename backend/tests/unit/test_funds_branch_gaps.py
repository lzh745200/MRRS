"""funds.py 分支覆盖缺口专项（分支清零第七批）。

覆盖 coverage report --show-missing 实测的 6 个部分分支中的 4 个直调可达弧：
- _fund_summary：extra=None 的假分支（70->72）；
- _resolve_fund_approval_tasks：多任务连续审批（147->140）与连续驳回（154->140）；
- _apply_fund_approval_result：审批人已不存在 → approved_by 保持 None（219->221）。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1.funds import (
    _apply_fund_approval_result,
    _fund_summary,
    _resolve_fund_approval_tasks,
)


def _admin():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.full_name = "管理员"
    u.is_superuser = True
    return u


def test_fund_summary_without_extra():
    """extra=None → 跳过附加字段合并（70->72）。"""
    fund = SimpleNamespace(name="经费A", amount=100)
    summary = _fund_summary(fund, None)
    assert isinstance(summary, dict)


def test_fund_summary_merges_extra_and_skips_none_values():
    """extra 合并不回归：值为 None 的键不进入摘要。"""
    fund = SimpleNamespace(name="经费A")
    summary = _fund_summary(fund, {"code": "F001", "note": None})
    assert summary.get("code") == "F001"
    assert "note" not in summary


def _task(tid, status):
    return SimpleNamespace(id=tid, status=status, entity_id=1, current_approver_id=None)


def test_resolve_fund_approval_tasks_two_approves():
    """两条待审任务连续通过 → 审批循环回边（147->140），返回完结数 2。"""
    db = MagicMock()
    fund = SimpleNamespace(id=1)
    db.query.return_value.filter.return_value.all.return_value = [
        _task(11, "pending"),
        _task(12, "pending"),
    ]
    with patch("app.api.v1.funds.ApprovalWorkflowService") as svc_cls:
        svc_cls.return_value.approve_task.side_effect = [
            SimpleNamespace(id=11, status="approved"),
            SimpleNamespace(id=12, status="approved"),
        ]
        count = _resolve_fund_approval_tasks(db, fund, "approve", operator=_admin())
    assert count == 2


def test_resolve_fund_approval_tasks_two_rejects():
    """两条待审任务连续驳回 → 驳回分支循环回边（154->140），返回完结数 2。"""
    db = MagicMock()
    fund = SimpleNamespace(id=1)
    db.query.return_value.filter.return_value.all.return_value = [
        _task(21, "pending"),
        _task(22, "pending"),
    ]
    with patch("app.api.v1.funds.ApprovalWorkflowService") as svc_cls:
        svc_cls.return_value.reject_task.side_effect = [
            SimpleNamespace(id=21, status="rejected"),
            SimpleNamespace(id=22, status="rejected"),
        ]
        count = _resolve_fund_approval_tasks(db, fund, "reject", operator=_admin(), reason="材料不全")
    assert count == 2


def test_apply_fund_approval_result_approver_missing():
    """审批人记录已不存在（first()=None）→ approved_by 保持 None（219->221）。"""
    fund = SimpleNamespace(id=1, status="pending")
    task = SimpleNamespace(id=9, status="approved", entity_id=1, current_approver_id=77)
    fund_q = MagicMock()
    fund_q.filter.return_value.first.return_value = fund
    user_q = MagicMock()
    user_q.filter.return_value.first.return_value = None
    db = MagicMock()
    db.query.side_effect = [fund_q, user_q]

    _apply_fund_approval_result(db, task)

    assert fund.approved_by is None
