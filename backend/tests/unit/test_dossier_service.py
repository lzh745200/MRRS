"""w17-007 一村/一校一档 PDF 服务测试。

覆盖：
- 展示值/状态/数值/地区/组织名等格式化分支；
- 帮扶村档案数据组装（基本信息 / 年度板块 / 项目 / 经费含合计 / 附件）；
- 帮扶学校档案数据组装（基本信息 / 年度资助汇总 / 项目经费 / 附件）；
- 空段降级：无年度数据 / 无项目 / 无经费 / 无附件时 PDF 仍正常成册；
- PDF 渲染（含合计行高亮分支）与审计留痕（村/校两类）。
"""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

from app.models.fund import Fund
from app.models.organization import Organization
from app.models.project import Project
from app.models.school import (
    ProjectPhase,
    ScholarshipStatus,
    ScholarshipStudent,
    School,
    SchoolAttachment,
    SchoolProject,
    SchoolSupport,
    SchoolType,
    SupportStatus,
)
from app.models.supported_village import (
    SupportedVillage,
    VillageAttachment,
    VillageIncome,
    VillagePopulation,
)
from app.services.dossier_service import (
    DossierService,
    _display,
    _num,
    _status_text,
    record_dossier_audit,
)

PDF_MAGIC = b"%PDF-"


def _render_bytes(document) -> bytes:
    """直接调用私有渲染入口（避免必须落库才能断言排版）。"""
    return DossierService()._render(document)


