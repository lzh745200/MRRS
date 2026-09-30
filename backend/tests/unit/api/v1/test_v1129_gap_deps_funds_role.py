"""v1.12.9 覆盖率补口：app/api/v1/deps.py 经费操作角色 allowlist（W15 深审 #36）。

覆盖行（当前代码行号）：
- 66-67 空 / 非字符串角色直接 403（fail-closed）：
  normalize_role 会把空值兜底成 user，沿用兜底等于给"未分配角色"账号发写权限；
- 72-73 归一化后不在白名单（super_admin/admin/user）内一律 403，
  原 denylist 实现让拼写错误、脏数据、历史未知角色全部被放行。
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.deps import require_funds_operator_role


def _actor(role, is_superuser=False):
    return SimpleNamespace(role=role, is_superuser=is_superuser)


class TestFundsOperatorRoleAllowlist:
    @pytest.mark.parametrize("role", ["super_admin", "admin", "user"])
    def test_allowlisted_roles_pass(self, role):
        assert require_funds_operator_role(_actor(role)) is None

    def test_legacy_roles_normalized_into_allowlist(self):
        # approval_leader/manager → admin，operator → user（历史角色不降级）
        assert require_funds_operator_role(_actor("manager")) is None
        assert require_funds_operator_role(_actor("approval_leader")) is None
        assert require_funds_operator_role(_actor("operator")) is None

    def test_superuser_flag_passes_even_with_unknown_role(self):
        assert require_funds_operator_role(_actor("legacy_unknown", is_superuser=True)) is None

    def test_viewer_rejected(self):
        with pytest.raises(HTTPException) as ei:
            require_funds_operator_role(_actor("viewer"))
        assert ei.value.status_code == 403
        assert "viewer" in ei.value.detail

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_missing_role_fail_closed(self, raw):
        with pytest.raises(HTTPException) as ei:
            require_funds_operator_role(_actor(raw))
        assert ei.value.status_code == 403
        assert "未分配有效角色" in ei.value.detail

    def test_non_string_role_fail_closed(self):
        """枚举 / 数字等非字符串角色同样拒绝（原先会落进装饰器分支被静默跳过）。"""
        with pytest.raises(HTTPException) as ei:
            require_funds_operator_role(_actor(123))
        assert ei.value.status_code == 403
        assert "未分配有效角色" in ei.value.detail

    def test_unknown_role_rejected_by_allowlist(self):
        with pytest.raises(HTTPException) as ei:
            require_funds_operator_role(_actor("auditor"))
        assert ei.value.status_code == 403
        assert "无权操作经费数据" in ei.value.detail
