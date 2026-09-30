"""Pydantic Schema - 乡村工作"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 预定义的日期格式和对应时区配置
_DATE_FORMATS = [
    ("%Y-%m-%dT%H:%M:%S.%fZ", timezone.utc),
    ("%Y-%m-%dT%H:%M:%S.%f", None),
    ("%Y-%m-%dT%H:%M:%SZ", timezone.utc),
    ("%Y-%m-%dT%H:%M:%S", None),
    ("%Y-%m-%dT%H:%M", None),
    ("%Y-%m-%d %H:%M:%S", None),
    ("%Y-%m-%d", None),
]


def _parse_date(v):
    """将日期字符串转换为 datetime，支持 ISO8601 和多种常用格式"""
    if v is None or isinstance(v, datetime):
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return None
        for fmt, tz in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(v, fmt)
                # 裸日期/无时区格式此前返回 naive，同一字段可 aware 可 naive，
                # 与 timezone=True 的模型列比较时行为随会话时区漂移（深审 LIVE）。
                # 统一：显式时区用声明的，其余一律按 UTC 解释。
                parsed = parsed.replace(tzinfo=tz or timezone.utc)
                return parsed
            except ValueError:
                continue
        raise ValueError(f"无法解析日期: {v}，支持的格式: YYYY-MM-DD 或 ISO8601")
    return v


class _DateValidationMixin:
    """日期字段验证 Mixin，为 start_date 和 end_date 提供解析功能"""

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        return _parse_date(v)


class RuralWorkCreate(_DateValidationMixin, BaseModel):
    """创建乡村工作"""

    name: str = Field(..., min_length=1, max_length=200, description="工作名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    type: Optional[str] = Field(None, description="类型")
    status: Optional[str] = Field(None, description="状态")
    village_id: Optional[int] = Field(None, description="村庄ID")
    responsible_person: Optional[str] = Field(None, max_length=50, description="负责人")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    target: Optional[str] = Field(None, description="目标")
    progress: Optional[int] = Field(0, ge=0, le=100, description="进度")


class RuralWorkUpdate(_DateValidationMixin, BaseModel):
    """更新乡村工作"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    type: Optional[str] = None
    status: Optional[str] = None
    village_id: Optional[int] = None
    responsible_person: Optional[str] = None
    contact_phone: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)


class RuralWorkResponse(BaseModel):
    """乡村工作响应"""

    id: int
    code: Optional[str] = None
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    village_id: Optional[int] = None
    village_name: Optional[str] = None
    responsible_person: Optional[str] = None
    contact_phone: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    target: Optional[str] = None
    progress: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RuralWork(RuralWorkResponse):
    """"""


class RuralWorkListResponse(BaseModel):
    """乡村工作列表响应"""

    total: int = 0
    items: list = Field(default_factory=list)
    skip: int = 0
    limit: int = 10


class RuralWorkStatistics(BaseModel):
    """乡村工作统计"""

    total: int = 0
    planned: int = 0
    in_progress: int = 0
    completed: int = 0
    delayed: int = 0
    by_type: Dict[str, Any] = Field(default_factory=dict)
    completion_rate: float = 0.0
