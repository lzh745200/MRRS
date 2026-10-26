"""WPS 兼容改造（P0/P1）回归用例。

覆盖三件此前**做不到**的事（改造前为红）：
1. `.xls`（Excel 97-2003 / WPS「97-2003 格式」）能被导入链路读出来；
2. `.et`（WPS 表格）两种容器（OOXML / OLE2）都能读；
3. 通用附件白名单接受 WPS 原生 `.et/.wps/.dps`。

以及三件必须保持的行为：
4. `.xlsx` 解析结果不变（回归护栏）；
5. `.wps/.dps` 给出"请另存为"的可读提示，而不是抛裸异常；
6. openpyxl 风格替身（`load_workbook_any`）的 `iter_rows` / `max_row` 语义。
"""

from pathlib import Path

import pytest

from app.core.office_formats import (
    DOCUMENT_UPLOAD_EXTS,
    SPREADSHEET_EXTS,
    file_ext,
    is_spreadsheet_upload,
    sniff_container,
    spreadsheet_upload_hint,
    wps_save_as_message,
)
from app.services.office_reader import (
    UnsupportedSpreadsheetFormat,
    load_workbook_any,
    read_rows,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "office"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


EXPECTED_ROWS = [["姓名", "年龄", "金额"], ["张三", 30, 1200], ["李四", 25, 800.5]]


# ── 4/6. 原本就该成立的行为（护栏）──


@pytest.mark.parametrize("name", ["sample.xlsx", "sample_ooxml.et", "sample_ole2.et", "sample.xls"])
def test_read_rows_supports_xlsx_and_both_et_containers(name: str):
    rows = read_rows(_fixture(name), name)

    assert [r[0] for r in rows] == ["姓名", "张三", "李四"]
    assert rows[1][1] == 30
    assert rows[2][1] == 25


def test_sniff_container_distinguishes_ooxml_from_ole2():
    assert sniff_container(_fixture("sample.xlsx")) == "zip"
    assert sniff_container(_fixture("sample.xls")) == "ole2"
    assert sniff_container(b"not-a-real-office-file") == "unknown"


def test_wps_native_extensions_are_known_but_storage_only():
    assert SPREADSHEET_EXTS == frozenset({"xlsx", "xls", "et"})
    assert is_spreadsheet_upload("报表.ET") is True
    assert is_spreadsheet_upload("报表.wps") is False
    for ext in ("et", "wps", "dps"):
        assert ext in DOCUMENT_UPLOAD_EXTS


def test_file_ext_handles_paths_and_missing_extension():
    assert file_ext("C:\\tmp\\a.XLSX") == "xlsx"
    assert file_ext("b.et") == "et"
    assert file_ext("noext") == ""
    assert file_ext(None) == ""


def test_wps_storage_only_files_get_save_as_hint():
    # 真实 .wps 是 Word 的 OLE2 容器（含 WordDocument 流），不是表格；
    # 这里用"OLE2 魔数 + 无法解析的载荷"精确命中"解析失败 → 给 WPS 另存为提示"分支。
    unparseable_ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
    with pytest.raises(UnsupportedSpreadsheetFormat) as excinfo:
        read_rows(unparseable_ole2, "sample.wps")

    assert "另存为" in str(excinfo.value)
    assert "另存为" in wps_save_as_message("a.wps")


def test_spreadsheet_upload_hint_mentions_wps():
    hint = spreadsheet_upload_hint()

    assert ".et" in hint
    assert "WPS" in hint


def test_load_workbook_any_mimics_openpyxl_api_for_ole2():
    wb = load_workbook_any(_fixture("sample.xls"), "sample.xls")
    try:
        sheet = wb.active
        assert sheet.max_row == 3
        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        assert rows[0][0] == "张三"
        assert sheet.max_row >= len(rows)
        assert wb.sheetnames
    finally:
        wb.close()


# ── 1/2. 改造后才成立：导入链路必须能读 .xls / .et（改造前为红）──


def test_excel_importer_service_reads_xls():
    from app.services.excel_importer_service import ExcelImporterService

    rows = ExcelImporterService._read_raw_rows(_fixture("sample.xls"))

    assert rows[0][:3] == ["姓名", "年龄", "金额"]
    assert rows[1][:3] == ["张三", 30, 1200]


def test_batch_optimizer_read_excel_raw_reads_ole2_et():
    from app.services.batch_import_optimizer import read_excel_raw

    rows = read_excel_raw(_fixture("sample_ole2.et"))

    assert len(rows) == 3
    assert rows[2][0] == "李四"


def test_import_data_parse_rows_reads_xls():
    from app.api.v1.import_export.import_data import _parse_excel_rows

    def parser(headers):
        mapping = {"姓名": "name", "年龄": "age", "金额": "amount"}
        return {i: mapping[h] for i, h in enumerate(headers) if h in mapping}

    rows = _parse_excel_rows(_fixture("sample.xls"), parser, [])

    assert rows[0]["name"] == "张三"
    assert rows[0]["age"] == 30
    assert rows[1]["amount"] == 800.5


def test_attachment_whitelist_accepts_wps_native_formats():
    from app.api.v1.files import _ALLOWED_EXTS

    document_exts = set(_ALLOWED_EXTS["document"])
    assert {"et", "wps", "dps"} <= document_exts
