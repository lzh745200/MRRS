# -*- coding: utf-8 -*-
"""T048：状态流转同步写操作日志回归。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1 import funds as funds_mod


def _run(target="approved", remark=None):
    db = MagicMock()
    fund = MagicMock()
    fund.id = 5
    fund.status = "pending"
    op = SimpleNamespace(id=9, username="op", full_name="操作员")
    with patch.object(funds_mod, "FundStatusHistory"), patch.object(
        funds_mod, "FundOperationLog"
    ) as oplog:
        funds_mod._transition_status(
            db, fund, target, ["pending"], operator=op, remark=remark
        )
    return oplog, db


def test_transition_writes_operation_log():
    oplog, db = _run("approved", remark="同意")
    assert oplog.call_count == 1
    kwargs = oplog.call_args.kwargs
    assert kwargs["operation_type"] == "status_approved"
    assert "approved" in kwargs["operation_detail"]
    assert "备注: 同意" in kwargs["operation_detail"]


def test_transition_without_remark_omits_note():
    oplog, _ = _run("allocated")
    assert "备注" not in oplog.call_args.kwargs["operation_detail"]


def test_log_failure_does_not_block_transition():
    db = MagicMock()
    fund = MagicMock()
    fund.id = 5
    fund.status = "pending"
    op = SimpleNamespace(id=9, username="op", full_name="x")
    with patch.object(funds_mod, "FundStatusHistory"), patch.object(
        funds_mod, "FundOperationLog", side_effect=RuntimeError("boom")
    ):
        # 日志失败不得抛出（内部 except 吞掉）
        funds_mod._transition_status(
            db, fund, "approved", ["pending"], operator=op
        )
