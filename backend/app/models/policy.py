import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.models.base import Base

"""政策法规模型"""


class PolicyStatus(str, enum.Enum):
    """政策状态"""

    ACTIVE = "active"
    INVALID = "invalid"
    DRAFT = "draft"


class PolicyLevel(str, enum.Enum):
    """政策级别"""

    NATIONAL = "national"
    PROVINCIAL = "provincial"
    MUNICIPAL = "municipal"
    COUNTY = "county"


class PolicyCategory(Base):
    """政策分类表"""

    __tablename__ = "policy_categories"

    __table_args__ = (
        Index("ix_policy_categories_parent_id", "parent_id"),
        Index("ix_policy_categories_is_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="分类名称")
    code = Column(String(50), unique=True, comment="分类编码")
    parent_id = Column(
        Integer,
        ForeignKey("policy_categories.id", ondelete="SET NULL"),
        nullable=True,
        comment="父分类ID",
    )
    sort_order = Column(Integer, default=0, comment="排序")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")


class PolicyFavorite(Base):
    """政策收藏表"""

    __tablename__ = "policy_favorites"

    __table_args__ = (
        UniqueConstraint("user_id", "policy_id", name="uq_policy_favorite_user_policy"),
        Index("ix_policy_favorites_user_id", "user_id"),
        Index("ix_policy_favorites_policy_id", "policy_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="用户ID",
    )
    policy_id = Column(
        Integer,
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
        comment="政策ID(政策删除时收藏行级联清除)",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="收藏时间")


class Policy(Base):
    """政策法规表"""

    __tablename__ = "policies"

    __table_args__ = (
        Index("ix_policies_status", "status"),
        Index("ix_policies_level", "level"),
        Index("ix_policies_category", "category"),
        Index("ix_policies_issue_date", "issue_date"),
        Index("ix_policies_status_level", "status", "level"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False, index=True, comment="法规标题")
    code = Column(String(100), unique=True, comment="法规文号")
    # 分类信息
    category = Column(String(50), comment="法规类别")
    level = Column(
        String(50),
        comment="法规级别: national-国家级, provincial-省级, municipal-市级, county-县级",
    )
    # 发布信息
    issuing_authority = Column(String(200), comment="发布机关")
    issue_date = Column(DateTime(timezone=True), comment="发布日期")
    effective_date = Column(DateTime(timezone=True), comment="生效日期")
    # 内容
    summary = Column(Text, comment="摘要")
    content = Column(Text, comment="全文内容")
    keywords = Column(String(500), comment="关键词,逗号分隔")
    # 附件
    file_path = Column(String(500), comment="文件路径")
    file_size = Column(Integer, comment="文件大小")
    file_type = Column(String(50), comment="文件类型")
    # 状态
    status = Column(
        String(20),
        default="active",
        comment="状态: active-有效, invalid-失效, draft-草稿",
    )
    is_important = Column(Boolean, default=False, comment="是否重要")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否活跃（软删除标记）")
    # 归属与审计
    organization_id = Column(Integer, nullable=True, index=True, comment="所属组织ID")
    created_by = Column(Integer, nullable=True, comment="创建人用户ID")
    # 学习统计
    view_count = Column(Integer, default=0, comment="查看次数")
    download_count = Column(Integer, default=0, comment="下载次数")
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Policy(id={self.id}, title='{self.title}', code='{self.code}')>"