def _seed_org(db, name="某部"):
    org = Organization(name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _seed_full_village(db):
    org = _seed_org(db)
    village = SupportedVillage(
        village_name="甲村",
        department="某部",
        support_unit="某单位",
        province="贵州省",
        city="贵阳市",
        county="云岩区",
        organization_id=org.id,
        created_by=1,
        is_revitalization_tier=True,
        honors="先进集体",
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    db.add(VillagePopulation(
        supported_village_id=village.id, year=2024,
        total_households=10, total_population=100, labor_force=50, poverty_population=5,
    ))
    db.add(VillageIncome(
        supported_village_id=village.id, year=2024,
        per_capita_income=1.25, collective_income=3.5,
    ))
    db.add(Project(name="修路项目", status="completed", budget=100, progress=100,
                   village_id=village.id, organization_id=org.id))
    db.add(Fund(name="产业经费", fund_type="产业扶持", amount=12.5, status="approved",
                village_id=village.id, organization_id=org.id))
    db.add(VillageAttachment(supported_village_id=village.id, file_name="村口照片.jpg",
                             file_path="/tmp/村口照片.jpg", file_size=1024,
                             description="村口"))
    db.commit()
    return db.query(SupportedVillage).filter(SupportedVillage.id == village.id).one(), org


def _seed_empty_village(db):
    village = SupportedVillage(village_name="空村", province=None, city=None, county=None)
    db.add(village)
    db.commit()
    db.refresh(village)
    return db.query(SupportedVillage).filter(SupportedVillage.id == village.id).one()


def _seed_full_school(db):
    org = _seed_org(db, name="教育局")
    school = School(
        name="希望小学",
        code="SCH-001",
        type=SchoolType.PRIMARY,
        province="贵州省",
        city="贵阳市",
        district="云岩区",
        student_count=120,
        teacher_count=10,
        class_count=6,
        support_status=SupportStatus.ACTIVE,
        support_unit="某单位",
        organization_id=org.id,
        created_by=1,
    )
    db.add(school)
    db.commit()
    db.refresh(school)
    db.add(SchoolProject(school_id=school.id, name="教学楼改造", category="基建",
                         phase=ProjectPhase.COMPLETED, budget=200, actual_cost=180))
    db.add(SchoolSupport(school_id=school.id, support_type="助学", amount=5000,
                         description="发放助学金", support_date=dt.datetime(2024, 1, 1)))
    db.add(ScholarshipStudent(school_id=school.id, student_name="张三", year=2024,
                              amount=500, status=ScholarshipStatus.APPROVED))
    db.add(ScholarshipStudent(school_id=school.id, student_name="李四", year=None, amount=300))
    db.add(SchoolAttachment(school_id=school.id, file_name="校园照片.jpg", file_path="/tmp/x.jpg",
                            file_size=2048, description="校园", uploaded_by="李四"))
    db.commit()
    return db.query(School).filter(School.id == school.id).one(), org


def _seed_empty_school(db):
    school = School(name="空校", province=None, city=None, district=None)
    db.add(school)
    db.commit()
    db.refresh(school)
    return db.query(School).filter(School.id == school.id).one()


class TestDisplayHelpers:
    def test_display(self):
        assert _display(None) == "-"
        assert _display("") == "-"
        assert _display(True) == "是"
        assert _display(False) == "否"
        assert _display(dt.datetime(2024, 5, 6, 7, 8)) == "2024-05-06"
        assert _display(3.5) == "3.5"

    def test_status_text(self):
        mapping = {"completed": "已完成"}
        assert _status_text(None, mapping) == "-"
        assert _status_text(SimpleNamespace(value="completed"), mapping) == "已完成"
        assert _status_text("completed", mapping) == "已完成"
        assert _status_text("unknown", mapping) == "unknown"

    def test_num(self):
        assert _num(None) == 0.0
        assert _num("3.5") == 3.5
        assert _num("不是数字") == 0.0

    def test_generated_by(self):
        assert DossierService()._generated_by() == "系统"
        assert DossierService(current_user=SimpleNamespace())._generated_by() == "系统"
        assert DossierService(
            current_user=SimpleNamespace(full_name="张三", username="u")
        )._generated_by() == "张三"
        assert DossierService(
            current_user=SimpleNamespace(full_name=None, username="u")
        )._generated_by() == "u"

    def test_footnote(self):
        text = DossierService(current_user=SimpleNamespace(full_name="张三", role="user"))._footnote()
        assert "口径说明" in text
        assert "生成人：张三" in text
        text_no_user = DossierService()._footnote()
        assert "生成人：系统" in text_no_user

    def test_region(self):
        full = SimpleNamespace(province="贵州省", city="贵阳市", county="云岩区")
        assert DossierService._region(full) == "贵州省 / 贵阳市 / 云岩区"
        assert DossierService._region(SimpleNamespace(province=None, city=None, county=None)) is None
        # 学校用 district 字段
        school = SimpleNamespace(province="贵州省", district="南明区")
        assert DossierService._region(school) == "贵州省 / 南明区"


class TestVillageDocument:
    def test_full_document(self, real_db_session):
        db = real_db_session
        village, org = _seed_full_village(db)
        svc = DossierService(db, SimpleNamespace(full_name="张三", role="super_admin", is_superuser=True))
        doc = svc.build_village_document(village)

        assert doc["entity_type"] == "supported_village"
        assert doc["title"] == "甲村 · 帮扶档案册"
        assert "帮扶管理信息系统 · 甲村" == doc["header"]
        assert "年度：2024" in doc["subtitle"]
        assert f"所属组织：{org.name}" in doc["subtitle"]
        basic = dict(doc["basic"])
        assert basic["帮扶村名称"] == "甲村"
        assert basic["所属组织"] == org.name
        assert basic["地区"] == "贵州省 / 贵阳市 / 云岩区"
        assert basic["是否振兴梯队"] == "是"
        assert basic["获得表彰"] == "先进集体"
        assert basic["创建时间"] != "-"

        section_titles = [section["title"] for section in doc["sections"]]
        assert "人口数据" in section_titles
        assert "收入数据" in section_titles
        population = next(s for s in doc["sections"] if s["title"] == "人口数据")
        assert population["headers"][0] == "年度"
        assert population["rows"][0][0] == "2024"
        assert population["rows"][0][1] == "10"

        assert doc["projects"]["rows"][0][0] == "修路项目"
        assert doc["projects"]["rows"][0][1] == "已完成"
        assert doc["funds"]["rows"][-1][0] == "合计"
        assert doc["funds"]["rows"][-1][2] == "12.50"
        assert doc["attachments"]["rows"][0][0] == "村口照片.jpg"
        assert "口径说明" in doc["footnote"]

    def test_empty_village_degrades(self, real_db_session):
        db = real_db_session
        village = _seed_empty_village(db)
        doc = DossierService(db).build_village_document(village)
        assert doc["sections"] == []
        assert doc["projects"]["rows"] == []
        assert doc["funds"]["rows"] == []
        assert doc["attachments"]["rows"] == []
        # 无年度数据时年度取当前年
        assert f"年度：{dt.datetime.now().year}" in doc["subtitle"]
        assert dict(doc["basic"])["所属组织"] == "-"
        pdf = DossierService(db).render_village_pdf(village)
        assert pdf.startswith(PDF_MAGIC) and len(pdf) > 1000

    def test_village_org_missing_and_name_fallback(self, real_db_session):
        db = real_db_session
        svc = DossierService(db)
        # 组织 ID 指向不存在的组织 + 无村名 → 走占位/兜底分支
        fake = SimpleNamespace(
            id=99999,
            village_name=None,
            organization_id=88888,
            province=None,
            city=None,
            county=None,
            department=None,
            support_unit=None,
            is_revitalization_tier=None,
            honors=None,
            created_at=None,
        )
        doc = svc.build_village_document(fake)
        assert doc["title"] == "帮扶村 · 帮扶档案册"
        basic = dict(doc["basic"])
        assert basic["所属组织"] == "-"
        assert basic["帮扶村名称"] == "-"
        assert doc["footnote"]

    def test_village_without_org_id(self, real_db_session):
        db = real_db_session
        village = _seed_empty_village(db)
        svc = DossierService(db)
        assert svc._organization_name(village) is None

    def test_render_with_data_tables(self, real_db_session):
        db = real_db_session
        village, _org = _seed_full_village(db)
        doc = DossierService(db).build_village_document(village)
        pdf = _render_bytes(doc)
        assert pdf.startswith(PDF_MAGIC)

    def test_data_table_totals_row_branch(self):
        doc = {
            "title": "t", "header": "h", "subtitle": "s", "footnote": "口径说明：x",
            "basic": [("k", "v")],
            "sections": [{"title": "板块", "headers": ["A", "B"], "rows": [["合计", "1"]]}],
            "projects": {"title": "项目", "headers": ["A"], "rows": [["非合计行"]]},
            "funds": {"title": "经费", "headers": ["A"], "rows": []},
            "attachments": {"title": "附件", "headers": ["A"], "rows": []},
        }
        pdf = _render_bytes(doc)
        assert pdf.startswith(PDF_MAGIC)
        # 非合计行不命中高亮分支
        assert DossierService._make_data_table(doc["projects"]) is not None


class TestSchoolDocument:
    def test_full_document(self, real_db_session):
        db = real_db_session
        school, org = _seed_full_school(db)
        svc = DossierService(db, SimpleNamespace(full_name="李四", role="super_admin", is_superuser=True))
        doc = svc.build_school_document(school)

        assert doc["entity_type"] == "school"
        assert doc["title"] == "希望小学 · 帮扶档案册"
        basic = dict(doc["basic"])
        assert basic["学校名称"] == "希望小学"
        assert basic["学校编码"] == "SCH-001"
        assert basic["所属组织"] == org.name
        assert basic["学校类型"] == "小学"
        assert basic["帮扶状态"] == "帮扶中"
        assert basic["地区"] == "贵州省 / 贵阳市 / 云岩区"

        assert [section["title"] for section in doc["sections"]] == ["年度资助数据"]
        yearly = doc["sections"][0]
        # 2024 年一行 + 未标注年度一行（按年份排序，未标注年度在后）
        assert yearly["rows"][0][0] == "2024"
        assert yearly["rows"][0][1] == "1"
        assert yearly["rows"][0][2] == "500.00"
        assert yearly["rows"][1][0] == "未标注年度"
        assert yearly["rows"][1][1] == "1"

        assert doc["projects"]["rows"][-1][0] == "合计"
        assert doc["projects"]["rows"][-1][3] == "200.00"
        assert doc["projects"]["rows"][-1][4] == "180.00"
        assert doc["funds"]["rows"][-1] == ["合计", "5000.00", "", ""]
        assert doc["attachments"]["rows"][0][0] == "校园照片.jpg"
        assert "口径说明" in doc["footnote"]

    def test_empty_school_degrades(self, real_db_session):
        db = real_db_session
        school = _seed_empty_school(db)
        doc = DossierService(db).build_school_document(school)
        assert doc["sections"] == []
        assert doc["projects"]["rows"] == []
        assert doc["funds"]["rows"] == []
        assert doc["attachments"]["rows"] == []
        pdf = DossierService(db).render_school_pdf(school)
        assert pdf.startswith(PDF_MAGIC) and len(pdf) > 1000

    def test_school_name_fallback(self, real_db_session):
        db = real_db_session
        fake = SimpleNamespace(
            id=99998,
            name=None,
            code=None,
            organization_id=None,
            type=None,
            province=None,
            city=None,
            district=None,
            support_status=None,
            support_unit=None,
            student_count=None,
            teacher_count=None,
            class_count=None,
        )
        doc = DossierService(db).build_school_document(fake)
        assert doc["title"] == "帮扶学校 · 帮扶档案册"
        assert dict(doc["basic"])["学校类型"] == "-"


class TestAudit:
    def test_record_dossier_audit_village(self):
        with patch("app.utils.audit_logger.AuditLogger.log") as log:
            record_dossier_audit(
                SimpleNamespace(id=1, username="admin"), "supported_village", 7, "甲村"
            )
        kwargs = log.call_args.kwargs
        assert kwargs["resource_type"] == "supported_village"
        assert kwargs["resource_id"] == 7
        assert kwargs["details"]["dossier"] == "一村一档"
        assert kwargs["details"]["name"] == "甲村"

    def test_record_dossier_audit_school(self):
        with patch("app.utils.audit_logger.AuditLogger.log") as log:
            record_dossier_audit(SimpleNamespace(id=2, username="u"), "school", 8, "希望小学")
        kwargs = log.call_args.kwargs
        assert kwargs["details"]["dossier"] == "一校一档"
        assert kwargs["resource_type"] == "school"
