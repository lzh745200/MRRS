"""W27：审批「真门禁」回归测试。

## 背景（W26 全栈检测跨域共性问题 C2「审批伪闭环」）
帮扶村 / 学校 / 政策三类实体的写操作此前都会创建审批任务，但：

* 回写处理器是空实现 ``_ = (db, task)``；
* 变更在提交时**已即时落库**，驳回也不回滚。

结果是审批中心里的「通过/驳回」对这三类实体零效果，纯装饰。

## 本文件锁定真门禁的三条语义
1. **管理员直通**（单机运维闭环）、**非管理员门控**（不落库，只建 pending 任务）；
2. 审批通过 → 回写处理器**真正写入**；
3. 审批任务无法创建时必须拒绝整次请求（不允许"既没落库也没任务"的静默丢失）。
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import approval_gate as gate


def _user(uid=1, role="user", is_superuser=False):
    return SimpleNamespace(id=uid, role=role, is_superuser=is_superuser, username=f"u{uid}")


def _task(**kw):
    defaults = dict(id=99, entity_id=1, change_data=None, original_data=None, status="approved")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ══════════════════════════════════════════════════════════════════
# 1. requires_approval —— 门控开关
# ══════════════════════════════════════════════════════════════════


class TestRequiresApproval:
    def test_normal_user_requires_approval(self):
        assert gate.requires_approval(_user(role="user")) is True

    def test_viewer_requires_approval(self):
        assert gate.requires_approval(_user(role="viewer")) is True

    def test_department_admin_passes_through(self):
        """管理员直通：单机部署常见"录入者即审批者"，强制审批会自我死锁。"""
        assert gate.requires_approval(_user(role="admin")) is False

    def test_super_admin_passes_through(self):
        assert gate.requires_approval(_user(role="super_admin")) is False

    def test_is_superuser_flag_passes_through(self):
        assert gate.requires_approval(_user(role="user", is_superuser=True)) is False


# ══════════════════════════════════════════════════════════════════
# 2. open_change_approval —— 任务创建 + 失败即拒绝
# ══════════════════════════════════════════════════════════════════


class TestOpenChangeApproval:
    def test_returns_task_id_on_success(self, monkeypatch):
        monkeypatch.setattr(gate, "submit_entity_change_approval", lambda *a, **k: 77)
        db = MagicMock()
        task_id = gate.open_change_approval(
            db, current_user=_user(), entity_type="school", entity_id=5,
            title="学校变更", change_data={"name": "新名"}, original_data={"name": "旧名"},
        )
        assert task_id == 77

    def test_raises_when_task_cannot_be_created(self, monkeypatch):
        """无法建任务 → 400 拒绝整次请求（不允许静默丢失）。"""
        monkeypatch.setattr(gate, "submit_entity_change_approval", lambda *a, **k: None)
        with pytest.raises(HTTPException) as ei:
            gate.open_change_approval(
                MagicMock(), current_user=_user(), entity_type="school", entity_id=5,
                title="学校变更",
            )
        assert ei.value.status_code == 400
        assert "审批" in ei.value.detail

    def test_passes_submitter_and_payload_through(self, monkeypatch):
        captured = {}

        def fake(db, **kw):
            captured.update(kw)
            return 1

        monkeypatch.setattr(gate, "submit_entity_change_approval", fake)
        gate.open_change_approval(
            MagicMock(), current_user=_user(uid=42), entity_type="supported_village",
            entity_id=9, title="t", change_data={"a": 1}, original_data={"a": 0},
        )
        assert captured["submitter_id"] == 42
        assert captured["entity_type"] == "supported_village"
        assert captured["entity_id"] == 9
        assert captured["change_data"] == {"a": 1}
        assert captured["original_data"] == {"a": 0}


# ══════════════════════════════════════════════════════════════════
# 3. apply_field_changes —— 逐字段应用
# ══════════════════════════════════════════════════════════════════


class TestApplyFieldChanges:
    def test_applies_existing_fields(self):
        record = SimpleNamespace(name="旧", district="A")
        applied = gate.apply_field_changes(record, {"name": "新", "district": "B"})
        assert applied == 2
        assert record.name == "新" and record.district == "B"

    def test_skips_reserved_keys(self):
        record = SimpleNamespace(name="旧")
        applied = gate.apply_field_changes(record, {"__deleted__": True, "name": "新"})
        assert applied == 1
        assert record.name == "新"
        assert not hasattr(record, "__deleted__")

    def test_skips_immutable_fields(self):
        """主键与归属审计列不得被审批回写覆盖。"""
        record = SimpleNamespace(id=1, created_by=1, created_at="t", organization_id=1, name="旧")
        applied = gate.apply_field_changes(
            record,
            {"id": 999, "created_by": 999, "created_at": "x", "organization_id": 999, "name": "新"},
        )
        assert applied == 1
        assert record.id == 1
        assert record.created_by == 1
        assert record.organization_id == 1
        assert record.name == "新"

    def test_unknown_field_is_skipped(self):
        record = SimpleNamespace(name="旧")
        applied = gate.apply_field_changes(record, {"not_a_field": 1, "name": "新"})
        assert applied == 1

    def test_none_change_data(self):
        assert gate.apply_field_changes(SimpleNamespace(), None) == 0

    def test_non_str_key_ignored(self):
        record = SimpleNamespace(name="旧")
        assert gate.apply_field_changes(record, {1: "x", "name": "新"}) == 1


class TestMarkers:
    def test_delete_marker(self):
        assert gate.is_delete_marker({gate.DELETED_KEY: True}) is True
        assert gate.is_delete_marker({"name": "x"}) is False
        assert gate.is_delete_marker(None) is False

    def test_restore_marker(self):
        assert gate.is_restore_marker({gate.RESTORED_KEY: True}) is True
        assert gate.is_restore_marker({gate.DELETED_KEY: True}) is False
        assert gate.is_restore_marker(None) is False


# ══════════════════════════════════════════════════════════════════
# 4. 帮扶村回写处理器
# ══════════════════════════════════════════════════════════════════


class TestVillageApplyHandler:
    def _run(self, task, village):
        from app.api.v1.supported_village import _apply_village_approval_result

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = village
        _apply_village_approval_result(db, task)
        return db

    def test_delete_marker_soft_deletes(self):
        village = SimpleNamespace(village_name="某村", is_active=True, deleted_at=None)
        self._run(_task(change_data={gate.DELETED_KEY: True}), village)
        assert village.is_active is False
        assert isinstance(village.deleted_at, datetime)

    def test_update_applies_fields(self):
        village = SimpleNamespace(village_name="旧名", transition_status="none")
        self._run(_task(change_data={"village_name": "新名"}), village)
        assert village.village_name == "新名"

    def test_missing_entity_id_returns(self):
        db = MagicMock()
        from app.api.v1.supported_village import _apply_village_approval_result

        _apply_village_approval_result(db, _task(entity_id=None))
        db.query.assert_not_called()

    def test_missing_village_returns(self):
        db = self._run(_task(change_data={"village_name": "x"}), None)
        db.flush.assert_not_called()

    def test_empty_change_data_logs_and_flushes(self):
        village = SimpleNamespace(village_name="某村")
        db = self._run(_task(change_data={}), village)
        db.flush.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# 5. 学校回写处理器
# ══════════════════════════════════════════════════════════════════


class TestSchoolApplyHandler:
    def _run(self, task, school):
        from app.api.v1.school import _apply_school_approval_result

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = school
        _apply_school_approval_result(db, task)
        return db

    def test_delete_marker_soft_deletes(self):
        school = SimpleNamespace(name="某校", is_active=True, deleted_at=None)
        self._run(_task(change_data={gate.DELETED_KEY: True}), school)
        assert school.is_active is False
        assert isinstance(school.deleted_at, datetime)

    def test_update_applies_fields(self):
        school = SimpleNamespace(name="旧校名", district="A")
        self._run(_task(change_data={"name": "新校名"}), school)
        assert school.name == "新校名"

    def test_missing_entity_id_returns(self):
        from app.api.v1.school import _apply_school_approval_result

        db = MagicMock()
        _apply_school_approval_result(db, _task(entity_id=None))
        db.query.assert_not_called()

    def test_missing_school_returns(self):
        db = self._run(_task(change_data={"name": "x"}), None)
        db.flush.assert_not_called()

    def test_empty_change_data_flushes(self):
        school = SimpleNamespace(name="某校")
        db = self._run(_task(change_data={}), school)
        db.flush.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# 6. 政策回写处理器
# ══════════════════════════════════════════════════════════════════


class TestPolicyApplyHandler:
    KEY = "__target_status__"

    def _run(self, task, policy):
        from app.api.v1.policy import _apply_policy_approval_result

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = policy
        _apply_policy_approval_result(db, task)
        return db

    def test_publish_target_applied(self):
        policy = SimpleNamespace(title="某政策", status="draft")
        self._run(_task(change_data={self.KEY: "active"}), policy)
        assert policy.status == "active"

    def test_archive_target_applied(self):
        policy = SimpleNamespace(title="某政策", status="active")
        self._run(_task(change_data={self.KEY: "invalid"}), policy)
        assert policy.status == "invalid"

    def test_invalid_target_rejected(self):
        """白名单外的目标状态一律不写库。"""
        policy = SimpleNamespace(title="某政策", status="active")
        self._run(_task(change_data={self.KEY: "deleted"}), policy)
        assert policy.status == "active"

    def test_missing_entity_id_returns(self):
        from app.api.v1.policy import _apply_policy_approval_result

        db = MagicMock()
        _apply_policy_approval_result(db, _task(entity_id=None, change_data={self.KEY: "active"}))
        db.query.assert_not_called()

    def test_missing_policy_returns(self):
        db = self._run(_task(change_data={self.KEY: "active"}), None)
        db.flush.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# 7. 端点门控接入（非管理员路径不落库、只建 pending 任务）
# ══════════════════════════════════════════════════════════════════


class TestVillageEndpointGate:
    """帮扶村 update/delete 的门控分支。"""

    @pytest.mark.asyncio
    async def test_update_village_non_admin_does_not_write(self, monkeypatch):
        from app.api.v1 import supported_village as sv

        village = SimpleNamespace(id=5, village_name="某村", transition_status=None)
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: village)
        monkeypatch.setattr(sv, "requires_approval", lambda u: True)
        monkeypatch.setattr(sv, "open_change_approval", lambda *a, **k: 42)
        monkeypatch.setattr(sv, "_village_to_diff_dict", lambda v: {"village_name": v.village_name})

        data = MagicMock()
        data.model_dump.return_value = {"village_name": "被篡改"}
        resp = await sv.update_village(5, data, current_user=_user(), db=MagicMock())

        assert resp["data"]["pending_approval"] is True
        assert resp["data"]["approval_task_id"] == 42
        # 关键：实体未被修改
        assert village.village_name == "某村"

    @pytest.mark.asyncio
    async def test_delete_village_non_admin_does_not_write(self, monkeypatch):
        from app.api.v1 import supported_village as sv

        village = SimpleNamespace(id=5, village_name="某村", is_active=True, deleted_at=None)
        monkeypatch.setattr(sv, "_get_village_or_404", lambda *a, **k: village)
        monkeypatch.setattr(sv, "requires_approval", lambda u: True)
        monkeypatch.setattr(sv, "open_change_approval", lambda *a, **k: 43)
        monkeypatch.setattr(sv, "_village_to_diff_dict", lambda v: {})

        resp = await sv.delete_village(5, current_user=_user(), db=MagicMock())

        assert resp["data"]["pending_approval"] is True
        assert village.is_active is True   # 未软删


class TestSchoolEndpointGate:
    """学校 update/delete 的门控分支。"""

    @staticmethod
    def _school(**kw):
        defaults = dict(id=7, name="某校", organization_id=1, created_by=1, code="S-1",
                        is_active=True, deleted_at=None, district=None)
        defaults.update(kw)
        obj = SimpleNamespace(**defaults)
        obj.to_dict = lambda: {"id": obj.id, "name": obj.name, "code": obj.code}
        return obj

    @pytest.mark.asyncio
    async def test_update_school_non_admin_does_not_write(self, monkeypatch):
        from app.api.v1 import school as sch

        school = self._school()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = school
        monkeypatch.setattr(sch, "require_data_permission", lambda *a, **k: None)
        monkeypatch.setattr(sch, "requires_approval", lambda u: True)
        monkeypatch.setattr(sch, "open_change_approval", lambda *a, **k: 44)

        data = MagicMock()
        data.model_dump.return_value = {"name": "被篡改"}
        resp = await sch.update_school(7, data, current_user=_user(), db=db)

        assert resp["data"]["pending_approval"] is True
        assert school.name == "某校"

    @pytest.mark.asyncio
    async def test_delete_school_non_admin_does_not_write(self, monkeypatch):
        from app.api.v1 import school as sch

        school = self._school()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = school
        monkeypatch.setattr(sch, "require_data_permission", lambda *a, **k: None)
        monkeypatch.setattr(sch, "requires_approval", lambda u: True)
        monkeypatch.setattr(sch, "open_change_approval", lambda *a, **k: 45)

        resp = await sch.delete_school(7, current_user=_user(), db=db)

        assert resp["data"]["pending_approval"] is True
        assert school.is_active is True


class TestPolicyEndpointGate:
    """政策 publish/archive 的门控分支。"""

    def _policy(self):
        return SimpleNamespace(id=3, title="某政策", status="draft", created_by=1)

    @pytest.mark.asyncio
    async def test_publish_non_admin_keeps_status(self, monkeypatch):
        from app.api.v1 import policy as pol

        policy = self._policy()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = policy
        monkeypatch.setattr(pol, "require_policy_operator_role", lambda u: None)
        monkeypatch.setattr(pol, "_assert_policy_writable", lambda p, u: None)
        monkeypatch.setattr(pol, "requires_approval", lambda u: True)
        monkeypatch.setattr(pol, "open_change_approval", lambda *a, **k: 46)

        resp = await pol.publish_policy(3, current_user=_user(), db=db)

        assert resp["data"]["pending_approval"] is True
        assert policy.status == "draft"   # 未发布

    @pytest.mark.asyncio
    async def test_archive_non_admin_keeps_status(self, monkeypatch):
        from app.api.v1 import policy as pol

        policy = self._policy()
        policy.status = "active"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = policy
        monkeypatch.setattr(pol, "require_policy_operator_role", lambda u: None)
        monkeypatch.setattr(pol, "_assert_policy_writable", lambda p, u: None)
        monkeypatch.setattr(pol, "requires_approval", lambda u: True)
        monkeypatch.setattr(pol, "open_change_approval", lambda *a, **k: 47)

        resp = await pol.archive_policy(3, current_user=_user(), db=db)

        assert resp["data"]["pending_approval"] is True
        assert policy.status == "active"   # 未归档
