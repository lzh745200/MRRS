"""Excel 导出服务 - 实现真实的数据导出功能"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


class ExcelExportService:
    """Excel 导出服务"""

    _HEADER_FONT = Font(bold=True, size=11)
    _HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    _HEADER_FONT_WHITE = Font(bold=True, size=11, color="FFFFFF")
    _THIN_BORDER = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    _CENTER_ALIGN = Alignment(horizontal="center", vertical="center")

    def _create_workbook(self, sheet_name: str, headers: list, rows: list[dict], watermark: str = "") -> Workbook:
        """创建通用 Excel 工作簿（统一军绿+金色样式 + A4 打印设置）。

        watermark 追加到页脚，用于审计溯源。
        """
        from app.utils.excel_report_style import build_report_sheet, make_subtitle

        wb = Workbook()
        matrix = [[row.get(h, "") for h in headers] for row in rows]
        build_report_sheet(
            wb,
            title=sheet_name,
            headers=headers,
            rows=matrix,
            subtitle=make_subtitle(extra=f"共 {len(rows)} 条记录"),
            sheet_name=sheet_name,
            ws=wb.active,
            watermark=watermark,
        )
        return wb

    @staticmethod
    def _to_bytes(wb: Workbook) -> bytes:
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def export_user_list(self, data: list[dict], watermark: str = "") -> bytes:
        headers = ["ID", "用户名", "邮箱", "姓名", "角色", "状态", "最后登录"]
        wb = self._create_workbook("用户列表", headers, data, watermark=watermark)
        return self._to_bytes(wb)

    def export_village_list(self, data: list[dict], watermark: str = "") -> bytes:
        headers = ["ID", "名称", "编码", "省份", "城市", "区县", "人口", "状态", "创建时间"]
        wb = self._create_workbook("村庄列表", headers, data, watermark=watermark)
        return self._to_bytes(wb)

    def export_school_list(self, data: list[dict], watermark: str = "") -> bytes:
        headers = ["ID", "名称", "编码", "类型", "城市", "学生数", "教师数", "状态"]
        wb = self._create_workbook("学校列表", headers, data, watermark=watermark)
        return self._to_bytes(wb)

    def export_project_list(self, data: list[dict], watermark: str = "") -> bytes:
        headers = ["ID", "名称", "编码", "类型", "状态", "预算", "进度", "开始日期", "结束日期"]
        wb = self._create_workbook("项目列表", headers, data, watermark=watermark)
        return self._to_bytes(wb)

    def export_fund_list(self, data: list[dict], watermark: str = "") -> bytes:
        headers = ["ID", "名称", "类型", "金额", "来源", "用途", "状态", "经办人", "使用日期"]
        wb = self._create_workbook("经费列表", headers, data, watermark=watermark)
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
        wb = self._create_workbook(filename, headers, organizations, watermark=watermark)
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
    ) -> bytes:
        """导出综合报表（多 sheet，统一军绿+金色样式 + A4 打印设置）"""
        from app.utils.excel_report_style import build_report_sheet, make_subtitle

        wb = Workbook()

        # 汇总 sheet
        summary_headers = ["统计项", "数值"]
        summary_rows = [[k, v] for k, v in summary.items()]
        build_report_sheet(
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
            build_report_sheet(
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
            build_report_sheet(
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
            build_report_sheet(
                wb,
                title="帮扶经费统计",
                headers=f_headers,
                rows=[[r.get(h, "") for h in f_headers] for r in fund_data],
                sheet_name="经费",
                watermark=watermark,
            )

        return self._to_bytes(wb)


export_service = ExcelExportService()
