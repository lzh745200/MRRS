"""OpenCodeReview 深度审查批次（2026-09-17）新增分支的覆盖率锁定。

本轮修复引入的新分支若无测试触达，会直接击穿 backend/.coveragerc 的
fail_under=100 门禁。这里为每一处补上最小充分用例。
"""
import json
import logging

import pytest

from app.core import build_info
from app.core.async_utils import gather_limited
from app.core.config import _absolutize_sqlite_url
from app.core import query_optimizer as qo
from app.middleware import query_counter as qc
from app.services.data_tier_service import DataTierService


# ── async_utils.gather_limited：并发参数校验（0 原会 Semaphore(0) 永久阻塞）──
async def test_gather_limited_rejects_zero_concurrency():
    async def one():
        return 1

    with pytest.raises(ValueError, match="concurrency 必须 >= 1"):
        await gather_limited(0, one())


async def test_gather_limited_rejects_negative_concurrency():
    async def one():
        return 1

    with pytest.raises(ValueError, match="concurrency 必须 >= 1"):
        await gather_limited(-3, one())


# ── build_info：合法但非对象的 JSON 必须按缺失处理（否则 /health 500）──
@pytest.mark.parametrize("payload", ['["a"]', '"1.2.3"', "123", "null"])
def test_build_info_non_object_json_degrades(tmp_path, monkeypatch, payload):
    f = tmp_path / "_build_info.json"
    f.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(build_info, "_BUILD_INFO_FILE", f)
    monkeypatch.setattr(build_info, "_cached", None)
    assert build_info._load() == {}


def test_build_info_object_json_still_read(tmp_path, monkeypatch):
    f = tmp_path / "_build_info.json"
    f.write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    monkeypatch.setattr(build_info, "_BUILD_INFO_FILE", f)
    monkeypatch.setattr(build_info, "_cached", None)
    assert build_info._load() == {"version": "9.9.9"}


# ── config._absolutize_sqlite_url：只剥离「开头」的 data/ 分量 ──
def test_absolutize_strips_leading_data_component():
    assert _absolutize_sqlite_url("sqlite:///./data/app.db", "/tmp/d") == "sqlite:////tmp/d/app.db"


def test_absolutize_keeps_inner_data_component():
    # 关键回归：str.replace 会把内层的 data/ 一并删掉，得到 "myapp.db"
    assert (
        _absolutize_sqlite_url("sqlite:///./data/mydata/app.db", "/tmp/d")
        == "sqlite:////tmp/d/mydata/app.db"
    )


def test_absolutize_without_data_prefix():
    assert (
        _absolutize_sqlite_url("sqlite:///./custom/x.db", "/tmp/d")
        == "sqlite:////tmp/d/custom/x.db"
    )


# ── query_optimizer：N+1 告警分支（计数来自 query_counter 真实链路）──
def test_analyze_n_plus_one_warns_over_threshold(monkeypatch, caplog):
    monkeypatch.setattr(qo, "get_query_count", lambda: 99)

    @qo.analyze_n_plus_one(threshold=5)
    def handler():
        return "ok"

    with caplog.at_level(logging.WARNING):
        assert handler() == "ok"
    assert any("可能的 N+1 查询" in r.message for r in caplog.records)


def test_analyze_n_plus_one_silent_under_threshold(monkeypatch, caplog):
    monkeypatch.setattr(qo, "get_query_count", lambda: 1)

    @qo.analyze_n_plus_one(threshold=5)
    def handler():
        return "ok"

    with caplog.at_level(logging.WARNING):
        assert handler() == "ok"
    assert not any("可能的 N+1 查询" in r.message for r in caplog.records)


# ── query_counter：上下文内计数清零 ──
def test_reset_current_query_count_clears_active_context():
    counter = [7]
    token = qc._query_counter_ctx.set(counter)
    try:
        assert qc.current_query_count() == 7
        qc.reset_current_query_count()
        assert counter[0] == 0
        assert qc.current_query_count() == 0
    finally:
        qc._query_counter_ctx.reset(token)


def test_reset_without_context_is_noop():
    # 无请求上下文时不得抛异常
    qc.reset_current_query_count()
    assert qc.current_query_count() == 0


# ── data_tier_service：归档文件名必须是纯文件名（防路径穿越）──
@pytest.mark.parametrize(
    "name",
    ["../../etc/passwd", "/etc/passwd", "C:\\Windows\\win.ini", "sub/evil.json.gz", ""],
)
def test_restore_from_archive_rejects_path_traversal(name):
    svc = DataTierService()
    count, message = svc.restore_from_archive(db=None, model_class=object, archive_file=name)
    assert count == 0
    assert "非法" in message


def test_restore_from_archive_accepts_plain_name():
    svc = DataTierService()
    count, message = svc.restore_from_archive(
        db=None, model_class=object, archive_file="village_20260101.json.gz"
    )
    assert count == 0
    assert "非法" not in message
    assert "不存在" in message
