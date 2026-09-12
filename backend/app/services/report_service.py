"""
Report generation service.

Provides Excel, PDF, and comprehensive report exports for village data.
Used by data/data/reports.py route handlers.
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating data reports in various formats.

    列表/详情查询由 ``DataReportService`` 承担；本服务只负责文件导出。
    """

    def __init__(self, db: Session):
        self.db = db

    async def export_to_excel(self, query_params: Dict[str, Any] = None, user: Any = None) -> bytes:
        """Generate an Excel report based on query parameters.

        Args:
            query_params: Filters (year, village_ids, report_type, etc.)
            user: 当前用户，用于数据权限过滤。

        Returns:
            Excel file as bytes.
        """
        try:
            import openpyxl

            from app.utils.excel_report_style import build_report_sheet, make_subtitle

            wb = openpyxl.Workbook()
            headers = ["序号", "名称", "省份", "市县", "振兴层级", "年度", "数据值", "更新时间"]

            data_rows = await self._fetch_report_data(query_params, user=user)
            build_report_sheet(
                wb,
                title="帮扶管理信息系统 · 数据报表",
                headers=headers,
                rows=data_rows,
                subtitle=make_subtitle(
                    year=(query_params or {}).get("year"),
                    extra=f"共 {len(data_rows)} 条记录",
                ),
                sheet_name="数据报表",
                ws=wb.active,
            )

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output.getvalue()
        except ImportError:  # pragma: no cover
            logger.warning("openpyxl not available, returning empty Excel")
            return self._empty_excel()
        except Exception as e:
            logger.error("Excel export failed: %s", e)
            raise

    async def export_to_pdf(self, query_params: Dict[str, Any] = None, user: Any = None) -> bytes:
        """Generate a PDF report (platypus + 内置 CID 中文字体).

        修复历史缺陷：旧实现用 ``Helvetica``（canvas）绘制中文 → 导出必乱码。
        现改用报告样式模块的 ``STSong-Light`` CID 字体，并加入 A4 页面、页眉页脚
        与「第 X 页 / 共 Y 页」页码，表格为军绿表头 + 交替行底的网格表。

        Args:
            query_params: Filters (year, village_ids, report_type, etc.)
            user: 当前用户，用于数据权限过滤。

        Returns:
            PDF file as bytes.
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

            from app.utils.pdf_report_style import (
                data_table_style,
                ensure_cjk_font,
                make_numbered_canvas,
                pdf_cell,
            )

            ensure_cjk_font()

            report_title = "帮扶管理信息系统 - 数据报表"
            rpt_type = (query_params or {}).get("report_type", "综合报表")
            headers = ["序号", "名称", "省份", "市县", "振兴层级", "年度", "数据值", "更新时间"]
            data_rows = await self._fetch_report_data(query_params, user=user)

            title_style = ParagraphStyle(
                "t", fontName="STSong-Light", fontSize=18, leading=26, alignment=1, spaceAfter=6
            )
            meta_style = ParagraphStyle(
                "m", fontName="STSong-Light", fontSize=10, leading=14, alignment=1, textColor=colors.grey
            )

            story = [
                Paragraph(report_title, title_style),
                Paragraph(
                    f"报表类型：{rpt_type}    生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    meta_style,
                ),
                Spacer(1, 6 * mm),
            ]

            table_data = [headers] + [
                [pdf_cell(c) for c in list(row)[: len(headers)]] for row in data_rows
            ]
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle(data_table_style()))
            story.append(table)

            buffer = io.BytesIO()
            SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=20 * mm,
                bottomMargin=18 * mm,
                title=report_title,
            ).build(story, canvasmaker=make_numbered_canvas(f"帮扶管理信息系统 - {rpt_type}"))
            buffer.seek(0)
            return buffer.getvalue()
        except ImportError:  # pragma: no cover
            logger.warning("reportlab not available, returning empty PDF")
            return self._empty_pdf()
        except Exception as e:
            logger.error("PDF export failed: %s", e)
            raise

    async def export_comprehensive_report(
        self, year: int = None, village_ids: List[int] = None, user: Any = None
    ) -> bytes:
        """Generate a comprehensive multi-section report.

        Args:
            year: Report year.
            village_ids: List of village IDs to include.
            user: 当前用户，用于数据权限过滤。

        Returns:
            Excel file as bytes (comprehensive reports are Excel).
        """
        return await self.export_to_excel({
            "year": year or datetime.now().year,
            "village_ids": village_ids,
            "report_type": "comprehensive",
        }, user=user)

    async def get_export_filename(self, query_params: Dict[str, Any] = None) -> str:
        """Generate a suitable filename for the export.

        Args:
            query_params: Export parameters used to name the file.

        Returns:
            Filename string.
        """
        report_type = (query_params or {}).get("report_type", "report")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{report_type}_{timestamp}.xlsx"

    async def get_report_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        """List report subscriptions for a user."""
        from app.models.supported_village import ReportSubscription

        rows = (
            self.db.query(ReportSubscription)
            .filter(ReportSubscription.user_id == user_id)
            .order_by(ReportSubscription.id.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "name": r.name or "",
                "report_type": r.report_type or "",
                "format": r.format or "xlsx",
                "frequency": r.frequency or "weekly",
                "send_day": r.send_day,
                "send_time": r.send_time,
                "email": r.email or "",
                "output_dir": r.output_dir or "",
                "output_format": r.output_format or "pdf",
                "is_active": bool(r.is_active),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def create_subscription(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new report subscription."""
        from app.core.transaction import safe_commit
        from app.models.supported_village import ReportSubscription

        sub = ReportSubscription(
            user_id=user_id,
            name=(data.get("name") or "").strip(),
            report_type=(data.get("report_type") or "").strip(),
            format=data.get("format") or "xlsx",
            year=data.get("year"),
            village_ids=(
                str(data["village_ids"])
                if data.get("village_ids")
                else None
            ),
            include_sections=(
                str(data["include_sections"])
                if data.get("include_sections")
                else None
            ),
            frequency=data.get("frequency") or "weekly",
            send_day=data.get("send_day"),
            send_time=data.get("send_time"),
            email=data.get("email"),
            output_dir=data.get("output_dir"),
            output_format=data.get("output_format") or "pdf",
            is_active=True,
        )
        self.db.add(sub)
        safe_commit(self.db)
        return {
            "id": sub.id,
            "user_id": sub.user_id,
            "name": sub.name,
            "report_type": sub.report_type,
            "format": sub.format,
            "frequency": sub.frequency,
            "is_active": True,
        }

    async def update_subscription(
        self, subscription_id: int, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing subscription."""
        from app.core.transaction import safe_commit
        from app.models.supported_village import ReportSubscription

        sub = (
            self.db.query(ReportSubscription)
            .filter(ReportSubscription.id == subscription_id)
            .first()
        )
        if sub is None:
            return None
        for key in (
            "name",
            "report_type",
            "format",
            "year",
            "village_ids",
            "include_sections",
            "frequency",
            "send_day",
            "send_time",
            "email",
            "output_dir",
            "output_format",
        ):
            if key in data and data[key] is not None:
                value = data[key]
                if key in ("village_ids", "include_sections") and isinstance(value, list):
                    value = str(value)
                setattr(sub, key, value)
        if "is_active" in data and data["is_active"] is not None:
            sub.is_active = bool(data["is_active"])
        safe_commit(self.db)
        return {
            "id": sub.id,
            "user_id": sub.user_id,
            "name": sub.name,
            "report_type": sub.report_type,
            "format": sub.format,
            "frequency": sub.frequency,
            "is_active": bool(sub.is_active),
        }

    async def cancel_subscription(self, subscription_id: int) -> bool:
        """Cancel a subscription (soft delete via is_active=False)."""
        from app.core.transaction import safe_commit
        from app.models.supported_village import ReportSubscription

        sub = (
            self.db.query(ReportSubscription)
            .filter(ReportSubscription.id == subscription_id)
            .first()
        )
        if sub is None:
            return False
        sub.is_active = False
        safe_commit(self.db)
        return True

    # ── Internal helpers ──

    async def _fetch_report_data(
        self, query_params: Dict[str, Any] = None, user: Any = None
    ) -> List[List[Any]]:
        """Fetch report data from the database.

        Args:
            query_params: 可选的查询过滤参数。
            user: 当前用户，用于数据权限过滤。

        Override this in production to query real models.
        """
        try:
            from app.services.data_scope_query import scoped_filter  # B1 下沉：服务层统一入口
            from app.models.supported_village import SupportedVillage

            query = self.db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
            # 数据权限过滤（参照 villages.py:50 范式）
            query = scoped_filter(query, SupportedVillage, user)
            rows = query.limit(100).all()
            return [
                [i + 1, r.village_name or "", r.province or "", r.county or "",
                 "是" if r.is_revitalization_tier else "否", "", "", r.updated_at.isoformat() if r.updated_at else ""]
                for i, r in enumerate(rows)
            ]
        except Exception:
            # 数据层故障必须让导出端点失败,而不是静默导出空报表误导用户
            logger.error("Failed to fetch report data from DB", exc_info=True)
            raise

    @staticmethod
    def _empty_excel() -> bytes:
        """Return a minimal empty Excel file."""
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            wb.active.title = "报表"
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return output.getvalue()
        except ImportError:  # pragma: no cover
            return b""

    @staticmethod
    def _empty_pdf() -> bytes:
        """Return a minimal empty PDF file."""
        try:
            from reportlab.pdfgen import canvas
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer)
            c.drawString(100, 750, "暂无数据")
            c.save()
            buffer.seek(0)
            return buffer.getvalue()
        except ImportError:  # pragma: no cover
            return b""
