"""
用户-组织关联模型
支持用户属于多个组织的场景
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.models.base import Base, UtcDateTime


class UserOrganization(Base):
    """用户-组织关联模型"""

    __tablename__ = "user_organizations"

    id = Column(Integer, primary_key=True, index=True, comment="主键ID")
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        comment="组织ID",
    )
    role = Column(
        String(20),
        nullable=True,
        comment="在该组织中的角色: admin, member, viewer",
    )
    created_at = Column(
        UtcDateTime(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        UtcDateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间",
    )

    # 索引和约束
    __table_args__ = (
        Index("idx_user_org", "user_id", "organization_id"),
        Index("idx_user_organizations_user", "user_id"),
        Index("idx_user_organizations_org", "organization_id"),
        UniqueConstraint("user_id", "organization_id", name="uq_user_org"),
        {"comment": "用户-组织关联表"},
    )

    def __repr__(self):
        return f"<UserOrganization(user_id={self.user_id}, org_id={self.organization_id}, role={self.role})>"
