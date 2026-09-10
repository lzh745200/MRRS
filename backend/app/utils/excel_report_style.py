"""统一 Excel 报表样式模块 — 军绿 + 金色正式档案风。

供所有报表导出服务复用（列表导出 / 综合报表 / 数据报表 / 帮扶村多模块 /
报表模板下载），统一提供：

- 抬头区：主标题（深绿底金字）+ 副标题（单位/年度/生成时间）+ 金色装饰线；
- 表头行：军绿底、金色上下框、白色粗体居中；
- 数据区：细边框、按列对齐、可选斑马纹；
- 打印设置：A4、自适应宽度、页边距、页眉页脚（含「第 X 页 共 Y 页」页码域）、
  重复打印表头行、冻结窗格。

设计约束
--------
- 仅依赖 ``openpyxl``（项目已具备），**不新增第三方依赖**。
- 所有函数对入参宽容：列数为 0 / 空表不抛错；非法列宽回落默认值。
- 单元格值统一经 ``_coerce`` 转换，规避 openpyxl 对 Decimal/enum 等类型的
  ``SerialisationError``（与 supported_village_export_service 的既有做法一致）。
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional, Sequence

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.properties import PageSetupProperties

# ═══════════════════════════════════════════════════════════════
# 配色常量（与数据导入模板 excel_template_service 保持一致）
# ═══════════════════════════════════════════════════════════════
MILITARY_DARK_GREEN = "1B4332"
MILITARY_GOLD = "D4AF37"
MILITARY_LIGHT_BG = "F0F4F0"
MILITARY_ZEBRA = "E8F0EB"
MILITARY_BORDER = "CBD5E1"
MILITARY_DARK_TEXT = "1E293B"
MILITARY_GRAY_TEXT = "64748B"
MILITARY_WHITE = "FFFFFF"

# 系统抬头（可选写入第 1 行）
SYSTEM_NAME = "★ 帮扶管理信息系统 ★"

# 纸张：9 = A4（openpyxl page_setup.paperSize 采用 Excel 编码）
_PAPER_A4 = 9

# ═══════════════════════════════════════════════════════════════
# 复用样式对象（模块级单例，避免重复创建）
# ═══════════════════════════════════════════════════════════════
_title_fill = PatternFill(start_color=MILITARY_DARK_GREEN, end_color=MILITARY_DARK_GREEN, fill_type="solid")
_title_font = Font(name="SimHei", bold=True, color=MILITARY_GOLD, size=16)
_subtitle_font = Font(name="SimHei", bold=False, color=MILITARY_WHITE, size=10)
_decor_fill = PatternFill(start_color=MILITARY_GOLD, end_color=MILITARY_GOLD, fill_type="solid")

_header_fill = PatternFill(start_color=MILITARY_DARK_GREEN, end_color=MILITARY_DARK_GREEN, fill_type="solid")
_header_font = Font(name="SimHei", bold=True, color=MILITARY_WHITE, size=11)
_data_font = Font(name="SimSun", color=MILITARY_DARK_TEXT, size=10)
_footer_font = Font(name="SimSun", color=MILITARY_GRAY_TEXT, size=9)

_thin_side = Side(style="thin", color=MILITARY_BORDER)
_thin_border = Border(left=_thin_side, right=_thin_side, top=_thin_side, bottom=_thin_side)
_header_border = Border(
    left=_thin_side,
    right=_thin_side,
    top=Side(style="medium", color=MILITARY_GOLD),
    bottom=Side(style="medium", color=MILITARY_GOLD),
)

_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
_right = Alignment(horizontal="right", vertical="center", wrap_text=True)

_zebra_fill = PatternFill(start_color=MILITARY_ZEBRA, end_color=MILITARY_ZEBRA, fill_type="solid")

_ALIGN_MAP = {"left": _left, "center": _center, "right": _right}


def _coerce(value: Any) -> Any:
    """将任意值转换为 openpyxl 可安全写入的类型。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            return float(value)
    except Exception:  # pragma: no cover - 标准库 import 永不失败
        pass
    try:
        import enum

        if isinstance(value, enum.Enum):
            return value.value
    except Exception:  # pragma: no cover
        pass
    return str(value)


