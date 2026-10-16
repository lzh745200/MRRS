"""
补覆盖测试 - app.services.report_export_service

针对既有测试未覆盖的缺口行（v1.8.1 新实现）：
- generate_school_statistics_report_data()：查询成功 / first() 为 None / 查询异常兜底
- generate_village_summary_report_data()：scalar 成功 / scalar 为 None 的 or 0 / 异常兜底
- generate_annual_summary_report_data()：合并四类报表数据
"""
from unittest.mock import MagicMock

from app.services.report_export_service import ReportExportService


class _FullScopeUser:
    """超管替身（R28 · H6）。

    报表数据构建方法自 R28 起强制 ``current_user`` 位置参数并套数据域过滤。
    本文件断言的是**聚合口径**（与数据域无关），故统一传超管替身
    （``is_superuser=True`` → ``filter_by_data_scope`` 原样返回查询），
    保持既有断言不变。数据域隔离本身由
    ``tests/unit/test_scope_service_r28_report_export.py`` 用真实 SQLite 锁定。
    """

    id = 1
    role = "super_admin"
    is_superuser = True
    organization_id = None


SCOPE_USER = _FullScopeUser()


class TestSchoolStatisticsReportData:
    """generate_school_statistics_report_data()"""

    def test_query_success(self):
        """first() 返回 (学校数, 学生数, 教师数) 元组时按值填充"""
        db = MagicMock(name="db")
        db.query.return_value.filter.return_value.first.return_value = (3, 120, 15)

        result = ReportExportService().generate_school_statistics_report_data(db, year=2025, current_user=SCOPE_USER)

        assert result["year"] == 2025
        assert result["title"] == "帮扶学校统计表"
        assert result["total_schools"] == 3
        assert result["total_students"] == 120
        assert result["total_teachers"] == 15
        paragraphs = result["sections"][0]["paragraphs"]
        assert any("3" in p and "120" in p and "15" in p for p in paragraphs)

    def test_first_returns_none_falls_back_to_zero(self):
        """first() 返回 None 时 schools 为假值，三项计数取 0（兜底分支）"""
        db = MagicMock(name="db")
        db.query.return_value.filter.return_value.first.return_value = None

        result = ReportExportService().generate_school_statistics_report_data(db, year=2025, current_user=SCOPE_USER)

        assert result["total_schools"] == 0
        assert result["total_students"] == 0
        assert result["total_teachers"] == 0
        assert result["sections"][0]["paragraphs"]

    def test_query_exception_returns_fallback(self):
        """查询抛异常时记录日志并返回全 0 兜底结构"""
        db = MagicMock(name="db")
        db.query.side_effect = RuntimeError("db down")

        result = ReportExportService().generate_school_statistics_report_data(db, year=2025, current_user=SCOPE_USER)

        assert result["year"] == 2025
        assert result["total_schools"] == 0
        assert result["total_students"] == 0
        assert result["total_teachers"] == 0
        assert result["sections"][0]["paragraphs"]


class TestVillageSummaryReportData:
    """generate_village_summary_report_data()"""

    def test_scalar_success(self):
        """scalar() 返回村数时填充 total_villages"""
        db = MagicMock(name="db")
        db.query.return_value.filter.return_value.scalar.return_value = 7

        result = ReportExportService().generate_village_summary_report_data(db, year=2024, current_user=SCOPE_USER)

        assert result["year"] == 2024
        assert result["title"] == "帮扶村年度汇总表"
        assert result["total_villages"] == 7
        assert any("7" in p for p in result["sections"][0]["paragraphs"])

    def test_scalar_none_falls_back_to_zero(self):
        """scalar() 返回 None 时走 `or 0` 兜底"""
        db = MagicMock(name="db")
        db.query.return_value.filter.return_value.scalar.return_value = None

        result = ReportExportService().generate_village_summary_report_data(db, year=2024, current_user=SCOPE_USER)

        assert result["total_villages"] == 0
        assert result["sections"][0]["paragraphs"]

    def test_query_exception_returns_fallback(self):
        """查询抛异常时记录日志并返回兜底结构"""
        db = MagicMock(name="db")
        db.query.side_effect = RuntimeError("db down")

        result = ReportExportService().generate_village_summary_report_data(db, year=2024, current_user=SCOPE_USER)

        assert result["total_villages"] == 0
        assert result["sections"][0]["paragraphs"]


class TestAnnualSummaryReportData:
    """generate_annual_summary_report_data() 合并村/学校/项目/资金"""

    def test_merges_all_sub_reports(self):
        db = MagicMock(name="db")
        # village 走 scalar()，school 走 first()；project/fund 走 all()
        db.query.return_value.filter.return_value.scalar.return_value = 2
        db.query.return_value.filter.return_value.first.return_value = (1, 10, 5)
        db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = []

        result = ReportExportService().generate_annual_summary_report_data(db, 2026, SCOPE_USER)

        assert result["year"] == 2026
        assert result["title"] == "年度综合总结报告"
        assert result["village_summary"]["total_villages"] == 2
        assert result["school_statistics"]["total_schools"] == 1
        assert result["school_statistics"]["total_students"] == 10
        assert result["school_statistics"]["total_teachers"] == 5
        assert result["project_progress"]["year"] == 2026
        assert result["fund_detail"]["year"] == 2026
        # 四大板块结构完整
        assert [s["title"] for s in result["sections"]] == [
            "一、帮扶村概况",
            "二、帮扶学校概况",
            "三、帮扶项目进展",
            "四、帮扶资金执行",
        ]
