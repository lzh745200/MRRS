"""捐赠物资台账数据模型

实物捐赠（图书 / 设备 / 物资）逐条登记：数量、折价、来源单位、去向、签收人、
凭证附件。金额与数量沿用全库 ``Numeric(15, 4)`` 口径（金额单位：万元），
``to_dict`` 统一转 float 与既有资金模块一致。

数据域字段（organization_id / created_by）与全库一致，列表查询经
``data_scope.filter_by_org_ids`` 过滤；``is_active`` 为软删标记。
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.sql import func

from .base import Base, UtcDateTime

# 物资类别：图书 / 设备 / 物资 / 其他
DONATION_CATEGORIES = ("book", "equipment", "material", "other")
# 去向类型：帮扶村 / 帮扶学校 / 帮扶项目
DESTINATION_TYPES = ("village", "school", "project")


class DonationItem(Base):
    """捐赠物资台账（一条一物）"""

    __tablename__ = "donation_items"

    __table_args__ = (
        Index(
            "ix_donation_items_destination",
            "destination_type",
            "village_id",
            "school_id",
            "project_id",
        ),
        Index("ix_donation_items_category", "category"),
        Index("ix_donation_items_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="物资名称")
    category = Column(
        String(16),
        nullable=False,
        default="material",
        server_default="material",
        comment="类别: book=图书 / equipment=设备 / material=物资 / other=其他",
    )
    quantity = Column(Numeric(15, 4), default=0, comment="数量")
    unit = Column(String(32), nullable=True, comment="计量单位（册/台/件/套）")
    valuation = Column(Numeric(15, 4), default=0, comment="折价(万元)")
    source_unit = Column(String(200), nullable=True, comment="来源单位（捐赠方）")
    destination_type = Column(
        String(16), nullable=False, comment="去向类型: village/school/project"
    )
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="SET NULL"),
        nullable=True,
        comment="去向帮扶村ID（去向为村时必填）",
    )
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        comment="去向帮扶学校ID（去向为学校时必填）",
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        comment="去向帮扶项目ID（去向为项目时必填）",
    )
    delivery_date = Column(Date, nullable=True, comment="交付日期")
    receiver = Column(String(64), nullable=True, comment="签收人")
    # MutableList 包装与 two_factor_auth 同约定：裸 Column(JSON) 的就地修改
    # （append/remove）不产生 attribute 事件、不落库；本模块虽然整列赋值，
    # 但保留包装以免后续改为就地修改时静默丢数据。
    attachments = Column(
        MutableList.as_mutable(JSON), nullable=True, default=list, comment="凭证附件列表"
    )
    remark = Column(String(500), nullable=True, comment="备注")
    # 数据权限字段
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
        return f"<DonationItem(id={self.id}, name={self.name}, category={self.category})>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "quantity": float(self.quantity or 0),
            "unit": self.unit,
            "valuation": float(self.valuation or 0),
            "source_unit": self.source_unit,
            "destination_type": self.destination_type,
            "village_id": self.village_id,
            "school_id": self.school_id,
            "project_id": self.project_id,
            "delivery_date": self.delivery_date.isoformat() if self.delivery_date else None,
            "receiver": self.receiver,
            "attachments": list(self.attachments or []),
            "remark": self.remark,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_active is False,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
