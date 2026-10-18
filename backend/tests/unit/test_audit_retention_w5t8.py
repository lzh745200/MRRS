"""W5-T8 回归：审计/日志大表保留期清理 + 调度接线。

背景（检测 P1-3）：audit_logs / api_access_logs / login_attempts /
security_events / data_export_logs / token_blacklist 六表只增不减（audit_middleware
在 H9 批量缓冲前为每请求一写），长期运行持续抬高库体积与索引维护成本。本文件锁定
清理契约：超期即删、期内保留、保留期可配、0/负数=禁用、永久吊销条目绝不删除、
删除必须提交；以及作业读取配置、返回/记录删除数、失败不外抛与调度注册。
"""

import contextlib
import logging
import threading
from datetime import timedelta
from unittest.mock import MagicMock

from app.models.audit import (
    APIAccessLog,
    AuditLog,
    DataExportLog,
    LoginAttempt,
    SecurityEvent,
)
from app.models.token_blacklist import TokenBlacklist
from app.services.audit_retention_service import (
    DEFAULT_RETENTION_DAYS,
    purge_expired_audit_rows,
)
from app.utils.time_utils import utcnow

TABLE_LABELS = (
    "audit_logs",
    "api_access_logs",
    "login_attempts",
    "security_events",
    "data_export_logs",
    "token_blacklist",
)


def _cfg(mapping):
    """构造 get_config 替身：命中映射返回配置值，未命中返回调用方默认值。"""

    def _get(key, default=None):
        return mapping.get(key, default)

    return _get


def _rows_at(now, age_days):
    """给五张「按时间列清理」的表各造一行（时间为 ``now - age_days``）。"""
    ts = now - timedelta(days=age_days)
    return [
        AuditLog(action="create", created_at=ts),
        APIAccessLog(endpoint="/api/x", method="GET", created_at=ts),
        LoginAttempt(username="zhangsan", attempt_time=ts),
        SecurityEvent(event_type="login", severity="low", description="事件", created_at=ts),
        DataExportLog(export_type="full", created_at=ts),
    ]


