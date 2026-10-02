"""
审计变更记录模型
记录数据变更的详细历史
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, ForeignKey, Integer, String

from app.models.base import Base, UtcDateTime


class AuditChange(Base):
    """审计变更记录表"""

    __tablename__ = "audit_changes"

    id = Column(Integer, primary_key=True, index=True)
    audit_log_id = Column(
        Integer,
        ForeignKey("audit_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name = Column(String(100), nullable=False)
    old_value = Column(JSON, nullable=True)  # 旧值
    new_value = Column(JSON, nullable=True)  # 新值
    change_type = Column(String(20), nullable=False)  # create/update/delete
    created_at = Column(UtcDateTime(), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<AuditChange(id={self.id}, field={self.field_name}, type={self.change_type})>"
