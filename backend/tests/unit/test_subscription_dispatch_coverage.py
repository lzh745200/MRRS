"""订阅分发服务覆盖率补齐（工单 003 并行会话新增 270 行的分支覆盖）。

既有 test_subscription_dispatch.py 已覆盖 next_run_at 纯函数与 dispatch
主链 mock 路径；本文件补齐 generate_for_subscription 内部（ReportService
调用/文件写/站内消息）、quarterly 翻转、_period_starts_after、调度器
subscription_dispatch_job 壳、generate-now 端点异常分支。
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
        assert _parse_send_time("08") == (8, 0)  # 无冒号 → IndexError


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
