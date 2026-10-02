"""app/utils/time_utils.py 单元测试：时间基准转换的全分支覆盖。

本模块是「naive UTC 存储 / 本地调度语义 / aware UTC 传输」三类转换的唯一入口，
分支必须逐条覆盖（覆盖率门禁 100%）。
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.utils.time_utils import (
    as_utc,
    as_utc_naive,
    local_naive,
    local_naive_to_utc,
    now_local,
    to_local,
    to_utc,
    to_utc_naive,
    utcnow,
    utcnow_naive,
)


class TestUtcNow:
    def test_utcnow_is_aware_utc(self):
        value = utcnow()
        assert value.tzinfo is not None
        assert value.utcoffset() == timedelta(0)

    def test_utcnow_naive_has_no_tzinfo(self):
        value = utcnow_naive()
        assert value.tzinfo is None
        # naive 值与当前 UTC 墙钟一致（允许秒级误差）
        assert abs((value - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()) < 5


class TestAsUtc:
    def test_none_passthrough(self):
        assert as_utc(None) is None

    def test_naive_treated_as_utc(self):
        naive = datetime(2026, 1, 1, 8, 0)
        assert as_utc(naive) == datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)

    def test_already_utc_returned_identically(self):
        aware = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
        assert as_utc(aware) is aware

    def test_non_utc_aware_converted(self):
        local = datetime(2026, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=8)))
        assert as_utc(local) == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


class TestAsUtcNaive:
    def test_none_passthrough(self):
        assert as_utc_naive(None) is None

    def test_non_utc_aware_becomes_naive_utc(self):
        local = datetime(2026, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=8)))
        result = as_utc_naive(local)
        assert result == datetime(2026, 1, 1, 0, 0)
        assert result.tzinfo is None


class TestToLocal:
    def test_none_passthrough(self):
        assert to_local(None) is None

    def test_naive_interpreted_as_utc_then_localized(self):
        naive_utc = datetime(2026, 1, 1, 0, 0)
        result = to_local(naive_utc)
        assert result is not None
        assert result.tzinfo is not None
        # 与把该 naive 值当作 UTC 后 astimezone() 的结果一致
        expected = naive_utc.replace(tzinfo=timezone.utc).astimezone()
        assert result == expected


class TestLocalNaive:
    def test_naive_input(self):
        naive_utc = datetime(2026, 6, 1, 4, 0)
        result = local_naive(naive_utc)
        assert result.tzinfo is None
        assert result == naive_utc.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)

    def test_aware_input(self):
        aware_utc = datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc)
        assert local_naive(aware_utc) == aware_utc.astimezone().replace(tzinfo=None)


class TestLocalNaiveToUtc:
    def test_naive_input_interpreted_as_local(self):
        wall = datetime(2026, 6, 1, 12, 0)
        result = local_naive_to_utc(wall)
        assert result.tzinfo is not None
        assert result == wall.astimezone().astimezone(timezone.utc)

    def test_aware_input_normalized_to_utc(self):
        aware = datetime(2026, 6, 1, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        assert local_naive_to_utc(aware) == datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc)


class TestToUtc:
    def test_none_passthrough(self):
        assert to_utc(None) is None

    def test_naive_interpreted_as_local(self):
        wall = datetime(2026, 6, 1, 12, 0)
        assert to_utc(wall) == wall.astimezone().astimezone(timezone.utc)

    def test_aware_normalized(self):
        aware = datetime(2026, 6, 1, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        assert to_utc(aware) == datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc)


class TestToUtcNaive:
    def test_none_passthrough(self):
        assert to_utc_naive(None) is None

    def test_local_wall_becomes_naive_utc(self):
        wall = datetime(2026, 6, 1, 12, 0)
        result = to_utc_naive(wall)
        assert result is not None and result.tzinfo is None
        assert result == wall.astimezone().astimezone(timezone.utc).replace(tzinfo=None)


class TestNowLocal:
    def test_is_aware_local(self):
        value = now_local()
        assert value.tzinfo is not None
        assert value.utcoffset() == datetime.now().astimezone().utcoffset()


class TestRoundTripContract:
    """核心不变量：库中 naive UTC ↔ 本地墙钟 ↔ aware UTC 三段转换可逆。"""

    @pytest.mark.parametrize(
        "wall",
        [
            datetime(2026, 1, 1, 0, 0),
            datetime(2026, 6, 15, 12, 30),
            datetime(2026, 12, 31, 23, 59, 59),
        ],
    )
    def test_local_wall_round_trip_through_utc(self, wall):
        """本地墙钟 → aware UTC → 本地墙钟 应回到原值（任何时区成立）。"""
        as_utc_instant = local_naive_to_utc(wall)
        back = local_naive(as_utc_instant)
        assert back == wall

    def test_naive_utc_is_not_reinterpreted_as_local(self):
        """as_utc 与 to_utc 对同一 naive 值的解释**必须不同**（这正是历史缺陷根因）。"""
        naive = datetime(2026, 6, 1, 12, 0)
        offset = datetime.now().astimezone().utcoffset() or timedelta(0)
        assert as_utc(naive).replace(tzinfo=None) == naive
        assert to_utc(naive) == naive.astimezone().astimezone(timezone.utc)
        # 仅当本机为 UTC 时两种解释才重合
        if offset != timedelta(0):
            assert to_utc(naive) != as_utc(naive)
