"""
RuralWork Model
"""

from enum import Enum

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.village import Village  # noqa: F401 — RuralWork.village relationship target

from .user import User  # noqa: F401 - relationship 字符串引用注册


class WorkType(str, Enum):
    infrastructure = "infrastructure"
    industry = "industry"
    education = "education"
    healthcare = "healthcare"
    environment = "environment"


class WorkStatus(str, Enum):
    pending = "pending"
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    delayed = "delayed"


class RuralWork(Base):
    __tablename__ = "rural_works"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=True)
    name = Column(String(200), nullable=False)
    type = Column(
        SQLEnum(WorkType, native_enum=False),
        default=WorkType.infrastructure,
        nullable=False,
    )
    status = Column(
        SQLEnum(WorkStatus, native_enum=False),
        default=WorkStatus.planned,
        nullable=False,
    )
    village_id = Column(Integer, ForeignKey("villages.id", ondelete="CASCADE"), nullable=True)
    responsible_person = Column(String(50), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    target = Column(Text, nullable=True)
    progress = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True,
        comment="所属组织ID（数据权限隔离；历史数据为空时按创建人过滤）",
    )

    village = relationship("Village", backref="rural_works")
    creator = relationship("User", foreign_keys=[created_by], backref="created_rural_works")
    updater = relationship("User", foreign_keys=[updated_by], backref="updated_rural_works")

    __table_args__ = (
        Index("ix_rural_works_type", "type"),
        Index("ix_rural_works_status", "status"),
        Index("ix_rural_works_village_id", "village_id"),
    )
