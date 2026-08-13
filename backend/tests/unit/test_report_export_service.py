"""report_export_service 真实实现测试（数据构建 + Word/PDF 渲染）。

历史 route 级测试（test_export.py TestExportReportWord/Pdf）mock 整个 service，
只验证路由接线；本文件针对真实 service 实现，断言导出文件非空且格式合法，
防止"返回 b'' 空文件"类回归（v1.8.1 根因修复）。
"""

import zipfile
from datetime import date, datetime
from io import BytesIO

import pytest

from app.models.fund import Fund
from app.models.project import Project
from app.services.report_export_service import ReportExportService

DOCX_MAGIC = b"PK\x03\x04"
PDF_MAGIC = b"%PDF-"


@pytest.fixture
def svc():
    return ReportExportService()


def _seed_funds(db):
    """2024 年两类三笔 + 2023 年一笔（应被年度过滤）+ 已删除一笔（应被过滤）。"""
    db.add(Fund(name="产业经费1", fund_type="产业扶持", date=date(2024, 3, 1),
                amount=100000, approved_amount=90000, allocated_amount=80000, used_amount=50000))
    db.add(Fund(name="产业经费2", fund_type="产业扶持", date=date(2024, 6, 1),
                amount=50000, approved_amount=50000, allocated_amount=40000, used_amount=30000))
    db.add(Fund(name="教育经费", fund_type="教育帮扶", date=date(2024, 9, 1),
                amount=20000, approved_amount=20000, allocated_amount=20000, used_amount=10000))
    db.add(Fund(name="旧年经费", fund_type="产业扶持", date=date(2023, 1, 1), amount=999999))
    db.add(Fund(name="已删经费", fund_type="产业扶持", date=date(2024, 4, 1), amount=888888, is_active=False))
    db.commit()


def _seed_projects(db):
    db.add(Project(name="修路项目", status="completed", progress=100,
                   budget=300000, actual_cost=280000, start_date=date(2024, 1, 10)))
    db.add(Project(name="引水项目", status="in_progress", progress=60,
                   budget=200000, actual_cost=50000, start_date=date(2024, 5, 10)))
    db.add(Project(name="旧年项目", status="completed", progress=100,
                   budget=1, actual_cost=1, start_date=date(2022, 1, 1)))
    db.commit()


# ────────────────────── 数据构建器 ──────────────────────


class TestFundDetailData:
    def test_aggregation(self, svc, real_db_session):
        _seed_funds(real_db_session)
        data = svc.generate_fund_detail_report_data(real_db_session, 2024)

        assert data["year"] == 2024
        assert data["title"] == "帮扶资金拨付明细表"
        table = data["sections"][0]["table"]
        body = {row[0]: row for row in table["rows"]}

        # 产业扶持：2 笔（旧年与已删记录被过滤）
        assert body["产业扶持"][1] == "2"
        assert body["产业扶持"][2] == "150,000.00"
        assert body["产业扶持"][4] == "120,000.00"
        # 教育帮扶：1 笔
        assert body["教育帮扶"][1] == "1"
        # 合计行
        assert body["合计"][1] == "3"
        assert body["合计"][3] == "160,000.00"  # 90000+50000+20000

    def test_empty_db(self, svc, real_db_session):
        data = svc.generate_fund_detail_report_data(real_db_session, 2024)
        section = data["sections"][0]
        assert section["table"]["rows"] == []
        assert any("暂无" in p for p in section["paragraphs"])

    def test_year_defaults_to_current(self, svc, real_db_session):
        data = svc.generate_fund_detail_report_data(real_db_session, None)
        assert data["year"] == datetime.now().year


class TestProjectProgressData:
    def test_aggregation(self, svc, real_db_session):
        _seed_projects(real_db_session)
        data = svc.generate_project_progress_report_data(real_db_session, 2024)

        table = data["sections"][0]["table"]
        body = {row[0]: row for row in table["rows"]}

        assert body["已完成"][1] == "1"
        assert body["已完成"][2] == "100.0%"
        assert body["进行中"][1] == "1"
        assert body["进行中"][2] == "60.0%"
        # 合计：2022 年项目被过滤
        assert body["合计"][1] == "2"
        assert body["合计"][3] == "500,000.00"

    def test_empty_db(self, svc, real_db_session):
        data = svc.generate_project_progress_report_data(real_db_session, 2024)
        section = data["sections"][0]
        assert section["table"]["rows"] == []
        assert any("暂无" in p for p in section["paragraphs"])


