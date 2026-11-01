"""短期项 7（2026-11-01）：业务指标计数器的语义与接线回归。

覆盖：
- ``core.business_metrics`` 的增/查/重置语义（含空事件名防御、快照隔离）；
- ``GET /system/metrics`` 的 ``business`` 段落确实来自计数器；
- 导出响应构造（``_export_file_response``）成功后确实计数。
"""

import asyncio

import pytest

from app.api.v1.import_export import export as export_api
from app.api.v1.system import metrics as metrics_api
from app.core import business_metrics


@pytest.fixture(autouse=True)
def _clean_metrics():
    """每个用例前后清空计数，避免用例间互相污染（进程级全局字典）。"""
    business_metrics.reset()
    yield
    business_metrics.reset()


def test_incr_and_snapshot_sorted():
    business_metrics.incr("export.csv")
    business_metrics.incr("export.csv")
    business_metrics.incr("backup.create")

    assert business_metrics.snapshot() == {"backup.create": 1, "export.csv": 2}


def test_incr_ignores_empty_event_name():
    business_metrics.incr("")

    assert business_metrics.snapshot() == {}


def test_snapshot_is_isolated_copy():
    business_metrics.incr("export.xlsx")
    snap = business_metrics.snapshot()
    snap["export.xlsx"] = 999

    assert business_metrics.snapshot() == {"export.xlsx": 1}


def test_reset_clears_counters():
    business_metrics.incr("data_package.import")
    business_metrics.reset()

    assert business_metrics.snapshot() == {}


def test_metrics_endpoint_exposes_business_section():
    business_metrics.incr("permission_package.import")

    payload = asyncio.run(metrics_api.get_system_metrics(current_user=None))

    assert payload["data"]["business"]["permission_package.import"] == 1


def test_export_file_response_counts_successful_export():
    response = asyncio.run(
        export_api._export_file_response(
            data=[{"id": 1, "name": "甲"}],
            format="csv",
            base_name="villages",
            xlsx_exporter=lambda: b"",
        )
    )

    assert response.status_code == 200
    assert business_metrics.snapshot()["export.csv"] == 1
