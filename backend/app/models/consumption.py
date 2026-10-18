"""消费帮扶台账数据模型（W22 v1.14.0，替换原舆情监测）。

一条记录 = 一次/一批消费帮扶成交：帮扶村（可空）向采购方供应农产品/畜禽/手工品，
登记数量、金额、供货方类型、年度与成交日期，凭证走通用 ``/files/upload`` 后回填 URL。

数据域字段（organization_id / created_by）与全库一致，列表/统计查询经
``data_scope.filter_by_org_ids`` 过滤；``is_active`` 为软删标记（软删后列表默认不可见，
管理员可用 ``include_deleted`` 查看）。
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.sql import func

from .base import Base, UtcDateTime

# 品类：农产品 / 畜禽 / 手工制品 / 其他
CONSUMPTION_CATEGORIES = ("agriculture", "livestock", "handicraft", "other")
# 供货方类型：农户 / 合作社 / 企业
SELLER_TYPES = ("farmer", "cooperative", "enterprise")


class ConsumptionRecord(Base):
    """消费帮扶台账（一条一成交）"""

    __tablename__ = "consumption_records"

    __table_args__ = (
        Index("ix_consumption_records_year", "year"),
        Index("ix_consumption_records_category", "category"),
        Index("ix_consumption_records_village", "supported_village_id"),
        Index("ix_consumption_records_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="SET NULL"),
        nullable=True,
        comment="帮扶村ID（可空，表示未关联具体村）",
    )
    category = Column(
        String(32),
        nullable=False,
        default="agriculture",
        server_default="agriculture",
        comment="品类: agriculture=农产品 / livestock=畜禽 / handicraft=手工 / other=其他",
    )
    item_name = Column(String(200), nullable=False, comment="产品名称")
    quantity = Column(Numeric(14, 2), nullable=True, comment="数量")
    unit = Column(String(20), nullable=True, comment="计量单位（斤/箱/件）")
    amount = Column(
        Numeric(14, 2),
        nullable=False,
        default=0,
        server_default="0",
        comment="成交金额（元）",
    )
    buyer = Column(String(200), nullable=True, comment="采购方（单位）")
    seller = Column(String(200), nullable=True, comment="供货方（农户/合作社/企业）")
    seller_type = Column(
        String(20),
        nullable=True,
        comment="供货方类型: farmer=农户 / cooperative=合作社 / enterprise=企业",
    )
    year = Column(Integer, nullable=False, comment="年度")
    record_date = Column(Date, nullable=True, comment="成交/登记日期")
    voucher_url = Column(String(500), nullable=True, comment="成交凭证文件URL")
    remarks = Column(Text, nullable=True, comment="备注")
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
        return f"<ConsumptionRecord(id={self.id}, item={self.item_name}, amount={self.amount})>"

    def to_dict(self):
        return {
            "id": self.id,
            "supported_village_id": self.supported_village_id,
            "category": self.category,
            "item_name": self.item_name,
            "quantity": float(self.quantity) if self.quantity is not None else None,
            "unit": self.unit,
            "amount": float(self.amount) if self.amount is not None else 0.0,
            "buyer": self.buyer,
            "seller": self.seller,
            "seller_type": self.seller_type,
            "year": self.year,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "voucher_url": self.voucher_url,
            "remarks": self.remarks,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_active is False,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
