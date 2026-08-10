"""数据上报 Schema"""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewActionEnum(str, enum.Enum):
    """审核动作"""

    APPROVE = "approve"
    REJECT = "reject"


class DataReportCreate(BaseModel):
    """创建数据上报"""

    title: str
    report_type: str
    package_id: int = Field(..., description="上报的数据包ID")
    data: Optional[Dict[str, Any]] = None
    target_org_id: Optional[int] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None


class DataReportResponse(BaseModel):
    """数据上报响应"""

    id: int
    title: str = ""
    report_type: str = ""
    status: str = "draft"
    source_org_id: Optional[int] = None
    target_org_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DataReportListResponse(BaseModel):
    """数据上报列表响应"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[DataReportResponse] = []


class DataReportReview(BaseModel):
    """数据上报审核

    服务层读取 action/rejection_reason；兼容旧客户端只传 status 的写法
    （status="approve"/"reject" 自动映射为 action）。
    """

    action: Optional[ReviewActionEnum] = None
    status: Optional[str] = None
    comment: Optional[str] = None
    rejection_reason: Optional[str] = None

    @model_validator(mode="after")
    def _derive_action(self):
        if self.action is None and self.status:
            normalized = self.status.strip().lower()
            if normalized in ("approve", "approved", "通过"):
                self.action = ReviewActionEnum.APPROVE
            elif normalized in ("reject", "rejected", "驳回"):
                self.action = ReviewActionEnum.REJECT
        if self.action is None:
            raise ValueError("action 不能为空（或由 status 映射：approve/reject）")
        return self


class DataReportStatistics(BaseModel):
    """数据上报统计"""

    total: int = 0
    submitted: int = 0
    approved: int = 0
    rejected: int = 0
    pending: int = 0


class SubordinateReportSummary(BaseModel):
    """下级单位上报摘要"""

    org_id: int
    org_name: str = ""
    total_reports: int = 0
    pending_reports: int = 0
    approved_reports: int = 0
    rejected_reports: int = 0


class SubordinateReportDashboard(BaseModel):
    """下级单位上报仪表板"""

    total_subordinates: int = 0
    reported_count: int = 0
    unreported_count: int = 0
    statistics: Optional[DataReportStatistics] = None
    subordinates: List[SubordinateReportSummary] = []
