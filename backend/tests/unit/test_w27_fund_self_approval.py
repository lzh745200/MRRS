"""W27 P1 回归：经费「不能自批」（财务内控 / 审计要求）。

## 缺陷
`approve_fund` 原先只校验操作角色与数据域，**不校验创建人** —— 录入人可以直接
审批自己创建的经费记录，"录入—审批"合一，资金类数据失去双人复核的意义。
（同类控制缺失也出现在组织授权包、审批门禁等处，本项目按 fail-closed 统一处理。）

## 语义（见 `_assert_can_approve_fund`）
* `FUND_ALLOW_SELF_APPROVAL=True` → 放行（单操作员部署的显式例外）；
* 超级管理员 → 放行（单机部署的最终审核人，避免自我死锁）；
* 其余情况 创建人 == 审批人 → 403。
* **驳回不受限**：驳回自己的提交不会让资金流出，现场常需自行撤回。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.funds import _assert_can_approve_fund


def _user(uid=1, is_superuser=False):
    return SimpleNamespace(id=uid, is_superuser=is_superuser, role="admin",
                           username="u", full_name="U")


def _fund(created_by=1):
    return SimpleNamespace(id=10, created_by=created_by, status="pending")


class TestFundSelfApprovalGuard:
    def test_creator_cannot_approve_own_fund(self):
        with pytest.raises(HTTPException) as ei:
            _assert_can_approve_fund(_fund(created_by=1), _user(uid=1))
        assert ei.value.status_code == 403
        assert "不能审批自己创建" in ei.value.detail

    def test_other_user_can_approve(self):
        _assert_can_approve_fund(_fund(created_by=1), _user(uid=2))  # 不抛

    def test_superuser_may_self_approve(self):
        """单机部署的最终审核人 —— 避免"只有一个人"时永远无法审批。"""
        _assert_can_approve_fund(_fund(created_by=1), _user(uid=1, is_superuser=True))

    def test_config_exception_allows_self_approval(self):
        with patch("app.api.v1.funds.settings") as s:
            s.FUND_ALLOW_SELF_APPROVAL = True
            _assert_can_approve_fund(_fund(created_by=1), _user(uid=1))

    def test_default_config_forbids(self):
        """默认配置必须是禁止（fail-closed）。"""
        from app.core.config import settings

        assert settings.FUND_ALLOW_SELF_APPROVAL is False

    def test_missing_creator_is_allowed(self):
        """历史数据 created_by 为 NULL → 无法判定归属，放行（不阻断审批流程）。"""
        _assert_can_approve_fund(_fund(created_by=None), _user(uid=1))


class TestApproveEndpointWiring:
    def test_approve_endpoint_calls_guard(self):
        """端点确实接线了守卫（防重构时静默丢失）。"""
        import inspect

        from app.api.v1 import funds as mod

        src = inspect.getsource(mod.approve_fund)
        assert "_assert_can_approve_fund" in src

    def test_reject_endpoint_has_no_self_guard(self):
        """驳回不受限（有意为之）。"""
        import inspect

        from app.api.v1 import funds as mod

        src = inspect.getsource(mod.reject_fund)
        assert "_assert_can_approve_fund" not in src
