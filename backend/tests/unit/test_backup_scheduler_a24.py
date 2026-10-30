"""app.services.backup_scheduler 调度内部闭包覆盖补充测试（a24）

缺口：245-246（重复启动跳过）、251-257（_run_async_job 成功/异常）、
267-268（daily _job 闭包）、283（weekly 目标时间已过顺延一周）、287-288（weekly _job 闭包）。
"""
from datetime import datetime

import pytest
from unittest.mock import patch

import app.services.backup_scheduler as bm


class FakeTimer:
    """替代 threading.Timer，记录回调而不真正调度。"""

    instances = []

    def __init__(self, delay, callback, *args, **kwargs):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.name = ""
        FakeTimer.instances.append(self)

    def start(self):
        pass

    def cancel(self):
        pass

    def is_alive(self):
        return False


@pytest.fixture(autouse=True)
def reset_scheduler_state():
    bm.stop_backup_scheduler()
    FakeTimer.instances = []
    yield
    bm.stop_backup_scheduler()
    FakeTimer.instances = []


def _start_with_fake_now(now):
    """以伪装的 datetime.now 与 FakeTimer 启动调度器。"""

    class FakeDateTime:
        @classmethod
        def now(cls):
            return now

        @classmethod
        def combine(cls, day, time_value):
            # next_backup_run 用 datetime.combine(day, time(...)) 计算 cron 目标；
            # 只伪装 now() 会让 combine 丢失（AttributeError），必须一并转发。
            return datetime.combine(day, time_value)

    with patch.object(bm, "datetime", FakeDateTime), \
         patch("app.services.backup_scheduler.threading.Timer", FakeTimer):
        bm.start_backup_scheduler()


class TestStartAlreadyStarted:
    def test_skip_when_already_running(self):
        bm._scheduler_started = True
        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer):
            bm.start_backup_scheduler()
        assert FakeTimer.instances == []
        assert bm._scheduler_started is True


class TestDailyJobClosure:
    def test_run_async_job_success(self):
        _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
        daily = next(t for t in FakeTimer.instances if t.name == "scheduler-kpi_precalculate")
        count_before = len(FakeTimer.instances)

        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer), \
             patch("app.services.backup_scheduler.kpi_precalculate_job"), \
             patch("asyncio.new_event_loop") as mock_new_loop, \
             patch("asyncio.set_event_loop") as mock_set_loop:
            daily.callback()

        mock_new_loop.assert_called_once_with()
        mock_set_loop.assert_called_once_with(mock_new_loop.return_value)
        loop = mock_new_loop.return_value
        loop.run_until_complete.assert_called_once()
        loop.close.assert_called_once()
        # _job 执行后会重新调度下一次
        assert len(FakeTimer.instances) == count_before + 1

    def test_run_async_job_exception_is_logged(self):
        _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
        daily = next(t for t in FakeTimer.instances if t.name == "scheduler-todo_reminder")
        count_before = len(FakeTimer.instances)

        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer), \
             patch("asyncio.new_event_loop", side_effect=RuntimeError("loop boom")):
            daily.callback()  # 异常被 _run_async_job 捕获并记录，不向上抛

        assert len(FakeTimer.instances) == count_before + 1


class TestWeeklySchedule:
    def test_weekly_target_passed_rolls_to_next_week(self):
        # 2025-01-06 是周一 07:00，周报目标为周一 06:30（已过）-> 顺延一周
        _start_with_fake_now(datetime(2025, 1, 6, 7, 0, 0))
        weekly = next(t for t in FakeTimer.instances if t.name == "scheduler-weekly_report")
        assert weekly.delay > 6 * 86400  # 约 7 天减 30 分钟

    def test_weekly_job_closure_runs_and_reschedules(self):
        _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
        weekly = next(t for t in FakeTimer.instances if t.name == "scheduler-weekly_report")
        count_before = len(FakeTimer.instances)

        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer), \
             patch("app.services.backup_scheduler.weekly_report_job"), \
             patch("asyncio.new_event_loop") as mock_new_loop, \
             patch("asyncio.set_event_loop"):
            weekly.callback()

        mock_new_loop.assert_called_once_with()
        assert len(FakeTimer.instances) == count_before + 1


class TestWeeklyAndIntervalReschedule:
    """触发周任务/间隔任务的 _job，覆盖其"执行后重排下一次"分支（695 / 718）。"""

    @staticmethod
    def _fire(timer):
        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer), \
             patch("asyncio.new_event_loop") as mock_new_loop, \
             patch("asyncio.set_event_loop"):
            timer.callback()
        return mock_new_loop

    def test_weekly_job_reschedules_after_fire(self):
        _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer):
            bm._schedule_weekly(_noop_coro, 0, 8, 0, "test_weekly_r27")
        weekly = next(t for t in FakeTimer.instances if t.name.endswith("test_weekly_r27"))
        count_before = len(FakeTimer.instances)

        self._fire(weekly)

        # _job 执行后按周粒度重排下一次
        assert len(FakeTimer.instances) == count_before + 1

    def test_interval_job_reschedules_after_fire(self):
        _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
        with patch("app.services.backup_scheduler.threading.Timer", FakeTimer):
            bm._schedule_interval(_noop_coro, 60, "test_interval_r27")
        interval = next(t for t in FakeTimer.instances if t.name.endswith("test_interval_r27"))
        count_before = len(FakeTimer.instances)

        self._fire(interval)

        # _job 执行后按间隔重建 Timer（718）
        assert len(FakeTimer.instances) == count_before + 1


async def _noop_coro():
    """调度器触发测试用的空协程工厂。"""


def test_weekly_job_does_not_reschedule_when_stopping():
    """作业执行期间收到停止信号 → 不再重排（695 return 分支）。"""
    _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
    with patch("app.services.backup_scheduler.threading.Timer", FakeTimer):
        bm._schedule_weekly(_noop_coro, 0, 8, 0, "test_weekly_stop")
    weekly = next(t for t in FakeTimer.instances if t.name.endswith("test_weekly_stop"))
    count_before = len(FakeTimer.instances)

    bm._stopping.set()  # 模拟执行期间调用了 stop()
    with patch("app.services.backup_scheduler.threading.Timer", FakeTimer), \
         patch("asyncio.new_event_loop"), patch("asyncio.set_event_loop"):
        weekly.callback()

    assert len(FakeTimer.instances) == count_before


def test_interval_job_does_not_reschedule_when_stopping():
    """间隔任务同理（718 return 分支）。"""
    _start_with_fake_now(datetime(2025, 1, 7, 10, 0, 0))
    with patch("app.services.backup_scheduler.threading.Timer", FakeTimer):
        bm._schedule_interval(_noop_coro, 60, "test_interval_stop")
    interval = next(t for t in FakeTimer.instances if t.name.endswith("test_interval_stop"))
    count_before = len(FakeTimer.instances)

    bm._stopping.set()
    with patch("app.services.backup_scheduler.threading.Timer", FakeTimer), \
         patch("asyncio.new_event_loop"), patch("asyncio.set_event_loop"):
        interval.callback()

    assert len(FakeTimer.instances) == count_before
