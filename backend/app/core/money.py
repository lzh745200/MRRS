"""金额字段入口量化（4 位小数，ROUND_HALF_UP）。

用法（替代裸 float 声明）::

    from app.core.money import MoneyField

    class FundCreate(BaseModel):
        amount: MoneyField = 0

Pydantic v2 在模型验证阶段完成量化；字段本身仍是 float（JSON 序列化兼容，
**不是** Decimal 全链路 —— 服务层/DB 列仍按 float/Numeric 处理）。
非法输入（NaN/Inf/超出可量化精度）一律转成 ValueError，由 Pydantic 归一为
422 校验失败，绝不冒泡成 500。
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated, Any

from pydantic import AfterValidator

MONEY_PLACES = Decimal("0.0001")


def _quantize_4(v: Any) -> Decimal:
    """量化为 4 位小数，ROUND_HALF_UP。

    Raises:
        ValueError: 输入无法解析为数值、非有限值（NaN/Inf），或数值超出
            可量化范围（quantize 抛 InvalidOperation —— ArithmeticError，
            Pydantic 不会把它转成 422，会直接 500，必须在此归一，深审 #15）。
    """
    if v is None:
        return Decimal("0")
    try:
        d = Decimal(str(v)) if not isinstance(v, Decimal) else v
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"金额格式非法: {v!r}") from exc
    if not d.is_finite():
        raise ValueError(f"金额必须为有限数值（不接受 NaN/Inf）: {v!r}")
    try:
        return d.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"金额超出可量化范围: {v!r}") from exc


MoneyField = Annotated[float, AfterValidator(lambda v: float(_quantize_4(v)))]
"""4 位小数金额字段：入口量化，序列化仍为 float 保持 JSON 兼容。"""
