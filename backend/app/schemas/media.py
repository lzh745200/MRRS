"""影像库请求 / 响应模型（W22 · 契约 §1.4 / §2）

- ``file_url`` 必填（复用 ``/files/upload`` 的 ``/uploads/...`` URL）；
- GPS 纬度/经度范围校验（-90~90 / -180~180），越界由 FastAPI 拒绝（422）；
- 响应统一使用 snake_case 字段名，与契约字段表一致。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PhotoArchiveCreate(BaseModel):
    """注册影像归档请求"""

    file_url: str = Field(..., min_length=1, max_length=500, description="上传后的文件 URL")
    file_name: Optional[str] = Field(default=None, max_length=255)
    file_size: Optional[int] = Field(default=None, ge=0)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    project_id: Optional[int] = None
    tag: Optional[str] = Field(default=None, max_length=50)
    spot_key: Optional[str] = Field(default=None, max_length=100)
    taken_at: Optional[datetime] = None
    gps_lat: Optional[float] = Field(default=None, ge=-90, le=90, description="纬度")
    gps_lng: Optional[float] = Field(default=None, ge=-180, le=180, description="经度")
    shot_source: Optional[str] = Field(default=None, max_length=20)


class PhotoArchiveUpdate(BaseModel):
    """更新影像归档请求（部分更新）"""

    file_name: Optional[str] = Field(default=None, max_length=255)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    project_id: Optional[int] = None
    tag: Optional[str] = Field(default=None, max_length=50)
    spot_key: Optional[str] = Field(default=None, max_length=100)
    taken_at: Optional[datetime] = None
    gps_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    gps_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    shot_source: Optional[str] = Field(default=None, max_length=20)


class PhotoArchiveOut(BaseModel):
    """影像归档响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    file_url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    village_id: Optional[int] = None
    school_id: Optional[int] = None
    project_id: Optional[int] = None
    tag: Optional[str] = None
    spot_key: Optional[str] = None
    taken_at: Optional[datetime] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    uploader_id: Optional[int] = None
    shot_source: Optional[str] = None
    organization_id: Optional[int] = None
    created_by: Optional[int] = None
    is_active: bool = True
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CompareImageRequest(BaseModel):
    """对比图合成请求（按传入顺序拼接）"""

    ids: list[int] = Field(..., min_length=1, max_length=9, description="影像 ID 列表（1~9 张）")
