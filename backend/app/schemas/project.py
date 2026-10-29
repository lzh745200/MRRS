
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

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

"""Pydantic"""


class ProjectBase(BaseModel):
    """"""

    name: str = Field(..., min_length=1, max_length=100, description="")
    description: Optional[str] = Field(None, max_length=500, description="")
    start_date: datetime = Field(..., description="")
    end_date: Optional[datetime] = Field(None, description="")
    status: str = Field(..., min_length=1, max_length=20, description="")
    budget: float = Field(..., ge=0, description="")
    responsible_person_id: Optional[int] = Field(None, description="ID")
    category: str = Field(..., min_length=1, max_length=50, description="")
    location: str = Field(..., min_length=1, max_length=200, description="")
    priority: str = Field(..., min_length=1, max_length=20, description="")
    remarks: Optional[str] = Field(None, max_length=500, description="")


class ProjectCreate(ProjectBase):
    """"""


class ProjectUpdate(BaseModel):
    """"""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="")
    start_date: Optional[datetime] = Field(None, description="")
    status: Optional[str] = Field(None, min_length=1, max_length=20, description="")
    budget: Optional[float] = Field(None, ge=0, description="")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="")
    location: Optional[str] = Field(None, min_length=1, max_length=200, description="")
    priority: Optional[str] = Field(None, min_length=1, max_length=20, description="")


class ProjectResponse(ProjectBase):
    """"""

    id: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """"""

    total: int = Field(..., description="")
    items: list[ProjectResponse] = Field(..., description="")


class ProjectProgressBase(BaseModel):
    """"""

    project_id: int = Field(..., description="ID")
    progress_date: datetime = Field(..., description="")
    progress_percentage: float = Field(..., ge=0, le=100, description="")
    description: str = Field(..., max_length=500, description="")
    reporter_id: Optional[int] = Field(None, description="ID")


class ProjectProgressCreate(ProjectProgressBase):
    """"""


class ProjectProgressResponse(ProjectProgressBase):
    """"""

    id: int
    created_at: datetime
