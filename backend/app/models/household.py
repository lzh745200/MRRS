"""一户一档数据模型（W22 契约 §1.1 / §1.2 / §1.3）。

三张表：

- ``Household``：建档户主档（帮扶村下一户一档），``is_active`` 为软删标记；
- ``HouseholdMember``：家庭成员，随户建档，``id_card`` 为 PII 透明加密列；
- ``HouseholdRiskRecord``：风险/预警记录（人工登记 + 关闭闭环）。

与 ``VillagePopulation`` 的关系：
    一户一档是**明细口径**，村年度人口是**汇总口径**。服务层
    ``rollup_to_village_population`` 按村把有效户数与成员数汇总回填到
    ``VillagePopulation`` 当年度行（总户数/总人口/脱贫户数/监测户数），
    幂等 upsert，不覆盖其它年度行。

数据域字段（organization_id / created_by）与全库一致：列表与点查统一经
``data_scope.filter_by_org_ids`` 收敛；PII 列（``helper_phone`` / ``id_card``）
只走 ORM 读写（EncryptedText），禁止裸 SQL 写入。
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
    UniqueConstraint,
)
from sqlalchemy.sql import func

from .base import Base, EncryptedText, UtcDateTime

# 高风险风险类型（命中即预警）
HIGH_RISK_TYPES = ("sudden", "multiple")


class Household(Base):
    """一户一档主档（帮扶村下的建档户）。"""

    __tablename__ = "households"

    __table_args__ = (
        # 户编号村内唯一（可空：SQLite/多数数据库允许多个 NULL）
        UniqueConstraint(
            "supported_village_id", "household_code", name="uq_households_village_code"
        ),
        Index("ix_households_village", "supported_village_id"),
        Index("ix_households_org", "organization_id"),
        Index("ix_households_risk_level", "risk_level"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    supported_village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属帮扶村ID",
    )
    household_code = Column(String(64), nullable=True, comment="户编号（村内唯一，可空）")
    household_name = Column(String(64), nullable=False, comment="户主姓名")
    address = Column(String(255), nullable=True, comment="详细地址")
    household_type = Column(
        String(20),
        nullable=False,
        default="general",
        server_default="general",
        comment="户类型: general=一般户 / poverty=脱贫户 / monitor=监测户",
    )
    risk_type = Column(
        String(32),
        nullable=False,
        default="none",
        server_default="none",
        comment="风险类型: none/income_drop/illness/housing/sudden/multiple",
    )
    risk_level = Column(
        String(10),
        nullable=False,
        default="low",
        server_default="low",
        comment="风险等级: low/medium/high",
    )
    helper_name = Column(String(64), nullable=True, comment="帮扶责任人")
    helper_phone = Column(
        EncryptedText(64), nullable=True, comment="帮扶责任人电话（PII 透明加密，ADR-0005）"
    )
    annual_income = Column(Numeric(14, 2), nullable=True, comment="户年收入(元)")
    migrant_workers = Column(Integer, nullable=True, default=0, comment="务工人数")
    has_serious_illness = Column(Boolean, nullable=False, default=False, comment="是否大病")
    housing_safe = Column(Boolean, nullable=False, default=True, comment="住房是否安全")
    last_visit_date = Column(Date, nullable=True, comment="最近走访日期（走访挂户时回写）")
    monitoring_note = Column(Text, nullable=True, comment="监测情况说明")

    # 数据域与软删（与全库一致）
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )
    created_by = Column(Integer, nullable=True, comment="创建者ID")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效（软删除标记）")
    deleted_at = Column(UtcDateTime(), nullable=True, comment="软删时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    @property
    def is_deleted(self) -> bool:
        """软删标记（与 is_active 互补，供 to_dict/响应模型读取）。"""
        return self.is_active is False

    def __repr__(self):
        return (
            f"<Household(id={self.id}, name={self.household_name}, "
            f"village={self.supported_village_id})>"
        )

    def to_dict(self) -> dict:
        """序列化为前端期望的 snake_case 结构（金额转 float、时间转 ISO）。"""
        return {
            "id": self.id,
            "supported_village_id": self.supported_village_id,
            "household_code": self.household_code,
            "household_name": self.household_name,
            "address": self.address,
            "household_type": self.household_type,
            "risk_type": self.risk_type,
            "risk_level": self.risk_level,
            "helper_name": self.helper_name,
            "helper_phone": self.helper_phone,
            "annual_income": float(self.annual_income) if self.annual_income is not None else None,
            "migrant_workers": self.migrant_workers,
            "has_serious_illness": bool(self.has_serious_illness),
            "housing_safe": bool(self.housing_safe),
            "last_visit_date": (
                self.last_visit_date.isoformat() if self.last_visit_date else None
            ),
            "monitoring_note": self.monitoring_note,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class HouseholdMember(Base):
    """家庭成员（隶属某个 Household）。"""

    __tablename__ = "household_members"

    __table_args__ = (
        Index("ix_household_members_household", "household_id"),
        Index("ix_household_members_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        Integer,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属户ID",
    )
    name = Column(String(64), nullable=False, comment="成员姓名")
    relation = Column(String(32), nullable=True, comment="与户主关系")
    id_card = Column(
        EncryptedText(64), nullable=True, comment="身份证号（PII 透明加密，ADR-0005）"
    )
    gender = Column(String(10), nullable=True, comment="性别")
    birth_year = Column(Integer, nullable=True, comment="出生年份")
    education = Column(String(32), nullable=True, comment="文化程度")
    health_status = Column(String(32), nullable=True, comment="健康状况：健康/慢性病/大病/残疾")
    employment_status = Column(
        String(32), nullable=True, comment="就业状态：务工/务农/学生/无劳动能力"
    )
    income = Column(Numeric(14, 2), nullable=True, comment="个人年收入(元)")
    is_special_support = Column(Boolean, nullable=False, default=False, comment="是否兜底保障对象")
    remarks = Column(String(500), nullable=True, comment="备注")

    # 数据域与软删
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID（随户继承）",
    )
    created_by = Column(Integer, nullable=True, comment="创建者ID")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效（软删除标记）")
    deleted_at = Column(UtcDateTime(), nullable=True, comment="软删时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    @property
    def is_deleted(self) -> bool:
        return self.is_active is False

    def __repr__(self):
        return f"<HouseholdMember(id={self.id}, name={self.name}, household={self.household_id})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "household_id": self.household_id,
            "name": self.name,
            "relation": self.relation,
            "id_card": self.id_card,
            "gender": self.gender,
            "birth_year": self.birth_year,
            "education": self.education,
            "health_status": self.health_status,
            "employment_status": self.employment_status,
            "income": float(self.income) if self.income is not None else None,
            "is_special_support": bool(self.is_special_support),
            "remarks": self.remarks,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class HouseholdRiskRecord(Base):
    """风险 / 预警记录（人工登记，支持关闭闭环）。"""

    __tablename__ = "household_risk_records"

    __table_args__ = (
        Index("ix_household_risk_records_household", "household_id"),
        Index("ix_household_risk_records_status", "status"),
        Index("ix_household_risk_records_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(
        Integer,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属户ID",
    )
    risk_type = Column(
        String(32),
        nullable=False,
        default="income_drop",
        server_default="income_drop",
        comment="风险类型: income_drop/illness/housing/sudden/multiple/none",
    )
    risk_level = Column(
        String(10),
        nullable=False,
        default="medium",
        server_default="medium",
        comment="风险等级: low/medium/high",
    )
    reason = Column(String(500), nullable=True, comment="风险原因/说明")
    detected_at = Column(
        UtcDateTime(), nullable=False, server_default=func.now(), comment="发现时间"
    )
    status = Column(
        String(10),
        nullable=False,
        default="open",
        server_default="open",
        comment="状态: open=处理中 / closed=已关闭",
    )
    closed_at = Column(UtcDateTime(), nullable=True, comment="关闭时间")
    closed_note = Column(String(500), nullable=True, comment="关闭说明")

    # 数据域与软删
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID（随户继承）",
    )
    created_by = Column(Integer, nullable=True, comment="创建者ID")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效（软删除标记）")
    deleted_at = Column(UtcDateTime(), nullable=True, comment="软删时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    @property
    def is_deleted(self) -> bool:
        return self.is_active is False

    def __repr__(self):
        return (
            f"<HouseholdRiskRecord(id={self.id}, risk_type={self.risk_type}, "
            f"status={self.status})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "household_id": self.household_id,
            "risk_type": self.risk_type,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "status": self.status,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "closed_note": self.closed_note,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
