# -*- coding: utf-8 -*-
"""报表订阅 send_time 格式校验（2026-10-29 审计）。"""
import pytest
from pydantic import ValidationError


def _create(**kw):
    from app.schemas.supported_village import ReportSubscriptionCreate

    base = {"name": "月度报表", "report_type": "village_summary"}
    base.update(kw)
    return ReportSubscriptionCreate(**base)


@pytest.mark.parametrize("value", ["08:30", "8:30", "00:00", "23:59"])
def test_valid_times_accepted(value):
    assert _create(send_time=value).send_time == value


@pytest.mark.parametrize("value", ["abc", "25:00", "12:60", "8-30", "", "08:30:00"])
def test_invalid_times_rejected(value):
    # 2026-10-29 审计：原 max_length=10 不校验格式，这些都能入库，调度端只能运行时崩
    with pytest.raises(ValidationError):
        _create(send_time=value)


def test_none_allowed():
    assert _create(send_time=None).send_time is None


def test_update_schema_also_validates():
    from app.schemas.supported_village import ReportSubscriptionUpdate

    assert ReportSubscriptionUpdate(send_time="7:05").send_time == "7:05"
    with pytest.raises(ValidationError):
        ReportSubscriptionUpdate(send_time="7:5")