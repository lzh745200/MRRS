"""CSV/Excel 公式注入净化回归（立即项 2026-11-01）。

覆盖三层：
1. 共享工具语义 ``app.utils.export_safety``；
2. 统一报表写入器 ``app.utils.excel_report_style._coerce``；
3. 真实导出出口（通用导出 CSV / 一户一档 CSV+XLSX / 消费帮扶 CSV+XLSX / 报表模板 CSV+XLSX）。
"""

import io
from datetime import date

import pytest

from app.utils.export_safety import sanitize_cell, sanitize_mapping, sanitize_row


class TestSanitizeCell:
    @pytest.mark.parametrize("raw", ["=SUM(A1)", "+86301", "-1+1", "@cmd", "\t=1", "\r=1"])
    def test_dangerous_prefix_is_escaped(self, raw):
        assert sanitize_cell(raw) == "'" + raw

    @pytest.mark.parametrize("raw", ["正常文本", "a=b", "1+1", "", "  =x", "－全角负号"])
    def test_safe_text_is_untouched(self, raw):
        assert sanitize_cell(raw) == raw

    @pytest.mark.parametrize("raw", [0, -5, 3.14, None, True, False, date(2026, 11, 1)])
    def test_non_string_is_untouched(self, raw):
        assert sanitize_cell(raw) is raw

    def test_row_and_mapping(self):
        assert sanitize_row(["=a", 1, None]) == ["'=a", 1, None]
        assert sanitize_mapping({"k": "=a", "n": 2}) == {"k": "'=a", "n": 2}


class TestExportPaths:
    def test_generic_export_csv(self):
        from app.api.v1.import_export.export import _to_csv

        data = [{"村名": "=HYPERLINK(\"http://evil\",\"x\")", "人口": 120}]
        content = _to_csv(data).decode("utf-8-sig")
        assert "'=HYPERLINK" in content
        assert "120" in content

    def test_household_csv_and_xlsx(self):
        from app.services.household_service import build_csv_bytes, build_xlsx_bytes

        headers = ["姓名", "备注"]
        rows = [["张三", "=1+1"], ["李四", "正常"]]

        csv_text = build_csv_bytes(headers, rows).decode("utf-8-sig")
        assert "'=1+1" in csv_text
        assert "正常" in csv_text

        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(build_xlsx_bytes(headers, rows)))
        ws = wb.active
        assert ws.cell(row=2, column=2).value == "'=1+1"
        assert ws.cell(row=3, column=2).value == "正常"

    def test_consumption_csv_and_xlsx(self):
        from app.api.v1.consumption import _build_export_bytes

        headers = ["产品", "金额"]
        rows = [["@evil", 100]]

        csv_text = _build_export_bytes("csv", headers, rows).decode("utf-8")
        assert "'@evil" in csv_text

        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(_build_export_bytes("xlsx", headers, rows)))
        assert wb.active.cell(row=2, column=1).value == "'@evil"
        assert wb.active.cell(row=2, column=2).value == 100

    def test_report_template_csv_and_xlsx(self):
        from types import SimpleNamespace

        from app.api.v1.report_templates import _template_export_csv, _template_export_xlsx

        template = SimpleNamespace(name="测试报表")
        headers = ["备注"]
        rows = [["-2+3"]]

        csv_text = _template_export_csv(headers, rows).decode("utf-8")
        assert "'-2+3" in csv_text

        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(_template_export_xlsx(template, headers, rows)))
        assert wb.active.cell(row=2, column=1).value == "'-2+3"

    def test_report_sheet_writer_sanitizes(self):
        from openpyxl import Workbook, load_workbook

        from app.utils.excel_report_style import build_report_sheet

        wb = Workbook()
        wb.remove(wb.active)
        build_report_sheet(
            wb,
            title="测试",
            headers=["列"],
            rows=[["=cmd|' /C calc'!A0"]],
        )
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        sheet = load_workbook(buffer).active
        values = [cell.value for row in sheet.iter_rows() for cell in row]
        assert any(isinstance(v, str) and v.startswith("'=cmd") for v in values)
