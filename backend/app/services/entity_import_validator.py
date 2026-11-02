"""
通用实体导入验证器
支持 projects、funds、schools、supported_villages 的 Excel 导入验证
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ValidationErrorCode(str, Enum):
    """验证错误码"""

    INVALID_FILE_FORMAT = "IMPORT_001"
    FILE_TOO_LARGE = "IMPORT_002"
    MISSING_REQUIRED_FIELD = "IMPORT_003"
    INVALID_DATA_FORMAT = "IMPORT_004"
    DUPLICATE_DATA = "IMPORT_005"
    DATABASE_ERROR = "IMPORT_006"
    ROW_LIMIT_EXCEEDED = "IMPORT_007"
    INVALID_COUNTY = "IMPORT_008"
    INVALID_TIERED_LEVEL = "IMPORT_009"
    INVALID_NUMERIC_VALUE = "IMPORT_010"
    VALUE_OUT_OF_RANGE = "IMPORT_011"
    INVALID_ENUM_VALUE = "IMPORT_012"
    INVALID_PHONE = "IMPORT_013"
    INVALID_DATE = "IMPORT_014"
    REFERENCE_NOT_FOUND = "IMPORT_015"


# 黔南州12个县市常量
QIANNAN_COUNTIES = [
    "都匀市",
    "长顺县",
    "独山县",
    "平塘县",
    "罗甸县",
    "惠水县",
    "贵定县",
    "福泉市",
    "瓮安县",
    "三都县",
    "荔波县",
    "龙里县",
]


@dataclass
class ValidationError:
    """验证错误"""

    row_number: int
    field_name: str
    error_code: ValidationErrorCode
    message: str
    value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_number": self.row_number,
            "field_name": self.field_name,
            "error_code": self.error_code.value,
            "message": self.message,
            "value": str(self.value) if self.value is not None else None,
        }


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    total_rows: int = 0
    valid_rows: int = 0
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
        }


class EntityImportValidator:
    """通用实体导入验证器"""

    ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_ROWS = 1000

    # ============== 项目导入定义 ==============
    PROJECT_FIELDS: List[Dict[str, Any]] = [
        {"name": "name", "label": "项目名称", "required": True, "type": "str", "example": "村内道路硬化项目"},
        {"name": "code", "label": "项目编号", "required": False, "type": "str", "example": "XM-2024-001"},
        {"name": "type", "label": "项目类型", "required": True, "type": "project_type", "example": "基础设施"},
        {"name": "status", "label": "项目状态", "required": False, "type": "project_status", "example": "draft"},
        {
            "name": "description",
            "label": "项目描述",
            "required": False,
            "type": "str",
            "example": "硬化村内主干道3公里",
        },
        {"name": "budget", "label": "预算金额", "required": False, "type": "float", "example": "50.00"},
        {"name": "start_date", "label": "开始日期", "required": False, "type": "date", "example": "2024-01-01"},
        {"name": "end_date", "label": "结束日期", "required": False, "type": "date", "example": "2024-12-31"},
        {"name": "leader", "label": "项目负责人", "required": False, "type": "str", "example": "张三"},
        {"name": "contact_phone", "label": "联系电话", "required": False, "type": "phone", "example": "13800138000"},
        {"name": "responsible_unit", "label": "负责单位", "required": False, "type": "str", "example": "某帮扶单位"},
        {"name": "village_name", "label": "关联村庄", "required": False, "type": "str", "example": "某某村"},
        {"name": "organization_code", "label": "组织编码", "required": False, "type": "str", "example": "ORG001"},
    ]

    # ============== 资金导入定义 ==============
    FUND_FIELDS: List[Dict[str, Any]] = [
        {"name": "name", "label": "资金名称", "required": True, "type": "str", "example": "第一季度帮扶资金"},
        {"name": "code", "label": "编号", "required": False, "type": "str", "example": "ZJ-2024-001"},
        {"name": "amount", "label": "金额", "required": True, "type": "float", "example": "100000.00"},
        {"name": "fund_type", "label": "资金类型", "required": False, "type": "fund_type", "example": "project"},
        {"name": "fund_source", "label": "资金来源", "required": False, "type": "fund_source", "example": "military"},
        {"name": "purpose", "label": "用途", "required": False, "type": "str", "example": "用于购买农资"},
        {"name": "status", "label": "状态", "required": False, "type": "fund_status", "example": "pending"},
        {"name": "operator", "label": "经办人", "required": False, "type": "str", "example": "李四"},
        {"name": "project_code", "label": "关联项目编号", "required": False, "type": "str", "example": "XM-2024-001"},
        {"name": "date", "label": "日期", "required": False, "type": "date", "example": "2024-03-15"},
        {"name": "receiver", "label": "接收人", "required": False, "type": "str", "example": "王五"},
        {"name": "remarks", "label": "备注", "required": False, "type": "str", "example": ""},
    ]

    # ============== 学校导入定义 ==============
    SCHOOL_FIELDS: List[Dict[str, Any]] = [
        {"name": "name", "label": "学校名称", "required": True, "type": "str", "example": "某某希望小学"},
        {"name": "code", "label": "学校编码", "required": False, "type": "str", "example": "SCH-001"},
        {"name": "type", "label": "学校类型", "required": False, "type": "school_type", "example": "小学"},
        {"name": "province", "label": "省份", "required": False, "type": "str", "example": "贵州省"},
        {"name": "city", "label": "城市", "required": False, "type": "str", "example": "黔南州"},
        {"name": "district", "label": "区县", "required": False, "type": "county", "example": "都匀市"},
        {"name": "address", "label": "详细地址", "required": False, "type": "str", "example": "某某镇某某路1号"},
        {"name": "principal", "label": "校长姓名", "required": False, "type": "str", "example": "赵六"},
        {"name": "contact_phone", "label": "联系电话", "required": False, "type": "phone", "example": "13900139000"},
        {"name": "student_count", "label": "学生人数", "required": False, "type": "int", "example": "520"},
        {"name": "teacher_count", "label": "教师人数", "required": False, "type": "int", "example": "35"},
        {"name": "support_unit", "label": "帮扶单位", "required": False, "type": "str", "example": "某部队"},
        {
            "name": "support_status",
            "label": "帮扶状态",
            "required": False,
            "type": "support_status",
            "example": "active",
        },
        {"name": "description", "label": "学校简介", "required": False, "type": "str", "example": ""},
    ]

    # ============== 一户一档导入定义 ==============
    HOUSEHOLD_FIELDS: List[Dict[str, Any]] = [
        {"name": "village_name", "label": "帮扶村名称", "required": True, "type": "str", "example": "某某村"},
        {"name": "county", "label": "县/市", "required": False, "type": "str", "example": "某某县"},
        {"name": "township", "label": "乡镇", "required": False, "type": "str", "example": "某某镇"},
        {"name": "household_code", "label": "户编号", "required": False, "type": "str", "example": "H-001"},
        {"name": "household_name", "label": "户主姓名", "required": True, "type": "str", "example": "张三"},
        {"name": "address", "label": "详细地址", "required": False, "type": "str", "example": "某某村1组"},
        {"name": "household_type", "label": "户类型", "required": False, "type": "household_type", "example": "一般户"},
        {"name": "risk_type", "label": "风险类型", "required": False, "type": "risk_type", "example": "无"},
        {"name": "risk_level", "label": "风险等级", "required": False, "type": "risk_level", "example": "低"},
        {"name": "helper_name", "label": "帮扶责任人", "required": False, "type": "str", "example": "李四"},
        {"name": "helper_phone", "label": "联系电话", "required": False, "type": "phone", "example": "13800138000"},
        {"name": "annual_income", "label": "年收入(元)", "required": False, "type": "float", "example": "12000.00"},
        {"name": "migrant_workers", "label": "务工人数", "required": False, "type": "int", "example": "2"},
        {"name": "has_serious_illness", "label": "大病", "required": False, "type": "bool", "example": "否"},
        {"name": "housing_safe", "label": "住房安全", "required": False, "type": "bool", "example": "是"},
        {"name": "last_visit_date", "label": "最近走访日期", "required": False, "type": "date", "example": "2026-10-01"},
        {"name": "monitoring_note", "label": "监测情况说明", "required": False, "type": "str", "example": ""},
    ]

    ENTITY_CONFIGS: Dict[str, Dict[str, Any]] = {
        "project": {
            "fields": PROJECT_FIELDS,
            "required": ["name", "type"],
            "duplicate_key": "name",
            "label": "项目",
        },
        "fund": {
            "fields": FUND_FIELDS,
            "required": ["name", "amount"],
            "duplicate_key": "name",
            "label": "资金",
        },
        "school": {
            "fields": SCHOOL_FIELDS,
            "required": ["name"],
            "duplicate_key": "name",
            "label": "学校",
        },
        "household": {
            "fields": HOUSEHOLD_FIELDS,
            "required": ["village_name", "household_name"],
            "duplicate_key": "household_code",
            "label": "一户一档",
        },
    }

    ENUM_VALUES = {
        "project_type": [
            "infrastructure",
            "education",
            "healthcare",
            "agriculture",
            "industry",
            "other",
            "基础设施",
            "教育",
            "医疗",
            "农业",
            "产业",
            "其他",
        ],
        "project_status": ["draft", "pending", "approved", "in_progress", "completed", "cancelled"],
        "fund_type": ["project", "operation", "education", "infrastructure", "emergency", "other"],
        "fund_source": ["military", "government", "donation", "enterprise", "other"],
        "fund_status": ["pending", "planned", "approved", "allocated", "in_use", "completed", "audited"],
        "school_type": ["primary", "middle", "high", "vocational", "other", "小学", "初中", "高中", "职业学校", "其他"],
        "support_status": ["active", "inactive", "completed", "帮扶中", "未帮扶", "已完成"],
        "household_type": ["general", "poverty", "monitor", "一般户", "脱贫户", "监测户"],
        "risk_type": [
            "none", "income_drop", "illness", "housing", "sudden", "multiple",
            "无", "收入骤减", "因病", "住房", "突发", "多重",
        ],
        "risk_level": ["low", "medium", "high", "低", "中", "高"],
    }

    def __init__(self, entity_type: str = "supported_village"):
        self.entity_type = entity_type
        self.config = self.ENTITY_CONFIGS.get(entity_type, {})

    def get_column_mapping(self) -> Dict[str, str]:
        """Excel列名到字段名的映射。

        R61：追加 `ID` 列（填报导出附带），回导时用于更新既有记录；
        官方模板不含该列，因此不影响原有导入。
        """
        fields = self.config.get("fields", [])
        mapping = {f["label"]: f["name"] for f in fields}
        mapping["ID"] = "id"
        mapping["Id"] = "id"
        return mapping

    def get_required_fields(self) -> List[str]:
        return self.config.get("required", [])

    def parse_excel_headers(self, headers: List[str]) -> Dict[int, str]:
        mapping = self.get_column_mapping()
        result = {}
        for idx, header in enumerate(headers):
            if header:
                clean_header = header.strip().lstrip("*").strip()
                field_name = mapping.get(clean_header)
                if field_name:
                    result[idx] = field_name
        return result

    def validate_file_format(self, filename: str) -> Tuple[bool, Optional[str]]:
        if not filename:
            return False, "文件名不能为空"
        import os

        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"不支持的文件格式: {ext}，仅支持 xlsx 和 xls 格式"
        return True, None

    def validate_file_size(self, file_size: int) -> Tuple[bool, Optional[str]]:
        if file_size > self.MAX_FILE_SIZE:
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"文件大小超过限制，最大允许 {max_mb}MB"
        return True, None

    def validate_row_count(self, row_count: int) -> Tuple[bool, Optional[str]]:
        if row_count > self.MAX_ROWS:
            return False, f"数据行数超过限制，单次最多导入 {self.MAX_ROWS} 条记录，当前 {row_count} 条"
        return True, None

    def _validate_int_field(self, str_value: str) -> None:
        int(str_value)

    def _validate_float_field(
        self, field_name: str, str_value: str, value: Any, label: str, row_number: int
    ) -> Optional[ValidationError]:
        float(str_value)
        if field_name == "amount" and float(str_value) < 0:
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.VALUE_OUT_OF_RANGE,
                message=f"字段 '{label}' 不能为负数",
                value=value,
            )
        return None

    def _validate_bool_field(self, str_value: str) -> None:
        if str_value.lower() not in ("是", "否", "true", "false", "1", "0", "yes", "no"):
            raise ValueError("请填写'是'或'否'")

    def _validate_date_field(self, str_value: str) -> None:
        from datetime import datetime

        datetime.strptime(str_value, "%Y-%m-%d")

    def _validate_phone_field(
        self, field_name: str, str_value: str, value: Any, label: str, row_number: int
    ) -> Optional[ValidationError]:
        import re

        if not re.match(r"^1[3-9]\d{9}$", str_value):
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.INVALID_PHONE,
                message=f"字段 '{label}' 手机号格式不正确",
                value=value,
            )
        return None

    def _validate_county_field(
        self, field_name: str, str_value: str, value: Any, label: str, row_number: int
    ) -> Optional[ValidationError]:
        if str_value and str_value not in QIANNAN_COUNTIES:
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.INVALID_COUNTY,
                message=f"字段 '{label}' 必须是黔南州12个县市之一",
                value=value,
            )
        return None

    def _validate_enum_field(
        self, field_name: str, field_type: str, str_value: str, value: Any, label: str, row_number: int
    ) -> Optional[ValidationError]:
        valid_values = self.ENUM_VALUES[field_type]
        if str_value.lower() not in [v.lower() for v in valid_values]:
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.INVALID_ENUM_VALUE,
                message=f"字段 '{label}' 值无效，可选: {', '.join(valid_values)}",
                value=value,
            )
        return None

    def _validate_field_format(
        self, field_name: str, value: Any, field_type: str, row_number: int
    ) -> Optional[ValidationError]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None

        label = self._get_field_label(field_name)
        str_value = str(value).strip()

        try:
            if field_type == "int":
                self._validate_int_field(str_value)
            elif field_type == "float":
                return self._validate_float_field(field_name, str_value, value, label, row_number)
            elif field_type == "bool":
                self._validate_bool_field(str_value)
            elif field_type == "date":
                self._validate_date_field(str_value)
            elif field_type == "phone":
                return self._validate_phone_field(field_name, str_value, value, label, row_number)
            elif field_type == "county":
                return self._validate_county_field(field_name, str_value, value, label, row_number)
            elif field_type in self.ENUM_VALUES:
                return self._validate_enum_field(field_name, field_type, str_value, value, label, row_number)
            return None
        except (ValueError, TypeError) as e:
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.INVALID_DATA_FORMAT,
                message=f"字段 '{label}' 格式错误: {str(e)}",
                value=value,
            )

    def validate_row(self, row: Dict[str, Any], row_number: int) -> List[ValidationError]:
        errors = []
        required = self.get_required_fields()
        fields_def = {f["name"]: f for f in self.config.get("fields", [])}

        for field_name in required:
            value = row.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(
                    ValidationError(
                        row_number=row_number,
                        field_name=field_name,
                        error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
                        message=f"必填字段 '{self._get_field_label(field_name)}' 不能为空",
                        value=value,
                    )
                )

        for field_name, value in row.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            fdef = fields_def.get(field_name)
            if not fdef:
                continue
            fmt_err = self._validate_field_format(field_name, value, fdef["type"], row_number)
            if fmt_err:
                errors.append(fmt_err)

        return errors

    def validate_batch(self, rows: List[Dict[str, Any]]) -> ValidationResult:
        ok, msg = self.validate_row_count(len(rows))
        if not ok:
            return ValidationResult(
                is_valid=False,
                total_rows=len(rows),
                valid_rows=0,
                errors=[
                    ValidationError(
                        row_number=0,
                        field_name="",
                        error_code=ValidationErrorCode.ROW_LIMIT_EXCEEDED,
                        message=msg or "数据行数超过限制",
                    )
                ],
            )

        all_errors = []
        valid_count = 0
        for idx, row in enumerate(rows, 1):
            errs = self.validate_row(row, idx)
            if errs:
                all_errors.extend(errs)
            else:
                valid_count += 1

        dup_errors = self.check_duplicates(rows)
        if dup_errors:
            all_errors.extend(dup_errors)
            dup_rows = {e.row_number for e in dup_errors}
            valid_count = sum(
                1 for idx, row in enumerate(rows, 1) if idx not in dup_rows and not self.validate_row(row, idx)
            )

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            total_rows=len(rows),
            valid_rows=valid_count,
            errors=all_errors,
            warnings=self._generate_warnings(rows),
        )

    def check_duplicates(self, rows: List[Dict[str, Any]]) -> List[ValidationError]:
        # 一户一档的唯一键是“村 + 户编号”，且跨村同号合法；导入器内部已按
        # (village_id, code/name) 做行级去重/跳过，这里不能再按单列整批判重。
        if self.entity_type == "household":
            return []
        key_field = self.config.get("duplicate_key", "name")
        seen: dict[str, int] = {}
        errors: list[ValidationError] = []
        for idx, row in enumerate(rows, 1):
            key = str(row.get(key_field, "")).strip().lower()
            if not key:
                continue
            if key in seen:
                errors.append(
                    ValidationError(
                        row_number=idx,
                        field_name=key_field,
                        error_code=ValidationErrorCode.DUPLICATE_DATA,
                        message=f"第 {idx} 行与第 {seen[key]} 行 {self._get_field_label(key_field)} 重复",
                        value=key,
                    )
                )
            else:
                seen[key] = idx
        return errors

    def _generate_warnings(self, rows: List[Dict[str, Any]]) -> List[str]:
        warnings = []
        required = set(self.get_required_fields())
        empty_counts: dict[str, int] = {}
        for row in rows:
            for field_name, value in row.items():
                if value is None or (isinstance(value, str) and not value.strip()):
                    empty_counts[field_name] = empty_counts.get(field_name, 0) + 1
        total = len(rows)
        for field_name, count in empty_counts.items():
            if count > total * 0.5 and field_name not in required:
                warnings.append(f"字段 '{self._get_field_label(field_name)}' 有 {count}/{total} 行为空")
        return warnings

    def _get_field_label(self, field_name: str) -> str:
        for f in self.config.get("fields", []):
            if f["name"] == field_name:
                return f["label"]
        return field_name

    def convert_row_types(self, row: Dict[str, Any]) -> Dict[str, Any]:
        converted: dict[str, Any] = {}
        fields_def = {f["name"]: f for f in self.config.get("fields", [])}
        for field_name, value in row.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                converted[field_name] = None
                continue
            ftype = fields_def.get(field_name, {}).get("type", "str")
            sval = str(value).strip()
            try:
                if ftype == "int":
                    converted[field_name] = int(float(sval))
                elif ftype == "float":
                    converted[field_name] = float(sval)
                elif ftype == "bool":
                    converted[field_name] = sval.lower() in ("是", "true", "1", "yes")
                elif ftype == "date":
                    from datetime import datetime

                    converted[field_name] = datetime.strptime(sval, "%Y-%m-%d").date()
                elif ftype in self.ENUM_VALUES:
                    # 将中文映射到英文枚举
                    converted[field_name] = self._normalize_enum(ftype, sval)
                else:
                    converted[field_name] = sval
            except (ValueError, TypeError):
                converted[field_name] = sval
        return converted

    def _normalize_enum(self, enum_type: str, value: str) -> str:
        """将中文/混合输入标准化为英文枚举值"""
        value = str(value).strip().lower()
        mapping = {
            "project_type": {
                "基础设施": "infrastructure",
                "教育": "education",
                "医疗": "healthcare",
                "农业": "agriculture",
                "产业": "industry",
                "其他": "other",
            },
            "school_type": {
                "小学": "primary",
                "初中": "middle",
                "高中": "high",
                "职业学校": "vocational",
                "其他": "other",
            },
            "support_status": {
                "帮扶中": "active",
                "未帮扶": "inactive",
                "已完成": "completed",
            },
            "household_type": {
                "一般户": "general",
                "脱贫户": "poverty",
                "监测户": "monitor",
            },
            "risk_type": {
                "无": "none",
                "收入骤减": "income_drop",
                "因病": "illness",
                "住房": "housing",
                "突发": "sudden",
                "多重": "multiple",
            },
            "risk_level": {
                "低": "low",
                "中": "medium",
                "高": "high",
            },
        }
        if enum_type in mapping and value in mapping[enum_type]:
            return mapping[enum_type][value]
        return value

    def get_field_definitions(self) -> List[Dict[str, Any]]:
        return self.config.get("fields", [])
