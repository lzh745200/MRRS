"""消费帮扶台账 Pydantic 模型（W22 v1.14.0）。

校验口径与既有台账模块（捐赠物资）一致：
- 品类 / 供货方类型枚举在 schema 层 fail-fast（422）；
- 金额、数量非负；年度限定 2000-2100；
- 名称等字符串字段限长，避免超长脏数据落库。
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.consumption import CONSUMPTION_CATEGORIES, SELLER_TYPES


def _check_category(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in CONSUMPTION_CATEGORIES:
        raise ValueError(
            f"品类不合法，可选：{'/'.join(CONSUMPTION_CATEGORIES)}"
        )
    return value


def _check_seller_type(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in SELLER_TYPES:
        raise ValueError(f"供货方类型不合法，可选：{'/'.join(SELLER_TYPES)}")
    return value


class ConsumptionRecordCreate(BaseModel):
    """新建消费帮扶台账记录"""

    supported_village_id: Optional[int] = Field(default=None, ge=1, description="帮扶村ID")
    category: str = Field(default="agriculture", max_length=32, description="品类")
    item_name: str = Field(..., min_length=1, max_length=200, description="产品名称")
    quantity: Optional[float] = Field(default=None, ge=0, description="数量")
    unit: Optional[str] = Field(default=None, max_length=20, description="计量单位")
    amount: float = Field(..., ge=0, description="成交金额（元）")
    buyer: Optional[str] = Field(default=None, max_length=200, description="采购方（单位）")
    seller: Optional[str] = Field(default=None, max_length=200, description="供货方")
    seller_type: Optional[str] = Field(default=None, max_length=20, description="供货方类型")
    year: int = Field(..., ge=2000, le=2100, description="年度")
    record_date: Optional[date] = Field(default=None, description="成交/登记日期")
    voucher_url: Optional[str] = Field(default=None, max_length=500, description="凭证URL")
    remarks: Optional[str] = Field(default=None, max_length=2000, description="备注")

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        return _check_category(value)

    @field_validator("seller_type")
    @classmethod
    def validate_seller_type(cls, value: Optional[str]) -> Optional[str]:
        return _check_seller_type(value)


class ConsumptionRecordUpdate(BaseModel):
    """更新消费帮扶台账记录（部分更新）"""

    supported_village_id: Optional[int] = Field(default=None, ge=1)
    category: Optional[str] = Field(default=None, max_length=32)
    item_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=20)
    amount: Optional[float] = Field(default=None, ge=0)
    buyer: Optional[str] = Field(default=None, max_length=200)
    seller: Optional[str] = Field(default=None, max_length=200)
    seller_type: Optional[str] = Field(default=None, max_length=20)
    year: Optional[int] = Field(default=None, ge=2000, le=2100)
    record_date: Optional[date] = None
    voucher_url: Optional[str] = Field(default=None, max_length=500)
    remarks: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: Optional[str]) -> Optional[str]:
        return _check_category(value)

    @field_validator("seller_type")
    @classmethod
    def validate_seller_type(cls, value: Optional[str]) -> Optional[str]:
        return _check_seller_type(value)
