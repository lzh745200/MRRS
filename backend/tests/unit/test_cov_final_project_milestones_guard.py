"""app.api.v1.project_milestones 覆盖补全：里程碑归属不匹配的 404 守卫。

- lines 130-136 —— GET 项目里程碑列表（项目可见 → 按 sort_order/planned_date 返回）。
- line 180 —— PUT 里程碑：id 存在但不属于该项目 / 不存在 → 404。
- line 220 —— DELETE 里程碑：同样按 (id, project_id) 双条件取，取不到 → 404。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.project_milestones import (
    MilestoneUpdate,
    delete_milestone,
    get_milestones,
    update_milestone,
)


def _chained_db():
    db = MagicMock(name="db")
    for name in ("query", "filter", "order_by", "offset", "limit", "options", "join"):
        getattr(db, name).return_value = db
    db.first.return_value = None
    db.all.return_value = []
    return db


def _user():
    return SimpleNamespace(
        id=1, username="admin", role="admin", is_superuser=True,
        is_active=True, organization_id=1,
    )


def _accessible_project():
    """数据域守卫放行（等价于 scoped_filter 命中了该项目）。"""
    return patch(
        "app.api.v1.project_milestones._get_accessible_project_or_404",
        return_value=SimpleNamespace(id=1, name="道路工程"),
    )


class TestGetMilestones:
    async def test_returns_rows_in_sort_order(self):
        """项目可见 → 返回查询到的里程碑（lines 130-136）。"""
        db = _chained_db()
        db.all.return_value = ["m1", "m2"]

        with _accessible_project():
            rows = await get_milestones(project_id=1, current_user=_user(), db=db)

        assert rows == ["m1", "m2"]
        # 列表查询按 (sort_order, planned_date) 排序
        assert "sort_order" in str(db.order_by.call_args.args[0])

    async def test_empty_list(self):
        db = _chained_db()
        with _accessible_project():
            assert await get_milestones(project_id=1, current_user=_user(), db=db) == []


class TestMilestoneNotFound:
    async def test_update_missing_milestone_returns_404(self):
        """里程碑不存在（或属于别的项目）→ 404，不落任何写操作（line 180）。"""
        db = _chained_db()
        db.first.return_value = None

        with _accessible_project():
            with pytest.raises(HTTPException) as excinfo:
                await update_milestone(
                    project_id=1, milestone_id=99,
                    data=MilestoneUpdate(name="不存在的里程碑"),
                    current_user=_user(), db=db,
                )

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "里程碑不存在"
        db.add.assert_not_called()
        db.commit.assert_not_called()

    async def test_update_requires_milestone_to_belong_to_project(self):
        """查询同时按 milestone_id 与 project_id 约束，防止跨项目改里程碑。"""
        db = _chained_db()
        db.first.return_value = None

        with _accessible_project():
            with pytest.raises(HTTPException) as excinfo:
                await update_milestone(
                    project_id=42, milestone_id=99,
                    data=MilestoneUpdate(status="completed"),
                    current_user=_user(), db=db,
                )

        assert excinfo.value.status_code == 404
        condition = " ".join(str(arg) for arg in db.filter.call_args.args)
        assert "project_milestones.project_id" in condition
        assert "project_milestones.id" in condition

    async def test_delete_missing_milestone_returns_404(self):
        """删除同样双条件取记录，取不到 → 404 且不执行 delete（line 220）。"""
        db = _chained_db()
        db.first.return_value = None

        with _accessible_project():
            with pytest.raises(HTTPException) as excinfo:
                await delete_milestone(
                    project_id=1, milestone_id=99, current_user=_user(), db=db,
                )

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "里程碑不存在"
        db.delete.assert_not_called()
        db.commit.assert_not_called()
