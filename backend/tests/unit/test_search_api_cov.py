# -*- coding: utf-8 -*-
"""search.py 覆盖率测试：5 个 _append_* 辅助函数 + global_search 端点"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.search as mod


def _chain_query(rows):
    """构造 filter/limit/all 链式 query mock"""
    q = MagicMock()
    q.filter.return_value = q
    q.limit.return_value = q
    q.all.return_value = rows
    return q


def _db_with(rows):
    db = MagicMock()
    db.query.return_value = _chain_query(rows)
    return db


# ---------- _append_village_results ----------

def test_append_village_results_success():
    row = MagicMock(id=1, village_name="幸福村", province="川", city="蓉", county="高新")
    db = _db_with([row])
    q = _chain_query([row])
    items = []
    with patch.object(mod, "scoped_filter", return_value=q):
        mod._append_village_results(items, "幸福", 3, db, MagicMock())
    assert len(items) == 1
    assert items[0].type == "village"
    assert items[0].link == "/villages/1"


def test_append_village_results_empty_location_subtitle_none():
    row = MagicMock(id=2, village_name="村", province=None, city=None, county=None)
    q = _chain_query([row])
    items = []
    with patch.object(mod, "scoped_filter", return_value=q):
        mod._append_village_results(items, "村", 3, MagicMock(), MagicMock())
    assert items[0].subtitle is None


def test_append_village_results_exception_swallowed():
    items = []
    with patch.object(mod, "scoped_filter", side_effect=RuntimeError("db down")):
        mod._append_village_results(items, "x", 3, MagicMock(), MagicMock())
    assert items == []


# ---------- _append_project_results ----------

def test_append_project_results_success():
    row = MagicMock(id=5, code="P001")
    row.name = "产业路"
    q = _chain_query([row])
    items = []
    with patch.object(mod, "scoped_filter", return_value=q):
        mod._append_project_results(items, "产业", 3, MagicMock(), MagicMock())
    assert items[0].type == "project"
    assert items[0].subtitle == "项目编号：P001"


def test_append_project_results_no_code():
    row = MagicMock(id=6, code=None)
    row.name = "项目"
    q = _chain_query([row])
    items = []
    with patch.object(mod, "scoped_filter", return_value=q):
        mod._append_project_results(items, "项", 3, MagicMock(), MagicMock())
    assert items[0].subtitle is None


def test_append_project_results_exception_swallowed():
    items = []
    with patch.object(mod, "scoped_filter", side_effect=RuntimeError("boom")):
        mod._append_project_results(items, "x", 3, MagicMock(), MagicMock())
    assert items == []


# ---------- _append_policy_results ----------

def test_append_policy_results_success():
    row = MagicMock(id=7, title="乡村振兴促进法", issuing_authority="国务院")
    items = []
    mod._append_policy_results(items, "乡村", 3, _db_with([row]))
    assert items[0].type == "policy"
    assert items[0].subtitle == "国务院"


def test_append_policy_results_exception_swallowed():
    db = MagicMock()
    db.query.side_effect = RuntimeError("boom")
    items = []
    mod._append_policy_results(items, "x", 3, db)
    assert items == []


# ---------- _append_school_results ----------

def test_append_school_results_success():
    row = MagicMock(id=8, province="川", city="蓉", district="高新")
    row.name = "希望小学"
    q = _chain_query([row])
    items = []
    with patch.object(mod, "scoped_filter", return_value=q):
        mod._append_school_results(items, "希望", 3, MagicMock(), MagicMock())
    assert items[0].type == "school"
    assert items[0].subtitle == "川 蓉 高新"


def test_append_school_results_all_none_subtitle_none():
    row = MagicMock(id=9, province=None, city=None, district=None)
    row.name = "校"
    q = _chain_query([row])
    items = []
    with patch.object(mod, "scoped_filter", return_value=q):
        mod._append_school_results(items, "校", 3, MagicMock(), MagicMock())
    assert items[0].subtitle is None


def test_append_school_results_exception_swallowed():
    items = []
    with patch.object(mod, "scoped_filter", side_effect=RuntimeError("boom")):
        mod._append_school_results(items, "x", 3, MagicMock(), MagicMock())
    assert items == []


# ---------- _append_user_results ----------

def test_append_user_results_not_superuser_skipped():
    items = []
    mod._append_user_results(items, "x", 3, MagicMock(), False)
    assert items == []


def test_append_user_results_success_with_full_name():
    row = MagicMock(id=10, full_name="张三", username="zhangsan")
    items = []
    mod._append_user_results(items, "张", 3, _db_with([row]), True)
    assert items[0].type == "user"
    assert items[0].title == "张三"
    assert items[0].subtitle == "zhangsan"


def test_append_user_results_without_full_name():
    row = MagicMock(id=11, full_name=None, username="lisi")
    items = []
    mod._append_user_results(items, "李", 3, _db_with([row]), True)
    assert items[0].title == "lisi"
    assert items[0].subtitle is None


def test_append_user_results_exception_swallowed():
    db = MagicMock()
    db.query.side_effect = RuntimeError("boom")
    items = []
    mod._append_user_results(items, "x", 3, db, True)
    assert items == []


# ---------- global_search 端点 ----------

@pytest.mark.asyncio
async def test_global_search_blank_q_returns_empty():
    resp = await mod.global_search(q="   ", limit=20, db=MagicMock(), current_user=MagicMock())
    assert resp.total == 0
    assert resp.items == []


@pytest.mark.asyncio
async def test_global_search_overlong_q_422():
    with pytest.raises(HTTPException) as exc:
        await mod.global_search(q="x" * 101, limit=20, db=MagicMock(), current_user=MagicMock())
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_global_search_aggregates_five_sources():
    user = MagicMock()
    user.is_superuser = True
    sess = MagicMock()

    def _append(items, *args, **kwargs):
        items.append(mod.SearchItem(id=1, type="village", title="t", link="/villages/1"))

    with patch("app.core.database.SessionLocal", return_value=sess), patch.object(
        mod, "_append_village_results", side_effect=_append
    ), patch.object(mod, "_append_project_results", side_effect=_append), patch.object(
        mod, "_append_policy_results", side_effect=_append
    ), patch.object(
        mod, "_append_school_results", side_effect=_append
    ), patch.object(
        mod, "_append_user_results", side_effect=_append
    ), patch.object(
        mod, "_append_fund_results", side_effect=_append, create=True
    ):
        resp = await mod.global_search(q="关键字", limit=20, db=MagicMock(), current_user=user)
    assert resp.total >= 5
    assert len(resp.items) >= 5
    assert sess.close.call_count >= 5


@pytest.mark.asyncio
async def test_global_search_limit_truncates():
    user = MagicMock()
    user.is_superuser = False
    sess = MagicMock()

    def _append(items, *args, **kwargs):
        for i in range(4):
            items.append(mod.SearchItem(id=i, type="village", title=f"t{i}", link="/villages/1"))

    with patch("app.core.database.SessionLocal", return_value=sess), patch.object(
        mod, "_append_village_results", side_effect=_append
    ), patch.object(mod, "_append_project_results"), patch.object(
        mod, "_append_policy_results"
    ), patch.object(
        mod, "_append_school_results"
    ), patch.object(
        mod, "_append_user_results"
    ):
        resp = await mod.global_search(q="关键字", limit=2, db=MagicMock(), current_user=user)
    assert resp.total == 2
