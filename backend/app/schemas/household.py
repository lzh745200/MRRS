"""一户一档 Pydantic 模型（W22 契约 §1 / §2）。

- 创建/更新入参校验：户主与成员姓名必填、金额 >= 0、枚举值白名单、
  手机号格式可选（空串归一为 None，非法手机号 422）；
- 响应模型：供 API 层把 ORM ``to_dict()`` 结果二次校验/序列化，
  保证出站字段形状稳定（金额 float、时间 ISO、PII 字段原样经 ORM 解密）。
"""

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# 中国大陆手机号（帮扶责任人联系电话为可选字段，空串视为未填写）
_MOBILE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

HouseholdType = Literal["general", "poverty", "monitor"]
RiskType = Literal["none", "income_drop", "illness", "housing", "sudden", "multiple"]
RiskLevel = Literal["low", "medium", "high"]


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    """手机号校验：None/空串 → None；格式不合法 → ValueError（422）。"""
    if value is None or value == "":
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if not _MOBILE_PATTERN.match(candidate):
        raise ValueError("手机号格式不正确（应为 11 位大陆手机号）")
    return candidate


class HouseholdCreate(BaseModel):
    """新建一户一档入参。"""

    supported_village_id: int = Field(..., gt=0, description="所属帮扶村ID")
    household_code: Optional[str] = Field(default=None, max_length=64, description="户编号（村内唯一）")
    household_name: str = Field(..., min_length=1, max_length=64, description="户主姓名")
    address: Optional[str] = Field(default=None, max_length=255)
    household_type: HouseholdType = "general"
    risk_type: RiskType = "none"
    risk_level: RiskLevel = "low"
    helper_name: Optional[str] = Field(default=None, max_length=64)
    helper_phone: Optional[str] = Field(default=None, description="帮扶责任人手机号（PII）")
    annual_income: Optional[float] = Field(default=None, ge=0, description="户年收入(元)")
    migrant_workers: Optional[int] = Field(default=None, ge=0, description="务工人数")
    has_serious_illness: bool = False
    housing_safe: bool = True
    last_visit_date: Optional[date] = None
    monitoring_note: Optional[str] = None

    @field_validator("helper_phone")
    @classmethod
    def _check_phone(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_phone(value)


class HouseholdUpdate(BaseModel):
    """更新一户一档入参（部分更新，仅传需要变更的字段）。"""

    supported_village_id: Optional[int] = Field(default=None, gt=0)
    household_code: Optional[str] = Field(default=None, max_length=64)
    household_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    address: Optional[str] = Field(default=None, max_length=255)
    household_type: Optional[HouseholdType] = None
    risk_type: Optional[RiskType] = None
    risk_level: Optional[RiskLevel] = None
    helper_name: Optional[str] = Field(default=None, max_length=64)
    helper_phone: Optional[str] = None
    annual_income: Optional[float] = Field(default=None, ge=0)
    migrant_workers: Optional[int] = Field(default=None, ge=0)
    has_serious_illness: Optional[bool] = None
    housing_safe: Optional[bool] = None
    last_visit_date: Optional[date] = None
    monitoring_note: Optional[str] = None

    @field_validator("helper_phone")
    @classmethod
    def _check_phone(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_phone(value)


class HouseholdMemberCreate(BaseModel):
    """新增家庭成员入参。"""

    name: str = Field(..., min_length=1, max_length=64, description="成员姓名")
    relation: Optional[str] = Field(default=None, max_length=32)
    id_card: Optional[str] = Field(default=None, max_length=64, description="身份证号（PII）")
    gender: Optional[str] = Field(default=None, max_length=10)
    birth_year: Optional[int] = Field(default=None, ge=1800, le=2200)
    education: Optional[str] = Field(default=None, max_length=32)
    health_status: Optional[str] = Field(default=None, max_length=32)
    employment_status: Optional[str] = Field(default=None, max_length=32)
    income: Optional[float] = Field(default=None, ge=0, description="个人年收入(元)")
    is_special_support: bool = False
    remarks: Optional[str] = Field(default=None, max_length=500, description="备注")


class HouseholdMemberUpdate(BaseModel):
    """更新家庭成员入参（部分更新）。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    relation: Optional[str] = Field(default=None, max_length=32)
    id_card: Optional[str] = Field(default=None, max_length=64)
    gender: Optional[str] = Field(default=None, max_length=10)
    birth_year: Optional[int] = Field(default=None, ge=1800, le=2200)
    education: Optional[str] = Field(default=None, max_length=32)
    health_status: Optional[str] = Field(default=None, max_length=32)
    employment_status: Optional[str] = Field(default=None, max_length=32)
    income: Optional[float] = Field(default=None, ge=0)
    is_special_support: Optional[bool] = None
    remarks: Optional[str] = Field(default=None, max_length=500, description="备注")


class HouseholdRiskRecordCreate(BaseModel):
    """登记风险/预警记录入参。"""

    risk_type: RiskType = Field(default="income_drop", description="风险类型")
    risk_level: Optional[RiskLevel] = Field(default=None, description="风险等级，缺省继承户风险等级")
    reason: Optional[str] = Field(default=None, max_length=500)
    detected_at: Optional[datetime] = None


class HouseholdRiskRecordClose(BaseModel):
    """关闭风险记录入参。"""

    closed_note: Optional[str] = Field(default=None, max_length=500)


class HouseholdResponse(BaseModel):
    """一户一档响应模型（由 ORM ``to_dict()`` 校验后出站）。"""

    id: int
    supported_village_id: int
    household_code: Optional[str] = None
    household_name: str
    address: Optional[str] = None
    household_type: str
    risk_type: str
    risk_level: str
    helper_name: Optional[str] = None
    helper_phone: Optional[str] = None
    annual_income: Optional[float] = None
    migrant_workers: Optional[int] = None
    has_serious_illness: bool = False
    housing_safe: bool = True
    last_visit_date: Optional[date] = None
    monitoring_note: Optional[str] = None
    organization_id: Optional[int] = None
    created_by: Optional[int] = None
    is_active: bool = True
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HouseholdMemberResponse(BaseModel):
    """家庭成员响应模型。"""

    id: int
    household_id: int
    name: str
    relation: Optional[str] = None
    id_card: Optional[str] = None
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    education: Optional[str] = None
    health_status: Optional[str] = None
    employment_status: Optional[str] = None
    income: Optional[float] = None
    is_special_support: bool = False
    remarks: Optional[str] = None
    organization_id: Optional[int] = None
    created_by: Optional[int] = None
    is_active: bool = True
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HouseholdRiskRecordResponse(BaseModel):
    """风险记录响应模型。"""

    id: int
    household_id: int
    risk_type: str
    risk_level: str
    reason: Optional[str] = None
    detected_at: Optional[datetime] = None
    status: str
    closed_at: Optional[datetime] = None
    closed_note: Optional[str] = None
    organization_id: Optional[int] = None
    created_by: Optional[int] = None
    is_active: bool = True
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
