"""工作移交 API 契约测试（w17-004）。

覆盖：清单（空/有数据/数据域）、接任人列表（同组织/关键字/参数边界）、
执行（成功/跨组织 403/本人 422/不存在 404/停用 404/无资产 422/各类非法入参 422/
伪造 ID 403/单事务失败全量回滚）、历史（快照回放/时间过滤/分页/分页参数校验）。
"""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def _user(**kw):
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


@pytest.fixture
def api_client():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app
    from app.models import Base
    from app.models.approval import ApprovalTask, ApprovalWorkflow  # noqa: F401
    from app.models.message import Message  # noqa: F401
    from app.models.organization import Organization  # noqa: F401
    from app.models.project import Project  # noqa: F401
    from app.models.supported_village import SupportedVillage  # noqa: F401
    from app.models.todo import Todo  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.work_log import WorkLog  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    state = {"user": _user()}

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, session, state
    finally:
        app.dependency_overrides = original_overrides
        session.close()
        engine.dispose()


def _as(state, **kw):
    state["user"] = _user(**kw)


def _mk_user(db, username="lisi", org_id=1, active=True, role="user", uid=None):
    from app.models.user import User

    user = User(
        id=uid,
        username=username,
        hashed_password="x",
        organization_id=org_id,
        is_active=active,
        role=role,
        full_name=username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_village(db, name="幸福村", created_by=7, org_id=1, active=True):
    from app.models.supported_village import SupportedVillage

    village = SupportedVillage(
        village_name=name, created_by=created_by, organization_id=org_id, is_active=active
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _mk_project(db, name="道路硬化", created_by=7, org_id=1):
    from app.models.project import Project

    project = Project(
        name=name, created_by=created_by, organization_id=org_id, status="in_progress"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _mk_todo(db, title="走访农户", user_id=7, deadline="2026-11-01", completed=False):
    from app.models.todo import Todo

    todo = Todo(title=title, user_id=user_id, deadline=deadline, completed=completed)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


def _mk_approval(db, submitter_id=7, approver_id=7, status="pending", entity_type="project"):
    from app.models.approval import ApprovalTask, ApprovalWorkflow

    workflow = ApprovalWorkflow(
        name=f"{entity_type}流程", entity_type=entity_type, is_active=True
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    task = ApprovalTask(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=1,
        submitter_id=submitter_id,
        current_level=1,
        current_approver_id=approver_id,
        status=status,
        title="项目变更申请",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _group_map(body):
    return {group["type"]: group for group in body["data"]["groups"]}


# ════════════════════════════════════════════════════════════════════
#  清单 / 接任人
# ════════════════════════════════════════════════════════════════════


class TestInventoryApi:
    def test_empty_inventory_returns_200_with_empty_groups(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/handover/inventory")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["success"] is True
        assert body["data"]["total"] == 0
        groups = _group_map(body)
        assert groups["village"]["count"] == 0
        assert groups["village"]["label"] == "帮扶村"
        assert groups["approval"]["items"] == []

    def test_inventory_lists_my_assets_only(self, api_client):
        client, db, _state = api_client
        _mk_village(db)
        _mk_project(db)
        _mk_todo(db)
        _mk_approval(db, submitter_id=7, approver_id=7)
        # 他人资产不应出现
        _mk_village(db, name="他人村", created_by=99, org_id=1)
        resp = client.get("/api/v1/handover/inventory")
        assert resp.status_code == 200
        groups = _group_map(resp.json())
        assert groups["village"]["count"] == 1
        assert groups["project"]["count"] == 1
        assert groups["todo"]["count"] == 1
        assert groups["approval"]["count"] == 1

    def test_inventory_respects_org_scope(self, api_client):
        client, db, _state = api_client
        _mk_village(db, name="本组织村", created_by=7, org_id=1)
        _mk_village(db, name="他组织村", created_by=7, org_id=2)
        resp = client.get("/api/v1/handover/inventory")
        groups = _group_map(resp.json())
        assert [item["title"] for item in groups["village"]["items"]] == ["本组织村"]


class TestCandidatesApi:
    def test_candidates_same_org_only(self, api_client):
        client, db, _state = api_client
        _mk_user(db, username="lisi", org_id=1)
        _mk_user(db, username="wangwu", org_id=2)
        resp = client.get("/api/v1/handover/candidates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 1
        assert data["items"][0]["username"] == "lisi"

    def test_candidates_keyword_and_limit(self, api_client):
        client, db, _state = api_client
        _mk_user(db, username="lisi", org_id=1)
        _mk_user(db, username="wangwu", org_id=1)
        resp = client.get("/api/v1/handover/candidates", params={"keyword": "lisi", "limit": 1})
        assert resp.status_code == 200
        assert [row["username"] for row in resp.json()["data"]["items"]] == ["lisi"]

    def test_candidates_limit_boundary_422(self, api_client):
        client, _db, _state = api_client
        assert client.get("/api/v1/handover/candidates", params={"limit": 0}).status_code == 422
        assert client.get("/api/v1/handover/candidates", params={"limit": 501}).status_code == 422

    def test_candidates_empty_returns_empty_list(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/handover/candidates")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"items": [], "total": 0, "page": 1, "page_size": 1}


# ════════════════════════════════════════════════════════════════════
#  执行
# ════════════════════════════════════════════════════════════════════


class TestExecuteApi:
    def test_execute_success_updates_ownership_and_audit(self, api_client):
        client, db, _state = api_client
        from app.models.approval import ApprovalRecord, ApprovalTask
        from app.models.message import Message
        from app.models.project import Project
        from app.models.supported_village import SupportedVillage
        from app.models.todo import Todo
        from app.models.work_log import WorkLog

        _mk_user(db, username="zhangsan", uid=7)
        target = _mk_user(db, username="lisi")
        village = _mk_village(db)
        project = _mk_project(db)
        todo = _mk_todo(db)
        task = _mk_approval(db, submitter_id=7, approver_id=7)

        resp = client.post(
            "/api/v1/handover/execute",
            json={"to_user_id": target.id, "note": "轮岗移交"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["record_no"].startswith("HO-")
        assert data["total"] == 4
        assert data["counts"] == {"village": 1, "project": 1, "todo": 1, "approval": 1}
        assert data["to_user"]["username"] == "lisi"
        assert data["note"] == "轮岗移交"

        db.expire_all()
        assert db.get(SupportedVillage, village.id).created_by == target.id
        assert db.get(Project, project.id).created_by == target.id
        assert db.get(Todo, todo.id).user_id == target.id
        refreshed = db.get(ApprovalTask, task.id)
        assert refreshed.current_approver_id == target.id
        assert refreshed.submitter_id == target.id
        assert db.query(ApprovalRecord).filter(ApprovalRecord.task_id == task.id).count() == 1
        assert db.query(Message).count() == 2
        log = db.query(WorkLog).filter(WorkLog.category == "handover").one()
        assert "逐项清单" in log.content
        snapshot = json.loads(log.attachments)
        assert snapshot["to_user"]["id"] == target.id

    def test_execute_with_selected_scope(self, api_client):
        client, db, _state = api_client
        target = _mk_user(db)
        _mk_village(db)
        todo = _mk_todo(db)
        resp = client.post(
            "/api/v1/handover/execute",
            json={"to_user_id": target.id, "scope": ["village"]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["counts"] == {"village": 1}
        db.expire_all()
        assert db.get(type(todo), todo.id).user_id == 7

    def test_execute_cross_org_403(self, api_client):
        client, db, _state = api_client
        _mk_village(db)
        target = _mk_user(db, username="lisi", org_id=2)
        resp = client.post("/api/v1/handover/execute", json={"to_user_id": target.id})
        assert resp.status_code == 403
        assert "跨组织" in resp.json()["detail"]

    def test_execute_self_422(self, api_client):
        client, db, _state = api_client
        _mk_user(db, username="zhangsan", uid=7)
        resp = client.post("/api/v1/handover/execute", json={"to_user_id": 7})
        assert resp.status_code == 422

    def test_execute_target_not_found_and_inactive(self, api_client):
        client, db, _state = api_client
        assert client.post("/api/v1/handover/execute", json={"to_user_id": 999}).status_code == 404
        disabled = _mk_user(db, username="disabled", active=False)
        resp = client.post("/api/v1/handover/execute", json={"to_user_id": disabled.id})
        assert resp.status_code == 404

    def test_execute_validation_errors(self, api_client):
        client, db, _state = api_client
        target = _mk_user(db)
        _mk_village(db)
        assert client.post("/api/v1/handover/execute", json={}).status_code == 422
        assert (
            client.post("/api/v1/handover/execute", json={"to_user_id": 0}).status_code == 422
        )
        # 未知类型 / 空勾选 / 不在范围内的类型 / 非数组 / 超长备注
        for payload in (
            {"to_user_id": target.id, "scope": ["alien"]},
            {"to_user_id": target.id, "scope": []},
            {"to_user_id": target.id, "scope": ["village"], "item_ids": {"todo": [1]}},
            {"to_user_id": target.id, "item_ids": {"alien": [1]}},
            {"to_user_id": target.id, "item_ids": {"village": "bad"}},
            {"to_user_id": target.id, "note": "x" * 501},
        ):
            assert client.post("/api/v1/handover/execute", json=payload).status_code == 422

    def test_execute_no_assets_422(self, api_client):
        client, db, _state = api_client
        target = _mk_user(db)
        resp = client.post("/api/v1/handover/execute", json={"to_user_id": target.id})
        assert resp.status_code == 422
        assert "没有可移交" in resp.json()["detail"]

    def test_execute_tampered_item_id_403(self, api_client):
        client, db, _state = api_client
        target = _mk_user(db)
        _mk_village(db)
        resp = client.post(
            "/api/v1/handover/execute",
            json={"to_user_id": target.id, "scope": ["village"], "item_ids": {"village": [999]}},
        )
        assert resp.status_code == 403
        assert "不适合" in resp.json()["detail"] or "不属于" in resp.json()["detail"]

    def test_execute_failure_rolls_back_all_changes(self, api_client, monkeypatch):
        from app.services import handover_service

        client, db, _state = api_client
        target = _mk_user(db)
        village = _mk_village(db)
        from app.models.message import Message
        from app.models.work_log import WorkLog

        def _boom(*_args, **_kwargs):
            raise RuntimeError("通知写入失败")

        monkeypatch.setattr(handover_service, "_write_notifications", _boom)
        resp = client.post("/api/v1/handover/execute", json={"to_user_id": target.id})
        assert resp.status_code == 500
        db.rollback()
        db.expire_all()
        from app.models.supported_village import SupportedVillage

        assert db.get(SupportedVillage, village.id).created_by == 7
        assert db.query(Message).count() == 0
        assert db.query(WorkLog).filter(WorkLog.category == "handover").count() == 0


# ════════════════════════════════════════════════════════════════════
#  历史
# ════════════════════════════════════════════════════════════════════


class TestHistoryApi:
    def _execute(self, client, db):
        target = _mk_user(db)
        _mk_village(db)
        resp = client.post(
            "/api/v1/handover/execute", json={"to_user_id": target.id, "note": "轮岗"}
        )
        assert resp.status_code == 200
        return resp.json()["data"]

    def test_history_returns_snapshot_of_executed_handover(self, api_client):
        client, db, _state = api_client
        data = self._execute(client, db)
        resp = client.get("/api/v1/handover/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["total"] == 1
        item = body["data"]["items"][0]
        assert item["record_no"] == data["record_no"]
        assert item["to_username"] == "lisi"
        assert item["counts"]["village"] == 1
        assert item["items"][0]["title"] == "幸福村"
        assert "逐项清单" in item["content"]

    def test_history_date_filters(self, api_client):
        client, db, _state = api_client
        self._execute(client, db)
        today = date.today().isoformat()
        assert client.get("/api/v1/handover/history", params={"date_from": today}).json()[
            "data"
        ]["total"] == 1
        assert client.get("/api/v1/handover/history", params={"date_to": today}).json()[
            "data"
        ]["total"] == 1
        assert client.get(
            "/api/v1/handover/history", params={"date_from": "2000-01-01", "date_to": "2000-01-02"}
        ).json()["data"]["total"] == 0

    def test_history_pagination_and_validation(self, api_client):
        client, db, _state = api_client
        self._execute(client, db)
        resp = client.get("/api/v1/handover/history", params={"page": 2, "page_size": 10})
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []
        assert resp.json()["data"]["total"] == 1
        assert client.get("/api/v1/handover/history", params={"page": 0}).status_code == 422
        assert client.get("/api/v1/handover/history", params={"page_size": 0}).status_code == 422
        assert client.get("/api/v1/handover/history", params={"page_size": 101}).status_code == 422

    def test_history_empty_returns_zero(self, api_client):
        client, _db, _state = api_client
        body = client.get("/api/v1/handover/history").json()
        assert body["data"] == {"items": [], "total": 0, "page": 1, "page_size": 20}

    def test_history_tolerates_legacy_work_log_without_snapshot(self, api_client):
        client, db, _state = api_client
        from app.models.work_log import WorkLog

        db.add(
            WorkLog(
                user_id=7,
                category="handover",
                content="execute: 历史遗留无快照",
                log_date=date.today(),
            )
        )
        db.commit()
        resp = client.get("/api/v1/handover/history")
        assert resp.status_code == 200
        item = resp.json()["data"]["items"][0]
        assert item["record_no"] is None
        assert item["items"] == []
        assert item["total"] == 0
