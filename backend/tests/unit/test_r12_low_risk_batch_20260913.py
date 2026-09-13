"""R12 低危一致性批量项回归（遗留风险治理计划 2026-09-13 · W4 批次）。

对应《deliverables/遗留风险彻底解决方案计划-2026-09-12.md》§R12：

- R12-2 慢请求/慢 SQL 计数器并发自增（原裸 "+=" 会丢计数 → 统计口径失真）
- R12-3 恢复演练状态一致性快照（原逐字段读写交错 → /health 撕裂结论）
- R12-6 内存任务表终态回收（原 _tasks 只增不减）
- R12-7 后台任务调度契约（见 tests/unit/test_async_utils.py 同步更新）
- R12-4 提醒线程双启动窗口、R12-5 优雅关闭（见 test_reminder_service.py /
  test_system_api_cov.py 的同步断言更新）
"""

import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _iso(**delta) -> str:
    return (datetime.now(timezone.utc) - timedelta(**delta)).isoformat()


def _record(task_id: str, status: str = "completed", **delta) -> dict:
    return {
        "task_id": task_id,
        "task_type": "backup",
        "task_name": f"任务{task_id}",
        "status": status,
        "progress": 100.0,
        "message": "m",
        "created_at": _iso(**delta) if delta else _iso(),
        "started_at": None,
        "completed_at": _iso(**delta) if delta else _iso(),
        "created_by": "root",
        "params": {},
        "result": None,
    }


# ══════════════════════════════════════════════════════════════════
# R12-2 计数器并发自增
# ══════════════════════════════════════════════════════════════════


