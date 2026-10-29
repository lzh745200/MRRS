
# DEPRECATED / 非契约（2026-10-29 全库审计标记）。
#
# 本模块**生产代码零引用**，仅被测试的模块清单导入；真正在用的同名契约定义在
# `app/api/v1/` 下（FastAPI 端点文件内），例如 SchoolCreate 在 app/api/v1/school.py
# 里另有一份与模型对齐的定义。
#
# 其中字段**可能与 ORM 模型漂移**（如 schemas/project.py 声明了 projects 表不存在的
# category / location / responsible_person_id），不得据此推断接口契约，也不要在此新增字段。
#
# 保留原因：删除需同步改 3 个测试的模块清单 + 1 个专门覆盖测试，收益低于风险；
# 后续重整 schema 层时应整体删除。

"""Pydantic :."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VillageBase(BaseModel):
    """."""

    name: str = Field(..., min_length=1, max_length=200, description="")
    code: str = Field(..., min_length=1, max_length=50, description="")
    province: Optional[str] = Field(None, max_length=50, description="")
    city: Optional[str] = Field(None, max_length=50, description="")
    county: Optional[str] = Field(None, max_length=50, description="")
    town: Optional[str] = Field(None, max_length=50, description="")
    address: Optional[str] = Field(None, max_length=255, description="")

    longitude: Optional[float] = Field(None, description="")
    latitude: Optional[float] = Field(None, description="")
    altitude: Optional[float] = Field(None, description="()")
    area: Optional[float] = Field(None, ge=0, description="()")

    population: Optional[int] = Field(None, ge=0, description="")
    households: Optional[int] = Field(None, ge=0, description="")
    poor_households: Optional[int] = Field(None, ge=0, description="")
    poor_population: Optional[int] = Field(None, ge=0, description="")

    party_secretary: Optional[str] = Field(None, max_length=50, description="")
    party_secretary_phone: Optional[str] = Field(None, max_length=20, description="")
    village_director: Optional[str] = Field(None, max_length=50, description="")
    village_director_phone: Optional[str] = Field(None, max_length=20, description="")

    organization_structure: Optional[Dict[str, Any]] = Field(None, description=" JSON")
    description: Optional[str] = Field(None, description="")
    main_industries: Optional[str] = Field(None, description="")
    infrastructure: Optional[str] = Field(None, description="")
    education_health: Optional[str] = Field(None, description="")
    support_start_date: Optional[datetime] = Field(None, description="")
    support_unit: Optional[str] = Field(None, max_length=200, description="")
    support_contact: Optional[str] = Field(None, max_length=50, description="")
    support_contact_phone: Optional[str] = Field(None, max_length=20, description="")
    support_status: Optional[str] = Field("ongoing", max_length=20, description="")
    images: Optional[List[str]] = Field(None, description="")
    achievements: Optional[str] = Field(None, description="")
    notes: Optional[str] = Field(None, description="")

    model_config = ConfigDict(from_attributes=True)


class VillageCreate(VillageBase):
    """."""


class VillageUpdate(BaseModel):
    """."""

    name: Optional[str] = Field(None, min_length=1, max_length=200, description="")
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="")
    province: Optional[str] = Field(None, max_length=50, description="")
    city: Optional[str] = Field(None, max_length=50, description="")
    county: Optional[str] = Field(None, max_length=50, description="")
    town: Optional[str] = Field(None, max_length=50, description="")
    address: Optional[str] = Field(None, max_length=255, description="")
    longitude: Optional[float] = Field(None, description="")
    latitude: Optional[float] = Field(None, description="")
    altitude: Optional[float] = Field(None, description="()")
    area: Optional[float] = Field(None, ge=0, description="()")
    population: Optional[int] = Field(None, ge=0, description="")
    households: Optional[int] = Field(None, ge=0, description="")
    poor_households: Optional[int] = Field(None, ge=0, description="")
    poor_population: Optional[int] = Field(None, ge=0, description="")
    party_secretary: Optional[str] = Field(None, max_length=50, description="")
    party_secretary_phone: Optional[str] = Field(None, max_length=20, description="")
    village_director: Optional[str] = Field(None, max_length=50, description="")
    village_director_phone: Optional[str] = Field(None, max_length=20, description="")
    organization_structure: Optional[Dict[str, Any]] = Field(None, description=" JSON")
    description: Optional[str] = Field(None, description="")
    main_industries: Optional[str] = Field(None, description="")
    infrastructure: Optional[str] = Field(None, description="")
    education_health: Optional[str] = Field(None, description="")
    support_start_date: Optional[datetime] = Field(None, description="")
    support_unit: Optional[str] = Field(None, max_length=200, description="")
    support_contact: Optional[str] = Field(None, max_length=50, description="")
    support_contact_phone: Optional[str] = Field(None, max_length=20, description="")
    support_status: Optional[str] = Field(None, max_length=20, description="")
    images: Optional[List[str]] = Field(None, description="")
    achievements: Optional[str] = Field(None, description="")
    notes: Optional[str] = Field(None, description="")

    model_config = ConfigDict(from_attributes=True)


class VillageResponse(VillageBase):
    """."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VillageListResponse(BaseModel):
    """."""

    total: int = Field(..., description="")
    items: List[VillageResponse] = Field(..., description="")

    model_config = ConfigDict(from_attributes=True)
