"""
组织机构模型
"""

import enum

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import backref, relationship

from .base import BaseModel, EncryptedText


class OrganizationType(str, enum.Enum):
    """组织类型"""

    DEPARTMENT = "department"
    SUPPORT_UNIT = "support_unit"
    OTHER = "other"


class OrganizationLevel(str, enum.Enum):
    """组织层级"""

    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    LEVEL_4 = "level_4"
    LEVEL_5 = "level_5"


class Organization(BaseModel):
    """组织机构模型"""

    __tablename__ = "organizations"

    __table_args__ = (
        Index("ix_organizations_name", "name"),
        Index("ix_organizations_parent_id", "parent_id"),
        Index("ix_organizations_org_type", "org_type"),
        Index("ix_organizations_is_active", "is_active"),
        Index("ix_organizations_level", "level"),
        Index("ix_organizations_created_by", "created_by"),
    )

    name = Column(String(200), nullable=False, comment="单位名称")
    code = Column(String(50), unique=True, nullable=True, comment="单位编号")
    parent_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="上级单位ID",
    )
    level = Column(String(50), nullable=True, comment="层级")
    type = Column(String(50), nullable=True, comment="单位类型")
    org_type = Column(String(50), nullable=True, comment="组织类型: department, support_unit")
    sort_order = Column(Integer, default=0, comment="排序")
    description = Column(Text, nullable=True, comment="描述")
    contact_person = Column(String(50), nullable=True, comment="联系人")
    contact_phone = Column(EncryptedText(64), nullable=True, comment="联系电话(透明加密, ADR-0005)")
    contact_email = Column(String(100), nullable=True, comment="联系邮箱")
    address = Column(String(200), nullable=True, comment="地址")
    region_code = Column(String(20), nullable=True, comment="行政区划编码（关联 regions.code，用于数据权限前缀匹配）")
    is_active = Column(Boolean, default=True, comment="是否启用")
    path = Column(String(500), nullable=True, comment="路径")
    created_by = Column(Integer, nullable=True, comment="创建人ID")
    updated_by = Column(Integer, nullable=True, comment="更新人ID")

    # 自引用关系（树形结构）
    children = relationship(
        "Organization",
        backref=backref("parent", remote_side="Organization.id"),
        cascade="all, delete-orphan",
    )
    funds = relationship("Fund", back_populates="organization")

    def __repr__(self):
        return f"<Organization(id={self.id}, name={self.name})>"
