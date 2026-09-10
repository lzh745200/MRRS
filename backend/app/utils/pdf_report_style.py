"""统一 PDF 报表样式模块 — 军绿 + 金色正式档案风（reportlab platypus）。

供公文报告 PDF（report_export_service）与数据报表 PDF（report_service）共用：

- ``ensure_cjk_font``：注册 reportlab 内置 CID 中文字体 ``STSong-Light``
  （免字体文件，解决中文乱码——历史缺陷用 Helvetica 渲染中文）。
- ``make_numbered_canvas``：返回一个「两遍式」Canvas 子类，在每页统一绘制
  页眉（居中抬头 + 分隔线）与页脚（第 X 页 / 共 Y 页）。
- ``data_table_style``：统一表格样式（军绿表头白字 + 交替行底 + 浅边框 +
  数据列右对齐）。

仅依赖 ``reportlab``（项目已具备），不新增第三方依赖。
"""

from __future__ import annotations

from typing import Optional

_CJK_FONT = "STSong-Light"


def ensure_cjk_font() -> str:
    """注册并返回内置 CID 中文字体名（幂等）。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    if _CJK_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(_CJK_FONT))
    return _CJK_FONT


def make_numbered_canvas(header_text: str, margin_mm: float = 20):
    """构造两遍式 Canvas 类：统一绘制页眉页脚与「共 N 页」页码。

    用法：``SimpleDocTemplate(...).build(story, canvasmaker=make_numbered_canvas(header))``
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as _canvas

    class _NumberedCanvas(_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_states = []

        def showPage(self):  # noqa: N802 (reportlab 命名约定)
            # 先累积本页状态，待全部页收集完毕再统一绘制（以便计算总页数）
            self._saved_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_states)
            for idx, state in enumerate(self._saved_states, 1):
                self.__dict__.update(state)
                self._draw_frame(total, idx)
                super().showPage()
            super().save()

        def _draw_frame(self, total: int, page_no: int) -> None:
            width, height = A4
            self.saveState()
            self.setFont(_CJK_FONT, 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            # 页眉
            self.drawCentredString(width / 2, height - 11 * mm, header_text)
            self.line(margin_mm * mm, height - 13 * mm, width - margin_mm * mm, height - 13 * mm)
            # 页脚
            self.line(margin_mm * mm, 13 * mm, width - margin_mm * mm, 13 * mm)
            self.drawCentredString(width / 2, 9 * mm, f"第 {page_no} 页 / 共 {total} 页")
            self.restoreState()

    return _NumberedCanvas


def data_table_style(right_align_from: int = 1):
    """统一数据表样式（第 0 行为军绿表头；数据列自 ``right_align_from`` 起右对齐）。"""
    from reportlab.lib import colors

    return [
        ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4332")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (right_align_from, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E8F0EB")]),
    ]


# 兼容：暴露字体名常量
CJK_FONT = _CJK_FONT


def pdf_cell(value: Optional[object]) -> str:
    """PDF 单元格值转字符串（None → 空串）。"""
    return "" if value is None else str(value)
