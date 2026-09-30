from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.school import SchoolLevel, SchoolType

"""Pydantic Schemas"""


class SchoolBase(BaseModel):
    """Schema"""

    name: str = Field(..., min_length=1, max_length=100, description="")
    code: str = Field(..., min_length=1, max_length=50, description="")
    school_type: SchoolType = Field(..., description="")
    school_level: SchoolLevel = Field(..., description="")
    province: Optional[str] = Field(None, max_length=50, description="")
    city: Optional[str] = Field(None, max_length=50, description="")
    district: Optional[str] = Field(None, max_length=50, description="")
    address: Optional[str] = Field(None, max_length=200, description="")
    student_count: Optional[int] = Field(None, ge=0, description="")
    teacher_count: Optional[int] = Field(None, ge=0, description="")
    class_count: Optional[int] = Field(None, ge=0, description="")
    area: Optional[float] = Field(None, ge=0, description="()")
    building_area: Optional[float] = Field(None, ge=0, description="()")
    has_library: bool = Field(default=False, description="")
    has_computer_room: bool = Field(default=False, description="")
    has_lab: bool = Field(default=False, description="")
    has_playground: bool = Field(default=False, description="")
    support_unit: Optional[str] = Field(None, max_length=100, description="")
    support_start_date: Optional[datetime] = Field(None, description="")
    is_active_support: bool = Field(default=True, description="")
    principal: Optional[str] = Field(None, max_length=50, description="")
    contact_phone: Optional[str] = Field(None, max_length=20, description="")
    email: Optional[str] = Field(None, max_length=100, description="")
    description: Optional[str] = Field(None, description="")
    current_needs: Optional[str] = Field(None, description="")
    support_achievements: Optional[str] = Field(None, description="")


class SchoolCreate(SchoolBase):
    """Schema"""


class SchoolUpdate(BaseModel):
    """Schema"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    school_type: Optional[SchoolType] = None
    school_level: Optional[SchoolLevel] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = Field(None, max_length=200)
    student_count: Optional[int] = Field(None, ge=0)
    teacher_count: Optional[int] = Field(None, ge=0)
    class_count: Optional[int] = Field(None, ge=0)
    area: Optional[float] = Field(None, ge=0)
    building_area: Optional[float] = Field(None, ge=0)
    has_library: Optional[bool] = None
    has_computer_room: Optional[bool] = None
    has_lab: Optional[bool] = None
    has_playground: Optional[bool] = None
    support_unit: Optional[str] = Field(None, max_length=100)
    support_start_date: Optional[datetime] = None
    is_active_support: Optional[bool] = None
    principal: Optional[str] = Field(None, max_length=50)
    contact_phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    current_needs: Optional[str] = None
    support_achievements: Optional[str] = None


class SchoolResponse(SchoolBase):
    """Schema"""

    # Pydantic v2 从 ORM 实例转换需显式开启（深审 LIVE）；缺失时
    # model_validate(orm_obj) 直接 ValidationError。
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SchoolListResponse(BaseModel):
    """Schema"""

    total: int = Field(..., description="")
    items: list[SchoolResponse] = Field(..., description="")
