"""
经费历史记录模型
用于记录经费的状态变更、字段修改等历史信息

注：三张历史/日志表的 fund_id 均为 NOT NULL + ON DELETE CASCADE。删除经费时须由
数据库级联清理，ORM 不得先把 fund_id 置空（非空列置空 → IntegrityError），故各
fund 关系统一配置 cascade="all, delete-orphan" + passive_deletes=True。
"""

from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from .base import Base, UtcDateTime

from .fund import Fund  # noqa: F401 - relationship 字符串引用注册
from .user import User  # noqa: F401 - relationship 字符串引用注册


class FundStatusHistory(Base):
    """经费状态变更历史"""

    __tablename__ = "fund_status_history"

    __table_args__ = (
        Index("ix_fund_status_history_fund_id", "fund_id"),
        Index("ix_fund_status_history_operation_time", "operation_time"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        comment="经费记录ID",
    )
    from_status = Column(String(50), nullable=True, comment="原状态")
    to_status = Column(String(50), nullable=False, comment="新状态")
    operator_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人ID",
    )
    operator_name = Column(String(100), nullable=True, comment="操作人姓名")
    # 列声明为 timezone=True 却写 naive utcnow：会话时区不同即静默偏移；
    # 且 datetime.utcnow 在 3.12+ 已废弃（深审 LIVE）。统一写 aware UTC。
    operation_time = Column(
        UtcDateTime(), default=lambda: datetime.now(timezone.utc), comment="操作时间"
    )
    remark = Column(String(500), nullable=True, comment="操作备注/原因")

    # 关联
    fund = relationship(
        "Fund",
        backref=backref("status_histories", cascade="all, delete-orphan", passive_deletes=True),
    )
    operator = relationship("User", foreign_keys=[operator_id])

    def to_dict(self):
        return {
            "id": self.id,
            "fund_id": self.fund_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "operation_time": (self.operation_time.isoformat() if self.operation_time else None),
            "remark": self.remark,
        }


class FundFieldChange(Base):
    """经费字段变更记录"""

    __tablename__ = "fund_field_changes"

    __table_args__ = (
        Index("ix_fund_field_changes_fund_id", "fund_id"),
        Index("ix_fund_field_changes_changed_at", "changed_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        comment="经费记录ID",
    )
    field_name = Column(String(50), nullable=False, comment="字段名")
    old_value = Column(Text, nullable=True, comment="旧值(JSON序列化)")
    new_value = Column(Text, nullable=True, comment="新值(JSON序列化)")
    changed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="修改人ID",
    )
    changed_by_name = Column(String(100), nullable=True, comment="修改人姓名")
    changed_at = Column(
        UtcDateTime(), default=lambda: datetime.now(timezone.utc), comment="修改时间"
    )

    # 关联
    fund = relationship(
        "Fund",
        backref=backref("field_changes", cascade="all, delete-orphan", passive_deletes=True),
    )
    changer = relationship("User", foreign_keys=[changed_by])

    def to_dict(self):
        return {
            "id": self.id,
            "fund_id": self.fund_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "changed_by_name": self.changed_by_name,
            "changed_at": (self.changed_at.isoformat() if self.changed_at else None),
        }


class FundOperationLog(Base):
    """经费操作日志（用于记录附件上传、删除等操作）"""

    __tablename__ = "fund_operation_logs"

    __table_args__ = (
        Index("ix_fund_operation_logs_fund_id", "fund_id"),
        Index("ix_fund_operation_logs_created_at", "created_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        comment="经费记录ID",
    )
    operation_type = Column(
        String(50),
        nullable=False,
        comment="操作类型: attachment_upload/attachment_delete/...",
    )
    operation_detail = Column(Text, nullable=True, comment="操作详情(JSON格式)")
    operator_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作人ID",
    )
    operator_name = Column(String(100), nullable=True, comment="操作人姓名")
    created_at = Column(UtcDateTime(), server_default=func.now(), comment="操作时间")

    # 关联
    fund = relationship(
        "Fund",
        backref=backref("operation_logs", cascade="all, delete-orphan", passive_deletes=True),
    )
    operator = relationship("User", foreign_keys=[operator_id])

    def to_dict(self):
        return {
            "id": self.id,
            "fund_id": self.fund_id,
            "operation_type": self.operation_type,
            "operation_detail": self.operation_detail,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "created_at": (self.created_at.isoformat() if self.created_at else None),
        }
