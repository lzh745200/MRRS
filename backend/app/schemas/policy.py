"""Pydantic Schema for Policy module."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ==================== 常量定义 ====================

CATEGORY_NAMES: Dict[str, str] = {
    "military": "专项政策",
    "local": "地方政策",
    "national": "国家政策",
    "regulation": "法规条例",
    "notice": "通知公告",
}

MILITARY_LEVEL_NAMES: Dict[str, str] = {
    "central": "中央部署",
    "theater": "区域级",
    "corps": "重点级",
    "division": "单元级",
    "regiment": "基础级",
}

LOCAL_LEVEL_NAMES: Dict[str, str] = {
    "national": "国家级",
    "provincial": "省级",
    "municipal": "市级",
    "county": "县级",
    "township": "乡镇级",
}

STATUS_NAMES: Dict[str, str] = {
    "active": "生效中",
    "draft": "草稿",
    "expired": "已过期",
    "revoked": "已废止",
}


# ==================== Schema 定义 ====================


class PolicyBase(BaseModel):
    title: str = Field(..., max_length=200, description="标题")
    content: str = Field(..., description="内容")
    issue_date: Optional[datetime] = Field(None, description="发布日期")
    effective_date: Optional[datetime] = Field(None, description="生效日期")
    expiry_date: Optional[datetime] = Field(None, description="失效日期")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    level: Optional[str] = Field(None, max_length=50, description="政策级别")
    issuing_authority: Optional[str] = Field(None, max_length=200, description="发布机关")
    summary: Optional[str] = Field(None, description="摘要")
    code: Optional[str] = Field(None, max_length=100, description="文号")
    file_path: Optional[str] = Field(None, description="附件路径")
    status: Optional[str] = Field("active", description="状态")
    keywords: Optional[str] = Field(None, description="关键词")

    model_config = ConfigDict(from_attributes=True)


class PolicyCreate(PolicyBase):
    """创建政策"""


class PolicyUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    issue_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    category: Optional[str] = None
    level: Optional[str] = None
    issuing_authority: Optional[str] = None
    summary: Optional[str] = None
    code: Optional[str] = None
    file_path: Optional[str] = None
    status: Optional[str] = None
    keywords: Optional[str] = None
    view_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PolicyResponse(BaseModel):
    id: int
    title: str
    content: str
    issue_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    category: Optional[str] = None
    level: Optional[str] = None
    issuing_authority: Optional[str] = None
    summary: Optional[str] = None
    code: Optional[str] = None
    file_path: Optional[str] = None
    status: Optional[str] = None
    keywords: Optional[str] = None
    view_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    category_name: Optional[str] = None
    level_name: Optional[str] = None
    status_name: Optional[str] = None
    download_count: int = 0
    is_important: bool = False
    file_size: Optional[int] = None
    file_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @property
    def organization_level(self) -> Optional[str]:
        return self.level

    @property
    def department(self) -> Optional[str]:
        return self.issuing_authority

    @property
    def document_number(self) -> Optional[str]:
        return self.code

    @property
    def publish_date(self) -> Optional[datetime]:
        return self.issue_date

    @property
    def attachment_urls(self) -> Optional[str]:
        return self.file_path


class PolicyListResponse(BaseModel):
    items: List[PolicyResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 10


class CategoryLevelConfig(BaseModel):
    value: str
    label: str


class CategoryConfig(BaseModel):
    value: str
    label: str
    levels: List[CategoryLevelConfig] = []


class CategoriesResponse(BaseModel):
    categories: List[CategoryConfig] = []
