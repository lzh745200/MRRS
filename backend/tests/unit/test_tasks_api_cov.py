"""app.api.v1.system.tasks 覆盖率攻坚测试

内存任务存储 _tasks 的列表/统计/详情/创建/取消/删除/运行计数全分支。
创建任务的后台执行函数通过捕获 BackgroundTasks.add_task 手动驱动，
避免真实 2.5s sleep 并确定性地覆盖正常与异常分支。
"""

import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

import app.api.v1.system.tasks as tasks_mod
from app.core.security import get_current_user

BASE = "/api/v1/system/tasks"


@pytest.fixture(autouse=True)
def _clean_tasks():
    tasks_mod._tasks.clear()
    yield
    tasks_mod._tasks.clear()


@pytest.fixture
def tk_client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="root", role="admin"
    )
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _iso(minutes_ago: float = 0) -> str:
    """生成 ISO 时间戳（默认=当前）。

    R12-6 起终态任务只保留 1 小时（_purge_finished_tasks_locked），测试数据
    必须"新鲜"，否则列表/统计端点会在断言前就把它们回收掉 —— 旧写法固定用
    2026-07 的历史时间戳，语义上等价于"放了一年的过期任务"。
    """
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def _seed(task_id="t1", status="completed", task_type="backup", created_at=None):
    created_at = created_at or _iso()
    rec = {
        "task_id": task_id,
        "task_type": task_type,
        "task_name": f"任务{task_id}",
        "status": status,
        "progress": 100.0,
        "message": "m",
        "created_at": created_at,
        "started_at": None,
        "completed_at": None,
        "created_by": "root",
        "params": {},
        "result": None,
    }
    tasks_mod._tasks[task_id] = rec
    return rec


def _capture_add_task():
    captured = {}

    def _capture(self, func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args

    return captured, patch.object(BackgroundTasks, "add_task", _capture)


# ==================== 列表 / 统计 / 详情 / 运行计数 ====================


class TestListAndStats:
    def test_list_filter_and_pagination(self, tk_client):
        _seed("a1", status="completed", task_type="backup", created_at=_iso(3))
        _seed("a2", status="running", task_type="data_import", created_at=_iso(1))
        _seed("a3", status="running", task_type="backup", created_at=_iso(2))
        resp = tk_client.get(f"{BASE}?status=running&task_type=backup&page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["task_id"] == "a3"

    def test_list_sort_desc_and_slice(self, tk_client):
        _seed("b1", created_at=_iso(3))
        _seed("b2", created_at=_iso(1))
        _seed("b3", created_at=_iso(2))
        resp = tk_client.get(f"{BASE}?page=2&page_size=2")
        data = resp.json()["data"]
        assert data["total"] == 3
        assert [i["task_id"] for i in data["items"]] == ["b1"]  # 倒序第3个

    def test_stats(self, tk_client):
        _seed("c1", status="pending", task_type="backup")
        _seed("c2", status="running", task_type="backup")
        _seed("c3", status="completed", task_type="other")
        resp = tk_client.get(f"{BASE}/stats")
        data = resp.json()["data"]
        assert data["total"] == 3
        assert data["by_status"] == {"pending": 1, "running": 1, "completed": 1}
        assert data["by_type"] == {"backup": 2, "other": 1}
        assert data["active_count"] == 2

    def test_get_task_found(self, tk_client):
        _seed("d1")
        resp = tk_client.get(f"{BASE}/d1")
        assert resp.status_code == 200
        assert resp.json()["data"]["task_id"] == "d1"

    def test_get_task_404(self, tk_client):
        resp = tk_client.get(f"{BASE}/ghost")
        assert resp.status_code == 404

    def test_running_count(self, tk_client):
        _seed("e1", status="running")
        _seed("e2", status="pending")
        _seed("e3", status="completed")
        resp = tk_client.get(f"{BASE}/running/count")
        data = resp.json()["data"]
        assert data == {"running": 1, "pending": 1, "total_active": 2}


# ==================== 创建任务 + 后台执行函数 ====================


class TestCreateTask:
    def test_create_and_execute_success(self, tk_client):
        captured, p = _capture_add_task()
        with p:
            resp = tk_client.post(
                BASE,
                json={"task_type": "backup", "task_name": "周备份", "params": {"k": 1}},
            )
        assert resp.status_code == 200
        task_id = resp.json()["data"]["task_id"]
        record = tasks_mod._tasks[task_id]
        assert record["created_by"] == "root"
        assert record["params"] == {"k": 1}
        assert record["status"] == "pending"

        # 手动驱动后台执行（屏蔽 sleep）
        with patch.object(time, "sleep", return_value=None):
            captured["func"](*captured["args"])
        record = tasks_mod._tasks[task_id]
        assert record["status"] == "completed"
        assert record["progress"] == 100.0
        assert record["result"] == {"success": True, "message": "任务执行成功"}
        assert record["started_at"] is not None
        assert record["completed_at"] is not None

    def test_execute_with_missing_task_returns(self, tk_client):
        """后台执行时任务记录已被删除 → 直接返回（覆盖 193-195）"""
        captured, p = _capture_add_task()
        with p:
            resp = tk_client.post(BASE, json={"task_name": "x"})
        assert resp.status_code == 200
        captured["func"]("ghost-id")  # 不抛异常即通过

    def test_execute_failure_branch(self, tk_client):
        """执行过程异常 → failed 状态（覆盖 213-217）"""
        captured, p = _capture_add_task()
        with p:
            resp = tk_client.post(BASE, json={"task_name": "会失败"})
        task_id = resp.json()["data"]["task_id"]
        with patch.object(time, "sleep", side_effect=RuntimeError("炸了啊")):
            captured["func"](*captured["args"])
        record = tasks_mod._tasks[task_id]
        assert record["status"] == "failed"
        assert "炸了啊" in record["message"]
        assert record["result"]["success"] is False


# ==================== 取消 / 删除 ====================


class TestCancelAndDelete:
    def test_cancel_pending(self, tk_client):
        _seed("f1", status="pending")
        resp = tk_client.post(f"{BASE}/f1/cancel")
        assert resp.status_code == 200
        rec = tasks_mod._tasks["f1"]
        assert rec["status"] == "cancelled"
        assert rec["completed_at"] is not None

    def test_cancel_404(self, tk_client):
        resp = tk_client.post(f"{BASE}/ghost/cancel")
        assert resp.status_code == 404

    def test_cancel_completed_400(self, tk_client):
        _seed("f2", status="completed")
        resp = tk_client.post(f"{BASE}/f2/cancel")
        assert resp.status_code == 400

    def test_delete_completed(self, tk_client):
        _seed("g1", status="completed")
        resp = tk_client.delete(f"{BASE}/g1")
        assert resp.status_code == 200
        assert "g1" not in tasks_mod._tasks

    def test_delete_404(self, tk_client):
        resp = tk_client.delete(f"{BASE}/ghost")
        assert resp.status_code == 404

    def test_delete_running_400(self, tk_client):
        _seed("g2", status="running")
        resp = tk_client.delete(f"{BASE}/g2")
        assert resp.status_code == 400
