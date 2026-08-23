# coding: utf-8
from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import BaseModel

from .supported_village import SupportedVillage  # noqa: F401 - relationship 字符串引用注册


class AnnualIndustry(BaseModel):
    """年度产业投入数据"""

    __tablename__ = "annual_industry"
    __table_args__ = (
        UniqueConstraint("supported_village_id", "year", name="uq_annual_industry_year"),
        Index("ix_annual_industry_village_id", "supported_village_id"),
        {"extend_existing": True},
    )

    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="帮扶村ID",
    )
    year = Column(Integer, nullable=False, comment="年份")

    industry_investment_2025 = Column(Numeric(15, 4), default=0, comment="产业投入_2025")
    industry_investment_2026 = Column(Numeric(15, 4), default=0, comment="产业投入_2026")
    industry_investment_total = Column(Numeric(15, 4), default=0, comment="产业投入合计")

    industry_2025_planting_and_breeding = Column(Integer, default=0, comment="2025年种植养殖")
    industry_2025_workshops = Column(Integer, default=0, comment="2025年帮扶车间")
    industry_2025_rural_tourism = Column(Integer, default=0, comment="2025年乡村旅游")
    industry_2025_other = Column(Integer, default=0, comment="2025年其他")

    village = relationship("SupportedVillage", backref="annual_industry_data")

    def __repr__(self):
        return f"<AnnualIndustry village_id={self.supported_village_id} year={self.year}>"
