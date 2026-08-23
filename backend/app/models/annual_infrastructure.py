# coding: utf-8
from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import BaseModel

from .supported_village import SupportedVillage  # noqa: F401 - relationship 字符串引用注册


class AnnualInfrastructure(BaseModel):
    """年度基础设施投入及明细"""

    __tablename__ = "annual_infrastructure"
    __table_args__ = (
        UniqueConstraint("supported_village_id", "year", name="uq_annual_infrastructure_year"),
        Index("ix_annual_infrastructure_village_id", "supported_village_id"),
        {"extend_existing": True},
    )

    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="帮扶村ID",
    )
    year = Column(Integer, nullable=False, comment="年份")

    infrastructure_investment_2025 = Column(Numeric(15, 4), default=0, comment="基础设施投入_2025")
    infrastructure_investment_2026 = Column(Numeric(15, 4), default=0, comment="基础设施投入_2026")
    infrastructure_investment_total = Column(Numeric(15, 4), default=0, comment="基础设施投入总计")

    road_km_2025 = Column(Float, default=0, comment="乡村道路公里_2025")
    housing_renovations_2025 = Column(Integer, default=0, comment="住房改造_2025")
    water_facilities_2025 = Column(Integer, default=0, comment="水利设施_2025")
    cultural_squares_2025 = Column(Integer, default=0, comment="文化广场_2025")
    bookhouses_internet_cubs_2025 = Column(Integer, default=0, comment="书屋/网吧_2025")
    other_infrastructure_2025 = Column(Integer, default=0, comment="其他_2025")

    village = relationship("SupportedVillage", backref="annual_infrastructure_data")

    def __repr__(self):
        return f"<AnnualInfrastructure village_id={self.supported_village_id} year={self.year}>"
