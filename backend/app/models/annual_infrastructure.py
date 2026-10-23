# coding: utf-8
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
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

    # W27 P1（死字段清理，迁移 r39_prune_annual_infra_cols_001）：
    # 原有一批"年份写死进列名"的字段已移除 —— infrastructure_investment_2025/2026/total、
    # road_km_2025、housing_renovations_2025、water_facilities_2025、cultural_squares_2025、
    # bookhouses_internet_cubs_2025、other_infrastructure_2025。
    # 它们与已删的 annual_income 是同一反模式（每过一年就得改模型），且全仓零引用；
    # 真正的行式明细在 infrastructure_improvement（investment/road_km/housing_renovation/
    # water_facilities/cultural_plaza/library_cafe，按 year 分行）。
    # 本表保留的意义仅为"当年是否填报过"（effectiveness_service 用 COUNT(id) 判断）。

    village = relationship("SupportedVillage", backref="annual_infrastructure_data")

    def __repr__(self):
        return f"<AnnualInfrastructure village_id={self.supported_village_id} year={self.year}>"
