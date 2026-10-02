"""工作日志模型"""

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func

from .base import Base, UtcDateTime


class WorkLog(Base):
    """帮扶工作日志"""

    __tablename__ = "work_logs"

    __table_args__ = (
        Index("ix_wl_user_id", "user_id"),
        Index("ix_wl_project_id", "project_id"),
        Index("ix_wl_village_id", "village_id"),
        Index("ix_wl_log_date", "log_date"),
        Index("idx_work_logs_user_date", "user_id", "log_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="记录人ID(用户删除后置空，日志留痕保留)",
    )
    log_date = Column(Date, nullable=False, comment="工作日期")
    content = Column(Text, nullable=False, comment="工作内容")
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联项目ID",
    )
    village_id = Column(
        Integer,
        ForeignKey("supported_villages.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联帮扶村ID",
    )
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联学校ID",
    )
    category = Column(
        String(50),
        nullable=True,
        comment="工作类别: visit/meeting/inspection/training/other",
    )
    location = Column(String(200), nullable=True, comment="工作地点")
    participants = Column(String(500), nullable=True, comment="参与人员(逗号分隔)")
    attachments = Column(Text, nullable=True, comment="附件路径(JSON数组)")
    created_at = Column(UtcDateTime(), server_default=func.now(), nullable=False)
    updated_at = Column(UtcDateTime(), server_default=func.now(), onupdate=func.now())

    # 兼容前端字段的属性
    @hybrid_property
    def title(self):
        """标题（从 content 截取）"""
        return self.content[:100] if self.content else ""

    @hybrid_property
    def work_date(self):
        """工作日期（兼容字段）"""
        return self.log_date

    @hybrid_property
    def log_type(self):
        """日志类型（兼容字段）"""
        return self.category or "daily"

    def __repr__(self):
        return f"<WorkLog(id={self.id}, date={self.log_date}, user_id={self.user_id})>"
