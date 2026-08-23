# coding: utf-8
from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import BaseModel

from .supported_village import SupportedVillage  # noqa: F401 - relationship 字符串引用注册


class AnnualIncome(BaseModel):
    """年度收入数据"""

    __tablename__ = "annual_income"
    __table_args__ = (
        UniqueConstraint("supported_village_id", "year", name="uq_annual_income_year"),
        Index("ix_annual_income_village_id", "supported_village_id"),
        Index("ix_annual_income_village_year", "supported_village_id", "year"),
        {"extend_existing": True},
    )

    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="帮扶村ID",
    )
    year = Column(Integer, nullable=False, comment="年份")

    per_capita_income_2020 = Column(Numeric(15, 4), default=0, comment="人均纯收入_2020(万元)")
    per_capita_income_2021 = Column(Numeric(15, 4), default=0, comment="人均纯收入_2021(万元)")
    per_capita_income_2022 = Column(Numeric(15, 4), default=0, comment="人均纯收入_2022(万元)")
    per_capita_income_2023 = Column(Numeric(15, 4), default=0, comment="人均纯收入_2023(万元)")
    per_capita_income_2024 = Column(Numeric(15, 4), default=0, comment="人均纯收入_2024(万元)")
    per_capita_income_2025 = Column(Numeric(15, 4), default=0, comment="人均纯收入_2025(万元)")

    county_per_capita_income_2025 = Column(Numeric(15, 4), default=0, comment="县区人均收入_2025(万元)")

    village_collective_income_2020 = Column(Numeric(15, 4), default=0, comment="村集体收入_2020(万元)")
    village_collective_income_2021 = Column(Numeric(15, 4), default=0, comment="村集体收入_2021(万元)")
    village_collective_income_2022 = Column(Numeric(15, 4), default=0, comment="村集体收入_2022(万元)")
    village_collective_income_2023 = Column(Numeric(15, 4), default=0, comment="村集体收入_2023(万元)")
    village_collective_income_2024 = Column(Numeric(15, 4), default=0, comment="村集体收入_2024(万元)")
    village_collective_income_2025 = Column(Numeric(15, 4), default=0, comment="村集体收入_2025(万元)")

    village = relationship("SupportedVillage", backref="annual_income_data")

    def __repr__(self):
        return f"<AnnualIncome village_id={self.supported_village_id} year={self.year}>"
