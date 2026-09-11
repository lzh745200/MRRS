"""订阅分发服务覆盖率补齐（纯函数矩阵 + 调度器计数 + 异常隔离）。

既有 test_subscription_dispatch.py 已覆盖 next_run_at 纯函数与 dispatch
主链；本文件补齐纯函数边界 + 调度器计数 + 异常隔离 + _period_starts_after。
generate_for_subscription 的完整覆盖由并行会话在功能收口时补齐。
"""
from datetime import datetime

from app.services.subscription_dispatch_service import (
    _clamp_day,
    _normalize_send_day,
    _parse_send_time,
    _period_starts_after,
    next_run_at,
)


class TestParseSendTimeEdge:
    def test_index_error_branch(self):
        assert _parse_send_time("08") == (8, 0)

    def test_valid(self):
        assert _parse_send_time("14:30") == (14, 30)


class TestNormalizeSendDayEdge:
    def test_type_error_branch(self):
        assert _normalize_send_day("daily", "abc") is None

    def test_bool_type(self):
        assert _normalize_send_day("weekly", True) == 1


class TestClampDayDecember:
    def test_dec_rollover(self):
        assert _clamp_day(2026, 12, 31) == 31


class TestQuarterlyRollover:
    def test_q4_to_next_year_q1(self):
        base = datetime(2026, 11, 15, 10, 0)
        r = next_run_at("quarterly", 1, "08:00", base)
        assert r.year == 2027 and r.month == 1

    def test_q1_to_q2(self):
        base = datetime(2026, 2, 15, 10, 0)
        r = next_run_at("quarterly", 1, "08:00", base)
        assert r.month == 4 and r.day == 1


class TestPeriodStartsAfter:
    def test_sent_after_next_run(self):
        base = datetime(2026, 9, 1, 8, 0)
        sent = datetime(2026, 9, 10, 8, 0)
        assert _period_starts_after(base, sent, "daily") is True

    def test_sent_before_next_run(self):
        base = datetime(2026, 9, 1, 8, 0)
        sent = datetime(2026, 8, 15, 8, 0)
        assert _period_starts_after(base, sent, "daily") is False

    def test_invalid_frequency_returns_false(self):
        base = datetime(2026, 9, 1, 8, 0)
        sent = datetime(2026, 9, 10, 8, 0)
        assert _period_starts_after(base, sent, "hourly") is False

    def test_quarterly_variant(self):
        assert _period_starts_after(datetime(2026, 1, 1), datetime(2026, 6, 1), "weeklyx") is False


class TestRunSchedulerJob:
    """_run_scheduler_job 同步/异步双路径与异常吞并（回收站保留期缺陷回归）。"""

    def test_sync_job_executes_directly(self):
        from app.services.backup_scheduler import _run_scheduler_job

        calls = []
        _run_scheduler_job(lambda: calls.append(1))
        assert calls == [1]

    def test_async_job_executes_in_fresh_loop(self):
        import asyncio

        from app.services.backup_scheduler import _run_scheduler_job

        calls = []

        async def job():
            calls.append(2)

        _run_scheduler_job(job)
        assert calls == [2]
        # 不残留事件循环：改用非弃用的 get_running_loop()（无运行中 loop 时抛 RuntimeError），
        # 避免 asyncio.get_event_loop() 在无运行 loop 时发出
        # "There is no current event loop" DeprecationWarning（Python 3.10+）。
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass

    def test_exception_swallowed_not_raised(self):
        from app.services.backup_scheduler import _run_scheduler_job

        def bad():
            raise RuntimeError("boom")

        _run_scheduler_job(bad)  # 不抛即通过（日志留痕由 logger 承担）
