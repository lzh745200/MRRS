"""R61 覆盖率收口：五类实体导出/回导、导入器边界与备份异常路径。"""

from __future__ import annotations

import io
import os
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

BASE = "/api/v1/import"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_bytes(headers, rows=()):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _user(db):
    from app.models.user import User

    return db.query(User).first()


def _org_id(db):
    return getattr(_user(db), "organization_id", None) or 1


def _seed_village(db, name="甲村", county="都匀市", township="平浪镇"):
    from app.models.supported_village import SupportedVillage

    village = SupportedVillage(
        village_name=name,
        department="测试单位",
        support_unit="测试单位",
        region_scope="西部地区",
        county=county,
        township=township,
        organization_id=_org_id(db),
        is_active=True,
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _seed_project(db, name="项目甲"):
    from app.models.project import Project

    project = Project(
        name=name,
        code="PJ001",
        type="infrastructure",
        status="in_progress",
        budget=Decimal("1000.50"),
        start_date=datetime(2024, 1, 1),
        end_date=date(2024, 12, 31),
        organization_id=_org_id(db),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _seed(db, entity_type):
    if entity_type == "project":
        return _seed_project(db)
    if entity_type == "fund":
        from app.models.fund import Fund

        project = _seed_project(db, "关联项目")
        fund = Fund(
            name="资金甲",
            code="F001",
            amount=Decimal("100.50"),
            fund_type="other",
            status="pending",
            date=datetime(2024, 2, 3),
            project_id=project.id,
            organization_id=_org_id(db),
        )
        db.add(fund)
        db.commit()
        db.refresh(fund)
        return fund
    if entity_type == "school":
        from app.models.school import School

        school = School(
            name="学校甲",
            type="primary",
            support_status="active",
            student_count=10,
            teacher_count=2,
            organization_id=_org_id(db),
        )
        db.add(school)
        db.commit()
        db.refresh(school)
        return school
    if entity_type == "household":
        from app.models.household import Household

        village = _seed_village(db, "导出村")
        household = Household(
            supported_village_id=village.id,
            household_code="H001",
            household_name="张三",
            household_type="general",
            risk_type="none",
            risk_level="low",
            has_serious_illness=False,
            housing_safe=True,
            last_visit_date=date(2024, 3, 1),
            annual_income=Decimal("12000.00"),
            organization_id=_org_id(db),
        )
        db.add(household)
        db.commit()
        db.refresh(household)
        return household
    raise AssertionError(entity_type)


def _name_of(record):
    return getattr(record, "name", None) or getattr(record, "household_name", None)


MODELS = {
    "project": "app.models.project:Project",
    "fund": "app.models.fund:Fund",
    "school": "app.models.school:School",
    "household": "app.models.household:Household",
}


def _model(entity_type):
    module_name, class_name = MODELS[entity_type].split(":")
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def _export(client, entity_type, ids=None):
    params = {"entity_type": entity_type}
    if ids:
        params["ids"] = ",".join(str(item) for item in ids)
    return client.get(f"{BASE}/export-fill", params=params)


def _sheet(resp):
    assert resp.status_code == 200, resp.text
    return load_workbook(io.BytesIO(resp.content)).active


def _find_header(sheet):
    for row in sheet.iter_rows(min_row=1, max_row=15):
        values = [str(cell.value).strip() if cell.value is not None else "" for cell in row]
        if "ID" in values:
            return row[0].row, values
    raise AssertionError("导出文件缺少 ID 列")


def _row_for(sheet, header_row, headers, field, value):
    column = headers.index(field) + 1
    for row in range(header_row + 1, sheet.max_row + 1):
        if str(sheet.cell(row=row, column=column).value or "").strip() == value:
            return row
    raise AssertionError(f"未找到 {field}={value} 的数据行")


def _post_import(client, entity_type, sheet):
    buffer = io.BytesIO()
    sheet.parent.save(buffer)
    return client.post(
        f"{BASE}/entities",
        files={"file": ("fill.xlsx", buffer.getvalue(), XLSX)},
        params={"entity_type": entity_type, "mode": "incremental"},
    )


ENTITIES = [
    ("project", "项目名称", "项目甲改"),
    ("fund", "资金名称", "资金甲改"),
    ("school", "学校名称", "学校甲改"),
    ("household", "户主姓名", "张三改"),
]


@pytest.mark.parametrize("entity_type,label,new_name", ENTITIES)
def test_export_fill_contains_id_for_every_entity(
    auth_client_with_db, entity_type, label, new_name
):
    client, db = auth_client_with_db
    record = _seed(db, entity_type)

    sheet = _sheet(_export(client, entity_type, [record.id]))
    header_row, headers = _find_header(sheet)
    assert label in headers
    row = _row_for(sheet, header_row, headers, label, _name_of(record))
    assert str(sheet.cell(row=row, column=headers.index("ID") + 1).value) == str(record.id)


@pytest.mark.parametrize("entity_type,label,new_name", ENTITIES)
def test_reimport_updates_entity_by_id(auth_client_with_db, entity_type, label, new_name):
    client, db = auth_client_with_db
    record = _seed(db, entity_type)
    model = _model(entity_type)

    sheet = _sheet(_export(client, entity_type, [record.id]))
    header_row, headers = _find_header(sheet)
    row = _row_for(sheet, header_row, headers, label, _name_of(record))
    sheet.cell(row=row, column=headers.index(label) + 1, value=new_name)

    resp = _post_import(client, entity_type, sheet)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success_rows"] == 1, body

    db.expire_all()
    updated = db.get(model, record.id)
    assert _name_of(updated) == new_name
    assert db.query(model).filter(model.id == record.id).count() == 1


@pytest.mark.parametrize("entity_type,label,new_name", ENTITIES)
def test_reimport_unknown_id_is_rejected(auth_client_with_db, entity_type, label, new_name):
    client, db = auth_client_with_db
    record = _seed(db, entity_type)
    model = _model(entity_type)

    sheet = _sheet(_export(client, entity_type, [record.id]))
    header_row, headers = _find_header(sheet)
    row = _row_for(sheet, header_row, headers, label, _name_of(record))
    sheet.cell(row=row, column=headers.index("ID") + 1, value="999999")

    resp = _post_import(client, entity_type, sheet)
    assert resp.status_code == 200, resp.text
    assert resp.json()["failed_rows"] == 1
    db.expire_all()
    assert db.query(model).filter(model.id == record.id).count() == 1


def test_export_fill_rejects_non_numeric_ids(auth_client_with_db):
    client, _db = auth_client_with_db
    resp = client.get(f"{BASE}/export-fill", params={"entity_type": "school", "ids": "1,abc"})
    assert resp.status_code == 400
    assert "ids" in resp.json()["detail"]


def test_export_fill_maps_service_value_error_to_400(auth_client_with_db, monkeypatch):
    client, _db = auth_client_with_db
    from app.api.v1.import_export import import_data as module

    class _FailingFill:
        def __init__(self, *args, **kwargs):
            pass

        def export(self, *args, **kwargs):
            raise ValueError("模板表头识别失败，无法导出填报数据")

    monkeypatch.setattr(module, "FillTemplateService", _FailingFill)
    resp = client.get(f"{BASE}/export-fill", params={"entity_type": "school"})
    assert resp.status_code == 400
    assert "模板表头识别失败" in resp.json()["detail"]


def test_to_import_error_response_maps_fields():
    from app.api.v1.import_export.import_data import _to_import_error_response
    from app.services.excel_importer_service import ImportError as RowImportError

    response = _to_import_error_response(
        RowImportError(row_number=2, field_name="name", error_code="IMPORT_001", message="坏行", value="x")
    )
    assert response.row_number == 2
    assert response.field_name == "name"
    assert response.error_code == "IMPORT_001"
    assert response.message == "坏行"
    assert response.value == "x"


def test_export_fill_supported_village_branch(auth_client_with_db):
    client, db = auth_client_with_db
    village = _seed_village(db, "丙村")
    sheet = _sheet(_export(client, "supported_village", [village.id]))
    header_row, headers = _find_header(sheet)
    row = _row_for(sheet, header_row, headers, "定点帮扶村", "丙村")
    assert str(sheet.cell(row=row, column=headers.index("ID") + 1).value) == str(village.id)


def test_value_of_household_uses_relationship_when_present():
    from types import SimpleNamespace

    from app.models.household import Household
    from app.services.fill_template_service import FillTemplateService

    record = Household(household_name="x", supported_village_id=1)
    record.supported_village = SimpleNamespace(village_name="甲村", county="都匀市", township="平浪镇")
    service = FillTemplateService(None)
    assert service._value_of(record, "village_name", "str") == "甲村"
    assert service._value_of(record, "county", "str") == "都匀市"


def test_fill_service_rejects_unsupported_entity(auth_client_with_db):
    _client, db = auth_client_with_db
    from app.services.fill_template_service import FillTemplateService

    with pytest.raises(ValueError, match="不支持的填报导出类型"):
        FillTemplateService(db).export("policy")


def test_fill_service_without_user_exports_records(auth_client_with_db):
    _client, db = auth_client_with_db
    from app.services.fill_template_service import FillTemplateService

    _seed(db, "school")
    content = FillTemplateService(db, current_user=None).export("school")
    sheet = load_workbook(io.BytesIO(content)).active
    header_row, headers = _find_header(sheet)
    assert any(
        str(sheet.cell(row=row, column=headers.index("学校名称") + 1).value or "").strip()
        == "学校甲"
        for row in range(header_row + 1, sheet.max_row + 1)
    )


def test_fill_service_custom_template_with_existing_id_column(auth_client_with_db, monkeypatch):
    _client, db = auth_client_with_db
    from app.services.excel_template_service import ExcelTemplateService
    from app.services.fill_template_service import FillTemplateService

    project = _seed(db, "project")
    template = _xlsx_bytes(["项目名称", "项目编号", "项目类型", "ID"], [["x", "x", "x", 0]])
    monkeypatch.setattr(
        ExcelTemplateService,
        "generate_project_template",
        lambda self, include_example=True: template,
    )

    content = FillTemplateService(db, current_user=None).export("project", [project.id])
    sheet = load_workbook(io.BytesIO(content)).active
    header_row, headers = _find_header(sheet)
    assert header_row == 1
    row = _row_for(sheet, header_row, headers, "项目名称", "项目甲")
    assert str(sheet.cell(row=row, column=headers.index("ID") + 1).value) == str(project.id)


def test_fill_service_raises_when_template_header_unrecognized(auth_client_with_db, monkeypatch):
    _client, db = auth_client_with_db
    from app.services.excel_template_service import ExcelTemplateService
    from app.services.fill_template_service import FillTemplateService

    template = _xlsx_bytes(["A", "B", "C", "D"])
    monkeypatch.setattr(
        ExcelTemplateService,
        "generate_project_template",
        lambda self, include_example=True: template,
    )
    with pytest.raises(ValueError, match="模板表头识别失败"):
        FillTemplateService(db).export("project")


def test_parse_excel_skips_row_without_mapped_values(auth_client_with_db, monkeypatch):
    _client, db = auth_client_with_db
    from app.services.excel_importer_service import ExcelImporterService

    service = ExcelImporterService(db)
    monkeypatch.setattr(service, "_read_raw_rows", lambda content: [[], ["only"]])
    rows, _headers = service.parse_excel(b"x", entity_type="project")
    assert rows == []


def test_scoped_get_works_without_current_user(auth_client_with_db):
    _client, db = auth_client_with_db
    from app.models.project import Project
    from app.services.excel_importer_service import ExcelImporterService

    project = _seed(db, "project")
    service = ExcelImporterService(db, current_user=None)
    found = service._scoped_get(Project, project.id)
    assert found is not None and found.id == project.id


def test_import_unexpected_error_returns_result(auth_client_with_db, monkeypatch):
    _client, db = auth_client_with_db
    from app.services import excel_importer_service as module

    service = module.ExcelImporterService(db)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "parse_excel", _boom)
    monkeypatch.setattr(module, "safe_commit", _boom)

    result = service.import_data(b"x", "a.xlsx", 1, user_id=1, entity_type="project")
    assert result.success is False
    assert result.errors and result.errors[0].error_code == "IMPORT_999"
    assert result.import_history_id is None


def test_encrypt_file_cleans_part_on_replace_failure(tmp_path, monkeypatch):
    from app.services.backup_service import BackupService

    target = tmp_path / "data.db"
    target.write_bytes(b"plain")

    def _replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr("app.services.backup_service.os.replace", _replace)
    with pytest.raises(OSError):
        BackupService._encrypt_file(str(target), "password")
    assert not os.path.exists(str(target) + ".enc.part")


def test_encrypt_file_swallows_remove_error_when_cleanup_fails(tmp_path, monkeypatch):
    from app.services.backup_service import BackupService

    target = tmp_path / "data.db"
    target.write_bytes(b"plain")

    def _replace(src, dst):
        raise OSError("replace failed")

    def _remove(path):
        raise OSError("remove failed")

    monkeypatch.setattr("app.services.backup_service.os.replace", _replace)
    monkeypatch.setattr("app.services.backup_service.os.remove", _remove)
    with pytest.raises(OSError):
        BackupService._encrypt_file(str(target), "password")


def test_preview_duplicate_column_unknown_entity_400():
    from fastapi import HTTPException

    from app.api.v1.import_export.import_data import _preview_duplicate_column

    with pytest.raises(HTTPException) as exc_info:
        _preview_duplicate_column("unknown_entity", "name")
    assert exc_info.value.status_code == 400


def test_preview_duplicate_column_household():
    from app.api.v1.import_export.import_data import _preview_duplicate_column
    from app.models.household import Household

    column = _preview_duplicate_column("household", "household_name")
    assert column is Household.household_name


def test_verify_backup_removes_bad_zip_even_if_remove_fails(tmp_path, monkeypatch):
    from app.services.backup_service import BackupIncompleteError, BackupService

    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")

    real_remove = os.remove

    def _remove(path):
        if str(path) == str(bad):
            raise OSError("locked")
        return real_remove(path)

    monkeypatch.setattr("app.services.backup_service.os.remove", _remove)
    service = BackupService.__new__(BackupService)
    with pytest.raises(BackupIncompleteError):
        service._verify_backup_recovery(str(bad))