class TestMergedReports:
    def test_summary_sections(self, svc, real_db_session):
        _seed_funds(real_db_session)
        _seed_projects(real_db_session)
        data = svc.generate_summary_report_data(real_db_session, 2024)

        titles = [s["title"] for s in data["sections"]]
        assert titles == ["一、帮扶村概况", "二、帮扶学校概况", "三、帮扶项目进展", "四、帮扶资金执行"]
        # 项目/经费块挂了真实表格
        assert data["sections"][2]["table"]["rows"]
        assert data["sections"][3]["table"]["rows"]

    def test_annual_summary(self, svc, real_db_session):
        data = svc.generate_annual_summary_report_data(real_db_session, 2024)
        assert len(data["sections"]) == 4
        assert "village_summary" in data and "fund_detail" in data

    def test_school_and_village_empty(self, svc, real_db_session):
        school = svc.generate_school_statistics_report_data(real_db_session, 2024)
        village = svc.generate_village_summary_report_data(real_db_session, 2024)
        assert school["total_schools"] == 0 and school["sections"][0]["paragraphs"]
        assert village["total_villages"] == 0 and village["sections"][0]["paragraphs"]


# ────────────────────── Word / PDF 渲染 ──────────────────────

ALL_TYPES = ["summary", "fund_detail", "project_progress", "school_statistics", "village_summary", "annual_summary"]

_BUILDERS = {
    "summary": "generate_summary_report_data",
    "fund_detail": "generate_fund_detail_report_data",
    "project_progress": "generate_project_progress_report_data",
    "school_statistics": "generate_school_statistics_report_data",
    "village_summary": "generate_village_summary_report_data",
    "annual_summary": "generate_annual_summary_report_data",
}


class TestExportWord:
    @pytest.mark.parametrize("report_type", ALL_TYPES)
    def test_real_docx_bytes(self, svc, real_db_session, report_type):
        """每种报告类型都必须产出真实 docx（禁止空 bytes 回归）。"""
        _seed_funds(real_db_session)
        _seed_projects(real_db_session)
        data = getattr(svc, _BUILDERS[report_type])(real_db_session, 2024)
        content = svc.export_word(report_type, data)

        assert isinstance(content, bytes) and len(content) > 1000
        assert content[:4] == DOCX_MAGIC

    def test_docx_contains_table_data(self, svc, real_db_session):
        _seed_funds(real_db_session)
        data = svc.generate_fund_detail_report_data(real_db_session, 2024)
        content = svc.export_word("fund_detail", data)

        with zipfile.ZipFile(BytesIO(content)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert "产业扶持" in xml
        assert "150,000.00" in xml

    def test_empty_sections_still_valid(self, svc):
        content = svc.export_word("summary", {"year": 2024, "sections": []})
        assert content[:4] == DOCX_MAGIC and len(content) > 1000
        with zipfile.ZipFile(BytesIO(content)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert "暂无" in xml


class TestExportPdf:
    @pytest.mark.parametrize("report_type", ALL_TYPES)
    def test_real_pdf_bytes(self, svc, real_db_session, report_type):
        _seed_funds(real_db_session)
        _seed_projects(real_db_session)
        data = getattr(svc, _BUILDERS[report_type])(real_db_session, 2024)
        content = svc.export_pdf(report_type, data)

        assert isinstance(content, bytes) and len(content) > 500
        assert content[:5] == PDF_MAGIC

    def test_empty_sections_still_valid(self, svc):
        content = svc.export_pdf("summary", {"year": 2024, "sections": []})
        assert content[:5] == PDF_MAGIC and len(content) > 500


class TestSingleton:
    def test_module_singleton_is_instance(self):
        from app.services.report_export_service import report_export_service

        assert isinstance(report_export_service, ReportExportService)
