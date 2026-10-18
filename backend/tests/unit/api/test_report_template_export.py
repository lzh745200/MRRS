"""报表模板增强（W22 v1.14.0）：任意字段组合导出 / 打印数据。

覆盖契约 §2 `/reports`：
- ``POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf&year``
- ``GET /report-templates/{id}/print-data?year``

口径：模块 → ORM 查询经 ``scoped_filter``（数据域）、软删模型过滤 is_active、
年度仅对具备 year 列的模块生效；村名对项目/乡村工作做派生解析。
"""

import csv
import io
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def _user(**kw):
    base = dict(id=7, username="mgr7", role="admin", organization_id=1, data_scope="all")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def api_client():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base
    from app.models.user import User  # noqa: F401  FK 目标表注册
    from app.models.organization import Organization  # noqa: F401
    from app.models.supported_village import SupportedVillage  # noqa: F401
    from app.models.school import School  # noqa: F401
    from app.models.project import Project  # noqa: F401
    from app.models.fund import Fund  # noqa: F401
    from app.models.rural_work import RuralWork  # noqa: F401
    from app.models.report_template import ReportTemplate  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    state = {"user": _user()}
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, session, state
    finally:
        app.dependency_overrides = original
        session.close()
        engine.dispose()


def _mk_data(db):
    """构造五类业务数据（同一组织）。"""
    from app.models.fund import Fund
    from app.models.organization import Organization
    from app.models.project import Project
    from app.models.rural_work import RuralWork, WorkStatus, WorkType
    from app.models.school import School, SchoolType, SupportStatus
    from app.models.supported_village import SupportedVillage

    org = Organization(id=1, name="测试单位")
    db.add(org)
    db.commit()
    village = SupportedVillage(
        village_name="幸福村", province="某省", county="某县",
        organization_id=1, created_by=7, is_active=True,
    )
    db.add(village)
    db.commit()
    db.refresh(village)

    school = School(
        name="希望小学", district="某区", type=SchoolType.PRIMARY,
        support_status=SupportStatus.ACTIVE, student_count=120,
        organization_id=1, created_by=7, is_active=True,
    )
    fund_2026 = Fund(
        name="2026 年帮扶经费", amount=12.5, year=2026, date=date(2026, 5, 1),
        organization_id=1, created_by=7, is_active=True,
    )
    fund_2025 = Fund(
        name="2025 年帮扶经费", amount=8.0, year=2025,
        organization_id=1, created_by=7, is_active=True,
    )
    project = Project(
        name="操场改造", budget=30.0, progress=60, village_id=village.id,
        organization_id=1, created_by=7, is_active=True,
    )
    project_no_village = Project(
        name="无村项目", budget=10.0, progress=0,
        organization_id=1, created_by=7, is_active=True,
    )
    work = RuralWork(
        name="产业帮扶工作", type=WorkType.industry, status=WorkStatus.in_progress,
        supported_village_id=village.id, progress=50,
        organization_id=1, created_by=7,
    )
    db.add_all([school, fund_2026, fund_2025, project, project_no_village, work])
    db.commit()
    for obj in (school, fund_2026, fund_2025, project, project_no_village, work):
        db.refresh(obj)
    return SimpleNamespace(
        org=org, village=village, school=school, fund_2026=fund_2026,
        fund_2025=fund_2025, project=project, project_no_village=project_no_village,
        work=work,
    )


def _mk_template(db, **kw):
    from app.models.report_template import ReportTemplate

    base = dict(
        name="测试模板",
        type="export",
        module="school",
        fields=json.dumps(
            [{"excel_header": "学校名称", "db_field": "name"}], ensure_ascii=False
        ),
        created_by=7,
    )
    base.update(kw)
    template = ReportTemplate(**base)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def _fields(*pairs):
    return json.dumps(
        [{"excel_header": header, "db_field": field} for header, field in pairs],
        ensure_ascii=False,
    )


