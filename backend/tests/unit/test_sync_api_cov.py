"""app.api.v1.sync 覆盖率攻坚测试

覆盖：
- GET /status：pending>0→syncing / pending=0→idle / 无记录last_sync=None
- GET /dashboard：全路径（action None→unknown / created_at None→unknown /
  success+failure 统计 / recent 截断20 / 包文件统计 / 磁盘信息）+
  空日志 success_rate=100.0 + 包目录不存在 + glob 异常降级
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user

BASE = "/api/v1/sync"


def _log(**kw):
    defaults = dict(
        id=1, action="export", created_at=datetime(2026, 7, 20, 10, 0, 0),
        username="root", resource_type="data", status="success", user_ip="127.0.0.1",
        started_at=datetime(2026, 7, 20, 10, 0, 0),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _db(last_log=None, pending=0, sync_logs=None):
    """单个全能 query mock：/status 用 first+count，/dashboard 用 all（端点内仅一次 db.query）"""
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = last_log
    q.count.return_value = pending
    q.all.return_value = sync_logs if sync_logs is not None else []
    db.query.return_value = q
    return db


@pytest.fixture
def client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="root")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = original


def _use_db(c, db):
    c.app.dependency_overrides[get_db] = lambda: db


class TestSyncStatus:
    def test_idle_with_last_sync(self, client):
        _use_db(client, _db(last_log=_log(), pending=0))
        resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["sync_status"] == "idle"
        assert data["last_sync"] == "2026-07-20T10:00:00"

    def test_syncing_when_pending(self, client):
        _use_db(client, _db(last_log=_log(), pending=3))
        data = client.get(f"{BASE}/status").json()["data"]
        assert data["sync_status"] == "syncing"
        assert data["pending_changes"] == 3

    def test_no_log_last_sync_none(self, client):
        _use_db(client, _db(last_log=None, pending=0))
        assert client.get(f"{BASE}/status").json()["data"]["last_sync"] is None

    def test_log_without_started_at(self, client):
        _use_db(client, _db(last_log=_log(started_at=None), pending=0))
        assert client.get(f"{BASE}/status").json()["data"]["last_sync"] is None


class TestSyncDashboard:
    def _patch_extras(self, uploads_exists=True, glob_error=False):
        """patch get_uploads_path 与 check_disk_space（均为函数内 import）"""
        uploads = MagicMock()
        uploads.exists.return_value = uploads_exists
        f1 = MagicMock()
        f1.stat.return_value = SimpleNamespace(st_size=2 * 1024 * 1024)
        f1.is_file.return_value = True
        if glob_error:
            uploads.glob.side_effect = OSError("fs gone")
        else:
            uploads.glob.side_effect = lambda pat: [f1] if pat == "*.zip" else []
        return [
            patch("app.utils.paths.get_runtime_uploads_path", return_value=uploads),
            patch("app.core.database.check_disk_space", return_value={"ok": True, "free_mb": 5000}),
        ]

    def test_dashboard_full_path(self, client):
        logs = [
            _log(id=1, action="export", status="success"),
            _log(id=2, action="import", status="failure", created_at=datetime(2026, 7, 21, 11, 0, 0)),
            _log(id=3, action=None, created_at=None, username=None, resource_type=None, status=None, user_ip=None),
        ]
        _use_db(client, _db(sync_logs=logs))
        patchers = self._patch_extras()
        for p in patchers:
            p.start()
        try:
            resp = client.get(f"{BASE}/dashboard?days=30")
        finally:
            for p in patchers:
                p.stop()
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 汇总
        assert data["summary"]["total_syncs"] == 3
        assert data["summary"]["success_count"] == 1
        assert data["summary"]["failure_count"] == 1
        assert data["summary"]["success_rate"] == 33.3
        # action None → unknown
        assert data["action_counts"]["unknown"] == 1
        assert data["action_counts"]["export"] == 1
        # created_at None → unknown 日期
        assert any(t["date"] == "unknown" for t in data["daily_trend"])
        # recent：None 字段回退
        act3 = data["recent_activities"][2]
        assert act3["time"] == ""
        assert act3["user"] == ""
        assert act3["status"] == "success"  # None → "success" 回退
        # 包文件统计（1 个 zip × 2MB）
        assert data["package_stats"]["total_packages"] == 1
        assert data["package_stats"]["total_size_mb"] == 2.0
        assert data["disk_info"]["ok"] is True

    def test_dashboard_empty_logs(self, client):
        _use_db(client, _db(sync_logs=[]))
        patchers = self._patch_extras(uploads_exists=False)
        for p in patchers:
            p.start()
        try:
            resp = client.get(f"{BASE}/dashboard")
        finally:
            for p in patchers:
                p.stop()
        data = resp.json()["data"]
        assert data["summary"]["total_syncs"] == 0
        assert data["summary"]["success_rate"] == 100.0
        assert data["package_stats"]["total_packages"] == 0

    def test_dashboard_glob_error_degrades(self, client):
        _use_db(client, _db(sync_logs=[]))
        patchers = self._patch_extras(glob_error=True)
        for p in patchers:
            p.start()
        try:
            resp = client.get(f"{BASE}/dashboard")
        finally:
            for p in patchers:
                p.stop()
        assert resp.status_code == 200
        assert resp.json()["data"]["package_stats"]["total_packages"] == 0

    def test_dashboard_recent_truncated_at_20(self, client):
        logs = [_log(id=i, created_at=datetime(2026, 7, 20, 10, i % 60, 0)) for i in range(25)]
        _use_db(client, _db(sync_logs=logs))
        patchers = self._patch_extras(uploads_exists=False)
        for p in patchers:
            p.start()
        try:
            resp = client.get(f"{BASE}/dashboard")
        finally:
            for p in patchers:
                p.stop()
        assert len(resp.json()["data"]["recent_activities"]) == 20
