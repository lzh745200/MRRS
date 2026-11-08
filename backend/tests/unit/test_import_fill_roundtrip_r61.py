"""表格填报导出 → 回导（ID 更新）端到端回归（R61）。"""

from __future__ import annotations

import io

from openpyxl import load_workbook

BASE = "/api/v1/import"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _seed_village(db, name: str = "甲村", department: str = "测试单位"):
    from app.models.supported_village import SupportedVillage
    from app.models.user import User

    user = db.query(User).first()
    village = SupportedVillage(
        village_name=name,
        department=department,
        support_unit=department,
        region_scope="西部地区",
        organization_id=getattr(user, "organization_id", None),
        is_active=True,
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _export(client, entity_type: str = "supported_village", ids: list[int] | None = None):
    params = {"entity_type": entity_type}
    if ids:
        params["ids"] = ",".join(str(i) for i in ids)
    return client.get(f"{BASE}/export-fill", params=params)


def _sheet(resp):
    assert resp.status_code == 200, resp.text
    return load_workbook(io.BytesIO(resp.content)).active


def _find_header(ws):
    for row in ws.iter_rows(min_row=1, max_row=15):
        values = [str(cell.value).strip() if cell.value is not None else "" for cell in row]
        if "ID" in values:
            return row[0].row, values
    raise AssertionError("导出文件缺少 ID 列")


def _row_for(ws, header_row: int, headers: list[str], field: str, value: str):
    col = headers.index(field) + 1
    for row in range(header_row + 1, ws.max_row + 1):
        if str(ws.cell(row=row, column=col).value or "").strip() == value:
            return row
    raise AssertionError(f"未找到 {field}={value} 的数据行")


def test_export_fill_template_contains_data_and_id(auth_client_with_db):
    client, db = auth_client_with_db
    village = _seed_village(db, "甲村")

    ws = _sheet(_export(client, ids=[village.id]))
    header_row, headers = _find_header(ws)
    assert "定点帮扶村" in headers
    row = _row_for(ws, header_row, headers, "定点帮扶村", "甲村")
    assert str(ws.cell(row=row, column=headers.index("ID") + 1).value) == str(village.id)


def test_export_fill_template_batch_length_matches(auth_client_with_db):
    client, db = auth_client_with_db
    _seed_village(db, "甲村")
    _seed_village(db, "乙村")

    ws = _sheet(_export(client))
    header_row, headers = _find_header(ws)
    name_col = headers.index("定点帮扶村") + 1
    names = {
        str(ws.cell(row=row, column=name_col).value or "").strip()
        for row in range(header_row + 1, ws.max_row + 1)
    }
    assert {"甲村", "乙村"} <= names


def test_reimport_updates_existing_record_by_id(auth_client_with_db):
    client, db = auth_client_with_db
    village = _seed_village(db, "甲村")
    from app.models.supported_village import SupportedVillage

    ws = _sheet(_export(client, ids=[village.id]))
    header_row, headers = _find_header(ws)
    row = _row_for(ws, header_row, headers, "定点帮扶村", "甲村")
    ws.cell(row=row, column=headers.index("定点帮扶村") + 1, value="甲村（改）")
    buf = io.BytesIO()
    ws.parent.save(buf)

    resp = client.post(
        f"{BASE}/entities",
        files={"file": ("fill.xlsx", buf.getvalue(), XLSX)},
        params={"entity_type": "supported_village", "mode": "incremental"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success_rows"] == 1
    assert db.query(SupportedVillage).filter(SupportedVillage.village_name == "甲村（改）").count() == 1
    assert db.query(SupportedVillage).filter(SupportedVillage.id == village.id).count() == 1


def test_reimport_unknown_id_is_rejected(auth_client_with_db):
    client, db = auth_client_with_db
    village = _seed_village(db, "甲村")
    from app.models.supported_village import SupportedVillage

    ws = _sheet(_export(client, ids=[village.id]))
    header_row, headers = _find_header(ws)
    row = _row_for(ws, header_row, headers, "定点帮扶村", "甲村")
    ws.cell(row=row, column=headers.index("ID") + 1, value="999999")
    buf = io.BytesIO()
    ws.parent.save(buf)

    resp = client.post(
        f"{BASE}/entities",
        files={"file": ("fill.xlsx", buf.getvalue(), XLSX)},
        params={"entity_type": "supported_village", "mode": "incremental"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["failed_rows"] == 1
    assert db.query(SupportedVillage).count() == 1


def test_export_fill_rejects_unknown_entity(auth_client_with_db):
    client, _db = auth_client_with_db
    resp = _export(client, "policy")
    assert resp.status_code == 400


def test_export_fill_forces_formula_like_text_to_string(auth_client_with_db):
    """R61 审计：以 = + - @ 开头的业务数据必须按文本写入，不能被当公式执行。"""
    client, db = auth_client_with_db
    _seed_village(db, "=1+1")

    ws = _sheet(_export(client))
    header_row, headers = _find_header(ws)
    row = _row_for(ws, header_row, headers, "定点帮扶村", "=1+1")
    cell = ws.cell(row=row, column=headers.index("定点帮扶村") + 1)
    assert cell.value == "=1+1"
    assert cell.data_type == "s"  # s=字符串；f=公式