class TestSlowRequestCounters:
    def test_bump_increments_named_counter(self):
        from app.middleware import slow_request_monitor as m

        before = m.get_slow_stats()["slow_sql_count"]
        m._bump("slow_sql_count", 3)
        assert m.get_slow_stats()["slow_sql_count"] == before + 3

    def test_concurrent_bumps_lose_nothing(self):
        """8 线程 × 400 次自增必须一次不丢（裸 += 在高并发下必丢）。"""
        from app.middleware import slow_request_monitor as m

        key = "total_requests"
        before = m.get_slow_stats()[key]
        threads_count, per_thread = 8, 400
        barrier = threading.Barrier(threads_count)

        def worker():
            barrier.wait()
            for _ in range(per_thread):
                m._bump(key)

        workers = [threading.Thread(target=worker) for _ in range(threads_count)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

        assert m.get_slow_stats()[key] == before + threads_count * per_thread

    def test_stats_snapshot_keeps_public_shape(self):
        from app.middleware import slow_request_monitor as m

        stats = m.get_slow_stats()
        for key in ("total_requests", "slow_api_count", "slow_sql_count"):
            assert key in stats
        assert "slow_api_peak_ms" in stats


# ══════════════════════════════════════════════════════════════════
# R12-3 恢复演练状态快照
# ══════════════════════════════════════════════════════════════════


class TestRestoreDrillSnapshot:
    def test_snapshot_is_a_detached_copy(self):
        from app.services.restore_drill_service import RESTORE_DRILL_STATUS, snapshot_status

        snap = snapshot_status()
        snap["status"] = "tampered"
        assert RESTORE_DRILL_STATUS["status"] != "tampered"

    def test_update_status_writes_consistent_snapshot(self):
        from app.services import restore_drill_service as m

        m._update_status("ok", "D:/backups/backup_20260913.zip", None, 4)
        snap = m.snapshot_status()
        assert snap["status"] == "ok"
        assert snap["backup_file"] == "backup_20260913.zip"
        assert snap["tables_checked"] == 4
        assert snap["error_type"] is None
        assert snap["checked_at"]

    def test_health_reads_snapshot_not_module_dict(self):
        """/health 必须经 snapshot_status()（撕裂读防线，main.py 侧接线）。"""
        from fastapi.testclient import TestClient

        from app.main import app

        fake = {
            "status": "fail",
            "checked_at": "2026-09-13T00:00:00",
            "backup_file": "backup_probe.zip",
            "error_type": "FileNotFoundError",
        }
        with patch("app.services.restore_drill_service.snapshot_status", return_value=fake):
            resp = TestClient(app).get("/health")
        assert resp.status_code == 200
        assert resp.json()["restore_drill"] == {
            "status": "fail",
            "checked_at": "2026-09-13T00:00:00",
            "backup_file": "backup_probe.zip",
            "error_type": "FileNotFoundError",
        }


# ══════════════════════════════════════════════════════════════════
# R12-6 内存任务表终态回收
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_tasks():
    import app.api.v1.system.tasks as t

    t._tasks.clear()
    yield t
    t._tasks.clear()


class TestTaskRetention:
    def test_expired_terminal_tasks_are_reclaimed(self, clean_tasks):
        t = clean_tasks
        t._tasks["done"] = _record("done", "completed", hours=2)
        t._tasks["failed"] = _record("failed", "failed", hours=3)
        t._tasks["cancelled"] = _record("cancelled", "cancelled", hours=5)
        assert t._purge_finished_tasks_locked() == 3
        assert t._tasks == {}

    def test_fresh_and_active_tasks_survive(self, clean_tasks):
        t = clean_tasks
        t._tasks["fresh"] = _record("fresh", "completed", minutes=10)
        t._tasks["running"] = _record("running", "running", hours=9)
        t._tasks["pending"] = _record("pending", "pending", hours=9)
        assert t._purge_finished_tasks_locked() == 0
        assert set(t._tasks) == {"fresh", "running", "pending"}

    def test_naive_timestamp_is_handled(self, clean_tasks):
        """completed_at 为无时区 naive 串（旧记录/外部写入）也要能判定过期。

        本仓写入侧统一是 datetime.now(timezone.utc).isoformat()，naive 串按 UTC
        解释（与既有 to_dict()/比较口径一致）。
        """
        t = clean_tasks
        rec = _record("naive", "completed")
        naive_utc = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4)
        rec["completed_at"] = naive_utc.isoformat()
        t._tasks["naive"] = rec
        assert t._purge_finished_tasks_locked() == 1

    def test_malformed_or_missing_timestamp_is_kept(self, clean_tasks):
        """时间戳缺失/损坏时保守保留（宁可占内存也不误删可见记录）。"""
        t = clean_tasks
        broken = _record("broken", "completed")
        broken["completed_at"] = None
        broken["created_at"] = "not-a-date"
        t._tasks["broken"] = broken
        assert t._purge_finished_tasks_locked() == 0
        assert "broken" in t._tasks

    def test_retention_window_is_one_hour(self, clean_tasks):
        from app.api.v1.system.tasks import _TASK_RETENTION_SECONDS

        assert _TASK_RETENTION_SECONDS == 3600

    async def test_list_endpoint_purges_expired(self, clean_tasks):
        t = clean_tasks
        t._tasks["stale"] = _record("stale", "completed", hours=2)
        t._tasks["live"] = _record("live", "running")
        out = await t.list_tasks(None, None, 1, 20, None)
        assert out["data"]["total"] == 1
        assert out["data"]["items"][0]["task_id"] == "live"

    async def test_stats_endpoint_purges_expired(self, clean_tasks):
        t = clean_tasks
        t._tasks["stale"] = _record("stale", "failed", hours=2)
        out = await t.get_task_stats(None)
        assert out["data"]["total"] == 0
        assert out["data"]["active_count"] == 0

    async def test_running_count_purges_expired(self, clean_tasks):
        t = clean_tasks
        t._tasks["stale"] = _record("stale", "completed", hours=2)
        t._tasks["live"] = _record("live", "running")
        out = await t.get_running_task_count()
        assert out["data"]["running"] == 1

    def test_create_record_triggers_purge(self, clean_tasks):
        """写入路径顺带回收：长跑进程不依赖任何一次查询就会收敛内存。"""
        t = clean_tasks
        t._tasks["stale"] = _record("stale", "completed", hours=2)
        t._create_task_record("backup", "新任务", "root", None)
        assert "stale" not in t._tasks
        assert len(t._tasks) == 1
