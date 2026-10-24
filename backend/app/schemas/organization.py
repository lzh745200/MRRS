"""组织机构 Schema"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrganizationBase(BaseModel):
    """组织基类 - 包含所有公共字段"""

    name: str = Field(..., min_length=1, max_length=100, description="组织名称")
    parent_id: Optional[int] = Field(None, description="父组织ID")
    level: Optional[str] = Field(None, max_length=50, description="层级")
    type: Optional[str] = Field(None, max_length=50, description="类型")
    org_type: Optional[str] = Field(None, max_length=50, description="组织类型")
    description: Optional[str] = Field(None, max_length=1000, description="描述")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    contact_email: Optional[str] = Field(None, max_length=200, description="联系邮箱")
    address: Optional[str] = Field(None, max_length=500, description="地址")
    is_active: bool = True


class OrganizationCreate(OrganizationBase):
    """创建组织"""

    # 组织编码 = 6 位行政区划代码（GB/T 2260），必填；
    # 层级由编码推导（XX0000 省级 / XXYY00 市州级 / XXYYZZ 县市级），
    # 口径唯一来源 services/organization_code_service.py。
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="组织编码（6 位行政区划代码，如 520000/520100/520102）",
    )
    code_prefix: Optional[str] = Field(None, max_length=50, description="编码前缀")
    sort_order: int = 0


class OrganizationUpdate(BaseModel):
    """更新组织 - 所有字段可选"""

    # 编码只读：端点对「传入且与库中不同」一律 422；此处声明字段仅为让
    # 校验层能识别该字段并给出明确语义（否则被 Pydantic 静默丢弃/端点 AttributeError）。
    code: Optional[str] = Field(
        None,
        max_length=6,
        description="组织编码（只读，不可修改；变更需停用后新建）",
    )
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="组织名称")
    parent_id: Optional[int] = None
    level: Optional[str] = Field(None, max_length=50, description="层级")
    type: Optional[str] = Field(None, max_length=50, description="类型")
    org_type: Optional[str] = Field(None, max_length=50, description="组织类型")
    sort_order: Optional[int] = None
    description: Optional[str] = Field(None, max_length=1000, description="描述")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    contact_email: Optional[str] = Field(None, max_length=200, description="联系邮箱")
    address: Optional[str] = Field(None, max_length=500, description="地址")
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    """组织响应"""

    id: int
    code: Optional[str] = Field(None, max_length=100, description="组织编码")
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationTreeNode(OrganizationBase):
    """组织树节点"""

    id: int
    code: Optional[str] = Field(None, max_length=100, description="组织编码")
    path: Optional[str] = Field(None, max_length=500, description="组织路径")
    sort_order: int = 0
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    children: List["OrganizationTreeNode"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class OrganizationStatistics(BaseModel):
    """组织统计"""

    total: int = 0
    active: int = 0
    inactive: int = 0
    by_level: dict = Field(default={}, alias="level_distribution")
    max_level: int = 0
    type_distribution: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,  # 允许通过字段名或别名填充
        extra="ignore",  # 忽略额外字段（兼容旧数据）
    )


class OrganizationListResponse(BaseModel):
    """组织列表响应"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[OrganizationResponse] = Field(default_factory=list)
