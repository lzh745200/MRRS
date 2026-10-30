"""Excel 导出服务 - 实现真实的数据导出功能"""

from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from openpyxl import Workbook


# ══════════════════════════════════════════════════════════════════════
# w17-006 导出物「口径脚注」— 数据截止 / 过滤条件 / 软删除 / 范围 / 生成人 / 时间
#
# 所有导出口共用一个生成函数：先 ``build_scope_footnote`` 产出结构化字段（空字段
# 自动省略），再按载体格式化成单行文本。Excel 走表尾脚注行，Word/PDF 走文末段落。
# 口径说明缺失是「汇报口径靠口头解释」的根因，故此处是唯一事实源，各服务只接线。
# ══════════════════════════════════════════════════════════════════════

FOOTNOTE_PREFIX = "口径说明"
_SOFT_DELETE_EXCLUDED = "已排除软删除记录"
_SOFT_DELETE_INCLUDED = "含软删除记录"


def _format_local_time(value: Optional[datetime]) -> str:
    """格式化时间：aware → 本地墙钟；naive 视为 UTC；None → 当前时刻。"""
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _format_scope_filters(filters: Optional[Dict[str, Any]]) -> Optional[str]:
    """把过滤条件字典整理为「键=值；…」文本；无有效条件返回 None（脚注不输出空字段）。"""
    if not filters:
        return None
    parts = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "是" if value else "否"
        text = str(value).strip()
        if not text:
            continue
        parts.append(f"{key}={text}")
    return "；".join(parts) if parts else None


def describe_data_scope(user: Any) -> Optional[str]:
    """当前用户数据范围的中文描述（None 用户返回 None，脚注省略该字段）。"""
    if user is None:
        return None
    from app.core.data_permission import DataScope, get_data_scope

    scope = get_data_scope(user)
    if scope == DataScope.ALL:
        return "全部数据（跨组织）"
    if scope == DataScope.OWN_DEPT:
        return "本组织及下级组织"
    return "仅本人创建的数据"


def exporter_from_watermark(watermark: Optional[str]) -> Optional[str]:
    """从导出审计水印（``导出人：张三  2026-01-01 10:00``）中解析生成人。

    解析不到（无 watermark / 无标记 / 标记后为空）时返回 None —— 脚注省略生成人，
    不输出「生成人：」这类空字段。
    """
    marker = "导出人："
    if not watermark or marker not in watermark:
        return None
    name = watermark.split(marker, 1)[1].strip()
    return name.split()[0] if name else None


def build_scope_footnote(
    *,
    data_cutoff: Optional[datetime] = None,
    filters: Optional[Dict[str, Any]] = None,
    include_deleted: bool = False,
    scope: Optional[str] = None,
    generated_by: Optional[str] = None,
    generated_at: Optional[datetime] = None,
) -> Dict[str, str]:
    """构造口径脚注字段（有序；空字段不输出，保持整洁）。

    Args:
        data_cutoff: 数据截止时刻（导出所反映的数据快照时间）；缺省取 generated_at。
        filters: 当前导出过滤条件（键 → 值）；值为 None/空串/空列表的条件自动省略。
        include_deleted: 是否包含软删除记录（导出默认排除）。
        scope: 数据范围描述（见 :func:`describe_data_scope`）。
        generated_by: 生成人（可选）。
        generated_at: 生成时间；缺省为当前时刻。
    """
    cutoff = data_cutoff if data_cutoff is not None else generated_at
    footnote: Dict[str, str] = {"数据截止": _format_local_time(cutoff)}
    filter_text = _format_scope_filters(filters)
    if filter_text:
        footnote["过滤条件"] = filter_text
    footnote["软删除"] = _SOFT_DELETE_INCLUDED if include_deleted else _SOFT_DELETE_EXCLUDED
    if scope:
        footnote["数据范围"] = scope
    if generated_by:
        footnote["生成人"] = generated_by
    footnote["生成时间"] = _format_local_time(generated_at)
    return footnote


def format_scope_footnote(footnote: Dict[str, str], prefix: str = FOOTNOTE_PREFIX) -> str:
    """把口径脚注字段序列化为单行文本（无字段时返回空串）。"""
    body = "；".join(f"{key}：{value}" for key, value in footnote.items() if value)
    return f"{prefix}：{body}" if body else ""


def apply_scope_footnote(ws, text: str, *, start_row: int, col_count: int = 1) -> int:
    """在 Excel 工作表尾部追加口径脚注（灰色小字 + 跨列合并），返回脚注行号。"""
    from openpyxl.styles import Alignment, Font

    cell = ws.cell(row=start_row, column=1, value=text)
    cell.font = Font(name="SimSun", size=9, color="64748B")
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    if col_count > 1:
        ws.merge_cells(
            start_row=start_row, start_column=1, end_row=start_row, end_column=col_count
        )
    ws.row_dimensions[start_row].height = 18
    return start_row


