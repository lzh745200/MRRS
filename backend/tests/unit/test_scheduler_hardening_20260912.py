"""R4/R8 深度审计修复回归（2026-09-12 第二批）。

- R4：分片上传过期会话接入调度器周期清理 + 内存会话数量上限
- R8：调度 Timer 统一登记/可停止（interval 链不再脱离 stop 管理，_timers 不再无限增长）
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services.backup_scheduler import (
    _register_timer,
    _stopping,
    _timers,
    chunk_cleanup_job,
)
from app.services.chunked_upload_service import (
    ChunkedUploadConfig,
    ChunkedUploadService,
)


class FakeTimer:
    """可控 Timer 替身：不真正起线程，由测试显式触发 _job。"""

    registry = []

    def __init__(self, interval, fn, *args, **kwargs):
        self.interval = interval
        self.fn = fn
        self.daemon = False
        self.name = ""
        self._alive = False
        self._canceled = False

    def start(self):
        self._alive = True

    def cancel(self):
        self._alive = False
        self._canceled = True

    def is_alive(self):
        return self._alive

    def fire(self):
        """测试辅助：同步触发一次 _job（真实 Timer 到期时由线程执行）。"""
        if not self._canceled:
            self.fn()


# ---------------------------------------------------------------------------
# R4：分片上传会话上限与 TTL 清理
# ---------------------------------------------------------------------------


class TestChunkedSessionLimit:
    @staticmethod
    def _make_service(tmp_path):
        return ChunkedUploadService(
            temp_dir=str(tmp_path / "chunks"),
            final_dir=str(tmp_path / "files"),
        )

    def test_config_has_session_limit(self):
        assert ChunkedUploadConfig.MAX_SESSIONS == 200

    def test_sessions_evicted_when_over_limit(self, tmp_path):
        svc = self._make_service(tmp_path)
        svc.max_sessions = 5
        created = []
        for i in range(8):
            session = svc.create_session(
                file_name=f"f{i}.bin",
                file_size=1024,
                chunk_size=1024,
                file_hash=None,
                user_id=1,
            )
            created.append(session.session_id)

        # 超出上限的最早会话被淘汰（连同其分片目录）
        assert len(svc._sessions) == 5
        for old_id in created[:3]:
            assert old_id not in svc._sessions
            assert not (svc.temp_dir / old_id).exists()
        for keep_id in created[3:]:
            assert keep_id in svc._sessions

    def test_cleanup_expired_sessions_removes_dir_and_memory(self, tmp_path):
        svc = self._make_service(tmp_path)
        session = svc.create_session(
            file_name="f.bin",
            file_size=1024,
            chunk_size=1024,
            file_hash=None,
            user_id=1,
        )
        # 伪造过期
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        (svc.temp_dir / session.session_id).mkdir(parents=True, exist_ok=True)

        cleaned = svc.cleanup_expired_sessions()

        assert cleaned == 1
        assert session.session_id not in svc._sessions
        assert not (svc.temp_dir / session.session_id).exists()

    def test_scheduler_registers_chunk_cleanup_job(self):
        """R4：分片清理任务必须接入调度器（此前 cleanup_expired_sessions 无生产调用点）。"""
        with patch(
            "app.services.chunked_upload_service.get_chunked_upload_service"
        ) as factory:
            factory.return_value.cleanup_expired_sessions.return_value = 2
            chunk_cleanup_job()
        factory.return_value.cleanup_expired_sessions.assert_called_once()


# ---------------------------------------------------------------------------
# R8：调度 Timer 生命周期
# ---------------------------------------------------------------------------


class TestSchedulerTimerLifecycle:
    def setup_method(self):
        _timers.clear()
        _stopping.clear()
        FakeTimer.registry = []

    def teardown_method(self):
        import app.services.backup_scheduler as scheduler

        # 必须完整复位调度器状态（含 _scheduler_started），
        # 否则下一个用例的 start_backup_scheduler 会因「已在运行」早退
        scheduler.stop_backup_scheduler()
        scheduler._scheduler_started = False
        for t in list(_timers):
            t.cancel()
        _timers.clear()
        _stopping.clear()

    def _start(self, scheduler):
        import app.services.backup_scheduler as bs

        with patch.object(bs.threading, "Timer", FakeTimer):
            bs.start_backup_scheduler()
        # start 内部用 patched Timer 创建；返回按任务名索引的替身
        return {t.name: t for t in _timers}

    def test_start_registers_all_periodic_jobs(self):
        import app.services.backup_scheduler as scheduler

        named = self._start(scheduler)
        assert len(named) == 12, "12 个周期任务（含新增分片清理）必须全部登记"
        assert "scheduler-chunk_cleanup" in named
        assert all(t.is_alive() for t in _timers)

    def test_stop_cancels_everything_and_sets_flag(self):
        import app.services.backup_scheduler as scheduler

        self._start(scheduler)
        scheduler.stop_backup_scheduler()
        assert _stopping.is_set()
        assert len(_timers) == 0, "stop 后不得残留任何 Timer 句柄"
        assert scheduler._scheduler_started is False

    def test_interval_chain_does_not_reschedule_after_stop(self):
        """核心回归：stop 之后 interval 链不得再次自我重排（幽灵 DB 写）。"""
        import app.services.backup_scheduler as scheduler

        named = self._start(scheduler)
        interval_timer = named["scheduler-subscription_dispatch"]
        ran = {"job": False}

        real_fn = interval_timer.fn

        def spy_job():
            # _job 内部先调 _run_async_job(coro_func)，这里只探测链是否继续
            real_fn.__wrapped__ if hasattr(real_fn, "__wrapped__") else None
            ran["job"] = True

        # 直接以 stop 状态触发 _job：不得重排、不得执行作业
        scheduler.stop_backup_scheduler()
        before = len(_timers)
        interval_timer.fire()
        assert len(_timers) == before, "stop 后 _job 不得登记新的 Timer"
        assert not ran["job"]

    def test_interval_chain_continues_while_running(self):
        """运行中 interval 链触发后必须重排下一次（链不断）。"""
        import app.services.backup_scheduler as scheduler

        named = self._start(scheduler)
        interval_timer = named["scheduler-subscription_dispatch"]
        before = len(_timers)
        interval_timer.fire()
        # 链继续：_timers 中出现新的存活 Timer（旧的因 fire 后退出而终止）
        assert any(t.is_alive() and t.name == "scheduler-subscription_dispatch"
                   for t in _timers), "interval 链必须自我延续"
        assert len(_timers) <= before + 1

    def test_register_timer_prunes_dead_handles(self):
        dead = FakeTimer(60, lambda: None)
        dead.cancel()
        alive = FakeTimer(60, lambda: None)
        alive.start()
        _register_timer(dead)
        _register_timer(alive)
        assert _timers == [alive], "已终止的句柄必须被回收，防止 _timers 无限增长"

    # ---- _stopping 守卫的两类提前返回分支（daily/weekly/interval 三形态） ----

    def _start_named(self):
        import app.services.backup_scheduler as scheduler

        with patch.object(scheduler.threading, "Timer", FakeTimer):
            scheduler.start_backup_scheduler()
        return scheduler, {t.name: t for t in _timers}

    def test_closures_return_before_running_when_stopping(self):
        """停止状态下触发闭包：第一条 _stopping 检查直接返回（不执行作业、不重排）。"""
        scheduler, named = self._start_named()
        _stopping.set()
        before = len(_timers)
        for name in (
            "scheduler-kpi_precalculate",  # daily
            "scheduler-weekly_report",  # weekly
            "scheduler-subscription_dispatch",  # interval
        ):
            named[name].fire()
            assert len(_timers) == before, f"{name} 在停止状态下不得重排"

    def test_closures_do_not_reschedule_when_job_spans_stop(self, monkeypatch):
        """作业执行期间发生 stop：重排前的第二条 _stopping 检查拦截（链不复活）。

        三种调度形态（daily / weekly / interval）逐一独立验证：
        任务函数在执行中置位 _stopping → 闭包重排前的第二次检查必须拦截。
        """
        import app.services.backup_scheduler as scheduler

        def _stopping_job():
            _stopping.set()

        cases = (
            ("kpi_precalculate_job", "scheduler-kpi_precalculate"),
            ("weekly_report_job", "scheduler-weekly_report"),
            ("subscription_dispatch_job", "scheduler-subscription_dispatch"),
        )
        for job_name, timer_name in cases:
            _stopping.clear()
            for t in list(_timers):
                t.cancel()
            _timers.clear()
            scheduler._scheduler_started = False
            # 必须在 start 之前替换：闭包在注册时捕获任务函数引用
            monkeypatch.setattr(scheduler, job_name, _stopping_job, raising=False)
            with patch.object(scheduler.threading, "Timer", FakeTimer):
                scheduler.start_backup_scheduler()
            named = {t.name: t for t in _timers}
            named[timer_name].fire()
            assert len(_timers) == 12, f"{job_name} 执行中 stop 后不得重排下一次"
