"""
学校管理数据模型
"""

import enum

from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from .base import Base


class SchoolLevel(str, enum.Enum):
    """学校级别"""

    PROVINCIAL = "provincial"  # 省级
    MUNICIPAL = "municipal"  # 市级
    COUNTY = "county"  # 县级
    TOWNSHIP = "township"  # 乡镇级
    OTHER = "other"  # 其他


class SchoolType(str, enum.Enum):
    """学校类型"""

    PRIMARY = "primary"  # 小学
    MIDDLE = "middle"  # 初中
    HIGH = "high"  # 高中
    VOCATIONAL = "vocational"  # 职业学校
    OTHER = "other"  # 其他


class SupportStatus(str, enum.Enum):
    """帮扶状态"""

    ACTIVE = "active"  # 帮扶中
    INACTIVE = "inactive"  # 未帮扶
    COMPLETED = "completed"  # 已完成


class School(Base):
    """学校模型"""

    __tablename__ = "schools"

    __table_args__ = (
        Index("ix_schools_name", "name"),
        Index("ix_schools_type", "type"),
        Index("ix_schools_support_status", "support_status"),
        Index("ix_schools_district", "district"),
        Index("ix_schools_is_active", "is_active"),
        Index("ix_schools_support_unit", "support_unit"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="学校名称")
    code = Column(String(50), unique=True, comment="学校编码")
    type = Column(
        # validate_strings=False：写入由 Pydantic schema 校验，读取端容忍
        # 历史脏数据/手工修复数据（此前单条非法枚举值会令整个列表端点 500）
        SQLEnum(SchoolType, native_enum=False, validate_strings=False),
        default=SchoolType.PRIMARY,
        comment="学校类型",
    )

    # 地理位置
    province = Column(String(50), comment="省份")
    city = Column(String(50), comment="城市")
    district = Column(String(50), comment="区县")
    address = Column(String(500), comment="详细地址")
    latitude = Column(Float, nullable=True, comment="纬度")
    longitude = Column(Float, nullable=True, comment="经度")

    # 基本信息
    student_count = Column(Integer, default=0, comment="学生人数")
    teacher_count = Column(Integer, default=0, comment="教师人数")
    class_count = Column(Integer, default=0, comment="班级数量")
    established_year = Column(Integer, comment="建校年份")

    # 帮扶信息
    support_status = Column(
        SQLEnum(SupportStatus, native_enum=False, validate_strings=False),
        default=SupportStatus.INACTIVE,
        comment="帮扶状态",
    )
    support_unit = Column(String(200), comment="帮扶单位")
    support_start_date = Column(DateTime(timezone=True), comment="帮扶开始日期")
    support_end_date = Column(DateTime(timezone=True), comment="帮扶结束日期")

    # 联系信息
    principal = Column(String(50), comment="校长姓名")
    contact_phone = Column(String(20), comment="联系电话")
    email = Column(String(100), comment="邮箱")

    # 其他
    description = Column(Text, comment="学校简介")
    remarks = Column(Text, comment="备注")
    is_active = Column(Boolean, default=True, comment="是否启用")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="软删时间(回收站保留期计算依据)")

    # 数据权限字段
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属组织ID",
    )
    created_by = Column(Integer, nullable=True, index=True, comment="创建者ID")

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def __repr__(self):
        return f"<School(id={self.id}, name={self.name})>"

    def to_dict(self):
        """转换为字典（同时提供 camelCase 和 snake_case 键以兼容前端）"""
        _support_status = self.support_status.value if self.support_status else None
        _type = self.type.value if self.type else None
        _created = self.created_at.isoformat() if self.created_at else None
        _updated = self.updated_at.isoformat() if self.updated_at else None
        _start = self.support_start_date.isoformat() if self.support_start_date else None
        _end = self.support_end_date.isoformat() if self.support_end_date else None
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "type": _type,
            "province": self.province,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "region": f"{self.province or ''}{self.city or ''}{self.district or ''}",
            "principal": self.principal,
            "email": self.email,
            "description": self.description,
            "remarks": self.remarks,
            # snake_case (前端使用)
            "student_count": self.student_count,
            "teacher_count": self.teacher_count,
            "class_count": self.class_count,
            "established_year": self.established_year,
            "support_status": _support_status,
            "support_unit": self.support_unit,
            "support_start_date": _start,
            "support_end_date": _end,
            "contact_phone": self.contact_phone,
            "is_active": self.is_active,
            "is_deleted": self.is_active is False,
            "created_at": _created,
            "updated_at": _updated,
            # camelCase (兼容)
            "status": _support_status,
            "studentCount": self.student_count,
            "teacherCount": self.teacher_count,
            "classCount": self.class_count,
            "establishedYear": self.established_year,
            "supportStatus": _support_status,
            "supportUnit": self.support_unit,
            "supportStartDate": _start,
            "supportEndDate": _end,
            "contactPhone": self.contact_phone,
            "isActive": self.is_active,
            "createdAt": _created,
            "updatedAt": _updated,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class SchoolAttachment(Base):
    """学校电子资料附件"""

    __tablename__ = "school_attachments"

    __table_args__ = (
        Index("ix_school_attachments_school_id", "school_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        comment="学校ID",
    )
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="存储路径")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    file_type = Column(String(50), comment="文件MIME类型")
    description = Column(String(500), comment="文件说明")
    uploaded_by = Column(String(50), comment="上传人")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="上传时间")

    def to_dict(self):
        return {
            "id": self.id,
            "school_id": self.school_id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "description": self.description,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SchoolSupport(Base):
    """学校帮扶记录"""

    __tablename__ = "school_supports"

    __table_args__ = (
        Index("ix_school_supports_school_id", "school_id"),
        Index("ix_school_supports_support_date", "support_date"),
        Index("ix_school_supports_support_type", "support_type"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        comment="学校ID",
    )
    support_type = Column(String(50), comment="帮扶类型")
    amount = Column(Integer, default=0, comment="帮扶金额")
    description = Column(Text, comment="描述")
    support_date = Column(DateTime(timezone=True), comment="帮扶日期")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")


class ProjectPhase(str, enum.Enum):
    """项目阶段"""

    RESEARCH = "research"  # 调研
    APPROVAL = "approval"  # 立项审批
    IMPLEMENTATION = "implementation"  # 实施
    ACCEPTANCE = "acceptance"  # 验收
    COMPLETED = "completed"  # 已完成


class SchoolProject(Base):
    """学校帮扶项目（助学兴教项目）"""

    __tablename__ = "school_projects"

    __table_args__ = (
        Index("ix_school_projects_school_id", "school_id"),
        Index("ix_school_projects_phase", "phase"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        comment="学校ID",
    )
    name = Column(String(200), nullable=False, comment="项目名称")
    phase = Column(
        SQLEnum(ProjectPhase, native_enum=False),
        default=ProjectPhase.RESEARCH,
        comment="项目阶段",
    )
    category = Column(String(100), comment="项目类别")
    budget = Column(Float, default=0, comment="预算金额(万元)")
    actual_cost = Column(Float, default=0, comment="实际投入(万元)")
    start_date = Column(DateTime(timezone=True), comment="开始日期")
    end_date = Column(DateTime(timezone=True), comment="结束日期")
    description = Column(Text, comment="项目描述")
    remarks = Column(Text, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "school_id": self.school_id,
            "name": self.name,
            "phase": self.phase.value if self.phase else None,
            "category": self.category,
            "budget": self.budget,
            "actual_cost": self.actual_cost,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "description": self.description,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScholarshipStatus(str, enum.Enum):
    """资助状态"""

    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已批准
    DISBURSED = "disbursed"  # 已发放
    COMPLETED = "completed"  # 已完成


class ScholarshipStudent(Base):
    """资助学生"""

    __tablename__ = "scholarship_students"

    __table_args__ = (
        Index("ix_scholarship_students_school_id", "school_id"),
        Index("ix_scholarship_students_year", "year"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        comment="学校ID",
    )
    student_name = Column(String(50), nullable=False, comment="学生姓名")
    grade = Column(String(50), comment="年级")
    year = Column(Integer, comment="资助年度")
    amount = Column(Float, default=0, comment="资助金额(元)")
    reason = Column(String(500), comment="资助原因")
    status = Column(
        SQLEnum(ScholarshipStatus, native_enum=False),
        default=ScholarshipStatus.PENDING,
        comment="资助状态",
    )
    contact_info = Column(String(100), comment="联系方式")
    remarks = Column(Text, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "school_id": self.school_id,
            "student_name": self.student_name,
            "grade": self.grade,
            "year": self.year,
            "amount": self.amount,
            "reason": self.reason,
            "status": self.status.value if self.status else None,
            "contact_info": self.contact_info,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
