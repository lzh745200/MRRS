# -*- coding: utf-8 -*-
"""office_reader / office_formats 覆盖率补测（2026-10-26）。

背景：WPS 兼容改造（v1.18.10）新增 office_reader.py(206 行) / office_formats.py(100 行)，
但全量覆盖率门禁报 99.95% ——
  office_formats 缺 82/111；office_reader 缺 xlrd 单元格类型归一、容器尝试顺序、
  shim 层、load_workbook_any 的 zip 分支等十余处。
本文件只补分支，不改实现；与既有 test_office_formats_wps.py 互补（新建文件避免冲突）。
"""
from __future__ import annotations

import sys
import types
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core import office_formats as fm
from app.services import office_reader as rd


def _fake_xlrd() -> types.ModuleType:
    m = types.ModuleType("xlrd")
    m.XL_CELL_EMPTY = 0
    m.XL_CELL_TEXT = 1
    m.XL_CELL_NUMBER = 2
    m.XL_CELL_DATE = 3
    m.XL_CELL_BOOLEAN = 4
    m.XL_CELL_BLANK = 6
    m.xldate_as_datetime = lambda v, mode: f"dt:{v}:{mode}"
    m.open_workbook = lambda **kw: None
    return m


@pytest.fixture()
def fake_xlrd(monkeypatch):
    mod = _fake_xlrd()
    monkeypatch.setitem(sys.modules, "xlrd", mod)
    return mod


def _cell(ctype: int, value):
    return SimpleNamespace(ctype=ctype, value=value)


# ── office_formats：两个纯函数分支 ──────────────────────────────


class TestFormatsBranches:
    def test_sniff_empty_content_is_unknown(self):
        assert fm.sniff_container(b"") == fm.CONTAINER_UNKNOWN

    def test_wps_message_without_ext(self):
        text = fm.wps_save_as_message(None)
        assert "另存为" in text and ".xlsx" in text

    def test_wps_message_with_ext(self):
        assert ".wps" in fm.wps_save_as_message("a.wps")


# ── office_reader：xlrd 单元格归一 ──────────────────────────────


class TestXlrdCell:
    def test_empty_and_blank_are_none(self, fake_xlrd):
        book = SimpleNamespace(datemode=0)
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_EMPTY, "")) is None
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_BLANK, "")) is None

    def test_text_empty_becomes_none(self, fake_xlrd):
        book = SimpleNamespace(datemode=0)
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_TEXT, "")) is None
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_TEXT, "ab")) == "ab"

    def test_number_integral_and_float(self, fake_xlrd):
        book = SimpleNamespace(datemode=0)
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_NUMBER, 3.0)) == 3
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_NUMBER, 3.5)) == 3.5

    def test_number_type_error_falls_back(self, fake_xlrd):
        book = SimpleNamespace(datemode=0)
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_NUMBER, "x")) == "x"

    def test_date_converted(self, fake_xlrd):
        book = SimpleNamespace(datemode=1)
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_DATE, 42.0)) == "dt:42.0:1"

    def test_boolean_and_fallback(self, fake_xlrd):
        book = SimpleNamespace(datemode=0)
        assert rd._xlrd_cell(book, _cell(fake_xlrd.XL_CELL_BOOLEAN, 1)) is True
        assert rd._xlrd_cell(book, _cell(99, "raw")) == "raw"


# ── office_reader：矩形化 / 尝试顺序 / 空内容 / 失败文案 ─────────


