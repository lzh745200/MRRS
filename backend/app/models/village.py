"""
村庄基础模型

包含村庄、村民、产业等基础实体。
"""

from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base, EncryptedText, TimestampMixin
from .industry import TeaPlantation, CactusFruitPlot  # noqa: F401 用于 back_populates 解析


class Village(Base, TimestampMixin):
    """村庄基础信息"""

    __tablename__ = "villages"

    __table_args__ = (
        Index("ix_village_name", "name"),
        Index("ix_village_county", "county"),
        Index("ix_village_organization", "organization_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="村庄名称")
    code = Column(String(50), nullable=True, unique=True, comment="村庄编码")
    province = Column(String(50), nullable=True, comment="省份")
    city = Column(String(50), nullable=True, comment="市/州")
    county = Column(String(50), nullable=True, comment="县/区")
    township = Column(String(100), nullable=True, comment="乡/镇")
    address = Column(String(500), nullable=True, comment="详细地址")

    # 地理信息
    longitude = Column(Float, nullable=True, comment="经度")
    latitude = Column(Float, nullable=True, comment="纬度")
    altitude = Column(Float, nullable=True, comment="海拔（米）")
    area_sq_km = Column(Float, nullable=True, comment="面积（平方公里）")

    # 民族与地貌
    ethnic_group = Column(String(100), nullable=True, comment="主要民族")
    is_ethnic_village = Column(Boolean, default=False, comment="是否少数民族村寨")
    karst_ratio = Column(Float, nullable=True, comment="喀斯特地貌比例（0.0-1.0）")
    terrain_type = Column(String(50), nullable=True, default="", comment="地形类型（喀斯特、丘陵、平原、山地等）")
    region_code = Column(String(20), nullable=True, comment="行政区划编码（关联 regions.code，用于数据权限前缀匹配）")

    # 组织关联
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )

    # 经济概况
    total_population = Column(Integer, nullable=True, comment="总人口")
    total_households = Column(Integer, nullable=True, comment="总户数")
    annual_income_per_capita = Column(Float, nullable=True, comment="人均年收入（元）")

    # 状态
    status = Column(String(50), nullable=True, default="active", comment="状态: active/inactive/developing/completed")
    is_active = Column(Boolean, default=True, comment="是否活跃")
    description = Column(Text, nullable=True, comment="备注说明")

    # 关系
    villagers = relationship("Villager", back_populates="village", cascade="all, delete-orphan")
    industries = relationship("Industry", back_populates="village", cascade="all, delete-orphan")
    # industry.py backref 需要显式声明以确保 selectinload 可用
    tea_plantations = relationship("TeaPlantation", back_populates="village", viewonly=True)
    cactus_fruit_plots = relationship("CactusFruitPlot", back_populates="village", viewonly=True)

    def __repr__(self):
        return f"<Village(id={self.id}, name={self.name})>"


class Villager(Base, TimestampMixin):
    """村民信息"""

    __tablename__ = "villagers"

    __table_args__ = (
        Index("ix_villager_village", "village_id"),
        Index("ix_villager_name", "name"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="CASCADE"), nullable=False, comment="所属村庄ID")
    name = Column(String(100), nullable=False, comment="姓名")
    id_card = Column(EncryptedText(64), nullable=True, comment="身份证号(透明加密, ADR-0005)")
    phone = Column(EncryptedText(64), nullable=True, comment="电话(透明加密, ADR-0005)")
    gender = Column(String(10), nullable=True, comment="性别")
    age = Column(Integer, nullable=True, comment="年龄")
    occupation = Column(String(100), nullable=True, comment="职业")
    is_household_head = Column(Boolean, default=False, comment="是否户主")
    is_poverty = Column(Boolean, default=False, comment="是否贫困户")
    description = Column(Text, nullable=True, comment="备注")

    # 关系
    village = relationship("Village", back_populates="villagers")

    def __repr__(self):
        return f"<Villager(id={self.id}, name={self.name})>"


class Industry(Base, TimestampMixin):
    """村庄产业信息"""

    __tablename__ = "industries"

    __table_args__ = (
        Index("ix_industry_village", "village_id"),
        Index("ix_industry_type", "industry_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="CASCADE"), nullable=False, comment="所属村庄ID")
    name = Column(String(200), nullable=False, comment="产业名称")
    industry_type = Column(String(100), nullable=True, comment="产业类型（种植、养殖、加工等）")
    scale = Column(String(100), nullable=True, comment="规模")
    annual_output = Column(Float, nullable=True, comment="年产值（万元）")
    employed_count = Column(Integer, nullable=True, comment="带动就业人数")
    is_featured = Column(Boolean, default=False, comment="是否特色产业")
    description = Column(Text, nullable=True, comment="备注")

    # 关系
    village = relationship("Village", back_populates="industries")

    def __repr__(self):
        return f"<Industry(id={self.id}, name={self.name})>"