class TestPurgeExpiredAuditRows:
    def test_deletes_old_rows_and_keeps_fresh(self, real_db_session):
        """默认保留期：全部超期行删除，期内行保留；token 只删已过期条目。"""
        db = real_db_session
        now = utcnow()
        old_rows = _rows_at(now, 400)  # 超过最长默认保留期（365 天）
        fresh_rows = _rows_at(now, 1)
        db.add_all(old_rows + fresh_rows)
        db.add_all(
            [
                TokenBlacklist(token_jti="expired", expires_at=now - timedelta(days=1)),
                TokenBlacklist(token_jti="valid", expires_at=now + timedelta(days=1)),
                TokenBlacklist(token_jti="permanent", expires_at=None),
            ]
        )
        db.commit()

        counts = purge_expired_audit_rows(db, DEFAULT_RETENTION_DAYS, now=now)

        assert counts == {
            "audit_logs": 1,
            "api_access_logs": 1,
            "login_attempts": 1,
            "security_events": 1,
            "data_export_logs": 1,
            "token_blacklist": 1,
        }
        assert {row.id for row in db.query(AuditLog).all()} == {fresh_rows[0].id}
        assert {row.id for row in db.query(APIAccessLog).all()} == {fresh_rows[1].id}
        assert {row.id for row in db.query(LoginAttempt).all()} == {fresh_rows[2].id}
        assert {row.id for row in db.query(SecurityEvent).all()} == {fresh_rows[3].id}
        assert {row.id for row in db.query(DataExportLog).all()} == {fresh_rows[4].id}
        # 永久吊销（expires_at IS NULL）绝不能被清掉：W1 安全不变量
        assert {row.token_jti for row in db.query(TokenBlacklist).all()} == {"valid", "permanent"}

    def test_boundary_row_exactly_at_cutoff_is_kept(self, real_db_session):
        """判定为严格早于截止点：恰好落在 cutoff 上的行保留（< 而非 <=）。"""
        db = real_db_session
        now = utcnow()
        exact = AuditLog(action="create", created_at=now - timedelta(days=180))
        just_older = AuditLog(action="create", created_at=now - timedelta(days=180, seconds=1))
        db.add_all([exact, just_older])
        db.commit()

        counts = purge_expired_audit_rows(db, DEFAULT_RETENTION_DAYS, now=now)

        assert counts["audit_logs"] == 1
        assert {row.id for row in db.query(AuditLog).all()} == {exact.id}

    def test_retention_override_and_default_fallback(self, real_db_session):
        """只覆盖传入的键；未传键回退默认值（而非 0/禁用）——防漏传静默停清理。"""
        db = real_db_session
        now = utcnow()
        audit_60d = AuditLog(action="create", created_at=now - timedelta(days=60))
        login_60d = LoginAttempt(username="zhangsan", attempt_time=now - timedelta(days=60))
        db.add_all([audit_60d, login_60d])
        db.commit()

        counts = purge_expired_audit_rows(db, {"audit_log_retention_days": 30}, now=now)

        # audit 覆盖为 30 天 → 60 天前删除（若用默认 180 天则会保留）
        assert counts["audit_logs"] == 1
        assert db.query(AuditLog).count() == 0
        # login 未传键 → 默认 90 天 → 60 天前保留
        assert counts["login_attempts"] == 0
        assert db.query(LoginAttempt).count() == 1

    def test_non_positive_retention_disables_table(self, real_db_session):
        """0/负数 = 显式禁用该表清理（防误配清空整表）。"""
        db = real_db_session
        now = utcnow()
        ancient = AuditLog(action="create", created_at=now - timedelta(days=3650))
        ancient_login = LoginAttempt(username="zhangsan", attempt_time=now - timedelta(days=3650))
        db.add_all([ancient, ancient_login])
        db.commit()

        counts = purge_expired_audit_rows(
            db,
            {"audit_log_retention_days": 0, "login_attempt_retention_days": -1},
            now=now,
        )

        assert counts["audit_logs"] == 0
        assert counts["login_attempts"] == 0
        assert db.query(AuditLog).count() == 1
        assert db.query(LoginAttempt).count() == 1

    def test_deletes_are_committed(self, real_db_session, monkeypatch):
        """get_db() 成功路径不 commit：清理必须显式提交，否则静默回滚。"""
        import app.services.audit_retention_service as ars

        db = real_db_session
        now = utcnow()
        db.add(AuditLog(action="create", created_at=now - timedelta(days=400)))
        db.commit()

        calls = []
        real_commit = ars.safe_commit

        def _spy(session):
            calls.append(session)
            return real_commit(session)

        monkeypatch.setattr(ars, "safe_commit", _spy)
        purge_expired_audit_rows(db, DEFAULT_RETENTION_DAYS, now=now)

        assert calls == [db]
        assert db.query(AuditLog).count() == 0


class TestRetentionDefaultsContract:
    def test_defaults_match_config_service(self):
        """默认保留期（服务层）与 SystemConfig 默认值（配置层）必须一致。"""
        from app.services.system_config_service import SystemConfigService

        assert DEFAULT_RETENTION_DAYS == {
            "audit_log_retention_days": 180,
            "api_access_log_retention_days": 180,
            "login_attempt_retention_days": 90,
            "security_event_retention_days": 365,
            "data_export_log_retention_days": 365,
        }
        for key, days in DEFAULT_RETENTION_DAYS.items():
            assert key in SystemConfigService.DEFAULT_CONFIGS, key
            assert SystemConfigService.DEFAULT_CONFIGS[key]["value"] == str(days), key


