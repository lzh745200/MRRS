"""
经费管理 ↔ 审批模块 闭环集成回归测试

验证「待审批任务板块」能读取经费管理板块的数据：
1. 经费申请/创建/更新自动创建审批任务（Requirement 3.2 数据变更自动创建审批任务）
2. 待审批列表返回经费变更数据摘要（change_data）
3. 审批通过/驳回后回写经费状态（Requirement 3.6 审批通过后执行数据变更）
4. 变更对比返回 change_data/original_data/diff_fields（前端 PendingList/History 契约）
5. 我的申请/审批历史任务端点返回任务（id 即任务 ID，撤回/重提可用）
6. 经费板块直接审批时同步完结关联审批任务（双向闭环）
"""
import pytest


@pytest.fixture(autouse=True)
def mock_auth(client):
    """自动为所有测试模拟管理员认证（id=1, role=admin）"""
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


def _apply_payload(**overrides):
    payload = {
        "name": "产业帮扶经费",
        "type": "industry",
        "fund_source": "military",
        "amount": 50000.0,
        "purpose": "发展茶叶产业",
    }
    payload.update(overrides)
    return payload


def _pending_tasks(client):
    resp = client.get("/api/v1/approval/tasks/pending?skip=0&limit=100")
    assert resp.status_code == 200
    body = resp.json()
    return body["data"], body.get("total", 0)


class TestFundApplyCreatesApprovalTask:
    """经费申请 → 自动创建审批任务 → 待审批板块可见"""

    def test_apply_creates_pending_task(self, client):
        resp = client.post("/api/v1/funds/apply", json=_apply_payload())
        assert resp.status_code in (200, 201)
        data = resp.json()["data"]
        assert data["approval_task_id"] is not None
        fund_id = data["id"]

        tasks, total = _pending_tasks(client)
        assert total >= 1
        fund_tasks = [t for t in tasks if t["entity_type"] == "fund" and t["entity_id"] == fund_id]
        assert len(fund_tasks) == 1
        task = fund_tasks[0]
        # 待审批板块能读取经费数据摘要
        assert task["change_data"] is not None
        assert task["change_data"]["name"] == "产业帮扶经费"
        assert float(task["change_data"]["amount"]) == 50000.0
        assert "经费申请" in (task["title"] or "")

    def test_apply_visible_in_my_applications(self, client):
        resp = client.post("/api/v1/funds/apply", json=_apply_payload(name="我的申请经费"))
        assert resp.status_code in (200, 201)

        r = client.get("/api/v1/approval/tasks/mine?skip=0&limit=100")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        # id 即任务 ID（撤回/重新提交可直接使用）
        mine = [t for t in body["data"] if t["entity_type"] == "fund"]
        assert mine and mine[0]["id"] == resp.json()["data"]["approval_task_id"]


class TestFundApproveWritesBack:
    """审批通过 → 经费状态 pending → approved（闭环回写）"""

    def test_approve_task_updates_fund_status(self, client):
        resp = client.post("/api/v1/funds/apply", json=_apply_payload(name="待审批回写经费"))
        assert resp.status_code in (200, 201)
        fund_id = resp.json()["data"]["id"]
        task_id = resp.json()["data"]["approval_task_id"]

        # 审批前经费为 pending
        assert client.get(f"/api/v1/funds/{fund_id}").json()["data"]["status"] == "pending"

        # 审批通过（默认单节点工作流：一级通过即完成）
        r = client.post(f"/api/v1/approval/tasks/{task_id}/approve", json={"opinion": "同意"})
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "approved"

        # 经费状态已回写为 approved
        fund = client.get(f"/api/v1/funds/{fund_id}").json()["data"]
        assert fund["status"] == "approved"

        # 审批回写留下状态变更历史（审计闭环）
        history = client.get(f"/api/v1/funds/{fund_id}/history/status").json()["data"]
        assert any(
            h.get("from_status") == "pending" and h.get("to_status") == "approved"
            for h in (history if isinstance(history, list) else history.get("items", []))
        )

        # 待审批板块中该任务已消失
        tasks, _ = _pending_tasks(client)
        assert all(not (t["entity_type"] == "fund" and t["entity_id"] == fund_id) for t in tasks)

    def test_reject_task_updates_fund_status(self, client):
        resp = client.post("/api/v1/funds/apply", json=_apply_payload(name="待驳回回写经费"))
        assert resp.status_code in (200, 201)
        fund_id = resp.json()["data"]["id"]
        task_id = resp.json()["data"]["approval_task_id"]

        r = client.post(f"/api/v1/approval/tasks/{task_id}/reject", json={"opinion": "预算不足"})
        assert r.status_code == 200
        assert client.get(f"/api/v1/funds/{fund_id}").json()["data"]["status"] == "rejected"


