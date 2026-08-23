"""费用标准数据库模型

存储设备购置费、会议费等各类费用标准限额，
支持按地方/行业灵活配置，提供版本管理与时效性控制。
"""

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.sql import func

from .base import Base


class FeeStandard(Base):
    """费用标准"""

    __tablename__ = "fee_standards"

    __table_args__ = (
        Index("ix_fstd_category", "category"),
        Index("ix_fstd_region", "region"),
        Index("ix_fstd_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(
        String(100),
        nullable=False,
        comment="费用类别: equipment/meeting/travel/consulting/other",
    )
    name = Column(String(200), nullable=False, comment="标准名称")
    upper_limit = Column(Numeric(15, 4), nullable=False, comment="标准上限金额(万元)")
    unit = Column(String(50), default="万元", comment="计量单位")
    region = Column(String(100), nullable=True, comment="适用地区(空=全国)")
    industry = Column(String(100), nullable=True, comment="适用行业(空=通用)")
    description = Column(Text, nullable=True, comment="标准说明")
    legal_basis = Column(String(500), nullable=True, comment="法规依据")
    version = Column(Integer, default=1, comment="标准版本号")
    is_active = Column(Boolean, default=True, comment="是否启用")
    effective_date = Column(DateTime(timezone=True), nullable=True, comment="生效日期")
    expiry_date = Column(DateTime(timezone=True), nullable=True, comment="失效日期")
    created_by = Column(String(50), nullable=True, comment="创建人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FeeStandard(id={self.id}, category={self.category}, name={self.name})>"
