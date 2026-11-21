"""消息日期筛选的时区回归（本地日历 → naive UTC）。"""

from datetime import datetime, timezone

from app.api.v1.messages import _parse_query_date


def _local_to_utc_naive(year: int, month: int, day: int, hour=0, minute=0, second=0, microsecond=0):
    local = datetime(year, month, day, hour, minute, second, microsecond)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def test_parse_start_date_uses_local_calendar():
    parsed = _parse_query_date("2026-11-22")
    assert parsed == _local_to_utc_naive(2026, 11, 22)


def test_parse_end_date_includes_whole_local_day():
    parsed = _parse_query_date("2026-11-22", end_of_day=True)
    assert parsed == _local_to_utc_naive(2026, 11, 22, 23, 59, 59, 999999)


def test_parse_datetime_with_time_is_local():
    parsed = _parse_query_date("2026-11-22 08:30:00")
    assert parsed == _local_to_utc_naive(2026, 11, 22, 8, 30, 0)


def test_parse_invalid_returns_none():
    assert _parse_query_date("not-a-date") is None
    assert _parse_query_date("") is None