def make_subtitle(unit: Optional[str] = None, year: Optional[Any] = None, extra: Optional[str] = None) -> str:
    """构造副标题（单位 / 年度 / 生成时间），空项自动省略。"""
    parts = []
    if unit:
        parts.append(f"单位：{unit}")
    if year:
        parts.append(f"年度：{year}")
    if extra:
        parts.append(extra)
    parts.append(f"生成时间：{_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "    ".join(parts)


# ═══════════════════════════════════════════════════════════════
# 抬头区
# ═══════════════════════════════════════════════════════════════
def apply_title_block(
    ws,
    title: str,
    subtitle: Optional[str] = None,
    col_count: int = 6,
    system_name: Optional[str] = None,
) -> int:
    """写入统一抬头区，返回数据/表头起始行号。

    布局：
      第1行 系统名（可选，深绿底金字）
      第2行 报表主标题（深绿底金字）
      第3行 副标题（深绿底白字）
      第4行 金色装饰线
      第5行 空白间隔
    未指定 ``system_name`` 时仅渲染 主标题/副标题/装饰线/间隔（共 4 行），
    数据起始行 = 5；指定 system_name 时数据起始行 = 6。
    """
    col_count = max(int(col_count or 0), 1)
    max_col = get_column_letter(col_count)
    row = 1

    if system_name:
        ws.merge_cells(f"A{row}:{max_col}{row}")
        c = ws.cell(row=row, column=1, value=system_name)
        c.font = _title_font
        c.fill = _title_fill
        c.alignment = _center
        ws.row_dimensions[row].height = 30
        row += 1

    # 主标题
    ws.merge_cells(f"A{row}:{max_col}{row}")
    c = ws.cell(row=row, column=1, value=title)
    c.font = _title_font
    c.fill = _title_fill
    c.alignment = _center
    ws.row_dimensions[row].height = 32
    row += 1

    # 副标题（含生成时间）
    sub_text = subtitle if subtitle is not None else make_subtitle()
    ws.merge_cells(f"A{row}:{max_col}{row}")
    c = ws.cell(row=row, column=1, value=sub_text)
    c.font = _subtitle_font
    c.fill = _title_fill
    c.alignment = _center
    ws.row_dimensions[row].height = 22
    row += 1

    # 金色装饰线
    for col in range(1, col_count + 1):
        ws.cell(row=row, column=col).fill = _decor_fill
    ws.row_dimensions[row].height = 3
    row += 1

    # 空白间隔
    ws.row_dimensions[row].height = 6
    row += 1

    return row


# ═══════════════════════════════════════════════════════════════
# 表头 / 数据区
# ═══════════════════════════════════════════════════════════════
def style_header_row(
    ws,
    row_idx: int,
    headers: Sequence[Any],
    col_widths: Optional[Sequence[float]] = None,
) -> None:
    """写入并样式化表头行（军绿底、金色上下框、白字粗体居中）。"""
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=row_idx, column=col_idx)
        cell.value = _coerce(header)
        cell.font = _header_font
        cell.fill = _header_fill
        cell.alignment = _center
        cell.border = _header_border
        letter = get_column_letter(col_idx)
        if col_widths and col_idx <= len(col_widths) and col_widths[col_idx - 1]:
            width = float(col_widths[col_idx - 1])
        else:
            label_len = len(str(header))
            width = max(label_len * 2.2, 12)
        ws.column_dimensions[letter].width = min(width, 45)
    ws.row_dimensions[row_idx].height = 28


