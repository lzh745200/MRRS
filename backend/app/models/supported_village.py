"""
帮扶村及相关支持模型

包含:
- SupportedVillage: 帮扶村基本信息
- VillagePopulation: 村级人口数据
- VillageIncome: 村级收入数据
- ForceInvestment: 专项投入
- IndustrySupport: 产业帮扶
- InfrastructureImprovement: 基础设施改善
- PartyBuildingSupport: 党建帮扶
- MedicalSupport: 医疗帮扶
- ConsumptionSupport: 消费帮扶
- EmploymentSupport: 就业帮扶
- EducationSupport: 教育帮扶
- SupportFunding: 帮扶经费
- ReportSubscription: 报表订阅
"""

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


# ══════════════════════════════════════════════════════════════
#  帮扶村基本信息
# ══════════════════════════════════════════════════════════════


class SupportedVillage(Base, TimestampMixin):
    """帮扶村基本信息"""

    __tablename__ = "supported_villages"

    __table_args__ = (
        Index("ix_supported_villages_province", "province"),
        Index("ix_supported_villages_organization_id", "organization_id"),
        Index("ix_supported_villages_created_by", "created_by"),
        Index("ix_supported_villages_department", "department"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sequence_no = Column(Integer, nullable=True, comment="序号")
    department = Column(String(200), nullable=True, comment="部门单位")
    support_unit = Column(String(200), nullable=True, comment="帮扶单位")
    village_name = Column(String(200), nullable=False, comment="帮扶村名称")
    province = Column(String(50), default="贵州省", comment="省份")
    city = Column(String(50), nullable=True, comment="城市")
    county = Column(String(50), nullable=True, comment="县/市")
    township = Column(String(50), nullable=True, comment="乡镇")
    region_scope = Column(String(100), nullable=True, comment="地区范围")
    latitude = Column(Float, nullable=True, comment="纬度")
    longitude = Column(Float, nullable=True, comment="经度")

    # 区域标记
    is_three_regions = Column(Boolean, default=False, comment="是否三区三州")
    is_border_area = Column(Boolean, default=False, comment="是否边疆地区")
    is_ethnic_area = Column(Boolean, default=False, comment="是否民族地区")
    is_revolutionary_area = Column(Boolean, default=False, comment="是否革命地区")
    is_key_county = Column(Boolean, default=False, comment="是否重点帮扶县")

    # 振兴发展
    is_revitalization_tier = Column(Boolean, default=False, comment="是否振兴梯队")
    is_provincial_demo = Column(Boolean, default=False, comment="是否省级示范")
    is_hundred_village_demo = Column(Boolean, default=False, comment="是否百村示范")
    is_tiered_development = Column(Boolean, default=False, comment="是否梯次振兴")
    transition_status = Column(
        String(20), default="none",
        comment="过渡状态: none/entering/in_transition/exiting/completed"
    )

    # 跨区域标记
    is_cross_province = Column(Boolean, default=False, comment="是否跨省帮扶")
    is_cross_city = Column(Boolean, default=False, comment="是否跨市帮扶")
    is_cross_unit_cooperation = Column(Boolean, default=False, comment="是否跨单位协作")
    is_in_overall_plan = Column(Boolean, default=False, comment="是否纳入总盘子")

    # 帮扶经费汇总
    transition_fund_military_total = Column(
        Float, default=0, comment="专项投入(万元)"
    )
    transition_fund_local_total = Column(
        Float, default=0, comment="协调地方投入(万元)"
    )
    transition_fund_items = Column(
        Text, default="[]", comment="帮扶经费按年度明细(JSON)"
    )

    honors = Column(String(2000), nullable=True, comment="获得表彰情况")

    # 软删标记（与 School/Project 一致，is_active=False 表示已删除）
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用(软删标记)")

    # 外键
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )
    region_code = Column(
        String(20),
        nullable=True,
        comment="行政区划编码（关联 regions.code，用于数据权限前缀匹配）",
    )
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者ID",
    )

    # ── 关系 ──
    population_data = relationship(
        "VillagePopulation",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    income_data = relationship(
        "VillageIncome",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    force_investment_data = relationship(
        "ForceInvestment",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    industry_support_data = relationship(
        "IndustrySupport",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    infrastructure_data = relationship(
        "InfrastructureImprovement",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    party_building_data = relationship(
        "PartyBuildingSupport",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    medical_support_data = relationship(
        "MedicalSupport",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    consumption_support_data = relationship(
        "ConsumptionSupport",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    employment_support_data = relationship(
        "EmploymentSupport",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    education_support_data = relationship(
        "EducationSupport",
        back_populates="village",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    funds = relationship(
        "Fund",
        back_populates="village",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        """序列化为前端期望的 camelCase 格式，同时返回 snake_case 别名以兼容历史前端代码"""
        return {
            "id": self.id,
            "sequenceNo": self.sequence_no,
            "sequence_no": self.sequence_no,
            "department": self.department,
            "supportUnit": self.support_unit,
            "support_unit": self.support_unit,
            "villageName": self.village_name,
            "village_name": self.village_name,
            "province": self.province,
            "city": self.city,
            "county": self.county,
            "township": self.township,
            "regionScope": self.region_scope,
            "region_scope": self.region_scope,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "isThreeRegions": self.is_three_regions or False,
            "is_three_regions": self.is_three_regions or False,
            "isBorderArea": self.is_border_area or False,
            "is_border_area": self.is_border_area or False,
            "isEthnicArea": self.is_ethnic_area or False,
            "is_ethnic_area": self.is_ethnic_area or False,
            "isRevolutionaryArea": self.is_revolutionary_area or False,
            "is_revolutionary_area": self.is_revolutionary_area or False,
            "isKeyCounty": self.is_key_county or False,
            "is_key_county": self.is_key_county or False,
            "isRevitalizationTier": self.is_revitalization_tier or False,
            "is_revitalization_tier": self.is_revitalization_tier or False,
            "isProvincialDemo": self.is_provincial_demo or False,
            "is_provincial_demo": self.is_provincial_demo or False,
            "isHundredVillageDemo": self.is_hundred_village_demo or False,
            "is_hundred_village_demo": self.is_hundred_village_demo or False,
            "isTieredDevelopment": self.is_tiered_development or False,
            "is_tiered_development": self.is_tiered_development or False,
            "isCrossProvince": self.is_cross_province or False,
            "is_cross_province": self.is_cross_province or False,
            "isCrossCity": self.is_cross_city or False,
            "is_cross_city": self.is_cross_city or False,
            "isCrossUnitCooperation": self.is_cross_unit_cooperation or False,
            "is_cross_unit_cooperation": self.is_cross_unit_cooperation or False,
            "isInOverallPlan": self.is_in_overall_plan or False,
            "is_in_overall_plan": self.is_in_overall_plan or False,
            "honors": self.honors or "",
            "transitionFundMilitaryTotal": self.transition_fund_military_total or 0,
            "transition_fund_military_total": self.transition_fund_military_total or 0,
            "transitionFundLocalTotal": self.transition_fund_local_total or 0,
            "transition_fund_local_total": self.transition_fund_local_total or 0,
            "isDeleted": self.is_active is False,
            "is_deleted": self.is_active is False,
            "organizationId": self.organization_id,
            "organization_id": self.organization_id,
            "createdBy": self.created_by,
            "created_by": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def name(self) -> str:
        """village_name 的别名 property。

        防御性措施：历史代码中存在误用 ``village.name`` 访问帮扶村名称的
        情形（实际字段为 ``village_name``）。提供此别名可避免 AttributeError
        导致 500 错误，同时保持向后兼容。
        """
        return self.village_name

    @name.setter
    def name(self, value: str) -> None:
        """允许通过 .name 设置 village_name（双向兼容）。"""
        self.village_name = value

    def __repr__(self):
        return f"<SupportedVillage(id={self.id}, name={self.village_name})>"


# ══════════════════════════════════════════════════════════════
#  村级年度数据模型（共用模式: village FK + year + 业务字段）
# ══════════════════════════════════════════════════════════════


class VillagePopulation(Base, TimestampMixin):
    """村级人口数据"""

    __tablename__ = "village_population"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_village_population_year"
        ),
        Index("ix_village_population_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="帮扶村ID",
    )
    year = Column(Integer, nullable=False, comment="年份")

    total_households = Column(Integer, default=0, comment="总户数")
    total_population = Column(Integer, default=0, comment="总人数")
    resident_population = Column(Integer, default=0, comment="常住人口")
    labor_force = Column(Integer, default=0, comment="劳动力")
    migrant_workers = Column(Integer, default=0, comment="外出务工人数")
    poverty_population = Column(Integer, default=0, comment="脱贫人口")
    poverty_households = Column(Integer, default=0, comment="脱贫户数")
    unstable_poverty_households = Column(Integer, default=0, comment="脱贫不稳定户(户)")
    unstable_poverty_population = Column(Integer, default=0, comment="脱贫不稳定户(人)")
    marginal_poverty_households = Column(Integer, default=0, comment="边缘易致贫户(户)")
    marginal_poverty_population = Column(Integer, default=0, comment="边缘易致贫户(人)")
    sudden_difficulty_households = Column(
        Integer, default=0, comment="突发严重困难户(户)"
    )
    sudden_difficulty_population = Column(
        Integer, default=0, comment="突发严重困难户(人)"
    )
    veteran_village_secretary = Column(
        Integer, default=0, comment="村支书(退役人员)"
    )
    veteran_village_committee = Column(
        Integer, default=0, comment="村委员(退役人员)"
    )

    village = relationship("SupportedVillage", back_populates="population_data")

    def __repr__(self):
        return f"<VillagePopulation(id={self.id}, village={self.supported_village_id}, year={self.year})>"


class VillageIncome(Base, TimestampMixin):
    """村级收入数据"""

    __tablename__ = "village_income"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_village_income_year"
        ),
        Index("ix_village_income_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="帮扶村ID",
    )
    year = Column(Integer, nullable=False, comment="年份")

    per_capita_income = Column(Float, default=0, comment="村人均纯收入(万元)")
    county_per_capita_income = Column(Float, default=0, comment="县区人均纯收入(万元)")
    collective_income = Column(Float, default=0, comment="村集体收入(万元)")

    village = relationship("SupportedVillage", back_populates="income_data")

    def __repr__(self):
        return f"<VillageIncome(id={self.id}, village={self.supported_village_id}, year={self.year})>"


# ══════════════════════════════════════════════════════════════
#  帮扶支持类模型
# ══════════════════════════════════════════════════════════════


class ForceInvestment(Base, TimestampMixin):
    """专项投入"""

    __tablename__ = "force_investment"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_force_investment_year"
        ),
        Index("ix_force_investment_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    senior_leader_visits = Column(Integer, default=0, comment="上级领导到村(人次)")
    unit_soldier_visits = Column(Integer, default=0, comment="帮扶单位人员到村(人次)")

    village = relationship("SupportedVillage", back_populates="force_investment_data")


class IndustrySupport(Base, TimestampMixin):
    """产业帮扶"""

    __tablename__ = "industry_support"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_industry_support_year"
        ),
        Index("ix_industry_support_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    investment = Column(Float, default=0, comment="当年投入(万元)")
    planned_investment = Column(Float, default=0, comment="计划投入(万元)")
    planting_breeding = Column(Integer, default=0, comment="种植养殖(个)")
    workshop = Column(Integer, default=0, comment="帮扶车间(个)")
    rural_tourism = Column(Integer, default=0, comment="乡村旅游(个)")
    other_industry = Column(Integer, default=0, comment="其他(个)")

    village = relationship("SupportedVillage", back_populates="industry_support_data")


class InfrastructureImprovement(Base, TimestampMixin):
    """基础设施改善"""

    __tablename__ = "infrastructure_improvement"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id",
            "year",
            name="uq_infrastructure_improvement_year",
        ),
        Index("ix_infrastructure_improvement_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    investment = Column(Float, default=0, comment="当年投入(万元)")
    planned_investment = Column(Float, default=0, comment="计划投入(万元)")
    road_km = Column(Float, default=0, comment="乡村道路(公里)")
    housing_renovation = Column(Integer, default=0, comment="住房改造(户)")
    water_facilities = Column(Integer, default=0, comment="水利设施(个)")
    cultural_plaza = Column(Integer, default=0, comment="文化广场(个)")
    library_cafe = Column(Integer, default=0, comment="书屋网吧(个)")

    village = relationship(
        "SupportedVillage", back_populates="infrastructure_data"
    )


class PartyBuildingSupport(Base, TimestampMixin):
    """党建帮扶"""

    __tablename__ = "party_building_support"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id",
            "year",
            name="uq_party_building_support_year",
        ),
        Index("ix_party_building_support_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    investment = Column(Float, default=0, comment="党建投入(万元)")
    planned_investment = Column(Float, default=0, comment="计划投入(万元)")
    paired_branches = Column(Integer, default=0, comment="结对帮扶村党支部(个)")
    party_instructors = Column(Integer, default=0, comment="兼职党建指导员(人)")
    joint_activities = Column(Integer, default=0, comment="联建共促活动(次)")
    civilization_activities = Column(Integer, default=0, comment="乡风文明活动(次)")

    village = relationship(
        "SupportedVillage", back_populates="party_building_data"
    )


class MedicalSupport(Base, TimestampMixin):
    """医疗帮扶"""

    __tablename__ = "medical_support"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_medical_support_year"
        ),
        Index("ix_medical_support_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    investment = Column(Float, default=0, comment="医疗投入(万元)")
    planned_investment = Column(Float, default=0, comment="计划投入(万元)")
    clinics_built = Column(Integer, default=0, comment="帮建卫生院室(个)")
    patients_served = Column(Integer, default=0, comment="巡诊群众(人次)")

    village = relationship("SupportedVillage", back_populates="medical_support_data")


class ConsumptionSupport(Base, TimestampMixin):
    """消费帮扶"""

    __tablename__ = "consumption_support"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_consumption_support_year"
        ),
        Index("ix_consumption_support_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    village_products_purchase = Column(
        Float, default=0, comment="采购帮扶村产品(万元)"
    )
    other_products_purchase = Column(Float, default=0, comment="采购其他产品(万元)")
    sales_counters = Column(Integer, default=0, comment="营区销售专柜(个)")
    benefited_population = Column(Integer, default=0, comment="惠及群众(人)")

    village = relationship(
        "SupportedVillage", back_populates="consumption_support_data"
    )


class EmploymentSupport(Base, TimestampMixin):
    """就业帮扶"""

    __tablename__ = "employment_support"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_employment_support_year"
        ),
        Index("ix_employment_support_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    hired_population = Column(Integer, default=0, comment="聘用群众(人)")
    trained_population = Column(Integer, default=0, comment="培训人数(人次)")
    recommended_employment = Column(Integer, default=0, comment="推荐就业(人次)")

    village = relationship(
        "SupportedVillage", back_populates="employment_support_data"
    )


class EducationSupport(Base, TimestampMixin):
    """教育帮扶"""

    __tablename__ = "education_support"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_education_support_year"
        ),
        Index("ix_education_support_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    investment = Column(Float, default=0, comment="教育投入(万元)")
    donated_schools = Column(Integer, default=0, comment="捐赠学校(所)")
    aided_external_schools = Column(Integer, default=0, comment="援建学校(所)")
    education_activities = Column(Integer, default=0, comment="助学活动(次)")
    aided_students = Column(Integer, default=0, comment="资助学生(人)")
    volunteer_counselors = Column(Integer, default=0, comment="兼职辅导员(人)")

    village = relationship(
        "SupportedVillage", back_populates="education_support_data"
    )


# ══════════════════════════════════════════════════════════════
#  帮扶经费 & 梯次发展
# ══════════════════════════════════════════════════════════════


class SupportFunding(Base, TimestampMixin):
    """帮扶经费（过渡期经费跟踪）"""

    __tablename__ = "support_funding"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id",
            "year",
            "funding_type",
            name="uq_support_funding_year_type",
        ),
        Index("ix_support_funding_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    funding_type = Column(String(50), default="transition", comment="经费类型")
    military_investment = Column(Float, default=0, comment="专项投入(万元)")
    local_investment = Column(Float, default=0, comment="地方投入(万元)")
    planned_investment = Column(Float, default=0, comment="计划投入(万元)")


# ══════════════════════════════════════════════════════════════
#  报表订阅
# ══════════════════════════════════════════════════════════════


class ReportSubscription(Base, TimestampMixin):
    """报表订阅"""

    __tablename__ = "report_subscriptions"

    __table_args__ = (
        Index("ix_report_subscriptions_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    name = Column(String(200), nullable=False, comment="订阅名称")
    report_type = Column(String(50), nullable=False, comment="报表类型")
    format = Column(String(20), default="xlsx", comment="导出格式")
    year = Column(Integer, nullable=True, comment="年份")
    village_ids = Column(Text, nullable=True, comment="村庄ID列表(JSON)")
    include_sections = Column(Text, nullable=True, comment="包含章节(JSON)")
    frequency = Column(String(20), default="weekly", comment="发送频率")
    send_day = Column(Integer, nullable=True, comment="发送日期")
    send_time = Column(String(10), nullable=True, comment="发送时间")
    email = Column(String(200), nullable=True, comment="接收邮箱（单机版保留兼容，未来联网可恢复）")
    output_dir = Column(String(500), nullable=True, comment="本地输出目录（单机版使用）")
    output_format = Column(String(20), default="pdf", comment="输出格式: pdf/excel")
    is_active = Column(Boolean, default=True, comment="是否启用")


# ══════════════════════════════════════════════════════════════
#  村委会信息 & 成员
# ══════════════════════════════════════════════════════════════


class VillageCommitteeInfo(Base, TimestampMixin):
    """村委会信息"""

    __tablename__ = "village_committee_info"

    __table_args__ = (
        UniqueConstraint(
            "supported_village_id", "year", name="uq_village_committee_info_year"
        ),
        Index("ix_village_committee_info_village_id", "supported_village_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    year = Column(Integer, nullable=False, comment="年份")
    overview = Column(Text, nullable=True, comment="村委会概况")
    special_industry = Column(String(200), nullable=True, comment="特色产业")
    collective_income_desc = Column(String(500), nullable=True, comment="集体收入描述")
    collective_income_amount = Column(Float, default=0, comment="集体收入金额(万元)")

    members = relationship(
        "VillageCommitteeMember",
        back_populates="committee_info",
        cascade="all, delete-orphan",
    )


class VillageCommitteeMember(Base, TimestampMixin):
    """村委会成员"""

    __tablename__ = "village_committee_members"

    __table_args__ = (
        Index("ix_village_committee_members_village_id", "supported_village_id"),
        Index("ix_village_committee_members_info_id", "committee_info_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    committee_info_id = Column(
        Integer,
        ForeignKey("village_committee_info.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(String(100), nullable=False, comment="姓名")
    position = Column(String(50), nullable=True, comment="职务")
    phone = Column(String(20), nullable=True, comment="电话")
    is_veteran = Column(Boolean, default=False, comment="是否退役人员")
    remark = Column(String(500), nullable=True, comment="备注")

    committee_info = relationship("VillageCommitteeInfo", back_populates="members")


# ══════════════════════════════════════════════════════════════
#  帮扶村附件
# ══════════════════════════════════════════════════════════════


class VillageAttachment(Base, TimestampMixin):
    """帮扶村附件文件"""

    __tablename__ = "village_attachments"

    __table_args__ = (
        Index("ix_village_attachments_village_id", "supported_village_id"),
        Index("ix_village_attachments_created_by", "created_by"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="存储路径")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    mime_type = Column(String(100), nullable=True, comment="MIME类型")
    description = Column(String(500), nullable=True, comment="文件描述")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="上传者ID",
    )


# 确保 Fund 模型已注册至 SQLAlchemy 映射器注册表，
# 以便 SupportedVillage.funds relationship("Fund", ...) 能解析。
# 放在文件末尾以避免循环导入。
from .fund import Fund  # noqa: E402, F401
