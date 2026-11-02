"""临时端到端探针：用真实官方模板走 preview + import（验证后删除）。"""
import io

from app.services.excel_template_service import ExcelTemplateService
from app.services.office_reader import load_workbook_any

BASE = "/api/v1/import"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _filled_village_template(overwrite_example: bool, fill: bool = True) -> bytes:
    content = ExcelTemplateService().generate_village_template()
    wb = load_workbook_any(content)
    ws = wb.active
    values = [
        "1", "黔南州民政局", "黔南州民政局", "都匀市平浪镇甲村", "西部地区",
        "否", "否", "否", "否", "是", "是", "否", "否", "是", "否", "否", "否", "是", "",
    ]
    if fill:
        row = 7 if overwrite_example else 8
        for col, value in enumerate(values, 1):
            ws.cell(row=row, column=col, value=value)
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def _post_file(client, url, data):
    return client.post(
        url,
        files={"file": ("village.xlsx", data, XLSX)},
        params={"entity_type": "supported_village", "mode": "incremental"},
    )


def test_preview_official_template(auth_client_with_db):
    client, _db = auth_client_with_db
    resp = _post_file(client, f"{BASE}/preview", _filled_village_template(False))
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_rows"] == 1


def test_import_official_template(auth_client_with_db):
    client, _db = auth_client_with_db
    resp = _post_file(client, f"{BASE}/entities", _filled_village_template(False))
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success_rows") == 1


def test_import_when_example_row_overwritten(auth_client_with_db):
    client, _db = auth_client_with_db
    resp = _post_file(client, f"{BASE}/entities", _filled_village_template(True))
    assert resp.status_code == 200, resp.text
    assert resp.json().get("success_rows") == 1, resp.text


def test_import_without_data_rows_is_rejected(auth_client_with_db):
    client, _db = auth_client_with_db
    resp = _post_file(client, f"{BASE}/entities", _filled_village_template(False, fill=False))
    assert resp.status_code == 400, resp.text
    assert "示例行" in resp.json()["detail"]
