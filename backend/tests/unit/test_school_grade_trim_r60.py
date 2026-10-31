# -*- coding: utf-8 -*-
"""资助学生导入的年级口径一致性（去重判据 == 落库值）。

背景（2026-10-31 巡检）：导入循环里
  * 去重判据用 _sgrade = str(row[1]).strip()（已去空白）
  * 落库却用 grade=str(row[1])（未去空白）
两者不一致 —— Excel 单元格里年级带前后空白时，「同校同姓名同年级」会被判为不同记录，
且库里落进带空白的值，后续按年级聚合/筛选都对不上。
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


def _db():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    return db


async def _run(rows):
    db = _db()
    added = []
    with (
        patch.object(sch, "_get_school_and_check_permission"),
        patch.object(sch, "submit_entity_change_approval", return_value=None),
        patch.object(sch, "safe_commit"),
        patch.object(sch, "ScholarshipStudent") as stu_cls,
    ):
        stu_cls.side_effect = lambda **kw: added.append(kw) or MagicMock()
        await sch.import_school_scholarship_students(1, _xlsx(rows), _user(), db)
    return added


@pytest.mark.asyncio
async def test_grade_is_trimmed_on_insert():
    """年级带前后空白 → 落库值应已去空白（与去重判据一致）。"""
    added = await _run([["张三", "  一年级  ", 2024, 1000, "资助", "待审批"]])
    assert len(added) == 1, added
    assert added[0]["grade"] == "一年级", repr(added[0]["grade"])


@pytest.mark.asyncio
async def test_blank_grade_becomes_none():
    """年级为纯空白 → 落库为 None（不落空字符串）。"""
    added = await _run([["李四", "   ", 2024, 500, "资助", "待审批"]])
    assert len(added) == 1, added
    assert added[0]["grade"] is None, repr(added[0]["grade"])


@pytest.mark.asyncio
async def test_same_grade_with_and_without_space_is_deduped():
    """'一年级' 与 ' 一年级 ' 视为同一记录（第二行被跳过）。"""
    db = _db()
    with (
        patch.object(sch, "_get_school_and_check_permission"),
        patch.object(sch, "submit_entity_change_approval", return_value=None),
        patch.object(sch, "safe_commit"),
    ):
        resp = await sch.import_school_scholarship_students(
            1,
            _xlsx([
                ["王五", "一年级", 2024, 1000, "资助", "待审批"],
                ["王五", " 一年级 ", 2024, 1200, "资助", "待审批"],
            ]),
            _user(),
            db,
        )
    body = resp["data"]
    assert body["imported"] == 1, body
    assert len(body["errors"]) == 1 and "已存在" in body["errors"][0], body["errors"]
