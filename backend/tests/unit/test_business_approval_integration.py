"""
业务板块 ↔ 审批模块 集成回归测试

验证「待审批任务板块」能读取各业务板块（项目/帮扶村/学校/乡村工作/资助学生/政策）的数据：
- 数据变更自动创建审批任务（Requirement 3.2）
- 待审批列表返回变更数据摘要
- 审批通过后回写业务实体状态（项目 pending→approved、资助学生 pending→approved）
"""
import pytest


@pytest.fixture(autouse=True)
def mock_auth(client):
    """自动为所有测试模拟管理员认证"""
    from unittest.mock import Mock

    from app.core.security import get_current_user

    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1
    user.email = "admin@test.com"
    user.full_name = "Admin"

    original_overrides = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield
    client.app.dependency_overrides = original_overrides


def _pending_of_type(client, entity_type):
    resp = client.get("/api/v1/approval/tasks/pending?skip=0&limit=200")
    assert resp.status_code == 200
    body = resp.json()
    return [t for t in body["data"] if t["entity_type"] == entity_type]


class TestProjectApprovalIntegration:
    def test_create_project_creates_task(self, client):
        resp = client.post("/api/v1/projects", json={
            "name": "审批集成测试项目",
            "type": "industry",
            "budget": 100000,
            "status": "pending",
        })
        assert resp.status_code in (200, 201)
        task_id = resp.json()["data"].get("approval_task_id")
        assert task_id is not None

        tasks = _pending_of_type(client, "project")
        assert any(t["id"] == task_id for t in tasks)

    def test_approve_task_writes_back_project_status(self, client):
        resp = client.post("/api/v1/projects", json={
            "name": "状态回写测试项目",
            "type": "industry",
            "budget": 50000,
        })
        assert resp.status_code in (200, 201)
        project_id = resp.json()["data"]["id"]

        # ProjectCreate 无 status 字段（新建为 draft），通过更新接口置为 pending
        # （更新同时生成变更审批任务，approval_task_id 在 data 中）
        upd = client.put(f"/api/v1/projects/{project_id}", json={"status": "pending"})
        assert upd.status_code == 200
        task_id = upd.json()["data"]["approval_task_id"]
        assert task_id is not None

        r = client.post(f"/api/v1/approval/tasks/{task_id}/approve", json={"opinion": "同意"})
        assert r.status_code == 200

        detail = client.get(f"/api/v1/projects/{project_id}").json()["data"]
        assert detail["status"] == "approved"


class TestVillageApprovalIntegration:
    def test_create_village_creates_task(self, client):
        resp = client.post("/api/v1/supported-villages", json={
            "village_name": "审批集成测试村",
            "county": "测试县",
        })
        assert resp.status_code in (200, 201)
        task_id = resp.json()["data"].get("approval_task_id")
        assert task_id is not None
        assert any(t["id"] == task_id for t in _pending_of_type(client, "supported_village"))


class TestSchoolApprovalIntegration:
    def test_create_school_creates_task(self, client):
        resp = client.post("/api/v1/schools", json={
            "name": "审批集成测试学校",
            "code": "SCH-APPROVAL-001",
            "district": "测试区",
        })
        assert resp.status_code in (200, 201)
        task_id = resp.json()["data"].get("approval_task_id")
        assert task_id is not None
        assert any(t["id"] == task_id for t in _pending_of_type(client, "school"))

    def test_scholarship_pending_creates_task_and_approve_writes_back(self, client):
        school_resp = client.post("/api/v1/schools", json={
            "name": "资助审批测试学校",
            "code": "SCH-SCHOLAR-001",
        })
        assert school_resp.status_code in (200, 201)
        school_id = school_resp.json()["data"]["id"]

        stu_resp = client.post(
            f"/api/v1/schools/{school_id}/scholarship-students",
            json={"student_name": "张三", "year": 2026, "amount": 2000, "status": "pending"},
        )
        assert stu_resp.status_code in (200, 201)
        task_id = stu_resp.json()["data"].get("approval_task_id")
        assert task_id is not None
        assert any(t["id"] == task_id for t in _pending_of_type(client, "scholarship_student"))

        # 审批通过 → 资助学生状态回写为 approved
        r = client.post(f"/api/v1/approval/tasks/{task_id}/approve", json={"opinion": "同意"})
        assert r.status_code == 200
        students = client.get(
            f"/api/v1/schools/{school_id}/scholarship-students"
        ).json()["data"]["items"]
        student = next(s for s in students if s["student_name"] == "张三")
        assert student["status"] in ("approved", "已批准")


class TestRuralWorkApprovalIntegration:
    def test_create_rural_work_creates_task(self, client):
        resp = client.post("/api/v1/rural-works", json={
            "name": "审批集成测试乡村工作",
            "type": "infrastructure",
            "status": "planned",
        })
        assert resp.status_code in (200, 201)
        data = resp.json().get("data") or {}
        assert data.get("approval_task_id") is not None
        assert any(t["id"] == data["approval_task_id"] for t in _pending_of_type(client, "rural_work"))


class TestPolicyApprovalIntegration:
    def test_publish_policy_creates_task(self, client):
        create_resp = client.post("/api/v1/policies", json={
            "title": "审批集成测试政策",
            "level": "provincial",
            "status": "draft",
        })
        assert create_resp.status_code in (200, 201)
        policy_id = create_resp.json()["data"]["id"]

        resp = client.post(f"/api/v1/policies/{policy_id}/publish")
        assert resp.status_code == 200
        task_id = resp.json()["data"].get("approval_task_id")
        assert task_id is not None
        assert any(t["id"] == task_id for t in _pending_of_type(client, "policy"))
