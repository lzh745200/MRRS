"""一村（校）一档 PDF 服务（w17-007）。

把单个帮扶村 / 帮扶学校的「档案 + 年度板块数据 + 关联项目经费 + 附件照片清单」
渲染成一份可直接打印归档的 PDF 册子：

- 封面：名称、所属组织、年度、档案生成信息；
- 基本信息表；
- 年度板块数据表（村：人口/收入/产业等年度子表；校：年度资助学生汇总）；
- 关联项目摘要与经费摘要（含合计行）；
- 附件照片清单；
- 文末口径脚注（数据截止 / 软删除 / 数据范围 / 生成人 / 生成时间）。

实现约束：
- 复用 :mod:`app.utils.pdf_report_style` —— 内置 CID 中文字体（免字体文件，
  解决中文乱码）、两遍式页眉页脚（「第 X 页 / 共 N 页」）、统一军绿表头表格样式；
- 空段降级：无年度数据 / 无项目 / 无经费 / 无附件时输出说明文字而非空表；
- 数据域校验与生成审计由 API 层负责（越权统一 404），本服务只渲染已授权记录。
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

DOSSIER_TITLE = "帮扶档案册"

# 项目状态中文映射（与 models/project.py ProjectStatus 取值一致）
_PROJECT_STATUS_CN = {
    "draft": "草稿",
    "pending": "待审批",
    "approved": "已批准",
    "in_progress": "进行中",
    "completed": "已完成",
    "cancelled": "已取消",
}

# 学校类型 / 帮扶状态中文映射（与 models/school.py 枚举一致）
_SCHOOL_TYPE_CN = {
    "primary": "小学",
    "middle": "初中",
    "high": "高中",
    "vocational": "职业学校",
    "other": "其他",
}

_SUPPORT_STATUS_CN = {
    "active": "帮扶中",
    "inactive": "未帮扶",
    "completed": "已完成",
}

# 学校项目阶段中文映射（与 models/school.py ProjectPhase 一致）
_SCHOOL_PHASE_CN = {
    "research": "调研",
    "approval": "立项审批",
    "implementation": "实施",
    "acceptance": "验收",
    "completed": "已完成",
}

# 村年度板块 → (模型关系名, 板块标题, [(字段名, 表头)])
_VILLAGE_SECTIONS: List[Tuple[str, str, List[Tuple[str, str]]]] = [
    (
        "population_data",
        "人口数据",
        [
            ("total_households", "总户数"),
            ("total_population", "总人口"),
            ("labor_force", "劳动力"),
            ("poverty_population", "脱贫人口"),
        ],
    ),
    (
        "income_data",
        "收入数据",
        [
            ("per_capita_income", "村人均纯收入(万元)"),
            ("collective_income", "村集体收入(万元)"),
        ],
    ),
    (
        "force_investment_data",
        "专项投入",
        [
            ("senior_leader_visits", "上级领导到村(人次)"),
            ("unit_soldier_visits", "帮扶单位人员到村(人次)"),
        ],
    ),
    (
        "industry_support_data",
        "产业帮扶",
        [
            ("investment", "当年投入(万元)"),
            ("planting_breeding", "种植养殖(个)"),
            ("rural_tourism", "乡村旅游(个)"),
        ],
    ),
    (
        "infrastructure_data",
        "基础设施改善",
        [
            ("investment", "当年投入(万元)"),
            ("road_km", "乡村道路(公里)"),
            ("housing_renovation", "住房改造(户)"),
        ],
    ),
    (
        "party_building_data",
        "党建帮扶",
        [
            ("investment", "党建投入(万元)"),
            ("paired_branches", "结对支部(个)"),
            ("party_instructors", "党建指导员(人)"),
        ],
    ),
    (
        "medical_support_data",
        "医疗帮扶",
        [
            ("investment", "医疗投入(万元)"),
            ("clinics_built", "帮建卫生院室(个)"),
            ("patients_served", "巡诊群众(人次)"),
        ],
    ),
    (
        "consumption_support_data",
        "消费帮扶",
        [
            ("village_products_purchase", "采购帮扶村产品(万元)"),
            ("benefited_population", "惠及群众(人)"),
        ],
    ),
    (
        "employment_support_data",
        "就业帮扶",
        [
            ("hired_population", "聘用群众(人)"),
            ("trained_population", "培训人数(人次)"),
        ],
    ),
    (
        "education_support_data",
        "教育帮扶",
        [
            ("investment", "教育投入(万元)"),
            ("aided_students", "资助学生(人)"),
            ("donated_schools", "捐赠学校(所)"),
        ],
    ),
]


def _display(value: Any) -> str:
    """档案展示值格式化：空值占位、布尔转是/否、日期取 yyyy-mm-dd。"""
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _status_text(status: Any, mapping: Dict[str, str]) -> str:
    """枚举/字符串状态转中文（未知取值原样展示，空值占位）。"""
    if status is None:
        return "-"
    raw = getattr(status, "value", status)
    return mapping.get(str(raw), str(raw))


def _num(value: Any) -> float:
    """数值安全转换（None/非法值按 0 计，避免合计行崩溃）。"""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def record_dossier_audit(
    current_user: Any, entity_type: str, entity_id: Any, entity_name: str
) -> None:
    """档案册生成留痕（导出审计）。"""
    from app.models.audit import AuditAction
    from app.utils.audit_logger import AuditLogger

    AuditLogger.log(
        action=AuditAction.EXPORT,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        resource_type=entity_type,
        resource_id=entity_id,
        details={
            "format": "pdf",
            "dossier": "一村一档" if entity_type == "supported_village" else "一校一档",
            "name": entity_name,
        },
    )


class DossierService:
    """一村（校）一档 PDF 渲染服务。"""

    def __init__(self, db=None, current_user=None):
        self.db = db
        self.current_user = current_user

    # ────────────────────── 通用 ──────────────────────

    def _generated_by(self) -> str:
        """生成人展示名（无用户上下文时记「系统」，脚注不输出空字段）。"""
        if self.current_user is None:
            return "系统"
        name = getattr(self.current_user, "full_name", None) or getattr(
            self.current_user, "username", None
        )
        return str(name) if name else "系统"

    def _footnote(self) -> str:
        """文末口径脚注文本。"""
        from app.services.export_service import (
            build_scope_footnote,
            describe_data_scope,
            format_scope_footnote,
        )

        return format_scope_footnote(
            build_scope_footnote(
                include_deleted=False,
                scope=describe_data_scope(self.current_user),
                generated_by=self._generated_by(),
            )
        )

    def _organization_name(self, record: Any) -> Optional[str]:
        """所属组织名称（无组织归属或组织已不存在时返回 None）。"""
        org_id = getattr(record, "organization_id", None)
        if org_id is None:
            return None
        from app.models.organization import Organization

        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        return getattr(org, "name", None) if org is not None else None

    @staticmethod
    def _region(record: Any) -> Optional[str]:
        """省/市/县拼接展示（全空返回 None）。"""
        parts = [
            getattr(record, "province", None),
            getattr(record, "city", None),
            getattr(record, "county", None) or getattr(record, "district", None),
        ]
        text = " / ".join(str(part) for part in parts if part)
        return text or None

    @staticmethod
    def _table_section(title: str, headers: List[str], rows: List[List[str]]) -> Dict[str, Any]:
        return {"title": title, "headers": headers, "rows": rows}

    # ────────────────────── 帮扶村 ──────────────────────

    def _yearly_rows(self, records: List[Any], fields: List[Tuple[str, str]]) -> List[List[str]]:
        rows = []
        for record in sorted(records, key=lambda r: getattr(r, "year", 0) or 0):
            row = [_display(getattr(record, "year", None))]
            row.extend(_display(getattr(record, field, None)) for field, _label in fields)
            rows.append(row)
        return rows

    def _village_sections(self, village: Any) -> List[Dict[str, Any]]:
        sections = []
        for attr, label, fields in _VILLAGE_SECTIONS:
            rows = self._yearly_rows(getattr(village, attr, None) or [], fields)
            if rows:
                sections.append(
                    self._table_section(label, ["年度"] + [header for _f, header in fields], rows)
                )
        return sections

    def _village_project_section(self, village: Any) -> Dict[str, Any]:
        from app.models.project import Project

        projects = (
            self.db.query(Project)
            .filter(Project.village_id == village.id, Project.is_active.is_(True))
            .order_by(Project.id)
            .all()
        )
        rows = [
            [
                _display(item.name),
                _status_text(item.status, _PROJECT_STATUS_CN),
                _display(item.budget),
                _display(item.progress),
            ]
            for item in projects
        ]
        return self._table_section(
            "关联项目摘要", ["项目名称", "状态", "预算(万元)", "进度(%)"], rows
        )

    def _village_fund_section(self, village: Any) -> Dict[str, Any]:
        from app.models.fund import Fund

        funds = (
            self.db.query(Fund)
            .filter(Fund.village_id == village.id, Fund.is_active.is_(True))
            .order_by(Fund.id)
            .all()
        )
        rows = [
            [
                _display(item.name),
                _display(item.fund_type),
                _display(item.amount),
                _display(item.status),
            ]
            for item in funds
        ]
        if rows:
            rows.append(["合计", "", f"{sum(_num(item.amount) for item in funds):.2f}", ""])
        return self._table_section(
            "帮扶经费摘要", ["名称", "类型", "金额(万元)", "状态"], rows
        )

    def _village_attachment_section(self, village: Any) -> Dict[str, Any]:
        from app.models.supported_village import VillageAttachment

        attachments = (
            self.db.query(VillageAttachment)
            .filter(VillageAttachment.supported_village_id == village.id)
            .order_by(VillageAttachment.id)
            .all()
        )
        rows = [
            [
                _display(item.file_name),
                _display(item.description),
                _display(item.file_size),
                _display(item.created_at),
            ]
            for item in attachments
        ]
        return self._table_section(
            "附件照片清单", ["文件名", "说明", "大小(字节)", "上传时间"], rows
        )

    def build_village_document(self, village: Any) -> Dict[str, Any]:
        """组装帮扶村档案册数据（渲染前可单测的纯数据层）。"""
        year = getattr(village, "latest_year", None) or datetime.now().year
        region = self._region(village)
        basic = [
            ("帮扶村名称", _display(getattr(village, "village_name", None))),
            ("所属组织", _display(self._organization_name(village))),
            ("地区", _display(region)),
            ("部门单位", _display(getattr(village, "department", None))),
            ("帮扶单位", _display(getattr(village, "support_unit", None))),
            ("是否振兴梯队", _display(getattr(village, "is_revitalization_tier", None))),
            ("获得表彰", _display(getattr(village, "honors", None))),
            ("创建时间", _display(getattr(village, "created_at", None))),
        ]
        name = getattr(village, "village_name", None) or "帮扶村"
        return {
            "entity_type": "supported_village",
            "title": f"{name} · {DOSSIER_TITLE}",
            "header": f"帮扶管理信息系统 · {name}",
            "subtitle": f"年度：{year}    所属组织：{_display(self._organization_name(village))}",
            "basic": basic,
            "sections": self._village_sections(village),
            "projects": self._village_project_section(village),
            "funds": self._village_fund_section(village),
            "attachments": self._village_attachment_section(village),
            "footnote": self._footnote(),
        }

    def render_village_pdf(self, village: Any) -> bytes:
        """渲染帮扶村档案册 PDF。"""
        return self._render(self.build_village_document(village))

    # ────────────────────── 帮扶学校 ──────────────────────

    def _school_project_section(self, school: Any) -> Dict[str, Any]:
        from app.models.school import SchoolProject

        projects = (
            self.db.query(SchoolProject)
            .filter(SchoolProject.school_id == school.id)
            .order_by(SchoolProject.id)
            .all()
        )
        rows = [
            [
                _display(item.name),
                _display(item.category),
                _status_text(item.phase, _SCHOOL_PHASE_CN),
                _display(item.budget),
                _display(item.actual_cost),
            ]
            for item in projects
        ]
        if rows:
            rows.append(
                [
                    "合计",
                    "",
                    "",
                    f"{sum(_num(item.budget) for item in projects):.2f}",
                    f"{sum(_num(item.actual_cost) for item in projects):.2f}",
                ]
            )
        return self._table_section(
            "助学兴教项目摘要", ["项目名称", "类别", "阶段", "预算(万元)", "实际投入(万元)"], rows
        )

    def _school_fund_section(self, school: Any) -> Dict[str, Any]:
        from app.models.school import SchoolSupport

        supports = (
            self.db.query(SchoolSupport)
            .filter(SchoolSupport.school_id == school.id)
            .order_by(SchoolSupport.id)
            .all()
        )
        rows = [
            [
                _display(item.support_type),
                _display(item.amount),
                _display(item.support_date),
                _display(item.description),
            ]
            for item in supports
        ]
        if rows:
            rows.append(["合计", f"{sum(_num(item.amount) for item in supports):.2f}", "", ""])
        return self._table_section(
            "帮扶经费摘要", ["帮扶类型", "金额(元)", "帮扶日期", "说明"], rows
        )

    def _school_scholarship_section(self, school: Any) -> Dict[str, Any]:
        """年度资助汇总（按年度聚合人数与金额）。"""
        from app.models.school import ScholarshipStudent

        students = (
            self.db.query(ScholarshipStudent)
            .filter(ScholarshipStudent.school_id == school.id)
            .order_by(ScholarshipStudent.id)
            .all()
        )
        grouped: Dict[Any, Dict[str, Any]] = {}
        for item in students:
            key = item.year
            bucket = grouped.setdefault(key, {"count": 0, "amount": 0.0})
            bucket["count"] += 1
            bucket["amount"] += _num(item.amount)
        rows = [
            [
                _display(year) if year is not None else "未标注年度",
                str(bucket["count"]),
                f"{bucket['amount']:.2f}",
            ]
            for year, bucket in sorted(grouped.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
        ]
        return self._table_section("年度资助数据", ["年度", "资助人数", "资助金额(元)"], rows)

    def _school_attachment_section(self, school: Any) -> Dict[str, Any]:
        from app.models.school import SchoolAttachment

        attachments = (
            self.db.query(SchoolAttachment)
            .filter(SchoolAttachment.school_id == school.id)
            .order_by(SchoolAttachment.id)
            .all()
        )
        rows = [
            [
                _display(item.file_name),
                _display(item.description),
                _display(item.file_size),
                _display(item.created_at),
            ]
            for item in attachments
        ]
        return self._table_section(
            "附件照片清单", ["文件名", "说明", "大小(字节)", "上传时间"], rows
        )

    def build_school_document(self, school: Any) -> Dict[str, Any]:
        """组装帮扶学校档案册数据（渲染前可单测的纯数据层）。"""
        name = getattr(school, "name", None) or "帮扶学校"
        basic = [
            ("学校名称", _display(getattr(school, "name", None))),
            ("学校编码", _display(getattr(school, "code", None))),
            ("所属组织", _display(self._organization_name(school))),
            ("学校类型", _status_text(getattr(school, "type", None), _SCHOOL_TYPE_CN)),
            ("地区", _display(self._region(school))),
            ("帮扶状态", _status_text(getattr(school, "support_status", None), _SUPPORT_STATUS_CN)),
            ("帮扶单位", _display(getattr(school, "support_unit", None))),
            ("学生人数", _display(getattr(school, "student_count", None))),
            ("教师人数", _display(getattr(school, "teacher_count", None))),
            ("班级数量", _display(getattr(school, "class_count", None))),
        ]
        sections = [self._school_scholarship_section(school)]
        return {
            "entity_type": "school",
            "title": f"{name} · {DOSSIER_TITLE}",
            "header": f"帮扶管理信息系统 · {name}",
            "subtitle": f"所属组织：{_display(self._organization_name(school))}",
            "basic": basic,
            "sections": [section for section in sections if section["rows"]],
            "projects": self._school_project_section(school),
            "funds": self._school_fund_section(school),
            "attachments": self._school_attachment_section(school),
            "footnote": self._footnote(),
        }

    def render_school_pdf(self, school: Any) -> bytes:
        """渲染帮扶学校档案册 PDF。"""
        return self._render(self.build_school_document(school))

    # ────────────────────── PDF 渲染 ──────────────────────

    @staticmethod
    def _make_basic_table(basic: List[Tuple[str, str]]):
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import Table, TableStyle

        from app.utils.pdf_report_style import CJK_FONT

        data = [[escape(str(label)), escape(str(value))] for label, value in basic]
        table = Table(data, colWidths=[38 * mm, 118 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), CJK_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F0EB")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    @staticmethod
    def _make_data_table(section: Dict[str, Any]):
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle

        from app.utils.pdf_report_style import data_table_style

        data = [section["headers"]] + [
            [escape(str(cell)) for cell in row] for row in section["rows"]
        ]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle(data_table_style()))
        # 合计行浅金底突出（仅当末行为「合计」）；字体沿用已注册的 CID 中文字体
        last_row = section["rows"][-1] if section["rows"] else None
        if last_row is not None and str(last_row[0]) == "合计":
            table.setStyle(
                TableStyle([("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F5EFD7"))])
            )
        return table

    def _render(self, document: Dict[str, Any]) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

        from app.utils.pdf_report_style import ensure_cjk_font, make_numbered_canvas

        ensure_cjk_font()
        title_style = ParagraphStyle(
            "cover_title", fontName="STSong-Light", fontSize=22, leading=32, alignment=1
        )
        cover_meta_style = ParagraphStyle(
            "cover_meta", fontName="STSong-Light", fontSize=11, leading=18, alignment=1,
            textColor=colors.HexColor("#334155"),
        )
        heading_style = ParagraphStyle(
            "dossier_heading", fontName="STSong-Light", fontSize=14, leading=20,
            spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#1B4332"),
        )
        sub_heading_style = ParagraphStyle(
            "dossier_sub", fontName="STSong-Light", fontSize=11, leading=16,
            spaceBefore=6, spaceAfter=3,
        )
        body_style = ParagraphStyle("dossier_body", fontName="STSong-Light", fontSize=10, leading=15)
        foot_style = ParagraphStyle(
            "dossier_foot", fontName="STSong-Light", fontSize=8, leading=12, textColor=colors.grey
        )

        story = [
            Spacer(1, 45 * mm),
            Paragraph(escape(document["title"]), title_style),
            Spacer(1, 10 * mm),
            Paragraph(escape(document["subtitle"]), cover_meta_style),
            Spacer(1, 6 * mm),
            Paragraph(escape(document["footnote"]), cover_meta_style),
            PageBreak(),
            Paragraph("一、基本信息", heading_style),
            self._make_basic_table(document["basic"]),
            Paragraph("二、年度数据", heading_style),
        ]

        sections = document["sections"]
        if sections:
            for section in sections:
                story.append(Paragraph(escape(section["title"]), sub_heading_style))
                story.append(self._make_data_table(section))
                story.append(Spacer(1, 3 * mm))
        else:
            story.append(Paragraph("暂无年度数据。", body_style))

        for heading, key, empty_text in (
            ("三、关联项目", "projects", "暂无关联项目。"),
            ("四、帮扶经费", "funds", "暂无帮扶经费记录。"),
            ("五、附件照片清单", "attachments", "暂无附件照片。"),
        ):
            story.append(Paragraph(heading, heading_style))
            section = document[key]
            if section["rows"]:
                story.append(self._make_data_table(section))
            else:
                story.append(Paragraph(empty_text, body_style))

        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(escape(document["footnote"]), foot_style))

        buf = BytesIO()
        SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=22 * mm,
            bottomMargin=18 * mm,
            title=document["title"],
        ).build(story, canvasmaker=make_numbered_canvas(document["header"]))
        return buf.getvalue()
