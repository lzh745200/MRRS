"""app.api.v1.organization 覆盖补全：无组织归属的 fail-closed 守卫。

- line 485 —— /my-organization 对"账号未关联组织"返回 404，绝不回退到
  "第一个活跃组织"（历史实现会把他人组织当成本人的，多组织部署下误导用户并让
  后续接口以错误归属提交数据）。
- lines 526-530 —— /subordinates 的组织范围收敛：非超管只能看自己组织的子树，
  无组织归属直接拒绝（历史实现对任意登录用户返回整张组织表 = 跨单位架构外泄）。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.organization import get_my_organization, get_subordinates


def _chained_db():
    db = MagicMock(name="db")
    for name in ("query", "filter", "order_by", "offset", "limit", "options", "join"):
        getattr(db, name).return_value = db
    db.all.return_value = []
    db.first.return_value = None
    return db


def _applied_filters(db) -> str:
    """把 db.filter(...) 收到的所有条件拼成一个可断言的字符串（大写归一）。"""
    return " ".join(
        str(arg) for call in db.filter.call_args_list for arg in call.args
    ).upper()


def _user(**over):
    base = dict(id=2, username="bob", full_name="张三", role="user",
                is_superuser=False, is_active=True, organization_id=7)
    base.update(over)
    return SimpleNamespace(**base)


class TestMyOrganizationWithoutOrg:
    """/my-organization：无组织归属 → 404（line 485）。"""

    @pytest.mark.parametrize("missing_org", [None, 0])
    async def test_no_org_membership_returns_404(self, missing_org):
        db = _chained_db()

        with pytest.raises(HTTPException) as excinfo:
            await get_my_organization(
                current_user=_user(organization_id=missing_org), db=db,
            )

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "当前用户未关联任何组织"
        # 无组织即无组织上下文：绝不发起任何"兜底"组织查询
        db.query.assert_not_called()
        db.first.assert_not_called()

    async def test_disabled_org_returns_404_without_fallback(self):
        """对照组：有组织归属但组织已停用/不存在 → 404（不走 line 485 的兜底改写）。"""
        db = _chained_db()
        db.first.return_value = None

        with pytest.raises(HTTPException) as excinfo:
            await get_my_organization(current_user=_user(organization_id=7), db=db)

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "当前用户所属组织不存在或已停用"


class TestGetSubordinatesScope:
    """/subordinates：组织子树范围收敛（lines 526-530）。"""

    async def test_non_superuser_is_limited_to_own_subtree(self):
        db = _chained_db()
        db.all.return_value = ["org-7", "org-8"]

        with patch(
            "app.core.data_permission._get_org_subtree",
            return_value=([7, 8], ["本级", "下级"]),
        ) as subtree:
            result = await get_subordinates(
                include_self=True, current_user=_user(), db=db,
            )

        subtree.assert_called_once_with(db, 7)
        assert result == ["org-7", "org-8"]
        # 过滤条件必须包含"本组织子树"白名单
        applied = _applied_filters(db)
        assert "ORGANIZATIONS.ID IN" in applied

    async def test_empty_subtree_falls_back_to_own_org_id(self):
        """子树解析为空（组织树断链）时退化为"仅本组织"，绝不放开全表。"""
        db = _chained_db()
        db.all.return_value = ["org-7"]

        with patch(
            "app.core.data_permission._get_org_subtree", return_value=([], []),
        ) as subtree:
            result = await get_subordinates(
                include_self=False, current_user=_user(), db=db,
            )

        subtree.assert_called_once_with(db, 7)
        assert result == ["org-7"]
        applied = _applied_filters(db)
        assert "ORGANIZATIONS.ID IN" in applied

    async def test_superuser_skips_subtree_restriction(self):
        """对照组：超管不受子树约束（不解析子树、不加 IN 白名单）。"""
        db = _chained_db()
        db.all.return_value = ["org-1", "org-2"]

        with patch("app.core.data_permission._get_org_subtree") as subtree:
            result = await get_subordinates(
                include_self=True,
                current_user=_user(role="super_admin", is_superuser=True),
                db=db,
            )

        subtree.assert_not_called()
        assert result == ["org-1", "org-2"]
        assert "ORGANIZATIONS.ID IN" not in _applied_filters(db)

    async def test_non_superuser_without_org_is_rejected(self):
        """无组织归属的非超管：守卫拒绝（line 528），一行组织数据都不读出。

        行为说明：line 528 抛的是 403，但本函数末尾的宽 except Exception 会把
        HTTPException（Exception 的子类）重新包装成 500 —— 仍然是 fail-closed
        （请求被拒 + 不返回任何组织数据）。本轮规则只允许改测试文件，故此处
        锁定真实可观测行为，同时断言"没有读出任何数据"。
        """
        db = _chained_db()

        with pytest.raises(HTTPException) as excinfo:
            await get_subordinates(
                include_self=False, current_user=_user(organization_id=None), db=db,
            )

        assert excinfo.value.status_code == 500
        assert "获取下级组织失败" in excinfo.value.detail
        # 拒绝发生在取数据之前：不泄漏任何组织行
        db.all.assert_not_called()
        db.order_by.assert_not_called()
