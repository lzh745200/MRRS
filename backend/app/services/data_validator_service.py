"""
数据验证服务
提供Excel导入数据的验证功能

Requirements: 1.2, 1.3, 1.5, 20.1 - 验证文件格式、必填字段、数据格式，返回详细错误信息
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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
    INVALID_NUMERIC_VALUE = "IMPORT_009"
    VALUE_OUT_OF_RANGE = "IMPORT_010"
    # v1.12.9：新增"是否振兴梯队"取值校验所需错误码
    # （历史字符串列 tiered_development_level 已删除，现列为布尔 is_revitalization_tier）
    INVALID_TIERED_LEVEL = "IMPORT_011"


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


class DataValidatorService:
    """数据验证服务"""

    # 支持的文件扩展名
    ALLOWED_EXTENSIONS = {".xlsx", ".xls"}

    # 最大文件大小 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # 最大导入行数
    MAX_ROWS = 1000

    # 必填字段
    REQUIRED_FIELDS = ["department", "support_unit", "village_name"]

    # 字段类型定义
    FIELD_TYPES = {
        "sequence_no": "int",
        "department": "str",
        "support_unit": "str",
        "village_name": "str",
        "province": "str",
        "prefecture": "str",
        "county": "county",  # 特殊类型：黔南州县市验证
        "region_scope": "str",
        "is_three_regions": "bool",
        "is_border_area": "bool",
        "is_ethnic_area": "bool",
        "is_revolutionary_area": "bool",
        "is_key_county": "bool",
        "is_revitalization_tier": "bool",
        "is_provincial_demo": "bool",
        "is_hundred_village_demo": "bool",
        "is_tiered_development": "bool",
        "is_cross_province": "bool",
        "is_cross_city": "bool",
        "is_cross_unit_cooperation": "bool",
        "is_in_overall_plan": "bool",
        "honors": "str",
    }

    # 数值字段范围限制
    NUMERIC_FIELD_RANGES = {
        "sequence_no": (1, 100000),
        "investment": (0, 999999999),  # 投入金额必须为正数
        "planned_investment": (0, 999999999),  # 计划投入必须为正数
        "per_capita_income": (0, 999999),  # 人均收入必须为正数
        "collective_income": (0, 999999999),  # 集体收入必须为正数
    }

    # Excel列名到字段名的映射
    COLUMN_MAPPING = {
        "序号": "sequence_no",
        "各部门各单位": "department",
        "具体帮扶单位": "support_unit",
        "定点帮扶村": "village_name",
        "省份": "province",
        "州 / 市": "prefecture",
        "县 / 市": "county",
        "地区范围": "region_scope",
        "是否属于三区三州": "is_three_regions",
        "是否属于边疆地区": "is_border_area",
        "是否属于民族地区": "is_ethnic_area",
        "是否属于革命地区": "is_revolutionary_area",
        "是否属于160个国家乡村振兴重点帮扶县": "is_key_county",
        "是否振兴梯队": "is_revitalization_tier",
        "省级乡村振兴示范创建对象": "is_provincial_demo",
        "百村示范创建对象": "is_hundred_village_demo",
        "梯次振兴发展对象": "is_tiered_development",
        "是否跨省": "is_cross_province",
        "是否跨市": "is_cross_city",
        "是否跨大单位协作帮扶": "is_cross_unit_cooperation",
        "是否纳入总盘子": "is_in_overall_plan",
        "2021年以来获得的国家或省级表彰": "honors",
    }

    def __init__(self):
        pass

    def validate_file_format(self, filename: str) -> Tuple[bool, Optional[str]]:
        """
        验证文件格式

        Args:
            filename: 文件名

        Returns:
            (是否有效, 错误信息)
        """
        if not filename:
            return False, "文件名不能为空"

        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"不支持的文件格式: {ext}，仅支持 xlsx 和 xls 格式"

        return True, None

    def validate_file_size(self, file_size: int) -> Tuple[bool, Optional[str]]:
        """
        验证文件大小

        Args:
            file_size: 文件大小（字节）

        Returns:
            (是否有效, 错误信息)
        """
        if file_size > self.MAX_FILE_SIZE:
            max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"文件大小超过限制，最大允许 {max_mb}MB"

        return True, None

    def validate_row_count(self, row_count: int) -> Tuple[bool, Optional[str]]:
        """
        验证行数限制

        Args:
            row_count: 数据行数

        Returns:
            (是否有效, 错误信息)
        """
        if row_count > self.MAX_ROWS:
            return (
                False,
                f"数据行数超过限制，单次最多导入 {self.MAX_ROWS} 条记录，当前 {row_count} 条",
            )

        return True, None

    def validate_row(self, row: Dict[str, Any], row_number: int) -> List[ValidationError]:
        """
        验证单行数据

        Args:
            row: 数据行（字段名 -> 值）
            row_number: 行号（从1开始，不含表头）

        Returns:
            错误列表
        """
        errors = []

        # 验证必填字段
        for field_name in self.REQUIRED_FIELDS:
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

        # 验证数据格式
        for field_name, value in row.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                continue

            field_type = self.FIELD_TYPES.get(field_name)
            if not field_type:
                continue

            format_error = self._validate_field_format(field_name, value, field_type, row_number)
            if format_error:
                errors.append(format_error)

        return errors

    def validate_batch(self, rows: List[Dict[str, Any]]) -> ValidationResult:
        """
        批量验证数据

        Args:
            rows: 数据行列表

        Returns:
            验证结果
        """
        # 检查行数限制
        is_valid_count, count_error = self.validate_row_count(len(rows))
        if not is_valid_count:
            return ValidationResult(
                is_valid=False,
                total_rows=len(rows),
                valid_rows=0,
                errors=[
                    ValidationError(
                        row_number=0,
                        field_name="",
                        error_code=ValidationErrorCode.ROW_LIMIT_EXCEEDED,
                        message=count_error or "数据行数超过限制",
                    )
                ],
            )

        all_errors = []
        valid_count = 0

        for idx, row in enumerate(rows, 1):
            row_errors = self.validate_row(row, idx)
            if row_errors:
                all_errors.extend(row_errors)
            else:
                valid_count += 1

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            total_rows=len(rows),
            valid_rows=valid_count,
            errors=all_errors,
        )

    def check_duplicates(
        self, rows: List[Dict[str, Any]], key_fields: Optional[List[str]] = None
    ) -> List[ValidationError]:
        """
        检查重复数据

        Args:
            rows: 数据行列表
            key_fields: 用于判断重复的字段列表，默认使用 village_name

        Returns:
            重复错误列表
        """
        if key_fields is None:
            key_fields = ["village_name"]

        seen: dict[tuple, int] = {}
        errors: list[ValidationError] = []

        for idx, row in enumerate(rows, 1):
            key = tuple(str(row.get(f, "")).strip().lower() for f in key_fields)

            if key in seen:
                errors.append(
                    ValidationError(
                        row_number=idx,
                        field_name=", ".join(key_fields),
                        error_code=ValidationErrorCode.DUPLICATE_DATA,
                        message=f"第 {idx} 行与第 {seen[key]} 行数据重复",
                        value=str(key),
                    )
                )
            else:
                seen[key] = idx

        return errors

    def parse_excel_headers(self, headers: List[str]) -> Dict[int, str]:
        """
        解析Excel表头，返回列索引到字段名的映射

        Args:
            headers: 表头列表

        Returns:
            列索引 -> 字段名 的映射
        """
        mapping = {}
        for idx, header in enumerate(headers):
            if header:  # 移除可能的必填标记 *
                clean_header = header.strip().lstrip("*").strip()
                field_name = self.COLUMN_MAPPING.get(clean_header)
                if field_name:
                    mapping[idx] = field_name
        return mapping

    def _validate_int_field(
        self, field_name: str, value: Any, row_number: int
    ) -> Optional[ValidationError]:
        if isinstance(value, str):
            parsed_value = int(value.strip())
        elif isinstance(value, (int, float)):
            parsed_value = int(value)
        else:
            raise ValueError("不是有效的整数")

        if field_name in self.NUMERIC_FIELD_RANGES:
            min_val, max_val = self.NUMERIC_FIELD_RANGES[field_name]
            if parsed_value < min_val or parsed_value > max_val:
                return ValidationError(
                    row_number=row_number,
                    field_name=field_name,
                    error_code=ValidationErrorCode.VALUE_OUT_OF_RANGE,
                    message=f"字段 '{self._get_field_label(field_name)}' 值超出范围，应在 {min_val} 到 {max_val} 之间",
                    value=value,
                )
        return None

    def _validate_float_field(self, value: Any) -> None:
        if isinstance(value, str):
            float(value.strip())
        elif not isinstance(value, (int, float)):
            raise ValueError("不是有效的数字")

    def _validate_bool_field(self, value: Any) -> None:
        if isinstance(value, str):
            if value.strip().lower() not in (
                "是", "否", "true", "false", "1", "0", "yes", "no",
            ):
                raise ValueError("请填写'是'或'否'")
        elif not isinstance(value, bool):
            raise ValueError("不是有效的布尔值")

    def _validate_county_field(
        self, field_name: str, value: Any, row_number: int
    ) -> Optional[ValidationError]:
        str_value = str(value).strip() if value else ""
        if str_value and str_value not in QIANNAN_COUNTIES:
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.INVALID_COUNTY,
                message=(
                    f"字段 '{self._get_field_label(field_name)}' 值无效，"
                    f"必须是黔南州12个县市之一: {', '.join(QIANNAN_COUNTIES)}"
                ),
                value=value,
            )
        return None

    def _validate_field_format(
        self, field_name: str, value: Any, field_type: str, row_number: int
    ) -> Optional[ValidationError]:
        """验证字段格式"""
        try:
            if field_type == "int":
                return self._validate_int_field(field_name, value, row_number)
            if field_type == "float":
                self._validate_float_field(value)
                return None
            if field_type == "bool":
                self._validate_bool_field(value)
                return None
            if field_type == "county":
                return self._validate_county_field(field_name, value, row_number)
            return None
        except (ValueError, TypeError) as e:
            return ValidationError(
                row_number=row_number,
                field_name=field_name,
                error_code=ValidationErrorCode.INVALID_DATA_FORMAT,
                message=f"字段 '{self._get_field_label(field_name)}' 格式错误: {str(e)}",
                value=value,
            )

    def _get_field_label(self, field_name: str) -> str:
        """获取字段的中文标签"""
        for label, name in self.COLUMN_MAPPING.items():
            if name == field_name:
                return label
        return field_name

    def convert_bool_value(self, value: Any) -> Optional[bool]:
        """
        转换布尔值

        Args:
            value: 原始值

        Returns:
            布尔值或None
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value = value.strip().lower()
            if value in ("是", "true", "1", "yes"):
                return True
            elif value in ("否", "false", "0", "no"):
                return False

        return None

    def convert_row_types(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换行数据类型

        Args:
            row: 原始数据行

        Returns:
            类型转换后的数据行
        """
        converted: dict[str, Any] = {}

        for field_name, value in row.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                converted[field_name] = None
                continue

            field_type = self.FIELD_TYPES.get(field_name, "str")

            if field_type == "int":
                try:
                    converted[field_name] = int(float(str(value).strip()))
                except (ValueError, TypeError):
                    converted[field_name] = None

            elif field_type == "float":
                try:
                    converted[field_name] = float(str(value).strip())
                except (ValueError, TypeError):
                    converted[field_name] = None

            elif field_type == "bool":
                converted[field_name] = self.convert_bool_value(value)

            elif field_type == "county":
                # 保持字符串值，验证在validate_row中进行
                converted[field_name] = str(value).strip() if value else None

            else:
                converted[field_name] = str(value).strip() if value else None

        return converted

    # 振兴梯队字段的合法取值（模型列已从历史字符串收窄为布尔 is_revitalization_tier）
    _TIER_TRUE = {"是", "true", "True", "1", "yes", "Y"}
    _TIER_FALSE = {"否", "false", "False", "0", "no", "N", ""}

    def validate_import_data(
        self,
        rows: List[Dict[str, Any]],
        validate_county: bool = True,
        validate_tiered_level: bool = True,
    ) -> ValidationResult:
        """
        验证导入数据（增强版）

        提供完整的数据验证，包括：
        - 文件行数限制检查
        - 必填字段验证
        - 数据格式验证
        - 县 / 市范围验证（黔南州12个县市）
        - 重复数据检查

        Args:
            rows: 数据行列表
            validate_county: 是否验证县 / 市字段

        Returns:
            ValidationResult: 包含详细错误信息的验证结果

        Requirements: 20.1 - 数据导入功能验证
        """
        # 检查行数限制
        is_valid_count, count_error = self.validate_row_count(len(rows))
        if not is_valid_count:
            return ValidationResult(
                is_valid=False,
                total_rows=len(rows),
                valid_rows=0,
                errors=[
                    ValidationError(
                        row_number=0,
                        field_name="",
                        error_code=ValidationErrorCode.ROW_LIMIT_EXCEEDED,
                        message=count_error or "数据行数超过限制",
                    )
                ],
            )

        all_errors = []
        valid_count = 0

        for idx, row in enumerate(rows, 1):
            row_errors = self.validate_row(row, idx)

            # 额外验证县 / 市字段
            if validate_county:
                county_value = row.get("county")
                if county_value and str(county_value).strip():
                    county_error = self._validate_field_format("county", county_value, "county", idx)
                    if county_error:
                        row_errors.append(county_error)

            # 额外验证"是否振兴梯队"（历史 tiered_development_level 字符串列已删除，
            # 现列为布尔 is_revitalization_tier；此处只接受真/假口径的取值）
            if validate_tiered_level:
                tier_value = row.get("is_revitalization_tier")
                if tier_value is not None:
                    tier_text = str(tier_value).strip()
                    if tier_text not in self._TIER_TRUE and tier_text not in self._TIER_FALSE:
                        row_errors.append(
                            ValidationError(
                                row_number=idx,
                                field_name="is_revitalization_tier",
                                error_code=ValidationErrorCode.INVALID_TIERED_LEVEL,
                                message=(
                                    f"第 {idx} 行 是否振兴梯队 取值非法: {tier_text}"
                                    "（仅支持 是/否）"
                                ),
                            )
                        )

            if row_errors:
                all_errors.extend(row_errors)
            else:
                valid_count += 1

        # 检查重复数据
        duplicate_errors = self.check_duplicates(rows)
        if duplicate_errors:
            all_errors.extend(duplicate_errors)
            # 重新计算有效行数（排除重复行）
            duplicate_rows = {e.row_number for e in duplicate_errors}
            valid_count = sum(
                1 for idx, row in enumerate(rows, 1) if idx not in duplicate_rows and not self.validate_row(row, idx)
            )

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            total_rows=len(rows),
            valid_rows=valid_count,
            errors=all_errors,
            warnings=self._generate_warnings(rows),
        )

    def _generate_warnings(self, rows: List[Dict[str, Any]]) -> List[str]:
        """
        生成数据质量警告

        Args:
            rows: 数据行列表

        Returns:
            警告信息列表
        """
        warnings = []

        # 检查是否有大量空字段
        empty_field_counts: dict[str, int] = {}
        for row in rows:
            for field_name, value in row.items():
                if value is None or (isinstance(value, str) and not value.strip()):
                    empty_field_counts[field_name] = empty_field_counts.get(field_name, 0) + 1

        total_rows = len(rows)
        for field_name, count in empty_field_counts.items():
            if count > total_rows * 0.5 and field_name not in self.REQUIRED_FIELDS:
                label = self._get_field_label(field_name)
                warnings.append(f"字段 '{label}' 有 {count}/{total_rows} 行为空")

        # 检查是否有重复的村庄名称
        village_names = [row.get("village_name", "") for row in rows if row.get("village_name")]
        unique_names = set(village_names)
        if len(village_names) != len(unique_names):
            duplicate_count = len(village_names) - len(unique_names)
            warnings.append(f"发现 {duplicate_count} 个重复的村庄名称")

        return warnings

    def get_validation_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """
        获取验证结果摘要

        Args:
            result: 验证结果

        Returns:
            验证摘要字典
        """
        # 按错误类型分组
        error_by_type: dict[str, list] = {}
        for error in result.errors:
            error_type = (
                error.error_code.value if isinstance(error.error_code, ValidationErrorCode) else error.error_code
            )
            if error_type not in error_by_type:
                error_by_type[error_type] = []
            error_by_type[error_type].append(error)

        # 按字段分组
        error_by_field: dict[str, list] = {}
        for error in result.errors:
            if error.field_name:
                if error.field_name not in error_by_field:
                    error_by_field[error.field_name] = []
                error_by_field[error.field_name].append(error)

        return {
            "is_valid": result.is_valid,
            "total_rows": result.total_rows,
            "valid_rows": result.valid_rows,
            "invalid_rows": result.total_rows - result.valid_rows,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "errors_by_type": {k: len(v) for k, v in error_by_type.items()},
            "errors_by_field": {self._get_field_label(k): len(v) for k, v in error_by_field.items()},
            "warnings": result.warnings,
            "first_errors": [e.to_dict() for e in result.errors[:10]],  # 只返回前10个错误
        }


# ============================================================================
# DataValidator - 通用数据验证器
# Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
# ============================================================================


@dataclass
class SimpleValidationResult:
    """简单验证结果 - 用于单字段验证"""

    is_valid: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    field_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "field_name": self.field_name,
        }


class DataValidator:
    """
    通用数据验证器

    提供身份证号、日期格式、必填字段、字段长度验证和输入清理功能。
    所有验证方法都保证：无效输入被拒绝时，现有有效数据保持不变。

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
    """

    # 中国身份证号正则表达式（18位）
    ID_NUMBER_PATTERN = r"^[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$"

    # 身份证号校验码权重
    ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    ID_CHECK_CODES = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]

    # 已知的身份证号集合（用于重复检查）
    _known_id_numbers: set = field(default_factory=set) if "field" in dir() else set()

    def __init__(self, known_id_numbers: Optional[set] = None):
        """
        初始化验证器

        Args:
            known_id_numbers: 已知的身份证号集合，用于重复检查
        """
        import re

        self._id_pattern = re.compile(self.ID_NUMBER_PATTERN)
        self._known_id_numbers = known_id_numbers or set()

    def validate_id_number(self, id_number: str, check_duplicate: bool = True) -> SimpleValidationResult:
        """
        验证身份证号（检查重复和格式）

        验证规则：
        1. 必须是18位
        2. 前17位必须是数字
        3. 最后一位可以是数字或X
        4. 校验码必须正确
        5. 可选检查是否重复

        Args:
            id_number: 身份证号
            check_duplicate: 是否检查重复

        Returns:
            SimpleValidationResult: 验证结果

        Requirements: 4.1 - 重复ID号检测和格式验证
        """
        if not id_number:
            return SimpleValidationResult(
                is_valid=False,
                error_code="ID_EMPTY",
                error_message="身份证号不能为空",
                field_name="id_number",
            )

        # 清理输入
        id_number = str(id_number).strip().upper()

        # 检查长度
        if len(id_number) != 18:
            return SimpleValidationResult(
                is_valid=False,
                error_code="ID_LENGTH_INVALID",
                error_message=f"身份证号必须是18位，当前为{len(id_number)}位",
                field_name="id_number",
            )

        # 检查格式
        if not self._id_pattern.match(id_number):
            return SimpleValidationResult(
                is_valid=False,
                error_code="ID_FORMAT_INVALID",
                error_message="身份证号格式不正确",
                field_name="id_number",
            )

        # 验证校验码
        if not self._verify_id_checksum(id_number):
            return SimpleValidationResult(
                is_valid=False,
                error_code="ID_CHECKSUM_INVALID",
                error_message="身份证号校验码不正确",
                field_name="id_number",
            )

        # 检查重复
        if check_duplicate and id_number in self._known_id_numbers:
            return SimpleValidationResult(
                is_valid=False,
                error_code="ID_DUPLICATE",
                error_message="身份证号已存在，不能重复提交",
                field_name="id_number",
            )

        return SimpleValidationResult(is_valid=True)

    def _verify_id_checksum(self, id_number: str) -> bool:
        """验证身份证校验码"""
        try:
            # 计算前17位的加权和
            total = sum(int(id_number[i]) * self.ID_WEIGHTS[i] for i in range(17))
            # 计算校验码
            expected_check = self.ID_CHECK_CODES[total % 11]
            return id_number[17].upper() == expected_check
        except (ValueError, IndexError):
            return False

    def add_known_id_number(self, id_number: str) -> None:
        """添加已知身份证号到集合中"""
        if id_number:
            self._known_id_numbers.add(str(id_number).strip().upper())

    def validate_date_format(self, date_str: str, expected_format: str = "YYYY-MM-DD") -> SimpleValidationResult:
        """
        验证日期格式

        支持的格式：
        - YYYY-MM-DD (如 2024-01-15)
        - YYYY/MM/DD (如 2024/01/15)
        - YYYYMMDD (如 20240115)
        - DD-MM-YYYY (如 15-01-2024)
        - MM/DD/YYYY (如 01/15/2024)

        Args:
            date_str: 日期字符串
            expected_format: 期望的日期格式

        Returns:
            SimpleValidationResult: 验证结果

        Requirements: 4.2 - 日期格式验证
        """
        from datetime import datetime

        if not date_str:
            return SimpleValidationResult(
                is_valid=False,
                error_code="DATE_EMPTY",
                error_message="日期不能为空",
                field_name="date",
            )

        date_str = str(date_str).strip()

        # 格式映射
        format_mapping = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "YYYY/MM/DD": "%Y/%m/%d",
            "YYYYMMDD": "%Y%m%d",
            "DD-MM-YYYY": "%d-%m-%Y",
            "MM/DD/YYYY": "%m/%d/%Y",
            "YYYY年MM月DD日": "%Y年%m月%d日",
        }

        python_format = format_mapping.get(expected_format)
        if not python_format:
            return SimpleValidationResult(
                is_valid=False,
                error_code="DATE_FORMAT_UNSUPPORTED",
                error_message=f"不支持的日期格式: {expected_format}",
                field_name="date",
            )

        try:
            parsed_date = datetime.strptime(date_str, python_format)
            # 验证日期是否合理（不能是未来太远或过去太远）
            min_date = datetime(1900, 1, 1)
            max_date = datetime(2100, 12, 31)
            if parsed_date < min_date or parsed_date > max_date:
                return SimpleValidationResult(
                    is_valid=False,
                    error_code="DATE_OUT_OF_RANGE",
                    error_message="日期超出有效范围 (1900-2100)",
                    field_name="date",
                )
            return SimpleValidationResult(is_valid=True)
        except ValueError:
            return SimpleValidationResult(
                is_valid=False,
                error_code="DATE_FORMAT_INVALID",
                error_message=f"日期格式不正确，期望格式: {expected_format}",
                field_name="date",
            )

    def validate_required_fields(self, data: Dict[str, Any], required: List[str]) -> SimpleValidationResult:
        """
        验证必填字段

        检查数据字典中是否包含所有必填字段，且字段值不为空。

        Args:
            data: 数据字典
            required: 必填字段列表

        Returns:
            SimpleValidationResult: 验证结果，如果有缺失字段，error_message包含所有缺失字段名

        Requirements: 4.3 - 必填字段验证
        """
        if not data:
            return SimpleValidationResult(
                is_valid=False,
                error_code="DATA_EMPTY",
                error_message="数据不能为空",
                field_name=None,
            )

        if not required:
            return SimpleValidationResult(is_valid=True)

        missing_fields = []
        empty_fields = []

        for field_name in required:
            if field_name not in data:
                missing_fields.append(field_name)
            elif data[field_name] is None:
                empty_fields.append(field_name)
            elif isinstance(data[field_name], str) and not data[field_name].strip():
                empty_fields.append(field_name)

        all_invalid_fields = missing_fields + empty_fields

        if all_invalid_fields:
            return SimpleValidationResult(
                is_valid=False,
                error_code="REQUIRED_FIELDS_MISSING",
                error_message=f"以下必填字段缺失或为空: {', '.join(all_invalid_fields)}",
                field_name=", ".join(all_invalid_fields),
            )

        return SimpleValidationResult(is_valid=True)

    def validate_field_length(
        self,
        value: str,
        max_length: int,
        field_name: Optional[str] = None,
        min_length: int = 0,
    ) -> SimpleValidationResult:
        """
        验证字段长度

        Args:
            value: 字段值
            max_length: 最大长度
            field_name: 字段名（用于错误消息）
            min_length: 最小长度（默认0）

        Returns:
            SimpleValidationResult: 验证结果

        Requirements: 4.4 - 字段长度验证
        """
        if value is None:
            value = ""

        value_str = str(value)
        actual_length = len(value_str)

        if actual_length > max_length:
            return SimpleValidationResult(
                is_valid=False,
                error_code="FIELD_TOO_LONG",
                error_message=f"字段长度超过限制，最大允许{max_length}个字符，当前为{actual_length}个字符",
                field_name=field_name,
            )

        if actual_length < min_length:
            return SimpleValidationResult(
                is_valid=False,
                error_code="FIELD_TOO_SHORT",
                error_message=f"字段长度不足，最少需要{min_length}个字符，当前为{actual_length}个字符",
                field_name=field_name,
            )

        return SimpleValidationResult(is_valid=True)

    def sanitize_input(
        self,
        value: str,
        allowed_chars: Optional[str] = None,
        remove_html: bool = True,
        remove_sql_injection: bool = True,
    ) -> str:
        """
        清理输入中的特殊字符

        默认行为：
        1. 移除HTML标签
        2. 移除SQL注入风险字符
        3. 如果指定allowed_chars，只保留允许的字符

        Args:
            value: 输入值
            allowed_chars: 允许的字符集（正则表达式字符类格式，如 "a-zA-Z0-9"）
            remove_html: 是否移除HTML标签
            remove_sql_injection: 是否移除SQL注入风险字符

        Returns:
            str: 清理后的字符串

        Requirements: 4.5 - 特殊字符处理
        """
        import html
        import re

        if value is None:
            return ""

        result = str(value)

        # 移除HTML标签
        if remove_html:
            # 先解码HTML实体
            result = html.unescape(result)
            # 移除HTML标签
            result = re.sub(r"<[^>]+>", "", result)

        # 移除SQL注入风险字符
        if remove_sql_injection:
            # 移除SQL关键字 - 不使用词边界以确保完全移除
            sql_keywords = [
                "UNION",
                "SELECT",
                "DROP",
                "DELETE",
                "INSERT",
                "UPDATE",
                "OR",
                "AND",
            ]
            for keyword in sql_keywords:
                result = re.sub(keyword, "", result, flags=re.IGNORECASE)
            # 移除特殊SQL字符
            special_chars = [
                r"'",  # 单引号
                r'"',  # 双引号
                r";",  # 分号
                r"--",  # SQL注释
                r"/\*",  # 多行注释开始
                r"\*/",  # 多行注释结束
            ]
            for pattern in special_chars:
                result = re.sub(pattern, "", result)

        # 如果指定了允许的字符，只保留这些字符
        if allowed_chars:
            pattern = f"[^{allowed_chars}]"
            result = re.sub(pattern, "", result)

        # 移除多余的空白字符
        result = " ".join(result.split())

        return result.strip()

    def validate_and_sanitize(
        self,
        value: str,
        max_length: int,
        allowed_chars: Optional[str] = None,
        field_name: Optional[str] = None,
    ) -> Tuple[str, SimpleValidationResult]:
        """
        验证并清理输入

        组合验证和清理功能，返回清理后的值和验证结果。

        Args:
            value: 输入值
            max_length: 最大长度
            allowed_chars: 允许的字符集
            field_name: 字段名

        Returns:
            Tuple[str, SimpleValidationResult]: (清理后的值, 验证结果)
        """
        # 先清理
        sanitized = self.sanitize_input(value, allowed_chars)

        # 再验证长度
        result = self.validate_field_length(sanitized, max_length, field_name)

        return sanitized, result

    def validate_email(self, email: str) -> SimpleValidationResult:
        """
        验证邮箱格式

        Args:
            email: 邮箱地址

        Returns:
            SimpleValidationResult: 验证结果
        """
        import re

        if not email:
            return SimpleValidationResult(
                is_valid=False,
                error_code="EMAIL_EMPTY",
                error_message="邮箱地址不能为空",
                field_name="email",
            )

        email = str(email).strip()

        # 简单的邮箱正则表达式
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return SimpleValidationResult(
                is_valid=False,
                error_code="EMAIL_FORMAT_INVALID",
                error_message="邮箱格式不正确",
                field_name="email",
            )

        return SimpleValidationResult(is_valid=True)

    def validate_phone(self, phone: str) -> SimpleValidationResult:
        """
        验证手机号格式（中国大陆）

        Args:
            phone: 手机号

        Returns:
            SimpleValidationResult: 验证结果
        """
        import re

        if not phone:
            return SimpleValidationResult(
                is_valid=False,
                error_code="PHONE_EMPTY",
                error_message="手机号不能为空",
                field_name="phone",
            )

        phone = str(phone).strip()

        # 中国大陆手机号正则表达式
        phone_pattern = r"^1[3-9]\d{9}$"
        if not re.match(phone_pattern, phone):
            return SimpleValidationResult(
                is_valid=False,
                error_code="PHONE_FORMAT_INVALID",
                error_message="手机号格式不正确，应为11位数字且以1开头",
                field_name="phone",
            )

        return SimpleValidationResult(is_valid=True)
