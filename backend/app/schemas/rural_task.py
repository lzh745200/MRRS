"""Pydantic Schema - 乡村振兴工作任务"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuralTaskCreate(BaseModel):
    """创建任务"""

    rural_work_id: int = Field(..., description="关联乡村工作ID")
    title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    category: Optional[str] = Field("other", description="分类")
    priority: Optional[str] = Field("medium", description="优先级")
    year: Optional[int] = Field(None, description="年度")
    quarter: Optional[int] = Field(None, ge=1, le=4, description="季度")
    description: Optional[str] = Field(None, description="描述")
    target: Optional[str] = Field(None, description="预期目标")
    budget: Optional[float] = Field(0.0, ge=0, description="预算(万元)")
    responsible_unit: Optional[str] = Field(None, max_length=100, description="责任单位")
    responsible_person: Optional[str] = Field(None, max_length=50, description="负责人")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    planned_start: Optional[datetime] = Field(None, description="计划开始日期")
    planned_end: Optional[datetime] = Field(None, description="计划结束日期")
    village_id: Optional[int] = Field(None, description="帮扶村ID")


class RuralTaskUpdate(BaseModel):
    """更新任务"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[int] = Field(None, ge=1, le=4)
    description: Optional[str] = None
    target: Optional[str] = None
    result: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    actual_cost: Optional[float] = Field(None, ge=0)
    progress: Optional[int] = Field(None, ge=0, le=100)
    responsible_unit: Optional[str] = None
    responsible_person: Optional[str] = None
    contact_phone: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    village_id: Optional[int] = None


class RuralTaskResponse(BaseModel):
    """任务响应"""

    id: int
    rural_work_id: int
    title: str
    code: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[int] = None
    description: Optional[str] = None
    target: Optional[str] = None
    result: Optional[str] = None
    budget: Optional[float] = 0.0
    actual_cost: Optional[float] = 0.0
    progress: Optional[int] = 0
    responsible_unit: Optional[str] = None
    responsible_person: Optional[str] = None
    contact_phone: Optional[str] = None
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    submitted_by: Optional[int] = None
    submitted_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    approval_comment: Optional[str] = None
    village_id: Optional[int] = None
    village_name: Optional[str] = None
    rural_work_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RuralTaskListResponse(BaseModel):
    """任务列表响应"""

    total: int = 0
    items: list = []
    skip: int = 0
    limit: int = 10


class RuralTaskStatistics(BaseModel):
    """任务统计"""

    total: int = 0
    draft: int = 0
    pending_approval: int = 0
    in_progress: int = 0
    completed: int = 0
    rejected: int = 0
    by_category: Dict[str, Any] = {}
    by_year: Dict[str, Any] = {}
    total_budget: float = 0.0
    total_actual_cost: float = 0.0
    completion_rate: float = 0.0


class TaskSubmitRequest(BaseModel):
    """提交审批请求"""

    comment: Optional[str] = Field(None, description="提交说明")


class TaskApproveRequest(BaseModel):
    """审批请求"""

    approved: bool = Field(..., description="是否批准")
    comment: Optional[str] = Field(None, description="审批意见")