class TestFundCreateUpdateCreatesApprovalTasks:
    """经费新增/变更也进入待审批板块（含变更对比数据）"""

    def test_create_fund_creates_task(self, client):
        resp = client.post("/api/v1/funds", json=_apply_payload(name="管理员新增经费"))
        assert resp.status_code in (200, 201)
        task_id = resp.json()["data"]["approval_task_id"]
        assert task_id is not None

        r = client.get(f"/api/v1/approval/tasks/{task_id}/diff")
        assert r.status_code == 200
        diff = r.json()["data"]
        # 前端契约字段
        assert "change_data" in diff and "original_data" in diff and "diff_fields" in diff
        assert diff["change_data"]["name"] == "管理员新增经费"

    def test_update_fund_creates_task_with_original(self, client):
        resp = client.post("/api/v1/funds/apply", json=_apply_payload(name="变更前名称"))
        assert resp.status_code in (200, 201)
        fund_id = resp.json()["data"]["id"]

        # 更新经费 → 生成变更审批任务（带 original_data 供对比）
        r = client.put(f"/api/v1/funds/{fund_id}", json={"name": "变更后名称", "amount": 60000.0})
        assert r.status_code == 200
        update_task_id = r.json()["data"]["approval_task_id"]
        assert update_task_id is not None

        diff = client.get(f"/api/v1/approval/tasks/{update_task_id}/diff").json()["data"]
        assert diff["change_data"]["name"] == "变更后名称"
        assert diff["original_data"]["name"] == "变更前名称"
        assert "name" in diff["diff_fields"]


class TestFundDirectApproveResolvesTasks:
    """经费板块直接审批 → 同步完结待审批板块的关联任务（双向闭环）"""

    def test_direct_approve_resolves_pending_task(self, client):
        resp = client.post("/api/v1/funds/apply", json=_apply_payload(name="直接审批经费"))
        assert resp.status_code in (200, 201)
        fund_id = resp.json()["data"]["id"]
        task_id = resp.json()["data"]["approval_task_id"]

        # 直接审批要求至少 1 个附件，先上传
        up = client.post(
            f"/api/v1/funds/{fund_id}/attachments",
            files={"file": ("contract.txt", b"contract-data", "text/plain")},
            data={"category": "contract"},
        )
        assert up.status_code in (200, 201)

        # 经费板块直接审批
        r = client.post(f"/api/v1/funds/{fund_id}/approve", json={})
        assert r.status_code == 200
        assert r.json()["data"]["resolved_tasks"] >= 1

        # 关联审批任务已被完结（approved），不再出现在待审批板块
        task = client.get(f"/api/v1/approval/tasks/history?skip=0&limit=100").json()["data"]
        matched = [t for t in task if t["id"] == task_id]
        assert matched and matched[0]["status"] == "approved"


class TestApprovalTaskHistoryEndpoints:
    """审批任务历史端点返回任务（含 total，分页正确）"""

    def test_history_returns_tasks_with_total(self, client):
        client.post("/api/v1/funds/apply", json=_apply_payload(name="历史经费A"))
        client.post("/api/v1/funds/apply", json=_apply_payload(name="历史经费B"))

        r = client.get("/api/v1/approval/tasks/history?completed=true&skip=0&limit=100")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["total"], int)

        # 待审批任务不在已办结列表中
        assert all(t["status"] != "pending" for t in body["data"])

    def test_history_entity_filter(self, client):
        client.post("/api/v1/funds/apply", json=_apply_payload(name="过滤经费"))

        r = client.get("/api/v1/approval/tasks/history?entity_type=fund&skip=0&limit=100")
        assert r.status_code == 200
        body = r.json()
        assert all(t["entity_type"] == "fund" for t in body["data"])
        assert body["total"] >= 1
