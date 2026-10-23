# coding: utf-8
from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint
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

    # W27 P1（死字段清理，迁移 r40_prune_annual_industry_cols_001）：
    # 原有一批"年份写死进列名"的字段已移除 —— industry_investment_2025/2026/total、
    # industry_2025_planting_and_breeding / workshops / rural_tourism / other。
    # 与已删的 annual_income 同属一种反模式（每过一年要改模型），且全仓零引用；
    # 真正的行式明细在 industry_support（investment/planting_breeding/workshop/
    # rural_tourism/other_industry，按 year 分行）。
    # 本表保留的意义仅为"当年是否填报过"（effectiveness_service 用 COUNT(id) 判断）。

    village = relationship("SupportedVillage", backref="annual_industry_data")

    def __repr__(self):
        return f"<AnnualIndustry village_id={self.supported_village_id} year={self.year}>"
