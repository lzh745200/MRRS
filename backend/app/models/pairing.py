"""结对帮扶与走访台账数据模型

- ``PairingRecord``：结对记录（帮扶主体 ↔ 帮扶对象），台账主表；
- ``VisitRecord``：走访记录，一次走访一行，挂在结对记录下（软删除独立）。

数据域字段（organization_id / created_by）与全库一致，
列表查询经 ``data_scope.filter_by_org_ids`` 过滤。
"""

from sqlalchemy import Boolean, Column, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base, UtcDateTime

# 帮扶主体类型：单位 / 党支部 / 个人（帮扶干部）
SUBJECT_TYPES = ("unit", "branch", "person")
# 帮扶对象类型：帮扶村 / 帮扶学校 / 困难学生
PARTNER_TYPES = ("village", "school", "student")
# 结对状态：帮扶中 / 已结束
PAIRING_STATUSES = ("active", "ended")


class PairingRecord(Base):
    """结对帮扶记录（台账主表）"""

    __tablename__ = "pairing_records"

    __table_args__ = (
        Index("ix_pairing_records_partner", "partner_type", "village_id", "school_id"),
        Index("ix_pairing_records_subject", "subject_type", "subject_name"),
        Index("ix_pairing_records_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_type = Column(String(16), nullable=False, comment="帮扶主体类型: unit/branch/person")
    subject_name = Column(
        String(128), nullable=False, comment="帮扶主体名称（单位名/支部名/干部姓名）"
    )
    subject_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联系统用户（帮扶干部本人，可空）",
    )
    partner_type = Column(String(16), nullable=False, comment="帮扶对象类型: village/school/student")
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="SET NULL"),
        nullable=True,
        comment="帮扶村ID（对象为帮扶村时必填）",
    )
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        comment="帮扶学校ID（对象为帮扶学校时必填）",
    )
    student_name = Column(String(64), nullable=True, comment="困难学生姓名（对象为学生时必填）")
    title = Column(String(200), nullable=False, comment="帮扶事项")
    content = Column(Text, comment="帮扶内容与计划")
    start_date = Column(Date, nullable=True, comment="结对起始日期")
    end_date = Column(Date, nullable=True, comment="结对结束日期")
    status = Column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        comment="状态: active=帮扶中 / ended=已结束",
    )
    note = Column(String(500), comment="备注")
    # 数据权限字段
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )
    created_by = Column(Integer, nullable=True, comment="创建者ID")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效（软删除标记）")
    deleted_at = Column(UtcDateTime(), nullable=True, comment="软删时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self):
        return f"<PairingRecord(id={self.id}, subject={self.subject_name}, title={self.title})>"

    def to_dict(self):
        return {
            "id": self.id,
            "subject_type": self.subject_type,
            "subject_name": self.subject_name,
            "subject_user_id": self.subject_user_id,
            "partner_type": self.partner_type,
            "village_id": self.village_id,
            "school_id": self.school_id,
            "student_name": self.student_name,
            "title": self.title,
            "content": self.content,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "note": self.note,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_active is False,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class VisitRecord(Base):
    """走访记录（挂靠结对记录）"""

    __tablename__ = "visit_records"

    __table_args__ = (
        Index("ix_visit_records_pairing_date", "pairing_id", "visit_date"),
        Index("ix_visit_records_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    pairing_id = Column(
        Integer,
        ForeignKey("pairing_records.id", ondelete="CASCADE"),
        nullable=False,
        comment="结对记录ID",
    )
    visit_date = Column(Date, nullable=False, comment="走访日期")
    visitors = Column(String(200), nullable=False, comment="走访人员（多人逗号分隔）")
    purpose = Column(String(200), comment="走访事项")
    content = Column(Text, comment="走访内容与结果")
    materials = Column(String(200), comment="慰问物资简记")
    # 数据权限字段（新建时从结对记录继承，保证与主表同域）
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属组织ID",
    )
    created_by = Column(Integer, nullable=True, comment="创建者ID")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否有效（软删除标记）")
    deleted_at = Column(UtcDateTime(), nullable=True, comment="软删时间")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        UtcDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self):
        return f"<VisitRecord(id={self.id}, pairing_id={self.pairing_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "pairing_id": self.pairing_id,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "visitors": self.visitors,
            "purpose": self.purpose,
            "content": self.content,
            "materials": self.materials,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "is_deleted": self.is_active is False,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