def style_data_region(
    ws,
    first_row: int,
    last_row: int,
    col_count: int,
    align_map: Optional[Dict[int, str]] = None,
    zebra: bool = False,
    font: Optional[Font] = None,
) -> None:
    """为数据区套用细边框 + 列对齐 + 可选斑马纹。

    Args:
        align_map: {1-based 列号: "left"/"center"/"right"}，缺省居中。
        zebra: 是否隔行浅绿底色。
    """
    if last_row < first_row:
        return
    data_font = font or _data_font
    for row_idx in range(first_row, last_row + 1):
        zebra_on = zebra and ((row_idx - first_row) % 2 == 1)
        for col_idx in range(1, col_count + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = _thin_border
            cell.font = data_font
            key = (align_map or {}).get(col_idx, "center")
            cell.alignment = _ALIGN_MAP.get(key, _center)
            if zebra_on:
                cell.fill = _zebra_fill


def autofit_widths(ws, headers: Sequence[Any], rows: Sequence[Sequence[Any]], min_w: float = 12, max_w: float = 45):
    """按表头与数据采样自适应列宽（采样前 100 行），返回列宽列表。"""
    widths = []
    for col_idx, header in enumerate(headers, 1):
        width = max(len(str(header)) * 2.0, min_w)
        for row in list(rows)[:100]:
            if col_idx - 1 < len(row):
                width = max(width, min(len(str(row[col_idx - 1] or "")), max_w))
        widths.append(min(width, max_w))
    return widths


# ═══════════════════════════════════════════════════════════════
# 打印设置
# ═══════════════════════════════════════════════════════════════
def setup_print(
    ws,
    col_count: int,
    last_row: int,
    header_row: Optional[int] = None,
    header_left: Optional[str] = None,
    header_right: Optional[str] = None,
    footer_text: Optional[str] = None,
    landscape: bool = True,
    freeze: bool = True,
) -> None:
    """套用 A4 打印设置：自适应宽度、页边距、页眉页脚（含页码）、重复表头、冻结。"""
    col_count = max(int(col_count or 0), 1)
    last_row = max(int(last_row or 0), 1)

    ws.page_setup.paperSize = _PAPER_A4
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    # fitToPage 必须显式开启，否则 fitToWidth/Height 被打开方忽略
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

    ws.page_margins = PageMargins(left=0.6, right=0.6, top=0.7, bottom=0.7, header=0.3, footer=0.3)
    ws.print_options.horizontalCentered = True

    # 打印区域
    ws.print_area = f"A1:{get_column_letter(col_count)}{last_row}"

    # 重复打印表头行（分页后每页顶部保留表头）
    if header_row:
        ws.print_title_rows = f"{header_row}:{header_row}"

    # 页眉：左=单位/标题，右=生成日期
    ws.oddHeader.left.text = header_left or SYSTEM_NAME
    ws.oddHeader.left.size = 9
    ws.oddHeader.left.color = MILITARY_GRAY_TEXT
    ws.oddHeader.right.text = header_right or _dt.date.today().strftime("%Y-%m-%d")
    ws.oddHeader.right.size = 9
    ws.oddHeader.right.color = MILITARY_GRAY_TEXT

    # 页脚：中=页码，左=审计水印（可选）
    page_no = "第 &P 页 / 共 &N 页"
    ws.oddFooter.center.text = f"{footer_text}    {page_no}" if footer_text else page_no
    ws.oddFooter.center.size = 9
    ws.oddFooter.center.color = MILITARY_GRAY_TEXT

    if freeze and header_row:
        ws.freeze_panes = f"A{header_row + 1}"


# ═══════════════════════════════════════════════════════════════
# 便捷入口
# ═══════════════════════════════════════════════════════════════
def build_report_sheet(
    wb,
    title: str,
    headers: Sequence[Any],
    rows: Sequence[Sequence[Any]] = (),
    *,
    subtitle: Optional[str] = None,
    sheet_name: Optional[str] = None,
    col_widths: Optional[Sequence[float]] = None,
    align_map: Optional[Dict[int, str]] = None,
    zebra: bool = True,
    watermark: Optional[str] = None,
    landscape: bool = True,
    system_name: Optional[str] = None,
    ws=None,
):
    """在 ``ws``（或新建工作表）上渲染一份带统一抬头/表头/边框/打印设置的报表。

    Returns:
        (ws, data_row_start, data_row_end)
    """
    if ws is None:
        ws = wb.create_sheet(title=(sheet_name or title or "报表")[:31])
    elif sheet_name:
        ws.title = sheet_name[:31]

    col_count = max(len(headers), 1)
    if col_widths is None:
        col_widths = autofit_widths(ws, headers, rows)

    header_row = apply_title_block(ws, title, subtitle=subtitle, col_count=col_count, system_name=system_name)
    style_header_row(ws, header_row, headers, col_widths=col_widths)

    data_start = header_row + 1
    for offset, row in enumerate(rows):
        r = data_start + offset
        for col_idx in range(1, col_count + 1):
            val = row[col_idx - 1] if (col_idx - 1) < len(row) else None
            ws.cell(row=r, column=col_idx, value=_coerce(val))
    data_end = data_start + len(rows) - 1 if rows else header_row

    style_data_region(ws, data_start, data_end, col_count, align_map=align_map, zebra=zebra)
    setup_print(
        ws,
        col_count=col_count,
        last_row=max(data_end, header_row),
        header_row=header_row,
        footer_text=watermark,
        landscape=landscape,
    )
    return ws, data_start, data_end
