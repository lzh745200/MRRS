"""app.core.data_permission 缺口补口（.coveragerc fail_under=100）。

缺失行：539-540 —— apply_scope_filter 中 OWN_DEPT 范围下 get_accessible_org_ids
返回**空列表**（非 None）时，记 debug 日志并降级为"仅本人"过滤。

为什么需要单独补口：正常口径下 get_accessible_org_ids 对 OWN_DEPT 用户至少返回
[org_id]（见 get_data_scope 与 _get_user_org_id 的联动），因此"空列表"只在权限计算
口径漂移时出现——它正是 ADR-0002 fail-closed 的兜底分支：**绝不能**返回未过滤的
query 全量放行。这里按函数契约（返回值约定明确含 ``[]``，"调用方应回退到仅本人"）
用 mock 直接驱动该分支，并用真实 SQLAlchemy Select 断言过滤条件落在 created_by 上。

构造用的用户是历史角色 manager（normalize_role → admin，但 is_admin 有意不认它）：
真实 get_data_scope 判定为 OWN_DEPT，从而走到该分支入口。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import select

import app.core.data_permission as dp
from app.models.supported_village import SupportedVillage


class TestOwnDeptEmptyOrgIdsFallback:
    """apply_scope_filter：可访问组织为空 ⇒ 仅本人（fail-closed），绝不放行全量。"""

    def test_empty_org_ids_degrades_to_owner_filter(self):
        db = MagicMock(name="db")
        user = SimpleNamespace(
            id=7,
            role="manager",          # normalize_role("manager") -> admin -> OWN_DEPT
            is_superuser=False,
            data_scope=None,
            organization_id=11,
        )
        stmt = select(SupportedVillage)

        with patch.object(dp, "get_accessible_org_ids", return_value=[]) as mock_org_ids, \
             patch.object(dp, "logger") as mock_logger:
            result = dp.apply_scope_filter(stmt, user, SupportedVillage, db=db)

        # 入参契约：按组织计算可访问范围（db 透传）
        mock_org_ids.assert_called_once_with(user, db=db)

        # 539：降级日志（debug，不是静默 pass）
        mock_logger.debug.assert_called_once()
        # 不是"模型缺组织字段"的 error 降级路径
        mock_logger.error.assert_not_called()

        # 540：过滤条件为 created_by == user.id，且未按组织过滤
        assert result is not stmt
        assert result.whereclause is not None
        where_sql = str(result.whereclause)
        assert "created_by" in where_sql
        assert "organization_id" not in where_sql
        assert 7 in result.compile().params.values()

    def test_control_non_empty_org_ids_filters_by_org(self):
        """对照组：org_ids 非空时按组织 IN 过滤（与本分支互斥）。"""
        user = SimpleNamespace(
            id=7,
            role="manager",
            is_superuser=False,
            data_scope=None,
            organization_id=11,
        )
        stmt = select(SupportedVillage)
        with patch.object(dp, "get_accessible_org_ids", return_value=[11, 12]):
            result = dp.apply_scope_filter(stmt, user, SupportedVillage, db=MagicMock(name="db"))

        where_sql = str(result.whereclause)
        assert "organization_id" in where_sql
        assert "created_by" not in where_sql
