"""表格填报导出服务（R61）。

把「导入模板」与「当前数据」合成一份可回导的 xlsx：
- 表头保持官方模板字段（中文标签），保证导入端原样识别；
- 每行末尾追加 `ID` 列，回导时按 ID 更新既有记录（不再重复建档）；
- 单条 / 批量共用同一实现，按数据权限过滤可见记录。
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from app.models.fund import Fund
from app.models.household import Household
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.services.data_scope_query import scoped_filter
from app.services.entity_import_validator import EntityImportValidator
from app.services.excel_template_service import ExcelTemplateService
from app.services.office_reader import load_workbook_any

MAX_EXPORT_ROWS = 5000

ENTITY_LABELS = {
    "supported_village": "帮扶村",
    "project": "项目",
    "fund": "资金",
    "school": "学校",
    "household": "一户一档",
}

TEMPLATE_METHODS = {
    "supported_village": "generate_village_template",
    "project": "generate_project_template",
    "fund": "generate_fund_template",
    "school": "generate_school_template",
    "household": "generate_household_template",
}

MODELS = {
    "supported_village": SupportedVillage,
    "project": Project,
    "fund": Fund,
    "school": School,
    "household": Household,
}

# 枚举英文值 → 模板中的中文标签（导出时写中文，回导时再归一为英文）
ENUM_DISPLAY = {
    "project_type": {
        "infrastructure": "基础设施",
        "education": "教育",
        "healthcare": "医疗",
        "agriculture": "农业",
        "industry": "产业",
        "other": "其他",
    },
    "school_type": {
        "primary": "小学",
        "middle": "初中",
        "high": "高中",
        "vocational": "职业学校",
        "other": "其他",
    },
    "support_status": {
        "active": "帮扶中",
        "inactive": "未帮扶",
        "completed": "已完成",
    },
    "household_type": {"general": "一般户", "poverty": "脱贫户", "monitor": "监测户"},
    "risk_type": {
        "none": "无",
        "income_drop": "收入骤减",
        "illness": "因病",
        "housing": "住房",
        "sudden": "突发",
        "multiple": "多重",
    },
    "risk_level": {"low": "低", "medium": "中", "high": "高"},
}


class FillTemplateService:
    """生成「已填数据」的导入模板（含 ID 列）。"""

    def __init__(self, db, current_user: Any = None):
        self.db = db
        self.current_user = current_user
        # household 模型没有 supported_village relationship，导出前按
        # supported_village_id 批量查村名/县/乡镇，保证回导时必填字段可识别。
        self._village_map: Dict[int, Any] = {}

    def export(self, entity_type: str, ids: Optional[Iterable[int]] = None) -> bytes:
        if entity_type not in ENTITY_LABELS:
            raise ValueError(f"不支持的填报导出类型: {entity_type}")

        template = getattr(ExcelTemplateService(), TEMPLATE_METHODS[entity_type])()
        workbook = load_workbook_any(template)
        sheet = workbook.active

        if entity_type == "supported_village":
            # 帮扶村沿用 DataValidatorService 的历史列映射（EntityImportValidator
            # 只覆盖 project/fund/school/household，没有 village 配置）。
            from app.services.data_validator_service import DataValidatorService

            validator = DataValidatorService()
            label_to_field = validator.COLUMN_MAPPING
        else:
            validator = EntityImportValidator(entity_type)
            label_to_field = validator.get_column_mapping()
        header_row, headers = self._locate_header(sheet, label_to_field)

        # 导出的“已填模板”去掉必填星号：回导/前端预览按纯标签匹配，避免
        # “*定点帮扶村”与“定点帮扶村”两种写法不一致。
        for col in range(1, len(headers) + 1):
            cell = sheet.cell(row=header_row, column=col)
            if isinstance(cell.value, str) and cell.value.startswith("*"):
                cell.value = cell.value.lstrip("*").strip()
        headers = [h.lstrip("*").strip() for h in headers]

        field_by_col: Dict[int, str] = {}
        for col, header in enumerate(headers, 1):
            clean = header.strip().lstrip("*").strip()
            field = label_to_field.get(clean)
            if field:
                field_by_col[col] = field

        id_col = next((col for col, field in field_by_col.items() if field == "id"), None)
        if id_col is None:
            id_col = len(headers) + 1
            sheet.cell(row=header_row, column=id_col, value="ID")

        # 删除模板示例行（避免用户再次在示例行上填写导致困惑）
        example_row = header_row + 1
        if any(
            "示例行" in str(sheet.cell(row=example_row, column=col).value or "")
            for col in range(1, max(id_col, len(headers)) + 1)
        ):
            sheet.delete_rows(example_row, 1)

        records = self._query_records(entity_type, ids)
        if entity_type == "household" and records:
            village_ids = {
                getattr(record, "supported_village_id", None) for record in records
            }
            village_ids.discard(None)
            # in_([]) 返回空集，无需再判空；保持单一查询路径便于覆盖。
            self._village_map = {
                village.id: village
                for village in self.db.query(SupportedVillage)
                .filter(SupportedVillage.id.in_(village_ids))
                .filter(SupportedVillage.is_active.is_(True))
                .all()
            }
        fields = {
            item["name"]: item
            for item in getattr(getattr(validator, "config", {}), "get", lambda *_: [])("fields", [])
        }

        for offset, record in enumerate(records):
            row = header_row + 1 + offset
            for col, field in field_by_col.items():
                if field == "id":
                    continue
                definition = fields.get(field, {})
                value = self._value_of(record, field, definition.get("type", "str"))
                sheet.cell(row=row, column=col, value=value)
            sheet.cell(row=row, column=id_col, value=record.id)

        buffer = io.BytesIO()
        workbook.save(buffer)
        workbook.close()
        return buffer.getvalue()

    def _query_records(self, entity_type: str, ids: Optional[Iterable[int]]) -> List[Any]:
        model = MODELS[entity_type]
        query = self.db.query(model)
        if ids:
            query = query.filter(model.id.in_([int(item) for item in ids]))
        if self.current_user is not None:
            query = scoped_filter(query, model, self.current_user)
        # 五个可导出模型均带 is_active（软删除），无需再做 hasattr 分支。
        query = query.filter(model.is_active.is_(True))
        return query.order_by(model.id).limit(MAX_EXPORT_ROWS).all()

    @staticmethod
    def _locate_header(sheet, label_to_field: Dict[str, str]) -> tuple[int, List[str]]:
        best_row, best_headers, best_hits = 1, [], 0
        for row_idx in range(1, min(sheet.max_row, 20) + 1):
            headers = [
                str(sheet.cell(row=row_idx, column=col).value or "").strip()
                for col in range(1, sheet.max_column + 1)
            ]
            hits = sum(
                1 for header in headers if header.lstrip("*").strip() in label_to_field
            )
            if hits > best_hits:
                best_row, best_headers, best_hits = row_idx, headers, hits
        if best_hits < 3:
            raise ValueError("模板表头识别失败，无法导出填报数据")
        # 返回去掉必填星号的表头，调用方按列号写值；避免 "定点帮扶村" 与
        # "*定点帮扶村" 两种写法导致回导测试/前端预览对不上。
        return best_row, [h.lstrip("*").strip() for h in best_headers]

    def _value_of(self, record: Any, field: str, field_type: str) -> Any:
        if field == "project_code":
            project = getattr(record, "project", None)
            return getattr(project, "code", "") or ""
        if field in ("village_name", "county", "township") and isinstance(record, Household):
            village = getattr(record, "supported_village", None)
            if village is None:
                village = self._village_map.get(getattr(record, "supported_village_id", None))
            return getattr(village, field, "") or ""
        value = getattr(record, field, None)
        if value is None:
            return ""
        # 模型列可能是 Python Enum（如 SchoolType.PRIMARY），取其 value 再转中文，
        # 否则会导出 "SchoolType.PRIMARY" 这类回导校验不认的字符串。
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, (datetime, date)):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, Decimal):
            return float(value)
        if field_type in ENUM_DISPLAY:
            return ENUM_DISPLAY[field_type].get(str(value), str(value))
        return value
