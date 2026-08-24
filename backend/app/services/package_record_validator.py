"""
上报数据包字段级校验与自动纠正

规则来源（均读自模型真实定义，禁止臆造）：

- 必填字段（从模型列元数据自动派生：nullable=False 且无 default/server_default，
  排除系统列 id/created_at/updated_at/organization_id/org_id/created_by/is_deleted/sync_version）：
  - SupportedVillage.village_name（models/supported_village.py:57，nullable=False 无默认）
  - Project.name（models/project.py:71，nullable=False 无默认）
  - School.name（models/school.py:59，nullable=False 无默认）
  - Fund 无必填业务字段（models/fund.py 业务列均 nullable 或有默认值）
- 电话字段：
  - Project.contact_phone / contact / payer_contact / payee_contact
    （models/project.py:110、:107、:118、:123）
  - School.contact_phone（models/school.py:95）
- 日期字段：按列类型 Date/DateTime 自动派生（排除系统时间戳列）
  - Project: start_date/end_date/actual_start_date/actual_end_date（models/project.py:98-101）
  - Fund: date/application_date/approval_date/allocation_date/start_date/end_date/audit_date
    （models/fund.py:88、:117-128）
  - School: support_start_date/support_end_date（models/school.py:90-91）
- 枚举字段（取值直接读模型内枚举类）：
  - Project.status ← ProjectStatus（models/project.py:25-33）
  - Project.type ← ProjectType（models/project.py:36-44）
  - Project.priority ← 列注释 low/medium/high（models/project.py:104）
  - Fund.status ← FundStatus / fund_type ← FundType / fund_source ← FundSource
    （models/fund.py:49-57、:30-37、:40-46）
  - School.type ← SchoolType / support_status ← SupportStatus（models/school.py:25-40）
  - SupportedVillage.transition_status ← 列注释 none/entering/in_transition/exiting/completed
    （models/supported_village.py:78-81）
- 数值字段：按列类型 Integer/Float/Numeric 自动派生（排除主键/外键/系统列），
  金额/数量类（列名含 amount/budget/cost/count/total/income/investment/progress）拦截负数

自动纠正：字符串 trim、空字符串转 None（可空列）、电话去分隔符、日期归一 ISO、
数字字符串转数；纠正不了的进 rejected 并给中文原因。
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Date, DateTime, Float, Integer, Numeric

from app.core.logging import logger
from app.models.fund import Fund, FundSource, FundStatus, FundType
from app.models.project import Project, ProjectStatus, ProjectType
from app.models.school import School, SchoolType, SupportStatus
from app.models.supported_village import SupportedVillage

# 与 data_package_service.DATA_TYPE_MODELS 保持一致（此处独立定义避免循环导入）
RECORD_MODELS = {
    "villages": SupportedVillage,
    "projects": Project,
    "funds": Fund,
    "schools": School,
}

# 系统列：不参与必填派生/数值派生/日期派生
_SYSTEM_COLUMNS = {
    "id", "created_at", "updated_at", "organization_id", "org_id",
    "created_by", "is_deleted", "sync_version",
}

# 电话字段（按模型实际字段名，见模块 docstring 来源标注）
_PHONE_FIELDS: Dict[str, List[str]] = {
    "projects": ["contact_phone", "contact", "payer_contact", "payee_contact"],
    "schools": ["contact_phone"],
}

# 枚举字段（取值读自模型枚举类；transition_status/priority 读自列注释）
_ENUM_FIELDS: Dict[str, Dict[str, List[str]]] = {
    "projects": {
        "status": [e.value for e in ProjectStatus],
        "type": [e.value for e in ProjectType],
        "priority": ["low", "medium", "high"],
    },
    "funds": {
        "status": [e.value for e in FundStatus],
        "fund_type": [e.value for e in FundType],
        "fund_source": [e.value for e in FundSource],
    },
    "schools": {
        "type": [e.value for e in SchoolType],
        "support_status": [e.value for e in SupportStatus],
    },
    "villages": {
        "transition_status": ["none", "entering", "in_transition", "exiting", "completed"],
    },
}

# 金额/数量类字段名特征（这些数值字段拦截负数；经纬度等不在此列）
_NON_NEGATIVE_HINTS = ("amount", "budget", "cost", "count", "total", "income", "investment", "progress")

# 手机号（11 位，1 开头）与带区号座机（去分隔符后：0 开头区号 + 7-8 位号码）
_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
_LANDLINE_RE = re.compile(r"^0\d{2,3}\d{7,8}$")

_DATE_COMPACT_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")  # YYYYMMDD
_DATE_LOOSE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")  # YYYY-M-D / YYYY/M/D


def _required_fields(model: Any) -> List[str]:
    """从模型列元数据派生必填字段：非 nullable 且无 default/server_default，排除系统列"""
    required = []
    for column in model.__table__.columns:
        if column.name in _SYSTEM_COLUMNS or column.primary_key:
            continue
        if column.nullable:
            continue
        if column.default is not None or column.server_default is not None:
            continue
        required.append(column.name)
    return required


def _date_fields(model: Any) -> List[str]:
    """按列类型派生日期字段（Date/DateTime，排除系统时间戳列）"""
    return [
        c.name
        for c in model.__table__.columns
        if c.name not in _SYSTEM_COLUMNS and isinstance(c.type, (Date, DateTime))
    ]


def _numeric_fields(model: Any) -> Dict[str, Any]:
    """按列类型派生数值字段（排除主键/外键/系统列），返回 {字段名: 列类型}"""
    result = {}
    for c in model.__table__.columns:
        if c.name in _SYSTEM_COLUMNS or c.primary_key or c.foreign_keys:
            continue
        if isinstance(c.type, (Integer, Float, Numeric)):
            result[c.name] = c.type
    return result


def _parse_date_string(value: str) -> Optional[datetime]:
    """解析日期字符串：支持 YYYYMMDD / YYYY-M-D / YYYY/M/D / ISO 格式，失败返回 None"""
    s = value.strip()
    if not s:
        return None
    m = _DATE_COMPACT_RE.match(s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _DATE_LOOSE_RE.match(s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _validate_phone(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """电话校验：去 -/空格后校验 11 位手机号或带区号座机。

    Returns:
        (纠正后的值, 错误原因) —— 合法返回 (值, None)，非法返回 (None, 原因)
    """
    cleaned = re.sub(r"[-\s]", "", str(raw))
    if _MOBILE_RE.match(cleaned) or _LANDLINE_RE.match(cleaned):
        return cleaned, None
    return None, f"电话格式不正确: {raw}（应为 11 位手机号或带区号座机）"


def _validate_numeric(
    name: str, raw: Any, col_type: Any
) -> Tuple[Optional[Any], Optional[str], bool]:
    """数值校验：数字字符串转数值，金额/数量类拦截负数。

    Returns:
        (纠正后的值, 错误原因, 是否发生了纠正)
    """
    if isinstance(raw, bool):
        return None, f"{name} 不是有效数值: {raw}", False
    if isinstance(raw, (int, float)):
        num = raw
        corrected = False
    elif isinstance(raw, str):
        s = raw.strip().replace(",", "")
        try:
            num = float(s) if ("." in s or "e" in s.lower()) else int(s)
        except ValueError:
            return None, f"{name} 不是有效数值: {raw}", False
        corrected = True
    else:
        return None, f"{name} 不是有效数值: {raw}", False

    if num < 0 and any(hint in name for hint in _NON_NEGATIVE_HINTS):
        return None, f"{name} 不允许为负数: {raw}", False

    # Integer 列取整（Float/Numeric 保留原数值）
    if isinstance(col_type, Integer) and isinstance(num, float):
        if not num.is_integer():
            return None, f"{name} 应为整数: {raw}", False
        num = int(num)
        corrected = True
    return num, None, corrected


def validate_records(data_type: str, records: List[Dict]) -> Dict[str, list]:  # noqa: C901
    """对某个数据类型的记录列表做字段级校验与自动纠正。

    Args:
        data_type: 数据类型（villages/projects/funds/schools）
        records: 记录字典列表

    Returns:
        {
            "ok": [...],                                    # 无需纠正直接通过
            "corrected": [{"row": i, "data": {纠正后}, "fixes": [str]}],
            "rejected": [{"row": i, "reasons": [str]}],     # 无法纠正，附中文原因
        }
    """
    result: Dict[str, list] = {"ok": [], "corrected": [], "rejected": []}
    model = RECORD_MODELS.get(data_type)
    if model is None:
        # 未知数据类型：不做字段级校验，原样放行（结构校验已拦截）
        result["ok"] = [r for r in (records or []) if isinstance(r, dict)]
        return result

    required = _required_fields(model)
    date_fields = set(_date_fields(model))
    numeric_fields = _numeric_fields(model)
    phone_fields = _PHONE_FIELDS.get(data_type, [])
    enum_fields = _ENUM_FIELDS.get(data_type, {})
    valid_columns = {c.name for c in model.__table__.columns}
    nullable_map = {c.name: c.nullable for c in model.__table__.columns}

    for i, record in enumerate(records or []):
        if not isinstance(record, dict):
            result["rejected"].append({"row": i, "reasons": ["记录不是有效的数据对象"]})
            continue

        data = dict(record)
        fixes: List[str] = []
        reasons: List[str] = []

        # ── 1. 字符串 trim + 空字符串转 None（可空列）──
        for key in list(data.keys()):
            value = data[key]
            if not isinstance(value, str):
                continue
            trimmed = value.strip()
            if trimmed != value:
                data[key] = trimmed
                fixes.append(f"{key}: 去除首尾空格")
            if trimmed == "" and key in valid_columns and nullable_map.get(key, True):
                data[key] = None
                fixes.append(f"{key}: 空字符串转为空值")

        # ── 2. 必填字段 ──
        for field in required:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                reasons.append(f"缺少必填字段: {field}")

        # ── 3. 电话字段 ──
        for field in phone_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            cleaned, err = _validate_phone(value)
            if err:
                reasons.append(f"{field} {err}")
            elif cleaned != value:
                data[field] = cleaned
                fixes.append(f"{field}: 去除分隔符")

        # ── 4. 日期字段归一 ISO ──
        for field in date_fields:
            value = data.get(field)
            if value is None or isinstance(value, (datetime, date)):
                continue
            if not isinstance(value, str) or not value.strip():
                reasons.append(f"{field} 日期格式无法识别: {value}")
                continue
            parsed = _parse_date_string(value)
            if parsed is None:
                reasons.append(f"{field} 日期格式无法识别: {value}")
                continue
            # 统一为带时间的 ISO 字符串，供导入清洗环节转为 datetime 入库
            normalized = parsed.replace(tzinfo=None).isoformat()
            if isinstance(value, str) and normalized != value:
                data[field] = normalized
                fixes.append(f"{field}: 日期归一为 {parsed.date().isoformat()}")

        # ── 5. 枚举字段 ──
        for field, allowed in enum_fields.items():
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if str(value) not in allowed:
                reasons.append(f"{field} 取值非法: {value}（可选: {', '.join(allowed)}）")

        # ── 6. 数值字段 ──
        for field, col_type in numeric_fields.items():
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            num, err, corrected = _validate_numeric(field, value, col_type)
            if err:
                reasons.append(err)
            elif corrected:
                data[field] = num
                fixes.append(f"{field}: 数字字符串转为数值 {num}")

        if reasons:
            result["rejected"].append({"row": i, "reasons": reasons})
        elif fixes:
            result["corrected"].append({"row": i, "data": data, "fixes": fixes})
        else:
            result["ok"].append(data)

    if result["rejected"] or result["corrected"]:
        logger.info(
            "数据包字段校验: type=%s ok=%d corrected=%d rejected=%d",
            data_type, len(result["ok"]), len(result["corrected"]), len(result["rejected"]),
        )
    return result