class ExcelExportService:
    """Excel 导出服务"""

    @staticmethod
    def _default_footnote(watermark: str) -> str:
        """默认口径脚注：生成人从审计水印解析，过滤条件由调用方显式传入。"""
        return format_scope_footnote(
            build_scope_footnote(generated_by=exporter_from_watermark(watermark))
        )

    def _resolve_footnote(self, footnote: Optional[str], watermark: str) -> str:
        """显式脚注优先；未传时生成默认口径脚注（列表导出无过滤条件上下文）。"""
        return self._default_footnote(watermark) if footnote is None else footnote

    def _create_workbook(
        self,
        sheet_name: str,
        headers: list,
        rows: list[dict],
        watermark: str = "",
        footnote: Optional[str] = None,
    ) -> "Workbook":
        """创建通用 Excel 工作簿（统一军绿+金色样式 + A4 打印设置）。

        watermark 追加到页脚，用于审计溯源；footnote 追加到数据区尾部（口径脚注）。
        """
        from app.utils.excel_report_style import build_report_sheet, make_subtitle
        # P2-4 启动优化：openpyxl 惰性导入（import 期约 760ms，含 numpy）
        from openpyxl import Workbook

        def _safe_export_value(value):
            """防公式注入：字符串危险前缀加单引号，保持数值/日期原样。"""
            if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
                return "'" + value
            return value

        wb = Workbook()
        matrix = [[_safe_export_value(row.get(h, "")) for h in headers] for row in rows]
        ws, _data_start, data_end = build_report_sheet(
            wb,
            title=sheet_name,
            headers=headers,
            rows=matrix,
            subtitle=make_subtitle(extra=f"共 {len(rows)} 条记录"),
            sheet_name=sheet_name,
            ws=wb.active,
            watermark=watermark,
        )
        if footnote:
            apply_scope_footnote(
                ws, footnote, start_row=data_end + 2, col_count=max(len(headers), 1)
            )
        return wb

    @staticmethod
    def _to_bytes(wb: "Workbook") -> bytes:
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def export_user_list(self, data: list[dict], watermark: str = "", footnote: Optional[str] = None) -> bytes:
        headers = ["ID", "用户名", "邮箱", "姓名", "角色", "状态", "最后登录"]
        footnote_text = self._resolve_footnote(footnote, watermark)
        wb = self._create_workbook(
            "用户列表", headers, data, watermark=watermark, footnote=footnote_text
        )
        return self._to_bytes(wb)

    def export_village_list(self, data: list[dict], watermark: str = "", footnote: Optional[str] = None) -> bytes:
        headers = ["ID", "名称", "编码", "省份", "城市", "区县", "人口", "状态", "创建时间"]
        footnote_text = self._resolve_footnote(footnote, watermark)
        wb = self._create_workbook(
            "村庄列表", headers, data, watermark=watermark, footnote=footnote_text
        )
        return self._to_bytes(wb)

    def export_school_list(self, data: list[dict], watermark: str = "", footnote: Optional[str] = None) -> bytes:
        headers = ["ID", "名称", "编码", "类型", "城市", "学生数", "教师数", "状态"]
        footnote_text = self._resolve_footnote(footnote, watermark)
        wb = self._create_workbook(
            "学校列表", headers, data, watermark=watermark, footnote=footnote_text
        )
        return self._to_bytes(wb)

    def export_project_list(self, data: list[dict], watermark: str = "", footnote: Optional[str] = None) -> bytes:
        headers = ["ID", "名称", "编码", "类型", "状态", "预算", "进度", "开始日期", "结束日期"]
        footnote_text = self._resolve_footnote(footnote, watermark)
        wb = self._create_workbook(
            "项目列表", headers, data, watermark=watermark, footnote=footnote_text
        )
        return self._to_bytes(wb)

    def export_fund_list(self, data: list[dict], watermark: str = "", footnote: Optional[str] = None) -> bytes:
        headers = ["ID", "名称", "类型", "金额", "来源", "用途", "状态", "经办人", "使用日期"]
        footnote_text = self._resolve_footnote(footnote, watermark)
        wb = self._create_workbook(
            "经费列表", headers, data, watermark=watermark, footnote=footnote_text
        )
        return self._to_bytes(wb)

    def export_organizations(
        self, organizations: list[dict], filename: str = "组织机构列表", watermark: str = ""
    ) -> bytes:
        """导出组织机构列表为 Excel。

        Args:
            organizations: 组织记录列表，每项为 dict。
            filename: 工作表名称。
            watermark: 页脚审计水印（导出人/时间）。
        """
        headers = [
            "名称", "编码", "类型", "层级", "联系人", "联系电话",
            "地址", "描述", "成员数", "状态", "创建时间",
        ]
        # 显式字段映射：_create_workbook 以“中文表头 == row 的键”取值，而调用方
        # （api/v1/organization.py::export_organizations）给的是英文字段名。历史实现直接
        # 把中文表头当键去 row.get → 11 列全部落空，导出文件只有表头。
        rows = [
            {
                "名称": item.get("name", ""),
                "编码": item.get("code", ""),
                "类型": item.get("type", ""),
                "层级": item.get("level", ""),
                "联系人": item.get("contact_person", ""),
                "联系电话": item.get("contact_phone", ""),
                "地址": item.get("address", ""),
                "描述": item.get("description", ""),
                "成员数": item.get("member_count", ""),
                "状态": item.get("status", ""),
                "创建时间": item.get("created_at", ""),
            }
            for item in organizations
        ]
        wb = self._create_workbook(filename, headers, rows, watermark=watermark)
        return self._to_bytes(wb)

    def export_organization_pass_codes(
        self, pass_codes: list[dict], filename: str = "组织通行证码列表", watermark: str = ""
    ) -> bytes:
        """导出组织通行证码列表为 Excel。

        Args:
            pass_codes: 通行证码记录列表，每项为 dict，包含 organization_name /
                verification_code / pass_code / allow_subordinate_generation /
                status / created_time 等键。
            filename: 工作表名称（同时用作导出文件名提示）。
            watermark: 页脚审计水印（导出人/时间）。
        """
        headers = ["组织名称", "校验码", "通行证码", "允许下级生成", "状态", "创建时间"]
        rows = [
            {
                "组织名称": item.get("organization_name", ""),
                "校验码": item.get("verification_code", ""),
                "通行证码": item.get("pass_code", ""),
                "允许下级生成": "是" if item.get("allow_subordinate_generation") else "否",
                "状态": item.get("status", ""),
                "创建时间": item.get("created_at", ""),
            }
            for item in pass_codes
        ]
        wb = self._create_workbook(filename, headers, rows, watermark=watermark)
        return self._to_bytes(wb)

    def export_comprehensive_report(
        self,
        summary: dict,
        village_data: list[dict],
        project_data: list[dict],
        fund_data: list[dict],
        watermark: str = "",
        footnote: Optional[str] = None,
    ) -> bytes:
        """导出综合报表（多 sheet，统一军绿+金色样式 + A4 打印设置）。

        w17-006：每个数据 sheet 的数据区尾部都追加同一条口径脚注。
        """
        from app.utils.excel_report_style import build_report_sheet, make_subtitle
        # P2-4 启动优化：openpyxl 惰性导入（同上）
        from openpyxl import Workbook

        wb = Workbook()
        footnote_text = self._resolve_footnote(footnote, watermark)

        def _sheet(*args, **kwargs):
            ws, _start, data_end = build_report_sheet(*args, **kwargs)
            apply_scope_footnote(
                ws, footnote_text, start_row=data_end + 2, col_count=max(len(kwargs["headers"]), 1)
            )

        # 汇总 sheet
        summary_headers = ["统计项", "数值"]
        summary_rows = [[k, v] for k, v in summary.items()]
        _sheet(
            wb,
            title="帮扶数据综合报表 · 汇总",
            headers=summary_headers,
            rows=summary_rows,
            subtitle=make_subtitle(),
            sheet_name="汇总",
            ws=wb.active,
            watermark=watermark,
        )

        # 村庄 sheet
        if village_data:
            v_headers = ["ID", "名称", "人口", "项目数", "产业数"]
            _sheet(
                wb,
                title="帮扶村统计",
                headers=v_headers,
                rows=[[r.get(h, "") for h in v_headers] for r in village_data],
                sheet_name="村庄",
                watermark=watermark,
            )

        # 项目 sheet
        if project_data:
            p_headers = ["ID", "名称", "状态", "预算", "进度"]
            _sheet(
                wb,
                title="帮扶项目统计",
                headers=p_headers,
                rows=[[r.get(h, "") for h in p_headers] for r in project_data],
                sheet_name="项目",
                watermark=watermark,
            )

        # 经费 sheet
        if fund_data:
            f_headers = ["ID", "名称", "金额", "状态", "使用日期"]
            _sheet(
                wb,
                title="帮扶经费统计",
                headers=f_headers,
                rows=[[r.get(h, "") for h in f_headers] for r in fund_data],
                sheet_name="经费",
                watermark=watermark,
            )

        return self._to_bytes(wb)


export_service = ExcelExportService()
