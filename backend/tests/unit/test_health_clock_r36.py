# -*- coding: utf-8 -*-
"""R36 · `/health` 时钟漂移可见化（`app/main.py` + `app/startup/preflight.py`）

背景：``_check_clock_drift()`` 只写日志 —— 单机离线机器被手动改时间后，
"最近 N 天"统计漏数据、定时任务错时，但运维看 ``/health`` 一切正常。

本文件锁定：
1. ``/health`` 新增 ``clock`` 字段（恰好 ``{status, behind_days}``），
   值来自 preflight 的时钟检查；
2. 漂移 → ``status=warning``；正常 → ``ok``；检查本身异常 → ``unknown``（不 5xx）；
3. **不改既有契约**：顶层 ``status`` 仍为 ``ok``、HTTP 仍 200、``migration``
   等既有子对象键集合不变，不泄露绝对路径；
4. ``journal_mode`` 健康快照同样在 ``/health`` 可查（R36 第 1 项）。
"""
from unittest.mock import patch

from app.core import database


class TestHealthClockField:
    def test_clock_warning_when_drift_detected(self, client):
        payload = {"status": "warning", "behind_days": 3.2}
        with patch("app.startup.preflight.clock_health", return_value=payload):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["clock"] == {"status": "warning", "behind_days": 3.2}
        # 顶层状态不受影响：时钟漂移不阻断可用性
        assert body["status"] == "ok"

    def test_clock_ok_when_no_drift(self, client):
        payload = {"status": "ok", "behind_days": 0.0}
        with patch("app.startup.preflight.clock_health", return_value=payload):
            body = client.get("/health").json()

        assert body["clock"] == {"status": "ok", "behind_days": 0.0}

    def test_clock_unknown_when_check_raises(self, client):
        """附带信号失败不得让 /health 5xx（监控不能因附带项变成红灯）。"""
        with patch(
            "app.startup.preflight.clock_health", side_effect=RuntimeError("boom")
        ):
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["clock"] == {"status": "unknown", "behind_days": None}
        assert body["status"] == "ok"

    def test_clock_field_has_exactly_two_keys(self, client):
        """契约收紧：只出 status/behind_days，避免把内部细节（异常原文等）带出去。"""
        body = client.get("/health").json()
        assert set(body["clock"]) == {"status", "behind_days"}

    def test_existing_health_contract_preserved(self, client):
        """既有字段不得被改动（只增不改）。"""
        with patch(
            "app.startup.preflight.clock_health",
            return_value={"status": "ok", "behind_days": 0.0},
        ):
            body = client.get("/health").json()

        assert body["status"] == "ok"
        assert "version" in body
        assert set(body["migration"]) == {
            "at_head",
            "head",
            "error_type",
            "auto_migration_enabled",
        }
        assert set(body["backup"]) == {"same_volume_as_database"}
        assert "maintenance" in body
        assert "restore_drill" in body

    def test_health_does_not_leak_paths_with_clock(self, client):
        raw = client.get("/health").text
        assert "rural_revitalization.db" not in raw
        assert "\\\\" not in raw.replace("\\n", "")


class TestHealthDatabaseJournalMode:
    def test_database_block_exposes_journal_mode(self, client, monkeypatch):
        monkeypatch.setattr(
            database,
            "_database_health",
            {"journal_mode": "delete", "journal_mode_ok": False},
        )
        body = client.get("/health").json()

        assert body["database"]["journal_mode"] == "delete"
        assert body["database"]["journal_mode_ok"] is False

    def test_database_block_defaults_to_unknown(self, client, monkeypatch):
        monkeypatch.setattr(database, "_database_health", {})
        body = client.get("/health").json()

        assert body["database"]["journal_mode"] == "unknown"
        assert body["database"]["journal_mode_ok"] is None
