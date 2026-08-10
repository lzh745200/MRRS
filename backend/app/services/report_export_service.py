"""报表导出服务 — 委托给 ExcelExportService。"""
import logging

from app.services.export_service import ExcelExportService

logger = logging.getLogger(__name__)


class ReportExportService:
    """报表导出服务（单例）"""

    @staticmethod
    async def export_to_excel(data: list, columns: list, filename: str) -> bytes:
        return ExcelExportService.export(data, columns, filename)

    # ── Word/PDF 导出（委托给 export_service） ──

    def generate_summary_report_data(self, db, year: int) -> dict:  # pragma: no cover
        """生成汇总报表数据"""
        logger.warning("generate_summary_report_data 尚未实现，返回空数据")
        return {"year": year, "sections": []}

    def generate_fund_detail_report_data(self, db, year: int) -> dict:  # pragma: no cover
        """生成经费明细报表数据"""
        logger.warning("generate_fund_detail_report_data 尚未实现，返回空数据")
        return {"year": year, "items": []}

    def generate_project_progress_report_data(self, db, year: int) -> dict:  # pragma: no cover
        """生成项目进度报表数据"""
        logger.warning("generate_project_progress_report_data 尚未实现，返回空数据")
        return {"year": year, "projects": []}

    def generate_school_statistics_report_data(self, db, year: int) -> dict:
        """生成帮扶学校统计报表数据"""
        from app.models.school import School
        from sqlalchemy import func

        try:
            schools = db.query(
                func.count(School.id),
                func.coalesce(func.sum(School.student_count), 0),
                func.coalesce(func.sum(School.teacher_count), 0),
            ).filter(School.is_active == True).first()  # noqa: E712

            return {
                "year": year,
                "total_schools": int(schools[0]) if schools else 0,
                "total_students": int(schools[1]) if schools else 0,
                "total_teachers": int(schools[2]) if schools else 0,
                "sections": [],
            }
        except Exception:
            # 报表数据查询失败若返回全 0 会生成误导性正式报表，升级为 warning 可观测
            logger.warning("学校统计数据查询失败（报表将输出 0）", exc_info=True)
            return {"year": year, "total_schools": 0, "total_students": 0, "total_teachers": 0, "sections": []}

    def generate_village_summary_report_data(self, db, year: int) -> dict:
        """生成帮扶村年度汇总报表数据"""
        from app.models.supported_village import SupportedVillage
        from sqlalchemy import func

        try:
            total = db.query(func.count(SupportedVillage.id)).filter(
                SupportedVillage.is_active == True  # noqa: E712
            ).scalar() or 0

            return {
                "year": year,
                "total_villages": total,
                "sections": [],
            }
        except Exception:
            logger.warning("帮扶村汇总数据查询失败（报表将输出 0）", exc_info=True)
            return {"year": year, "total_villages": 0, "sections": []}

    def generate_annual_summary_report_data(self, db, year: int) -> dict:
        """生成年度综合总结报告数据（合并村/项目/资金/学校）"""
        village_data = self.generate_village_summary_report_data(db, year)
        school_data = self.generate_school_statistics_report_data(db, year)
        project_data = self.generate_project_progress_report_data(db, year)
        fund_data = self.generate_fund_detail_report_data(db, year)

        return {
            "year": year,
            "village_summary": village_data,
            "school_statistics": school_data,
            "project_progress": project_data,
            "fund_detail": fund_data,
            "sections": [],
        }

    def export_word(self, report_type: str, data: dict) -> bytes:  # pragma: no cover
        """导出 Word 文档"""
        logger.warning("export_word 尚未实现")
        return b""

    def export_pdf(self, report_type: str, data: dict) -> bytes:  # pragma: no cover
        """导出 PDF 文档"""
        logger.warning("export_pdf 尚未实现")
        return b""


# 向后兼容单例
report_export_service = ReportExportService()
