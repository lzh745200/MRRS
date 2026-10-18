"""工作移交服务层单测（w17-004）：清单/选择/归属改写/消息/审计/历史 全分支。"""

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.approval import ApprovalStatus, ApprovalTask, ApprovalWorkflow
from app.models.message import Message
from app.models.organization import Organization  # noqa: F401 - FK 目标表
from app.models.project import Project
from app.models.supported_village import SupportedVillage
from app.models.todo import Todo
from app.models.user import User
from app.models.work_log import WorkLog
from app.services import handover_service
from app.services.handover_service import (
    _apply_ownership,
    _assert_moved,
    _audit_detail,
    _build_snapshot,
    _history_item,
    _parse_snapshot,
    _select_assets,
    _split_scope,
    _summary_text,
    _transfer_approvals,
    _validate_item_ids,
    _write_notifications,
    assert_handover_target,
    build_inventory,
    execute_handover,
    generate_record_no,
    list_candidates,
    query_history,
)


# ════════════════════════════════════════════════════════════════════
#  fixtures / helpers
# ════════════════════════════════════════════════════════════════════


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _actor(**kw):
    base = dict(
        id=7,
        username="zhangsan",
        full_name="张三",
        role="admin",
        organization_id=1,
        is_superuser=False,
        is_active=True,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _mk_user(db, username="lisi", org_id=1, active=True, role="user", full_name="李四", uid=None):
    user = User(
        id=uid,
        username=username,
        hashed_password="x",
        organization_id=org_id,
        is_active=active,
        role=role,
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_village(
    db, name="幸福村", created_by=7, org_id=1, active=True, province="贵州省",
    city="贵阳市", county="修文县",
):
    village = SupportedVillage(
        village_name=name,
        created_by=created_by,
        organization_id=org_id,
        is_active=active,
        province=province,
        city=city,
        county=county,
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _mk_project(db, name="道路硬化", created_by=7, org_id=1, active=True, status="in_progress"):
    project = Project(
        name=name,
        created_by=created_by,
        organization_id=org_id,
        is_active=active,
        status=status,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _mk_todo(db, title="走访农户", user_id=7, completed=False, deadline="2026-11-01"):
    todo = Todo(title=title, user_id=user_id, completed=completed, deadline=deadline)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


def _mk_workflow(db, entity_type="project"):
    workflow = ApprovalWorkflow(name=f"{entity_type}流程", entity_type=entity_type, is_active=True)
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def _mk_approval(db, *, submitter_id=7, approver_id=7, status="pending", title=None,
                 entity_type="project", entity_id=1, workflow=None):
    workflow = workflow or _mk_workflow(db, entity_type)
    task = ApprovalTask(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=entity_id,
        submitter_id=submitter_id,
        current_level=1,
        current_approver_id=approver_id,
        status=status,
        title=title,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _inventory_by_type(inventory):
    return {group["type"]: group for group in inventory["groups"]}


# ════════════════════════════════════════════════════════════════════
#  基础工具
# ════════════════════════════════════════════════════════════════════


class TestBasicHelpers:
    def test_generate_record_no_with_explicit_now(self):
        record_no = generate_record_no(datetime(2026, 10, 17, 8, 30, 0, tzinfo=timezone.utc))
        assert record_no.startswith("HO-20261017-083000-")
        assert len(record_no) == len("HO-20261017-083000-") + 8

    def test_generate_record_no_defaults_to_now(self):
        assert generate_record_no().startswith("HO-")

    def test_split_scope_none_returns_all_types(self):
        assert _split_scope(None) == list(handover_service.ASSET_TYPES)

    def test_split_scope_dedupes_and_keeps_order(self):
        assert _split_scope(["todo", "village", "todo"]) == ["todo", "village"]

    def test_split_scope_rejects_non_sequence(self):
        with pytest.raises(HTTPException) as ei:
            _split_scope("village")
        assert ei.value.status_code == 422

    def test_split_scope_rejects_unknown_type(self):
        with pytest.raises(HTTPException) as ei:
            _split_scope(["village", "unknown"])
        assert ei.value.status_code == 422
        assert "unknown" in ei.value.detail

    def test_split_scope_rejects_empty_selection(self):
        with pytest.raises(HTTPException) as ei:
            _split_scope([])
        assert ei.value.status_code == 422

    def test_validate_item_ids_none_is_noop(self):
        _validate_item_ids(None, ["village"])

    def test_validate_item_ids_rejects_non_dict(self):
        with pytest.raises(HTTPException) as ei:
            _validate_item_ids(["village"], ["village"])
        assert ei.value.status_code == 422

    def test_validate_item_ids_rejects_unknown_type(self):
        with pytest.raises(HTTPException) as ei:
            _validate_item_ids({"alien": [1]}, ["village"])
        assert ei.value.status_code == 422

    def test_validate_item_ids_rejects_out_of_scope_type(self):
        with pytest.raises(HTTPException) as ei:
            _validate_item_ids({"todo": [1]}, ["village"])
        assert ei.value.status_code == 422
        assert "范围" in ei.value.detail

    def test_validate_item_ids_rejects_non_list_value(self):
        with pytest.raises(HTTPException) as ei:
            _validate_item_ids({"village": 1}, ["village"])
        assert ei.value.status_code == 422

    def test_validate_item_ids_accepts_valid_payload(self):
        _validate_item_ids({"village": [1, 2]}, ["village"])

    def test_summary_text_skips_zero_counts(self):
        text = _summary_text({"village": 2, "project": 0, "todo": 1, "approval": 0})
        assert text == "帮扶村 2 项、待办事项 1 项"

    def test_summary_text_all_zero_is_empty(self):
        assert _summary_text({}) == ""

    def test_assert_moved_equal_is_noop(self):
        _assert_moved("village", 2, 2)

    def test_assert_moved_mismatch_raises_conflict(self):
        with pytest.raises(HTTPException) as ei:
            _assert_moved("project", 1, 2)
        assert ei.value.status_code == 409
        assert "帮扶项目" in ei.value.detail


# ════════════════════════════════════════════════════════════════════
#  接任人校验
# ════════════════════════════════════════════════════════════════════


class TestAssertHandoverTarget:
    def test_missing_target_404(self):
        with pytest.raises(HTTPException) as ei:
            assert_handover_target(_actor(), None)
        assert ei.value.status_code == 404

    def test_self_target_422(self):
        actor = _actor()
        with pytest.raises(HTTPException) as ei:
            assert_handover_target(actor, SimpleNamespace(id=7, is_active=True))
        assert ei.value.status_code == 422

    def test_inactive_target_404(self):
        actor = _actor()
        target = SimpleNamespace(id=8, is_active=False, organization_id=1)
        with pytest.raises(HTTPException) as ei:
            assert_handover_target(actor, target)
        assert ei.value.status_code == 404

    def test_cross_org_target_403(self):
        actor = _actor(organization_id=1)
        target = SimpleNamespace(id=8, is_active=True, organization_id=2)
        with pytest.raises(HTTPException) as ei:
            assert_handover_target(actor, target)
        assert ei.value.status_code == 403
        assert "跨组织" in ei.value.detail

    def test_actor_without_org_is_fail_closed(self):
        actor = _actor(organization_id=None)
        target = SimpleNamespace(id=8, is_active=True, organization_id=None)
        with pytest.raises(HTTPException) as ei:
            assert_handover_target(actor, target)
        assert ei.value.status_code == 403

    def test_same_org_target_passes(self):
        actor = _actor(organization_id=1)
        assert_handover_target(actor, SimpleNamespace(id=8, is_active=True, organization_id=1))

    def test_superuser_may_cross_org(self):
        actor = _actor(is_superuser=True, organization_id=1)
        assert_handover_target(actor, SimpleNamespace(id=8, is_active=True, organization_id=2))


# ════════════════════════════════════════════════════════════════════
#  接任人列表
# ════════════════════════════════════════════════════════════════════


class TestListCandidates:
    def test_same_org_active_users_excluding_self(self, db):
        _mk_user(db, username="lisi", org_id=1)
        _mk_user(db, username="wangwu", org_id=1)
        _mk_user(db, username="other", org_id=2)
        _mk_user(db, username="disabled", org_id=1, active=False)
        _mk_user(db, username="zhangsan", org_id=1)  # 本人（id != 7，但按 id 过滤）
        candidates = list_candidates(db, _actor())
        usernames = {row["username"] for row in candidates}
        assert "lisi" in usernames
        assert "wangwu" in usernames
        assert "other" not in usernames
        assert "disabled" not in usernames
        assert all(row["organization_id"] == 1 for row in candidates)

    def test_actor_without_org_gets_empty_list(self, db):
        _mk_user(db, username="lisi", org_id=1)
        assert list_candidates(db, _actor(organization_id=None)) == []

    def test_superuser_sees_all_orgs(self, db):
        _mk_user(db, username="lisi", org_id=1)
        _mk_user(db, username="other", org_id=2)
        candidates = list_candidates(db, _actor(is_superuser=True))
        assert {row["username"] for row in candidates} >= {"lisi", "other"}

    def test_keyword_filter_and_limit_clamp(self, db):
        _mk_user(db, username="lisi", org_id=1, full_name="李四")
        _mk_user(db, username="wangwu", org_id=1, full_name="王五")
        by_keyword = list_candidates(db, _actor(), keyword="李")
        assert [row["username"] for row in by_keyword] == ["lisi"]
        assert len(list_candidates(db, _actor(), limit=0)) >= 1
        assert len(list_candidates(db, _actor(), limit=9999)) >= 1
        assert len(list_candidates(db, _actor(), limit=-3)) >= 1

    def test_missing_optional_fields_are_tolerated(self, db):
        user = User(
            username="nofields",
            hashed_password="x",
            organization_id=1,
            is_active=True,
        )
        db.add(user)
        db.commit()
        row = [item for item in list_candidates(db, _actor()) if item["username"] == "nofields"][0]
        assert row["full_name"] is None
        assert row["department"] is None


# ════════════════════════════════════════════════════════════════════
#  清单
# ════════════════════════════════════════════════════════════════════


class TestBuildInventory:
    def test_empty_inventory_returns_empty_groups_and_zero_total(self, db):
        inventory = build_inventory(db, _actor())
        assert inventory["total"] == 0
        assert [group["type"] for group in inventory["groups"]] == list(
            handover_service.ASSET_TYPES
        )
        assert all(group["count"] == 0 and group["items"] == [] for group in inventory["groups"])
        assert inventory["generated_at"]

    def test_inventory_collects_all_asset_types(self, db):
        _mk_village(db)
        _mk_project(db)
        _mk_todo(db)
        _mk_approval(db, submitter_id=7, approver_id=7)
        inventory = build_inventory(db, _actor())
        groups = _inventory_by_type(inventory)
        assert inventory["total"] == 4
        assert groups["village"]["count"] == 1
        assert groups["village"]["items"][0]["subtitle"] == "贵州省 / 贵阳市 / 修文县"
        assert groups["project"]["items"][0]["subtitle"] == "状态：in_progress"
        assert groups["todo"]["items"][0]["subtitle"] == "截止 2026-11-01"
        assert groups["approval"]["items"][0]["subtitle"] == "待审批 · 我发起且待我审批"
        assert groups["approval"]["items"][0]["role"] == "both"

    def test_inventory_skips_inactive_completed_and_foreign_records(self, db):
        _mk_village(db, name="已删除村", active=False)
        _mk_village(db, name="他人村", created_by=99)
        _mk_project(db, name="已删除项目", active=False)
        _mk_todo(db, title="已办待办", completed=True)
        # 他人审批 + 已通过的审批都不在清单内
        _mk_approval(db, submitter_id=99, approver_id=99)
        _mk_approval(db, submitter_id=99, approver_id=99, status=ApprovalStatus.APPROVED.value)
        inventory = build_inventory(db, _actor())
        assert inventory["total"] == 0

    def test_inventory_respects_data_scope_for_department_admin(self, db):
        # 部门级 admin（org=1）只能看到本组织记录；本人创建但属他组织的记录被隔离
        _mk_village(db, name="本组织村", created_by=7, org_id=1)
        _mk_village(db, name="他组织村", created_by=7, org_id=2)
        _mk_project(db, name="他组织项目", created_by=7, org_id=2)
        groups = _inventory_by_type(build_inventory(db, _actor(role="admin", organization_id=1)))
        assert [item["title"] for item in groups["village"]["items"]] == ["本组织村"]
        assert groups["project"]["count"] == 0

    def test_inventory_superuser_sees_all_orgs(self, db):
        _mk_village(db, name="他组织村", created_by=7, org_id=2)
        groups = _inventory_by_type(build_inventory(db, _actor(is_superuser=True)))
        assert groups["village"]["count"] == 1

    def test_unexpected_type_is_ignored_defensively(self, db):
        from app.services.handover_service import _collect_assets

        collected = _collect_assets(db, _actor(), ["approval", "unexpected"])
        assert set(collected) == {"approval"}

    def test_inventory_optional_field_fallbacks(self, db):
        _mk_village(db, name="无地区村", province="", city="", county=None)
        _mk_project(db, name="无状态项目", status="")
        _mk_todo(db, title="无截止待办", deadline=None)
        _mk_approval(db, submitter_id=7, approver_id=99, title=None)
        _mk_approval(db, submitter_id=99, approver_id=7, title="我审批的申请")
        groups = _inventory_by_type(build_inventory(db, _actor()))
        assert groups["village"]["items"][0]["subtitle"] is None
        assert groups["project"]["items"][0]["subtitle"] is None
        assert groups["todo"]["items"][0]["subtitle"] is None
        approvals = {item["id"]: item for item in groups["approval"]["items"]}
        assert "project#1" in [item["title"] for item in approvals.values()]
        roles = {item["id"]: item["role"] for item in groups["approval"]["items"]}
        assert "submitter" in roles.values()
        assert "approver" in roles.values()


# ════════════════════════════════════════════════════════════════════
#  勾选裁剪
# ════════════════════════════════════════════════════════════════════


class TestSelectAssets:
    def _collected(self):
        return {
            "village": [{"type": "village", "id": 1, "title": "村1"}],
            "project": [{"type": "project", "id": 2, "title": "项目2"}],
            "todo": [],
        }

    def test_absent_type_ids_means_whole_group(self):
        selected = _select_assets(self._collected(), ["village"], None)
        assert [item["id"] for item in selected["village"]] == [1]

    def test_empty_list_means_skip_group(self):
        selected = _select_assets(self._collected(), ["village", "project"], {"village": []})
        assert "village" not in selected
        assert [item["id"] for item in selected["project"]] == [2]

    def test_subset_selection(self):
        collected = {"village": [{"type": "village", "id": 1}, {"type": "village", "id": 3}]}
        selected = _select_assets(collected, ["village"], {"village": [3]})
        assert [item["id"] for item in selected["village"]] == [3]

    def test_empty_group_is_skipped(self):
        selected = _select_assets(self._collected(), ["todo"], None)
        assert selected == {}

    def test_tampered_id_raises_403(self):
        with pytest.raises(HTTPException) as ei:
            _select_assets(self._collected(), ["village"], {"village": [999]})
        assert ei.value.status_code == 403
        assert "帮扶村" in ei.value.detail


# ════════════════════════════════════════════════════════════════════
#  归属改写 / 审批转交 / 消息 / 快照
# ════════════════════════════════════════════════════════════════════


class TestApplyOwnership:
    def test_village_mismatch_raises_conflict(self, db):
        # 选中项属于他人 → 批量 update 行数不足 → 409（执行期复核）
        village = _mk_village(db, created_by=99)
        target = _mk_user(db)
        selected = {"village": [{"type": "village", "id": village.id}]}
        with pytest.raises(HTTPException) as ei:
            _apply_ownership(db, _actor(), target, selected, None)
        assert ei.value.status_code == 409
        db.rollback()

    def test_project_mismatch_raises_conflict(self, db):
        project = _mk_project(db, created_by=99)
        target = _mk_user(db)
        selected = {"project": [{"type": "project", "id": project.id}]}
        with pytest.raises(HTTPException) as ei:
            _apply_ownership(db, _actor(), target, selected, None)
        assert ei.value.status_code == 409
        db.rollback()

    def test_todo_mismatch_raises_conflict(self, db):
        todo = _mk_todo(db, user_id=99)
        target = _mk_user(db)
        selected = {"todo": [{"type": "todo", "id": todo.id}]}
        with pytest.raises(HTTPException) as ei:
            _apply_ownership(db, _actor(), target, selected, None)
        assert ei.value.status_code == 409
        db.rollback()

    def test_approvals_missing_raises_conflict(self, db):
        target = _mk_user(db)
        selected = {"approval": [{"type": "approval", "id": 999}]}
        with pytest.raises(HTTPException) as ei:
            _apply_ownership(db, _actor(), target, selected, None)
        assert ei.value.status_code == 409
        db.rollback()

    def test_approval_not_owned_raises_403(self, db):
        task = _mk_approval(db, submitter_id=99, approver_id=99)
        target = _mk_user(db)
        selected = {"approval": [{"type": "approval", "id": task.id}]}
        with pytest.raises(HTTPException) as ei:
            _transfer_approvals(db, _actor(), target, selected["approval"], None)
        assert ei.value.status_code == 403
        db.rollback()


class TestNotificationsAndSnapshot:
    def test_notifications_include_note_and_both_parties(self, db):
        target = _mk_user(db, username="lisi")
        actor = _actor()
        items = [{"type": "village", "id": 1, "title": "幸福村"}]
        _write_notifications(db, actor, target, "HO-1", {"village": 1}, 1, items, "请尽快接手")
        db.commit()
        messages = db.query(Message).order_by(Message.id.asc()).all()
        assert len(messages) == 2
        assert messages[0].user_id == target.id
        assert "请尽快接手" in messages[0].content
        assert "幸福村" in messages[0].content
        assert messages[1].user_id == actor.id
        assert "HO-1" in messages[1].content
        assert all(message.link == "/handover" for message in messages)

    def test_notifications_without_note_or_usernames(self, db):
        target = SimpleNamespace(id=8, username=None)
        actor = SimpleNamespace(id=7, username=None)
        _write_notifications(
            db, actor, target, "HO-2", {"todo": 1}, 1,
            [{"type": "todo", "id": 3, "title": "走访"}], None,
        )
        db.commit()
        messages = db.query(Message).all()
        assert len(messages) == 2
        assert "系统用户" in messages[0].content
        assert "接任人" in messages[0].content
        assert "备注" not in messages[0].content

    def test_build_snapshot_keeps_item_roles(self):
        actor = _actor()
        target = SimpleNamespace(id=8, username="lisi", full_name="李四")
        snapshot = _build_snapshot(
            record_no="HO-1",
            actor=actor,
            target=target,
            note="备注",
            items=[{"type": "approval", "id": 2, "title": "申请", "role": "both"}],
            counts={"approval": 1},
            total=1,
        )
        assert snapshot["from_user"]["username"] == "zhangsan"
        assert snapshot["to_user"]["id"] == 8
        assert snapshot["items"][0]["role"] == "both"
        assert snapshot["counts"]["village"] == 0

    def test_audit_detail_contains_each_item_and_note(self):
        snapshot = {
            "to_user": {"id": 8},
            "to_username": "lisi",
            "items": [
                {"type": "village", "id": 1, "title": "幸福村"},
                {"type": "todo", "id": 3, "title": "走访"},
            ],
            "note": "轮岗",
        }
        detail = _audit_detail(snapshot, {"village": 1, "todo": 1}, 2)
        assert "接任人：lisi（ID 8）" in detail
        assert "帮扶村#1《幸福村》→lisi" in detail
        assert "待办事项#3《走访》→lisi" in detail
        assert "轮岗" in detail

    def test_audit_detail_without_note_and_fallback_username(self):
        snapshot = {
            "to_user": {"id": None},
            "to_username": None,
            "items": [],
            "note": None,
        }
        detail = _audit_detail(snapshot, {}, 0)
        assert "接任人：接任人" in detail
        assert "备注" not in detail


# ════════════════════════════════════════════════════════════════════
#  执行移交
# ════════════════════════════════════════════════════════════════════


class TestExecuteHandover:
    def _seed(self, db):
        target = _mk_user(db, username="lisi")
        village = _mk_village(db)
        project = _mk_project(db)
        todo = _mk_todo(db)
        task = _mk_approval(db, submitter_id=7, approver_id=7)
        return target, village, project, todo, task

    def test_execute_all_assets_success(self, db):
        target, village, project, todo, task = self._seed(db)
        result = execute_handover(db, _actor(), to_user_id=target.id, note="轮岗移交")
        assert result["record_no"].startswith("HO-")
        assert result["total"] == 4
        assert result["counts"] == {"village": 1, "project": 1, "todo": 1, "approval": 1}
        assert result["to_user"]["id"] == target.id
        assert result["note"] == "轮岗移交"
        assert len(result["items"]) == 4

        db.expire_all()
        assert db.get(SupportedVillage, village.id).created_by == target.id
        assert db.get(Project, project.id).created_by == target.id
        assert db.get(Todo, todo.id).user_id == target.id
        refreshed = db.get(ApprovalTask, task.id)
        assert refreshed.current_approver_id == target.id
        assert refreshed.submitter_id == target.id
        # 审批转交留痕
        from app.models.approval import ApprovalRecord
        record = db.query(ApprovalRecord).filter(ApprovalRecord.task_id == task.id).first()
        assert record is not None
        assert record.transfer_to_id == target.id
        assert record.transfer_reason == "轮岗移交"
        # 双方站内消息
        assert db.query(Message).count() == 2
        # 审计（WorkLog category=handover，含逐项清单与 JSON 快照）
        log = db.query(WorkLog).filter(WorkLog.category == "handover").one()
        assert log.user_id == 7
        assert "逐项清单" in log.content
        assert "帮扶村#" in log.content
        snapshot = json.loads(log.attachments)
        assert snapshot["record_no"] == result["record_no"]
        assert snapshot["total"] == 4

        # 验收：原责任人清单清空、接任人清单可见（工作台/待办在归属变更后随人走）
        db.expire_all()
        assert build_inventory(db, _actor())["total"] == 0
        receiver_inventory = build_inventory(db, target)
        assert receiver_inventory["total"] == 4
        assert {group["type"] for group in receiver_inventory["groups"] if group["count"]} == {
            "village",
            "project",
            "todo",
            "approval",
        }

    def test_execute_scope_and_item_ids_subset(self, db):
        target, village, project, todo, task = self._seed(db)
        result = execute_handover(
            db,
            _actor(),
            to_user_id=target.id,
            scope=["village", "todo"],
            item_ids={"todo": []},
        )
        assert result["counts"] == {"village": 1}
        db.expire_all()
        assert db.get(SupportedVillage, village.id).created_by == target.id
        assert db.get(Todo, todo.id).user_id == 7  # 未勾选 → 不动
        assert db.get(Project, project.id).created_by == 7

    def test_execute_without_assets_raises_422(self, db):
        target = _mk_user(db)
        with pytest.raises(HTTPException) as ei:
            execute_handover(db, _actor(), to_user_id=target.id)
        assert ei.value.status_code == 422

    def test_execute_rejects_self_and_cross_org(self, db):
        _mk_user(db, username="zhangsan", uid=7)
        target = _mk_user(db, username="lisi", org_id=2)
        with pytest.raises(HTTPException) as ei:
            execute_handover(db, _actor(), to_user_id=target.id)
        assert ei.value.status_code == 403
        with pytest.raises(HTTPException) as ei2:
            execute_handover(db, _actor(), to_user_id=7)
        assert ei2.value.status_code == 422

    def test_execute_rejects_unknown_target(self, db):
        with pytest.raises(HTTPException) as ei:
            execute_handover(db, _actor(), to_user_id=999)
        assert ei.value.status_code == 404

    def test_execute_invalid_scope_payloads(self, db):
        target = _mk_user(db)
        _mk_village(db)
        with pytest.raises(HTTPException):
            execute_handover(db, _actor(), to_user_id=target.id, scope=["alien"])
        with pytest.raises(HTTPException):
            execute_handover(db, _actor(), to_user_id=target.id, scope=[])
        with pytest.raises(HTTPException):
            execute_handover(
                db, _actor(), to_user_id=target.id, scope=["village"],
                item_ids={"village": [999]},
            )

    def test_execute_failure_rolls_back_everything(self, db, monkeypatch):
        target, village, project, todo, task = self._seed(db)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("消息推送失败")

        monkeypatch.setattr(handover_service, "_write_notifications", _boom)
        with pytest.raises(RuntimeError):
            execute_handover(db, _actor(), to_user_id=target.id)
        db.rollback()
        db.expire_all()
        # 归属、消息、审计全部未落库（单事务全量回滚）
        assert db.get(SupportedVillage, village.id).created_by == 7
        assert db.get(Project, project.id).created_by == 7
        assert db.get(Todo, todo.id).user_id == 7
        assert db.get(ApprovalTask, task.id).current_approver_id == 7
        assert db.query(Message).count() == 0
        assert db.query(WorkLog).filter(WorkLog.category == "handover").count() == 0

    def test_execute_commits_when_write_work_log_skipped(self, db, monkeypatch):
        target, village, _project, _todo, _task = self._seed(db)
        monkeypatch.setattr(handover_service, "write_work_log", lambda *a, **k: None)
        result = execute_handover(db, _actor(), to_user_id=target.id)
        assert result["record_id"] is None
        db.expire_all()
        # write_work_log 防御性跳过时，本层兜底提交，归属已落库
        assert db.get(SupportedVillage, village.id).created_by == target.id


# ════════════════════════════════════════════════════════════════════
#  历史
# ════════════════════════════════════════════════════════════════════


class TestHistory:
    def test_query_history_parses_snapshot(self, db):
        target = _mk_user(db)
        _mk_village(db)
        execute_handover(db, _actor(), to_user_id=target.id, note="轮岗")
        items, total = query_history(db, _actor())
        assert total == 1
        assert items[0]["record_no"].startswith("HO-")
        assert items[0]["to_username"] == "lisi"
        assert items[0]["counts"]["village"] == 1
        assert items[0]["total"] == 1
        assert items[0]["items"][0]["title"] == "幸福村"
        assert items[0]["log_date"]
        assert items[0]["created_at"]

    def test_query_history_date_filters_and_pagination(self, db):
        _mk_village(db)
        target = _mk_user(db)
        execute_handover(db, _actor(), to_user_id=target.id)
        assert query_history(db, _actor(), date_from=date.today())[1] == 1
        assert query_history(db, _actor(), date_to=date.today())[1] == 1
        assert query_history(db, _actor(), date_from=date(2000, 1, 1), date_to=date(2000, 1, 2))[1] == 0
        # 翻页越界：items 为空但 total 仍为真实总数
        assert query_history(db, _actor(), page=5, page_size=10) == ([], 1)

    def test_query_history_only_returns_current_user_rows(self, db):
        log = WorkLog(
            user_id=99, category="handover", content="execute: x", log_date=date.today(),
        )
        db.add(log)
        db.commit()
        assert query_history(db, _actor())[1] == 0

    def test_parse_snapshot_fallbacks(self):
        assert _parse_snapshot(SimpleNamespace(attachments=None, id=1)) == {}
        assert _parse_snapshot(SimpleNamespace(attachments="{bad-json", id=2)) == {}
        assert _parse_snapshot(SimpleNamespace(attachments="[1, 2]", id=3)) == {}
        assert _parse_snapshot(SimpleNamespace(attachments='{"record_no": "HO-1"}', id=4)) == {
            "record_no": "HO-1"
        }

    def test_history_item_tolerates_broken_snapshot(self):
        row = SimpleNamespace(
            id=1,
            attachments=json.dumps(
                {"counts": "not-a-dict", "items": "not-a-list",
                 "from_user": "not-a-dict", "to_user": "not-a-dict", "total": 0}
            ),
            content="execute: x",
            log_date=None,
            created_at=None,
        )
        item = _history_item(row)
        assert item["counts"] == {"village": 0, "project": 0, "todo": 0, "approval": 0}
        assert item["items"] == []
        assert item["total"] == 0
        assert item["from_user_id"] is None
        assert item["to_user_id"] is None
        assert item["log_date"] is None
        assert item["created_at"] is None
