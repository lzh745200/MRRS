# -*- coding: utf-8 -*-
"""资助学生导入的去重查询次数（N+1 回归）。

背景（2026-10-31 巡检）：导入循环里每行发一次 ScholarshipStudent 去重查询。
实测 1000 行耗时 413ms vs 批量预查 10ms（40 倍）。改为「一次预查 + 内存集合」，
本文件锁定「查询次数与行数无关」这一契约。
"""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import UploadFile
from openpyxl import Workbook

import app.api.v1.school as sch


def _user():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["姓名", "年级", "年份", "金额", "原因", "状态"])
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return UploadFile(file=buf, filename="t.xlsx")


def _db(existing=()):
    """db：预查返回 existing（(student_name, grade) 元组序列）。"""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = list(existing)
    db.query.return_value.filter.return_value.first.return_value = None
    return db


@pytest.mark.asyncio
async def test_one_row_one_school_no_extra_query():
    """单行导入：去重查询只发 1 次（预查），不是「预查 + 每行一次」。"""
    db = _db()
    with (
        patch.object(sch, "_get_school_and_check_permission"),
        patch.object(sch, "submit_entity_change_approval", return_value=None),
        patch.object(sch, "safe_commit"),
    ):
        await sch.import_school_scholarship_students(
            1, _xlsx([["张三", "一年级", 2024, 1000, "资助", "待审批"]]), _user(), db
        )
    assert db.query.call_count == 1, f"应只查 1 次（预查），实际 {db.query.call_count} 次"


@pytest.mark.asyncio
async def test_query_count_independent_of_row_count():
    """5 行导入：查询次数仍为 1（与行数无关）—— N+1 的核心回归。"""
    db = _db()
    rows = [["学生%d" % i, "一年级", 2024, 1000, "资助", "待审批"] for i in range(5)]
    with (
        patch.object(sch, "_get_school_and_check_permission"),
        patch.object(sch, "submit_entity_change_approval", return_value=None),
        patch.object(sch, "safe_commit"),
    ):
        await sch.import_school_scholarship_students(1, _xlsx(rows), _user(), db)
    assert db.query.call_count == 1, f"5 行应只查 1 次，实际 {db.query.call_count} 次"


@pytest.mark.asyncio
async def test_existing_student_is_skipped_without_query():
    """预查已命中的学生 → 跳过且不再查库。"""
    db = _db(existing=[("张三", "一年级")])
    with (
        patch.object(sch, "_get_school_and_check_permission"),
        patch.object(sch, "submit_entity_change_approval", return_value=None),
        patch.object(sch, "safe_commit"),
    ):
        resp = await sch.import_school_scholarship_students(
            1, _xlsx([["张三", "一年级", 2024, 1000, "资助", "待审批"]]), _user(), db
        )
    assert db.query.call_count == 1
    body = resp.get("data") if isinstance(resp, dict) else None
    assert body is not None and body["imported"] == 0, body
    assert any("已存在" in e for e in body["errors"]), body["errors"]


@pytest.mark.asyncio
async def test_duplicate_within_same_file_is_skipped():
    """同一文件内重复行：第二行应被跳过（内存集合纳入本次新增）。"""
    db = _db()
    rows = [
        ["张三", "一年级", 2024, 1000, "资助", "待审批"],
        ["张三", "一年级", 2024, 1200, "资助", "待审批"],
    ]
    with (
        patch.object(sch, "_get_school_and_check_permission"),
        patch.object(sch, "submit_entity_change_approval", return_value=None),
        patch.object(sch, "safe_commit"),
    ):
        resp = await sch.import_school_scholarship_students(1, _xlsx(rows), _user(), db)
    body = resp["data"]
    assert body["imported"] == 1, body
    assert len(body["errors"]) == 1 and "已存在" in body["errors"][0], body["errors"]
    assert db.query.call_count == 1