class TestAuditLogCleanupJob:
    def _run_job(self, monkeypatch, db, config=None):
        import asyncio

        import app.services.backup_scheduler as sched

        monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(db))
        monkeypatch.setattr(sched, "get_config", _cfg(config or {}))
        return asyncio.run(sched.audit_log_cleanup_job())

    def test_reads_config_and_returns_counts(self, real_db_session, monkeypatch, caplog):
        """配置覆盖生效（audit=10 天）、未配置表用默认值，计数写日志。"""
        db = real_db_session
        now = utcnow()
        db.add_all(
            [
                AuditLog(action="create", created_at=now - timedelta(days=20)),
                APIAccessLog(endpoint="/api/x", method="GET", created_at=now - timedelta(days=200)),
                LoginAttempt(username="zhangsan", attempt_time=now - timedelta(days=1)),
            ]
        )
        db.commit()

        with caplog.at_level(logging.INFO, logger="app.services.backup_scheduler"):
            counts = self._run_job(monkeypatch, db, {"audit_log_retention_days": "10"})

        assert counts["audit_logs"] == 1  # 20 天 > 覆盖的 10 天
        assert counts["api_access_logs"] == 1  # 200 天 > 默认 180 天
        assert counts["login_attempts"] == 0  # 1 天 < 默认 90 天
        assert db.query(AuditLog).count() == 0
        assert db.query(APIAccessLog).count() == 0
        assert db.query(LoginAttempt).count() == 1
        assert "审计日志保留期清理完成：删除 2 行" in caplog.text

    def test_noop_logs_when_nothing_expired(self, real_db_session, monkeypatch, caplog):
        """无超期数据：返回全 0 计数、保留数据、记「无超期数据」日志。"""
        db = real_db_session
        now = utcnow()
        db.add(AuditLog(action="create", created_at=now))
        db.commit()

        with caplog.at_level(logging.INFO, logger="app.services.backup_scheduler"):
            counts = self._run_job(monkeypatch, db)

        assert counts == {label: 0 for label in TABLE_LABELS}
        assert db.query(AuditLog).count() == 1
        assert "审计日志保留期清理完成：无超期数据" in caplog.text

    def test_swallows_errors_and_returns_empty_counts(self, monkeypatch, caplog):
        """清理异常：记 ERROR、不外抛（调度器不被拖垮），返回空计数。"""
        import asyncio

        import app.services.audit_retention_service as ars
        import app.services.backup_scheduler as sched

        monkeypatch.setattr(sched, "get_db_context", lambda: contextlib.nullcontext(MagicMock()))
        monkeypatch.setattr(sched, "get_config", _cfg({}))

        def _boom(*args, **kwargs):
            raise RuntimeError("db gone")

        monkeypatch.setattr(ars, "purge_expired_audit_rows", _boom)

        with caplog.at_level(logging.ERROR, logger="app.services.backup_scheduler"):
            counts = asyncio.run(sched.audit_log_cleanup_job())  # 不应抛出

        assert counts == {}
        assert "审计日志保留期清理失败" in caplog.text


class TestSchedulerRegistration:
    def test_job_registered_in_source(self):
        """接线断言：必须在 start_backup_scheduler 中按 04:20 每日注册。"""
        import inspect

        import app.services.backup_scheduler as bs

        src = inspect.getsource(bs.start_backup_scheduler)
        assert '_schedule_daily(audit_log_cleanup_job, 4, 20, "audit_log_cleanup")' in src

    def test_job_timer_created_on_start(self, monkeypatch):
        """启动调度器即创建 ``scheduler-audit_log_cleanup`` daemon Timer。"""
        import app.services.backup_scheduler as bs

        created = []

        class _FakeTimer:
            def __init__(self, delay, fn, args=(), kwargs=None):
                self.delay = delay
                self.fn = fn
                self.daemon = False
                self.name = None
                self.started = False
                self._alive = True

            def is_alive(self):
                return self._alive

            def start(self):
                self.started = True

            def cancel(self):
                self._alive = False

        def _factory(delay, fn, args=(), kwargs=None):
            timer = _FakeTimer(delay, fn, args, kwargs)
            created.append(timer)
            return timer

        monkeypatch.setattr(bs, "_scheduler_started", False)
        monkeypatch.setattr(bs, "_timers", [])
        monkeypatch.setattr(bs, "_stopping", threading.Event())
        monkeypatch.setattr(bs.threading, "Timer", _factory)

        bs.start_backup_scheduler()

        matched = [t for t in created if t.name == "scheduler-audit_log_cleanup"]
        assert len(matched) == 1
        assert matched[0].started is True
        assert matched[0].daemon is True
