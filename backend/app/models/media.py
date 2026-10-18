"""影像库数据模型（W22 · 契约 §1.4）

``photo_archives``：帮扶影像归档（村 / 学校 / 项目现场照片、多期对比）。

- 归档注册复用通用上传 ``/files/upload`` 返回的 ``/uploads/...`` URL；
- 拍摄时间 / GPS 由服务层从 EXIF 补全（``taken_at``/``gps_lat``/``gps_lng``）；
- ``spot_key`` 为拍摄点标识（默认 GPS 量化串），用于同点多期对比；
- 数据域字段 ``organization_id`` / ``created_by`` 与全库一致，列表经
  ``OrgScopeFilter.filter_by_org_ids`` 过滤；``is_active=False`` 为软删除。
"""

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.sql import func

from .base import Base, UtcDateTime


class PhotoArchive(Base):
    """帮扶影像归档（一条一图）"""

    __tablename__ = "photo_archives"

    __table_args__ = (
        Index("ix_photo_archives_organization_id", "organization_id"),
        Index("ix_photo_archives_spot_key", "spot_key"),
        Index("ix_photo_archives_taken_at", "taken_at"),
        Index("ix_photo_archives_village_id", "village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_url = Column(String(500), nullable=False, comment="文件访问 URL（/uploads/...）")
    file_name = Column(String(255), nullable=True, comment="原始文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    mime_type = Column(String(100), nullable=True, comment="MIME 类型")
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联帮扶村ID",
    )
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联帮扶学校ID",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联帮扶项目ID",
    )
    tag = Column(String(50), nullable=True, comment="标签")
    spot_key = Column(String(100), nullable=True, comment="拍摄点标识（多期对比依据）")
    taken_at = Column(UtcDateTime(), nullable=True, comment="拍摄时间（优先 EXIF）")
    gps_lat = Column(Numeric(10, 6), nullable=True, comment="拍摄纬度")
    gps_lng = Column(Numeric(10, 6), nullable=True, comment="拍摄经度")
    uploader_id = Column(Integer, nullable=True, comment="上传者用户ID")
    shot_source = Column(
        String(20),
        nullable=False,
        default="manual",
        server_default="manual",
        comment="拍摄信息来来源: exif / manual",
    )
    # 数据域 / 软删（与全库一致）
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )
    created_by = Column(Integer, nullable=True, comment="创建者ID")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效（软删除标记）")
    deleted_at = Column(UtcDateTime(), nullable=True, comment="软删时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self):
        return f"<PhotoArchive(id={self.id}, file_url={self.file_url!r})>"
