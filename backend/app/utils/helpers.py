"""Common helper functions."""

import hashlib
import json
import secrets
import string
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional


def generate_random_string(length: int = 16) -> str:
    """Generate a random string."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_code(prefix: str, id_value: int) -> str:
    """Generate a code with prefix and zero-padded ID."""
    year = datetime.now().year
    return f"{prefix}{year}{str(id_value).zfill(4)}"


def hash_string(value: str) -> str:
    """Hash a string using SHA256."""
    return hashlib.sha256(value.encode()).hexdigest()


def safe_json_loads(value: Optional[str], default: Any = None) -> Any:
    """Safely load JSON string.

    Supports:
    - JSON arrays: ["a", "b"]
    - JSON objects: {"a": 1}
    - Comma-separated strings: "a,b,c"
    """
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        # Fallback: try comma-separated format
        if isinstance(value, str) and "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return default


def safe_json_dumps(value: Any) -> str:
    """Safely dump to JSON string."""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return "{}"


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string."""
    if not dt:
        return ""
    return dt.strftime(fmt)


def format_date(d: Optional[date], fmt: str = "%Y-%m-%d") -> str:
    """Format date to string."""
    if not d:
        return ""
    return d.strftime(fmt)


def parse_datetime(value: Optional[str], fmt: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """Parse string to datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def parse_date(value: Optional[str], fmt: str = "%Y-%m-%d") -> Optional[date]:
    """Parse string to date."""
    if not value:
        return None
    try:
        return datetime.strptime(value, fmt).date()
    except ValueError:
        return None


def paginate(items: List[Any], page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """Paginate a list of items."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


def clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Remove None values from dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def deep_merge(base: Dict, update: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# 金额统一保留4位小数（四舍五入），全系统金额字段口径
MONEY_PLACES = Decimal("0.0001")

# Fund 模型的金额字段（万元）
FUND_MONEY_FIELDS = frozenset({
    "amount", "planned_amount", "approved_amount",
    "allocated_amount", "used_amount", "remaining_amount",
})

# FundBudget / BudgetRecord 的金额字段（万元）
BUDGET_MONEY_FIELDS = frozenset({"budget_amount", "executed_amount", "used_amount"})


def quantize_money(value: Any) -> Decimal:
    """将金额量化为4位小数（ROUND_HALF_UP 四舍五入）。

    None/非法输入返回 Decimal("0")，便于直接用于列默认值。
    """
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value)).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0")


def quantize_money_fields(payload: Dict[str, Any], fields: Any = FUND_MONEY_FIELDS) -> Dict[str, Any]:
    """就地量化字典中指定的金额字段（值为 None 时跳过）。"""
    for key in fields:
        if key in payload and payload[key] is not None:
            payload[key] = quantize_money(payload[key])
    return payload
