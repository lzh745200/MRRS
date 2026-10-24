"""
特色产业模型 - 贵州省版

包含贵州省特色农业产业实体：
- TeaPlantation: 茶园（都匀毛尖、贵定云雾等）
- CactusFruitPlot: 刺梨园
- 喀斯特地貌关联算法
"""

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, Text

from .base import Base, TimestampMixin


class TeaPlantation(Base, TimestampMixin):
    """
    茶园实体

    贵州省是中国重要的茶叶产区，以都匀毛尖、贵定云雾茶闻名。
    茶园数据关联村庄，记录品种、面积、产量及喀斯特地貌影响因子。
    """

    __tablename__ = "tea_plantations"

    __table_args__ = (
        Index("ix_tea_supported_village_id", "supported_village_id"),
        Index("ix_tea_harvest_year", "harvest_year"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # W22 起库里已改名为 supported_village_id（FK→supported_villages.id），
    # 但模型一直留在旧名 village_id —— 这正是三层对齐门禁报出的模型/库漂移
    # （r42_align_stack_columns_001 的 downgrade/upgrade 均按 supported_village_id 操作）。
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属帮扶村ID（W22：原 villages.id 改为 supported_villages.id）",
    )
    name = Column(String(100), nullable=False, comment="茶园名称")
    area_mu = Column(Float, default=0, comment="面积（亩）")
    tea_variety = Column(String(100), nullable=True, comment="品种（都匀毛尖、贵定云雾等）")
    altitude = Column(Float, nullable=True, comment="海拔（米）")
    annual_yield_kg = Column(Float, default=0, comment="年产量（公斤）")
    harvest_year = Column(Integer, nullable=True, comment="采收年份")
    karst_soil_moisture = Column(
        Float, nullable=True, comment="喀斯特土壤湿度指数（0.0-1.0）"
    )
    quality_score = Column(Float, nullable=True, comment="品质评分（1-10）")
    description = Column(Text, nullable=True, comment="备注说明")

    def __repr__(self):
        return f"<TeaPlantation(id={self.id}, name={self.name}, variety={self.tea_variety})>"

    def calculate_quality(self) -> float:
        """计算茶叶品质评分（基于海拔和土壤湿度）"""
        if self.altitude is None or self.karst_soil_moisture is None:
            return 0.0
        return calculate_tea_quality(self.altitude, self.karst_soil_moisture)


class CactusFruitPlot(Base, TimestampMixin):
    """
    刺梨园实体

    刺梨是贵州省特有水果，黔南州是主要产区。
    刺梨耐旱耐瘠，适合喀斯特地貌种植。
    """

    __tablename__ = "cactus_fruit_plots"

    __table_args__ = (
        Index("ix_cactus_supported_village_id", "supported_village_id"),
        Index("ix_cactus_harvest_year", "harvest_year"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属帮扶村ID（W22：原 villages.id 改为 supported_villages.id）",
    )
    name = Column(String(100), nullable=False, comment="园区名称")
    area_mu = Column(Float, default=0, comment="面积（亩）")
    plant_density = Column(Integer, nullable=True, comment="种植密度（株/亩）")
    annual_yield_kg = Column(Float, default=0, comment="年产量（公斤）")
    harvest_year = Column(Integer, nullable=True, comment="采收年份")
    karst_adaptation_score = Column(
        Float, nullable=True, comment="喀斯特适应性评分（1-10）"
    )
    slope_degree = Column(Float, nullable=True, comment="坡度（度）")
    soil_depth_cm = Column(Float, nullable=True, comment="土层厚度（厘米）")
    annual_rainfall_mm = Column(Float, nullable=True, comment="年降雨量（毫米）")
    description = Column(Text, nullable=True, comment="备注说明")

    def __repr__(self):
        return f"<CactusFruitPlot(id={self.id}, name={self.name})>"

    def calculate_adaptation(self) -> float:
        """计算喀斯特适应性评分"""
        if (
            self.slope_degree is None
            or self.soil_depth_cm is None
            or self.annual_rainfall_mm is None
        ):
            return 0.0
        return calculate_karst_adaptation(
            self.slope_degree, self.soil_depth_cm, self.annual_rainfall_mm
        )


# ==================== 喀斯特地貌关联算法 ====================


def calculate_tea_quality(altitude: float, soil_moisture: float) -> float:
    """
    计算茶叶品质评分。

    算法原理：
    - 海拔因子：800m以上为优质茶区，黔南州平均海拔1000m+
    - 土壤湿度因子：喀斯特地貌漏水特性导致土壤偏干，
      适度干燥有利于茶叶芳香物质积累

    Args:
        altitude: 海拔（米），黔南州范围 400-1800m
        soil_moisture: 喀斯特土壤湿度指数（0.0-1.0）

    Returns:
        品质评分（1.0-10.0）
    """
    # 海拔因子：400m起算，每80m增加1分，上限10分
    altitude_score = min(10.0, max(1.0, (altitude - 400) / 80))

    # 湿度因子：喀斯特漏水导致偏干，适度干燥（0.2-0.4）最佳
    # 湿度越低（干燥），茶叶品质越好（香气浓郁）
    moisture_score = max(1.0, 10.0 - soil_moisture * 8.0)

    # 综合评分（海拔权重60%，湿度权重40%）
    score = altitude_score * 0.6 + moisture_score * 0.4
    return round(min(10.0, max(1.0, score)), 2)


def calculate_karst_adaptation(
    slope: float, soil_depth: float, rainfall: float
) -> float:
    """
    计算刺梨的喀斯特地貌适应性评分。

    算法原理：
    - 刺梨耐旱耐瘠薄，适合15-35度坡地种植
    - 土层厚度影响根系发育
    - 年降雨800-1200mm为最适宜区（黔南州年均1100mm）

    Args:
        slope: 坡度（度）
        soil_depth: 土层厚度（厘米）
        rainfall: 年降雨量（毫米）

    Returns:
        适应性评分（1.0-10.0）
    """
    # 坡度因子：25度为最适宜，偏离越远评分越低
    slope_score = max(1.0, 10.0 - abs(slope - 25.0) / 3.0)

    # 土层因子：刺梨耐瘠薄，30cm以上即可良好生长
    depth_score = min(10.0, max(1.0, soil_depth / 5.0))

    # 降雨因子：1000mm为最适宜，偏离越远评分越低
    rain_score = max(1.0, 10.0 - abs(rainfall - 1000.0) / 100.0)

    # 综合评分（三项等权重）
    score = (slope_score + depth_score + rain_score) / 3.0
    return round(min(10.0, max(1.0, score)), 2)
