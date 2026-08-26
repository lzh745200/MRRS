"""金额字段 Pydantic 全链路量化 (Phase: Decimal 化)。

用法（替代裸 float 声明）::

    from app.core.money import MoneyField

    class FundCreate(BaseModel):
        amount: MoneyField = 0

Pydantic v2 在模型验证阶段自动将输入量化为 4 位小数（ROUND_HALF_UP），
后续服务层拿到的已是干净值，无需二次处理。
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Any

from pydantic import AfterValidator

MONEY_PLACES = Decimal("0.0001")


def _quantize_4(v: Any) -> Decimal:
    """量化为 4 位小数，ROUND_HALF_UP。"""
    if v is None:
        return Decimal("0")
    d = Decimal(str(v)) if not isinstance(v, Decimal) else v
    return d.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


MoneyField = Annotated[float, AfterValidator(lambda v: float(_quantize_4(v)))]
"""4 位小数金额字段：入口量化，序列化仍为 float 保持 JSON 兼容。"""
