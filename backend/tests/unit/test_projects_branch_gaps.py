"""projects.py 分支覆盖缺口专项（分支覆盖棘轮 P0-1 清零行动）。

针对 coverage json 实测的 12 个部分分支中可直接直调函数覆盖的部分：
- `_apply_project_approval_result`：非 approved 早退 / 项目不存在或非 pending 的无变更路径；
- 三个日期 before 校验器（ProjectCreate/ProjectUpdate/TaskCreate）：v=None 的假分支；
- `_apply_project_changes`：未知字段 AttributeError → continue 的跳过路径。
其余（update 端点的 changed_fields 为空、stats 多行循环、code 冲突重试等）
需要 TestClient 级编排，留待下一轮。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.v1.projects import (
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    _apply_project_approval_result,
    _apply_project_changes,
)
from app.models.project import ProjectStatus


class TestApplyProjectApprovalResult:
    def test_skips_non_approved_task(self):
        """task 非 approved → 直接早退，不触发任何查询（L107 早退分支）。"""
        db = MagicMock()
        task = SimpleNamespace(status="rejected", entity_id=1)
        _apply_project_approval_result(db, task)
        db.query.assert_not_called()

    def test_ignores_when_project_missing(self):
        """approved 但项目不存在 → 无状态变更（L109->exit 假分支）。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        task = SimpleNamespace(status="approved", entity_id=404)
        _apply_project_approval_result(db, task)  # 不抛错即可

    def test_ignores_when_project_not_pending(self):
        """approved 但项目已非 pending（如已实施）→ 不改状态（L109->exit 假分支）。"""
        db = MagicMock()
        project = SimpleNamespace(status=ProjectStatus.IN_PROGRESS.value)
        db.query.return_value.filter.return_value.first.return_value = project
        task = SimpleNamespace(status="approved", entity_id=7)
        _apply_project_approval_result(db, task)
        assert project.status == ProjectStatus.IN_PROGRESS.value

    def test_promotes_pending_project_to_approved(self):
        """approved + pending → 状态推进为 approved（闭环正路径）。"""
        db = MagicMock()
        project = SimpleNamespace(status=ProjectStatus.PENDING.value)
        db.query.return_value.filter.return_value.first.return_value = project
        task = SimpleNamespace(status="approved", entity_id=7)
        _apply_project_approval_result(db, task)
        assert project.status == ProjectStatus.APPROVED.value


class TestDateValidatorsNoneBranch:
    """三个 before 校验器的 `if v:` 假分支（v=None → 原样返回）。"""

    def test_project_create_accepts_none_dates(self):
        assert ProjectCreate.validate_date_format(None) is None

    def test_project_update_accepts_none_dates(self):
        assert ProjectUpdate.validate_date_format(None) is None

    def test_task_create_accepts_none_due_date(self):
        assert TaskCreate.validate_date(None) is None

    def test_still_rejects_bad_format(self):
        """守门语义不回归：非法格式仍拒绝。"""
        import pytest

        with pytest.raises(ValueError, match="日期格式应为 YYYY-MM-DD"):
            ProjectCreate.validate_date_format("2026/10/07")


class TestApplyProjectChanges:
    def test_skips_unknown_fields(self):
        """未知字段（模型无此列）→ AttributeError → 跳过，不中断整批（L963 continue）。"""
        project = SimpleNamespace(name="旧名")
        changed = _apply_project_changes(project, {"name": "新名", "幽灵字段": 123})
        assert changed == ["name"]
        assert project.name == "新名"
        assert not hasattr(project, "幽灵字段")

    def test_dedupes_unchanged_fields(self):
        """值未变化 → 不记入 changed_fields，但仍 setattr（幂等）。"""
        project = SimpleNamespace(name="同名", progress=50)
        changed = _apply_project_changes(project, {"name": "同名", "progress": 80})
        assert changed == ["progress"]
        assert project.progress == 80
