# -*- coding: utf-8 -*-
"""备份 cron 调度（解析 / next_run / 热重排 / job 闭包）的分支覆盖。

这些逻辑是新增的自动备份唯一事实源：解析错误必须 fail-closed，热重排必须
只在调度器已启动时生效，job 触发必须尊重停止标志。
"""
from datetime import datetime

import pytest
from unittest.mock import MagicMock, patch

import app.services.backup_scheduler as bm


class FakeTimer:
    instances = []

    def __init__(self, delay, callback, *args, **kwargs):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.name = kwargs.get("name", "")
        FakeTimer.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        pass

    def is_alive(self):
        return False


@pytest.fixture(autouse=True)
def reset_scheduler():
    bm.stop_backup_scheduler()
    bm._backup_timer = None
    bm._scheduler_started = False
    bm._stopping.clear()
    FakeTimer.instances = []
    yield
    bm.stop_backup_scheduler()
    bm._backup_timer = None
    bm._scheduler_started = False
    bm._stopping.clear()
    FakeTimer.instances = []


class TestParseBackupSchedule:
    @pytest.mark.parametrize(
        "schedule,expected",
        [
            ("0 2 * * *", (0, 2, None, None)),
            ("30 3 15 * *", (30, 3, 15, None)),
            ("15 4 * * 1", (15, 4, None, 1)),
        ],
    )
    def test_valid_schedules(self, schedule, expected):
        assert bm.parse_backup_schedule(schedule) == expected

    @pytest.mark.parametrize(
        "schedule",
        [
            "0 2 * *",
            "a 2 * * *",
            "70 2 * * *",
            "0 25 * * *",
            "0 2 1 2 *",
            "0 2 1 * 1",
            "0 2 a * *",
            "0 2 0 * *",
            "0 2 * * 7",
        ],
    )
    def test_invalid_schedules_raise(self, schedule):
        with pytest.raises(ValueError):
            bm.parse_backup_schedule(schedule)


class TestNextBackupRun:
    def test_month_day_and_weekday_skip_to_next_match(self):
        month_hit = bm.next_backup_run("0 2 31 * *", now=datetime(2025, 1, 1, 3, 0))
        assert month_hit.year == 2025 and month_hit.month == 1 and month_hit.day == 31

        week_hit = bm.next_backup_run("0 2 * * 1", now=datetime(2025, 1, 6, 3, 0))
        assert week_hit.weekday() == 0
        assert week_hit > datetime(2025, 1, 6, 3, 0)

    def test_unreachable_cron_guard_is_reached_with_stuck_clock(self):
        class StuckDateTime(datetime):
            @classmethod
            def now(cls):
                return cls(2025, 1, 1, 3, 0)

            def __add__(self, other):
                return self

        with patch.object(bm, "datetime", StuckDateTime):
            with pytest.raises(ValueError, match="一年内"):
                bm.next_backup_run("0 2 * * *")


class TestAutoBackupCronScheduler:
    def test_invalid_config_falls_back_to_daily_2am(self):
        with patch.object(bm, "get_config", return_value="bad"), patch(
            "app.services.backup_scheduler.threading.Timer", FakeTimer
        ):
            bm._schedule_auto_backup_cron()
        assert bm._backup_timer is not None
        assert bm._backup_timer.name == "scheduler-auto_backup"

    def test_job_runs_and_reschedules_while_running(self):
        with patch.object(bm, "get_config", return_value="30 3 * * *"), patch(
            "app.services.backup_scheduler.threading.Timer", FakeTimer
        ):
            bm._schedule_auto_backup_cron()
        timer = bm._backup_timer
        assert timer is not None
        bm._scheduler_started = True

        with patch.object(
            bm, "_run_scheduler_job"
        ) as run_job, patch.object(
            bm, "_schedule_auto_backup_cron"
        ) as reschedule:
            timer.callback()

        run_job.assert_called_once()
        reschedule.assert_called_once()

    def test_job_does_not_run_or_reschedule_after_stop(self):
        with patch.object(bm, "get_config", return_value="30 3 * * *"), patch(
            "app.services.backup_scheduler.threading.Timer", FakeTimer
        ):
            bm._schedule_auto_backup_cron()
        timer = bm._backup_timer
        assert timer is not None
        bm._stopping.set()

        with patch.object(
            bm, "_run_scheduler_job"
        ) as run_job, patch.object(
            bm, "_schedule_auto_backup_cron"
        ) as reschedule:
            timer.callback()

        run_job.assert_not_called()
        reschedule.assert_not_called()

    def test_job_does_not_reschedule_when_job_stops_scheduler(self):
        """job 执行后置停止标志：不得再登记下一次 auto_backup Timer。"""
        with patch.object(bm, "get_config", return_value="30 3 * * *"), patch(
            "app.services.backup_scheduler.threading.Timer", FakeTimer
        ):
            bm._schedule_auto_backup_cron()
        timer = bm._backup_timer
        assert timer is not None

        def _run_job_and_stop(*args, **kwargs):
            bm._stopping.set()

        with patch.object(bm, "_run_scheduler_job", side_effect=_run_job_and_stop), patch.object(
            bm, "_schedule_auto_backup_cron"
        ) as reschedule:
            timer.callback()

        run_job_args = None
        assert bm._stopping.is_set()
        assert reschedule.call_count == 0
        assert run_job_args is None

    def test_reschedule_only_when_started(self):
        with patch.object(bm, "_schedule_auto_backup_cron") as reschedule:
            bm.reschedule_auto_backup_job()
        reschedule.assert_not_called()

        bm._scheduler_started = True
        with patch.object(bm, "_schedule_auto_backup_cron") as reschedule:
            bm.reschedule_auto_backup_job()
        reschedule.assert_called_once()
