"""Pydantic Schema."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

try:  # pragma: no cover -
    from app.models.fund import FundSource, FundStatus, FundType
except Exception:  # noqa: BLE001  # pragma: no cover —— app.models.fund 为项目内模块必然可导入，防御回退不可达

    class FundType(str, Enum):  # type: ignore[override]
        PROJECT = "project"
        OPERATION = "operation"
        EDUCATION = "education"
        INFRASTRUCTURE = "infrastructure"
        EMERGENCY = "emergency"
        OTHER = "other"

    class FundSource(str, Enum):  # type: ignore[override]
        MILITARY = "military"
        GOVERNMENT = "government"
        DONATION = "donation"
        ENTERPRISE = "enterprise"
        OTHER = "other"

    class FundStatus(str, Enum):  # type: ignore[override]
        PENDING = "pending"
        PLANNED = "planned"
        APPROVED = "approved"
        REJECTED = "rejected"
        ALLOCATED = "allocated"
        IN_USE = "in_use"
        COMPLETED = "completed"
        AUDITED = "audited"


class FundBase(BaseModel):
    code: Optional[str] = Field(None, max_length=50, description="编号（可选，留空自动生成）")
    name: str = Field(..., min_length=1, max_length=200, description="")
    type: Optional[str] = Field(None, max_length=50, description="经费大类")
    amount: Optional[float] = Field(None, ge=0, description="申请金额")
    date: Optional[datetime] = Field(None, description="业务发生日期")
    operator: Optional[str] = Field(None, max_length=100, description="经办人")
    source: Optional[str] = Field(None, max_length=200, description="来源说明")
    purpose: Optional[str] = Field(None, max_length=2000, description="用途")
    fund_type: Optional[FundType] = Field(None, description="经费类型")
    fund_source: Optional[FundSource] = Field(None, description="经费来源")
    status: FundStatus = Field(default=FundStatus.PLANNED, description="")
    planned_amount: Optional[float] = Field(0, ge=0, description="计划金额")
    approved_amount: Optional[float] = Field(None, ge=0, description="()")
    allocated_amount: float = Field(default=0, ge=0, description="()")
    used_amount: float = Field(default=0, ge=0, description="()")
    remaining_amount: float = Field(default=0, ge=0, description="()")
    project_id: Optional[int] = Field(None, description="ID")
    village_id: Optional[int] = Field(None, description="ID")
    school_id: Optional[int] = Field(None, description="ID")
    applicant: Optional[str] = Field(None, max_length=100, description="/")
    application_date: Optional[datetime] = Field(None, description="")
    approved_by: Optional[str] = Field(None, max_length=100, description="")
    approval_date: Optional[datetime] = Field(None, description="")
    allocation_date: Optional[datetime] = Field(None, description="")
    allocation_method: Optional[str] = Field(None, max_length=50, description="")
    receiver: Optional[str] = Field(None, max_length=100, description="/")
    usage_description: Optional[str] = Field(None, max_length=2000, description="")
    start_date: Optional[datetime] = Field(None, description="")
    end_date: Optional[datetime] = Field(None, description="")
    audit_date: Optional[datetime] = Field(None, description="")
    audit_result: Optional[str] = Field(None, max_length=50, description="")
    audit_opinion: Optional[str] = Field(None, max_length=2000, description="")
    remarks: Optional[str] = Field(None, max_length=1000, description="")

    model_config = ConfigDict(from_attributes=True)


class FundCreate(FundBase):
    """."""


class FundUpdate(BaseModel):
    """()."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    fund_type: Optional[FundType] = None
    fund_source: Optional[FundSource] = None
    status: Optional[FundStatus] = None
    planned_amount: Optional[float] = Field(None, ge=0)
    approved_amount: Optional[float] = Field(None, ge=0)
    allocated_amount: Optional[float] = Field(None, ge=0)
    used_amount: Optional[float] = Field(None, ge=0)
    remaining_amount: Optional[float] = Field(None, ge=0)
    project_id: Optional[int] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    applicant: Optional[str] = Field(None, max_length=100)
    application_date: Optional[datetime] = None
    approved_by: Optional[str] = Field(None, max_length=100)
    approval_date: Optional[datetime] = None
    allocation_date: Optional[datetime] = None
    allocation_method: Optional[str] = Field(None, max_length=50)
    receiver: Optional[str] = Field(None, max_length=100)
    usage_description: Optional[str] = Field(None, max_length=2000)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    audit_date: Optional[datetime] = None
    audit_result: Optional[str] = Field(None, max_length=50)
    audit_opinion: Optional[str] = Field(None, max_length=2000)
    remarks: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(from_attributes=True)


class FundResponse(FundBase):
    id: int
    created_at: datetime
    updated_at: datetime


class FundListResponse(BaseModel):
    total: int = Field(..., description="")
    items: List[FundResponse] = Field(..., description="")

    model_config = ConfigDict(from_attributes=True)


class FundTransactionBase(BaseModel):
    fund_id: int = Field(..., description="ID")
    transaction_type: str = Field(..., min_length=1, max_length=50, description=": income-, expense-")
    amount: float = Field(..., ge=0, description="()")
    description: Optional[str] = Field(None, max_length=1000, description="")
    transaction_date: datetime = Field(..., description="")
    created_by: Optional[str] = Field(None, max_length=100, description="")

    model_config = ConfigDict(from_attributes=True)


class FundTransactionCreate(FundTransactionBase):
    """."""


class FundTransactionResponse(FundTransactionBase):
    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="")
    updated_at: datetime = Field(..., description="")