class TestReaderHelpers:
    def test_normalize_empty_rows_returns_same(self):
        assert rd._normalize_rows([]) == []

    def test_normalize_pads_short_rows(self):
        assert rd._normalize_rows([[1], [2, 3]]) == [[1, None], [2, 3]]

    def test_attempt_order_unknown_container(self):
        order = rd._attempt_order("unknown")
        assert [name for name, _ in order] == ["openpyxl", "xlrd"]

    def test_attempt_order_by_container(self):
        assert [n for n, _ in rd._attempt_order(fm.CONTAINER_ZIP)] == ["openpyxl", "xlrd"]
        assert [n for n, _ in rd._attempt_order(fm.CONTAINER_OLE2)] == ["xlrd", "openpyxl"]

    def test_read_rows_empty_content_raises(self):
        with pytest.raises(rd.UnsupportedSpreadsheetFormat) as ei:
            rd.read_rows(b"", "a.xlsx")
        assert "文件为空" in str(ei.value)

    def test_read_rows_import_error_branch_message(self):
        def _boom(_content):
            raise ImportError("no xlrd")

        with patch.object(rd, "_attempt_order", return_value=(("xlrd", _boom),)):
            with pytest.raises(rd.UnsupportedSpreadsheetFormat) as ei:
                rd.read_rows(fm.OLE2_MAGIC + b"junk", "a.xls")
        assert "依赖缺失" in str(ei.value)

    def test_read_rows_unknown_ext_failure_message(self):
        def _boom(_content):
            raise ValueError("bad")

        with patch.object(rd, "_attempt_order", return_value=(("openpyxl", _boom),)):
            with pytest.raises(rd.UnsupportedSpreadsheetFormat) as ei:
                rd.read_rows(b"whatever", "a.bin")
        assert "解析失败原因" in str(ei.value)

    def test_read_rows_wps_ext_uses_save_as_message(self):
        def _boom(_content):
            raise ValueError("bad")

        with patch.object(rd, "_attempt_order", return_value=(("openpyxl", _boom),)):
            with pytest.raises(rd.UnsupportedSpreadsheetFormat) as ei:
                rd.read_rows(b"whatever", "a.wps")
        assert "另存为" in str(ei.value)


# ── office_reader：shim 层 ─────────────────────────────────────


class TestShims:
    def test_cell_shim_holds_value(self):
        assert rd._CellShim(7).value == 7

    def test_sheet_shim_properties(self):
        sheet = rd._SheetShim([[1, 2, 3], [4]])
        assert sheet.max_row == 2
        assert sheet.max_column == 3

    def test_sheet_iter_rows_values_only(self):
        sheet = rd._SheetShim([[1, 2], [3, 4]])
        assert list(sheet.iter_rows(values_only=True)) == [(1, 2), (3, 4)]

    def test_sheet_iter_rows_cell_objects_and_range(self):
        sheet = rd._SheetShim([[1, 2], [3, 4]])
        rows = list(sheet.iter_rows(min_row=2, max_row=2))
        assert len(rows) == 1
        assert [c.value for c in rows[0]] == [3, 4]

    def test_workbook_shim_getitem(self):
        wb = rd._WorkbookShim([[1]], sheet_name="S1")
        assert wb.active.max_row == 1
        assert wb["S1"].max_row == 1
        assert wb[0].max_row == 1
        with pytest.raises(KeyError):
            _ = wb["nope"]

    def test_workbook_shim_close_is_noop(self):
        assert rd._WorkbookShim([[1]]).close() is None


# ── office_reader：load_workbook_any 两条分支 ───────────────────


class TestLoadWorkbookAny:
    def test_real_xlsx_returns_openpyxl_workbook(self):
        from openpyxl import Workbook

        buf = BytesIO()
        wb = Workbook()
        wb.active.append(["a", "b"])
        wb.save(buf)
        content = buf.getvalue()

        loaded = rd.load_workbook_any(content, "t.xlsx")
        rows = [list(r) for r in loaded.active.iter_rows(values_only=True)]
        # openpyxl 的 iter_rows 返回 tuple 或 list 因版本而异，统一转 list 再比
        assert rows == [["a", "b"]]

    def test_broken_zip_falls_back_to_generic_reader(self):
        # zip 魔数但内容损坏 → openpyxl 失败 → 回退 read_rows → 同样失败 → 统一异常
        with pytest.raises(rd.UnsupportedSpreadsheetFormat):
            rd.load_workbook_any(fm.ZIP_MAGIC + b"broken", "t.xlsx")