class TestTemplateExportFormats:
    def test_export_xlsx(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, module="village",
            fields=_fields(("村名", "village_name"), ("县", "county")),
        )
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=xlsx")
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.content[:2] == b"PK"
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(resp.content), read_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        workbook.close()
        assert rows[0] == ("村名", "县")
        assert rows[1] == ("幸福村", "某县")

    def test_export_csv_with_year_filter(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, module="fund",
            fields=_fields(("名称", "name"), ("金额", "amount"), ("年度", "year")),
        )
        resp = client.post(
            f"/api/v1/report-templates/{template.id}/export?format=csv&year=2026"
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.content.decode("utf-8")
        assert text.startswith("\ufeff")
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        assert rows[0] == ["名称", "金额", "年度"]
        assert len(rows) == 2                      # 年度过滤只留 2026 一条
        assert rows[1][0] == "2026 年帮扶经费"
        assert float(rows[1][1]) == 12.5

        # 不带年度 → 两年数据都在
        all_resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=csv")
        all_rows = list(csv.reader(io.StringIO(all_resp.content.decode("utf-8").lstrip("\ufeff"))))
        assert len(all_rows) == 3

    def test_export_docx(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, name="经费报表", module="fund",
            fields=_fields(("名称", "name"), ("日期", "date")),
        )
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=docx&year=2026")
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.headers["content-type"]
        assert resp.content[:2] == b"PK"           # docx 是 zip 容器
        assert len(resp.content) > 1000

    def test_export_pdf(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, name="项目报表", module="project",
            fields=_fields(("项目名称", "name"), ("帮扶村", "village_name"), ("预算", "budget")),
        )
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"

    def test_export_xlsx_wide_table_landscape(self, api_client):
        """字段数 > 6 → A4 横向打印设置分支。"""
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db,
            module="village",
            fields=_fields(
                ("村名", "village_name"), ("省", "province"), ("县", "county"),
                ("乡镇", "township"), ("邮编", "postal_code"), ("备注", "remarks"),
                ("ID", "id"),
            ),
        )
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=xlsx")
        assert resp.status_code == 200
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(resp.content))
        sheet = workbook.active
        assert sheet.page_setup.orientation == "landscape"
        workbook.close()

    def test_export_no_related_village_ids(self, api_client):
        """字段含村相关列但所有记录都未关联村 → 跳过村名预取（village_ids 空）。"""
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, module="fund",
            fields=_fields(("名称", "name"), ("帮扶村ID", "village_id")),
        )
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=csv")
        assert resp.status_code == 200
        rows = list(
            csv.reader(io.StringIO(resp.content.decode("utf-8").lstrip("\ufeff")))
        )
        assert rows[0] == ["名称", "帮扶村ID"]
        assert len(rows) == 3                      # 两条经费记录
        assert all(row[1] == "" for row in rows[1:])


class TestTemplateExportErrors:
    def test_invalid_format(self, api_client):
        client, db, _state = api_client
        template = _mk_template(db)
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=html")
        assert resp.status_code == 400
        assert "不支持的导出格式" in resp.json()["detail"]

    def test_template_not_found(self, api_client):
        client, _db, _state = api_client
        assert client.post("/api/v1/report-templates/999/export?format=xlsx").status_code == 404
        assert client.get("/api/v1/report-templates/999/print-data").status_code == 404

    def test_no_fields(self, api_client):
        client, db, _state = api_client
        template = _mk_template(db, fields="[]")
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=xlsx")
        assert resp.status_code == 400
        assert "字段映射" in resp.json()["detail"]

    def test_unsupported_module(self, api_client):
        client, db, _state = api_client
        template = _mk_template(
            db, module="comprehensive", fields=_fields(("村名", "village_name"))
        )
        resp = client.post(f"/api/v1/report-templates/{template.id}/export?format=xlsx")
        assert resp.status_code == 400
        assert "暂不支持数据导出" in resp.json()["detail"]


class TestTemplatePrintData:
    def test_print_data_with_derived_village_name(self, api_client):
        client, db, _state = api_client
        created = _mk_data(db)
        template = _mk_template(
            db, module="project",
            fields=_fields(("项目名称", "name"), ("帮扶村", "village_name"), ("进度", "progress")),
        )
        body = client.get(f"/api/v1/report-templates/{template.id}/print-data").json()
        assert body["code"] == 200
        data = body["data"]
        assert data["module"] == "project"
        assert data["module_label"] == "帮扶项目"
        assert data["columns"] == [
            {"key": "name", "label": "项目名称"},
            {"key": "village_name", "label": "帮扶村"},
            {"key": "progress", "label": "进度"},
        ]
        assert data["headers"] == ["项目名称", "帮扶村", "进度"]
        assert data["total"] == 2
        rows = {row[0]: row for row in data["rows"]}
        assert rows["操场改造"][1] == "幸福村"        # 由 Project.village_id 派生
        assert rows["无村项目"][1] == ""              # 无关联村 → 空串
        assert rows["操场改造"][2] == 60
        assert data["template"]["id"] == template.id
        assert created.village.village_name == "幸福村"

    def test_print_data_rural_work_enums_and_year(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, module="rural_work",
            fields=_fields(("工作名称", "name"), ("帮扶村", "village_name"),
                           ("状态", "status"), ("类型", "type")),
        )
        data = client.get(
            f"/api/v1/report-templates/{template.id}/print-data?year=2026"
        ).json()["data"]
        assert data["module_label"] == "乡村工作"
        assert data["total"] == 1
        row = data["rows"][0]
        assert row[0] == "产业帮扶工作"
        assert row[1] == "幸福村"                     # RuralWork.supported_village_id 派生
        assert row[2] == "in_progress"                # 枚举名 → 枚举值
        assert row[3] == "industry"

    def test_print_data_empty_when_year_mismatch(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, module="school", fields=_fields(("学校名称", "name"))
        )
        data = client.get(
            f"/api/v1/report-templates/{template.id}/print-data?year=2020"
        ).json()["data"]
        # school 无 year 列 → 年度参数不生效，仍有数据
        assert data["total"] == 1

    def test_print_data_village_module_enum_bool_values(self, api_client):
        client, db, _state = api_client
        _mk_data(db)
        template = _mk_template(
            db, module="school",
            fields=_fields(("学校名称", "name"), ("学校类型", "type"),
                           ("帮扶状态", "support_status"), ("是否启用", "is_active")),
        )
        data = client.get(f"/api/v1/report-templates/{template.id}/print-data").json()["data"]
        row = data["rows"][0]
        assert row[1] == "primary"                    # 枚举对象 → 值
        assert row[2] == "active"
        assert row[3] == "是"                         # 布尔 → 是/否
